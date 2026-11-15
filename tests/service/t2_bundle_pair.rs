//! BX1 (#2098): CloudRoom runs one app as two mounts of the same AppImage
//! file: the GUI on one mount, and its direct child, the AppImage bridge
//! supervisor, on another. Only that exact pair is accepted, and its
//! launcher comes from the bridge's mount; every other shape of two or more
//! running roots stays `Ambiguous`.
//!
//! Synthetic proc and mount relationships only; no real process is read.
//! Synthetic assumptions (shape seen in the read-only PC discovery, values
//! invented): the GUI's own environment names no mount, its direct parent
//! (the AppImage's launcher shell, outside every mount) carries `APPDIR` =
//! the GUI's mount, and the bridge head carries `APPDIR` = its own mount;
//! both carry the same `APPIMAGE`.
//!
//! Red run (2026-11-08, before the pair rule): `cargo test -p openwiz-tests
//! --test service t2_bundle_pair` exited 101: the accepted pair got
//! `Err(Ambiguous)`, expected `Ok(<bridge mount>/.../room-cli)`, in both
//! tests (the refusal table's first baseline is that pair). Log:
//! `private/evidence/bx1/red-run.txt`. Each refusal row's guard is proven by
//! the mutation runs in `private/evidence/bx1/mutations.txt`.

use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};

use openwiz_adapter_cloudroom::locate::{Basis, LocateError};

use super::{Fixture, TAIL, dirs};

const GUI: &str = ".mount_synthetic_gui";
const BRIDGE: &str = ".mount_synthetic_bridge";
const THIRD: &str = ".mount_synthetic_third";
const LAUNCHER: &str = "#!/bin/sh\n\":\" //; exit 0\n";

/// The PC's shape: launcher shell 100 starts the GUI 201 on GUI, which
/// starts the bridge supervisor 301 on BRIDGE; each has a child.
struct Pair {
    f: Fixture,
    appimage: PathBuf,
}

impl Pair {
    fn new() -> Self {
        let f = Fixture::new();
        for mount in [GUI, BRIDGE, THIRD] {
            let cli = f.file(format!("{mount}/{TAIL}"));
            super::process::executable(&cli, LAUNCHER);
        }
        let appimage = f.file("home/Synthetic-x86_64.AppImage");
        let pair = Self { f, appimage };
        pair.shell("100", "1", &pair.record(GUI));
        pair.app("201", GUI, "100", None);
        pair.app("202", GUI, "201", None);
        pair.app("301", BRIDGE, "201", Some(&pair.record(BRIDGE)));
        pair.app("302", BRIDGE, "301", Some(&pair.record(BRIDGE)));
        pair
    }

    fn mount(&self, mount: &str) -> PathBuf {
        self.f.0.join(mount)
    }

    fn cli(&self, mount: &str) -> PathBuf {
        self.mount(mount).join(TAIL)
    }

    fn proc(&self, pid: &str) -> PathBuf {
        self.f.process_root().join(pid)
    }

    /// The AppImage runtime's environment for `mount`, among unrelated values.
    fn record(&self, mount: &str) -> Vec<u8> {
        environ(&[
            "HOME=/home/synthetic".as_bytes(),
            format!("APPDIR={}", self.mount(mount).display()).as_bytes(),
            format!("APPIMAGE={}", self.appimage.display()).as_bytes(),
            b"OWD=/home/synthetic",
        ])
    }

    fn stat(&self, pid: &str, ppid: &str) {
        fs::write(
            self.proc(pid).join("stat"),
            format!("{pid} (synthetic (x)) S {ppid} {pid} {pid} 0 -1 4194560 0\n"),
        )
        .unwrap();
    }

    // Synthetic full stat: starttime is field 22. The comm deliberately
    // includes spaces and parentheses, which are legal kernel stat content.
    fn identity(&self, pid: &str, parent: &str, start: u64) {
        fs::write(
            self.proc(pid).join("stat"),
            format!(
                "{pid} (synthetic (reader)) S {parent} 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 {start} 0\n"
            ),
        )
        .unwrap();
    }

    fn locator(&self) -> String {
        let pid = std::process::id().to_string();
        self.shell(&pid, "1", b"");
        self.identity(&pid, "1", 100);
        pid
    }

    /// A process outside every mount (the launcher shell), with its parent.
    fn shell(&self, pid: &str, ppid: &str, environ: &[u8]) {
        let shell = self.f.0.join("bin/synthetic-shell");
        if !shell.exists() {
            self.f.file("bin/synthetic-shell");
        }
        dirs::private_dir_all(self.proc(pid)).unwrap();
        std::os::unix::fs::symlink(shell, self.proc(pid).join("exe")).unwrap();
        self.stat(pid, ppid);
        fs::write(self.proc(pid).join("environ"), environ).unwrap();
    }

