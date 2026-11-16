//! #790 (LC2): `openwiz loop validate`, run as the real binary on the pinned
//! WizLoops fixtures (`contracts/fixtures/wizloops/`), with a `room-cli` that
//! records any call. Expected results come from the fixtures' own
//! `expected.json`, never from the reader. These read `contracts/`, so they
//! live here rather than in the CLI crate (see `loop_contract.rs`).
use serde_json::{Value, json};
use std::fs;
use std::path::Path;

use super::{ROOT, Sandbox, schema};

const FIXTURES: &str = "contracts/fixtures/wizloops";

fn load(path: &str) -> Value {
    serde_json::from_str(&fs::read_to_string(Path::new(ROOT).join(path)).unwrap()).unwrap()
}

/// Runs `loop validate` with `args`, checks the one JSON document against
/// the contract's schema and that nothing called `room-cli`.
fn validate(sandbox: &Sandbox, contract: &Value, args: &[&str]) -> (i32, Value) {
    let mut argv = vec!["loop", "validate"];
    argv.extend(args);
    argv.push("--json");
    let output = sandbox.run(&argv);
    let code = output.status.code().unwrap();
    assert!(output.stdout.ends_with(b"\n"), "{args:?}");
    let doc: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(schema::validate(contract, &doc), Vec::<String>::new(), "{args:?}: {doc}");
    assert_eq!(doc["exit_code"], code, "{args:?}");
    assert!(!sandbox.0.join("calls").exists(), "{args:?} called room-cli");
    (code, doc)
}

/// `expected.json`'s refusals for one file, with `file` as validate names it.
fn refusals(expected: &Value, file: &str) -> Value {
    expected["refusals"]
        .as_array()
        .map(|list| {
            list.iter()
                .map(|r| {
                    json!({"file": file, "code": r["code"], "field": r["field"], "message": r["message"]})
                })
                .collect()
        })
        .unwrap_or_default()
}

// catches: a reader that accepts an invalid fixture, refuses a valid one, or
// names the wrong code, field or message (text or JSON), or a validate that
// calls room-cli. One file per run, as given.
#[test]
fn each_pinned_fixture_file_passes_or_refuses_as_expected_json_says() {
    let contract = load("contracts/loop-cli.v1.schema.json");
    let fixtures = load(&format!("{FIXTURES}/expected.json"));
    let sandbox = Sandbox::new();
    let mut checked = 0;
    for (name, expected) in fixtures["fixtures"].as_object().unwrap() {
        if name.ends_with('/') {
            continue;
        }
        let path = format!("{ROOT}/{FIXTURES}/{name}");
        let (code, doc) = validate(&sandbox, &contract, &[&path]);
        let valid = expected["result"] == "valid";
        assert_eq!(code, if valid { 0 } else { 5 }, "{name}: {doc}");
        let id = expected["parsed"].get("id").cloned().unwrap_or(Value::Null);
        let entry = &doc["files"][0];
        assert_eq!(doc["files"].as_array().unwrap().len(), 1, "{name}");
        assert_eq!(
            (&entry["file"], &entry["result"], &entry["refusals"]),
            (&json!(path), &expected["result"], &refusals(expected, &path)),
            "{name}"
        );
        if valid {
            assert_eq!(entry["id"], id, "{name}");
        }
        assert_eq!(doc["folder_refusals"], json!([]), "{name}");
        // Text: each refusal as `<file>: <field>: <message>`, on stdout.
        let output = sandbox.run(&["loop", "validate", &path]);
        assert_eq!(output.status.code(), Some(code), "{name}");
        let stdout = String::from_utf8(output.stdout).unwrap();
        for r in expected["refusals"].as_array().into_iter().flatten() {
            let line = format!(
                "{path}: {}: {}\n",
                r["field"].as_str().unwrap(),
                r["message"].as_str().unwrap()
            );
            assert!(stdout.contains(&line), "{name}: {stdout}");
        }
        checked += 1;
    }
    assert!(checked >= 60, "every fixture file is checked: {checked}");
}

