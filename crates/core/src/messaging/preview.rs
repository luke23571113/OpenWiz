use std::time::Instant;

use serde::{Deserialize, Serialize};

use crate::limits::cap_field;
use crate::model::{Fact, SessionId, Timestamp};
use crate::ops::Clock;
use crate::source::SourceError;

use super::effects::{Effects, work_out};
use super::send::{FailReason, Messenger, SendGap, TargetView, read_failure};
use super::{InvalidRequest, Mode, SEND_BUDGET};

pub const PREVIEW_SCHEMA_ID: &str = "openwiz.send-preview.v1";

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PreviewStatus {
    Ready,
    NeedsAcknowledgement,
    Refused,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Refusal {
    pub reason: FailReason,
    pub text: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct PreviewReport {
    pub schema: String,
    pub target: TargetView,
    pub requested_mode: Mode,
    pub status: PreviewStatus,
    pub summary: String,
    pub effects: Option<Effects>,
    pub refusal: Option<Refusal>,
    pub read_at: Timestamp,
    pub gaps: Vec<SendGap>,
}

pub(crate) struct Look {
    pub read_at: Timestamp,
    pub title: Option<Fact<String>>,
    pub problems: Vec<SendGap>,
    pub outcome: Result<Effects, (FailReason, String)>,
}

pub(crate) fn look(
    messenger: &dyn Messenger,
    clock: &dyn Clock,
    target: &SessionId,
    mode: Mode,
    deadline: Instant,
) -> Look {
    let read_at = clock.now();
    let refused = |reason: FailReason, words: String| Look {
        read_at,
        title: None,
        problems: vec![],
        outcome: Err((reason, words)),
    };
    let record = match messenger.read_target(target, deadline) {
        Ok(record) => record,
        Err(SourceError::NotFound { .. }) => {
            return refused(
                FailReason::NotFound,
                FailReason::NotFound.words().to_owned(),
            );
        }
        Err(e) => {
            let words = format!(
                "the target could not be read ({}); nothing was sent",
                read_failure("the target read", &e)
            );
            return refused(FailReason::TargetNotRead, words);
        }
    };
    let title = Some(match &record.title {
        Fact::Known(title) => Fact::Known(cap_field(title)),
        Fact::Unknown(why) => Fact::Unknown(cap_field(why)),
    });
    let visibility = match (&record.archived, &record.hidden) {
        (Fact::Known(true), _) => Some(FailReason::TargetArchived),
        (_, Fact::Known(true)) => Some(FailReason::TargetHidden),
        (Fact::Known(false), Fact::Known(false)) => None,
        _ => Some(FailReason::TargetVisibilityUnknown),
    };
    let outcome = match visibility {
        Some(reason) => Err((reason, reason.words().to_owned())),
        None => Ok(work_out(&record, mode, read_at, clock.now())),
    };
    Look {
        read_at,
        title,
        problems: record.problems,
        outcome,
    }
}

pub(crate) fn held_back(
    effects: &Effects,
    resume_paused_queue: bool,
    clock: &dyn Clock,
    deadline: Instant,
) -> Option<FailReason> {
    if effects.needs_acknowledgement && !resume_paused_queue {
        return Some(FailReason::PausedQueueNotAcknowledged);
    }
    if clock.monotonic() >= deadline {
        return Some(FailReason::BudgetExhausted);
    }
    None
}

pub fn preview(
    messenger: &dyn Messenger,
    clock: &dyn Clock,
    target: &SessionId,
    mode: Mode,
) -> Result<PreviewReport, InvalidRequest> {
    messenger.check_target_id(target)?;
    let deadline = clock.monotonic() + SEND_BUDGET;
    let look = look(messenger, clock, target, mode, deadline);
    let unknown = |why: &str| format!("unknown ({why})");
    let refused = |reason: FailReason, text: String, effects: Option<Effects>| {
        let words = format!("a send would be refused: {text}");
        let refusal = Some(Refusal { reason, text });
        (PreviewStatus::Refused, effects, refusal, words)
    };
    let (status, effects, refusal, words) = match look.outcome {
        Err((reason, text)) => refused(reason, text, None),
        Ok(effects) => match held_back(&effects, false, clock, deadline) {
            None => {
                let words = match &effects.effect {
                    Fact::Known(effect) => format!("a send {}", effect.text),
                    Fact::Unknown(why) => format!("the effect is {}", unknown(why)),
                };
                (PreviewStatus::Ready, Some(effects), None, words)
            }
            Some(reason @ FailReason::PausedQueueNotAcknowledged) => {
                let refusal = Refusal {
                    reason,
                    text: reason.words().to_owned(),
                };
                let paused = match &effects.paused_queue {
                    Fact::Known(paused) => paused.text.clone(),
                    Fact::Unknown(why) => format!("the paused queue is {}", unknown(why)),
                };
                let words =
                    format!("{paused}; a send needs the owner's acknowledgement to resume it");
                let status = PreviewStatus::NeedsAcknowledgement;
                (status, Some(effects), Some(refusal), words)
            }
            Some(reason) => refused(reason, reason.words().to_owned(), Some(effects)),
        },
    };
    Ok(PreviewReport {
        schema: PREVIEW_SCHEMA_ID.to_owned(),
        target: TargetView {
            id: target.clone(),
            title: look
                .title
                .unwrap_or_else(|| Fact::Unknown("not read".to_owned())),
        },
        requested_mode: mode,
        status,
        summary: format!("{} · preview: {words}; nothing was sent", mode.requested()),
        effects,
        refusal,
        read_at: look.read_at,
        gaps: look.problems,
    })
}
