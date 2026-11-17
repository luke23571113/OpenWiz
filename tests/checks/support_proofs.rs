//! The shared test support's own proofs (#811). Each support file is
//! compiled into several targets; its tests live here so they run once, in
//! the checks target CI always runs, instead of once per including target.

use std::fs;
use std::path::Path;
use std::thread;
use std::time::{Duration, Instant};

use serde_json::json;

use crate::forks::{LIMIT, file_id, lock_on, wait_until_unlocked};
use crate::real_time::{Form, form_in, scale};
use crate::schema::{lint, validate};

// tests/support/real_time.rs

/// The scaling rule, on literal durations.
#[test]
fn a_scaled_duration_covers_the_measured_read_within_its_cap() {
    let ms = Duration::from_millis;
    let cases = [
        // (nominal, measured, cap, expected)
        (ms(2000), ms(0), ms(20000), ms(2000)),
        (ms(2000), ms(100), ms(20000), ms(2000)),
        (ms(2000), ms(500), ms(20000), ms(2000)),
        (ms(2000), ms(501), ms(20000), ms(2004)),
        (ms(2000), ms(1300), ms(20000), ms(5200)),
        (ms(2000), ms(9000), ms(20000), ms(20000)),
        (ms(1000), ms(250), ms(15000), ms(1000)),
        (ms(1000), ms(1000), ms(15000), ms(4000)),
        (ms(10000), ms(3000), ms(20000), ms(12000)),
        (ms(2000), Duration::MAX, ms(20000), ms(20000)),
    ];
    for (nominal, measured, cap, expected) in cases {
        assert_eq!(
            scale(nominal, measured, cap),
            expected,
            "{nominal:?} {measured:?} {cap:?}"
        );
    }
}

/// The context matrix: only the exact first-attempt pull request to `main`
/// gets the fast form.
#[test]
fn only_a_first_attempt_pull_request_to_main_gets_the_fast_form() {
    let pr = [
        ("GITHUB_ACTIONS", "true"),
        ("GITHUB_EVENT_NAME", "pull_request"),
        ("GITHUB_BASE_REF", "main"),
        ("GITHUB_RUN_ATTEMPT", "1"),
    ];
    let form_of = |vars: &[(&str, &str)]| {
        let vars: Vec<(String, String)> = vars
            .iter()
            .map(|(k, v)| ((*k).to_owned(), (*v).to_owned()))
            .collect();
        form_in(&|name| vars.iter().find(|(k, _)| k == name).map(|(_, v)| v.clone()))
    };
    let with = |name: &str, value: Option<&str>| {
        let mut vars: Vec<(&str, &str)> = pr.iter().copied().filter(|(k, _)| *k != name).collect();
        if let Some(value) = value {
            vars.push((name, value));
        }
        form_of(&vars)
    };
    assert_eq!(form_of(&pr), Form::Fast, "a first-attempt PR to main");
    assert_eq!(form_of(&[]), Form::Full, "a local run");
    let mut full_too = pr.to_vec();
    full_too.push(("OPENWIZ_TESTS_FULL", ""));
    assert_eq!(form_of(&full_too), Form::Full, "an explicit full run wins");
    for (name, value) in [
        ("GITHUB_ACTIONS", None),
        ("GITHUB_ACTIONS", Some("false")),
        ("GITHUB_ACTIONS", Some("TRUE")),
        ("GITHUB_EVENT_NAME", None),
        ("GITHUB_EVENT_NAME", Some("push")),
        ("GITHUB_EVENT_NAME", Some("schedule")),
        ("GITHUB_EVENT_NAME", Some("workflow_dispatch")),
        ("GITHUB_EVENT_NAME", Some("merge_group")),
        ("GITHUB_EVENT_NAME", Some("pull_request_target")),
        ("GITHUB_EVENT_NAME", Some("Pull_request")),
        ("GITHUB_BASE_REF", None),
        ("GITHUB_BASE_REF", Some("")),
        ("GITHUB_BASE_REF", Some("release-0.0.7")),
        ("GITHUB_BASE_REF", Some("main-null")),
        ("GITHUB_BASE_REF", Some(" main")),
        ("GITHUB_RUN_ATTEMPT", None),
        ("GITHUB_RUN_ATTEMPT", Some("2")),
        ("GITHUB_RUN_ATTEMPT", Some("01")),
        ("GITHUB_RUN_ATTEMPT", Some("")),
    ] {
        assert_eq!(with(name, value), Form::Full, "{name}={value:?}");
    }
}

