//! B4 (ClosedWiz#120): the archive's one shape, `thread archive <id>
//! --json`, the CloudRoom allowlist's third write, built from the allowlist
//! alone. Moved here from `tests/fleet/b4_archive.rs` by TV4 (#806); the
//! archives on the recording fake `room-cli` stay there.

use openwiz_adapter_cloudroom::allowlist::{Invocation, ThreadId};

#[test]
fn the_archive_is_built_in_exactly_its_one_shape() {
    let id = ThreadId::parse("thr_syn_0001").expect("an id");
    assert_eq!(
        Invocation::ThreadArchive(id).argv(),
        ["thread", "archive", "thr_syn_0001", "--json"]
    );
    // The id is one argument and never a flag: `ThreadId` can't hold one.
    for bad in ["", "-x", "--self", "thr syn", "thr;syn"] {
        assert!(ThreadId::parse(bad).is_err(), "{bad:?}");
    }
}
