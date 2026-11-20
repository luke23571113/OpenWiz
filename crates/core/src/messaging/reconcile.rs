use serde::{Deserialize, Serialize};

use crate::model::Timestamp;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ObservationSource {
    QueueList,
    ThreadLog,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Observation {
    pub source: ObservationSource,
    pub same_text: bool,
    pub observed_at: Timestamp,
    pub attributed: bool,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Reconciliation {
    NotRead,
    Observed { matching: usize, total: usize },
    Attributed,
}

pub const MATCH_WINDOW_MS: i64 = 120_000;

pub fn reconcile(dispatched_at: Timestamp, observations: &[Observation]) -> Reconciliation {
    if observations.iter().any(|o| o.attributed) {
        return Reconciliation::Attributed;
    }
    let matching = observations
        .iter()
        .filter(|o| {
            o.same_text
                && o.observed_at.0.abs_diff(dispatched_at.0) <= MATCH_WINDOW_MS.unsigned_abs()
        })
        .count();
    Reconciliation::Observed {
        matching,
        total: observations.len(),
    }
}

pub const ATTRIBUTION_0_43_1: &str =
    "none: room-cli 0.43.1 documents no identifier that ties a delivered message to this request";
