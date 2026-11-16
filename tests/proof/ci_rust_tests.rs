//! `ci/rust-tests.sh`, as #1260 changed it: on its one-command path, a pull
//! request to `main` keeps #1253's main-only skips after the 8 test threads,
//! and the fixture release `openwiz` is built first.
//!
//! The run's other rules (the release fixture first and once on either path,
//! a failed build starts no test, 8 test threads, a failed test run fails
//! the step) are checked by `.github/actions/docs-only/test_rust_runner.sh`,
//! which CI runs on every change (#805's ledger). This case runs the real
//! script with a fake `cargo` and `nproc` first on `PATH` and a fake cgroup
//! (`RUST_TESTS_ROOT`); the fake `cargo` logs each call and runs nothing.

use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::Path;
use std::process::Command;

const ROOT: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/..");

const PREBUILD: &str = "build --release --locked -p openwiz-tests --example openwiz";

#[test]
fn a_pull_request_to_main_keeps_the_main_only_skips_with_eight_threads() {
    let dir = Path::new(env!("CARGO_TARGET_TMPDIR")).join("ci-prebuild-threads-pr");
    let _ = fs::remove_dir_all(&dir);
    let bin = dir.join("bin");
    crate::dirs::private_dir_all(&bin).unwrap();
    let log = dir.join("cargo.log");
    let script = |name: &str, body: &str| {
        let file = bin.join(name);
        fs::write(&file, format!("#!/bin/sh\n{body}")).unwrap();
        fs::set_permissions(&file, fs::Permissions::from_mode(0o755)).unwrap();
    };
    script(
        "cargo",
        "printf '%s\\n' \"$*\" >> \"$FAKE_CARGO_LOG\"\nexit 0\n",
    );
    // Fewer than 4 CPUs: one `cargo test --workspace`.
    script("nproc", "echo 2\n");
    let fake_root = dir.join("root");
    let cgroup = fake_root.join("sys/fs/cgroup");
    crate::dirs::private_dir_all(&cgroup).unwrap();
    crate::dirs::private_dir_all(fake_root.join("proc/self")).unwrap();
    fs::write(cgroup.join("cgroup.controllers"), "cpu memory\n").unwrap();
    fs::write(fake_root.join("proc/self/cgroup"), "0::/\n").unwrap();
    let path_var = format!(
        "{}:{}",
        bin.display(),
        std::env::var("PATH").unwrap_or_default()
    );
    let out = Command::new("sh")
        .arg("ci/rust-tests.sh")
        .current_dir(ROOT)
        .env("PATH", path_var)
        .env("RUST_TESTS_ROOT", &fake_root)
        .env("FAKE_CARGO_LOG", &log)
        .env("GITHUB_EVENT_NAME", "pull_request")
        .env("GITHUB_BASE_REF", "main")
        .output()
        .expect("run ci/rust-tests.sh");
    let calls: Vec<String> = fs::read_to_string(&log)
        .unwrap_or_default()
        .lines()
        .map(str::to_owned)
        .collect();
    assert_eq!(out.status.code(), Some(0), "{calls:?}");
    assert_eq!(
        calls,
        [
            PREBUILD,
            "test --workspace --locked -- --test-threads=8 --exact \
             --skip a_candidate_that_exits_without_readiness_rolls_back_to_the_running_old_build \
             --skip a_failing_merge_is_kept_and_recorded_once_without_retrying_the_gate \
             --skip a_passing_main_merge_is_staged_but_not_reported_as_running \
             --skip a_real_candidate_must_confirm_readiness_before_selection_or_switched"
        ]
    );
}