// tests/support/forks.rs

/// The wait's own proof: a lock is listed while it is held, a child's copy
/// of the open file keeps it listed after this process lets go, and it is
/// gone once that child is.
#[test]
fn a_lock_stays_listed_while_a_childs_copy_holds_it() {
    use std::process::{Command, Stdio};
    let dir = Path::new(env!("CARGO_TARGET_TMPDIR"))
        .join("forks")
        .join(std::process::id().to_string());
    let _ = fs::remove_dir_all(&dir);
    crate::dirs::private_dir_all(&dir).expect("dir");
    let path = dir.join("held.lock");
    fs::write(&path, "").expect("file");
    let id = file_id(&path);
    assert_eq!(lock_on(&id), None, "never locked yet");
    let file = fs::File::open(&path).expect("open");
    file.try_lock().expect("lock");
    wait_until_listed(&id);
    // A child with a copy of the locked open file, as a fork makes one.
    let mut child = Command::new("sleep")
        .arg("600")
        .stdin(Stdio::from(file.try_clone().expect("a copy")))
        .spawn()
        .expect("start sleep");
    drop(file);
    let line = wait_until_listed(&id);
    assert!(line.contains("FLOCK"), "{line}");
    child.kill().expect("stop sleep");
    child.wait().expect("reap sleep");
    wait_until_unlocked(&path);
    assert_eq!(lock_on(&id), None, "nobody can lock it again");
    let _ = fs::remove_dir_all(&dir);
}

/// Other tests take and drop locks while /proc/locks is being read. A
/// single scan missed this proof's held lock on CI (#1391); re-read before
/// asserting presence. The kernel cause of that omission is unverified.
/// Only use this while a known open descriptor keeps the lock held.
fn wait_until_listed(id: &str) -> String {
    let started = Instant::now();
    loop {
        if let Some(line) = lock_on(id) {
            return line;
        }
        assert!(
            started.elapsed() < LIMIT,
            "held lock {id} was not listed in /proc/locks after {LIMIT:?}"
        );
        thread::sleep(Duration::from_millis(1));
    }
}

// tests/support/schema.rs

// Messaging's exact parity reproducer uses this checker. Accepting a
// keyword without enforcing it would silently accept invalid requests.
#[test]
fn shared_text_keywords_are_linted_and_enforced() {
    let schema = json!({
        "$ref": "#/$defs/text",
        "$defs": {"text": {
            "type": "string", "pattern": "^[A-Z][A-Za-zé]*$", "maxUtf8Bytes": 4
        }}
    });
    assert_eq!(lint(&schema), Vec::<String>::new());
    for (text, expected) in [
        ("A", true),
        ("Aé", true),
        ("AZZZ", true),
        ("Aéé", false),
        ("AZZZZ", false),
        ("abc", false),
        ("", false),
    ] {
        assert_eq!(
            validate(&schema, &json!(text)).is_empty(),
            expected,
            "{text:?}"
        );
    }
    let branches = json!({"oneOf": [
        {"type": "string", "pattern": "^A$"},
        {"type": "string", "pattern": "^B$"}
    ]});
    for (text, expected) in [("A", true), ("B", true), ("C", false)] {
        assert_eq!(
            validate(&branches, &json!(text)).is_empty(),
            expected,
            "{text:?}"
        );
    }
    for bad in [
        json!({"type": "string", "pattern": "^.$"}),
        json!({"type": "string", "pattern": 3}),
        json!({"type": "integer", "pattern": "^A$"}),
        json!({"type": "string", "maxUtf8Bytes": -1}),
        json!({"type": "integer", "maxUtf8Bytes": 4}),
        json!({"type": "array", "uniqueItems": false}),
        json!({"type": "array", "minItems": -1}),
        json!({"type": "string", "unknownRule": true}),
    ] {
        assert!(!lint(&bad).is_empty(), "unchecked rule: {bad}");
    }
}

