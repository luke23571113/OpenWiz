use std::collections::{BTreeMap, BTreeSet};
use std::sync::Mutex;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::thread;
use std::time::{Duration, Instant};

use super::model::{
    Blocker, Check, CheckResult, CloudRoomSource, Commit, Counts, Coverage, Envelope, Failed,
    Fleet, FleetView, Freshness, Gh, GitHubSource, Issue, IssueState, ListOutcome, MergedPr,
    NeedsYou, NeedsYouKind, NonEmpty, Number, Outcome, PrFields, Project, PullRequest, Read,
    ReadId, ReadKind, Repository, Review, Reviewer, RoomCli, SchemaId, SourceName, Sources, State,
    Thread, Ticket, TicketCore, TicketState, Truncated, Unplaced, Verdict, View, WorkedOut,
};
use crate::envelope::{Completeness, GapKind};
use crate::model::Timestamp;
use crate::ops::Clock;
use crate::source::SourceError;

pub const MAX_CONCURRENT_READS: usize = 4;

pub const AGENTS_NOT_READ: &str = "not read: a ticket's agents come with A6 (#114)";

pub const NO_REVIEWER_CHAIN: &str = "no verified chain places a reviewer in version 1";

pub const READY_FOR_AGENT: &str = "ready-for-agent";
pub const READY_FOR_HUMAN: &str = "ready-for-human";
pub const HELD: &str = "held";
pub const NEEDS_INFO: &str = "needs-info";

