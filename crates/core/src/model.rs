use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Fact<T> {
    Known(T),
    Unknown(String),
}

impl<T> Fact<T> {
    pub fn map<U>(self, f: impl FnOnce(T) -> U) -> Fact<U> {
        match self {
            Self::Known(value) => Fact::Known(f(value)),
            Self::Unknown(reason) => Fact::Unknown(reason),
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(transparent)]
pub struct Timestamp(pub i64);

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(transparent)]
pub struct SessionId(pub String);

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize)]
#[serde(transparent)]
pub struct ProjectId(pub String);

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct BoundedText {
    pub text: String,
    pub truncated: bool,
}

impl BoundedText {
    pub fn chars(text: &str, max: usize) -> Self {
        match text.char_indices().nth(max) {
            Some((end, _)) => Self {
                text: text[..end].to_owned(),
                truncated: true,
            },
            None => Self {
                text: text.to_owned(),
                truncated: false,
            },
        }
    }

    pub fn bytes(text: &str, max: usize) -> Self {
        if text.len() <= max {
            return Self {
                text: text.to_owned(),
                truncated: false,
            };
        }
        let mut end = max;
        while !text.is_char_boundary(end) {
            end -= 1;
        }
        Self {
            text: text[..end].to_owned(),
            truncated: true,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Location {
    Cloud,
    Local { machine: Fact<String> },
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Grouping {
    Project { id: ProjectId, name: Fact<String> },
    Ungrouped { reason: String },
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Recap {
    PurposeAsReported(BoundedText),
    NoRecapYet,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct ReportedConfiguration {
    pub model: Fact<String>,
    pub effort: Fact<String>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Session {
    pub id: SessionId,
    pub title: Fact<String>,
    pub provider: Fact<String>,
    pub status: Fact<String>,
    pub location: Fact<Location>,
    pub group: Grouping,
    pub parent: Fact<Option<SessionId>>,
    pub hidden: Fact<bool>,
    pub archived: Fact<bool>,
    pub recap: Fact<Recap>,
    pub reported_configuration: ReportedConfiguration,
    pub updated_at: Fact<Timestamp>,
    pub age_ms: Fact<i64>,
    pub started_at: Fact<Timestamp>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum FinalOutput {
    Reported(BoundedText),
    NoFinalOutputYet,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Inventory {
    pub sessions: Vec<Session>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct SessionView {
    pub session: Session,
    pub final_output: Fact<FinalOutput>,
    pub reported_error: Fact<Option<BoundedText>>,
}
