//! #791 (LC3): `openwiz loop export`, run as the real fixture binary against
//! the fake `room-cli`'s synthetic `loops/` scenario and synthetic lists.
//! These read `contracts/` and `tests/fake-room-cli/`, so they live here
//! rather than in the CLI crate, whose tests also run where only the crates
//! are copied (the service's update proofs).
use serde_json::{Value, json};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Output, Stdio};

use super::{ROOT, Sandbox, fixture_cli, schema};

const PROJECT: &str = "prj_syn_0001";

/// A sandbox whose `room-cli` is the fake, answering from `scenario`.
struct Room(Sandbox);

impl Room {
    fn new(scenario: &Path) -> Self {
        let room = Self(Sandbox::new());
        let bin = room.0.0.join("bin");
        fs::remove_file(bin.join("room-cli")).unwrap();
        std::os::unix::fs::symlink(env!("CARGO_BIN_EXE_fake-room-cli"), bin.join("room-cli"))
            .unwrap();
        fs::write(
            bin.join("fake-room-cli.scenario"),
            scenario.to_str().unwrap(),
        )
        .unwrap();
        room
    }

    /// The synthetic `loops/` scenario that LC1 wrote.
    fn loops() -> Self {
        Self::new(&Path::new(ROOT).join("tests/fake-room-cli/loops/scenario.json"))
    }

    /// A scenario whose `loop list --json` prints `automations`.
    fn listing(automations: Value) -> Self {
        Self::answering(json!({
            "argv": ["loop", "list", "--json"],
            "stdout": json!({"automations": automations}).to_string(),
        }))
    }

    fn answering(response: Value) -> Self {
        let dir = Sandbox::new();
        let path = dir.0.join("scenario.json");
        fs::write(
            &path,
            json!({"synthetic_assumptions": ["LC3 synthetic loop list"], "responses": [response]})
                .to_string(),
        )
        .unwrap();
        let room = Self::new(&path);
        std::mem::forget(dir);
        room
    }

    fn dir(&self) -> &Path {
        &self.0.0
    }

    fn run(&self, args: &[&str]) -> Output {
        Command::new(fixture_cli())
            .args(args)
            .env_clear()
            .env("PATH", self.dir().join("bin"))
            .env("HOME", self.dir().join("home"))
            .env("OPENWIZ_STATE_DIR", self.dir().join("state"))
            .env("OPENWIZ_FIXTURE_PROGRAM", self.dir().join("bin/room-cli"))
            .current_dir(self.dir())
            .stdin(Stdio::null())
            .output()
            .unwrap()
    }

    fn export(&self, extra: &[&str]) -> Output {
        let mut args = vec!["loop", "export", "--project", PROJECT];
        args.extend_from_slice(extra);
        self.run(&args)
    }

    /// Every `room-cli` call the run made.
    fn calls(&self) -> Vec<Value> {
        fs::read_to_string(self.dir().join("bin/invocations.log"))
            .unwrap_or_default()
            .lines()
            .map(|l| serde_json::from_str(l).unwrap())
            .collect()
    }

    fn read(&self, rel: &str) -> String {
        fs::read_to_string(self.dir().join(rel)).unwrap_or_else(|e| panic!("{rel}: {e}"))
    }
}