    /// A process running the mount's app binary, with its parent and,
    /// optionally, a readable environment.
    fn app(&self, pid: &str, mount: &str, ppid: &str, environ: Option<&[u8]>) {
        self.f.running(mount, pid);
        self.stat(pid, ppid);
        if let Some(environ) = environ {
            fs::write(self.proc(pid).join("environ"), environ).unwrap();
        }
    }

    fn set_environ(&self, pid: &str, environ: &[u8]) {
        fs::write(self.proc(pid).join("environ"), environ).unwrap();
    }

    fn resolve(&self) -> Result<PathBuf, LocateError> {
        self.f.discovery().resolve()
    }
}

fn environ(entries: &[&[u8]]) -> Vec<u8> {
    let mut bytes = Vec::new();
    for entry in entries {
        bytes.extend_from_slice(entry);
        bytes.push(0);
    }
    bytes
}

/// A record naming `appdir` and `appimage` exactly, nothing else checked.
fn named(appdir: &Path, appimage: &Path) -> Vec<u8> {
    environ(&[
        format!("APPDIR={}", appdir.display()).as_bytes(),
        format!("APPIMAGE={}", appimage.display()).as_bytes(),
    ])
}

// #2852 reopened: synthetic assumption, not a live process observation. A
// GUI helper is launched through a shell outside both mounts. BX1 used to
// count it as another GUI head; #2866 only excludes the locator's children.
// Claim: the server's Sessions read, then create-form options and preview
// reads, all rediscover the same verified pair, including concurrent requests.
// Red on main (2026-11-14):
// cargo test -p openwiz-tests --test service t2_bundle_pair_server_reads -- --nocapture
// /api/v1/inventory: HTTP/1.1 502 Bad Gateway
// "kind": "read_failed"
// "message": "thread list could not be run: CloudRoom not running: room-cli
// could not be started (ambiguous app bundles). ..."
// test result: FAILED. 0 passed; 1 failed; 64 filtered out.
// #2991 red (2026-11-14): the same command with only thread-list logging
// suppressed (responses unchanged) exited 101 at the exact count: 0 != 1.
// Suppressing only cloud-status logging exited 101 at its count: 0 != 2.
// The HTTP status/verdict checks passed in both runs; nonempty version logs
// alone therefore no longer satisfy this proof.
#[test]
fn t2_bundle_pair_server_reads_accept_a_helper_through_an_intermediate_shell() {
    use std::io::{BufRead, BufReader, Read, Write};
    use std::net::{SocketAddr, TcpStream};
    use std::process::{Child, Command, Stdio};
    use std::time::Duration;

    struct Server(Child);
    impl Drop for Server {
        fn drop(&mut self) {
            let _ = self.0.kill();
            let _ = self.0.wait();
        }
    }
    let pair = Pair::new();
    for (pid, parent, start) in [("201", "100", 100), ("301", "201", 110)] {
        pair.identity(pid, parent, start);
    }
    let calls = pair.f.0.join("calls");
    let script = format!(
        r#"#!/bin/sh
":" //; printf '%s %s\n' "$0" "$*" >> '{}'
case "$1 $2" in
  '--version ') printf 'v141\n';;
  'project list') printf '%s\n' '[{{"id":"prj_syn_0001","name":"Synthetic","kind":"standard","gitRemoteUrl":"https://github.com/synthetic-owner/synthetic-repo.git","createdAt":1699100600000,"updatedAt":1699200600000,"sources":[]}}]';;
  'cloud status') printf '%s\n' '{{"ready":true,"harnesses":[{{"id":"codex","model":"synthetic-model","reasoning_levels":["high"],"models":[{{"model":"synthetic-model","reasoning_levels":["high"]}}]}}]}}';;
  'thread list'|'machine list') printf '[]\n';;
  *) exit 97;;
