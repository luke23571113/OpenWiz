use std::fmt;
use std::time::Instant;

use crate::envelope::Gap;
use crate::model::{Fact, ProjectId, SessionId, Timestamp};

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct SessionScope {
    pub include_hidden: bool,
    pub include_archived: bool,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Rows<T> {
    pub records: Vec<T>,
    pub unreadable: Vec<Gap>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Placement {
    Cloud,
    Host(String),
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SessionRecord {
    pub id: SessionId,
    pub project_id: Fact<ProjectId>,
    pub title: Fact<String>,
    pub provider: Fact<String>,
    pub status: Fact<String>,
    pub hidden: Fact<bool>,
    pub archived: Fact<bool>,
    pub parent: Fact<Option<SessionId>>,
    pub placement: Fact<Placement>,
    pub purpose_text: Fact<Option<String>>,
    pub updated_at: Fact<Timestamp>,
    pub started_at: Fact<Timestamp>,
    pub problems: Vec<Gap>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SessionDetailRecord {
    pub session: SessionRecord,
    pub model: Fact<String>,
    pub effort: Fact<String>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct OutputRecord {
    pub output: Fact<Option<String>>,
    pub error: Fact<Option<String>>,
    pub problems: Vec<Gap>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ProjectRecord {
    pub id: ProjectId,
    pub name: Fact<String>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct MachineRecord {
    pub id: String,
    pub name: Fact<String>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum SourceError {
    NotFound {
        subject: String,
    },
    InvalidId {
        id: String,
        detail: String,
    },
    CommandFailed {
        exit_code: Option<i32>,
        detail: String,
    },
    TimedOut {
        after_ms: u64,
    },
    Malformed {
        detail: String,
    },
    Unavailable {
        detail: String,
    },
}

impl fmt::Display for SourceError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::NotFound { subject } => write!(f, "reported {subject} not found"),
            Self::InvalidId { id, detail } => write!(f, "was not run for the id {id}: {detail}"),
            Self::CommandFailed {
                exit_code: Some(code),
                detail,
            } => write!(f, "exited {code}: {detail}"),
            Self::CommandFailed {
                exit_code: None,
                detail,
            } => write!(f, "ended without an exit code: {detail}"),
            Self::TimedOut { after_ms } => write!(f, "timed out after {after_ms} ms"),
            Self::Malformed { detail } => write!(f, "returned malformed output: {detail}"),
            Self::Unavailable { detail } => write!(f, "could not be run: {detail}"),
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Read {
    Version,
    Sessions,
    Projects,
    Machines,
    SessionDetail,
    SessionOutput,
}

impl Read {
    pub fn generic_name(self) -> &'static str {
        match self {
            Self::Version => "version",
            Self::Sessions => "session list",
            Self::Projects => "project list",
            Self::Machines => "machine list",
            Self::SessionDetail => "session detail",
            Self::SessionOutput => "session output",
        }
    }
}

pub trait SessionSource: Send + Sync {
    fn name(&self) -> &str;

    fn tested_version(&self) -> &str;

    fn read_name(&self, read: Read) -> &str {
        read.generic_name()
    }

    fn version(&self, deadline: Instant) -> Result<String, SourceError>;

    fn list_sessions(
        &self,
        scope: SessionScope,
        deadline: Instant,
    ) -> Result<Rows<SessionRecord>, SourceError>;

    fn list_projects(
        &self,
        include_hidden: bool,
        deadline: Instant,
    ) -> Result<Rows<ProjectRecord>, SourceError>;

    fn list_machines(&self, deadline: Instant) -> Result<Rows<MachineRecord>, SourceError>;

    fn session_detail(
        &self,
        id: &SessionId,
        deadline: Instant,
    ) -> Result<SessionDetailRecord, SourceError>;

    fn session_output(
        &self,
        id: &SessionId,
        deadline: Instant,
    ) -> Result<OutputRecord, SourceError>;
}
