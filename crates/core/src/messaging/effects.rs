use serde::{Deserialize, Serialize};

use crate::model::{Fact, SessionId, Timestamp};
use crate::source::Placement;

use super::Mode;
use super::send::SendGap;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Activity {
    Idle,
    Running,
    Errored,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum QueuedWork {
    None,
    Waiting,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct TargetRecord {
    pub id: SessionId,
    pub title: Fact<String>,
    pub activity: Fact<Activity>,
    pub hidden: Fact<bool>,
    pub archived: Fact<bool>,
    pub placement: Fact<Placement>,
    pub host_connected: Option<Fact<bool>>,
    pub queued_work: Fact<QueuedWork>,
    pub queued_message_count: Fact<u64>,
    pub pending_interaction: Fact<bool>,
    pub problems: Vec<SendGap>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EffectKind {
    StartsTurn,
    QueuesBehindTurn,
    AsksToSteer,
    WaitsForInteraction,
    WaitsForHost,
}

impl EffectKind {
    pub fn words(self) -> &'static str {
        match self {
            Self::StartsTurn => "starts a turn; may wake it",
            Self::QueuesBehindTurn => "queues behind the current turn",
            Self::AsksToSteer => "asks to steer the current turn",
            Self::WaitsForInteraction => "waits for the pending interaction to be answered",
            Self::WaitsForHost => "waits for its host to come back online",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Effect {
    pub kind: EffectKind,
    pub text: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct PausedQueue {
    pub appears_paused: bool,
    pub queued_messages: Fact<u64>,
    pub text: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Effects {
    pub read_at: Timestamp,
    pub read_age_ms: i64,
    pub effect: Fact<Effect>,
    pub paused_queue: Fact<PausedQueue>,
    pub needs_acknowledgement: bool,
}

pub fn work_out(target: &TargetRecord, mode: Mode, read_at: Timestamp, now: Timestamp) -> Effects {
    let paused_queue = paused_queue(target);
    let needs_acknowledgement = match &paused_queue {
        Fact::Known(paused) => paused.appears_paused,
        Fact::Unknown(_) => true,
    };
    Effects {
        read_at,
        read_age_ms: now.0.saturating_sub(read_at.0),
        effect: effect(target, mode),
        paused_queue,
        needs_acknowledgement,
    }
}

pub const NO_PAUSED_QUEUE: &str = "no paused queue seen";

fn effect(target: &TargetRecord, mode: Mode) -> Fact<Effect> {
    let known = |kind: EffectKind| {
        Fact::Known(Effect {
            kind,
            text: kind.words().to_owned(),
        })
    };
    match &target.pending_interaction {
        Fact::Known(true) => return known(EffectKind::WaitsForInteraction),
        Fact::Known(false) => {}
        Fact::Unknown(why) => {
            return Fact::Unknown(format!("whether an interaction is pending: {why}"));
        }
    }
    match (&target.placement, &target.host_connected) {
        (_, Some(Fact::Known(false))) => return known(EffectKind::WaitsForHost),
        (_, Some(Fact::Unknown(why))) => {
            return Fact::Unknown(format!("whether its host is connected: {why}"));
        }
        (Fact::Unknown(why), None) => {
            return Fact::Unknown(format!("where it runs: {why}"));
        }
        _ => {}
    }
    match &target.activity {
        Fact::Known(Activity::Idle) => known(EffectKind::StartsTurn),
        Fact::Known(Activity::Running) => known(match mode {
            Mode::Queue => EffectKind::QueuesBehindTurn,
            Mode::Steer => EffectKind::AsksToSteer,
        }),
        Fact::Known(Activity::Errored) => Fact::Unknown(
            "the thread reports an error; how it takes a new message is not documented".to_owned(),
        ),
        Fact::Unknown(why) => Fact::Unknown(format!("its status: {why}")),
    }
}

fn paused_queue(target: &TargetRecord) -> Fact<PausedQueue> {
    let not_paused = || {
        Fact::Known(PausedQueue {
            appears_paused: false,
            queued_messages: target.queued_message_count.clone(),
            text: NO_PAUSED_QUEUE.to_owned(),
        })
    };
    match (&target.queued_work, &target.activity) {
        (Fact::Known(QueuedWork::Waiting), Fact::Known(Activity::Idle)) => {
            let follow = match &target.queued_message_count {
                Fact::Known(1) => "1 queued message may run after this one".to_owned(),
                Fact::Known(n) => format!("{n} queued messages may run after this one"),
                Fact::Unknown(_) => {
                    "an unknown number of queued messages may run after this one".to_owned()
                }
            };
            Fact::Known(PausedQueue {
                appears_paused: true,
                queued_messages: target.queued_message_count.clone(),
                text: format!("resumes the paused queue; {follow}"),
            })
        }
        (Fact::Known(QueuedWork::Waiting), Fact::Known(Activity::Running)) => not_paused(),
        (Fact::Known(QueuedWork::Waiting), Fact::Known(Activity::Errored)) => {
            Fact::Unknown("queued work is waiting on a thread that reports an error".to_owned())
        }
        (Fact::Known(QueuedWork::Waiting), Fact::Unknown(why)) => Fact::Unknown(format!(
            "queued work is waiting, and its status is unknown: {why}"
        )),
        (Fact::Known(QueuedWork::None), _) => not_paused(),
        (Fact::Unknown(why), _) => match target.queued_message_count {
            Fact::Known(0) => not_paused(),
            _ => Fact::Unknown(format!("its queued work: {why}")),
        },
    }
}