esac
"#,
        calls.display()
    );
    for mount in [GUI, BRIDGE] {
        super::process::executable(&pair.cli(mount), &script);
    }
    let child = Command::new(super::process::fixture_binary("openwiz-server"))
        .args(["--port", "0", "--allowed-host", "synthetic.example"])
        .env("OPENWIZ_FIXTURE_ROOT", &pair.f.0)
        .env("OPENWIZ_STATE_DIR", pair.f.0.join("state"))
        .env_remove(openwiz_server::ALLOWED_HOST_ENV)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    let mut server = Server(child);
    let stderr = server.0.stderr.take().unwrap();
    let (tx, rx) = std::sync::mpsc::channel();
    let reader = std::thread::spawn(move || {
        let mut stderr = BufReader::new(stderr);
        let mut line = String::new();
        stderr.read_line(&mut line).unwrap();
        tx.send(line).unwrap();
        std::io::copy(&mut stderr, &mut std::io::sink()).unwrap();
    });
    let first = rx.recv_timeout(Duration::from_secs(10)).unwrap();
    let address: SocketAddr = first
        .trim()
        .strip_prefix("openwiz-server: listening on http://")
        .and_then(|s| s.split(' ').next())
        .unwrap_or_else(|| panic!("server did not announce its address: {first}"))
        .parse()
        .unwrap();
    let request = |method: &str, path: &str, body: &str| {
        let mut stream = TcpStream::connect(address).unwrap();
        stream
            .set_read_timeout(Some(Duration::from_secs(10)))
            .unwrap();
        write!(stream, "{method} {path} HTTP/1.1\r\nHost: synthetic.example\r\nOrigin: https://synthetic.example\r\nSec-Fetch-Site: same-origin\r\nX-OpenWiz-Send: 1\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}", body.len()).unwrap();
        let mut response = String::new();
        stream.read_to_string(&mut response).unwrap();
        response
    };
    let read_form = || {
        for (method, path, body) in [
            ("GET", "/api/v1/inventory", ""),
            ("GET", "/api/v1/cloud-options", ""),
            (
                "POST",
                "/api/v1/projects/prj_syn_0001/threads/preview",
                r#"{"op_id":"0123456789abcdef0123456789abcdef","harness":"codex","model":"synthetic-model","effort":"high","text":"Synthetic preview","attachments":[]}"#,
            ),
        ] {
            let response = request(method, path, body);
            assert!(response.starts_with("HTTP/1.1 200 "), "{path}: {response}");
            assert!(!response.contains("ambiguous app bundles"), "{response}");
            assert!(!response.contains("could not be started"), "{response}");
            let body: serde_json::Value =
                serde_json::from_str(response.split_once("\r\n\r\n").unwrap().1).unwrap();
            if path == "/api/v1/cloud-options" {
                assert_eq!(body["state"]["kind"], "offered", "{body}");
            } else if method == "POST" {
                assert_eq!(body["verdict"]["kind"], "ready", "{body}");
            }
        }
    };
    let count = |suffix: &str| {
        fs::read_to_string(&calls)
            .unwrap()
            .lines()
            .filter(|line| line.ends_with(suffix))
            .count()
    };
    read_form(); // The unchanged pair works before the helper starts.
    assert_eq!(count(" thread list --json"), 1);
    assert_eq!(count(" cloud status --json"), 2);
    pair.shell("500100", "201", b"");
    pair.identity("500100", "201", 120);
    pair.app("500000", GUI, "500100", None);
    pair.identity("500000", "500100", 130);
    read_form(); // Red on main: inventory returns 502 / Ambiguous here.
    assert_eq!(count(" thread list --json"), 2);
    assert_eq!(count(" cloud status --json"), 4);
    std::thread::scope(|scope| {
        for _ in 0..8 {
            scope.spawn(|| {
                for _ in 0..8 {
                    read_form();
                }
            });
        }
    });
    // A broken ancestry proof never licenses the pair, nor a third bundle.
    for (parent, start) in [("1", 120), ("301", 120), ("201", 140), ("500000", 120)] {
        pair.identity("500100", parent, start);
        assert_eq!(pair.resolve(), Err(LocateError::Ambiguous));
    }
    pair.identity("500100", "201", 120);
    pair.app("500001", THIRD, "500100", None);
    pair.identity("500001", "500100", 130);
    assert_eq!(pair.resolve(), Err(LocateError::Ambiguous));
    drop(server);
    reader.join().unwrap();
    let ran = fs::read_to_string(&calls).unwrap();
    assert!(
        ran.lines()
            .all(|line| line.split_once(' ').unwrap().0 == pair.cli(BRIDGE).to_str().unwrap()),
        "only the verified bridge launcher may run: {ran}"
    );
    assert!(!ran.contains("thread spawn"), "preview must only read");
    // Runs::call shares identical in-flight reads, so the 64 concurrent
    // forms cannot promise exactly 66 thread lists and 132 cloud statuses
    // overall. The two serial forms above pin exact counts for inventory,
    // options and preview; concurrency must add each read within those bounds.
    // Default inventory has no hidden/archived flags.
    assert!(
        (3..=66).contains(&count(" thread list --json")),
        "concurrent inventories must reach thread list: {ran}"
    );
    assert!(
        (6..=132).contains(&count(" cloud status --json")),
        "concurrent options and previews must reach cloud status: {ran}"
    );
}

