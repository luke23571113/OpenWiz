//! A fixture service stopped together with every program it started.
//!
//! Killing only the service leaves a fixture script it had just started (a
//! `room` or `gh` script) running, and that script can still write into the
//! fixture's directory while the test removes it: `DirectoryNotEmpty` (#719,
//! #762). The service leads its own process group, so those scripts are in it
//! too; stopping it kills the whole group and waits until no member is left.
//! A program that moves to a group of its own (the loop-check and update
//! runners do) is not covered.

use openwiz_core::limits::RUN_BUDGET;
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};

/// The running fixture service; dropping it stops its whole process group.
pub struct Service(pub Child);

impl Service {
    /// Starts `command` as the leader of a new process group.
    pub fn start(command: &mut Command) -> Self {
        use std::os::unix::process::CommandExt;
        Self(command.process_group(0).spawn().unwrap())
    }
}

/// Sends `signal` to process group `group` through `/bin/kill`; true when it
/// was delivered, so when the group still has a member.
fn signal_group(signal: &str, group: &str) -> bool {
    Command::new("/bin/kill")
        .args([signal, "--", group])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .is_ok_and(|status| status.success())
}

impl Drop for Service {
    fn drop(&mut self) {
        // The leader is not reaped yet, so its id still names only this group.
        let group = format!("-{}", self.0.id());
        signal_group("-KILL", &group);
        let _ = self.0.kill();
        let _ = self.0.wait();
        // Killed members stay in the group until they are reaped.
        let until = Instant::now() + RUN_BUDGET;
        while signal_group("-0", &group) {
            if Instant::now() >= until {
                if !std::thread::panicking() {
                    panic!("the fixture service's process group outlived its stop");
                }
                return;
            }
            std::thread::park_timeout(Duration::from_millis(5));
        }
    }
}
