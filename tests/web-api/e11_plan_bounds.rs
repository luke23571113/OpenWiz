//! EP1 transport guards and shared-slot behavior, using private synthetic FIFOs.
use crate::{
    e11_plan_support as p,
    fake::{self, Fake},
    http::{self, Gated, TestServer},
    support::FakeGh,
};
use openwiz_adapter_github::plan::Request;
use openwiz_server::{Config, Limits, Plan};
use serde_json::{Value, json};
use std::{
    fs,
    io::Write,
    process::Command,
    sync::{Arc, Condvar, Mutex},
    thread,
    time::{Duration, Instant},
};

#[test]
fn e11_plan_exact_get_has_all_existing_guards_and_private_route_logs() {
    let gh = p::github("ep1-guards", p::responses(vec![], vec![]));
    let room = Fake::new("ep1-guards-room", "normal");
    let log = Arc::new(Mutex::new(vec![]));
    let lines = log.clone();
    let first_not_found = (Mutex::new(false), Condvar::new());
    let server = openwiz_server::start_with_plan(
        openwiz_server::bind(0).unwrap(),
        Default::default(),
        Arc::new(room.source()),
        Arc::new(fake::clock()),
        Arc::new(move |line| {
            let status = line.split_whitespace().nth(2).unwrap();
            let (observed, ready) = &first_not_found;
            // The response is already sent. Hold its 421 log until a later
            // request's 404 is logged, reproducing CI's callback order.
            if status == "421" {
                let (seen, _) = ready
                    .wait_timeout_while(observed.lock().unwrap(), Duration::from_secs(5), |seen| {
                        !*seen
                    })
                    .unwrap();
                assert!(*seen, "the later 404 callback did not arrive");
            }
            lines.lock().unwrap().push(line.to_owned());
            if status == "404" {
                *observed.lock().unwrap() = true;
                ready.notify_one();
            }
        }),
        None,
        Some(Plan::with_program(gh.program())),
    )
    .unwrap();
    let s = TestServer {
        addr: server.local_addr(),
        server,
        log,
    };
    let mut expected = vec![];
    for method in [
        "HEAD",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
        "CONNECT",
        "TRACE",
        "SYNTHETIC",
    ] {
        let r = s.request(method, "/api/v1/plan");
        assert_eq!(r.status, 405);
        assert_eq!(r.header("Allow"), Some("GET"));
        crate::c3_routes::headers(&r);
        expected.push((PLAN, 405));
        if method == "HEAD" {
            assert!(r.body.is_empty());
            assert_eq!(r.header("Content-Length"), None);
        }
    }
    for suffix in ["?", "?secret=synthetic-secret", "?limit=1", "?x=1&x=2"] {
        let r = s.get(&format!("/api/v1/plan{suffix}"));
        assert_eq!(r.status, 400);
        crate::c3_routes::headers(&r);
        expected.push((PLAN, 400));
    }
    for framing in [
        "Content-Length: 1\r\n",
        "Transfer-Encoding: chunked\r\n",
        "Content-Length: 0\r\nContent-Length: 0\r\n",
    ] {
        let r = s.send(
            format!(
                "GET /api/v1/plan HTTP/1.1\r\nHost: {}\r\n{framing}\r\nx",
                s.host()
            )
            .as_bytes(),
        );
        assert_eq!(r.status, 400);
        crate::c3_routes::headers(&r);
        expected.push((PLAN, 400));
    }
    let r = s.send(b"GET /api/v1/plan HTTP/1.1\r\nHost: foreign.example.invalid\r\n\r\n");
    assert_eq!(r.status, 421);
    expected.push((PLAN, 421));
    for path in ["/api/v1/plan/", "/api/v1/Plan", "/api/v1/plan/902"] {
        assert_eq!(s.get(path).status, 404);
        expected.push(("-", 404));
    }
    assert!(gh.invocations().is_empty());
    assert!(room.invocations().is_empty());
    let r = s.get("/api/v1/plan");
    assert_eq!(r.status, 200);
    crate::c3_routes::headers(&r);
    expected.push((PLAN, 200));
    let log = s.settled_log();
    let lines: Vec<_> = log.lines().collect();
    let position = |status| {
        lines
            .iter()
            .position(|line| line.split_whitespace().nth(2) == Some(status))
            .unwrap()
    };
    // The 421's log line was held until the later 404 logged (#423).
    assert!(position("404") < position("421"));
    // Callback order is unconstrained; the (route, status) pairs, their exact
    // text and counts are not (#429).
    assert_route_log(&log, &expected);
    assert!(!log.contains("synthetic-secret"));
    assert_eq!(gh.invocations().len(), 3);
}