/// The one JSON document, checked against `export_report` (or `def`).
fn report(output: &Output, code: i32, def: &str) -> Value {
    assert_eq!(
        output.status.code(),
        Some(code),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    let text = String::from_utf8(output.stdout.clone()).unwrap();
    assert!(
        text.ends_with('\n') && text.lines().count() == 1,
        "{text:?}"
    );
    let doc: Value = serde_json::from_str(&text).unwrap();
    let mut contract: Value = serde_json::from_str(
        &fs::read_to_string(Path::new(ROOT).join(match def {
            "error" => "contracts/cli.v1.schema.json",
            _ => "contracts/loop-cli.v1.schema.json",
        }))
        .unwrap(),
    )
    .unwrap();
    contract["$ref"] = json!(format!("#/$defs/{def}"));
    assert_eq!(
        schema::validate(&contract, &doc),
        Vec::<String>::new(),
        "{doc}"
    );
    assert_eq!(doc["exit_code"], code);
    doc
}

/// Every file under `dir`, relative, sorted.
fn tree(dir: &Path) -> Vec<String> {
    fn walk(root: &Path, dir: &Path, out: &mut Vec<String>) {
        for entry in fs::read_dir(dir).unwrap() {
            let path: PathBuf = entry.unwrap().path();
            if path.is_dir() {
                walk(root, &path, out);
            } else {
                out.push(path.strip_prefix(root).unwrap().display().to_string());
            }
        }
    }
    let mut out = Vec::new();
    if dir.exists() {
        walk(dir, dir, &mut out);
    }
    out.sort();
    out
}

const TRIAGE_MD: &str = r#"---
id: "syn-triage"
name: "Synthetic triage every ten minutes"
trigger: {"cron": "*/10 * * * *", "timezone": "UTC"}
check: {"run": "syn-triage/check", "timeout": 60}
thread: "new"
agent: {"provider": "synthetic-provider", "model": "synthetic-model", "reasoning": "medium"}
secrets: ["SYNTHETIC_TOKEN", ".env"]
priority: 2
params: {"repo": "synthetic-org/synthetic-repo"}
---
Synthetic: triage the due items the check printed below."#;

const TRIAGE_CHECK: &str = "#!/bin/sh\n# Synthetic check: prints the due items in $WIZLOOP_PARAM_REPO, nothing when none is due.\nif [ -f due.txt ]; then cat due.txt; fi\nexit 0\n";

const DELIVERY_MD: &str = r#"---
id: "syn-delivery"
name: "Synthetic delivery"
trigger: {"webhook": true}
thread: "new"
secrets: []
priority: 4
---
Synthetic: route each request that arrived to its owner."#;

const NIGHTLY_MD: &str = r#"---
id: "syn-nightly"
name: "Synthetic nightly note"
trigger: {"cron": "0 5 * * *", "timezone": "America/Los_Angeles"}
thread: "new"
secrets: "all"
priority: 3
---
Synthetic: post a short nightly note."#;

const REMINDER_MD: &str = r#"---
id: "syn-reminder"
name: "Synthetic reminder"
trigger: {"at": "2030-01-02T03:04:05.000Z"}
thread: "same"
secrets: []
priority: 1
---
Synthetic: remind the owner to read the report."#;

const KICK_MD: &str = r#"---
id: "synthetic-hourly-kick"
name: "Synthetic hourly kick"
trigger: {"cron": "12 * * * *", "timezone": "UTC"}
check: {"run": "synthetic-hourly-kick/check", "timeout": 60}
thread: "new"
secrets: []
priority: 3
---
Synthetic: nothing to do."#;

// catches: an export that drops, reorders or mismaps a setting `loop list`
// returns (trigger, check and its params, agent, secrets including "all",
// priority, thread, body), reads another project's loop, writes a Cloudroom
// identifier, a webhook address or run state into a file, writes anything
// but the one `loop list --json` read, or loses the binding an unmarked loop
// needs.
#[test]
fn export_writes_each_loop_of_the_project_complete_and_secret_free() {
    let room = Room::loops();
    let doc = report(
        &room.export(&["--out", "exported", "--json"]),
        0,
        "export_report",
    );
    let written = |loop_: &str, id: &str, files: &[&str], binding: Value| {
        json!({"loop": loop_, "id": id, "result": "written", "files": files,
               "binding": binding, "refusals": []})
    };
    assert_eq!(
        doc,
        json!({
            "schema": "openwiz.loop-export.v1", "command": "export", "exit_code": 0,
            "project": PROJECT, "out": "exported",
            "loops": [
                written("loop_syn_1", "syn-triage", &["syn-triage.md", "syn-triage/check"], Value::Null),
                written("loop_syn_2", "syn-delivery", &["syn-delivery.md"], Value::Null),
                written("loop_syn_3", "syn-nightly", &["syn-nightly.md"], Value::Null),
                written("loop_syn_4", "syn-reminder", &["syn-reminder.md"], Value::Null),
                written(
                    "loop_syn_5", "synthetic-hourly-kick",
                    &["synthetic-hourly-kick.md", "synthetic-hourly-kick/check"],
                    json!({"id": "synthetic-hourly-kick", "loop": "loop_syn_5"}),
                ),
            ],
        })
    );
    assert_eq!(
        tree(&room.dir().join("exported")),
        [
            "syn-delivery.md",
            "syn-nightly.md",
            "syn-reminder.md",
            "syn-triage.md",
            "syn-triage/check",
            "synthetic-hourly-kick.md",
            "synthetic-hourly-kick/check",
        ]
    );
    for (rel, bytes) in [
        ("syn-triage.md", TRIAGE_MD),
        ("syn-triage/check", TRIAGE_CHECK),
        ("syn-delivery.md", DELIVERY_MD),
        ("syn-nightly.md", NIGHTLY_MD),
        ("syn-reminder.md", REMINDER_MD),
        ("synthetic-hourly-kick.md", KICK_MD),
        ("synthetic-hourly-kick/check", "#!/bin/sh\nexit 0\n"),
    ] {
        assert_eq!(room.read(&format!("exported/{rel}")), bytes, "{rel}");
    }
    for rel in tree(&room.dir().join("exported")) {
        let text = room.read(&format!("exported/{rel}"));
        for never in [
            "loop_syn",
            "prj_syn",
            "thr_syn",
            "example.invalid",
            "enabled",
            "last_error",
            "runs",
        ] {
            assert!(!text.contains(never), "{rel} holds {never}");
        }
    }
    assert_eq!(room.calls(), [json!(["loop", "list", "--json"])]);
    assert!(!room.dir().join("bin/loop-writes.log").exists());
}

// catches: a second export that replaces a file someone edited, rewrites
// identical files instead of reporting them unchanged, or stops the other
// loops when one is refused.
#[test]
fn export_never_replaces_a_file_with_other_bytes() {
    let room = Room::loops();
    report(
        &room.export(&["--out", "exported", "--json"]),
        0,
        "export_report",
    );
    let doc = report(
        &room.export(&["--out", "exported", "--json"]),
        0,
        "export_report",
    );
    let results: Vec<&Value> = doc["loops"]
        .as_array()
        .unwrap()
        .iter()
        .map(|l| &l["result"])
        .collect();
    assert_eq!(results, ["unchanged"; 5]);
    assert_eq!(
        doc["loops"][0]["files"],
        json!(["syn-triage.md", "syn-triage/check"])
    );

    let edited = "#!/bin/sh\n# edited by hand\nexit 0\n";
    fs::write(room.dir().join("exported/syn-triage/check"), edited).unwrap();
    fs::remove_file(room.dir().join("exported/syn-nightly.md")).unwrap();
    let doc = report(
        &room.export(&["--out", "exported", "--json"]),
        5,
        "export_report",
    );
    assert_eq!(
        doc["loops"][0],
        json!({"loop": "loop_syn_1", "id": "syn-triage", "result": "refused", "files": [],
               "binding": null, "refusals": [{
                   "file": "Synthetic triage every ten minutes [wizloop:syn-triage]",
                   "code": "export-exists", "field": "file",
                   "message": "exported/syn-triage/check already exists with other bytes; nothing was written for this loop"}]})
    );
    assert_eq!(doc["loops"][2]["result"], "written");
    assert_eq!(doc["loops"][1]["result"], "unchanged");
    assert_eq!(room.read("exported/syn-triage/check"), edited);
    assert_eq!(room.read("exported/syn-triage.md"), TRIAGE_MD);
    assert_eq!(room.read("exported/syn-nightly.md"), NIGHTLY_MD);

    // A file, or a link elsewhere, where a check's folder goes: that loop is
    // refused and nothing is written through the link.
    fs::create_dir_all(room.dir().join("other")).unwrap();
    fs::write(room.dir().join("other/synthetic-hourly-kick"), "a file\n").unwrap();
    fs::create_dir_all(room.dir().join("elsewhere")).unwrap();
    std::os::unix::fs::symlink(
        room.dir().join("elsewhere"),
        room.dir().join("other/syn-triage"),
    )
    .unwrap();
    let doc = report(
        &room.export(&["--out", "other", "--json"]),
        5,
        "export_report",
    );
    for (n, folder) in [(0, "syn-triage"), (4, "synthetic-hourly-kick")] {
        assert_eq!(doc["loops"][n]["result"], "refused");
        assert_eq!(
            doc["loops"][n]["refusals"][0]["message"],
            format!(
                "other/{folder} already exists with other bytes; nothing was written for this loop"
            )
        );
    }
    assert_eq!(doc["loops"][1]["result"], "written");
    assert_eq!(tree(&room.dir().join("elsewhere")), Vec::<String>::new());
    assert!(!room.dir().join("other/syn-triage.md").exists());
    assert!(!room.dir().join("other/synthetic-hourly-kick.md").exists());

    let text = room.export(&["--out", "exported"]);
    assert_eq!(text.status.code(), Some(5));
    assert!(String::from_utf8_lossy(&text.stderr).contains(
        "Synthetic triage every ten minutes [wizloop:syn-triage]: file: exported/syn-triage/check already exists with other bytes; nothing was written for this loop\n"
    ));
}

/// One synthetic `loop list` item of the project, with `over` applied.
fn item(id: &str, name: &str, over: Value) -> Value {
    let mut base = json!({
        "id": id, "project_id": PROJECT, "session_id": "thr_syn_0001", "name": name,
        "cron": "0 9 * * 1", "timezone": "UTC", "run_at": null, "webhook": false,
        "new_thread": true, "script": null, "agent": null, "secrets": [], "priority": 3,
        "prompt": "Synthetic: a weekly note.", "enabled": true, "last_error": null,
        "last_run_at": null, "next_run_at": null, "runs": 0
    });
    for (k, v) in over.as_object().unwrap() {
        if v == "<absent>" {
            base.as_object_mut().unwrap().remove(k);
        } else {
            base[k] = v.clone();
        }
    }
    base
}

fn refused(loop_: &str, id: Value, file: &str, refusals: &[(&str, &str, &str)]) -> Value {
    json!({"loop": loop_, "id": id, "result": "refused", "files": [], "binding": null,
           "refusals": refusals.iter().map(|(code, field, message)| json!({
               "file": file, "code": code, "field": field, "message": message})).collect::<Vec<_>>()})
}

// catches: a loop the adapter cannot write as a valid, faithful file that is
// written anyway (or silently dropped from the report), a refusal with the
// wrong code, field or message, or one refused loop that stops the rest.
#[test]
fn export_reports_each_loop_it_cannot_represent_and_writes_the_rest() {
    let cases: Vec<(Value, Value)> = vec![
        // Two loops carry one marker: both refused.
        (
            item("loop_a1", "Twin one [wizloop:twin]", json!({})),
            refused(
                "loop_a1",
                json!("twin"),
                "Twin one [wizloop:twin]",
                &[(
                    "cf-duplicate-marker",
                    "id",
                    "two Cloudroom loops in this project carry [wizloop:twin]",
                )],
            ),
        ),
        (
            item("loop_a2", "Twin two [wizloop:twin]", json!({})),
            refused(
                "loop_a2",
                json!("twin"),
                "Twin two [wizloop:twin]",
                &[(
                    "cf-duplicate-marker",
                    "id",
                    "two Cloudroom loops in this project carry [wizloop:twin]",
                )],
            ),
        ),
        // Two unmarked loops derive one id: both refused.
        (
            item("loop_b1", "Same Name!", json!({})),
            refused(
                "loop_b1",
                Value::Null,
                "Same Name!",
                &[(
                    "cf-export-id",
                    "id",
                    "another unmarked loop in this project derives the same id",
                )],
            ),
        ),
        (
            item("loop_b2", "same  name", json!({})),
            refused(
                "loop_b2",
                Value::Null,
                "same  name",
                &[(
                    "cf-export-id",
                    "id",
                    "another unmarked loop in this project derives the same id",
                )],
            ),
        ),
        (
            item(
                "loop_c",
                "No trigger [wizloop:no-trigger]",
                json!({"cron": null}),
            ),
            refused(
                "loop_c",
                json!("no-trigger"),
                "No trigger [wizloop:no-trigger]",
                &[(
                    "cf-export-trigger",
                    "trigger",
                    "the loop has no cron, run time or webhook",
                )],
            ),
        ),
        (
            item(
                "loop_d",
                "Odd preamble [wizloop:odd-preamble]",
                json!({"script":
            "#!/bin/sh\n# wizloop: params from the loop file, as data\nexport WIZLOOP_PARAM_REPO=\"x\"\n# wizloop: the check\necho \"$WIZLOOP_PARAM_REPO\"\n"}),
            ),
            refused(
                "loop_d",
                json!("odd-preamble"),
                "Odd preamble [wizloop:odd-preamble]",
                &[(
                    "cf-export-preamble",
                    "check",
                    "the script's params preamble is not one this adapter writes",
                )],
            ),
        ),
        (
            item(
                "loop_e",
                "Same with secrets [wizloop:same-secrets]",
                json!({"new_thread": false, "secrets": ["SYNTHETIC_TOKEN"]}),
            ),
            refused(
                "loop_e",
                json!("same-secrets"),
                "Same with secrets [wizloop:same-secrets]",
                &[(
                    "cf-export-invalid",
                    "secrets",
                    "would be refused by the format as same-thread-secrets",
                )],
            ),
        ),
        (
            item(
                "loop_f",
                "Braces [wizloop:braces]",
                json!({"prompt": "Synthetic: print {{ .title }}."}),
            ),
            refused(
                "loop_f",
                json!("braces"),
                "Braces [wizloop:braces]",
                &[(
                    "cf-export-invalid",
                    "body",
                    "would be refused by the format as bad-placeholder",
                )],
            ),
        ),
        (
            item(
                "loop_g",
                &format!("{} [wizloop:long-name]", "n".repeat(101)),
                json!({}),
            ),
            refused(
                "loop_g",
                json!("long-name"),
                &format!("{} [wizloop:long-name]", "n".repeat(101)),
                &[(
                    "cf-export-invalid",
                    "name",
                    "would be refused by the format as bad-name",
                )],
            ),
        ),
        (
            item(
                "loop_h",
                "Spaced agent [wizloop:spaced-agent]",
                json!({"agent": {"provider": "synthetic-provider", "model": "synthetic model", "reasoning": "medium"}}),
            ),
            refused(
                "loop_h",
                json!("spaced-agent"),
                "Spaced agent [wizloop:spaced-agent]",
                &[(
                    "cf-export-invalid",
                    "agent.model",
                    "would be refused by the format as bad-agent",
                )],
            ),
        ),
        (
            item(
                "loop_i",
                "Unset param [wizloop:unset-param]",
                json!({"script": "#!/bin/sh\necho \"$WIZLOOP_PARAM_REPO\"\n"}),
            ),
            refused(
                "loop_i",
                json!("unset-param"),
                "Unset param [wizloop:unset-param]",
                &[(
                    "cf-export-invalid",
                    "check",
                    "would be refused by the format as undeclared-param",
                )],
            ),
        ),
        (
            item(
                "loop_j",
                "Placeholder in check [wizloop:check-placeholder]",
                json!({"script": "#!/bin/sh\necho {{repo}}\n"}),
            ),
            refused(
                "loop_j",
                json!("check-placeholder"),
                "Placeholder in check [wizloop:check-placeholder]",
                &[(
                    "cf-export-invalid",
                    "check",
                    "would be refused by the format as param-in-check",
                )],
            ),
        ),
        (
            item(
                "loop_k",
                "Too low [wizloop:too-low]",
                json!({"priority": 0}),
            ),
            refused(
                "loop_k",
                json!("too-low"),
                "Too low [wizloop:too-low]",
                &[(
                    "cf-export-invalid",
                    "priority",
                    "would be refused by the format as bad-priority",
                )],
            ),
        ),
        (
            item(
                "loop_l",
                "Bad secret [wizloop:bad-secret]",
                json!({"secrets": ["lower_case"]}),
            ),
            refused(
                "loop_l",
                json!("bad-secret"),
                "Bad secret [wizloop:bad-secret]",
                &[(
                    "cf-export-invalid",
                    "secrets",
                    "would be refused by the format as bad-secret",
                )],
            ),
        ),
        (
            item(
                "loop_m",
                "Carriage return [wizloop:carriage]",
                json!({"prompt": "Synthetic:\r\na note."}),
            ),
            refused(
                "loop_m",
                json!("carriage"),
                "Carriage return [wizloop:carriage]",
                &[(
                    "cf-export-invalid",
                    "file",
                    "would be refused by the format as encoding",
                )],
            ),
        ),
        (
            item(
                "loop_n",
                "Bad cron [wizloop:bad-cron]",
                json!({"cron": "0 9 * * MON"}),
            ),
            refused(
                "loop_n",
                json!("bad-cron"),
                "Bad cron [wizloop:bad-cron]",
                &[(
                    "cf-export-invalid",
                    "trigger.cron",
                    "would be refused by the format as bad-cron",
                )],
            ),
        ),
        (
            item(
                "loop_o",
                "Two triggers [wizloop:two-triggers]",
                json!({"webhook": true}),
            ),
            refused(
                "loop_o",
                json!("two-triggers"),
                "Two triggers [wizloop:two-triggers]",
                &[(
                    "cf-export-invalid",
                    "trigger",
                    "would be refused by the format as trigger-kind",
                )],
            ),
        ),
        (
            item("loop_p", "!!!", json!({})),
            refused(
                "loop_p",
                Value::Null,
                "!!!",
                &[(
                    "cf-export-invalid",
                    "id",
                    "would be refused by the format as bad-id",
                )],
            ),
        ),
        (
            item(
                "loop_q",
                "New setting [wizloop:new-setting]",
                json!({"max_runs": 5}),
            ),
            refused(
                "loop_q",
                json!("new-setting"),
                "New setting [wizloop:new-setting]",
                &[(
                    "export-unknown-key",
                    "max_runs",
                    "Cloudroom returned max_runs, which the adapter does not map; nothing was written for this loop",
                )],
            ),
        ),
        // A good loop among them is still written.
        (
            item("loop_z", "Still written [wizloop:still-written]", json!({})),
            json!({"loop": "loop_z", "id": "still-written", "result": "written", "files": ["still-written.md"],
                "binding": null, "refusals": []}),
        ),
    ];
    let room = Room::listing(Value::Array(cases.iter().map(|(i, _)| i.clone()).collect()));
    let doc = report(&room.export(&["--json"]), 5, "export_report");
    assert_eq!(doc["out"], ".");
    for (n, (_, expected)) in cases.iter().enumerate() {
        assert_eq!(&doc["loops"][n], expected, "case {n}");
    }
    assert_eq!(doc["loops"].as_array().unwrap().len(), cases.len());
    let files: Vec<String> = tree(room.dir())
        .into_iter()
        .filter(|f| f.ends_with(".md") || f.ends_with("/check"))
        .collect();
    assert_eq!(files, ["still-written.md"]);
    assert_eq!(
        room.read("still-written.md"),
        "---\nid: \"still-written\"\nname: \"Still written\"\ntrigger: {\"cron\": \"0 9 * * 1\", \"timezone\": \"UTC\"}\nthread: \"new\"\nsecrets: []\npriority: 3\n---\nSynthetic: a weekly note."
    );
}

// catches: a preamble read back wrongly (a quoted value not unquoted, an
// integer read as a string, the preamble left in the check), checked against
// the pinned WizLoops fixtures' own checks and params: the adapter rules'
// stated scripts and prompts for `cron-check.md` and `params-env.md`.
#[test]
fn export_reads_the_params_preamble_back_into_the_pinned_fixtures_checks() {
    let fixtures = Path::new(ROOT).join("contracts/fixtures/wizloops");
    let expected: Value =
        serde_json::from_str(&fs::read_to_string(fixtures.join("expected.json")).unwrap()).unwrap();
    // The scripts and prompts exactly as contracts/wizloops-cloudroom.v1.md
    // writes them for these two creates.
    let cron_check = "#!/bin/sh\n# wizloop: params from the loop file, as data\nexport WIZLOOP_PARAM_REPO='example-org/example-repo'\n# wizloop: the check\n# Prints one line per due item in $WIZLOOP_PARAM_REPO; nothing when none is due.\nif [ -f due.txt ]; then cat due.txt; fi\nexit 0\n";
    let params_env = "#!/bin/sh\n# wizloop: params from the loop file, as data\nexport WIZLOOP_PARAM_REF='release/\";printf${IFS}WAKE;false${IFS}\"'\nexport WIZLOOP_PARAM_REPO='example-org/example-repo'\nexport WIZLOOP_PARAM_SPEC=7\nexport WIZLOOP_PARAM_TITLE='it'\\''s $(touch marker) `touch marker`'\n# wizloop: the check\n# Reads its params from the environment as data and prints nothing, so no\n# agent starts: $WIZLOOP_PARAM_REPO, $WIZLOOP_PARAM_REF, $WIZLOOP_PARAM_TITLE\n# and $WIZLOOP_PARAM_SPEC.\nexit 0\n";
    let room = Room::listing(json!([
        item(
            "loop_cc",
            "Example triage every ten minutes [wizloop:cron-check]",
            json!({
            "cron": "*/10 * * * *", "script": cron_check,
            "agent": {"provider": "example-provider", "model": "example-model", "reasoning": "medium"},
            "secrets": ["EXAMPLE_TOKEN", ".env"], "priority": 2,
            "prompt": "Triage the due items for spec 42 that the check printed below.\n"})
        ),
        item(
            "loop_pe",
            "Params reach the check as data [wizloop:params-env]",
            json!({
            "cron": "30 6 * * *", "script": params_env,
            "prompt": "Report the check's output for spec 7 in example-org/example-repo.\n"})
        ),
    ]));
    let doc = report(&room.export(&["--out", "x", "--json"]), 0, "export_report");
    for (n, id, carried) in [
        (0, "cron-check", &["repo"][..]),
        (1, "params-env", &["ref", "repo", "spec", "title"]),
    ] {
        assert_eq!(doc["loops"][n]["result"], "written");
        assert_eq!(
            room.read(&format!("x/{id}/check")),
            fs::read_to_string(fixtures.join(format!("valid/{id}/check.sh"))).unwrap(),
            "{id}"
        );
        let parsed = &expected["fixtures"][format!("valid/{id}.md")]["parsed"];
        assert!(parsed.is_object(), "{id}");
        let mut params = serde_json::Map::new();
        for name in carried {
            params.insert((*name).to_owned(), parsed["params"][name].clone());
        }
        let file = room.read(&format!("x/{id}.md"));
        let line = file
            .lines()
            .find_map(|l| l.strip_prefix("params: "))
            .unwrap_or_else(|| panic!("{id} has no params line"));
        assert_eq!(
            serde_json::from_str::<Value>(line).unwrap(),
            Value::Object(params),
            "{id}"
        );
        for key in ["id", "name", "trigger", "thread", "secrets", "priority"] {
            let line = file
                .lines()
                .find_map(|l| l.strip_prefix(&format!("{key}: ")))
                .unwrap_or_else(|| panic!("{id} has no {key}"));
            assert_eq!(
                serde_json::from_str::<Value>(line).unwrap(),
                parsed[key],
                "{id} {key}"
            );
        }
    }
}

// catches: a failed `loop list` that still writes files, prints a report, or
// passes room-cli's error text into the JSON result.
#[test]
fn a_failed_loop_list_writes_nothing() {
    for response in [
        json!({"argv": ["loop", "list", "--json"], "exit": 1, "stderr": "SYNTHETIC_SECRET_DO_NOT_PRINT"}),
        json!({"argv": ["loop", "list", "--json"], "stdout": "[]"}),
        json!({"argv": ["loop", "list", "--json"], "stdout": "{\"automations\": [{\"id\": \"a\", \"id\": \"b\"}]}"}),
    ] {
        let room = Room::answering(response.clone());
        let doc = report(&room.export(&["--out", "exported", "--json"]), 1, "error");
        assert_eq!(doc["command"], "loop.export");
        assert_eq!(doc["error"]["kind"], "read_failed");
        assert!(!doc.to_string().contains("SYNTHETIC_SECRET"), "{response}");
        assert!(!room.dir().join("exported").exists(), "{response}");
        let text = room.export(&["--out", "exported"]);
        assert_eq!(text.status.code(), Some(1));
        assert!(text.stdout.is_empty());
        assert!(!room.dir().join("exported").exists());
    }
}
