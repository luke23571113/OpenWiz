//! Waiting out a forked child's copy of a lock (#176, the flakes on #146).
//!
//! A test binary runs its tests on several threads, and most of them start
//! programs. Each start forks this process, and the child keeps a copy of
//! every file this process had open at that moment until it runs its
//! program (each one is close-on-exec). A lock (`flock`) belongs to the open
//! file, and the child's copy is the same open file. So a lock a test has
//! just let go of can still be held for a moment by a child that another
//! test's thread forked while the test held it.
//!
//! [`wait_until_unlocked`] waits for the explicit state the test needs:
//! `/proc/locks` (Linux) lists no lock on the file. A lock stays listed
//! while any copy of its open file is left, even one a fork is still
//! making. It never takes the lock itself to look: a lock taken to look is
//! one more open file a fork could copy.
//!
//! Its own proof is in `tests/checks/support_proofs.rs`, so it runs once,
//! not once per target that includes this file (#811).

use std::fs;
use std::os::unix::fs::MetadataExt;
use std::path::Path;
use std::thread;
use std::time::{Duration, Instant};

/// How long a lock may stay held before the wait fails.
pub const LIMIT: Duration = Duration::from_secs(10);

/// Waits until no process holds a lock on `path`'s file. Call it once this
/// process has let go of the lock: from then on no new copy of it can be
/// made, and each copy left goes when its child runs its program. Fails
/// after [`LIMIT`], with the lock's line.
pub fn wait_until_unlocked(path: &Path) {
    let id = file_id(path);
    let started = Instant::now();
    while let Some(line) = lock_on(&id) {
        assert!(
            started.elapsed() < LIMIT,
            "{} is still locked after {LIMIT:?}: {line}",
            path.display()
        );
        thread::sleep(Duration::from_millis(1));
    }
}

/// The line of `/proc/locks` for a lock on the file `id` names, if any.
pub fn lock_on(id: &str) -> Option<String> {
    fs::read_to_string("/proc/locks")
        .expect("read /proc/locks")
        .lines()
        .find(|line| line.split_whitespace().any(|field| field == id))
        .map(str::to_owned)
}

/// How `/proc/locks` names `path`'s file: `MAJOR:MINOR:INODE`, the device
/// numbers in hex, split as Linux splits a device number.
pub fn file_id(path: &Path) -> String {
    let meta = fs::metadata(path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    let dev = meta.dev();
    let major = ((dev >> 8) & 0xfff) | ((dev >> 32) & !0xfff);
    let minor = (dev & 0xff) | ((dev >> 12) & !0xff);
    format!("{major:02x}:{minor:02x}:{}", meta.ino())
}
