//! AP5 Originals unchanged, the store's half: whatever is at the source's
//! path when it is opened must be the file that was looked at. Moved from
//! `tests/attachments` by #810; the CLI's cases and the FIFO cases (they
//! run `mkfifo`) stay there.

use std::fs;
use std::path::PathBuf;

use openwiz_core::attachment::FailReason;
use openwiz_store::attachments::{Durability, Staged, Step};

use crate::bench::{Bench, CONTENT, Free, PLENTY, T0, sha256_of};

/// What [`SwapAfterLook`] puts at the source's path once it has been looked
/// at, before it is opened.
enum Swap {
    /// A link to another regular file.
    LinkTo(PathBuf),
    /// Another regular file under the same name (the original moved away,
    /// so its inode can't be reused).
    Replace(Vec<u8>),
}

struct SwapAfterLook(PathBuf, Swap);

impl Durability for SwapAfterLook {
    fn done(&self, step: Step) {
        if step != Step::Looked {
            return;
        }
        let moved = self.0.with_extension("moved");
        fs::rename(&self.0, &moved).unwrap();
        match &self.1 {
            Swap::LinkTo(other) => std::os::unix::fs::symlink(other, &self.0).unwrap(),
            Swap::Replace(bytes) => fs::write(&self.0, bytes).unwrap(),
        }
    }
}

/// Sol, round 1, R1: whatever is at the path when it is opened must be the
/// file that was looked at (the same device and inode). A file or a link
/// swapped in between is refused, never staged; a link chosen as the source
/// still stages its target.
#[test]
fn a_file_swapped_in_after_the_look_is_refused() {
    let bench = Bench::new("ap05_swapped_file");
    let other = bench.source("syn-ap05-other.txt", b"SYNTHETIC-CONTENT, swapped in\n");
    let target = bench.source("syn-ap05-target.txt", CONTENT.as_bytes());
    let store = bench.store();
    for (case, link, swap) in [
        ("a link to another file", false, Swap::LinkTo(other.clone())),
        (
            "another file",
            false,
            Swap::Replace(b"SYNTHETIC-CONTENT, new\n".to_vec()),
        ),
        (
            "a chosen link, pointed elsewhere",
            true,
            Swap::LinkTo(other.clone()),
        ),
    ] {
        let source = bench
            .sources
            .join(format!("syn-ap05-swap-{}.txt", case.len()));
        if link {
            std::os::unix::fs::symlink(&target, &source).unwrap();
        } else {
            fs::write(&source, CONTENT).unwrap();
        }
        let staged = store
            .stage_with(
                &source,
                T0,
                &Free::new(PLENTY),
                &SwapAfterLook(source.clone(), swap),
            )
            .unwrap();
        assert_eq!(staged, Staged::Failed(FailReason::SizeMismatch), "{case}");
        assert!(bench.ids().is_empty(), "{case}: nothing was staged");
    }
    // Unswapped, a chosen link stages its target's bytes.
    let link = bench.sources.join("syn-ap05-link-kept.txt");
    std::os::unix::fs::symlink(&target, &link).unwrap();
    let Staged::Ready(ready) = store.stage(&link, T0, &Free::new(PLENTY)).unwrap() else {
        panic!("a chosen link to a regular file stages");
    };
    assert_eq!(ready.attachment.sha256.as_str(), sha256_of(&target));
    assert_eq!(
        fs::read(&other).unwrap(),
        b"SYNTHETIC-CONTENT, swapped in\n",
        "the file swapped in is untouched"
    );
}