pub trait GitHub: Send + Sync {
    fn version(&self, deadline: Instant) -> Result<String, SourceError>;
    fn repository(&self, deadline: Instant) -> Result<RepositoryAnswer, SourceError>;
    fn issue(&self, number: Number, deadline: Instant) -> Result<IssueAnswer, SourceError>;
    fn stock_issue(
        &self,
        number: Number,
        deadline: Instant,
    ) -> Result<(IssueAnswer, crate::model::Fact<bool>), SourceError> {
        self.issue(number, deadline).map(|i| {
            (
                i,
                crate::model::Fact::Unknown(
                    "Recorded-start evidence is not retained by this provider".into(),
                ),
            )
        })
    }
    fn pull_request(&self, number: Number, deadline: Instant) -> Result<PrAnswer, SourceError>;
    fn checks(&self, pr: Number, deadline: Instant) -> Result<Vec<Check>, SourceError>;
    fn verdict_comments(&self, pr: Number, deadline: Instant) -> Result<Vec<String>, SourceError>;
    fn on_base(
        &self,
        commit: &Commit,
        base: &NonEmpty,
        deadline: Instant,
    ) -> Result<bool, SourceError>;
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RepositoryAnswer {
    pub name: NonEmpty,
    pub name_with_owner: NonEmpty,
    pub url: NonEmpty,
}

pub trait Agents: Send + Sync {
    fn read(&self, repository: Option<&RepositoryAnswer>, deadline: Instant) -> AgentReads;
    fn place(&self, spec: Number, tickets: &[Number], reads: &[Read]) -> Placed;
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AgentReads {
    pub version: Outcome<NonEmpty>,
    pub projects: ListOutcome<Project>,
    pub threads: ListOutcome<Thread>,
    pub workspaces: Vec<(NonEmpty, Outcome<NonEmpty>)>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Placed {
    pub builders: Vec<WorkedOut<Option<NonEmpty>>>,
    pub unplaced: WorkedOut<Vec<Unplaced>>,
}

#[derive(Clone, Copy, Debug, Default)]
pub struct NotRead;

impl Agents for NotRead {
    fn read(&self, _repository: Option<&RepositoryAnswer>, _deadline: Instant) -> AgentReads {
        AgentReads {
            version: Outcome::Failed(agents_not_read()),
            projects: ListOutcome::Failed(agents_not_read()),
            threads: ListOutcome::Failed(agents_not_read()),
            workspaces: Vec::new(),
        }
    }

    fn place(&self, spec: Number, tickets: &[Number], reads: &[Read]) -> Placed {
        let requires: Requires = reads
            .iter()
            .filter(|read| match &read.kind {
                ReadKind::Projects { .. } | ReadKind::Threads { .. } => true,
                ReadKind::Workspace { .. } => true,
                ReadKind::SubIssues { spec: s, .. } => *s == spec,
                ReadKind::PrDiscovery { issue, .. } => tickets.contains(issue),
                _ => false,
            })
            .map(|read| read.id)
            .collect();
        let records = Records::new(reads);
        Placed {
            builders: tickets
                .iter()
                .map(|_| records.worked_out(&requires, || None))
                .collect(),
            unplaced: records.worked_out(&requires, Vec::new),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Link {
    pub number: Number,
    pub url: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ListAnswer {
    pub nodes: Vec<Link>,
    pub total: u64,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct IssueAnswer {
    pub issue: Issue,
    pub sub_issues: ListAnswer,
    pub blocked_by: ListAnswer,
    pub closed_by: Vec<Link>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PrAnswer {
    pub number: Number,
    pub draft: bool,
    pub head_branch: NonEmpty,
    pub head_commit: Commit,
    pub base_branch: NonEmpty,
    pub state: PrState,
    pub closes: Vec<Link>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum PrState {
    Open,
    Closed,
    Merged {
        merge_commit: Commit,
        merged_at: Timestamp,
    },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct FleetRequest {
    pub spec: Number,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TestedVersions<'a> {
    pub github: &'a str,
    pub cloudroom: &'a str,
}

pub fn fleet(
    request: FleetRequest,
    github: &dyn GitHub,
    agents: &dyn Agents,
    tested: TestedVersions<'_>,
    clock: &dyn Clock,
    budget: Duration,
) -> Envelope {
    let snapshot_at = clock.now();
    let run = Run {
        github,
        agents,
        clock,
        deadline: clock.monotonic() + budget,
    };
    let answers = run.read_all(request.spec);
    Assembly::new(request.spec, &answers).envelope(agents, tested, snapshot_at)
}

#[derive(Clone, Debug, PartialEq, Eq)]
enum Miss {
    Source(SourceError),
    Budget,
}

type Answer<T> = Result<T, Miss>;

struct Run<'a> {
    github: &'a dyn GitHub,
    agents: &'a dyn Agents,
    clock: &'a dyn Clock,
    deadline: Instant,
}

struct Answers {
    version: Answer<String>,
    repository: Answer<RepositoryAnswer>,
    issues: BTreeMap<Number, Answer<IssueAnswer>>,
    prs: BTreeMap<Number, Answer<PrAnswer>>,
    checks: BTreeMap<Number, Answer<Vec<Check>>>,
    verdicts: BTreeMap<Number, Answer<Vec<String>>>,
    on_base: BTreeMap<Number, Answer<bool>>,
    agents: AgentReads,
}

#[derive(Clone)]
enum Job {
    Version,
    Repository,
    Issue(Number),
    Pr(Number),
    Checks(Number),
    Verdicts(Number),
    OnBase(Number, Commit, NonEmpty),
}

enum Got {
    Version(Answer<String>),
    Repository(Answer<RepositoryAnswer>),
    Issue(Number, Answer<IssueAnswer>),
    Pr(Number, Answer<PrAnswer>),
    Checks(Number, Answer<Vec<Check>>),
    Verdicts(Number, Answer<Vec<String>>),
    OnBase(Number, Answer<bool>),
}

impl Run<'_> {
    fn call<T>(&self, read: impl FnOnce(Instant) -> Result<T, SourceError>) -> Answer<T> {
        if self.clock.monotonic() >= self.deadline {
            return Err(Miss::Budget);
        }
        read(self.deadline).map_err(Miss::Source)
    }

    fn job(&self, job: &Job) -> Got {
        let gh = self.github;
        match *job {
            Job::Version => Got::Version(self.call(|d| gh.version(d))),
            Job::Repository => Got::Repository(self.call(|d| gh.repository(d))),
            Job::Issue(n) => Got::Issue(n, self.call(|d| gh.issue(n, d))),
            Job::Pr(n) => Got::Pr(n, self.call(|d| gh.pull_request(n, d))),
            Job::Checks(n) => Got::Checks(n, self.call(|d| gh.checks(n, d))),
            Job::Verdicts(n) => Got::Verdicts(n, self.call(|d| gh.verdict_comments(n, d))),
            Job::OnBase(n, ref commit, ref base) => {
                Got::OnBase(n, self.call(|d| gh.on_base(commit, base, d)))
            }
        }
    }

    fn parallel<J: Sync, T: Send>(&self, jobs: &[J], work: impl Fn(&J) -> T + Sync) -> Vec<T> {
        let next = AtomicUsize::new(0);
        let results: Vec<Mutex<Option<T>>> = jobs.iter().map(|_| Mutex::new(None)).collect();
        thread::scope(|scope| {
            for _ in 0..MAX_CONCURRENT_READS.min(jobs.len()) {
                scope.spawn(|| {
                    loop {
                        let i = next.fetch_add(1, Ordering::SeqCst);
                        let Some(job) = jobs.get(i) else { break };
                        let got = work(job);
                        *results[i].lock().unwrap_or_else(|p| p.into_inner()) = Some(got);
                    }
                });
            }
        });
        results
            .into_iter()
            .map(|r| {
                r.into_inner()
                    .unwrap_or_else(|p| p.into_inner())
                    .expect("every job ran")
            })
            .collect()
    }

    fn jobs(&self, jobs: &[Job], answers: &mut Answers) {
        for got in self.parallel(jobs, |job| self.job(job)) {
            match got {
                Got::Version(a) => answers.version = a,
                Got::Repository(a) => answers.repository = a,
                Got::Issue(n, a) => {
                    answers.issues.insert(n, a);
                }
                Got::Pr(n, a) => {
                    answers.prs.insert(n, a);
                }
                Got::Checks(n, a) => {
                    answers.checks.insert(n, a);
                }
                Got::Verdicts(n, a) => {
                    answers.verdicts.insert(n, a);
                }
                Got::OnBase(n, a) => {
                    answers.on_base.insert(n, a);
                }
            }
        }
    }

    fn read_all(&self, spec: Number) -> Answers {
        let mut answers = Answers {
            version: Err(Miss::Budget),
            repository: Err(Miss::Budget),
            issues: BTreeMap::new(),
            prs: BTreeMap::new(),
            checks: BTreeMap::new(),
            verdicts: BTreeMap::new(),
            on_base: BTreeMap::new(),
            agents: NotRead.read(None, self.deadline),
        };
        self.jobs(
            &[Job::Version, Job::Repository, Job::Issue(spec)],
            &mut answers,
        );
        let repository = answers.repository.as_ref().ok().cloned();
        let (agents, mut answers) = thread::scope(|scope| {
            let agents = scope.spawn(|| self.agents.read(repository.as_ref(), self.deadline));
            let answers = self.read_github(spec, answers);
            (agents.join(), answers)
        });
        answers.agents = agents.unwrap_or_else(|panic| std::panic::resume_unwind(panic));
        answers
    }

    fn read_github(&self, spec: Number, mut answers: Answers) -> Answers {
        let tickets = Members::of(spec, &answers).tickets;
        let unread = |answers: &Answers, numbers: &BTreeSet<Number>| -> Vec<Job> {
            numbers
                .iter()
                .filter(|n| !answers.issues.contains_key(*n))
                .map(|&n| Job::Issue(n))
                .collect()
        };
        let jobs = unread(&answers, &tickets.iter().copied().collect());
        self.jobs(&jobs, &mut answers);
        let blockers = Members::of(spec, &answers).blockers;
        let jobs = unread(&answers, &blockers);
        self.jobs(&jobs, &mut answers);

        let members = Members::of(spec, &answers);
        let mut prs = BTreeSet::new();
        if let Ok(repository) = &answers.repository {
            for n in members.discovered() {
                if let Some(Ok(issue)) = answers.issues.get(&n) {
                    prs.extend(here(&issue.closed_by, repository, PULL));
                }
            }
        }
        let jobs: Vec<Job> = prs.into_iter().map(Job::Pr).collect();
        self.jobs(&jobs, &mut answers);

        let mut jobs = BTreeMap::new();
        for n in members.discovered() {
            match discover(n, &answers) {
                Ok(Some(PullRequest::Open(pr))) if members.tickets.contains(&n) => {
                    jobs.insert((pr.number, 0), Job::Checks(pr.number));
                    jobs.insert((pr.number, 1), Job::Verdicts(pr.number));
                }
                Ok(Some(PullRequest::Merged(pr))) => {
                    let n = pr.fields.number;
                    jobs.insert(
                        (n, 2),
                        Job::OnBase(n, pr.merge_commit, pr.fields.base_branch),
                    );
                }
                _ => {}
            }
        }
        let jobs: Vec<Job> = jobs.into_values().collect();
        self.jobs(&jobs, &mut answers);
        answers
    }
}

const PULL: &str = "pull";
const ISSUES: &str = "issues";

fn here<'a>(
    links: &'a [Link],
    repository: &'a RepositoryAnswer,
    kind: &'a str,
) -> impl Iterator<Item = Number> + 'a {
    links
        .iter()
        .filter(move |link| is_here(link, repository, kind))
        .map(|link| link.number)
}

fn is_here(link: &Link, repository: &RepositoryAnswer, kind: &str) -> bool {
    link.url == format!("{}/{kind}/{}", repository.url.as_str(), link.number)
}

struct Members {
    tickets: Vec<Number>,
    blockers: BTreeSet<Number>,
}

impl Members {
    fn of(spec: Number, answers: &Answers) -> Self {
        let tickets = match list(spec, answers, Relation::SubIssues) {
            ListRead::Read { numbers, .. } => numbers,
            ListRead::Failed(_) => Vec::new(),
        };
        let mut blockers = BTreeSet::new();
        for &t in &tickets {
            if let ListRead::Read { numbers, .. } = list(t, answers, Relation::BlockedBy) {
                blockers.extend(numbers);
            }
        }
        Self { tickets, blockers }
    }

    fn discovered(&self) -> BTreeSet<Number> {
        self.tickets
            .iter()
            .copied()
            .chain(self.blockers.iter().copied())
            .collect()
    }
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Relation {
    SubIssues,
    BlockedBy,
}

enum ListRead {
    Read {
        numbers: Vec<Number>,
        truncated: Option<String>,
    },
    Failed(Failed),
}

fn failed(gap: GapKind, reason: impl Into<String>) -> Failed {
    Failed {
        gap,
        reason: NonEmpty::new(reason).unwrap_or_else(|| NonEmpty::new("unreadable").expect("text")),
    }
}

fn gap_of(error: &SourceError) -> GapKind {
    match error {
        SourceError::NotFound { .. } => GapKind::NotFound,
        SourceError::TimedOut { .. } => GapKind::TimedOut,
        SourceError::Malformed { .. } | SourceError::InvalidId { .. } => GapKind::Malformed,
        SourceError::CommandFailed { .. } | SourceError::Unavailable { .. } => {
            GapKind::CommandFailed
        }
    }
}

fn missed(miss: &Miss, what: &str) -> Failed {
    match miss {
        Miss::Source(error) => failed(gap_of(error), format!("{what} couldn't be read: {error}")),
        Miss::Budget => failed(
            GapKind::BudgetExhausted,
            format!("{what} wasn't read: the run's time ran out first"),
        ),
    }
}

fn list(number: Number, answers: &Answers, relation: Relation) -> ListRead {
    let (noun, plural) = match relation {
        Relation::SubIssues => ("sub-issue", "sub-issues"),
        Relation::BlockedBy => ("blocker", "blockers"),
    };
    let issue = match answers.issues.get(&number) {
        Some(Ok(issue)) => issue,
        Some(Err(miss)) => return ListRead::Failed(missed(miss, &format!("#{number}"))),
        None => return ListRead::Failed(missed(&Miss::Budget, &format!("#{number}"))),
    };
    let repository = match &answers.repository {
        Ok(repository) => repository,
        Err(miss) => {
            let why = missed(miss, "this repository");
            return ListRead::Failed(failed(
                why.gap,
                format!(
                    "#{number}'s {plural} can't be told from other repositories' issues: {}",
                    why.reason.as_str()
                ),
            ));
        }
    };
    let answer = match relation {
        Relation::SubIssues => &issue.sub_issues,
        Relation::BlockedBy => &issue.blocked_by,
    };
    if answer.nodes.iter().any(|l| !is_here(l, repository, ISSUES)) {
        return ListRead::Failed(failed(
            GapKind::Malformed,
            format!(
                "#{number}'s {plural} include an issue of another repository; OpenWiz reads one \
                 repository"
            ),
        ));
    }
    let mut numbers: Vec<Number> = answer.nodes.iter().map(|l| l.number).collect();
    numbers.sort_unstable();
    if numbers.windows(2).any(|w| w[0] == w[1]) {
        return ListRead::Failed(failed(
            GapKind::Malformed,
            format!("GitHub listed one of #{number}'s {plural} twice"),
        ));
    }
    if numbers.contains(&number) {
        return ListRead::Failed(failed(
            GapKind::Malformed,
            format!("GitHub listed #{number} as its own {noun}"),
        ));
    }
    let listed = numbers.len() as u64;
    let truncated = match listed.cmp(&answer.total) {
        std::cmp::Ordering::Equal => None,
        std::cmp::Ordering::Less => Some(format!(
            "GitHub listed {listed} of #{number}'s {} {plural}",
            answer.total
        )),
        std::cmp::Ordering::Greater => {
            return ListRead::Failed(failed(
                GapKind::Malformed,
                format!(
                    "GitHub listed {listed} of #{number}'s {plural}, more than its total of {}",
                    answer.total
                ),
            ));
        }
    };
    ListRead::Read { numbers, truncated }
}

fn discover(n: Number, answers: &Answers) -> Result<Option<PullRequest>, Failed> {
    let issue = match answers.issues.get(&n) {
        Some(Ok(issue)) => issue,
        Some(Err(miss)) => return Err(missed(miss, &format!("#{n}"))),
        None => return Err(missed(&Miss::Budget, &format!("#{n}"))),
    };
    let repository = match &answers.repository {
        Ok(repository) => repository,
        Err(miss) => {
            let why = missed(miss, "this repository");
            return Err(failed(
                why.gap,
                format!(
                    "#{n}'s pull requests can't be told from other repositories': {}",
                    why.reason.as_str()
                ),
            ));
        }
    };
    let mut open = Vec::new();
    let mut merged = Vec::new();
    let mut numbers: Vec<Number> = here(&issue.closed_by, repository, PULL).collect();
    numbers.sort_unstable();
    numbers.dedup();
    for number in numbers {
        let pr = match answers.prs.get(&number) {
            Some(Ok(pr)) => pr,
            Some(Err(miss)) => return Err(missed(miss, &format!("pull request #{number}"))),
            None => return Err(missed(&Miss::Budget, &format!("pull request #{number}"))),
        };
        let fields = pr_fields(pr, repository)?;
        if !fields.closes.contains(&n) {
            return Err(failed(
                GapKind::Malformed,
                format!(
                    "GitHub says pull request #{number} closes #{n}, but its closing references \
                     don't name #{n}"
                ),
            ));
        }
        match &pr.state {
            PrState::Open => open.push(fields),
            PrState::Closed => {}
            PrState::Merged {
                merge_commit,
                merged_at,
            } => merged.push(MergedPr {
                fields,
                merge_commit: merge_commit.clone(),
                merged_at: *merged_at,
            }),
        }
    }
    let several = |numbers: Vec<Number>| Some(PullRequest::Several { numbers });
    Ok(match (merged.len(), open.len()) {
        (1, _) => merged.pop().map(PullRequest::Merged),
        (0, 0) => None,
        (0, 1) => open.pop().map(PullRequest::Open),
        (0, _) => several(open.iter().map(|p| p.number).collect()),
        _ => several(merged.iter().map(|p| p.fields.number).collect()),
    })
}

fn pr_fields(pr: &PrAnswer, repository: &RepositoryAnswer) -> Result<PrFields, Failed> {
    if pr
        .closes
        .iter()
        .any(|link| !is_here(link, repository, ISSUES))
    {
        return Err(failed(
            GapKind::Malformed,
            format!(
                "pull request #{} also closes an issue of another repository; OpenWiz reads one \
                 repository",
                pr.number
            ),
        ));
    }
    let mut closes: Vec<Number> = here(&pr.closes, repository, ISSUES).collect();
    closes.sort_unstable();
    if closes.windows(2).any(|w| w[0] == w[1]) {
        return Err(failed(
            GapKind::Malformed,
            format!(
                "GitHub listed an issue twice among pull request #{}'s closing references",
                pr.number
            ),
        ));
    }
    Ok(PrFields {
        number: pr.number,
        draft: pr.draft,
        head_branch: pr.head_branch.clone(),
        head_commit: pr.head_commit.clone(),
        base_branch: pr.base_branch.clone(),
        closes,
    })
}

fn verdict(pr: Number, comments: &[String]) -> Result<Option<Review>, Failed> {
    let Some(latest) = comments.last() else {
        return Ok(None);
    };
    let line = latest.split('\n').next().unwrap_or_default();
    let line = line.strip_suffix('\r').unwrap_or(line);
    let parsed = line.strip_prefix("VERDICT: ").and_then(|rest| {
        let (word, commit) = rest.split_once(" at ")?;
        let verdict = match word {
            "APPROVE" => Verdict::Approve,
            "CHANGES" => Verdict::Changes,
            _ => return None,
        };
        Some(Review {
            verdict,
            commit: Commit::parse(commit)?,
        })
    });
    match parsed {
        Some(review) => Ok(Some(review)),
        None => Err(failed(
            GapKind::Malformed,
            format!(
                "pull request #{pr}'s latest VERDICT comment isn't review-ticket's form \
                 (VERDICT: APPROVE or CHANGES at a full commit)"
            ),
        )),
    }
}

fn checked(pr: Number, mut checks: Vec<Check>) -> Result<Vec<Check>, Failed> {
    checks.sort_by(|a, b| a.name.cmp(&b.name));
    if checks.windows(2).any(|w| w[0].name == w[1].name) {
        return Err(failed(
            GapKind::Malformed,
            format!("GitHub listed one check of pull request #{pr} twice"),
        ));
    }
    Ok(checks)
}

pub type Requires = BTreeSet<ReadId>;

pub struct Records<'a> {
    by_id: BTreeMap<ReadId, &'a Read>,
}

impl<'a> Records<'a> {
    pub fn new(reads: &'a [Read]) -> Self {
        Self {
            by_id: reads.iter().map(|r| (r.id, r)).collect(),
        }
    }

    pub fn get(&self, id: ReadId) -> Option<&'a Read> {
        self.by_id.get(&id).copied()
    }

    pub fn complete(&self, id: ReadId) -> bool {
        let Some(read) = self.get(id) else {
            return false;
        };
        match &read.kind {
            ReadKind::Version { outcome, .. } | ReadKind::Workspace { outcome, .. } => {
                matches!(outcome, Outcome::Complete { .. })
            }
            ReadKind::Repository { outcome } => matches!(outcome, Outcome::Complete { .. }),
            ReadKind::Issue { outcome, .. } => matches!(outcome, Outcome::Complete { .. }),
            ReadKind::PrDiscovery { outcome, .. } => matches!(outcome, Outcome::Complete { .. }),
            ReadKind::Comments { outcome, .. } => matches!(outcome, Outcome::Complete { .. }),
            ReadKind::MergeReadback { outcome, .. } => {
                matches!(outcome, Outcome::Complete { .. })
            }
            ReadKind::SpecList { outcome }
            | ReadKind::SubIssues { outcome, .. }
            | ReadKind::BlockedBy { outcome, .. } => {
                matches!(outcome, ListOutcome::Complete { .. })
            }
            ReadKind::Checks { outcome, .. } => matches!(outcome, ListOutcome::Complete { .. }),
            ReadKind::Projects { outcome } => matches!(outcome, ListOutcome::Complete { .. }),
            ReadKind::Threads { outcome } => matches!(outcome, ListOutcome::Complete { .. }),
        }
    }

    pub fn worked_out<T>(&self, requires: &Requires, value: impl FnOnce() -> T) -> WorkedOut<T> {
        let unread: Vec<ReadId> = requires
            .iter()
            .copied()
            .filter(|&id| !self.complete(id))
            .collect();
        if unread.is_empty() {
            WorkedOut::Known(value())
        } else {
            WorkedOut::Unread(unread)
        }
    }

    pub fn issue(&self, id: ReadId) -> Option<&'a Issue> {
        match self.get(id).map(|r| &r.kind) {
            Some(ReadKind::Issue {
                outcome: Outcome::Complete { value },
                ..
            }) => Some(value),
            _ => None,
        }
    }

    pub fn list(&self, id: ReadId) -> Option<&'a [Number]> {
        match self.get(id).map(|r| &r.kind) {
            Some(
                ReadKind::BlockedBy { outcome, .. }
                | ReadKind::SubIssues { outcome, .. }
                | ReadKind::SpecList { outcome },
            ) => match outcome {
                ListOutcome::Complete { value } | ListOutcome::Partial { value, .. } => Some(value),
                ListOutcome::Failed(_) => None,
            },
            _ => None,
        }
    }

    pub fn pull_request(&self, id: ReadId) -> Option<&'a Option<PullRequest>> {
        match self.get(id).map(|r| &r.kind) {
            Some(ReadKind::PrDiscovery {
                outcome: Outcome::Complete { value },
                ..
            }) => Some(value),
            _ => None,
        }
    }

    pub fn checks(&self, id: ReadId) -> Option<&'a [Check]> {
        match self.get(id).map(|r| &r.kind) {
            Some(ReadKind::Checks {
                outcome: ListOutcome::Complete { value },
                ..
            }) => Some(value),
            _ => None,
        }
    }

    pub fn review(&self, id: ReadId) -> Option<&'a Option<Review>> {
        match self.get(id).map(|r| &r.kind) {
            Some(ReadKind::Comments {
                outcome: Outcome::Complete { value },
                ..
            }) => Some(value),
            _ => None,
        }
    }

