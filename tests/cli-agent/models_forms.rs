//! #1804 (MD2): `openwiz models show`, `list` and `set` against every models
//! contract fixture (`contracts/fixtures/models/`), with a fake `cloud
//! status` read that offers exactly the contract's `list/` snapshot. All
//! inputs are synthetic.
use super::models::{FixedClock, Models};
use super::{ROOT, schema};
use openwiz_adapter_cloudroom::source::CloudRoomSource;
use serde_json::{Value, json};
use std::{fs, path::Path};

const FLEET: &str = "docs/agents/fleet.md";
const SNAPSHOT: &str = "docs/agents/models-offered.json";
const READ: [&str; 3] = ["cloud", "status", "--json"];

fn fixture(rel: &str) -> String {
    fs::read_to_string(Path::new(ROOT).join("contracts/fixtures/models").join(rel)).unwrap()
}

fn doc(rel: &str) -> Value {
    serde_json::from_str(&fixture(rel)).unwrap()
}

/// The `cloud status` answer behind `list/models-offered.json`: two mapped
/// harnesses and one that lists no models.
fn catalogue() -> Value {
    let models = |rows: &[(&str, &[&str])]| -> Value {
        rows.iter()
            .map(|(m, e)| json!({"model": m, "reasoning_levels": e}))
            .collect()
    };
    let all = ["low", "medium", "high", "xhigh", "max"];
    json!({"ready": true, "harnesses": [
        {"id": "claude-code", "model": "syn-default", "reasoning_levels": all, "models": models(&[
            ("claude-opus-5-5", &all), ("claude-sonnet-5-5", &all[..3])])},
        {"id": "codex", "model": "syn-default", "reasoning_levels": all, "models": models(&[
            ("gpt-6.2-sol", &all[..4]), ("vendor/demo", &["medium", "high"]),
            ("syn-vendor/demo:latest", &["medium"])])},
        {"id": "syn-other", "model": "syn-default", "reasoning_levels": all, "models": null},
    ]})
}

/// A sandbox whose `fleet.md` is the named fixture (none when empty) and
/// whose fake `cloud status` answers `answer`.
fn project(fleet: &str, answer: Value) -> Models {
    let fake = Models::new(json!({ "stdout": answer.to_string() }));
    fs::create_dir_all(fake.0.0.join("docs/agents")).unwrap();
    if !fleet.is_empty() {
        fs::write(fake.0.0.join(FLEET), fixture(fleet)).unwrap();
    }
    fake
}

/// `openwiz models <args>` in this process, from the sandbox's root, with
/// the fixed clock: the contract's `read_at`.
fn run(fake: &Models, args: &[&str]) -> (i32, String, String) {
    let args: Vec<String> = args.iter().map(|a| a.to_string()).collect();
    let source = CloudRoomSource::new(fake.0.0.join("bin/room-cli"));
    let (mut out, mut err) = (Vec::new(), Vec::new());
    let code = openwiz_cli::models::run_models_in(
        &args,
        &fake.0.0,
        &source,
        &FixedClock,
        &mut out,
        &mut err,
    );
    let text = |b| String::from_utf8(b).unwrap();
    (code, text(out), text(err))
}

/// The one JSON document a form printed, checked against its definition in
/// `contracts/models.v1.schema.json`.
fn report(out: &str, definition: &str) -> Value {
    assert!(out.ends_with('\n'), "{out}");
    let got: Value = serde_json::from_str(out).expect("one JSON document");
    let mut contract: Value = serde_json::from_str(
        &fs::read_to_string(Path::new(ROOT).join("contracts/models.v1.schema.json")).unwrap(),
    )
    .unwrap();
    contract["$ref"] = json!(format!("#/$defs/{definition}"));
    contract.as_object_mut().unwrap().remove("oneOf");
    assert_eq!(
        schema::validate(&contract, &got),
        Vec::<String>::new(),
        "{got}"
    );
    got
}

/// A contract snapshot with `syn-other`'s text as `openwiz models` words it:
/// the snapshot copies the read's own unavailable text (ruling 1).
fn as_read(mut snapshot: Value) -> Value {
    snapshot["unavailable"][0]["text"] = json!("unavailable (catalogue not reported)");
    snapshot
}