#[test]
fn t2_bundle_pair_gui_and_its_bridge_from_one_appimage_select_the_bridge_launcher() {
    let pair = Pair::new();
    assert_eq!(pair.resolve(), Ok(pair.cli(BRIDGE)));
    // The diagnostics record the choice: the bridge's mount, beside the GUI's.
    let located = pair.f.discovery().locate().unwrap();
    assert_eq!(
        located.basis,
        Basis::AppImagePair {
            gui: pair.mount(GUI),
            bridge: pair.mount(BRIDGE),
        }
    );
    assert_eq!(
        located.basis.describe(),
        format!(
            "room-cli from the bridge's mount {} (paired with the GUI's mount {}: \
             one AppImage file, identical room-cli)",
            pair.mount(BRIDGE).display(),
            pair.mount(GUI).display()
        )
    );
    // The same pair with the bridge's own helpers gone is still the pair.
    fs::remove_dir_all(pair.proc("302")).unwrap();
    assert_eq!(pair.resolve(), Ok(pair.cli(BRIDGE)));
    // With the GUI's tree gone, the bridge's mount is the one running root,
    // selected as before BX1 with no record read.
    for pid in ["100", "201", "202"] {
        fs::remove_dir_all(pair.proc(pid)).unwrap();
    }
    fs::remove_file(pair.proc("301").join("environ")).unwrap();
    let located = pair.f.discovery().locate().unwrap();
    assert_eq!(
        (located.launcher, located.basis),
        (pair.cli(BRIDGE), Basis::OneRoot)
    );
}

// #2852 synthetic assumption: a bundled CLI runs the bridge mount's app
// executable as a child of the locator, outside the GUI/bridge process tree.
// Keep overlapping reads' proc entries present behind a barrier, so the red
// reproduces the ambiguity without depending on OS scheduling or live reads.
// Red (#2852, 2026-11-14), before descendant exclusion:
// cargo test -p openwiz-tests --test service t2_bundle_pair_concurrent_reads -- --nocapture
// assertion `left == right` failed: 256 concurrent reads
//   left: 256
//  right: 0
// test result: FAILED. 0 passed; 1 failed; 0 ignored; 61 filtered out.
#[test]
fn t2_bundle_pair_concurrent_reads_ignore_only_verified_locator_descendants() {
    use openwiz_adapter_cloudroom::source::CloudRoomSource;
    use openwiz_core::source::SessionSource;
    use std::sync::Barrier;
    use std::time::{Duration, Instant};

    const READERS: usize = 8;
    const READS: usize = 32;
    let pair = Pair::new();
    let locator = pair.locator();
    pair.shell("500100", &locator, b"");
    pair.identity("500100", &locator, 110);
    for index in 0..READERS {
        let pid = (500_000 + index).to_string();
        let parent = if index % 2 == 0 { &locator } else { "500100" };
        pair.app(&pid, BRIDGE, parent, Some(&pair.record(BRIDGE)));
        pair.identity(&pid, parent, 120);
    }
    let launcher = "#!/bin/sh\n\":\" //; printf 'v141\\n'\n";
    for mount in [GUI, BRIDGE] {
        super::process::executable(&pair.cli(mount), launcher);
    }
    let discovery = pair.f.discovery();
    let barrier = Barrier::new(READERS);
    let read_concurrently = || {
        std::thread::scope(|scope| {
            let workers: Vec<_> = (0..READERS)
                .map(|_| {
                    scope.spawn(|| {
                        barrier.wait();
                        (0..READS)
                            .map(|_| {
                                discovery.resolve().map(|launcher| {
                                    CloudRoomSource::new(launcher)
                                        .version(Instant::now() + Duration::from_secs(5))
                                })
                            })
                            .collect::<Vec<_>>()
                    })
                })
                .collect();
            workers
                .into_iter()
                .flat_map(|w| w.join().unwrap())
                .collect::<Vec<_>>()
        })
    };
    let results = read_concurrently();
    let ambiguous = results
        .iter()
        .filter(|r| matches!(r, Err(LocateError::Ambiguous)))
        .count();
    assert_eq!(ambiguous, 0, "{} concurrent reads", READERS * READS);
    assert_eq!(results.len(), READERS * READS);
    for result in results {
        assert_eq!(result, Ok(Ok("v141".to_owned())));
    }

    // Same launcher bytes and layout, but another canonical AppImage path
    // and inode: own children never license choosing between distinct apps.
    let other = pair.f.file("home/Other-x86_64.AppImage");
    pair.set_environ("301", &named(&pair.mount(BRIDGE), &other));
    let results = read_concurrently();
    assert_eq!(results.len(), READERS * READS);
    assert!(
        results
            .iter()
            .all(|r| matches!(r, Err(LocateError::Ambiguous)))
    );
}

