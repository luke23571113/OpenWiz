//! M10 The record is synced, readable by the owner only, outside the
//! repository, and correct under concurrent writers.
//!
//! Durability against power loss cannot be shown on fixtures. What is shown:
//! the dispatching mark is on disk, visible to another process, at the
//! moment of the call; and the store syncs both the file and its directory
//! (a static tripwire, like P8(a)).
//!
//! The store's own cases (the default state directory, the repository
//! refusals and the sync tripwires) are `crates/store/tests/state_dir.rs`
//! (#809).

use std::fs;
use std::os::unix::fs::{DirBuilderExt, PermissionsExt};

use openwiz_cli::send::EXIT_RECORD_UNAVAILABLE;
use openwiz_core::messaging::Mode;
use openwiz_core::messaging::send::Status;
use openwiz_store::FileStore;
use serde_json::json;

use crate::support::*;

#[test]
fn unknown_send_record_schemas_are_unavailable_without_side_effects() {
    let fake = SendFake::new("m10_unknown_schema", "send");
    let id = "op-m10-unknown-schema";
    let sent = fake.report(&request("thr_syn_0001", Mode::Queue, "Synthetic", id));
    assert_eq!(sent.status, Status::Accepted);
    let mut record = fake.record(id);
    for schema in [
        "openwiz.send-record.v999",
        "openwiz.send-record.v0",
        "",
        "OPENWIZ.SEND-RECORD.V1",
        "openwiz.send-record.v1 ",
        "openwiz.send-record.v１",
    ] {
        record["schema"] = json!(schema);
        fs::write(fake.record_path(id), serde_json::to_vec(&record).unwrap()).unwrap();
        let calls = fake.invocations();
        let files = sends_listing(&fake);
        for json in [false, true] {
            let mut args = vec!["thr_syn_0001", "--op-id", id, "--check"];
            if json {
                args.push("--json");
            }
            let (code, out, err) = fake.cli(&args, "");
            assert_eq!(
                code, EXIT_RECORD_UNAVAILABLE,
                "schema {schema:?}: {out}{err}"
            );
            assert!(out.is_empty(), "{out}");
            assert!(
                err.starts_with("openwiz: the send record could not be used:"),
                "{err}"
            );
            assert!(err.contains("nothing was sent"), "{err}");
            assert_eq!(fake.invocations(), calls, "lookup called the provider");
            assert_eq!(sends_listing(&fake), files, "lookup changed the store");
        }
    }
}

#[test]
fn v1_send_records_still_load_and_replay() {
    let fake = SendFake::new("m10_v1_schema", "send");
    let id = "op-m10-v1-schema";
    let sent = fake.report(&request("thr_syn_0001", Mode::Queue, "Synthetic", id));
    assert_eq!(sent.status, Status::Accepted);
    let mut record = fake.record(id);
    assert_eq!(record["schema"], "openwiz.send-record.v1");
    assert!(record.get("attachments").is_none());
    for legacy in [false, true] {
        if legacy {
            record.as_object_mut().unwrap().remove("source");
            fs::write(fake.record_path(id), serde_json::to_vec(&record).unwrap()).unwrap();
        }
        let calls = fake.invocations();
        let files = sends_listing(&fake);
        for check in [true, false] {
            let mut args = vec!["thr_syn_0001", "--op-id", id];
            if check {
                args.push("--check");
            } else {
                args.extend(["--", "Synthetic"]);
            }
            let (code, value) = fake.cli_json(&args, "");
            assert_eq!(code, 0, "legacy {legacy}, check {check}: {value:#}");
            let report = if check {
                assert_eq!(value["result"]["kind"], "recorded");
                &value["result"]["report"]
            } else {
                &value
            };
            assert_eq!(report["status"], "accepted");
            assert_eq!(report["result"]["replayed"], true);
            assert_eq!(fake.invocations(), calls, "v1 replay called the provider");
            assert_eq!(sends_listing(&fake), files, "v1 replay changed the store");
        }
    }
}

