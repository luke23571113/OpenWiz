//! N15 Nothing else changes: the inventory and `send` keep their behaviour
//! (P1 to P12 and M1 to M18 run unchanged in the same `cargo test
//! --workspace`), and no inventory path can reach a write: `ls`, `ls -l`,
//! `show`, `models` and `new --status` make no `spawn` and no `tell`.

use serde_json::json;

use crate::fake::*;

#[test]
fn no_read_command_reaches_a_write() {
    let fake = NewFake::with(
        "n15_reads",
        vec![json!({
            "argv": ["thread", "list", "--json"],
            "stdout_file": file("thread-list.json"),
        })],
    );
    for args in [
        &["ls", "--json"][..],
        &["ls", "-l", "-a", "--hidden", "--json"][..],
        &["show", "thr_syn_0001", "--json"][..],
        &["models", "--json"][..],
        &["models"][..],
        &["new", "--status", "op-n15-none", "--json"][..],
        &[
            "new",
            "Synthetic project one",
            "--harness",
            "codex",
            "--model",
            "syn-codex-model-01",
            "--effort",
            "high",
            "--",
            "Synthetic preview",
        ][..],
    ] {
        let out = fake.run_process(args, "");
        assert!(out.status.code().is_some(), "{args:?}");
    }
    assert!(fake.writes().is_empty(), "{:?}", fake.writes());
    assert_eq!(fake.spawn_count(), 0);
    // `ls` and `show` never read the catalogue either.
    let catalogue_reads = fake
        .invocations()
        .iter()
        .filter(|a| starts(a, &["cloud", "status"]))
        .count();
    assert_eq!(catalogue_reads, 3, "models twice and the preview once");
}