// Claim: a parent name, environment record, incomplete chain or recycled pid
// cannot hide an independent head. Existing BX1 cases don't exercise the
// descendant exemption. Every case first proves its valid chain is accepted.
#[test]
fn t2_bundle_pair_unproven_locator_children_remain_ambiguous() {
    type Break = fn(&Pair, &str);
    let cases: &[(&str, Break)] = &[
        ("missing child stat", |p, _| {
            fs::remove_file(p.proc("500000").join("stat")).unwrap()
        }),
        ("missing locator stat", |p, me| {
            fs::remove_file(p.proc(me).join("stat")).unwrap()
        }),
        ("short child stat", |p, _| p.stat("500000", "500100")),
        ("wrong stat pid", |p, _| {
            fs::write(p.proc("500000").join("stat"), "999 (synthetic) S 500100\n").unwrap()
        }),
        ("unrelated parent", |p, _| p.identity("500000", "1", 120)),
        ("missing intermediate", |p, _| {
            fs::remove_file(p.proc("500100").join("stat")).unwrap()
        }),
        ("parent cycle", |p, _| p.identity("500100", "500000", 110)),
        ("reused locator pid", |p, me| p.identity(me, "1", 130)),
        ("reused intermediate pid", |p, me| {
            p.identity("500100", me, 130)
        }),
        ("oversized stat", |p, _| {
            fs::write(p.proc("500000").join("stat"), "x".repeat(4097)).unwrap()
        }),
        ("non-numeric parent", |p, _| {
            p.identity("500000", "+500100", 120)
        }),
        ("ancestry exceeds the walk bound", |p, me| {
            let mut parent = me.to_owned();
            for index in 0..64 {
                let pid = (501_000 + index).to_string();
                p.shell(&pid, &parent, b"");
                p.identity(&pid, &parent, 110);
                parent = pid;
            }
            p.identity("500000", &parent, 120);
        }),
    ];
    for (name, break_chain) in cases {
        let pair = Pair::new();
        let locator = pair.locator();
        pair.shell("500100", &locator, b"");
        pair.identity("500100", &locator, 110);
        pair.app("500000", BRIDGE, "500100", Some(&pair.record(BRIDGE)));
        pair.identity("500000", "500100", 120);
        assert_eq!(pair.resolve(), Ok(pair.cli(BRIDGE)), "{name}: baseline");
        break_chain(&pair, &locator);
        assert_eq!(pair.resolve(), Err(LocateError::Ambiguous), "{name}");
    }

    // Even a proven child on a third mount must pass the original bundle
    // checks. Ignoring it before verification would hide these violations.
    type Change = fn(&Pair);
    let invalid: &[(&str, Change)] = &[
        ("bad launcher prefix", |p| {
            fs::write(p.cli(THIRD), "synthetic impostor\n").unwrap()
        }),
        ("writable launcher", |p| {
            fs::set_permissions(p.cli(THIRD), fs::Permissions::from_mode(0o777)).unwrap()
        }),
    ];
    for (name, break_bundle) in invalid {
        let pair = Pair::new();
        let locator = pair.locator();
        pair.app("500000", THIRD, &locator, None);
        pair.identity("500000", &locator, 120);
        assert_eq!(
            pair.resolve(),
            Err(LocateError::Ambiguous),
            "{name}: baseline"
        );
        break_bundle(&pair);
        assert_eq!(pair.resolve(), Err(LocateError::UnexpectedFile), "{name}");
    }
}

// Claim (#2906): the final re-read of every ancestry link stops a pid reused
// during the walk from supplying the descendant proof. The intermediate's
// stat is a FIFO that serves the valid identity to its first reader only;
// while that reader still holds it, the path is replaced by the reused pid's
// identity (new starttime), so only a later read sees the change. Every
// static case above already fails during the walk itself.
// Red (#2906, 2026-11-14), with the `family.iter().rev().all(...)` clause
// deleted:
// cargo test -p openwiz-tests --test service t2_bundle_pair_an_ancestor
// assertion `left == right` failed
//   left: Ok(<synthetic bridge launcher>)
//  right: Err(Ambiguous)
#[test]
fn t2_bundle_pair_an_ancestor_reused_after_the_walk_reads_it_stays_ambiguous() {
    use std::io::Write;
    use std::os::unix::fs::FileTypeExt;

    let pair = Pair::new();
    let locator = pair.locator();
    pair.shell("500100", &locator, b"");
    pair.identity("500100", &locator, 110);
    pair.app("500000", BRIDGE, "500100", Some(&pair.record(BRIDGE)));
    pair.identity("500000", "500100", 120);
    assert_eq!(pair.resolve(), Ok(pair.cli(BRIDGE)), "baseline");

    let stat = pair.proc("500100").join("stat");
    let reused = pair.proc("500100").join("stat.reused");
    let valid = fs::read(&stat).unwrap();
    pair.identity("500100", &locator, 130);
    fs::rename(&stat, &reused).unwrap();
    let made = std::process::Command::new("mkfifo").arg(&stat).status();
    assert!(made.is_ok_and(|status| status.success()), "mkfifo");
    let writer = {
        let stat = stat.clone();
        std::thread::spawn(move || {
            // Opening blocks until the walk opens the stat for reading.
            let mut fifo = fs::OpenOptions::new().write(true).open(&stat).unwrap();
            fs::rename(&reused, &stat).unwrap();
            fifo.write_all(&valid).unwrap();
        })
    };
    let result = pair.resolve();
    let served = !fs::symlink_metadata(&stat).unwrap().file_type().is_fifo();
    if !served {
        // Release the writer so a broken fixture fails instead of hanging.
        let _ = fs::read(&stat);
    }
    writer.join().unwrap();
    assert!(served, "the walk never read the intermediate stat");
    assert_eq!(result, Err(LocateError::Ambiguous));
}