const PLAN: &str = "/api/v1/plan";

/// The server's log for `expected`'s requests, one line each, in any order
/// (#429): the same (route, status) pairs, each as many times, and every
/// route the plan's or `-`.
fn assert_route_log(log: &str, expected: &[(&str, u16)]) {
    let mut logged: Vec<_> = log
        .lines()
        .map(|line| {
            let fields: Vec<_> = line.split_whitespace().collect();
            assert!(fields[1] == PLAN || fields[1] == "-", "route in {line:?}");
            (fields[1].to_owned(), fields[2].to_owned())
        })
        .collect();
    let mut want: Vec<_> = expected
        .iter()
        .map(|(route, status)| ((*route).to_owned(), status.to_string()))
        .collect();
    logged.sort();
    want.sort();
    assert_eq!(logged, want);
}

fn gated(name: &str, limits: Limits) -> (Fake, FakeGh, Arc<Gated>, TestServer, String) {
    let gh = p::github(name, p::responses(vec![], vec![]));
    let fifo = gh.dir.join("plan-pipe");
    assert!(
        Command::new("mkfifo")
            .arg(&fifo)
            .status()
            .unwrap()
            .success()
    );
    let path = gh.dir.join("plan.json");
    let scenario: Value = serde_json::from_str(&fs::read_to_string(&path).unwrap()).unwrap();
    let output = scenario["responses"][2]["stdout"]
        .as_str()
        .unwrap()
        .to_owned();
    use std::os::unix::fs::PermissionsExt;
    let wrapper = gh.dir.join("gated-gh");
    let dir = gh.dir.display();
    let script = format!(
        "#!/bin/sh\nif ln '{dir}/gated-gh' '{dir}/gate-once' 2>/dev/null; then\n: > '{dir}/gate-entered'\ncat '{dir}/plan-pipe' >/dev/null\nfi\nexec '{}' \"$@\"\n",
        gh.program().display()
    );
    // A sibling fork must never inherit a writable executable descriptor.
    // Only the writer child opens this inode; wait before starting the server.
    let mut writer = Command::new("/bin/sh")
        .args(["-c", "umask 077; cat > \"$1\"", "fixture-writer"])
        .arg(&wrapper)
        .stdin(std::process::Stdio::piped())
        .spawn()
        .unwrap();
    writer
        .stdin
        .take()
        .unwrap()
        .write_all(script.as_bytes())
        .unwrap();
    assert!(writer.wait().unwrap().success(), "write gated gh wrapper");
    fs::set_permissions(&wrapper, fs::Permissions::from_mode(0o700)).unwrap();
    let room = Fake::new(&format!("{name}-room"), "normal");
    let gate = Arc::new(Gated::new(Arc::new(room.source())));
    let log = Arc::new(Mutex::new(vec![]));
    let lines = log.clone();
    let server = openwiz_server::start_with_plan(
        openwiz_server::bind(0).unwrap(),
        Config {
            limits,
            ..Default::default()
        },
        gate.clone(),
        Arc::new(fake::clock()),
        Arc::new(move |line| lines.lock().unwrap().push(line.to_owned())),
        None,
        Some(Plan::with_program(wrapper)),
    )
    .unwrap();
    let s = TestServer {
        addr: server.local_addr(),
        server,
        log,
    };
    (room, gh, gate, s, output)
}
fn wait_gate(gh: &FakeGh) {
    let until = Instant::now() + Duration::from_secs(5);
    while !gh.dir.join("gate-entered").is_file() {
        assert!(
            Instant::now() < until,
            "GitHub wrapper did not reach its gate"
        );
        thread::yield_now();
    }
}
fn release(gh: &FakeGh, output: &str) {
    fs::OpenOptions::new()
        .write(true)
        .open(gh.dir.join("plan-pipe"))
        .unwrap()
        .write_all(output.as_bytes())
        .unwrap();
}
fn ungate(gh: &FakeGh, output: &str) {
    let path = gh.dir.join("plan.json");
    let mut v: Value = serde_json::from_str(&fs::read_to_string(&path).unwrap()).unwrap();
    v["responses"][2] = json!({"argv":Request::Issues.argv(None),"stdout":output});
    fs::write(path, v.to_string()).unwrap();
}

