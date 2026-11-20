use serde::{Deserialize, Serialize};

use crate::model::{Fact, Timestamp};

pub const SCHEMA_ID: &str = "openwiz.inventory.v1";

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Envelope<T> {
    pub schema: String,
    pub source: SourceInfo,
    pub coverage: Coverage,
    pub freshness: Freshness,
    pub gaps: Vec<Gap>,
    pub data: T,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct SourceInfo {
    pub name: String,
    pub version: Fact<String>,
    pub tested_version: String,
    pub version_tested: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Completeness {
    Complete,
    Partial,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Coverage {
    pub state: Completeness,
    pub counts: Option<Counts>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Counts {
    pub listed: u64,
    pub unreadable: u64,
    pub excluded_hidden: u64,
    pub excluded_archived: u64,
    pub hidden_read: bool,
    pub archived_read: bool,
    pub matched: u64,
    pub offset: u64,
    pub limit: u64,
    pub shown: u64,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Freshness {
    pub snapshot_at: Timestamp,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Gap {
    pub kind: GapKind,
    pub subject: Option<String>,
    pub detail: String,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum GapKind {
    UntestedVersion,
    CommandFailed,
    TimedOut,
    BudgetExhausted,
    Malformed,
    MissingField,
    WrongType,
    NotFound,
}
