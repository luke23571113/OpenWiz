use serde::Serialize;

use crate::attachment::PromptAttachment;
use crate::envelope::SourceInfo;
use crate::messaging::OpId;
use crate::messaging::record::StoreError;
use crate::messaging::send::UncertainReason;
use crate::model::Timestamp;

use super::effects::Effects;
use super::outcome::{FailReason, Gap, Outcome};
use super::{Binding, ProjectView, RECORD_SCHEMA_ID, Settings};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum RecordState {
    Claimed,
    Dispatching,
    Finished,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct NewThreadRecord {
    pub schema: String,
    pub op_id: OpId,
    pub binding: Binding,
    pub request_id: String,
    pub requested: Settings,
    pub provider: Option<String>,
    pub text: Option<String>,
    pub text_bytes: u64,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub attachments: Vec<PromptAttachment>,
    pub state: RecordState,
    pub project: Option<ProjectView>,
    pub source: Option<SourceInfo>,
    pub effects: Option<Effects>,
    pub outcome: Option<Outcome>,
    pub gaps: Vec<Gap>,
    pub recovered: bool,
    pub claimed_at: Timestamp,
    pub dispatching_at: Option<Timestamp>,
    pub finished_at: Option<Timestamp>,
}

impl NewThreadRecord {
    pub fn claimed(
        op_id: OpId,
        binding: Binding,
        requested: Settings,
        text: &str,
        now: Timestamp,
    ) -> Self {
        Self {
            schema: RECORD_SCHEMA_ID.to_owned(),
            request_id: super::request_id(&op_id),
            op_id,
            binding,
            requested,
            provider: None,
            text: Some(text.to_owned()),
            text_bytes: text.len() as u64,
            attachments: vec![],
            state: RecordState::Claimed,
            project: None,
            source: None,
            effects: None,
            outcome: None,
            gaps: vec![],
            recovered: false,
            claimed_at: now,
            dispatching_at: None,
            finished_at: None,
        }
    }

    pub fn with_attachments(self, attachments: Vec<PromptAttachment>) -> Self {
        Self {
            attachments,
            ..self
        }
    }

    pub fn dispatching(&self, now: Timestamp) -> Self {
        Self {
            state: RecordState::Dispatching,
            dispatching_at: Some(now),
            ..self.clone()
        }
    }

    pub fn finished(&self, outcome: Outcome, now: Timestamp) -> Self {
        let created = matches!(outcome, Outcome::Created { .. });
        Self {
            text: if created { None } else { self.text.clone() },
            state: RecordState::Finished,
            outcome: Some(outcome),
            finished_at: Some(now),
            ..self.clone()
        }
    }
}

pub fn recover(record: &NewThreadRecord, now: Timestamp) -> NewThreadRecord {
    let outcome = match record.state {
        RecordState::Finished => return record.clone(),
        RecordState::Claimed => Outcome::failed(FailReason::InterruptedBeforeDispatch),
        RecordState::Dispatching => {
            Outcome::uncertain(UncertainReason::InterruptedAfterDispatchMark)
        }
    };
    NewThreadRecord {
        recovered: true,
        ..record.finished(outcome, now)
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Claim {
    Owned,
    Existing(NewThreadRecord),
    InProgress(NewThreadRecord),
    Pending,
}

pub trait NewThreadStore: Send + Sync {
    fn load(&self, op_id: &OpId) -> Result<Option<NewThreadRecord>, StoreError>;

    fn claim(&self, record: &NewThreadRecord, now: Timestamp) -> Result<Claim, StoreError>;

    fn update(&self, record: &NewThreadRecord) -> Result<(), StoreError>;

    fn release(&self, op_id: &OpId);

    fn inspect(&self, op_id: &OpId, now: Timestamp) -> Result<Option<NewThreadRecord>, StoreError>;

    fn withdraw(&self, op_id: &OpId) -> Result<(), StoreError>;
}