#[test]
fn e11_plan_shares_inflight_only_and_competes_with_inventory_for_two_slots() {
    let (_room, gh, gate, s, output) = gated(
        "ep1-flight",
        Limits {
            slot_wait: Duration::from_millis(80),
            ..Default::default()
        },
    );
    let addr = s.addr;
    let inventory = thread::spawn(move || http::get(addr, "/api/v1/inventory"));
    gate.wait_held(1);
    let a = thread::spawn(move || http::get(addr, "/api/v1/plan"));
    wait_gate(&gh);
    let b = thread::spawn(move || http::get(addr, "/api/v1/plan"));
    s.wait_for("shared plan and inventory", |s| {
        s.core_runs == 2 && s.attached == 3
    });
    let r = s.get("/api/v1/inventory?limit=2");
    assert_eq!(r.status, 503);
    assert_eq!(r.header("Retry-After"), Some("5"));
    assert_eq!(gh.invocations().len(), 0);
    assert_eq!(gate.runs(), 1);
    release(&gh, &output);
    gate.open();
    let a = a.join().unwrap();
    let b = b.join().unwrap();
    assert_eq!(a.status, 200);
    assert_eq!(a.body, b.body);
    assert_eq!(inventory.join().unwrap().status, 200);
    s.wait_for("runs released", |s| s.core_runs == 0);
    ungate(&gh, &output);
    assert_eq!(s.get("/api/v1/plan").status, 200);
    assert_eq!(gh.invocations().len(), 6);
}
#[test]
fn e11_plan_deadline_retains_its_slot_until_the_source_really_finishes() {
    let (_room, gh, gate, s, output) = gated(
        "ep1-deadline",
        Limits {
            // The gate forces expiration; recovery admission is observed below.
            request_deadline: Duration::from_secs(2),
            slot_wait: Duration::from_millis(60),
            ..Default::default()
        },
    );
    let addr = s.addr;
    let plan = thread::spawn(move || http::get(addr, "/api/v1/plan"));
    wait_gate(&gh);
    assert_eq!(plan.join().unwrap().status, 504);
    assert_eq!(s.server.stats().core_runs, 1);
    let inventory = thread::spawn(move || http::get(addr, "/api/v1/inventory"));
    gate.wait_held(1);
    let r = s.get("/api/v1/inventory?limit=2");
    assert_eq!(r.status, 503);
    assert_eq!(r.header("Retry-After"), Some("5"));
    assert_eq!(s.get("/api/v1/plan").status, 504);
    assert_eq!(gh.invocations().len(), 0);
    assert_eq!(s.server.stats().core_runs, 2);
    release(&gh, &output);
    gate.open();
    assert_eq!(inventory.join().unwrap().status, 504);
    s.wait_for("timed out sources actually finish", |s| s.core_runs == 0);
    // Re-arm the source gate: recovery must admit a fresh worker and free
    // its slot after actual completion, even if launching it is slow. A
    // healthy 200 is owned by the shared-flight keeper above; requiring it
    // inside this deliberately short HTTP deadline races scheduling (#936).
    fs::remove_file(gh.dir.join("gate-entered")).unwrap();
    fs::remove_file(gh.dir.join("gate-once")).unwrap();
    let recovered = thread::spawn(move || http::get(addr, "/api/v1/plan"));
    wait_gate(&gh);
    assert_eq!(
        s.server.stats().core_runs,
        1,
        "a fresh plan owns the freed slot"
    );
    assert_eq!(
        gh.invocations().len(),
        3,
        "recovery is held before its first call"
    );
    assert_eq!(recovered.join().unwrap().status, 504);
    assert_eq!(
        s.server.stats().core_runs,
        1,
        "HTTP expiry still cannot free it"
    );
    release(&gh, &output);
    s.wait_for("the recovery source actually finishes", |s| {
        s.core_runs == 0
    });
    assert_eq!(gh.invocations().len(), 6);
}
