use serde::Serialize;

use crate::messaging::send::{SendGap, UncertainReason};

pub type Gap = SendGap;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ProviderRefusal {
    Unsupported,
    ModelUnavailable,
    EffortUnavailable,
    MessageTooLong,
    MessageEmpty,
    ProjectNotFound,
    RequestIdConflict,
    DiscoveryUnavailable,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum SpawnReply {
    Created {
        thread_id: String,
    },
    Refused(ProviderRefusal),
    NotStarted,
    Unclear {
        reason: UncertainReason,
        gaps: Vec<Gap>,
    },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RefusalReason {
    NoOptions,
    HarnessNotOffered,
    ModelNotOffered,
    EffortNotOffered,
    ProjectNotFound,
    ProjectAmbiguous,
    ProjectPersonal,
    ProjectNotStandard,
    ProjectNoGithubRemote,
    ProjectRemoteNotConfirmed,
    ProviderUnsupported,
    ProviderModelUnavailable,
    ProviderEffortUnavailable,
    ProviderMessageTooLong,
    ProviderMessageEmpty,
    ProviderProjectNotFound,
    ProviderRequestIdConflict,
    ProviderDiscoveryUnavailable,
}

impl RefusalReason {
    pub fn words(self) -> &'static str {
        match self {
            Self::NoOptions => "CloudRoom offers no Cloud options right now",
            Self::HarnessNotOffered => "the harness is not offered",
            Self::ModelNotOffered => "the model is not offered for this harness",
            Self::EffortNotOffered => "the effort is not offered for this model",
            Self::ProjectNotFound => "no project has this id or name",
            Self::ProjectAmbiguous => {
                "more than one project has this name; use its id or name~<last 6 of its id>"
            }
            Self::ProjectPersonal => "personal projects are refused",
            Self::ProjectNotStandard => "only standard projects are accepted",
            Self::ProjectNoGithubRemote => {
                "the project has no GitHub remote, and only projects with one are accepted"
            }
            Self::ProjectRemoteNotConfirmed => {
                "whether the project has a GitHub remote could not be read"
            }
            Self::ProviderUnsupported => "CloudRoom refused: Cloud does not support this choice",
            Self::ProviderModelUnavailable => {
                "CloudRoom refused: the model is unavailable on Cloud"
            }
            Self::ProviderEffortUnavailable => "CloudRoom refused: the effort is unavailable",
            Self::ProviderMessageTooLong => "CloudRoom refused: the prompt is too long",
            Self::ProviderMessageEmpty => "CloudRoom refused: the prompt is empty",
            Self::ProviderProjectNotFound => "CloudRoom refused: the project was not found",
            Self::ProviderRequestIdConflict => {
                "CloudRoom refused: this request id was already used with different content"
            }
            Self::ProviderDiscoveryUnavailable => {
                "CloudRoom refused: its Cloud model discovery is unavailable"
            }
        }
    }
}

impl From<ProviderRefusal> for RefusalReason {
    fn from(refusal: ProviderRefusal) -> Self {
        match refusal {
            ProviderRefusal::Unsupported => Self::ProviderUnsupported,
            ProviderRefusal::ModelUnavailable => Self::ProviderModelUnavailable,
            ProviderRefusal::EffortUnavailable => Self::ProviderEffortUnavailable,
            ProviderRefusal::MessageTooLong => Self::ProviderMessageTooLong,
            ProviderRefusal::MessageEmpty => Self::ProviderMessageEmpty,
            ProviderRefusal::ProjectNotFound => Self::ProviderProjectNotFound,
            ProviderRefusal::RequestIdConflict => Self::ProviderRequestIdConflict,
            ProviderRefusal::DiscoveryUnavailable => Self::ProviderDiscoveryUnavailable,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum FailReason {
    InterruptedBeforeDispatch,
    ProjectsNotRead,
    RecordNotWritten,
    BudgetExhausted,
    CallNotStarted,
}

impl FailReason {
    pub fn words(self) -> &'static str {
        match self {
            Self::InterruptedBeforeDispatch => {
                "interrupted before dispatch: the process stopped after claiming the op id and \
                 before the dispatching mark, so nothing was sent"
            }
            Self::ProjectsNotRead => "the project list could not be read; nothing was sent",
            Self::RecordNotWritten => "the dispatching mark could not be written; nothing was sent",
            Self::BudgetExhausted => "the time budget ran out before the call; nothing was sent",
            Self::CallNotStarted => "the provider's command could not be started; nothing was sent",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Outcome {
    Created {
        thread_id: String,
        text: String,
    },
    Refused {
        reason: RefusalReason,
        offered: Vec<String>,
        text: String,
    },
    Failed {
        reason: FailReason,
        text: String,
    },
    Uncertain {
        reason: UncertainReason,
        text: String,
    },
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Status {
    Created,
    Refused,
    Failed,
    Uncertain,
    InProgress,
    ConflictingReuse,
}

pub const CREATED_WORDS: &str = "created: CloudRoom recorded the thread and its first prompt. \
     That is not a start: the start stage is shown separately";

impl Outcome {
    pub fn created(thread_id: String) -> Self {
        Self::Created {
            thread_id,
            text: CREATED_WORDS.to_owned(),
        }
    }

    pub fn with_attachments(self, count: usize) -> Self {
        match self {
            Self::Created { thread_id, text } if count > 0 => Self::Created {
                thread_id,
                text: format!("{text}{}", crate::prompt::handed_over(count)),
            },
            other => other,
        }
    }

    pub fn refused(reason: RefusalReason) -> Self {
        Self::refused_because(reason, reason.words(), vec![])
    }

    pub fn refused_because(reason: RefusalReason, words: &str, offered: Vec<String>) -> Self {
        Self::Refused {
            reason,
            offered,
            text: format!("refused: {words}; nothing was created"),
        }
    }

    pub fn failed(reason: FailReason) -> Self {
        Self::Failed {
            reason,
            text: format!("failed: {}", reason.words()),
        }
    }

    pub fn uncertain(reason: UncertainReason) -> Self {
        Self::Uncertain {
            reason,
            text: format!(
                "uncertain: {}. The thread may or may not have been created; the prompt is kept \
                 and nothing is retried",
                reason.words()
            ),
        }
    }

    pub fn from_reply(reply: SpawnReply) -> (Self, Vec<Gap>) {
        match reply {
            SpawnReply::Created { thread_id } => (Self::created(thread_id), vec![]),
            SpawnReply::Refused(refusal) => (Self::refused(refusal.into()), vec![]),
            SpawnReply::NotStarted => (Self::failed(FailReason::CallNotStarted), vec![]),
            SpawnReply::Unclear { reason, gaps } => (Self::uncertain(reason), gaps),
        }
    }

    pub fn text(&self) -> &str {
        match self {
            Self::Created { text, .. }
            | Self::Refused { text, .. }
            | Self::Failed { text, .. }
            | Self::Uncertain { text, .. } => text,
        }
    }

    pub fn status(&self) -> Status {
        match self {
            Self::Created { .. } => Status::Created,
            Self::Refused { .. } => Status::Refused,
            Self::Failed { .. } => Status::Failed,
            Self::Uncertain { .. } => Status::Uncertain,
        }
    }
}