// catches: a reader that disagrees with the contract on any role's harness,
// model, effort or follow, a family's review or fix round, or a warning (a
// stale older table winning, a same-family pair or kept older row unnamed).
#[test]
fn show_prints_every_contract_fixtures_reading_and_reads_nothing_else() {
    for (fleet, want) in [
        ("one-table/fleet.md", "one-table/show.json"),
        ("five-tables/fleet.md", "five-tables/show.json"),
        ("both/fleet.md", "both/show.json"),
        ("overridden/fleet.md", "overridden/show.json"),
        ("same-family/fleet.md", "same-family/show.json"),
        ("set-namespaced/after.md", "set-namespaced/show.json"),
        (
            "set-older-namespaced/after.md",
            "set-older-namespaced/show.json",
        ),
    ] {
        let fake = project(fleet, catalogue());
        let (code, out, err) = run(&fake, &["show", "--json"]);
        assert_eq!((code, err.as_str()), (0, ""), "{fleet}");
        assert_eq!(report(&out, "show_report"), doc(want), "{fleet}");
        assert!(
            fake.invocations().is_empty(),
            "{fleet}: show reads no cloud status"
        );
    }
}

// catches: `list` making more than one read, dropping or adding an offered
// choice, recommending other than J255 or the current Orchestrator, or
// `--save` writing anything but the snapshot (or writing without `--save`).
#[test]
fn list_offers_the_read_with_recommendations_and_saves_only_when_asked() {
    let fake = project("one-table/fleet.md", catalogue());
    let (code, out, _) = run(&fake, &["list", "--json"]);
    let mut want = doc("list/list.json");
    want["offered"] = as_read(want["offered"].take());
    want["saved"] = Value::Null;
    assert_eq!((code, report(&out, "list_report")), (0, want.clone()));
    assert!(!fake.0.0.join(SNAPSHOT).exists(), "saved without --save");
    let (code, out, _) = run(&fake, &["list", "--save", "--json"]);
    want["saved"] = json!(SNAPSHOT);
    assert_eq!((code, report(&out, "list_report")), (0, want));
    let saved: Value =
        serde_json::from_str(&fs::read_to_string(fake.0.0.join(SNAPSHOT)).unwrap()).unwrap();
    assert_eq!(saved, as_read(doc("list/models-offered.json")));
    assert_eq!(fake.invocations(), [READ, READ], "one read per run");
    assert_eq!(
        fs::read_to_string(fake.0.0.join(FLEET)).unwrap(),
        fixture("one-table/fleet.md")
    );
}

// catches: `set` writing a choice that wasn't offered or can't be written,
// changing another role, leaving the older tables out of step or a kept row
// unnamed, a missing same-family warning, or files other than its report's.
#[test]
fn set_does_what_every_contract_case_says_and_writes_only_its_files() {
    for case in [
        "set-older",
        "set-same-family",
        "set-namespaced",
        "set-older-namespaced",
        "unoffered",
        "unwritable",
    ] {
        let spec = doc(&format!("{case}/case.json"));
        let start = spec["fleet"].as_str().unwrap();
        let fake = project(start, catalogue());
        let argv: Vec<&str> = spec["argv"]
            .as_array()
            .unwrap()
            .iter()
            .map(|a| a.as_str().unwrap())
            .collect();
        assert_eq!(argv[0], "models");
        let (code, out, _) = run(&fake, &argv[1..]);
        assert_eq!(code, spec["exit"], "{case}: {out}");
        assert_eq!(
            report(&out, "set_report"),
            doc(&format!("{case}/set.json")),
            "{case}"
        );
        let writes = &spec["writes"];
        let fleet = writes[FLEET].as_str().unwrap_or(start);
        assert_eq!(
            fs::read_to_string(fake.0.0.join(FLEET)).unwrap(),
            fixture(fleet),
            "{case}"
        );
        match writes[SNAPSHOT].as_str() {
            Some(want) => {
                let saved = fs::read_to_string(fake.0.0.join(SNAPSHOT)).unwrap();
                assert_eq!(
                    serde_json::from_str::<Value>(&saved).unwrap(),
                    as_read(doc(want)),
                    "{case}"
                );
            }
            None => assert!(
                !fake.0.0.join(SNAPSHOT).exists(),
                "{case}: wrote a snapshot"
            ),
        }
        assert_eq!(fake.invocations(), [READ], "{case}: one read");
    }
}

