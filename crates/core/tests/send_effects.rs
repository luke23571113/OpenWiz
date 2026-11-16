//! The core's send rules on their own, with no adapter, store or client:
//! the effects rule for states the `room-cli` fixtures cannot show (M5),
//! and a core that does no I/O. Moved here from
//! `tests/messaging/m05_effects.rs` and `tests/messaging/structure.rs` by
//! #809; the M5 cases that read through the adapter and the fake `room-cli`
//! stay there.

use std::fs;
use std::path::{Path, PathBuf};

use openwiz_core::messaging::Mode;
use openwiz_core::messaging::effects::{
    Activity, EffectKind, Effects, QueuedWork, TargetRecord, work_out,
};
use openwiz_core::model::{Fact, SessionId, Timestamp};
use openwiz_core::source::Placement;

const T0: Timestamp = Timestamp(1_700_000_600_000);

fn kind(effects: &Effects) -> Option<EffectKind> {
    match &effects.effect {
        Fact::Known(effect) => Some(effect.kind),
        Fact::Unknown(_) => None,
    }
}

#[test]
fn send_effects_contracts_preserve_original_cases() {
    let cases: [(&str, fn()); 2] = [
        (
            "the_core_rule_covers_states_the_fixtures_cannot_show",
            the_core_rule_covers_states_the_fixtures_cannot_show,
        ),
        (
            "waiting_work_on_an_errored_target_stays_unknown_and_requires_acknowledgement",
            waiting_work_on_an_errored_target_stays_unknown_and_requires_acknowledgement,
        ),
    ];
    for (name, proof) in cases {
        eprintln!("TA2 case: send_effects::{name}");
        proof();
    }
}

fn target() -> TargetRecord {
    TargetRecord {
        id: SessionId("thr_syn_0001".to_owned()),
        title: Fact::Known("Synthetic session 1".to_owned()),
        activity: Fact::Known(Activity::Idle),
        hidden: Fact::Known(false),
        archived: Fact::Known(false),
        placement: Fact::Known(Placement::Cloud),
        host_connected: None,
        queued_work: Fact::Known(QueuedWork::None),
        queued_message_count: Fact::Known(0),
        pending_interaction: Fact::Known(false),
        problems: vec![],
    }
}

fn waiting_work_on_an_errored_target_stays_unknown_and_requires_acknowledgement() {
    let mut errored = target();
    errored.activity = Fact::Known(Activity::Errored);
    errored.queued_work = Fact::Known(QueuedWork::Waiting);
    errored.queued_message_count = Fact::Known(1);

    for mode in [Mode::Queue, Mode::Steer] {
        let effects = work_out(&errored, mode, T0, T0);
        assert_eq!(
            (
                matches!(effects.paused_queue, Fact::Unknown(_)),
                effects.needs_acknowledgement,
            ),
            (true, true),
            "{mode:?}: a paused queue cannot be ruled out on an errored target"
        );
    }
}

fn the_core_rule_covers_states_the_fixtures_cannot_show() {
    let read = Timestamp(1_000_000);
    let now = Timestamp(1_004_500);
    let base = work_out(&target(), Mode::Queue, read, now);
    assert_eq!(base.read_age_ms, 4_500, "the read's age when shown");
    assert_eq!(kind(&base), Some(EffectKind::StartsTurn));

    let mut offline = target();
    offline.placement = Fact::Known(Placement::Host("mch_syn_0001".to_owned()));
    offline.host_connected = Some(Fact::Known(false));
    let e = work_out(&offline, Mode::Steer, read, now);
    assert_eq!(kind(&e), Some(EffectKind::WaitsForHost));
    assert_eq!(
        EffectKind::WaitsForHost.words(),
        "waits for its host to come back online"
    );

    let mut host_unknown = offline.clone();
    host_unknown.host_connected = Some(Fact::Unknown("synthetic".to_owned()));
    assert_eq!(kind(&work_out(&host_unknown, Mode::Queue, read, now)), None);

    // Queued work waiting behind a running turn is not a paused queue.
    let mut running = target();
    running.activity = Fact::Known(Activity::Running);
    running.queued_work = Fact::Known(QueuedWork::Waiting);
    running.queued_message_count = Fact::Known(3);
    let e = work_out(&running, Mode::Queue, read, now);
    assert!(!e.needs_acknowledgement, "{e:#?}");
    assert_eq!(kind(&e), Some(EffectKind::QueuesBehindTurn));

    // Waiting work on a thread whose activity is unknown: cannot be ruled out.
    let mut unknown_activity = running.clone();
    unknown_activity.activity = Fact::Unknown("synthetic".to_owned());
    let e = work_out(&unknown_activity, Mode::Queue, read, now);
    assert!(e.needs_acknowledgement, "{e:#?}");
    assert!(matches!(e.paused_queue, Fact::Unknown(_)));
    assert_eq!(kind(&e), None);

    // Unknown queued work, but nothing queued: no paused queue to resume.
    let mut nothing_queued = target();
    nothing_queued.queued_work = Fact::Unknown("synthetic".to_owned());
    let e = work_out(&nothing_queued, Mode::Queue, read, now);
    assert!(!e.needs_acknowledgement, "{e:#?}");

    // An unknown count on a paused queue still names the effect.
    let mut paused = target();
    paused.queued_work = Fact::Known(QueuedWork::Waiting);
    paused.queued_message_count = Fact::Unknown("synthetic".to_owned());
    let e = work_out(&paused, Mode::Queue, read, now);
    assert!(e.needs_acknowledgement);
    match &e.paused_queue {
        Fact::Known(p) => assert_eq!(
            p.text,
            "resumes the paused queue; an unknown number of queued messages may run after this one"
        ),
        other => panic!("{other:?}"),
    }

    // A pending interaction that cannot be read: unknown, never guessed.
    let mut interaction = target();
    interaction.pending_interaction = Fact::Unknown("synthetic".to_owned());
    assert_eq!(kind(&work_out(&interaction, Mode::Queue, read, now)), None);
}

fn rust_files(dir: &Path, out: &mut Vec<PathBuf>) {
    for entry in fs::read_dir(dir).unwrap() {
        let path = entry.unwrap().path();
        if path.is_dir() {
            rust_files(&path, out);
        } else if path.extension().is_some_and(|e| e == "rs") {
            out.push(path);
        }
    }
}

#[test]
fn the_core_does_no_io() {
    let mut files = Vec::new();
    rust_files(
        &Path::new(env!("CARGO_MANIFEST_DIR")).join("src"),
        &mut files,
    );
    assert!(files.iter().any(|f| f.ends_with("messaging/send.rs")));
    for path in files {
        let text = fs::read_to_string(&path).unwrap();
        for io in [
            "std::fs",
            "std::io",
            "std::net",
            "std::process",
            "std::env",
            "std::os",
            "SystemTime",
            "Instant::now",
            "println!",
            "eprintln!",
        ] {
            assert!(!text.contains(io), "{path:?} uses {io}");
        }
    }
}
