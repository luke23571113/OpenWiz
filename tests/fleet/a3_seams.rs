//! A3 (ClosedWiz#111): dependency direction for the GitHub adapter crate.
//! It depends on the core, and on no client and no other adapter; the core
//! never depends on it.

use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};
use std::process::Command;

use serde_json::Value;

const CORE: &str = "openwiz-core";
const GITHUB: &str = "openwiz-adapter-github";

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("..")
}

fn metadata() -> Value {
    let output = Command::new(env!("CARGO"))
        .args(["metadata", "--format-version", "1", "--locked", "--offline"])
        .args([
            "--filter-platform",
            String::from_utf8(
                Command::new("rustc")
                    .args(["--print", "host-tuple"])
                    .output()
                    .expect("rustc")
                    .stdout,
            )
            .expect("host")
            .trim(),
        ])
        .current_dir(root())
        .output()
        .expect("run cargo metadata");
    assert!(
        output.status.success(),
        "cargo metadata failed: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    serde_json::from_slice(&output.stdout).expect("metadata is JSON")
}

/// Each workspace package's name and its manifest's path, from the root.
fn members(meta: &Value) -> BTreeMap<String, String> {
    let ids: BTreeSet<&str> = meta["workspace_members"]
        .as_array()
        .expect("workspace members")
        .iter()
        .map(|m| m.as_str().expect("member id"))
        .collect();
    let root = root().canonicalize().expect("root");
    meta["packages"]
        .as_array()
        .expect("packages")
        .iter()
        .filter(|p| ids.contains(p["id"].as_str().expect("id")))
        .map(|p| {
            let manifest = Path::new(p["manifest_path"].as_str().expect("manifest"));
            let relative = manifest.strip_prefix(&root).expect("inside the root");
            (
                p["name"].as_str().expect("name").to_owned(),
                relative.to_str().expect("UTF-8 path").to_owned(),
            )
        })
        .collect()
}

/// Package name to the names of its normal dependencies, resolved.
fn graph(meta: &Value) -> BTreeMap<String, BTreeSet<String>> {
    let names: BTreeMap<&str, &str> = meta["packages"]
        .as_array()
        .expect("packages")
        .iter()
        .map(|p| (p["id"].as_str().unwrap(), p["name"].as_str().unwrap()))
        .collect();
    meta["resolve"]["nodes"]
        .as_array()
        .expect("resolve nodes")
        .iter()
        .map(|node| {
            let deps = node["deps"]
                .as_array()
                .unwrap()
                .iter()
                .filter(|d| {
                    d["dep_kinds"]
                        .as_array()
                        .unwrap()
                        .iter()
                        .any(|k| k["kind"].is_null())
                })
                .map(|d| names[d["pkg"].as_str().unwrap()].to_owned())
                .collect();
            (names[node["id"].as_str().unwrap()].to_owned(), deps)
        })
        .collect()
}

fn reachable(graph: &BTreeMap<String, BTreeSet<String>>, from: &str) -> BTreeSet<String> {
    let mut seen = BTreeSet::new();
    let mut stack = vec![from.to_owned()];
    while let Some(next) = stack.pop() {
        for dep in graph.get(&next).into_iter().flatten() {
            if seen.insert(dep.clone()) {
                stack.push(dep.clone());
            }
        }
    }
    seen
}

#[test]
fn the_github_adapters_dependencies_point_inward() {
    let meta = metadata();
    let g = graph(&meta);
    assert!(
        g.contains_key(GITHUB),
        "{GITHUB} is not in the resolved graph"
    );
    let core = reachable(&g, CORE);
    assert!(
        !core.contains(GITHUB),
        "the core reaches {GITHUB}: {core:?}"
    );

    let github = reachable(&g, GITHUB);
    assert!(
        github.contains(CORE),
        "{GITHUB} implements the core's interfaces"
    );
    // Every other workspace crate is a client or another adapter.
    for (name, _) in members(&meta) {
        if name != CORE && name != GITHUB {
            assert!(
                !github.contains(&name),
                "{GITHUB} depends on {name}: {github:?}"
            );
        }
    }
}
