use std::num::NonZeroU64;

use serde::Serialize;

use crate::envelope::{Completeness, GapKind};
use crate::model::{Fact, Timestamp};

pub const SCHEMA_ID: &str = "openwiz.fleet.v1";

pub type Number = NonZeroU64;

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize)]
#[serde(transparent)]
pub struct NonEmpty(String);

impl NonEmpty {
    pub fn new(text: impl Into<String>) -> Option<Self> {
        let text = text.into();
        (!text.is_empty()).then_some(Self(text))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize)]
#[serde(transparent)]
pub struct Commit(String);

impl Commit {
    pub fn parse(id: &str) -> Option<Self> {
        let hex = id.len() == 40 && id.bytes().all(|b| matches!(b, b'0'..=b'9' | b'a'..=b'f'));
        hex.then(|| Self(id.to_owned()))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize)]
#[serde(into = "String")]
pub struct ReadId(pub u32);

impl From<ReadId> for String {
    fn from(id: ReadId) -> Self {
        format!("r{}", id.0)
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Envelope {
    pub schema: SchemaId,
    pub sources: Sources,
    pub reads: Vec<Read>,
    pub coverage: Coverage,
    pub freshness: Freshness,
    pub data: View,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
pub enum SchemaId {
    #[serde(rename = "openwiz.fleet.v1")]
    V1,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Sources {
    pub github: GitHubSource,
    pub cloudroom: Option<CloudRoomSource>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct GitHubSource {
    pub name: Gh,
    pub version: ReadId,
    pub tested_version: String,
    pub version_tested: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
pub enum Gh {
    #[serde(rename = "gh")]
    Gh,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct CloudRoomSource {
    pub name: RoomCli,
    pub version: ReadId,
    pub tested_version: String,
    pub version_tested: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
pub enum RoomCli {
    #[serde(rename = "room-cli")]
    RoomCli,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
pub struct Coverage {
    pub state: Completeness,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
pub struct Freshness {
    pub snapshot_at: Timestamp,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Read {
    pub id: ReadId,
    #[serde(flatten)]
    pub kind: ReadKind,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum ReadKind {
    Version {
        source: SourceName,
        outcome: Outcome<NonEmpty>,
    },
    Repository {
        outcome: Outcome<Repository>,
    },
    SpecList {
        outcome: ListOutcome<Number>,
    },
    Issue {
        issue: Number,
        outcome: Outcome<Issue>,
    },
    SubIssues {
        spec: Number,
        outcome: ListOutcome<Number>,
    },
    BlockedBy {
        ticket: Number,
        outcome: ListOutcome<Number>,
    },
    PrDiscovery {
        issue: Number,
        outcome: Outcome<Option<PullRequest>>,
    },
    Checks {
        pr: Number,
        outcome: ListOutcome<Check>,
    },
    Comments {
        pr: Number,
        outcome: Outcome<Option<Review>>,
    },
    MergeReadback {
        pr: Number,
        outcome: Outcome<bool>,
    },
    Projects {
        outcome: ListOutcome<Project>,
    },
    Threads {
        outcome: ListOutcome<Thread>,
    },
    Workspace {
        thread: NonEmpty,
        outcome: Outcome<NonEmpty>,
    },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum SourceName {
    Github,
    Cloudroom,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "state", rename_all = "snake_case")]
pub enum Outcome<T> {
    Complete { value: T },
    Failed(Failed),
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "state", rename_all = "snake_case")]
pub enum ListOutcome<T> {
    Complete {
        value: Vec<T>,
    },
    Partial {
        gap: Truncated,
        reason: NonEmpty,
        value: Vec<T>,
    },
    Failed(Failed),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Truncated {
    Truncated,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Failed {
    pub gap: GapKind,
    pub reason: NonEmpty,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Repository {
    pub name: NonEmpty,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Issue {
    pub title: String,
    pub state: IssueState,
    pub milestone: Option<Milestone>,
    pub labels: Vec<NonEmpty>,
    pub owned_paths: Option<NonEmpty>,
    pub relies_on: Option<NonEmpty>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pending_question: Option<PendingQuestion>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct PendingQuestion {
    pub wording: NonEmpty,
    pub link: NonEmpty,
    pub asked_at: Timestamp,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum IssueState {
    Open,
    Closed,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Milestone {
    pub number: Number,
    pub title: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "state", rename_all = "snake_case")]
pub enum PullRequest {
    Open(PrFields),
    Merged(MergedPr),
    Several { numbers: Vec<Number> },
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct PrFields {
    pub number: Number,
    pub draft: bool,
    pub head_branch: NonEmpty,
    pub head_commit: Commit,
    pub base_branch: NonEmpty,
    pub closes: Vec<Number>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct MergedPr {
    #[serde(flatten)]
    pub fields: PrFields,
    pub merge_commit: Commit,
    pub merged_at: Timestamp,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Check {
    pub name: NonEmpty,
    pub result: CheckResult,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum CheckResult {
    Pass,
    Fail,
    Pending,
    Skipping,
    Cancel,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Review {
    pub verdict: Verdict,
    pub commit: Commit,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Verdict {
    Approve,
    Changes,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Project {
    pub id: NonEmpty,
    pub name: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Thread {
    Cloud {
        thread: NonEmpty,
        project: NonEmpty,
    },
    Local {
        thread: NonEmpty,
        project: NonEmpty,
        branch: Option<NonEmpty>,
    },
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum WorkedOut<T> {
    Known(T),
    Unread(Vec<ReadId>),
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum State {
    Known(TicketState),
    Unread(Vec<ReadId>),
    Unknown(NonEmpty),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TicketState {
    Ready,
    Building,
    InReview,
    ChangesRequested,
    Merged,
    Held,
    Blocked,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Reviewer {
    Undefined(NonEmpty),
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "view", rename_all = "snake_case")]
pub enum View {
    Fleets(FleetsView),
    Fleet(FleetView),
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct FleetsView {
    pub repository: ReadId,
    pub specs: ReadId,
    pub fleets: Vec<Fleet>,
    pub tickets: Vec<TicketCore>,
    pub blockers: Vec<Blocker>,
    pub needs_you: WorkedOut<Vec<NeedsYou>>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct FleetView {
    pub repository: ReadId,
    pub projects: ReadId,
    pub threads: ReadId,
    pub fleet: Fleet,
    pub tickets: Vec<Ticket>,
    pub blockers: Vec<Blocker>,
    pub needs_you: WorkedOut<Vec<NeedsYou>>,
    pub unplaced: WorkedOut<Vec<Unplaced>>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Fleet {
    pub spec: Number,
    pub issue: ReadId,
    pub tickets: ReadId,
    pub progress: WorkedOut<Counts>,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize)]
pub struct Counts {
    pub tickets: u64,
    pub ready: u64,
    pub building: u64,
    pub in_review: u64,
    pub changes_requested: u64,
    pub merged: u64,
    pub held: u64,
    pub blocked: u64,
    pub unknown: u64,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct TicketCore {
    pub number: Number,
    pub issue: ReadId,
    pub blocked_by: ReadId,
    pub pr: ReadId,
    pub ci: Option<ReadId>,
    pub review: Option<ReadId>,
    pub on_base: Option<ReadId>,
    pub state: State,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Ticket {
    #[serde(flatten)]
    pub core: TicketCore,
    pub builder: WorkedOut<Option<NonEmpty>>,
    pub reviewer: Reviewer,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Blocker {
    pub number: Number,
    pub issue: ReadId,
    pub pr: ReadId,
    pub on_base: Option<ReadId>,
    pub fleet: WorkedOut<Option<Number>>,
    pub merged: WorkedOut<bool>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct NeedsYou {
    pub kind: NeedsYouKind,
    pub spec: Number,
    pub ticket: Number,
    pub wording: Fact<NonEmpty>,
    pub link: Fact<NonEmpty>,
    pub asked_at: Fact<Timestamp>,
    pub risk: Fact<NeedsYouRisk>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum NeedsYouRisk {
    Live,
    Release,
    Publish,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum NeedsYouKind {
    NeedsInfo,
    Held,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Unplaced {
    pub thread: NonEmpty,
    pub reason: UnplacedReason,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum UnplacedReason {
    NoBranch,
    SharedBranch,
    NoPullRequest,
    SeveralTickets,
    SeveralIssues,
}
