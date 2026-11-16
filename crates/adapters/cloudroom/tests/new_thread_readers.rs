//! The new-thread readers of `room-cli`'s answers, through the adapter's
//! public functions alone: the `spawn` receipt (Sol, round 1, R2: a strict,
//! hand-written reader that sees every key as the text gives it, so a key
//! given twice is refused at any depth), and the project list's kind and
//! remote (N3, sheet A-5). Moved here from
//! `tests/new-thread/` (`boundary_readers.rs`, `n03_existing_projects.rs`)
//! by #808. The proofs that run the CLI against the fake `room-cli` stay
//! there, and so does the catalogue table: M12 reads every file under
//! `crates/` as product source and refuses the word `steer` it spells.

use std::path::Path;

use openwiz_adapter_cloudroom::new_thread::{is_github_remote, parse_projects, spawn_receipt};
use openwiz_core::messaging::send::UncertainReason;
use openwiz_core::model::Fact;
use openwiz_core::new_thread::outcome::SpawnReply;
use serde_json::{Value, json};

/// The synthetic `room-cli` v127 new-thread answers (`tests/fixtures/`).
const FIXTURES: &str = concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../../tests/fixtures/room-cli-v127/new-thread"
);

fn fixture(name: &str) -> Vec<u8> {
    std::fs::read(Path::new(FIXTURES).join(name)).unwrap_or_else(|e| panic!("fixture {name}: {e}"))
}

fn fixture_json(name: &str) -> Value {
    serde_json::from_slice(&fixture(name)).unwrap_or_else(|e| panic!("fixture {name}: {e}"))
}

/// `text` with the first `from` replaced by `to`: a key given twice, which
/// no `Value` can hold.
fn twice(text: &str, from: &str, to: &str) -> String {
    let changed = text.replacen(from, to, 1);
    assert_ne!(changed, text, "{from} is in the document");
    changed
}

fn with(value: &Value, key: &str, new: Value) -> String {
    let mut v = value.clone();
    v[key] = new;
    v.to_string()
}

fn without(value: &Value, key: &str) -> String {
    let mut v = value.clone();
    v.as_object_mut().unwrap().remove(key);
    v.to_string()
}

/// Sol's counterexample, as he ran it.
const SOLS_RECEIPT: &str = r#"{"id":"thr_syn_wrong","id":"thr_syn_0021","projectId":"prj_syn_wrong","projectId":"prj_syn_0001","unexpected":true}"#;

fn github(n: &str) -> String {
    format!("https://github.com/synthetic-owner/synthetic-repo-{n}.git")
}

/// The rows of `tests/new-thread/fake.rs`'s `project list` this proof reads.
fn project_list() -> Value {
    let row = |id: &str, name: &str, kind: &str, remote: Value| {
        json!({
            "id": id, "kind": kind, "name": name, "gitRemoteUrl": remote,
            "createdAt": 1_699_100_600_000_i64, "updatedAt": 1_699_200_600_000_i64,
            "sources": [],
        })
    };
    json!([
        row(
            "prj_syn_0001",
            "Synthetic project one",
            "standard",
            json!(github("0001"))
        ),
        row(
            "prj_syn_0002",
            "Synthetic project two",
            "standard",
            Value::Null
        ),
        row(
            "prj_syn_0003",
            "Synthetic personal",
            "personal",
            Value::Null
        ),
        row(
            "prj_syn_0004",
            "Synthetic shared",
            "standard",
            json!("git@github.com:synthetic-owner/synthetic-repo-0004.git"),
        ),
        row(
            "prj_syn_0006",
            "Synthetic elsewhere",
            "standard",
            json!("https://example.invalid/synthetic/repo-0006.git"),
        ),
    ])
}