// tests/support/place.rs

/// Descriptors of this process open for writing on `path`'s file.
fn writers(path: &Path) -> usize {
    use std::os::unix::fs::MetadataExt;
    let target = fs::metadata(path).unwrap();
    fs::read_dir("/proc/self/fd")
        .unwrap()
        .filter_map(|fd| {
            let fd = fd.ok()?.file_name();
            let file = fs::metadata(Path::new("/proc/self/fd").join(&fd)).ok()?;
            let info = fs::read_to_string(Path::new("/proc/self/fdinfo").join(&fd)).ok()?;
            let flags = info.lines().find_map(|l| l.strip_prefix("flags:"))?;
            let access = u32::from_str_radix(flags.trim(), 8).unwrap() & 3;
            (file.dev() == target.dev() && file.ino() == target.ino() && access != 0).then_some(())
        })
        .count()
}

/// The ETXTBSY flake's cause, held still: the copy is paused mid-way on a
/// FIFO, and at that moment this process must hold no writable descriptor
/// for the placed program, which a child forked then would inherit. Then the
/// placed program runs.
#[test]
fn placing_a_program_leaves_no_writer_a_concurrent_fork_could_inherit() {
    use std::io::Write;
    use std::os::unix::fs::OpenOptionsExt;
    let dir = Path::new(env!("CARGO_TARGET_TMPDIR"))
        .join("place")
        .join(std::process::id().to_string());
    let _ = fs::remove_dir_all(&dir);
    crate::dirs::private_dir_all(&dir).expect("dir");
    let fifo = dir.join("source.fifo");
    let made = std::process::Command::new("mkfifo").arg(&fifo).status();
    assert!(made.expect("mkfifo runs").success());
    let program = dir.join("placed");
    let placing = {
        let (fifo, program) = (fifo.clone(), program.clone());
        thread::spawn(move || crate::place::place(&fifo, &program))
    };
    // Open the FIFO's writer without blocking, once the copier reads it.
    let until = Instant::now() + LIMIT;
    let mut source = loop {
        // O_NONBLOCK on Linux: ENXIO until a reader has the FIFO open.
        match fs::OpenOptions::new()
            .write(true)
            .custom_flags(0o4000)
            .open(&fifo)
        {
            Ok(file) => break file,
            Err(_) if Instant::now() < until && !placing.is_finished() => {
                thread::sleep(Duration::from_millis(1))
            }
            Err(e) => panic!("the copier never opened the FIFO: {e}"),
        }
    };
    let head = b"#!/bin/sh\n";
    source.write_all(head).expect("first bytes");
    while fs::metadata(&program).map_or(true, |m| m.len() < head.len() as u64) {
        assert!(Instant::now() < until, "the copy never started");
        thread::sleep(Duration::from_millis(1));
    }
    let held = writers(&program);
    source.write_all(b"printf 'PLACED\\n'\n").expect("the rest");
    drop(source);
    placing.join().expect("placed");
    assert_eq!(
        held, 0,
        "mid-copy, this process held a writable descriptor for the placed \
         program: a child forked then keeps it busy (ETXTBSY)"
    );
    let run = std::process::Command::new(&program).output().unwrap();
    assert_eq!(run.stdout, b"PLACED\n");
    let _ = fs::remove_dir_all(&dir);
}
