//! #789 (LC1): the pinned WizLoops copy matches its record. This reads
//! `contracts/`, so it lives here rather than in the CLI crate, whose tests
//! also run where only the crates are copied (the service's update proofs).
use std::path::Path;

use super::ROOT;

// OpenWiz's own SHA-256 (no crate is approved for it), compiled in here.
#[allow(dead_code)]
#[path = "../../crates/core/src/messaging/sha256.rs"]
mod sha256;

// catches: a stub whose real output, through the fixture binary, drifts from
// the contract's not_built schema, or one that reads room-cli or state.
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