#[test]
fn the_receipt_table() {
    let receipt = fixture_json("spawn-receipt-created.json");
    let text = receipt.to_string();
    let mut documented = receipt.clone();
    for (key, value) in [
        (
            "purpose",
            json!({"text": "Synthetic purpose.", "percent": 0}),
        ),
        ("activity", json!({"activeGoalCount": 0})),
        ("runtime", json!({"displayStatus": "idle"})),
        ("projectCopy", Value::Null),
        ("queuedWork", json!("none")),
        ("hasPendingInteraction", json!(false)),
        ("environmentHostId", Value::Null),
        ("environmentIsWorktree", Value::Null),
        ("lastError", Value::Null),
    ] {
        documented[key] = value;
    }
    let good = [
        text.clone(),
        documented.to_string(),
        // #949: room-cli v155's declared receipt adds keys the old reader refused.
        String::from_utf8(fixture("spawn-receipt-created-v155.json")).unwrap(),
        json!({"id": "thr_syn_0021", "projectId": "prj_syn_0001", "status": "pending"}).to_string(),
        // #949: only id and projectId are read; any other key, of any type,
        // is not drift (an additive room-cli release must not break new).
        with(&receipt, "unexpected", json!(true)),
        with(&receipt, "thread", json!({})),
        with(
            &receipt,
            "syntheticExtraField",
            json!([{"a": null}, 1.5, "x"]),
        ),
        with(&receipt, "createdAt", json!("1700000600000")),
        with(&receipt, "canSpawnChild", json!("true")),
        with(&receipt, "title", json!(7)),
        with(&receipt, "status", Value::Null),
        with(&receipt, "purpose", json!("Synthetic purpose")),
    ];
    for row in &good {
        assert_eq!(
            spawn_receipt(row.as_bytes(), "prj_syn_0001"),
            SpawnReply::Created {
                thread_id: "thr_syn_0021".to_owned()
            },
            "{row}"
        );
    }
    let bad = [
        SOLS_RECEIPT.to_owned(),
        twice(&text, "\"id\":", "\"id\":\"thr_syn_0099\",\"id\":"),
        twice(&text, "\"id\":", "\"id\":\"thr_syn_0021\",\"id\":"),
        twice(
            &text,
            "\"projectId\":",
            "\"projectId\":\"prj_syn_0002\",\"projectId\":",
        ),
        twice(&text, "\"title\":", "\"title\":\"Synthetic\",\"title\":"),
        twice(
            &documented.to_string(),
            "\"percent\":",
            "\"percent\":1,\"percent\":",
        ),
        without(&receipt, "id"),
        without(&receipt, "projectId"),
        Value::Array(receipt.as_object().unwrap().values().cloned().collect()).to_string(),
        json!({"thread": receipt}).to_string(),
        json!({"created": receipt}).to_string(),
        with(&receipt, "id", json!(21)),
        with(&receipt, "projectId", json!({"id": "prj_syn_0001"})),
        with(&receipt, "id", Value::Null),
        with(&receipt, "projectId", Value::Null),
        // #949: a key given twice inside a key OpenWiz does not read.
        twice(
            &with(&receipt, "syntheticExtraField", json!({"x": 1})),
            "\"x\":",
            "\"x\":2,\"x\":",
        ),
    ];
    for row in &bad {
        let reply = spawn_receipt(row.as_bytes(), "prj_syn_0001");
        let SpawnReply::Unclear { reason, gaps } = &reply else {
            panic!("accepted: {row}\n{reply:?}")
        };
        assert_eq!(*reason, UncertainReason::UnexpectedReceipt, "{row}");
        let shown = format!("{gaps:?}");
        for echoed in [
            "thr_syn_wrong",
            "prj_syn_wrong",
            "thr_syn_0099",
            "unexpected",
        ] {
            assert!(!shown.contains(echoed), "{echoed} echoed: {shown}");
        }
    }
}

#[test]
fn the_github_rule() {
    for url in [
        github("0001"),
        "https://github.com/a/b".to_owned(),
        "git@github.com:synthetic-owner/repo.git".to_owned(),
        "ssh://git@github.com/synthetic-owner/repo.git".to_owned(),
    ] {
        assert!(is_github_remote(&url), "{url}");
    }
    for url in [
        "",
        "https://github.com/",
        "https://github.com",
        "https://github.com.example.invalid/a/b",
        "https://example.invalid/github.com/a/b",
        "http://github.com/a/b",
        "https://GITHUB.COM.example.invalid/a",
        "https://user@github.com/a/b",
        "git@github.com:",
        "github.com/a/b",
        "/synthetic/local/repo",
        "file:///synthetic/repo",
        " https://github.com/a/b",
    ] {
        assert!(!is_github_remote(url), "{url:?}");
    }
}

#[test]
fn projects_are_read_with_their_kind_and_remote() {
    let rows = parse_projects(project_list().to_string().as_bytes()).expect("parsed");
    let find = |id: &str| rows.iter().find(|p| p.id == id).unwrap().clone();
    assert_eq!(find("prj_syn_0001").github_remote, Fact::Known(true));
    assert_eq!(
        find("prj_syn_0001").kind,
        Fact::Known("standard".to_owned())
    );
    assert_eq!(find("prj_syn_0002").github_remote, Fact::Known(false));
    assert_eq!(find("prj_syn_0004").github_remote, Fact::Known(true));
    assert_eq!(find("prj_syn_0006").github_remote, Fact::Known(false));
    assert_eq!(
        find("prj_syn_0003").kind,
        Fact::Known("personal".to_owned())
    );
    // Drift: a missing or mistyped field is unknown, so the project is
    // refused; a row without an id, or with an empty one, can't be named.
    let drift = json!([
        {"id": "prj_syn_0011", "kind": "standard", "name": "Synthetic a"},
        {"id": "prj_syn_0012", "kind": 3, "name": "Synthetic b", "gitRemoteUrl": github("0012")},
        {"id": "prj_syn_0013", "kind": "standard", "name": "Synthetic c", "gitRemoteUrl": 7},
        {"kind": "standard", "name": "Synthetic d", "gitRemoteUrl": github("0014")},
        {"id": "", "kind": "standard", "name": "Synthetic e", "gitRemoteUrl": github("0015")},
        "not a row",
    ]);
    let rows = parse_projects(drift.to_string().as_bytes()).expect("parsed");
    assert_eq!(rows.len(), 3, "{rows:?}");
    assert!(matches!(rows[0].github_remote, Fact::Unknown(_)));
    assert!(matches!(rows[1].kind, Fact::Unknown(_)));
    assert!(matches!(rows[2].github_remote, Fact::Unknown(_)));
    assert!(parse_projects(b"{}").is_err(), "not a list");
    assert!(parse_projects(b"not json").is_err());
}