// catches: the contract's text forms drifting: a role, review or fix line,
// the same-family warning, a refusal without the offered list, or `list`
// losing today's text or its recommendation lines.
#[test]
fn the_text_forms_print_the_contracts_lines() {
    let fake = project("same-family/fleet.md", catalogue());
    let (code, out, _) = run(&fake, &["show"]);
    assert_eq!(code, 0, "{out}");
    for line in [
        "Orchestrator: Opus 5.5 Medium on Claude Code (claude-code claude-opus-5-5 medium)",
        "Small builder: follows Builder: Opus 5.5 Medium on Claude Code (claude-code claude-opus-5-5 medium)",
        "Review of Claude-built work: waits",
        "Fix round for a GPT builder: waits",
        "The Reviewer and the Builder are both Claude models, so reviews of Claude-built work wait (ADR 0008).",
    ] {
        assert!(out.lines().any(|l| l == line), "{line:?} not in:\n{out}");
    }
    let (code, out, _) = run(
        &fake,
        &[
            "set",
            "builder",
            "claude-code",
            "syn-model-not-offered",
            "medium",
        ],
    );
    assert_eq!(code, 5, "{out}");
    assert!(
        out.starts_with(
            "not offered: claude-code syn-model-not-offered medium; nothing was changed\n"
        ),
        "{out}"
    );
    assert!(out.contains("  vendor/demo: medium, high\n"), "{out}");
    let (code, out, _) = run(
        &fake,
        &["set", "reviewer", "codex", "gpt-6.2-sol", "medium"],
    );
    assert_eq!(code, 0, "{out}");
    for line in [
        "Reviewer: Opus 5.5 High on Claude Code (claude-code claude-opus-5-5 high) -> Sol 6.2 Medium on Codex (codex gpt-6.2-sol medium)",
        "wrote docs/agents/fleet.md",
        "wrote docs/agents/models-offered.json",
    ] {
        assert!(out.lines().any(|l| l == line), "{line:?} not in:\n{out}");
    }
    let (code, out, _) = run(&fake, &["list"]);
    assert_eq!(code, 0, "{out}");
    assert!(
        out.starts_with("openwiz models · read 2023-11-14T22:23:20Z · "),
        "{out}"
    );
    assert!(out.ends_with(
        "recommended Builder: Opus 5.5 Medium on Claude Code (claude-code claude-opus-5-5 medium), OpenWiz's current choice (J255)\n\
         recommended Reviewer: Sol 6.2 Medium on Codex (codex gpt-6.2-sol medium), OpenWiz's current choice (J255)\n"
    ), "{out}");
}

// catches: `follows-builder` reading CloudRoom or writing a snapshot, a row
// written in another form than the contract's, or setting a role's current
// value touching the file.
#[test]
fn set_follows_builder_reads_nothing_and_an_unchanged_set_leaves_the_file() {
    let fake = project("overridden/fleet.md", catalogue());
    let (code, out, _) = run(&fake, &["set", "fixer", "follows-builder", "--json"]);
    let got = report(&out, "set_report");
    assert_eq!(
        (code, &got["outcome"], &got["files"]),
        (0, &json!("changed"), &json!([FLEET]))
    );
    let written = fs::read_to_string(fake.0.0.join(FLEET)).unwrap();
    assert!(
        written.contains("\n| Fixer | follows Builder | | | |\n"),
        "{written}"
    );
    assert!(fake.invocations().is_empty() && !fake.0.0.join(SNAPSHOT).exists());
    let (code, out, _) = run(&fake, &["set", "fixer", "follows-builder", "--json"]);
    assert_eq!(
        (code, &report(&out, "set_report")["outcome"]),
        (0, &json!("unchanged"))
    );
    assert_eq!(fs::read_to_string(fake.0.0.join(FLEET)).unwrap(), written);
}

