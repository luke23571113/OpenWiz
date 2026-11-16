//! #789 (LC1): the loop CLI's contract files. The pinned WizLoops copy
//! matches its record, and the stubs' real output matches
//! `contracts/loop-cli.v1.schema.json`. These read `contracts/`, so they live
//! here rather than in the CLI crate, whose tests also run where only the
//! crates are copied (the service's update proofs).
use serde_json::Value;
use std::fs;
use std::path::Path;

use super::{ROOT, Sandbox, schema};

// OpenWiz's own SHA-256 (no crate is approved for it), compiled in here.
#[allow(dead_code)]
#[path = "../../crates/core/src/messaging/sha256.rs"]
mod sha256;

// catches: a stub whose real output, through the fixture binary, drifts from
// the contract's not_built schema, or one that reads room-cli or state.
#[test]
fn the_stubs_print_the_schemas_not_built_document_and_read_nothing() {
    let contract: Value = serde_json::from_str(
        &fs::read_to_string(Path::new(ROOT).join("contracts/loop-cli.v1.schema.json")).unwrap(),
    )
    .unwrap();
    assert_eq!(schema::lint(&contract), Vec::<String>::new());
    // validate is built (#790): loop_validate.rs checks its real output
    // against the same schema and that it reads no source.
    for args in [
        // export (#791) is built: its keeper is loop_export.rs, which checks
        // its real output against export_report in the same schema.
        // plan (#792) is built: its keeper is tests/cli-agent/loop_plan.rs,
        // whose every document is checked against this schema.
        &[
            "loop",
            "apply",
            "nightly",
            "--project",
            "project-synthetic",
            "--json",
        ],
    ] {
        let sandbox = Sandbox::new();
        let output = sandbox.run(args);
        assert_eq!(output.status.code(), Some(5), "{args:?}");
        let doc: Value = serde_json::from_slice(&output.stdout).unwrap();
        assert_eq!(
            schema::validate(&contract, &doc),
            Vec::<String>::new(),
            "{args:?}"
        );
        assert_eq!(doc["schema"], "openwiz.loop-not-built.v1");
        assert!(
            !sandbox.0.join("calls").exists(),
            "{args:?} called a source"
        );
        assert!(!sandbox.0.join("state").exists(), "{args:?} touched state");
    }
}

// catches: a pinned WizLoops file that drifts from the pinned commit (an
// edit in place, or a tool that strips crlf.md's carriage returns), or a
// fixture added or lost without re-pinning.
#[test]
fn the_pinned_wizloops_files_match_their_record() {
    let root = Path::new(ROOT);
    let record =
        std::fs::read_to_string(root.join("contracts/fixtures/wizloops/README.md")).unwrap();
    assert!(record.contains("`c7c2ed434dd984d3e984df2a45eb66d43bcdf759`"));
    let block = record
        .split("```sha256\n")
        .nth(1)
        .and_then(|b| b.split("\n```").next())
        .expect("the sha256 block");
    let recorded: std::collections::BTreeMap<&str, &str> = block
        .lines()
        .map(|l| {
            let (hash, path) = l.split_once("  ").unwrap();
            (path, hash)
        })
        .collect();
    let mut pinned = vec![
        "contracts/wizloops-loop.v1.md".to_owned(),
        "contracts/wizloops-loop.v1.schema.json".to_owned(),
        "contracts/wizloops-cloudroom.v1.md".to_owned(),
    ];
    fn walk(dir: &Path, root: &Path, out: &mut Vec<String>) {
        for entry in std::fs::read_dir(dir).unwrap() {
            let path = entry.unwrap().path();
            if path.is_dir() {
                walk(&path, root, out);
            } else if !path.ends_with("contracts/fixtures/wizloops/README.md") {
                out.push(
                    path.strip_prefix(root)
                        .unwrap()
                        .to_str()
                        .unwrap()
                        .to_owned(),
                );
            }
        }
    }
    walk(&root.join("contracts/fixtures/wizloops"), root, &mut pinned);
    let mut listed: Vec<&str> = recorded.keys().copied().collect();
    listed.sort_unstable();
    let mut found: Vec<&str> = pinned.iter().map(String::as_str).collect();
    found.sort_unstable();
    assert_eq!(
        found, listed,
        "the record lists every pinned file, and only those"
    );
    for path in found {
        let bytes = std::fs::read(root.join(path)).unwrap();
        assert_eq!(
            Some(&sha256::sha256_hex(&bytes).as_str()),
            recorded.get(path),
            "{path} differs from WizLoops"
        );
    }
}