#[test]
fn t2_bundle_pair_every_other_shape_stays_ambiguous() {
    // R1 red (#2852): this test exited 101 before the bundle comparison:
    // distinct verified bundle under the locator beside the pair
    // left: Ok(<synthetic bridge launcher>), right: Err(Ambiguous).
    // test result: FAILED. 0 passed; 1 failed; 62 filtered out.
    type Shape = fn(&Pair);
    let shapes: [(&str, Shape); 36] = [
        (
            "distinct verified bundle under the locator beside the pair",
            |p| {
                let locator = p.locator();
                super::process::executable(
                    &p.cli(THIRD),
                    "#!/bin/sh\n\":\" //; printf 'v999\\n'\n",
                );
                p.app("500000", THIRD, &locator, None);
                p.identity("500000", &locator, 120);
            },
        ),
        (
            "distinct verified bundle under the locator beside one root",
            |p| {
                let locator = p.locator();
                super::process::executable(
                    &p.cli(THIRD),
                    "#!/bin/sh\n\":\" //; printf 'v999\\n'\n",
                );
                p.app("500000", THIRD, &locator, None);
                p.identity("500000", &locator, 120);
                for pid in ["100", "201", "202"] {
                    fs::remove_dir_all(p.proc(pid)).unwrap();
                }
            },
        ),
        // Two unrelated apps.
        ("bridge started by init, not the GUI", |p| {
            p.stat("301", "1")
        }),
        ("bridge started by the launcher shell", |p| {
            p.stat("301", "100")
        }),
        ("bridge started by a GUI helper", |p| p.stat("301", "202")),
        ("GUI started by the bridge", |p| {
            p.stat("301", "100");
            p.stat("201", "301");
        }),
        // Lineage that doesn't check out.
        ("a second, independent start on the bridge mount", |p| {
            p.app("303", BRIDGE, "1", Some(&p.record(BRIDGE)));
        }),
        ("a second, independent start on the GUI mount", |p| {
            p.app("203", GUI, "100", None);
        }),
        ("a GUI-mount process under the bridge", |p| {
            p.app("203", GUI, "301", None);
        }),
        ("a parent cycle on the bridge mount", |p| {
            p.app("303", BRIDGE, "304", None);
            p.app("304", BRIDGE, "303", None);
        }),
        ("a bridge-mount process with no parent record", |p| {
            fs::remove_file(p.proc("302").join("stat")).unwrap();
        }),
        ("the GUI with no parent record", |p| {
            fs::remove_file(p.proc("201").join("stat")).unwrap();
        }),
        ("a stat line for another pid", |p| {
            fs::write(p.proc("301").join("stat"), "999 (synthetic) S 201 1\n").unwrap();
        }),
        ("a malformed parent field", |p| {
            fs::write(p.proc("301").join("stat"), "301 (synthetic) S +201 1\n").unwrap();
        }),
        ("the GUI's launcher runs from the bridge's mount", |p| {
            p.stat("201", "302");
            p.set_environ("302", &p.record(GUI));
        }),
        ("the GUI's launcher is gone", |p| {
            fs::remove_dir_all(p.proc("100")).unwrap();
        }),
        // Different AppImage files, or records that don't name them.
        ("bridge from another AppImage file", |p| {
            let other = p.f.file("home/Other-x86_64.AppImage");
            p.set_environ("301", &named(&p.mount(BRIDGE), &other));
        }),
        ("GUI from another AppImage file", |p| {
            let other = p.f.file("home/Other-x86_64.AppImage");
            p.set_environ("100", &named(&p.mount(GUI), &other));
        }),
        ("the same AppImage through a symlink", |p| {
            let link = p.f.0.join("home/link.AppImage");
            std::os::unix::fs::symlink(&p.appimage, &link).unwrap();
            p.set_environ("301", &named(&p.mount(BRIDGE), &link));
        }),
        (
            "both records name the AppImage through a symlinked folder",
            |p| {
                let folder = p.f.0.join("home-link");
                std::os::unix::fs::symlink(p.f.0.join("home"), &folder).unwrap();
                let link = folder.join("Synthetic-x86_64.AppImage");
                p.set_environ("301", &named(&p.mount(BRIDGE), &link));
                p.set_environ("100", &named(&p.mount(GUI), &link));
            },
        ),
        ("the AppImage path is gone", |p| {
            fs::remove_file(&p.appimage).unwrap()
        }),
        ("the AppImage path is a directory", |p| {
            fs::remove_file(&p.appimage).unwrap();
            dirs::private_dir(&p.appimage).unwrap();
        }),
        ("a relative AppImage path", |p| {
            let relative = Path::new("home/Synthetic-x86_64.AppImage");
            p.set_environ("301", &named(&p.mount(BRIDGE), relative));
            p.set_environ("100", &named(&p.mount(GUI), relative));
        }),
        ("the bridge record names the GUI's mount", |p| {
            p.set_environ("301", &named(&p.mount(GUI), &p.appimage));
        }),
        ("the launcher record names the bridge's mount", |p| {
            p.set_environ("100", &named(&p.mount(BRIDGE), &p.appimage));
        }),
        ("the bridge head has no record", |p| {
            fs::remove_file(p.proc("301").join("environ")).unwrap();
        }),
        ("the bridge record has APPDIR twice", |p| {
            let mut twice = p.record(BRIDGE);
            twice.extend(environ(&[
                format!("APPDIR={}", p.mount(BRIDGE).display()).as_bytes()
            ]));
            p.set_environ("301", &twice);
        }),
        ("the launcher record has no APPIMAGE", |p| {
            p.set_environ(
                "100",
                &environ(&[format!("APPDIR={}", p.mount(GUI).display()).as_bytes()]),
            );
        }),
        // Differing launcher bytes.
        ("differing room-cli bytes", |p| {
            super::process::executable(&p.cli(GUI), "#!/bin/sh\n\":\" //; exit 1\n");
        }),
        // A third root.
        ("a third running root", |p| p.app("401", THIRD, "201", None)),
        // A failed permission check on either root.
        ("GUI room-cli group-writable", |p| {
            fs::set_permissions(p.cli(GUI), fs::Permissions::from_mode(0o775)).unwrap();
        }),
        ("bridge room-cli not executable", |p| {
            fs::set_permissions(p.cli(BRIDGE), fs::Permissions::from_mode(0o644)).unwrap();
        }),
        ("GUI room-cli missing a sibling", |p| {
            fs::remove_file(p.cli(GUI).with_file_name("index.js")).unwrap();
        }),
        ("bridge room-cli missing a sibling", |p| {
            fs::remove_file(p.cli(BRIDGE).with_file_name("daemon-bundle.mjs")).unwrap();
        }),
        ("GUI app binary group-writable", |p| {
            let app = p.mount(GUI).join("synthetic-app");
            fs::set_permissions(app, fs::Permissions::from_mode(0o575)).unwrap();
        }),
        ("GUI room-cli without the launcher prefix", |p| {
            super::process::executable(&p.cli(GUI), "#!/bin/sh\nexit 0\n");
            super::process::executable(&p.cli(BRIDGE), "#!/bin/sh\nexit 0\n");
        }),
    ];
    // The scan's existing per-process checks refuse these before any pair
    // is considered, with their existing error, as for one running root.
    let scan_refusals = [
        "GUI room-cli missing a sibling",
        "bridge room-cli missing a sibling",
        "GUI app binary group-writable",
    ];
    for (name, shape) in shapes {
        let pair = Pair::new();
        assert_eq!(pair.resolve(), Ok(pair.cli(BRIDGE)), "baseline for {name}");
        shape(&pair);
        let expected = if scan_refusals.contains(&name) {
            LocateError::UnexpectedFile
        } else {
            LocateError::Ambiguous
        };
        assert_eq!(pair.resolve(), Err(expected), "{name}");
    }
}