// catches: a folder read that misses `duplicate-id` or `catalog-all-secrets`,
// reads `README.md` or files out of byte order, or names the folder's files
// with the wrong path.
#[test]
fn folders_and_catalogs_refuse_as_expected_json_says() {
    let contract = load("contracts/loop-cli.v1.schema.json");
    let fixtures = load(&format!("{FIXTURES}/expected.json"));
    let sandbox = Sandbox::new();
    for (name, expected) in fixtures["fixtures"].as_object().unwrap() {
        let Some(folder) = name.strip_suffix('/') else {
            continue;
        };
        let path = format!("{ROOT}/{FIXTURES}/{folder}");
        let mut args = vec![path.as_str()];
        if expected["read_as"] == "catalog" {
            args.push("--catalog");
        }
        let (code, doc) = validate(&sandbox, &contract, &args);
        assert_eq!(code, 5, "{name}: {doc}");
        let wanted: Vec<Value> = expected["refusals"]
            .as_array()
            .unwrap()
            .iter()
            .map(|r| {
                json!({"file": format!("{path}/{}", r["file"].as_str().unwrap()),
                       "code": r["code"], "field": r["field"], "message": r["message"]})
            })
            .collect();
        assert_eq!(doc["folder_refusals"], json!(wanted), "{name}");
        // Each file inside is valid alone, in byte order of name.
        let mut inside: Vec<&String> = fixtures["fixtures"]
            .as_object()
            .unwrap()
            .keys()
            .filter(|k| k.len() > name.len() && k.starts_with(name.as_str()))
            .collect();
        inside.sort_unstable();
        let files: Vec<Value> = inside
            .iter()
            .map(|k| {
                let id = &fixtures["fixtures"][k.as_str()]["parsed"]["id"];
                json!({"file": format!("{path}/{}", &k[name.len()..]), "id": id,
                       "result": "valid", "refusals": []})
            })
            .collect();
        assert_eq!(doc["files"], json!(files), "{name}");
    }
    // The catalog's file is valid when its folder is not read as a catalog.
    let (code, doc) = validate(
        &sandbox,
        &contract,
        &[&format!("{ROOT}/{FIXTURES}/catalog")],
    );
    assert_eq!((code, &doc["folder_refusals"]), (0, &json!([])));
}

// catches: a reader whose parse of a valid file differs from the format's
// (a default left out, a value changed), which plan and export (#791, #792)
// map to `room-cli`.
#[test]
fn each_valid_fixture_parses_to_expected_json() {
    let fixtures = load(&format!("{FIXTURES}/expected.json"));
    let mut checked = 0;
    for (name, expected) in fixtures["fixtures"].as_object().unwrap() {
        if expected["result"] != "valid" || name.ends_with('/') {
            continue;
        }
        let path = Path::new(ROOT).join(FIXTURES).join(name);
        let read = openwiz_adapter_cloudroom::loop_files::read_loop_path(&path).unwrap();
        let file = read.file.unwrap_or_else(|| panic!("{name}: {:?}", read.refusals));
        assert_eq!(Value::Object(file.frontmatter), expected["parsed"], "{name}");
        checked += 1;
    }
    assert!(checked >= 15, "{checked}");
}

// catches: several paths reported out of the order given, a refused file
// that does not fail the run, or an unreadable path that prints a report
// instead of the contract's error with exit 1.
#[test]
fn several_paths_keep_their_order_and_an_unreadable_one_fails_the_run() {
    let contract = load("contracts/loop-cli.v1.schema.json");
    let sandbox = Sandbox::new();
    let valid = format!("{ROOT}/{FIXTURES}/valid/at-same.md");
    let refused = format!("{ROOT}/{FIXTURES}/invalid/bad-id.md");
    let (code, doc) = validate(&sandbox, &contract, &[&valid, &refused, &valid]);
    assert_eq!(code, 5);
    let order: Vec<(&Value, &Value)> = doc["files"]
        .as_array()
        .unwrap()
        .iter()
        .map(|f| (&f["file"], &f["result"]))
        .collect();
    assert_eq!(
        order,
        [
            (&json!(valid), &json!("valid")),
            (&json!(refused), &json!("refused")),
            (&json!(valid), &json!("valid")),
        ]
    );
    let missing = sandbox.0.join("no-such-loop.md");
    let missing = missing.to_str().unwrap();
    let (code, doc) = validate(&sandbox, &contract, &[&valid, missing]);
    assert_eq!(code, 1);
    assert_eq!(
        (&doc["schema"], &doc["command"], &doc["error"]["kind"]),
        (
            &json!("openwiz.cli-error.v1"),
            &json!("loop.validate"),
            &json!("read_failed")
        )
    );
    let output = sandbox.run(&["loop", "validate", missing]);
    assert_eq!(output.status.code(), Some(1));
    assert!(output.stdout.is_empty());
    assert!(String::from_utf8(output.stderr).unwrap().contains(missing));
}
