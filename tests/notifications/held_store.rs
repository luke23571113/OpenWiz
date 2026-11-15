//! #753, synthetic state only: a notification tap waits on the held store
//! (504 at its deadline) only while every read of it answers Busy. The
//! service's own atomic save of `service/state.json`, seen by a reader that is
//! then descheduled past the private-state inspection's retry budget, used to
//! answer Unavailable, and the tap a 404 for an existing reference.
//!
//! The reader runs in a child copy of this test binary, which is paused as a
//! starved CPU deschedules it; nothing else in this binary is paused.

use openwiz_core::notifications::model::Fingerprint;
use openwiz_store::notifications::{Error, Store};
use std::fs::{self, DirBuilder, OpenOptions};
use std::io::Write;
use std::os::unix::fs::{DirBuilderExt, OpenOptionsExt};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

const READER: &str = "OPENWIZ_TEST_HELD_STORE_READER";
const NAME: &str =
    "held_store::held_store_reads_stay_busy_while_the_service_saves_its_state_in_a_stalled_process";

#[test]
fn held_store_reads_stay_busy_while_the_service_saves_its_state_in_a_stalled_process() {
    if std::env::var_os(READER).is_some() {
        return stalled_reader();
    }
    let mut reader = Command::new(std::env::current_exe().unwrap())
        .args(["--exact", NAME, "--nocapture", "--test-threads=1"])
        .env(READER, "1")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    // Pause the reader 150 ms in every 170 ms: longer than the 100 ms retry
    // budget. The loop ends when the reader has exited; it never leaves the
    // reader stopped, because the reader can't exit while stopped.
    let script =
        r#"while kill -STOP "$1" 2>/dev/null; do sleep 0.15; kill -CONT "$1"; sleep 0.02; done"#;
    let mut stalls = Command::new("/bin/sh")
        .args(["-c", script, "sh", &reader.id().to_string()])
        .spawn()
        .unwrap();
    let (out, err) = (reader.stdout.take().unwrap(), reader.stderr.take().unwrap());
    let out = std::thread::spawn(move || std::io::read_to_string(out).unwrap());
    let err = std::thread::spawn(move || std::io::read_to_string(err).unwrap());
    let status = reader.wait().unwrap();
    stalls.wait().unwrap();
    let (out, err) = (out.join().unwrap(), err.join().unwrap());
    assert!(
        status.success() && out.contains("1 passed"),
        "the stalled reader failed ({status}):\n{out}\n{err}"
    );
}

fn stalled_reader() {
    let fixture = Fixture::new();
    let store = Store::new(&fixture.0);
    store
        .initialize()
        .unwrap_or_else(|_| panic!("a safe store initializes"));
    let token = Fingerprint::new("e".repeat(64)).unwrap();
    let held = store
        .lock()
        .unwrap_or_else(|_| panic!("the test holds the store"));
    // The service's State::save: a private temporary file renamed over
    // service/state.json, while the store's lock is held by someone else.
    let stop = Arc::new(AtomicBool::new(false));
    let writer = std::thread::spawn({
        let (root, stop) = (fixture.0.clone(), stop.clone());
        move || {
            let (temporary, state) = (
                root.join("service/.state.tmp"),
                root.join("service/state.json"),
            );
            let mut saves = 0_u64;
            while !stop.load(Ordering::Relaxed) {
                write_private(&temporary);
                fs::rename(&temporary, &state).unwrap();
                saves += 1;
            }
            saves
        }
    });
    let (began, mut reads, mut not_busy) = (Instant::now(), 0_u64, 0_u64);
    while began.elapsed() < Duration::from_secs(6) {
        reads += 1;
        if !matches!(store.target(&token), Err(Error::Busy)) {
            not_busy += 1;
        }
    }
    stop.store(true, Ordering::Relaxed);
    let saves = writer.join().unwrap();
    assert!(saves > 0 && reads > 0, "{saves} saves, {reads} reads");
    assert_eq!(
        not_busy, 0,
        "{not_busy} of {reads} held reads were not Busy during {saves} safe saves"
    );
    // The store itself stayed safe and readable: an unknown token is absent.
    drop(held);
    assert!(matches!(store.target(&token), Ok(None)));
}

struct Fixture(PathBuf);
impl Fixture {
    fn new() -> Self {
        let path = std::env::temp_dir().join(format!("openwiz-held-store-{}", std::process::id()));
        let _ = fs::remove_dir_all(&path);
        DirBuilder::new().mode(0o700).create(&path).unwrap();
        DirBuilder::new()
            .mode(0o700)
            .create(path.join("service"))
            .unwrap();
        for name in ["config.json", "state.json"] {
            write_private(&path.join("service").join(name));
        }
        Self(path)
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}
fn write_private(path: &Path) {
    OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(path)
        .unwrap()
        .write_all(b"{}")
        .unwrap();
}
