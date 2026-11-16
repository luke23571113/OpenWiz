//! #793 (LC5): `openwiz loop apply`, run as the real fixture binary against
//! the fake `room-cli`, on the pinned WizLoops fixtures and synthetic lists
//! built from the fake's `loops/` scenario. Expected values are literals
//! from `contracts/loop-cli.v1.md` and `contracts/wizloops-cloudroom.v1.md`,
//! never computed by the code under test. These read `contracts/` and
//! `tests/fake-room-cli/`, so they live here rather than in the CLI crate.
//!
//! No test can reach a real `room-cli`: `PATH` holds only the sandbox's
//! `bin/`, whose `room-cli` is a two-line recorder in front of the fake,
//! and every test checks the exact calls the fake recorded. The recorder
//! only switches the fake to a second synthetic scenario once a write has
//! been recorded, so a read-back can see what the write changed.
use serde_json::{Value, json};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Output, Stdio};

use super::{ROOT, Sandbox, dirs, fixture_cli, place, schema};

const PROJECT: &str = "prj_syn_0001";
const LIST: [&str; 3] = ["loop", "list", "--json"];

/// A sandbox whose `room-cli` is the fake, behind a recorder that answers
/// from `before` until a loop write is recorded and from `after` once one is.
struct Room(PathBuf, #[allow(dead_code)] Sandbox);

impl Room {
    fn new(before: Vec<Value>, after: Vec<Value>) -> Self {
        let sandbox = Sandbox::new();
        let root = sandbox.0.clone();
        let bin = root.join("bin");
        for (name, responses) in [("before.json", before), ("after.json", after)] {
            fs::write(
                root.join(name),
                json!({"synthetic_assumptions": ["LC5 synthetic loop answers"], "responses": responses})
                    .to_string(),
            )
            .unwrap();
        }
        fs::write(
            bin.join("fake-room-cli.scenario"),
            root.join("before.json").to_str().unwrap(),
        )
        .unwrap();
        std::os::unix::fs::symlink(env!("CARGO_BIN_EXE_fake-room-cli"), bin.join("fake-room-cli"))
            .unwrap();
        fs::remove_file(bin.join("room-cli")).unwrap();
        let b = bin.display();
        let after = root.join("after.json");
        place::place_script(
            &bin.join("room-cli"),
            &format!(
                "#!/bin/sh\nif [ -e '{b}/loop-writes.log' ]; then printf '%s' '{}' > '{b}/fake-room-cli.scenario'; fi\nexec '{b}/fake-room-cli' \"$@\"\n",
                after.display()
            ),
        );
        dirs::private_dir(root.join("tmp")).unwrap();
        Self(root, sandbox)
    }

    /// `loop list` answers `before`, then `after` once a write is recorded;
    /// every write is accepted.
    fn listing(before: &Value, after: &Value) -> Self {
        Self::new(
            vec![list(before), accept()],
            vec![list(after), accept()],
        )
    }

    fn dir(&self) -> &Path {
        &self.0
    }

    fn write(&self, rel: &str, text: &str) -> String {
        let path = self.0.join(rel);
        dirs::private_dir_all(path.parent().unwrap()).unwrap();
        fs::write(&path, text).unwrap();
        path.to_str().unwrap().to_owned()
    }

    fn run_env(&self, args: &[&str], env: &[(&str, &str)]) -> Output {
        Command::new(fixture_cli())
            .args(args)
            .env_clear()
            .env("PATH", self.0.join("bin"))
            .env("HOME", self.0.join("home"))
            .env("TMPDIR", self.0.join("tmp"))
            .env("OPENWIZ_STATE_DIR", self.0.join("state"))
            .env("OPENWIZ_FIXTURE_PROGRAM", self.0.join("bin/room-cli"))
            .envs(env.iter().copied())
            .current_dir(&self.0)
            .stdin(Stdio::null())
            .output()
            .unwrap()
    }

    fn apply(&self, args: &[&str]) -> Output {
        let mut all = vec!["loop", "apply"];
        all.extend_from_slice(args);
        all.extend(["--project", PROJECT]);
        self.run_env(&all, &[])
    }

    /// Runs with `--json`; checks one document against its schema and the
    /// process's exit code.
    fn json(&self, args: &[&str]) -> (i32, Value) {
        self.json_env(args, &[])
    }

    fn json_env(&self, args: &[&str], env: &[(&str, &str)]) -> (i32, Value) {
        let mut all = vec!["loop", "apply"];
        all.extend_from_slice(args);
        if !args.contains(&"--project") {
            all.extend(["--project", PROJECT]);
        }
        all.push("--json");
        let output = self.run_env(&all, env);
        let code = output.status.code().unwrap();
        (code, document(&output, code))
    }

    /// Every `room-cli` call made, in order.
    fn calls(&self) -> Vec<Value> {
        fs::read_to_string(self.0.join("bin/invocations.log"))
            .unwrap_or_default()
            .lines()
            .map(|l| serde_json::from_str(l).unwrap())
            .collect()
    }

    /// Every loop write the fake recorded: its arguments and named files.
    fn writes(&self) -> Vec<Value> {
        fs::read_to_string(self.0.join("bin/loop-writes.log"))
            .unwrap_or_default()
            .lines()
            .map(|l| serde_json::from_str(l).unwrap())
            .collect()
    }

    /// Nothing is left in apply's temporary folder.
    fn assert_no_temporary_files(&self) {
        let left: Vec<PathBuf> = fs::read_dir(self.0.join("tmp"))
            .unwrap()
            .map(|e| e.unwrap().path())
            .collect();
        assert_eq!(left, Vec::<PathBuf>::new(), "apply left files behind");
    }
}

fn document(output: &Output, code: i32) -> Value {
    let stdout = String::from_utf8(output.stdout.clone()).unwrap();
    assert!(
        stdout.ends_with('\n') && stdout.lines().count() == 1,
        "{stdout}\n{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let doc: Value = serde_json::from_str(&stdout).unwrap();
    let against = contract(if doc["schema"] == "openwiz.cli-error.v1" {
        "cli.v1.schema.json"
    } else {
        "loop-cli.v1.schema.json"
    });
    assert_eq!(
        schema::validate(&against, &doc),
        Vec::<String>::new(),
        "{doc:#}"
    );
    assert_eq!(doc["exit_code"], code, "{doc:#}");
    doc
}

fn contract(name: &str) -> Value {
    serde_json::from_str(&fs::read_to_string(Path::new(ROOT).join("contracts").join(name)).unwrap())
        .unwrap()
}

fn fixture(name: &str) -> String {
    Path::new(ROOT)
        .join("contracts/fixtures/wizloops/valid")
        .join(name)
        .to_str()
        .unwrap()
        .to_owned()
}

/// The fake's synthetic account (`tests/fake-room-cli/loops/list.json`).
fn account() -> Value {
    serde_json::from_str(
        &fs::read_to_string(Path::new(ROOT).join("tests/fake-room-cli/loops/list.json")).unwrap(),
    )
    .unwrap()
}

/// The account with `id`'s loop changed by `change`.
fn changed(id: &str, change: impl Fn(&mut Value)) -> Value {
    let mut list = account();
    for item in list["automations"].as_array_mut().unwrap() {
        if item["id"] == id {
            change(item);
        }
    }
    list
}

/// The account with `item` added.
fn with(item: Value) -> Value {
    let mut list = account();
    list["automations"].as_array_mut().unwrap().push(item);
    list
}

fn list(doc: &Value) -> Value {
    json!({"argv": LIST, "stdout": doc.to_string()})
}

fn accept() -> Value {
    json!({"any_loop_write": "update", "stdout": "Synthetic loop updated\n"})
}

fn argv(words: &str) -> Value {
    json!(words.split('|').collect::<Vec<_>>())
}

/// The account's own `syn-triage` loop as its file, by hand from
/// `loops/list.json` and the adapter's "`room-cli loop list` to a file",
/// with `priority` as given.
fn triage(room: &Room, priority: u8) -> String {
    room.write(
        "loops/syn-triage/check",
        "#!/bin/sh\n# Synthetic check: prints the due items in $WIZLOOP_PARAM_REPO, nothing when none is due.\nif [ -f due.txt ]; then cat due.txt; fi\nexit 0\n",
    );
    room.write(
        "loops/syn-triage.md",
        &format!("---\nid: \"syn-triage\"\nname: \"Synthetic triage every ten minutes\"\ntrigger: {{\"cron\": \"*/10 * * * *\", \"timezone\": \"UTC\"}}\ncheck: {{\"run\": \"syn-triage/check\", \"timeout\": 60}}\nthread: \"new\"\nagent: {{\"provider\": \"synthetic-provider\", \"model\": \"synthetic-model\", \"reasoning\": \"medium\"}}\nsecrets: [\"SYNTHETIC_TOKEN\", \".env\"]\npriority: {priority}\nparams: {{\"repo\": \"synthetic-org/synthetic-repo\"}}\n---\nSynthetic: triage the due items the check printed below."),
    )
}

// catches (C4): apply running anything but its own plan's one command for
// that id (another file's command, a second write, a retry, a `loop show`),
// a command that differs from what plan printed, no read-back after the
// write, or a read-back that is not one `loop list` compared as plan
// compares.
#[test]
fn apply_runs_only_its_plans_command_then_reads_back() {
    let room = Room::listing(
        &account(),
        &changed("loop_syn_1", |l| l["priority"] = json!(3)),
    );
    let file = triage(&room, 3);
    // Another file beside it, which apply must leave alone.
    room.write(
        "loops/syn-nightly.md",
        "---\nid: \"syn-nightly\"\nname: \"Synthetic nightly note\"\ntrigger: {\"cron\": \"0 5 * * *\", \"timezone\": \"UTC\"}\nthread: \"new\"\nsecrets: \"all\"\npriority: 1\n---\nSynthetic: post a short nightly note.",
    );
    let update = argv("loop|update|loop_syn_1|--priority|3");

    // The plan apply runs: printed first, by plan itself.
    let planned = room.run_env(
        &[
            "loop", "plan", "loops", "--project", PROJECT, "--json",
        ],
        &[],
    );
    let planned: Value = serde_json::from_slice(&planned.stdout).unwrap();
    let triage_item = planned["items"]
        .as_array()
        .unwrap()
        .iter()
        .find(|i| i["id"] == "syn-triage")
        .unwrap();
    assert_eq!(triage_item["commands"], json!([{"argv": update, "files": {}}]));
    assert_eq!(room.calls(), vec![json!(LIST)], "plan only read");

    let (code, doc) = room.json(&["syn-triage", "--from", &file]);
    assert_eq!(code, 0, "{doc:#}");
    assert_eq!(
        doc,
        json!({
            "schema": "openwiz.loop-apply.v1", "command": "apply", "exit_code": 0,
            "project": PROJECT, "id": "syn-triage", "file": file, "action": "update",
            "loop": "loop_syn_1", "commands": triage_item["commands"],
            "outcome": "updated", "read_back": {"differences": []}, "refusals": [],
        })
    );
    // Plan's one list, then apply's: one list, its one update, one list.
    assert_eq!(
        room.calls(),
        vec![json!(LIST), json!(LIST), update.clone(), json!(LIST)]
    );
    assert_eq!(room.writes(), vec![json!({"argv": update, "files": {}})]);
    room.assert_no_temporary_files();
}

// catches (C4): a create whose prompt or script files are not the plan's
// text byte for byte, are left behind or are not in a private temporary
// folder; or a created loop's id not read back from `loop list`.
#[test]
fn apply_creates_with_the_plans_files_and_removes_them() {
    let script = "#!/bin/sh\n# wizloop: params from the loop file, as data\nexport WIZLOOP_PARAM_REPO='example-org/example-repo'\n# wizloop: the check\n# Prints one line per due item in $WIZLOOP_PARAM_REPO; nothing when none is due.\nif [ -f due.txt ]; then cat due.txt; fi\nexit 0\n";
    let prompt = "Triage the due items for spec 42 that the check printed below.\n";
    let created = json!({"id": "loop_syn_7", "project_id": PROJECT, "session_id": "thr_syn_0001", "name": "Example triage every ten minutes [wizloop:cron-check]", "cron": "*/10 * * * *", "timezone": "UTC", "run_at": null, "webhook": false, "new_thread": true, "script": script, "agent": {"provider": "example-provider", "model": "example-model", "reasoning": "medium"}, "secrets": ["EXAMPLE_TOKEN", ".env"], "priority": 2, "prompt": prompt, "enabled": true, "last_error": null, "last_run_at": null, "next_run_at": null, "runs": 0});
    let room = Room::new(
        vec![
            list(&account()),
            json!({"any_loop_write": "create", "stdout": "Synthetic loop created: loop_syn_7\n"}),
        ],
        vec![list(&with(created))],
    );
    let file = fixture("cron-check.md");
    let (code, doc) = room.json(&["cron-check", "--from", &file]);
    assert_eq!(code, 0, "{doc:#}");
    let create = "loop|create|--name|Example triage every ten minutes [wizloop:cron-check]|--prompt-file|@prompt|--cron|*/10 * * * *|--timezone|UTC|--new-thread|--script-file|@script|--provider|example-provider|--model|example-model|--reasoning|medium|--priority|2|--secrets|EXAMPLE_TOKEN,.env";
    assert_eq!(
        doc,
        json!({
            "schema": "openwiz.loop-apply.v1", "command": "apply", "exit_code": 0,
            "project": PROJECT, "id": "cron-check", "file": file, "action": "create",
            "loop": "loop_syn_7",
            "commands": [{"argv": argv(create), "files": {"@prompt": prompt, "@script": script}}],
            "outcome": "created", "read_back": {"differences": []}, "refusals": [],
        })
    );
    let writes = room.writes();
    assert_eq!(writes.len(), 1, "{writes:#?}");
    let ran: Vec<&str> = writes[0]["argv"]
        .as_array()
        .unwrap()
        .iter()
        .map(|a| a.as_str().unwrap())
        .collect();
    // The same command, with each `@` operand a file apply wrote.
    let (prompt_path, script_path) = (ran[5], ran[12]);
    let mut expected: Vec<&str> = create.split('|').collect();
    expected[5] = prompt_path;
    expected[12] = script_path;
    assert_eq!(ran, expected);
    let tmp = room.dir().join("tmp");
    for path in [prompt_path, script_path] {
        assert!(Path::new(path).starts_with(&tmp), "{path}");
        assert!(!Path::new(path).exists(), "{path} was left behind");
    }
    assert_eq!(
        writes[0]["files"],
        json!({"--prompt-file": prompt, "--script-file": script})
    );
    assert_eq!(
        room.calls(),
        vec![json!(LIST), writes[0]["argv"].clone(), json!(LIST)]
    );
    room.assert_no_temporary_files();
}

// catches: a webhook address that is lost, or written anywhere but the one
// result (a file, the plan, a log), contrary to the adapter's "A webhook
// address is shown once".
#[test]
fn a_created_webhooks_address_reaches_only_the_caller_once() {
    let address = "https://example.invalid/synthetic/hook";
    let created = json!({"id": "loop_syn_7", "project_id": PROJECT, "session_id": "thr_syn_0001", "name": "Wake on a delivery [wizloop:webhook-new]", "cron": null, "timezone": null, "run_at": null, "webhook": true, "new_thread": true, "script": null, "agent": null, "secrets": [], "priority": 4, "prompt": "Read the requests that arrived and route each one to its owner.\n", "enabled": true, "last_error": null, "last_run_at": null, "next_run_at": null, "runs": 0});
    let answers = vec![
        list(&account()),
        json!({"any_loop_write": "create", "webhook": true, "stdout": format!("Synthetic loop created: loop_syn_7\n{address}\n")}),
    ];
    let room = Room::new(answers.clone(), vec![list(&with(created.clone()))]);
    let file = fixture("webhook-new.md");
    let (code, doc) = room.json(&["webhook-new", "--from", &file]);
    assert_eq!(code, 0, "{doc:#}");
    assert_eq!(
        (&doc["outcome"], &doc["loop"], &doc["webhook_address"]),
        (&json!("created"), &json!("loop_syn_7"), &json!(address))
    );
    // Once in the result, and in no file apply could have written.
    fn walk(dir: &Path, address: &str) {
        for entry in fs::read_dir(dir).unwrap() {
            let path = entry.unwrap().path();
            if path.is_dir() {
                walk(&path, address);
            } else if !path.ends_with("before.json") {
                let bytes = fs::read(&path).unwrap_or_default();
                assert!(
                    !String::from_utf8_lossy(&bytes).contains(address),
                    "{} holds the address",
                    path.display()
                );
            }
        }
    }
    walk(room.dir(), address);
    // The text run prints it once, escaped like every other value.
    let room = Room::new(answers, vec![list(&with(created))]);
    let output = room.apply(&["webhook-new", "--from", &file]);
    let text = String::from_utf8(output.stdout).unwrap();
    assert_eq!(text.matches(address).count(), 1, "{text}");
}

// catches (C4, an unclear outcome): a read-back that differs reported as
// success, or a write retried to make it match.
#[test]
fn a_differing_read_back_is_reported_and_never_retried() {
    // Cloudroom accepts the update, and `loop list` still shows priority 2.
    let room = Room::listing(&account(), &account());
    let file = triage(&room, 3);
    let (code, doc) = room.json(&["syn-triage", "--from", &file]);
    assert_eq!(code, 5, "{doc:#}");
    assert_eq!(doc["outcome"], "different");
    assert_eq!(
        doc["read_back"],
        json!({"differences": [{"field": "priority", "file": 3, "live": 2}]})
    );
    let update = argv("loop|update|loop_syn_1|--priority|3");
    assert_eq!(room.calls(), vec![json!(LIST), update, json!(LIST)]);
    assert_eq!(room.writes().len(), 1);
}

// catches (C4, an unclear outcome): a write that times out, ends without an
// exit code, or is followed by a failed read-back being reported as done,
// failed or refused, or retried; and a hung write that is never stopped.
#[test]
fn an_unclear_outcome_is_unknown_and_never_retried() {
    let update = argv("loop|update|loop_syn_1|--priority|3");
    let cases: [(&str, Vec<Value>, Vec<Value>, Vec<Value>); 3] = [
        (
            "the write hangs",
            vec![
                list(&account()),
                json!({"any_loop_write": "update", "hang": true}),
            ],
            vec![],
            vec![json!(LIST), update.clone()],
        ),
        (
            "the write ends without an exit code",
            vec![
                list(&account()),
                json!({"any_loop_write": "update", "abort": true}),
            ],
            vec![],
            vec![json!(LIST), update.clone()],
        ),
        (
            "the read-back fails",
            vec![list(&account()), accept()],
            vec![json!({"argv": LIST, "stderr": "Error: HTTP 503: Service Unavailable", "exit": 1})],
            vec![json!(LIST), update.clone(), json!(LIST)],
        ),
    ];
    for (case, before, after, calls) in cases {
        let room = Room::new(before, after);
        let file = triage(&room, 3);
        let (code, doc) = room.json_env(
            &["syn-triage", "--from", &file],
            &[("OPENWIZ_FIXTURE_READ_TIMEOUT_MS", "500")],
        );
        assert_eq!(code, 6, "{case}: {doc:#}");
        assert_eq!(
            (&doc["outcome"], &doc["read_back"], &doc["action"]),
            (&json!("unknown"), &json!(null), &json!("update")),
            "{case}"
        );
        assert_eq!(room.calls(), calls, "{case}");
        assert_eq!(room.writes().len(), 1, "{case}: one write, never retried");
        room.assert_no_temporary_files();
        // A hung write was stopped and reaped.
        if let Ok(pid) = fs::read_to_string(room.dir().join("bin/hang.pid")) {
            assert!(
                !cfg!(target_os = "linux") || !Path::new("/proc").join(pid.trim()).exists(),
                "{case}: the hung room-cli is still running"
            );
        }
    }
}

// catches: a command Cloudroom refused being reported as done or unknown,
// its message changed or withheld, or apply going on to read back or run
// anything more.
#[test]
fn a_command_cloudroom_refuses_is_failed_with_its_message_unchanged() {
    let message = "Error: HTTP 409: Synthetic refusal, the loop changed (try later)";
    let room = Room::new(
        vec![
            list(&account()),
            json!({"any_loop_write": "update", "stderr": message, "exit": 1}),
        ],
        vec![],
    );
    let file = triage(&room, 3);
    let (code, doc) = room.json(&["syn-triage", "--from", &file]);
    assert_eq!(code, 5, "{doc:#}");
    assert_eq!(
        (&doc["outcome"], &doc["read_back"]),
        (&json!("failed"), &json!(null))
    );
    assert_eq!(
        doc["refusals"],
        json!([{"file": file, "code": "room-cli", "field": "file", "message": message}])
    );
    assert_eq!(
        room.calls(),
        vec![json!(LIST), argv("loop|update|loop_syn_1|--priority|3")]
    );
}

// catches: apply writing (or reading) for a file it should refuse: one
// whose id is not the one named, one the adapter refuses, or one with no
// change to make.
#[test]
fn apply_writes_nothing_it_should_not() {
    let room = Room::listing(&account(), &account());
    // The file's id is not the one asked for: nothing is read at all.
    let file = triage(&room, 3);
    let (code, doc) = room.json(&["syn-nightly", "--from", &file]);
    assert_eq!(code, 5, "{doc:#}");
    assert_eq!(
        (&doc["outcome"], &doc["action"], &doc["commands"], &doc["read_back"]),
        (&json!("refused"), &json!("refused"), &json!([]), &json!(null))
    );
    assert_eq!(
        doc["refusals"],
        json!([{"file": file, "code": "apply-id-mismatch", "field": "id", "message": "the file's id is syn-triage, not syn-nightly"}])
    );
    assert_eq!(room.calls(), Vec::<Value>::new());

    // The adapter refuses it (Cloudroom cannot change a loop's thread).
    let file = room.write(
        "loops/syn-nightly.md",
        "---\nid: \"syn-nightly\"\nname: \"Synthetic nightly note\"\ntrigger: {\"cron\": \"0 5 * * *\", \"timezone\": \"America/Los_Angeles\"}\nthread: \"same\"\nsecrets: \"all\"\npriority: 3\n---\nSynthetic: post a short nightly note.",
    );
    let (code, doc) = room.json(&["syn-nightly", "--from", &file]);
    assert_eq!(code, 5, "{doc:#}");
    assert_eq!(
        (&doc["outcome"], &doc["action"], &doc["loop"]),
        (&json!("refused"), &json!("refused"), &json!("loop_syn_3"))
    );
    assert_eq!(
        doc["refusals"],
        json!([{"file": file, "code": "cf-update-thread", "field": "thread", "message": "Cloudroom cannot change a loop's thread"}])
    );
    assert_eq!(room.calls(), vec![json!(LIST)]);

    // Nothing differs: unchanged, from `./<id>.md` by default.
    room.write(
        "syn-nightly.md",
        "---\nid: \"syn-nightly\"\nname: \"Synthetic nightly note\"\ntrigger: {\"cron\": \"0 5 * * *\", \"timezone\": \"America/Los_Angeles\"}\nthread: \"new\"\nsecrets: \"all\"\npriority: 3\n---\nSynthetic: post a short nightly note.",
    );
    let (code, doc) = room.json(&["syn-nightly"]);
    assert_eq!(code, 0, "{doc:#}");
    assert_eq!(
        doc,
        json!({
            "schema": "openwiz.loop-apply.v1", "command": "apply", "exit_code": 0,
            "project": PROJECT, "id": "syn-nightly", "file": "./syn-nightly.md",
            "action": "none", "loop": "loop_syn_3", "commands": [],
            "outcome": "unchanged", "read_back": null, "refusals": [],
        })
    );
    assert_eq!(room.calls(), vec![json!(LIST), json!(LIST)]);
    assert_eq!(room.writes(), Vec::<Value>::new());
}

// catches: a failed read before any write (the file, or `loop list`)
// reported as a result, or followed by a write.
#[test]
fn a_failed_read_before_any_write_exits_1_and_writes_nothing() {
    let room = Room::new(
        vec![json!({"argv": LIST, "stderr": "Error: HTTP 503: Service Unavailable", "exit": 1}), accept()],
        vec![],
    );
    let (code, doc) = room.json(&["syn-triage", "--from", "missing.md"]);
    assert_eq!(code, 1, "{doc:#}");
    assert_eq!(doc["schema"], "openwiz.cli-error.v1");
    assert_eq!(room.calls(), Vec::<Value>::new());
    let file = triage(&room, 3);
    let (code, doc) = room.json(&["syn-triage", "--from", &file]);
    assert_eq!(code, 1, "{doc:#}");
    assert_eq!(doc["schema"], "openwiz.cli-error.v1");
    assert_eq!(room.calls(), vec![json!(LIST)]);
    assert_eq!(room.writes(), Vec::<Value>::new());
}

// catches: an `--adopt` binding that is ignored, names another id, or is
// passed to the read-back, so an adopted loop never reads back as its file.
#[test]
fn apply_adopts_an_unmarked_loop_by_its_binding() {
    let room = Room::listing(
        &account(),
        &changed("loop_syn_5", |l| {
            l["name"] = json!("Synthetic hourly kick [wizloop:synthetic-hourly-kick]");
        }),
    );
    room.write("loops/synthetic-hourly-kick/check", "#!/bin/sh\nexit 0\n");
    let file = room.write(
        "loops/synthetic-hourly-kick.md",
        "---\nid: \"synthetic-hourly-kick\"\nname: \"Synthetic hourly kick\"\ntrigger: {\"cron\": \"12 * * * *\", \"timezone\": \"UTC\"}\ncheck: {\"run\": \"synthetic-hourly-kick/check\", \"timeout\": 60}\nthread: \"new\"\nsecrets: []\npriority: 3\n---\nSynthetic: nothing to do.",
    );
    // A binding for another id is a usage error, and nothing is read.
    let (code, doc) = room.json(&[
        "synthetic-hourly-kick",
        "--from",
        &file,
        "--adopt",
        "other=loop_syn_5",
    ]);
    assert_eq!(code, 2, "{doc:#}");
    assert_eq!(doc["error"]["kind"], "usage");
    assert_eq!(room.calls(), Vec::<Value>::new());

    let (code, doc) = room.json(&[
        "synthetic-hourly-kick",
        "--from",
        &file,
        "--adopt",
        "synthetic-hourly-kick=loop_syn_5",
    ]);
    assert_eq!(code, 0, "{doc:#}");
    let rename = argv(
        "loop|update|loop_syn_5|--name|Synthetic hourly kick [wizloop:synthetic-hourly-kick]",
    );
    assert_eq!(
        (&doc["outcome"], &doc["loop"], &doc["read_back"]),
        (
            &json!("updated"),
            &json!("loop_syn_5"),
            &json!({"differences": []})
        )
    );
    assert_eq!(room.calls(), vec![json!(LIST), rename, json!(LIST)]);
}

// catches (revision 3, red first with the round-trip fixture): apply
// silently dropping a live setting the adapter does not map. `loop update`
// sends only the mapped flags, and nothing shows whether Cloudroom keeps
// the rest (an agent rotation, say, which one `--provider` ends), so a loop
// carrying such a key is refused before any write, never written.
#[cfg(target_os = "linux")]
#[test]
fn apply_refuses_a_loop_with_an_unmapped_setting_and_writes_nothing() {
    // The round-trip fixture: the synthetic account plus one marked loop
    // carrying a key the adapter does not map (as `loop_plan.rs`'s
    // `export_then_plan_shows_no_difference` builds it).
    let mut budget = account()["automations"][2].clone();
    budget["id"] = json!("loop_syn_8");
    budget["name"] = json!("Synthetic budget [wizloop:syn-budget]");
    budget["prompt"] = json!("Synthetic: report the budget.");
    budget["budget_synthetic"] = json!({"max_runs": 3});
    let accounts = with(budget);
    let room = Room::listing(&accounts, &accounts);
    dirs::private_dir_all(room.dir().join("exported")).unwrap();
    let export = room.run_env(
        &[
            "loop", "export", "--project", PROJECT, "--out", "exported", "--json",
        ],
        &[],
    );
    assert_eq!(export.status.code(), Some(0));
    let file = room.dir().join("exported/syn-budget.md");
    let exported = fs::read_to_string(&file).unwrap();
    let file = file.to_str().unwrap();

    // Exactly as exported: nothing to write, so nothing is dropped.
    let (code, doc) = room.json(&["syn-budget", "--from", file]);
    assert_eq!(code, 0, "{doc:#}");
    assert_eq!(doc["outcome"], "unchanged");

    // A changed priority would need a write: refused, nothing written.
    fs::write(file, exported.replace("priority: 3", "priority: 1")).unwrap();
    let (code, doc) = room.json(&["syn-budget", "--from", file]);
    assert_eq!(code, 5, "{doc:#}");
    assert_eq!(
        (&doc["outcome"], &doc["action"], &doc["loop"], &doc["read_back"]),
        (&json!("refused"), &json!("update"), &json!("loop_syn_8"), &json!(null))
    );
    assert_eq!(
        doc["commands"],
        json!([{"argv": argv("loop|update|loop_syn_8|--priority|1"), "files": {}}])
    );
    assert_eq!(
        doc["refusals"],
        json!([{"file": file, "code": "apply-unmapped", "field": "file", "message": "Cloudroom loop loop_syn_8 carries settings the adapter does not map (budget_synthetic), and nothing shows that a write keeps them; nothing was written"}])
    );
    assert_eq!(room.writes(), Vec::<Value>::new());
    assert_eq!(
        room.calls(),
        vec![json!(LIST), json!(LIST), json!(LIST)],
        "export's list, then one list for each apply"
    );
}

// catches: a text run that prints room-cli's message, a Cloudroom id or a
// path with its terminal controls (so they can clear the screen or set the
// clipboard), or that does not show the exact command before it runs.
#[test]
fn text_output_previews_the_command_and_never_prints_a_terminal_control() {
    let message = "Error: HTTP 409: Synthetic\u{1b}]52;c;eA==\u{7} refusal";
    let room = Room::new(
        vec![
            list(&account()),
            json!({"any_loop_write": "update", "stderr": message, "exit": 1}),
        ],
        vec![],
    );
    let file = triage(&room, 3);
    let output = room.apply(&["syn-triage", "--from", &file]);
    assert_eq!(output.status.code(), Some(5));
    let text = String::from_utf8(output.stdout).unwrap();
    let err = String::from_utf8(output.stderr).unwrap();
    for out in [&text, &err] {
        assert!(!out.contains('\u{1b}') && !out.contains('\u{7}'), "{out:?}");
    }
    assert!(
        text.contains("  room-cli 'loop' 'update' 'loop_syn_1' '--priority' '3'\n"),
        "{text}"
    );
    assert!(
        text.contains(&format!(
            "{file}: file: Error: HTTP 409: Synthetic?]52;c;eA==? refusal\n"
        )),
        "{text}"
    );
    assert!(text.contains(&format!("{file}: failed loop_syn_1\n")), "{text}");
}
