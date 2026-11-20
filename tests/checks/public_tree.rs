//! A public-tree promise from #1277, restored by #1270: every public link in
//! contracts, code, apps and tests uses OpenWiz's final address. No other
//! check keeps the retired address out of these paths.

use std::process::Command;

const ROOT: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/..");

#[test]
fn public_files_use_the_final_openwiz_address() {
    let old = concat!("jparker2006/", "OpenWiz");
    // CI prunes files a job never reads from the worktree. Check the public
    // Git index so this guard still covers those files without requiring
    // deleted files (or build output) to exist on disk.
    let output = Command::new("git")
        .args(["grep", "--cached", "-a", "-l", "-z", "-F", "-e", old])
        .args(["--", "contracts", "crates", "apps", "tests"])
        .current_dir(ROOT)
        .output()
        .expect("scan the public Git index");
    assert!(
        matches!(output.status.code(), Some(0 | 1)),
        "git grep failed"
    );
    assert!(
        output.status.code() == Some(1),
        "old OpenWiz address in: {}",
        String::from_utf8_lossy(&output.stdout).replace('\0', "\n")
    );
}