#[test]
fn the_record_is_readable_by_the_owner_only() {
    let fake = SendFake::new("m10_owner_only", "send");
    let _ = fake.report(&request(
        "thr_syn_0001",
        Mode::Queue,
        "Synthetic",
        "op-m10-owner",
    ));
    assert_eq!(mode_of(&fake.state), 0o700);
    assert_eq!(mode_of(&fake.state.join("sends")), 0o700);
    assert_eq!(mode_of(&fake.record_path("op-m10-owner")), 0o600);
    assert_eq!(
        mode_of(&fake.state.join("sends").join("op-m10-owner.lock")),
        0o600
    );
    for entry in fs::read_dir(fake.state.join("sends")).unwrap() {
        let path = entry.unwrap().path();
        assert_eq!(mode_of(&path), 0o600, "{path:?}");
    }
}

#[test]
fn a_state_directory_others_can_read_is_refused() {
    let fake = SendFake::new("m10_open_dir", "send");
    fs::DirBuilder::new()
        .mode(0o755)
        .create(&fake.state)
        .unwrap();
    fs::set_permissions(&fake.state, fs::Permissions::from_mode(0o755)).unwrap();
    assert!(FileStore::open(&fake.state).is_err());
    let (code, out, err) = fake.cli(&["thr_syn_0001", "--", "Synthetic"], "");
    assert_eq!(code, 10, "{out}{err}");
    assert!(out.is_empty());
    assert!(err.starts_with("openwiz: "), "{err}");
    assert_eq!(fake.tell_count(), 0, "nothing sent");
}

#[test]
fn the_dispatching_mark_is_on_disk_before_the_call() {
    let fake = SendFake::new("m10_mark", "send");
    let text = "Synthetic durable mark";
    let _ = fake.report(&request("thr_syn_0001", Mode::Queue, text, "op-m10-mark"));
    let at_tell = fake.records_at_tell(1);
    assert_eq!(at_tell.len(), 1);
    let record = &at_tell[0];
    assert_eq!(record["op_id"], "op-m10-mark");
    assert_eq!(record["state"], "dispatching");
    assert!(record["dispatching_at"].is_i64(), "{record}");
    assert_eq!(
        record["text"], text,
        "the text is on disk until the outcome"
    );
    assert!(record["delivery"].is_null());
}

#[test]
fn the_text_is_kept_only_while_uncertain_or_failed() {
    let fake = SendFake::with(
        "m10_retention",
        vec![tell_response(
            "thr_syn_0003",
            "queue",
            json!({"abort": true}),
        )],
    );
    for (target, op_id, status, kept) in [
        ("thr_syn_0001", "op-m10-accepted", Status::Accepted, false),
        ("thr_syn_0006", "op-m10-queued", Status::Queued, false),
        ("thr_syn_0005", "op-m10-failed", Status::Failed, true),
        ("thr_syn_9999", "op-m10-not-found", Status::Failed, true),
        ("thr_syn_0003", "op-m10-uncertain", Status::Uncertain, true),
    ] {
        let text = format!("Synthetic retention {op_id}");
        let report = fake.report(&request(target, Mode::Queue, &text, op_id));
        assert_eq!(report.status, status, "{op_id}");
        let record = fake.record(op_id);
        assert_eq!(
            record["text"],
            if kept { json!(text) } else { json!(null) },
            "{op_id}"
        );
        assert_eq!(
            record["binding"]["text_sha256"],
            openwiz_core::messaging::sha256_hex(text.as_bytes()),
            "the hash stays"
        );
        assert_eq!(record["text_bytes"], text.len());
        let errors = validate_def("record", &record);
        assert!(errors.is_empty(), "{op_id}: {errors:#?}");
    }
}