// catches: a usage error that reads CloudRoom or writes, nothing offered
// still writing, or a missing fleet.md not exiting 1 with the CLI's error
// document.
#[test]
fn usage_errors_nothing_offered_and_no_fleet_md_change_nothing() {
    let fake = project("one-table/fleet.md", catalogue());
    for args in [
        &["set", "builder", "follows-builder"][..],
        &["set", "boss", "codex", "gpt-6.2-sol", "medium"],
        &["set", "builder", "codex", "gpt-6.2-sol"],
        &["show", "--json", "--json"],
        &["list", "--save", "--save"],
        &["show", "extra"],
        &["set", "builder", "codex", "gpt-6.2-sol", "medium", "--save"],
    ] {
        let (code, out, err) = run(&fake, args);
        assert_eq!((code, out.as_str()), (2, ""), "{args:?}");
        assert!(
            err.starts_with("openwiz: ") && err.lines().count() == 1,
            "{err}"
        );
    }
    assert!(fake.invocations().is_empty(), "a usage error reads nothing");
    let none = project(
        "one-table/fleet.md",
        json!({"ready": false, "harnesses": null}),
    );
    let (code, out, _) = run(
        &none,
        &["set", "reviewer", "codex", "gpt-6.2-sol", "high", "--json"],
    );
    let got = report(&out, "set_report");
    assert_eq!(
        (code, &got["outcome"], &got["files"]),
        (13, &json!("no_options"), &json!([]))
    );
    let (code, out, _) = run(&none, &["list", "--save", "--json"]);
    assert_eq!(
        (code, &report(&out, "list_report")["saved"]),
        (13, &Value::Null)
    );
    assert!(!none.0.0.join(SNAPSHOT).exists());
    assert_eq!(
        fs::read_to_string(none.0.0.join(FLEET)).unwrap(),
        fixture("one-table/fleet.md")
    );
    let empty = project("", catalogue());
    let (code, out, _) = empty.run(&["models", "show", "--json"]);
    let got: Value = serde_json::from_str(&out).unwrap();
    assert_eq!(
        (code, &got["schema"], &got["command"]),
        (1, &json!("openwiz.cli-error.v1"), &json!("models"))
    );
}

// catches: a broken Models table (a misnamed or misplaced row, a following
// Builder, broken flags, a wrong header, two `## Models`) that `show` or
// `set` still reads, or that `set` rewrites; and `show` writing anything.
#[test]
fn a_broken_models_table_is_refused_by_show_and_set_and_never_written() {
    let good = fixture("one-table/fleet.md");
    let builder = "| Builder | Claude Code | Opus 5.5 | Medium | `--provider claude-code --model claude-opus-5-5 --reasoning-level medium` |";
    for (from, to) in [
        ("| Reviewer | Codex", "| Reviewers | Codex"),
        (builder, "| Builder | follows Builder | | | |"),
        (
            "--reasoning-level medium` |\n| Reviewer",
            "--effort medium` |\n| Reviewer",
        ),
        (
            "| Small builder | follows Builder | | | |\n| Fixer",
            "| Fixer | follows Builder | | | |\n| Small builder",
        ),
        ("`room-cli thread spawn` flags |", "flags |"),
        ("## Loop", "## Models\n\n## Loop"),
    ] {
        assert!(good.contains(from), "{from}");
        let broken = good.replacen(from, to, 1);
        let fake = project("one-table/fleet.md", catalogue());
        fs::write(fake.0.0.join(FLEET), &broken).unwrap();
        for args in [
            &["show", "--json"][..],
            &["set", "fixer", "follows-builder"],
        ] {
            let (code, out, err) = run(&fake, args);
            assert_eq!((code, out.as_str()), (1, ""), "{to}: {args:?}");
            assert!(err.starts_with("openwiz: models "), "{err}");
        }
        assert_eq!(
            fs::read_to_string(fake.0.0.join(FLEET)).unwrap(),
            broken,
            "{to}"
        );
        let mut left: Vec<_> = fs::read_dir(fake.0.0.join("docs/agents"))
            .unwrap()
            .map(|e| e.unwrap().file_name())
            .collect();
        left.sort();
        assert_eq!(left, ["fleet.md"], "{to}: wrote another file");
        assert!(fake.invocations().is_empty(), "{to}");
    }
}
