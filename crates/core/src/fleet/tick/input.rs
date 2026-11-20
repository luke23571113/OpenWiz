use super::super::model::{
    Check, Commit, Issue, IssueState, MergedPr, NonEmpty, Number, PrFields, Review,
};
use serde::Serialize;
use std::collections::BTreeMap;

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Observed<T> {
    Complete(T),
    Unread(Vec<Problem>),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum Problem {
    Issue,
    Approval,
    Graph,
    Blockers,
    PullRequest,
    Checks,
    Reports,
    Agents,
    Starts,
    Records,
    Contracts,
    FollowUps,
}

impl Problem {
    pub(crate) fn reason(self) -> &'static str {
        match self {
            Self::Issue => "issue unread",
            Self::Approval => "approval unread",
            Self::Graph => "graph unread",
            Self::Blockers => "blockers unread",
            Self::PullRequest => "pull request unread",
            Self::Checks => "checks unread",
            Self::Reports => "reports unread",
            Self::Agents => "agents unread",
            Self::Starts => "starts unread",
            Self::Records => "records unread",
            Self::Contracts => "contracts unread",
            Self::FollowUps => "follow-ups unread",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(transparent)]
pub struct Fingerprint(String);
impl Fingerprint {
    pub fn parse(s: &str) -> Option<Self> {
        (s.len() == 64
            && s.bytes()
                .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b)))
        .then(|| Self(s.to_owned()))
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Approval {
    pub comment: Number,
    pub revision: Number,
    pub fingerprint: Fingerprint,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Ready {
    Agent,
    Human,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PlanApproval {
    pub approval: Approval,
    pub rows: BTreeMap<Number, Ready>,
    pub approved_at: u64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Snapshot {
    pub default_branch: Observed<NonEmpty>,
    pub fleets: Observed<Vec<FleetInput>>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FleetInput {
    pub spec: Number,
    pub facts: Observed<FleetFacts>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FleetFacts {
    pub issue: Issue,
    pub approval: Option<PlanApproval>,
    pub fingerprint_now: Fingerprint,
    pub tickets: Vec<TicketInput>,
    pub changes: Vec<ContractChange>,
    pub follow_ups: Vec<Number>,
    pub records: SpecRecords,
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct SpecRecords {
    pub summary_written: bool,
    pub approval_notified: Vec<Fingerprint>,
    pub looked: Vec<String>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TicketInput {
    pub number: Number,
    pub facts: Observed<TicketFacts>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TicketFacts {
    pub issue: Issue,
    pub blockers: Vec<BlockerInput>,
    pub pr: Option<PrInput>,
    pub builder: Option<Agent>,
    pub builder_source: Option<BuilderSource>,
    pub reviewers: Vec<Reviewer>,
    pub starts: Vec<Start>,
    pub relies_on: Vec<NonEmpty>,
    pub holds: Vec<Hold>,
    pub held_label_comment: Option<Number>,
    pub question: Option<Number>,
    pub records: TicketRecords,
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct TicketRecords {
    pub archived: bool,
    pub builder_fallback_due: bool,
    pub question_passed: Option<Number>,
    pub person_notified: bool,
    pub noted: Vec<Number>,
    pub looked: Vec<String>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BlockerInput {
    pub number: Number,
    pub state: IssueState,
    pub merged: Option<MergeInput>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct MergeInput {
    pub pr: MergedPr,
    pub read_back: bool,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum PrInput {
    Open(Box<OpenPr>),
    Merged(MergeInput),
    Several(Vec<Number>),
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct OpenPr {
    pub fields: PrFields,
    pub subject: String,
    pub ci: Option<CheckRun>,
    pub base_now: Option<Commit>,
    pub reports: Vec<ReportComment>,
    pub starts: Vec<Start>,
    pub records: PrRecords,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CheckRun {
    pub head_commit: Commit,
    pub base_commit: Commit,
    pub checks: Vec<Check>,
}

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct PrRecords {
    pub findings_sent: Vec<Commit>,
    pub ci_sent: Vec<Commit>,
    pub recheck_sent: Vec<Commit>,
    pub dispute_asked: Vec<Commit>,
    pub diagnosis_asked: Vec<Commit>,
    pub merge_blocked: Vec<Commit>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ReportComment {
    pub comment: Number,
    pub text: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Reviewer {
    pub pr: Number,
    pub agent: Agent,
    pub head: Commit,
    pub last_activity_at: u64,
    pub given_up: bool,
    pub output: Option<Review>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Agent {
    pub thread: NonEmpty,
    pub archived: bool,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Start {
    pub id: crate::messaging::OpId,
    pub state: StartState,
    pub logged: bool,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum StartState {
    Pending,
    Uncertain,
    Started { thread: NonEmpty },
    Refused { reason: StartReason },
    Failed { reason: StartReason },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum StartReason {
    Refused,
    Interrupted,
}
impl StartReason {
    pub(crate) fn text(self) -> &'static str {
        match self {
            Self::Refused => "the configured agent was refused",
            Self::Interrupted => "the start failed before a thread was made",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct MergeFact {
    pub number: Number,
    pub merge_commit: Commit,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Hold {
    pub comment: Number,
    pub merged: MergeFact,
    pub files: Vec<NonEmpty>,
    pub notified: bool,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ContractChange {
    pub merged: MergeInput,
    pub files: Vec<ChangedFile>,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ChangedFile {
    pub path: NonEmpty,
    pub previous_path: Option<NonEmpty>,
    pub added: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum BuilderFamily {
    Claude,
    Gpt,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BuilderSource {
    pub thread: NonEmpty,
    pub branch: NonEmpty,
    pub family: BuilderFamily,
    pub plan_limit: bool,
}