// R1 (#2101 review): the choice reaches the owner through production
// dispatch, as one sanitized stderr diagnostic beside the one JSON document,
// once per process however many room-cli calls the command makes.
// Red run (2026-11-08, before the diagnostic): this test exited 101: stderr
// was empty, expected the one note line. Log: `private/evidence/bx1/red-run-r1.txt`.
#[test]
fn t2_bundle_pair_the_cli_reports_the_chosen_mount_once_on_stderr() {
    let pair = Pair::new();
    let calls = answering(&pair);
    let out = std::process::Command::new(super::process::fixture_binary("openwiz"))
        .args(["ls", "--json"])
        .env("OPENWIZ_FIXTURE_ROOT", &pair.f.0)
        .output()
        .unwrap();
    assert!(
        out.status.success(),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
    let json: serde_json::Value = serde_json::from_slice(&out.stdout).unwrap();
    assert_eq!(json["schema"], "openwiz.inventory.v1");
    assert_eq!(
        String::from_utf8(out.stderr).unwrap(),
        format!(
            "openwiz: note: room-cli from the bridge's mount {} (paired with the GUI's \
             mount {}: one AppImage file, identical room-cli)\n",
            pair.mount(BRIDGE).display(),
            pair.mount(GUI).display()
        )
    );
    let ran: Vec<_> = fs::read_to_string(&calls)
        .unwrap()
        .lines()
        .map(|line| line.split_once(' ').unwrap().0.to_owned())
        .collect();
    assert_eq!(ran.len(), 4, "every room-cli call of ls");
    assert!(
        ran.iter().all(|path| Path::new(path) == pair.cli(BRIDGE)),
        "{ran:?}"
    );
    // One running root, as before BX1: no note at all.
    for pid in ["100", "201", "202"] {
        fs::remove_dir_all(pair.proc(pid)).unwrap();
    }
    let out = std::process::Command::new(super::process::fixture_binary("openwiz"))
        .args(["ls", "--json"])
        .env("OPENWIZ_FIXTURE_ROOT", &pair.f.0)
        .output()
        .unwrap();
    assert!(
        out.status.success(),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
    assert_eq!(String::from_utf8(out.stderr).unwrap(), "");
}

#[test]
fn t2_bundle_pair_the_description_carries_no_control_characters() {
    let basis = Basis::AppImagePair {
        gui: PathBuf::from("/tmp/.mount_gui\u{1b}[31m"),
        bridge: PathBuf::from("/tmp/.mount_bridge\nforged line\r"),
    };
    assert_eq!(
        basis.describe(),
        "room-cli from the bridge's mount /tmp/.mount_bridge?forged line? (paired with the \
         GUI's mount /tmp/.mount_gui?[31m: one AppImage file, identical room-cli)"
    );
}

/// Byte-identical answering launchers in both mounts; each call's `$0` (which
/// mount's file ran) and arguments go to the returned log.
fn answering(pair: &Pair) -> PathBuf {
    let calls = pair.f.0.join("calls");
    let script = format!(
        "#!/bin/sh\n\":\" //; printf '%s %s\\n' \"$0\" \"$*\" >> '{}'\nif [ \"$1\" = --version ]; then printf 'v141\\n'; else printf '[]\\n'; fi\n",
        calls.display()
    );
    for mount in [GUI, BRIDGE] {
        super::process::executable(&pair.cli(mount), &script);
    }
    calls
}

/// Runs the fixture `openwiz` (production dispatch) with `stderr`, and gives
/// it 60 seconds to finish; a hung run is killed and fails the test.
fn bounded(pair: &Pair, args: &[&str], stderr: std::process::Stdio) -> std::process::Output {
    let empty = pair.f.0.join("empty-path");
    if !empty.exists() {
        dirs::private_dir(&empty).unwrap();
    }
    let child = std::process::Command::new(super::process::fixture_binary("openwiz"))
        .args(args)
        .env("OPENWIZ_FIXTURE_ROOT", &pair.f.0)
        // No gh: GitHub's reads fail at once; CloudRoom's still run.
        .env("PATH", &empty)
        .stdout(std::process::Stdio::piped())
        .stderr(stderr)
        .spawn()
        .unwrap();
    let pid = child.id();
    let (done, finished) = std::sync::mpsc::channel();
    std::thread::spawn(move || done.send(child.wait_with_output()));
    match finished.recv_timeout(std::time::Duration::from_secs(60)) {
        Ok(out) => out.unwrap(),
        Err(_) => {
            let _ = std::process::Command::new("/bin/kill")
                .args(["-KILL", &pid.to_string()])
                .status();
            panic!("openwiz {args:?} did not finish within 60 s");
        }
    }
}

// R2 (#2101 review 2): `fleet` reads CloudRoom on a worker thread while CLI
// dispatch holds the stderr lock; the pair note must not wait for that lock.
// Red run (2026-11-08, before the fix): killed after 60 s, deadlocked.
// Log: `private/evidence/bx1/red-run-r2-r3.txt`.
#[test]
fn t2_bundle_pair_fleet_reads_cloudroom_off_the_main_thread_without_hanging() {
    let pair = Pair::new();
    let calls = answering(&pair);
    let out = bounded(
        &pair,
        &["fleet", "1", "--json"],
        std::process::Stdio::piped(),
    );
    let stderr = String::from_utf8(out.stderr).unwrap();
    assert_eq!(
        stderr
            .matches("openwiz: note: room-cli from the bridge's mount")
            .count(),
        1,
        "{stderr}"
    );
    let doc: serde_json::Value = serde_json::from_slice(&out.stdout).unwrap();
    assert!(doc.is_object(), "{doc}");
    let ran = fs::read_to_string(&calls).unwrap();
    assert!(
        ran.lines().any(|line| line.ends_with(" --version")),
        "{ran}"
    );
}

// R3 (#2101 review 2): a failing diagnostic sink never aborts the command.
// Red run (2026-11-08, before the fix): exit 101, the `eprintln!` panic
// (its own message could not reach the full stderr either).
#[test]
fn t2_bundle_pair_a_failing_stderr_never_aborts_the_command() {
    let pair = Pair::new();
    answering(&pair);
    let full = fs::OpenOptions::new()
        .write(true)
        .open("/dev/full")
        .unwrap();
    let out = bounded(&pair, &["ls", "--json"], std::process::Stdio::from(full));
    assert_eq!(out.status.code(), Some(0));
    let doc: serde_json::Value = serde_json::from_slice(&out.stdout).unwrap();
    assert_eq!(doc["schema"], "openwiz.inventory.v1");
}
