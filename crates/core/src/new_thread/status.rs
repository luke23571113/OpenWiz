use std::time::Duration;

use serde::Serialize;

use crate::messaging::OpId;
use crate::messaging::record::StoreError;
use crate::messaging::send::read_failure;
use crate::model::Timestamp;
use crate::ops::Clock;

use super::STATUS_SCHEMA_ID;
use super::operation::{
    NewThreadClient, NewThreadReport, ObservedThread, from_record, in_flight_report,
};
use super::outcome::{Gap, Outcome};
use super::record::{NewThreadStore, RecordState};
use super::start::{StartView, start_view};

pub const OBSERVATIONS_ONLY: &str = "observations only: no documented field ties a listed thread \
     to this request, so the outcome stays uncertain";

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Observations {
    pub read_at: Timestamp,
    pub threads: Vec<ObservedThread>,
    pub text: String,
    pub gaps: Vec<Gap>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum StatusResult {
    NoRecord,
    Recorded(Box<Recorded>),
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Recorded {
    pub report: NewThreadReport,
    pub start: Option<StartView>,
    pub observations: Option<Observations>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct NewThreadStatus {
    pub schema: String,
    pub op_id: OpId,
    pub result: StatusResult,
}

pub fn new_thread_status(
    client: &dyn NewThreadClient,
    store: &dyn NewThreadStore,
    clock: &dyn Clock,
    op_id: &OpId,
    budget: Duration,
) -> Result<NewThreadStatus, StoreError> {
    let deadline = clock.monotonic() + budget;
    let status = |result| NewThreadStatus {
        schema: STATUS_SCHEMA_ID.to_owned(),
        op_id: op_id.clone(),
        result,
    };
    let Some(record) = store.inspect(op_id, clock.now())? else {
        return Ok(status(StatusResult::NoRecord));
    };
    if record.state != RecordState::Finished {
        return Ok(status(StatusResult::Recorded(Box::new(Recorded {
            report: in_flight_report(&record),
            start: None,
            observations: None,
        }))));
    }
    let report = from_record(&record, true, vec![]);
    let (start, observations) = match &record.outcome {
        Some(Outcome::Created { thread_id, .. }) => {
            let provider = record
                .provider
                .as_deref()
                .unwrap_or(&record.requested.harness);
            let read = client.show_thread(thread_id, deadline);
            let requested = (
                provider,
                record.requested.model.as_str(),
                record.requested.effort.as_str(),
            );
            (
                Some(start_view(thread_id, requested, read, clock.now())),
                None,
            )
        }
        Some(Outcome::Uncertain { .. }) => {
            let observations = record.project.as_ref().map(|project| {
                match client.threads_since(&project.id, record.claimed_at, deadline) {
                    Ok(threads) => Observations {
                        read_at: clock.now(),
                        threads,
                        text: OBSERVATIONS_ONLY.to_owned(),
                        gaps: vec![],
                    },
                    Err(e) => Observations {
                        read_at: clock.now(),
                        threads: vec![],
                        text: OBSERVATIONS_ONLY.to_owned(),
                        gaps: vec![Gap {
                            subject: "thread list".to_owned(),
                            detail: read_failure("thread list", &e),
                        }],
                    },
                }
            });
            (None, observations)
        }
        _ => (None, None),
    };
    Ok(status(StatusResult::Recorded(Box::new(Recorded {
        report,
        start,
        observations,
    }))))
}
