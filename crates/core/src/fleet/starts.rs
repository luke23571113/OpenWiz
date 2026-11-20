use std::time::Duration;

use serde::Serialize;

use crate::messaging::record::StoreError;
use crate::messaging::{InvalidRequest, OpId, sha256_hex};
use crate::model::Timestamp;
use crate::new_thread::operation::{
    NewThreadClient, NewThreadError, NewThreadReport, NewThreadResult, new_thread,
};
use crate::new_thread::outcome::{Gap, Outcome};
use crate::new_thread::record::NewThreadStore;
use crate::new_thread::status::{StatusResult, new_thread_status};
use crate::new_thread::{Binding, NEW_THREAD_BUDGET, NewThreadRequest, ProjectRef, Settings};
use crate::ops::Clock;
use crate::prompt::{PromptPayload, attachments_digest};

use super::model::{Commit, Number};

pub const START_RECORD_SCHEMA_ID: &str = "openwiz.start-record.v1";

pub const START_ID_DOMAIN: &str = "openwiz.start.v1:";

pub const START_ID_PREFIX: &str = "start-";

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Role {
    Builder,
    Reviewer,
}

impl Role {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Builder => "builder",
            Self::Reviewer => "reviewer",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(transparent)]
pub struct Repository(String);

impl Repository {
    pub fn parse(text: &str) -> Result<Self, InvalidRequest> {
        let valid = text.split_once('/').is_some_and(|(owner, name)| {
            (1..=39).contains(&owner.len())
                && !owner.starts_with('-')
                && owner
                    .bytes()
                    .all(|b| b.is_ascii_alphanumeric() || b == b'-')
                && (1..=100).contains(&name.len())
                && name != "."
                && name != ".."
                && name
                    .bytes()
                    .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'.' | b'_' | b'-'))
        });
        if valid {
            Ok(Self(text.to_ascii_lowercase()))
        } else {
            Err(InvalidRequest(
                "a repository is owner/name, as GitHub names them".to_owned(),
            ))
        }
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct StartKey {
    repository: Repository,
    role: Role,
    number: Number,
    commit: Option<Commit>,
}

impl StartKey {
    pub fn builder(repository: Repository, ticket: Number) -> Self {
        Self {
            repository,
            role: Role::Builder,
            number: ticket,
            commit: None,
        }
    }

    pub fn reviewer(repository: Repository, pull_request: Number, commit: Commit) -> Self {
        Self {
            repository,
            role: Role::Reviewer,
            number: pull_request,
            commit: Some(commit),
        }
    }

    pub fn repository(&self) -> &Repository {
        &self.repository
    }

    pub fn role(&self) -> Role {
        self.role
    }

    pub fn number(&self) -> Number {
        self.number
    }

    pub fn commit(&self) -> Option<&Commit> {
        self.commit.as_ref()
    }

    pub fn id(&self) -> OpId {
        let key = match &self.commit {
            None => format!(
                "{}:{}#{}",
                self.role.as_str(),
                self.repository.0,
                self.number
            ),
            Some(commit) => format!(
                "{}:{}#{}@{}",
                self.role.as_str(),
                self.repository.0,
                self.number,
                commit.as_str()
            ),
        };
        let digest = sha256_hex(format!("{START_ID_DOMAIN}{key}").as_bytes());
        OpId::parse(&format!("{START_ID_PREFIX}{}", &digest[..40]))
            .expect("a prefix and hex digits make an op id")
    }
}

