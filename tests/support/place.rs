//! Placing an executable fixture (#811).
//!
//! A test binary runs its tests on several threads, and most of them start
//! programs. Each start forks this process, and the child keeps a copy of
//! every descriptor this process had open at that moment until it runs its
//! program. If this process holds a writable descriptor for an executable it
//! is placing, such a child keeps that file busy, and starting it fails with
//! ETXTBSY ("Text file busy"), as `tests/cli-agent/init.rs` did on #811's
//! base (as #1754, #2559 and #2583 elsewhere).

use std::os::unix::fs::PermissionsExt;
use std::path::Path;

/// Copies the program `src` to `dst` and makes it executable, owner-only.
pub fn place(src: &Path, dst: &Path) {
    let mut from = std::fs::File::open(src).unwrap();
    let mut to = std::fs::File::create(dst).unwrap();
    std::io::copy(&mut from, &mut to).unwrap_or_else(|e| panic!("copy {}: {e}", dst.display()));
    drop(to);
    std::fs::set_permissions(dst, std::fs::Permissions::from_mode(0o700)).unwrap();
}

/// Places a fixture script the same way, from a source file that never runs.
pub fn place_script(dst: &Path, text: &str) {
    let src = dst.with_extension("src");
    std::fs::write(&src, text).unwrap();
    place(&src, dst);
    std::fs::remove_file(&src).unwrap();
}
