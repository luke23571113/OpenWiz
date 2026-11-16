//! AP4 Ready means verified. Stopping the process right after each staging
//! step leaves either nothing usable (removed at the next open) or a fully
//! verified attachment, never a ready one with wrong bytes. The store's own
//! order of steps, and what is never ready, are proved in `openwiz-store`'s
//! `attachments` target (`crates/store/tests/attachments/ap04_ready.rs`).

use std::os::unix::process::ExitStatusExt;

use openwiz_core::attachment::AttachmentId;
use openwiz_store::attachments::{
    CLAIMS_LOCK, COPY_CHUNK_BYTES, Listed, NoClaims, STAGING_LOCK, Step, Verified,
};
use serde_json::json;

use crate::bench::{Bench, T0, sha256_of};
use crate::child::{STEPS, run_child};
use crate::support::{PNG, padded};

#[test]
fn stopped_after_any_step_nothing_usable_is_left_or_a_verified_attachment() {
    for (step_name, step) in STEPS {
        let bench = Bench::new(&format!("ap04_stop_{step_name}"));
        let source = bench.source(
            "syn-ap04-stop.png",
            &padded(PNG, (COPY_CHUNK_BYTES * 2 + 5) as u64),
        );
        let before = sha256_of(&source);
        let out = bench.root.join("child.json");
        let child = run_child(&json!({
            "mode": "kill",
            "state": bench.state,
            "source": source,
            "step": step_name,
            "out": out,
        }));
        assert_eq!(
            child.status.signal(),
            Some(6),
            "{step_name}: the child was not stopped there: {child:?}"
        );
        assert!(!out.exists(), "{step_name}: the child ran past its step");
        assert_eq!(sha256_of(&source), before, "the original is unchanged");

        let store = bench.store();
        let listed = store.list(&NoClaims).unwrap();
        let ids = bench.ids();
        if step == Step::Looked {
            // Only looked at: nothing was made, not even the lock.
            assert!(listed.is_empty(), "{step_name}: {listed:?}");
            assert!(
                bench.entries().is_empty(),
                "{step_name}: {:?}",
                bench.entries()
            );
            continue;
        }
        assert_eq!(ids.len(), 1, "{step_name}: one directory was made");
        let id = AttachmentId::parse(&ids[0]).unwrap();
        if step == Step::Ready {
            let [Listed::Ready { attachment, .. }] = listed.as_slice() else {
                panic!("{step_name}: {listed:?}");
            };
            assert_eq!(attachment.attachment.sha256.as_str(), before);
            assert_eq!(
                store.verify(&id).unwrap(),
                Verified::Ready(attachment.clone())
            );
            let swept = store.sweep(T0, &NoClaims).unwrap();
            assert_eq!(swept.unfinished, 0, "{step_name}");
            assert_eq!(bench.ids(), ids, "{step_name}: the ready one is kept");
        } else {
            assert!(listed.is_empty(), "{step_name}: {listed:?}");
            assert_eq!(store.verify(&id).unwrap(), Verified::NotFound);
            let swept = store.sweep(T0, &NoClaims).unwrap();
            assert_eq!(swept.unfinished, 1, "{step_name}");
            // B2 (ClosedWiz#15): a sweep holds the claims lock while it
            // applies the retention rule, so the lock file is there too.
            assert_eq!(
                bench.entries(),
                [CLAIMS_LOCK, STAGING_LOCK],
                "{step_name}: the unfinished copy is deleted"
            );
        }
    }
}