pub fn brief(key: &StartKey) -> String {
    match &key.commit {
        None => format!(
            "You are the builder for #{}. Read skills/build-ticket/SKILL.md and follow it.",
            key.number
        ),
        Some(commit) => format!(
            "You are the reviewer for pull request #{} at {}. Read skills/review-ticket/SKILL.md \
             and follow it.",
            key.number,
            commit.as_str()
        ),
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum AttemptOutcome {
    Pending,
    Created { thread_id: String },
    NotCreated { status: NotCreated, words: String },
    Uncertain { words: String },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum NotCreated {
    Refused,
    Failed,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Attempt {
    pub op_id: OpId,
    pub at: Timestamp,
    pub outcome: AttemptOutcome,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct StartRecord {
    schema: String,
    id: OpId,
    key: StartKey,
    project_id: String,
    settings: Settings,
    attempts: Vec<Attempt>,
}

impl StartRecord {
    fn first(request: &StartRequest, op_id: OpId, now: Timestamp) -> Self {
        Self {
            schema: START_RECORD_SCHEMA_ID.to_owned(),
            id: request.key.id(),
            key: request.key.clone(),
            project_id: request.project_id.clone(),
            settings: request.settings.clone(),
            attempts: vec![Attempt {
                op_id,
                at: now,
                outcome: AttemptOutcome::Pending,
            }],
        }
    }

    pub fn id(&self) -> &OpId {
        &self.id
    }

    pub fn key(&self) -> &StartKey {
        &self.key
    }

    pub fn project_id(&self) -> &str {
        &self.project_id
    }

    pub fn settings(&self) -> &Settings {
        &self.settings
    }

    pub fn attempts(&self) -> &[Attempt] {
        &self.attempts
    }

    fn last(&self) -> &Attempt {
        self.attempts.last().expect("a start record has an attempt")
    }

    fn settled(&self, outcome: AttemptOutcome) -> Self {
        let mut record = self.clone();
        if let Some(last) = record.attempts.last_mut() {
            last.outcome = outcome;
        }
        record
    }

    fn retried(&self, op_id: OpId, now: Timestamp) -> Self {
        let mut record = self.clone();
        record.attempts.push(Attempt {
            op_id,
            at: now,
            outcome: AttemptOutcome::Pending,
        });
        record
    }

    pub fn from_parts(
        id: OpId,
        key: StartKey,
        project_id: String,
        settings: Settings,
        attempts: Vec<Attempt>,
    ) -> Result<Self, String> {
        if id != key.id() {
            return Err("its id is not its key's".to_owned());
        }
        StartRequest::new(key.clone(), project_id.clone(), settings.clone())
            .validate()
            .map_err(|e| e.0)?;
        if attempts.is_empty() {
            return Err("it has no attempt".to_owned());
        }
        for (i, attempt) in attempts.iter().enumerate() {
            if attempts[..i].iter().any(|a| a.op_id == attempt.op_id) {
                return Err(format!("attempt {i}'s op id is given twice"));
            }
            if attempt.at.0 < 0 {
                return Err(format!("attempt {i}'s time is before 1970"));
            }
            let created_nothing = matches!(attempt.outcome, AttemptOutcome::NotCreated { .. });
            if i + 1 < attempts.len() && !created_nothing {
                return Err(format!(
                    "attempt {i} is not the last, so it must have created nothing"
                ));
            }
            if let AttemptOutcome::Created { thread_id } = &attempt.outcome
                && !safe_id(thread_id)
            {
                return Err(format!("attempt {i}'s thread id is not safe to pass"));
            }
        }
        Ok(Self {
            schema: START_RECORD_SCHEMA_ID.to_owned(),
            id,
            key,
            project_id,
            settings,
            attempts,
        })
    }
}

pub fn safe_id(id: &str) -> bool {
    (1..=128).contains(&id.len())
        && !id.starts_with('-')
        && id
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b == b'_' || b == b'-')
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Locked {
    Mine(Option<Box<StartRecord>>),
    Busy,
}

pub trait StartStore: Send + Sync {
    fn lock(&self, key: &StartKey) -> Result<Locked, StoreError>;

    fn write(&self, record: &StartRecord) -> Result<(), StoreError>;

    fn unlock(&self, key: &StartKey);

    fn inspect(&self, key: &StartKey) -> Result<Option<StartRecord>, StoreError>;
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StartRequest {
    pub key: StartKey,
    pub project_id: String,
    pub settings: Settings,
    pub budget: Duration,
}

impl StartRequest {
    pub fn new(key: StartKey, project_id: impl Into<String>, settings: Settings) -> Self {
        Self {
            key,
            project_id: project_id.into(),
            settings,
            budget: NEW_THREAD_BUDGET,
        }
    }

    pub fn validate(&self) -> Result<(), InvalidRequest> {
        if !safe_id(&self.project_id) {
            return Err(InvalidRequest(
                "the project id is 1 to 128 ASCII letters, digits, _ or -, not starting with -"
                    .to_owned(),
            ));
        }
        self.new_thread(self.key.id()).validate()
    }

    fn new_thread(&self, op_id: OpId) -> NewThreadRequest {
        let mut request = NewThreadRequest::new(
            ProjectRef::Id(self.project_id.clone()),
            self.settings.clone(),
            PromptPayload::text(brief(&self.key)),
            op_id,
        );
        request.budget = self.budget;
        request
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum StartField {
    Project,
    Harness,
    Model,
    Effort,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum StartOutcome {
    Started {
        thread_id: String,
        by_this_call: bool,
    },
    NotStarted {
        words: String,
    },
    Uncertain {
        words: String,
    },
    InProgress,
    Conflicting {
        differs: Vec<StartField>,
    },
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct StartReport {
    pub key: StartKey,
    pub op_id: Option<OpId>,
    pub outcome: StartOutcome,
    pub gaps: Vec<Gap>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum StartError {
    Invalid(InvalidRequest),
    Store(StoreError),
    OpId(String),
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Next {
    Attempt,
    Reconcile { op_id: OpId },
    Started { op_id: OpId, thread_id: String },
    Uncertain { op_id: OpId, words: String },
    Conflicting { differs: Vec<StartField> },
}

pub fn next_step(record: Option<&StartRecord>, request: &StartRequest) -> Next {
    let Some(record) = record else {
        return Next::Attempt;
    };
    let last = record.last();
    match &last.outcome {
        AttemptOutcome::Created { thread_id } => Next::Started {
            op_id: last.op_id.clone(),
            thread_id: thread_id.clone(),
        },
        AttemptOutcome::Uncertain { words } => Next::Uncertain {
            op_id: last.op_id.clone(),
            words: words.clone(),
        },
        AttemptOutcome::Pending => Next::Reconcile {
            op_id: last.op_id.clone(),
        },
        AttemptOutcome::NotCreated { .. } => match differences(record, request) {
            differs if differs.is_empty() => Next::Attempt,
            differs => Next::Conflicting { differs },
        },
    }
}

fn differences(record: &StartRecord, request: &StartRequest) -> Vec<StartField> {
    [
        (StartField::Project, record.project_id == request.project_id),
        (
            StartField::Harness,
            record.settings.harness == request.settings.harness,
        ),
        (
            StartField::Model,
            record.settings.model == request.settings.model,
        ),
        (
            StartField::Effort,
            record.settings.effort == request.settings.effort,
        ),
    ]
    .into_iter()
    .filter(|(_, same)| !same)
    .map(|(field, _)| field)
    .collect()
}

pub fn preview_start(starts: &dyn StartStore, request: &StartRequest) -> Result<Next, StoreError> {
    Ok(next_step(starts.inspect(&request.key)?.as_ref(), request))
}

pub fn start_agent(
    client: &dyn NewThreadClient,
    threads: &dyn NewThreadStore,
    starts: &dyn StartStore,
    clock: &dyn Clock,
    new_op_id: &dyn Fn() -> Result<OpId, String>,
    request: &StartRequest,
) -> Result<StartReport, StartError> {
    request.validate().map_err(StartError::Invalid)?;
    let Locked::Mine(record) = starts.lock(&request.key).map_err(StartError::Store)? else {
        return Ok(report(request, None, StartOutcome::InProgress, vec![]));
    };
    let record = record.map(|r| *r);
    let started = Start {
        client,
        threads,
        starts,
        clock,
        request,
    }
    .run(record, new_op_id);
    starts.unlock(&request.key);
    started
}

struct Start<'a> {
    client: &'a dyn NewThreadClient,
    threads: &'a dyn NewThreadStore,
    starts: &'a dyn StartStore,
    clock: &'a dyn Clock,
    request: &'a StartRequest,
}

impl Start<'_> {
    fn run(
        &self,
        record: Option<StartRecord>,
        new_op_id: &dyn Fn() -> Result<OpId, String>,
    ) -> Result<StartReport, StartError> {
        if let Some(r) = &record
            && r.key != self.request.key
        {
            return Err(StartError::Store(StoreError(
                "the start record holds another start".to_owned(),
            )));
        }
        let record = match next_step(record.as_ref(), self.request) {
            Next::Started { op_id, thread_id } => {
                let started = StartOutcome::Started {
                    thread_id,
                    by_this_call: false,
                };
                return Ok(report(self.request, Some(op_id), started, vec![]));
            }
            Next::Uncertain { op_id, words } => {
                let uncertain = StartOutcome::Uncertain { words };
                return Ok(report(self.request, Some(op_id), uncertain, vec![]));
            }
            Next::Conflicting { differs } => return Ok(self.conflicting(differs)),
            Next::Reconcile { op_id } => {
                let record = record.expect("a pending attempt has a record");
                let reconciled = self.reconcile(&record, &op_id)?;
                let differs = differences(&record, self.request);
                match reconciled {
                    Reconciled::Done(report) => return Ok(report),
                    Reconciled::NothingSent | Reconciled::NotCreated(_) if !differs.is_empty() => {
                        return Ok(self.conflicting(differs));
                    }
                    Reconciled::NothingSent => return self.call(&record, op_id),
                    Reconciled::NotCreated(settled) => Some(settled),
                }
            }
            Next::Attempt => record,
        };
        let op_id = new_op_id().map_err(StartError::OpId)?;
        if let Some(r) = &record
            && r.attempts.iter().any(|a| a.op_id == op_id)
        {
            return Err(StartError::OpId(
                "the new op id was used before for this start".to_owned(),
            ));
        }
        let now = self.clock.now();
        let pending = match &record {
            None => StartRecord::first(self.request, op_id.clone(), now),
            Some(r) => r.retried(op_id.clone(), now),
        };
        self.starts.write(&pending).map_err(StartError::Store)?;
        self.call(&pending, op_id)
    }

    fn conflicting(&self, differs: Vec<StartField>) -> StartReport {
        report(
            self.request,
            None,
            StartOutcome::Conflicting { differs },
            vec![],
        )
    }

    fn reconcile(&self, record: &StartRecord, op_id: &OpId) -> Result<Reconciled, StartError> {
        let status = new_thread_status(
            self.client,
            self.threads,
            self.clock,
            op_id,
            self.request.budget,
        )
        .map_err(StartError::Store)?;
        let StatusResult::Recorded(found) = status.result else {
            return Ok(Reconciled::NothingSent);
        };
        if !binds(record, op_id, &found.report) {
            return Ok(Reconciled::Done(self.not_ours(record)));
        }
        let outcome = match found.report.result {
            NewThreadResult::Outcome { outcome, .. } => outcome,
            NewThreadResult::InProgress { .. } => {
                let in_progress = report(
                    self.request,
                    Some(op_id.clone()),
                    StartOutcome::InProgress,
                    vec![],
                );
                return Ok(Reconciled::Done(in_progress));
            }
            NewThreadResult::ConflictingReuse { .. } => {
                return Ok(Reconciled::Done(self.not_ours(record)));
            }
        };
        let (settled, started) = self.settle(record, op_id, &outcome, false);
        if let AttemptOutcome::NotCreated { .. } = settled.last().outcome {
            self.starts.write(&settled).map_err(StartError::Store)?;
            return Ok(Reconciled::NotCreated(settled));
        }
        Ok(Reconciled::Done(self.record_outcome(&settled, started)))
    }

    fn call(&self, record: &StartRecord, op_id: OpId) -> Result<StartReport, StartError> {
        let made = new_thread(
            self.client,
            self.threads,
            self.clock,
            &self.request.new_thread(op_id.clone()),
        );
        let result = match made {
            Ok(made) => made.result,
            Err(NewThreadError::Invalid(e)) => return Err(StartError::Invalid(e)),
            Err(NewThreadError::Store(e)) => return Err(StartError::Store(e)),
        };
        let outcome = match result {
            NewThreadResult::Outcome {
                outcome, replayed, ..
            } => (outcome, !replayed),
            NewThreadResult::InProgress { .. } => {
                let in_progress = StartOutcome::InProgress;
                return Ok(report(self.request, Some(op_id), in_progress, vec![]));
            }
            NewThreadResult::ConflictingReuse { .. } => return Ok(self.not_ours(record)),
        };
        let (settled, started) = self.settle(record, &op_id, &outcome.0, outcome.1);
        Ok(self.record_outcome(&settled, started))
    }

    fn settle(
        &self,
        record: &StartRecord,
        op_id: &OpId,
        outcome: &Outcome,
        by_this_call: bool,
    ) -> (StartRecord, StartOutcome) {
        let words = outcome.text().to_owned();
        let (attempt, started) = match outcome {
            Outcome::Created { thread_id, .. } => (
                AttemptOutcome::Created {
                    thread_id: thread_id.clone(),
                },
                StartOutcome::Started {
                    thread_id: thread_id.clone(),
                    by_this_call,
                },
            ),
            Outcome::Refused { .. } | Outcome::Failed { .. } => {
                let status = if matches!(outcome, Outcome::Refused { .. }) {
                    NotCreated::Refused
                } else {
                    NotCreated::Failed
                };
                (
                    AttemptOutcome::NotCreated {
                        status,
                        words: words.clone(),
                    },
                    StartOutcome::NotStarted { words },
                )
            }
            Outcome::Uncertain { .. } => (
                AttemptOutcome::Uncertain {
                    words: words.clone(),
                },
                StartOutcome::Uncertain { words },
            ),
        };
        debug_assert_eq!(&record.last().op_id, op_id);
        (record.settled(attempt), started)
    }

    fn not_ours(&self, record: &StartRecord) -> StartReport {
        let words = "its op id holds another start's create, so nothing was sent for this start \
                     under it; the next start uses a new op id"
            .to_owned();
        let settled = record.settled(AttemptOutcome::NotCreated {
            status: NotCreated::Failed,
            words: words.clone(),
        });
        self.record_outcome(&settled, StartOutcome::NotStarted { words })
    }

    fn record_outcome(&self, settled: &StartRecord, started: StartOutcome) -> StartReport {
        let mut gaps = vec![];
        if let Err(e) = self.starts.write(settled) {
            gaps.push(Gap {
                subject: "start record".to_owned(),
                detail: format!(
                    "what came of the start could not be recorded ({e}); the next start reads \
                     its status first"
                ),
            });
        }
        let op_id = settled.last().op_id.clone();
        report(self.request, Some(op_id), started, gaps)
    }
}

fn binds(record: &StartRecord, op_id: &OpId, report: &NewThreadReport) -> bool {
    let request = StartRequest::new(
        record.key.clone(),
        record.project_id.clone(),
        record.settings.clone(),
    );
    let own = Binding::new(&request.new_thread(op_id.clone()), attachments_digest(&[]));
    report.project_ref == own.project
        && report.requested.harness == own.harness
        && report.requested.model == own.model
        && report.requested.effort == own.effort
        && report.text_sha256 == own.text_sha256
        && report.attachments_digest == own.attachments_digest
        && report.attachments.is_empty()
}

enum Reconciled {
    Done(StartReport),
    NothingSent,
    NotCreated(StartRecord),
}

fn report(
    request: &StartRequest,
    op_id: Option<OpId>,
    outcome: StartOutcome,
    gaps: Vec<Gap>,
) -> StartReport {
    StartReport {
        key: request.key.clone(),
        op_id,
        outcome,
        gaps,
    }
}
