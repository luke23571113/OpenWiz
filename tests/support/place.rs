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

/// Copies the program `src` to `dst` and makes it executable, owner-only. A
/// separate `cp` writes it, so this process never holds its writer.
pub fn place(src: &Path, dst: &Path) {
    // `cp` would copy into a directory and succeed (#2721).
    assert!(!dst.is_dir(), "{} is a directory", dst.display());
    let out = std::process::Command::new("cp")
        .arg("--")
        .arg(src)
        .arg(dst)
        .stdin(std::process::Stdio::null())
        .output()
        .expect("cp runs");
    assert!(
        out.status.success(),
        "cp {}: {}",
        dst.display(),
        String::from_utf8_lossy(&out.stderr)
    );
    std::fs::set_permissions(dst, std::fs::Permissions::from_mode(0o700)).unwrap();
}

/// Places a fixture script the same way, from a source file that never runs.
pub fn place_script(dst: &Path, text: &str) {
    let src = dst.with_extension("src");
    std::fs::write(&src, text).unwrap();
    place(&src, dst);
    std::fs::remove_file(&src).unwrap();
}