    pub fn on_base(&self, id: ReadId) -> Option<bool> {
        match self.get(id).map(|r| &r.kind) {
            Some(ReadKind::MergeReadback {
                outcome: Outcome::Complete { value },
                ..
            }) => Some(*value),
            _ => None,
        }
    }

    pub fn version(&self, id: ReadId) -> Option<&'a str> {
        match self.get(id).map(|r| &r.kind) {
            Some(ReadKind::Version {
                outcome: Outcome::Complete { value },
                ..
            }) => Some(value.as_str()),
            _ => None,
        }
    }

    pub fn coverage(&self) -> Completeness {
        if self.by_id.keys().all(|&id| self.complete(id)) {
            Completeness::Complete
        } else {
            Completeness::Partial
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Ci {
    Failed,
    Pending,
    Passed,
    None,
}

pub fn ci(checks: &[Check]) -> Ci {
    let any = |r: &[CheckResult]| checks.iter().any(|c| r.contains(&c.result));
    if any(&[CheckResult::Fail, CheckResult::Cancel]) {
        Ci::Failed
    } else if any(&[CheckResult::Pending]) {
        Ci::Pending
    } else if any(&[CheckResult::Pass]) {
        Ci::Passed
    } else {
        Ci::None
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TicketReads {
    pub issue: ReadId,
    pub blocked_by: ReadId,
    pub pr: ReadId,
    pub ci: Option<ReadId>,
    pub review: Option<ReadId>,
    pub on_base: Option<ReadId>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct BlockerReads {
    pub pr: ReadId,
    pub on_base: Option<ReadId>,
}

pub fn merged_requires(blocker: &BlockerReads) -> Requires {
    let mut requires = Requires::from([blocker.pr]);
    requires.extend(blocker.on_base);
    requires
}

pub fn merged(records: &Records<'_>, blocker: &BlockerReads) -> WorkedOut<bool> {
    records.worked_out(&merged_requires(blocker), || {
        is_merged(records, blocker.pr, blocker.on_base)
    })
}

fn is_merged(records: &Records<'_>, pr: ReadId, on_base: Option<ReadId>) -> bool {
    matches!(records.pull_request(pr), Some(Some(PullRequest::Merged(_))))
        && on_base.and_then(|id| records.on_base(id)) == Some(true)
}

pub fn state_requires(ticket: &TicketReads, blockers: &[BlockerReads]) -> Requires {
    let mut requires = Requires::from([ticket.issue, ticket.blocked_by, ticket.pr]);
    requires.extend(
        [ticket.ci, ticket.review, ticket.on_base]
            .into_iter()
            .flatten(),
    );
    for blocker in blockers {
        requires.extend(merged_requires(blocker));
    }
    requires
}

pub fn state(records: &Records<'_>, ticket: &TicketReads, blockers: &[BlockerReads]) -> State {
    match records.worked_out(&state_requires(ticket, blockers), || {
        state_table(records, ticket, blockers)
    }) {
        WorkedOut::Known(Ok(state)) => State::Known(state),
        WorkedOut::Known(Err(reason)) => State::Unknown(reason),
        WorkedOut::Unread(ids) => State::Unread(ids),
    }
}

fn state_table(
    records: &Records<'_>,
    ticket: &TicketReads,
    blockers: &[BlockerReads],
) -> Result<TicketState, NonEmpty> {
    let unknown = |why: &str| Err(NonEmpty::new(why).expect("a reason"));
    let Some(issue) = records.issue(ticket.issue) else {
        return unknown("its issue couldn't be read");
    };
    let has = |label: &str| issue.labels.iter().any(|l| l.as_str() == label);
    let Some(pr) = records.pull_request(ticket.pr) else {
        return unknown("its pull request couldn't be read");
    };
    if is_merged(records, ticket.pr, ticket.on_base) {
        return Ok(TicketState::Merged);
    }
    if issue.state == IssueState::Closed {
        return unknown("closed on GitHub, and no merge was read back");
    }
    if has(HELD) {
        return Ok(TicketState::Held);
    }
    match pr {
        Some(PullRequest::Open(open)) => {
            let review = ticket
                .review
                .and_then(|id| records.review(id))
                .cloned()
                .flatten();
            let checks = ticket
                .ci
                .and_then(|id| records.checks(id))
                .unwrap_or_default();
            if review.is_some_and(|r| r.verdict == Verdict::Changes && r.commit == open.head_commit)
            {
                return Ok(TicketState::ChangesRequested);
            }
            if open.draft || ci(checks) != Ci::Passed {
                return Ok(TicketState::Building);
            }
            Ok(TicketState::InReview)
        }
        None => {
            if !has(READY_FOR_AGENT) && !has(READY_FOR_HUMAN) {
                return unknown("no pull request, and no ready label: not approved yet");
            }
            if blockers
                .iter()
                .any(|b| !is_merged(records, b.pr, b.on_base))
            {
                return Ok(TicketState::Blocked);
            }
            if has(READY_FOR_AGENT) {
                return Ok(TicketState::Ready);
            }
            unknown("no pull request, every blocker merged, and ready for a human only")
        }
        Some(PullRequest::Several { .. }) => {
            unknown("several pull requests close it, so none is its own")
        }
        Some(PullRequest::Merged(_)) => {
            unknown("its pull request is merged, but the merge wasn't found on its base")
        }
    }
}

pub fn counts<'s>(states: impl IntoIterator<Item = &'s State>) -> Counts {
    let mut counts = Counts::default();
    for state in states {
        counts.tickets += 1;
        match state {
            State::Known(TicketState::Ready) => counts.ready += 1,
            State::Known(TicketState::Building) => counts.building += 1,
            State::Known(TicketState::InReview) => counts.in_review += 1,
            State::Known(TicketState::ChangesRequested) => counts.changes_requested += 1,
            State::Known(TicketState::Merged) => counts.merged += 1,
            State::Known(TicketState::Held) => counts.held += 1,
            State::Known(TicketState::Blocked) => counts.blocked += 1,
            State::Unknown(_) | State::Unread(_) => counts.unknown += 1,
        }
    }
    counts
}

pub fn progress(
    records: &Records<'_>,
    tickets_read: ReadId,
    tickets: &[(TicketReads, Vec<BlockerReads>)],
) -> WorkedOut<Counts> {
    let mut requires = Requires::from([tickets_read]);
    for (ticket, blockers) in tickets {
        requires.extend(state_requires(ticket, blockers));
    }
    records.worked_out(&requires, || {
        let states: Vec<State> = tickets
            .iter()
            .map(|(ticket, blockers)| state(records, ticket, blockers))
            .collect();
        counts(&states)
    })
}

pub fn needs_you(
    records: &Records<'_>,
    lists: &Requires,
    tickets: &[(Number, Number, ReadId)],
) -> WorkedOut<Vec<NeedsYou>> {
    let mut requires = lists.clone();
    requires.extend(tickets.iter().map(|&(_, _, issue)| issue));
    records.worked_out(&requires, || {
        let mut items = Vec::new();
        for &(spec, ticket, issue) in tickets {
            let Some(issue) = records.issue(issue) else {
                continue;
            };
            for (label, kind) in [
                (HELD, NeedsYouKind::Held),
                (NEEDS_INFO, NeedsYouKind::NeedsInfo),
            ] {
                if issue.labels.iter().any(|l| l.as_str() == label) {
                    items.push(super::fleets::needs_you_item(
                        kind,
                        spec,
                        ticket,
                        issue,
                        super::fleets::QUESTION_NOT_FOUND,
                    ));
                }
            }
        }
        items
    })
}

pub fn blocker_fleet(
    records: &Records<'_>,
    lists: &Requires,
    fleets: &[(Number, ReadId)],
    blocker: Number,
) -> WorkedOut<Option<Number>> {
    records.worked_out(lists, || {
        fleets
            .iter()
            .filter(|(_, tickets)| records.list(*tickets).is_some_and(|t| t.contains(&blocker)))
            .map(|(spec, _)| *spec)
            .min()
    })
}

struct Assembly {
    spec: Number,
    reads: Vec<Read>,
    ids: Ids,
    tickets: Vec<Number>,
    blockers: Vec<Number>,
}

#[derive(Default)]
struct Ids {
    github_version: Option<ReadId>,
    cloudroom_version: Option<ReadId>,
    repository: Option<ReadId>,
    issue: BTreeMap<Number, ReadId>,
    sub_issues: BTreeMap<Number, ReadId>,
    blocked_by: BTreeMap<Number, ReadId>,
    pr_discovery: BTreeMap<Number, ReadId>,
    checks: BTreeMap<Number, ReadId>,
    comments: BTreeMap<Number, ReadId>,
    merge_readback: BTreeMap<Number, ReadId>,
    projects: Option<ReadId>,
    threads: Option<ReadId>,
}

impl Assembly {
    fn new(spec: Number, answers: &Answers) -> Self {
        let members = Members::of(spec, answers);
        let mut assembly = Self {
            spec,
            reads: Vec::new(),
            ids: Ids::default(),
            tickets: members.tickets,
            blockers: members.blockers.into_iter().collect(),
        };
        assembly.record_all(answers);
        assembly
    }

    fn push(&mut self, kind: ReadKind) -> ReadId {
        let id = ReadId(u32::try_from(self.reads.len() + 1).expect("fewer reads than u32"));
        self.reads.push(Read { id, kind });
        id
    }

    fn record_all(&mut self, answers: &Answers) {
        let version = match &answers.version {
            Ok(text) => match NonEmpty::new(text.clone()) {
                Some(v) => Outcome::Complete { value: v },
                None => Outcome::Failed(failed(
                    GapKind::UntestedVersion,
                    "gh --version printed no version",
                )),
            },
            Err(miss) => {
                let why = missed(miss, "gh --version");
                Outcome::Failed(failed(GapKind::UntestedVersion, why.reason.as_str()))
            }
        };
        self.ids.github_version = Some(self.push(ReadKind::Version {
            source: SourceName::Github,
            outcome: version,
        }));
        self.ids.cloudroom_version = Some(self.push(ReadKind::Version {
            source: SourceName::Cloudroom,
            outcome: answers.agents.version.clone(),
        }));
        let repository = match &answers.repository {
            Ok(r) => Outcome::Complete {
                value: Repository {
                    name: r.name.clone(),
                },
            },
            Err(miss) => Outcome::Failed(missed(miss, "this repository")),
        };
        self.ids.repository = Some(self.push(ReadKind::Repository {
            outcome: repository,
        }));

        let spec = self.spec;
        self.record_issue(spec, answers);
        let outcome = list_outcome(list(spec, answers, Relation::SubIssues));
        let id = self.push(ReadKind::SubIssues { spec, outcome });
        self.ids.sub_issues.insert(spec, id);

        for t in self.tickets.clone() {
            self.record_issue(t, answers);
            let outcome = list_outcome(list(t, answers, Relation::BlockedBy));
            let id = self.push(ReadKind::BlockedBy { ticket: t, outcome });
            self.ids.blocked_by.insert(t, id);
            self.record_discovery(t, true, answers);
        }
        for b in self.blockers.clone() {
            if !self.tickets.contains(&b) {
                self.record_issue(b, answers);
                self.record_discovery(b, false, answers);
            }
        }

        let agents = &answers.agents;
        self.ids.projects = Some(self.push(ReadKind::Projects {
            outcome: agents.projects.clone(),
        }));
        self.ids.threads = Some(self.push(ReadKind::Threads {
            outcome: agents.threads.clone(),
        }));
        for (thread, outcome) in &agents.workspaces {
            self.push(ReadKind::Workspace {
                thread: thread.clone(),
                outcome: outcome.clone(),
            });
        }
    }

    fn record_issue(&mut self, n: Number, answers: &Answers) {
        if self.ids.issue.contains_key(&n) {
            return;
        }
        let outcome = match answers.issues.get(&n) {
            Some(Ok(answer)) => Outcome::Complete {
                value: answer.issue.clone(),
            },
            Some(Err(miss)) => Outcome::Failed(missed(miss, &format!("#{n}"))),
            None => Outcome::Failed(missed(&Miss::Budget, &format!("#{n}"))),
        };
        let id = self.push(ReadKind::Issue { issue: n, outcome });
        self.ids.issue.insert(n, id);
    }

    fn record_discovery(&mut self, n: Number, ticket: bool, answers: &Answers) {
        let found = discover(n, answers);
        let outcome = match &found {
            Ok(pr) => Outcome::Complete { value: pr.clone() },
            Err(why) => Outcome::Failed(why.clone()),
        };
        let id = self.push(ReadKind::PrDiscovery { issue: n, outcome });
        self.ids.pr_discovery.insert(n, id);
        match found {
            Ok(Some(PullRequest::Open(pr))) if ticket => {
                let pr = pr.number;
                if !self.ids.checks.contains_key(&pr) {
                    let what = format!("the checks of pull request #{pr}");
                    let outcome = match answers.checks.get(&pr) {
                        Some(Ok(checks)) => match checked(pr, checks.clone()) {
                            Ok(value) => ListOutcome::Complete { value },
                            Err(why) => ListOutcome::Failed(why),
                        },
                        Some(Err(miss)) => ListOutcome::Failed(missed(miss, &what)),
                        None => ListOutcome::Failed(missed(&Miss::Budget, &what)),
                    };
                    let id = self.push(ReadKind::Checks { pr, outcome });
                    self.ids.checks.insert(pr, id);
                }
                if !self.ids.comments.contains_key(&pr) {
                    let what = format!("the comments of pull request #{pr}");
                    let outcome = match answers.verdicts.get(&pr) {
                        Some(Ok(comments)) => match verdict(pr, comments) {
                            Ok(value) => Outcome::Complete { value },
                            Err(why) => Outcome::Failed(why),
                        },
                        Some(Err(miss)) => Outcome::Failed(missed(miss, &what)),
                        None => Outcome::Failed(missed(&Miss::Budget, &what)),
                    };
                    let id = self.push(ReadKind::Comments { pr, outcome });
                    self.ids.comments.insert(pr, id);
                }
            }
            Ok(Some(PullRequest::Merged(pr))) => {
                let pr = pr.fields.number;
                if !self.ids.merge_readback.contains_key(&pr) {
                    let what = format!("the merge of pull request #{pr}, on its base,");
                    let outcome = match answers.on_base.get(&pr) {
                        Some(Ok(there)) => Outcome::Complete { value: *there },
                        Some(Err(miss)) => Outcome::Failed(missed(miss, &what)),
                        None => Outcome::Failed(missed(&Miss::Budget, &what)),
                    };
                    let id = self.push(ReadKind::MergeReadback { pr, outcome });
                    self.ids.merge_readback.insert(pr, id);
                }
            }
            _ => {}
        }
    }

    fn pr_pointers(
        &self,
        records: &Records<'_>,
        n: Number,
    ) -> (Option<ReadId>, Option<ReadId>, Option<ReadId>) {
        match records.pull_request(self.ids.pr_discovery[&n]) {
            Some(Some(PullRequest::Open(pr))) => (
                self.ids.checks.get(&pr.number).copied(),
                self.ids.comments.get(&pr.number).copied(),
                None,
            ),
            Some(Some(PullRequest::Merged(pr))) => (
                None,
                None,
                self.ids.merge_readback.get(&pr.fields.number).copied(),
            ),
            _ => (None, None, None),
        }
    }

    fn ticket_reads(&self, records: &Records<'_>, t: Number) -> TicketReads {
        let (ci, review, on_base) = self.pr_pointers(records, t);
        TicketReads {
            issue: self.ids.issue[&t],
            blocked_by: self.ids.blocked_by[&t],
            pr: self.ids.pr_discovery[&t],
            ci,
            review,
            on_base,
        }
    }

    fn blocker_reads(&self, records: &Records<'_>, b: Number) -> BlockerReads {
        BlockerReads {
            pr: self.ids.pr_discovery[&b],
            on_base: self.pr_pointers(records, b).2,
        }
    }

    fn with_blockers(&self, records: &Records<'_>, t: Number) -> (TicketReads, Vec<BlockerReads>) {
        let ticket = self.ticket_reads(records, t);
        let blockers = records
            .list(ticket.blocked_by)
            .unwrap_or_default()
            .iter()
            .map(|&b| self.blocker_reads(records, b))
            .collect();
        (ticket, blockers)
    }

    fn envelope(
        &self,
        agents: &dyn Agents,
        tested: TestedVersions<'_>,
        snapshot_at: Timestamp,
    ) -> Envelope {
        let records = Records::new(&self.reads);
        let spec = self.spec;
        let lists = Requires::from([self.ids.sub_issues[&spec]]);
        let placed = agents.place(spec, &self.tickets, &self.reads);
        assert_eq!(
            placed.builders.len(),
            self.tickets.len(),
            "Agents::place gives one builder per ticket"
        );

        let ticket_reads: Vec<(TicketReads, Vec<BlockerReads>)> = self
            .tickets
            .iter()
            .map(|&t| self.with_blockers(&records, t))
            .collect();
        let tickets: Vec<Ticket> = self
            .tickets
            .iter()
            .zip(&ticket_reads)
            .zip(placed.builders)
            .map(|((&number, (reads, blockers)), builder)| Ticket {
                core: TicketCore {
                    number,
                    issue: reads.issue,
                    blocked_by: reads.blocked_by,
                    pr: reads.pr,
                    ci: reads.ci,
                    review: reads.review,
                    on_base: reads.on_base,
                    state: state(&records, reads, blockers),
                },
                builder,
                reviewer: Reviewer::Undefined(NonEmpty::new(NO_REVIEWER_CHAIN).expect("text")),
            })
            .collect();
        let fleets = [(spec, self.ids.sub_issues[&spec])];
        let blockers = self
            .blockers
            .iter()
            .map(|&b| {
                let reads = self.blocker_reads(&records, b);
                Blocker {
                    number: b,
                    issue: self.ids.issue[&b],
                    pr: reads.pr,
                    on_base: reads.on_base,
                    fleet: blocker_fleet(&records, &lists, &fleets, b),
                    merged: merged(&records, &reads),
                }
            })
            .collect();
        let needs: Vec<(Number, Number, ReadId)> = self
            .tickets
            .iter()
            .map(|&t| (spec, t, self.ids.issue[&t]))
            .collect();
        let github_version = self.ids.github_version.expect("recorded");
        let cloudroom_version = self.ids.cloudroom_version.expect("recorded");
        Envelope {
            schema: SchemaId::V1,
            sources: Sources {
                github: GitHubSource {
                    name: Gh::Gh,
                    version: github_version,
                    tested_version: tested.github.to_owned(),
                    version_tested: records.version(github_version) == Some(tested.github),
                },
                cloudroom: Some(CloudRoomSource {
                    name: RoomCli::RoomCli,
                    version: cloudroom_version,
                    tested_version: tested.cloudroom.to_owned(),
                    version_tested: records.version(cloudroom_version) == Some(tested.cloudroom),
                }),
            },
            reads: self.reads.clone(),
            coverage: Coverage {
                state: records.coverage(),
            },
            freshness: Freshness { snapshot_at },
            data: View::Fleet(FleetView {
                repository: self.ids.repository.expect("recorded"),
                projects: self.ids.projects.expect("recorded"),
                threads: self.ids.threads.expect("recorded"),
                fleet: Fleet {
                    spec,
                    issue: self.ids.issue[&spec],
                    tickets: self.ids.sub_issues[&spec],
                    progress: progress(&records, self.ids.sub_issues[&spec], &ticket_reads),
                },
                tickets,
                blockers,
                needs_you: needs_you(&records, &lists, &needs),
                unplaced: placed.unplaced,
            }),
        }
    }
}

fn agents_not_read() -> Failed {
    failed(GapKind::BudgetExhausted, AGENTS_NOT_READ)
}

fn list_outcome(read: ListRead) -> ListOutcome<Number> {
    match read {
        ListRead::Read {
            numbers,
            truncated: None,
        } => ListOutcome::Complete { value: numbers },
        ListRead::Read {
            numbers,
            truncated: Some(reason),
        } => ListOutcome::Partial {
            gap: Truncated::Truncated,
            reason: NonEmpty::new(reason).expect("a reason"),
            value: numbers,
        },
        ListRead::Failed(why) => ListOutcome::Failed(why),
    }
}

pub fn fleet_unreadable(envelope: &Envelope) -> Option<&Failed> {
    let View::Fleet(view) = &envelope.data else {
        return None;
    };
    envelope.reads.iter().find_map(|read| match &read.kind {
        ReadKind::SubIssues {
            outcome: ListOutcome::Failed(why),
            ..
        } if read.id == view.fleet.tickets => Some(why),
        _ => None,
    })
}