#[test]
fn concurrent_writers_keep_every_record_whole() {
    let fake = SendFake::new("m10_concurrent", "send");
    let children: Vec<_> = (0..12)
        .map(|i| {
            fake.harness(
                "thr_syn_0001",
                "queue",
                &format!("op-m10-writer-{i}"),
                "none",
                &format!("Synthetic writer {i}"),
            )
            .spawn()
            .unwrap()
        })
        .collect();
    for child in children {
        let out = child.wait_with_output().unwrap();
        assert!(
            out.status.success(),
            "{}",
            String::from_utf8_lossy(&out.stderr)
        );
    }
    assert_eq!(fake.tell_count(), 12);
    for i in 0..12 {
        let record = fake.record(&format!("op-m10-writer-{i}"));
        assert_eq!(record["op_id"], format!("op-m10-writer-{i}"));
        assert_eq!(record["state"], "finished");
        assert_eq!(record["delivery"]["kind"], "accepted");
        assert!(validate_def("record", &record).is_empty());
    }
    let leftovers: Vec<_> = fs::read_dir(fake.state.join("sends"))
        .unwrap()
        .map(|e| e.unwrap().file_name().to_string_lossy().into_owned())
        .filter(|n| !n.ends_with(".json") && !n.ends_with(".lock"))
        .collect();
    assert!(
        leftovers.is_empty(),
        "no temporary files left: {leftovers:?}"
    );
}

/// Haiku A8: a claimer that finds the lock held by an owner with no record
/// yet takes the claim if that owner lets go while it waits.
#[test]
fn a_claimer_takes_a_lock_released_while_it_waits() {
    use openwiz_core::messaging::record::{Claim, SendRecord, SendStore};
    use openwiz_core::messaging::{Binding, OpId};
    let fake = SendFake::new("m10_lock_released", "send");
    let store = fake.store();
    let op_id = OpId::parse("op-m10-released").unwrap();
    let lock = fs::OpenOptions::new()
        .create(true)
        .truncate(false)
        .write(true)
        .open(fake.state.join("sends").join("op-m10-released.lock"))
        .unwrap();
    lock.lock().unwrap();
    let holder = std::thread::spawn(move || {
        std::thread::sleep(std::time::Duration::from_millis(300));
        drop(lock);
    });
    let record = SendRecord::claimed(
        op_id,
        Binding::new(sid("thr_syn_0001"), Mode::Queue, "Synthetic"),
        "Synthetic",
        T0,
    );
    let claim = store.claim(&record, T0).unwrap();
    holder.join().unwrap();
    assert_eq!(claim, Claim::Owned);
}

/// Sol S1: an op id is valid however it arrives. An invalid one cannot be
/// deserialized, and a record on disk with one never reaches the file
/// system as a path.
#[test]
fn an_invalid_op_id_never_becomes_a_path() {
    use openwiz_core::messaging::OpId;
    for bad in ["../../escaped", "", "-x", "a/b"] {
        assert!(
            serde_json::from_value::<OpId>(json!(bad)).is_err(),
            "deserialized {bad:?}"
        );
    }
    assert!(serde_json::from_value::<OpId>(json!("op-ok")).is_ok());

    let fake = SendFake::new("m10_planted_op_id", "send");
    let text = "Synthetic planted record";
    let _ = fake.report(&request(
        "thr_syn_0001",
        Mode::Queue,
        text,
        "op-m10-planted",
    ));
    // A record file whose op id escapes the directory, left claimed.
    let mut planted = fake.record("op-m10-planted");
    planted["op_id"] = json!("../../syn-escaped");
    planted["state"] = json!("claimed");
    planted["delivery"] = json!(null);
    fs::write(
        fake.state.join("sends").join("op-m10-planted.json"),
        serde_json::to_string(&planted).unwrap(),
    )
    .unwrap();
    let mut again = request("thr_syn_0001", Mode::Queue, text, "op-m10-planted-2");
    again.accept_possible_duplicate = false;
    let _ = fake.send(&again);
    let escaped = fake.state.join("syn-escaped.lock");
    let escaped_up = fake.state.parent().unwrap().join("syn-escaped.lock");
    assert!(!escaped.exists() && !escaped_up.exists(), "a path escaped");
}
