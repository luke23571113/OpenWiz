//! IF5's embedded read composition, through the real service dispatch.
//! All GitHub and CloudRoom responses are synthetic; no live calls are possible.
use super::*;

fn github(f: &Fixture) {
    place_script(
        &f.root.join("tools/gh"),
        r#"#!/usr/bin/python3 -I
import json
import os
from pathlib import Path
import sys
args = sys.argv[1:]
root = Path(__file__).parent.parent
selected = 'synthetic-owner/synthetic-repo'
if (root / 'installed-context').exists():
    selected = os.environ.get('GH_REPO')
    with (root / 'github-context.jsonl').open('a') as log:
        log.write(json.dumps({'repository':selected, 'cwd':os.getcwd()}) + '\n')
    # Synthetic source visibility: the selected repo exists; the unrelated
    # foreign checkout is inaccessible to this installation.
    if selected != 'synthetic-owner/selected-repo':
        sys.exit(97)
with (root / 'embedded-reads.jsonl').open('a') as log:
    log.write(json.dumps(args) + '\n')
if (root / 'read-failure').exists():
    sys.stderr.write('SYNTHETIC_PRIVATE_DIAGNOSTIC /synthetic/private\n')
    sys.exit(97)
data = json.loads((root / 'populated.json').read_text()) if (root / 'populated.json').exists() else {}
def page(nodes):
    return {'totalCount': len(nodes), 'pageInfo': {'hasNextPage': False, 'endCursor': None}, 'nodes': nodes}
if args == ['--version']:
    print('gh version 2.100.0 (2026-09-03)')
elif args[:3] == ['repo', 'view', '--json']:
    repository = {'nameWithOwner': selected, 'url': 'https://github.com/' + selected, 'defaultBranchRef': {'name':'main'}}
    print(json.dumps({key: repository[key] for key in args[3].split(',')}))
elif args == ['api', 'repos/{owner}/{repo}/pulls/901', '--jq', '{number,head_sha:.head.sha}']:
    print(json.dumps({'number':901, 'head_sha':'a' * 40}))
elif args[:2] == ['api', 'graphql']:
    query = next(value for value in args if value.startswith('query='))
    if 'object(expression:$expression)' in query:
        if 'expression=' + 'a' * 40 + ':docs/grills/synthetic-choice.md' not in args:
            sys.exit(97)
        # Unverifiable saved wording remains unknown, independently of
        # this fixture's successful repository and PR-head reads.
        print(json.dumps({'data': {'repository': {
            'pullRequest': {'number':901, 'headRefOid':'a' * 40},
            'object': {'__typename':'Blob', 'text':'Synthetic source', 'isTruncated':False}}}}))
    else:
        field = 'milestones' if 'milestones(' in query else 'issues'
        print(json.dumps({'data': {'repository': {field: page(data.get(field, []))}}}))
elif args[:2] == ['api', '--include']:
    print('HTTP/2.0 200 OK\n\n' + json.dumps(data.get('comments', [])))
elif args[:2] == ['api', 'repos/{owner}/{repo}/issues/901']:
    print(json.dumps({'number':901, 'body':'Synthetic source', 'is_pull_request':True}))
elif args[:2] == ['issue', 'list']:
    print(json.dumps(data.get('fleet_issues', [])))
elif args[:2] == ['pr', 'list']:
    print('[]')
else:
    sys.exit(97)
"#,
    );
}

fn read(f: &Fixture, path: &str) -> Value {
    let (status, body) = f.request("GET", path, &format!("127.0.0.1:{}", f.port));
    assert_eq!(status, 200, "{body}");
    serde_json::from_str(&body).unwrap()
}

#[test]
fn embedded_plan_decisions_and_answer_target_survive_clean_restart() {
    let mut f = Fixture::new();
    github(&f);
    for _ in 0..2 {
        let running = f.start();
        let original = fs::read(f.root.join("service/config.json")).unwrap();
        let plan = read(&f, "/api/v1/plan");
        assert_eq!(plan["coverage"], json!({"state":"complete","gaps":[]}));
        assert_eq!(plan["tickets"], json!([]));
        let decisions = read(&f, "/api/v1/decisions");
        assert_eq!(decisions["coverage"], json!({"state":"complete","gaps":[]}));
        assert_eq!(decisions["items"], json!([]));
        assert_eq!(
            decisions["orchestrator"]["target"],
            json!({"known":"thr_syn_0001"})
        );
        assert_eq!(
            decisions["orchestrator"]["coverage"],
            json!({"state":"complete","gaps":[]})
        );
        let fleets = read(&f, "/api/v1/fleets");
        assert_eq!(fleets["orchestrator"], "thr_syn_0001");
        // HTTP reads never rewrite configuration or create a new engine.
        assert_eq!(
            fs::read(f.root.join("service/config.json")).unwrap(),
            original
        );
        drop(running);
    }
}

#[test]
fn unreadable_configured_answer_target_is_unknown_after_restart() {
    let mut f = Fixture::new();
    github(&f);
    let config_path = f.root.join("service/config.json");
    let mut config: Value = serde_json::from_slice(&fs::read(&config_path).unwrap()).unwrap();
    config["orchestrator_thread"] = json!("thr_syn_missing_target");
    private_file(&config_path, config.to_string());
    for _ in 0..2 {
        let running = f.start();
        let decisions = read(&f, "/api/v1/decisions");
        assert!(decisions["orchestrator"]["target"].get("unknown").is_some());
        assert_eq!(decisions["orchestrator"]["coverage"]["state"], "partial");
        assert_eq!(decisions["coverage"], json!({"state":"complete","gaps":[]}));
        assert!(read(&f, "/api/v1/fleets").get("orchestrator").is_none());
        drop(running);
    }
}

#[test]
fn setup_reports_saved_engine_credit_evidence_without_claiming_readiness() {
    let mut f = Fixture::new();
    private_dir(&f.root.join("setup"));
    let running = f.start();
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_millis() as u64;
    for (credits, choice) in [(1, "Cloud"), (20, "Local")] {
        let state = json!({"schema":"openwiz.setup-state.v1","revision":1,
            "checks":{"started":0,"committed":0},"project":{"repository":"synthetic-owner/synthetic-repo",
                "project":"prj_syn_0001","operator":"synthetic-owner","service_issue":7,
                "answer_thread":"thr_syn_0001","harness":"codex","model":"synthetic-model","effort":"high",
                "runtime":format!("0.0.99 {}", "1".repeat(40))},"app":null,"observations":{},
            "operations":[{"operation_id":"0123456789abcdef0123456789abcdef","kind":"activate_engine",
                "phase":"proposed","fingerprint":"2222222222222222222222222222222222222222222222222222222222222222",
                "effects":["Select one engine."],"reason":"Activation remains closed."}],
            "engine":{"location":"local","revision":1,"runtime":format!("0.0.99 {}", "1".repeat(40)),
                "operation_id":"0123456789abcdef0123456789abcdef",
                "fingerprint":"2222222222222222222222222222222222222222222222222222222222222222",
                "cost":{"source":"cloudroom_usage","provenance":"measured","credits":credits,
                    "window_s":86400,"free_allowance":3000,"observed_at":now,"allowance_at":now}}});
        private_file(&f.root.join("setup/state.json"), state.to_string());
        let report = read(&f, "/api/v1/setup");
        assert_eq!(report["engine"], "local");
        assert_eq!(report["ready"], false);
        assert_eq!(
            report["cost"]["monthly_projection"],
            json!(f64::from(credits * 30))
        );
        assert!(
            report["cost"]["reason"]
                .as_str()
                .unwrap()
                .contains(&format!("Free-account default: {choice}."))
        );
        let e = &state["engine"];
        let mut array_engine = state.clone();
        array_engine["engine"] = json!([
            e["location"],
            e["revision"],
            e["runtime"],
            e["operation_id"],
            e["fingerprint"],
            e["cost"]
        ]);
        private_file(&f.root.join("setup/state.json"), array_engine.to_string());
        assert_eq!(
            read(&f, "/api/v1/setup")["engine"],
            "unselected",
            "engine state must be an object"
        );
        let mut missing_cost = state.clone();
        missing_cost["engine"]
            .as_object_mut()
            .unwrap()
            .remove("cost");
        private_file(&f.root.join("setup/state.json"), missing_cost.to_string());
        assert_eq!(
            read(&f, "/api/v1/setup")["engine"],
            "unselected",
            "nullable fields must still be present"
        );
        let mut stale = state;
        stale["engine"]["cost"]["allowance_at"] = json!(1);
        private_file(&f.root.join("setup/state.json"), stale.to_string());
        let report = read(&f, "/api/v1/setup");
        assert_eq!(report["cost"]["provenance"], "unknown");
        assert_eq!(report["cost"]["credits"], Value::Null);
    }
    drop(running);
}

#[test]
fn engine_absence_does_not_allow_positional_setup_state() {
    let f = Fixture::new();
    private_dir(&f.root.join("setup"));
    let good = json!({"schema":"openwiz.setup-state.v1","revision":0,
        "checks":{"started":0,"committed":0},"project":null,"app":null,
        "observations":{},"operations":[],"engine":null});
    private_file(&f.root.join("setup/state.json"), good.to_string());
    assert!(openwiz_store::setup::read(&f.root).unwrap().is_some());
    for positional in [
        json!(["openwiz.setup-state.v1",0,{"started":0,"committed":0},null,null,{},[],null]),
        json!(["openwiz.setup-state.v1",0,{"started":0,"committed":0},null,null,{},[]]),
    ] {
        private_file(&f.root.join("setup/state.json"), positional.to_string());
        assert!(openwiz_store::setup::read(&f.root).is_err(), "{positional}");
    }
}

#[test]
fn installed_repository_context_survives_hostile_ambient_and_clean_restart() {
    let mut f = Fixture::new();
    github(&f);
    private_file(&f.root.join("installed-context"), "synthetic fixture");
    let foreign = f.root.join("foreign-checkout");
    private_dir(&foreign);
    Command::new("git")
        .arg("init")
        .arg(&foreign)
        .output()
        .unwrap();
    assert!(
        Command::new("git")
            .args([
                "remote",
                "add",
                "origin",
                "https://github.com/synthetic-owner/wrong-repo.git"
            ])
            .current_dir(&foreign)
            .status()
            .unwrap()
            .success()
    );
    // A selected repository with no issues is still a complete empty read. A
    // wrong ambient repo must not masquerade as the configured service repo.
    let mut config: Value =
        serde_json::from_slice(&fs::read(f.root.join("service/config.json")).unwrap()).unwrap();
    config["repository"]["name"] = json!("selected-repo");
    private_file(&f.root.join("service/config.json"), config.to_string());
    for _ in 0..2 {
        let output = Command::new("/usr/bin/python3")
            .args([
                "-I",
                concat!(
                    env!("CARGO_MANIFEST_DIR"),
                    "/../../tests/service/fixtures/engine_environment.py"
                ),
            ])
            .arg(&f.root)
            .arg(ROOT)
            .current_dir(&foreign)
            .env("GH_REPO", "synthetic-owner/wrong-repo")
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
        let manager: Value = serde_json::from_slice(&output.stdout).unwrap();
        assert_eq!(
            manager["environment"]["GH_REPO"],
            "synthetic-owner/selected-repo"
        );
        assert!(
            manager["definition"]
                .as_str()
                .unwrap()
                .contains("GH_REPO=synthetic-owner/selected-repo")
        );
        private_file(
            &f.root.join("runtime-environment.json"),
            manager["environment"].to_string(),
        );
        let running = f.start();
        let plan = read(&f, "/api/v1/plan");
        assert_eq!(plan["coverage"], json!({"state":"complete","gaps":[]}));
        assert_eq!(plan["tickets"], json!([]));
        let decisions = read(&f, "/api/v1/decisions");
        assert_eq!(decisions["coverage"], json!({"state":"complete","gaps":[]}));
        assert_eq!(decisions["items"], json!([]));
        let calls = fs::read_to_string(f.root.join("github-context.jsonl")).unwrap();
        let observed: Vec<Value> = calls
            .lines()
            .map(|line| serde_json::from_str(line).unwrap())
            .collect();
        assert!(!observed.is_empty());
        assert!(
            observed
                .iter()
                .all(|call| call["repository"] == "synthetic-owner/selected-repo"
                    && call["cwd"] == foreign.to_str().unwrap()),
            "{calls}"
        );
        drop(running);
    }
}

fn bind_repository(f: &Fixture) {
    let base = Path::new(ROOT).join("tests/fixtures/room-cli-0.43.1/normal");
    let mut scenario: Value =
        serde_json::from_slice(&fs::read(base.join("scenario.json")).unwrap()).unwrap();
    scenario["synthetic_assumptions"].as_array_mut().unwrap().push(json!("Project one has the synthetic GitHub repository consumed by the service's configured read sources."));
    for response in scenario["responses"].as_array_mut().unwrap() {
        if let Some(name) = response["stdout_file"].as_str().map(str::to_owned) {
            if name == "project-list.json" {
                let mut projects: Value =
                    serde_json::from_slice(&fs::read(base.join(&name)).unwrap()).unwrap();
                projects[0]["gitRemoteUrl"] =
                    json!("https://github.com/synthetic-owner/synthetic-repo.git");
                response.as_object_mut().unwrap().remove("stdout_file");
                response["stdout"] = json!(projects.to_string());
            } else {
                response["stdout_file"] = json!(base.join(name));
            }
        }
    }
    let path = f.root.join("tools/embedded-scenario.json");
    private_file(&path, scenario.to_string());
    private_file(
        &f.root.join("tools/fake-room-cli.scenario"),
        path.to_str().unwrap(),
    );
}

fn populated(f: &Fixture) {
    let page = |nodes: Vec<Value>| json!({"totalCount":nodes.len(),"pageInfo":{"hasNextPage":false,"endCursor":null},"nodes":nodes});
    let link = |n| json!({"number":n,"url":format!("https://github.com/synthetic-owner/synthetic-repo/issues/{n}")});
    let issues=[901,902].map(|n|json!({"number":n,"title":format!("Synthetic issue {n}"),"url":format!("https://github.com/synthetic-owner/synthetic-repo/issues/{n}"),"state":"OPEN","milestone":null,
        "parent":if n==902 {link(901)} else {Value::Null},
        "labels":page(if n==902 {vec![json!({"name":"ready-for-agent"})]} else {vec![]}),
        "subIssues":page(if n==901 {vec![link(902)]} else {vec![]}),
        "blockedBy":page(vec![]),"closedByPullRequestsReferences":page(vec![])}));
    // Existing independent canonical-hash vector from the decisions proofs;
    // no production hashing/normalization generates the expected fingerprint.
    let proposal = json!({"schema":"openwiz.decisions.v1","kind":"grill_round","id":"synthetic-open",
        "status":"open","fingerprint":"a362c2cc752a0ee9f7be29ef3fdf2f29286ae9b8a2611e68515ffe8f51a4bf49","risk":"ordinary",
        "grill_file":"docs/grills/synthetic-choice.md","round":1,
        "questions":[{"id":"G1","decides":"Synthetic choice?","context":"Exact context 合成.","recommendation":"Keep spaces. "}],"answered":[]});
    let comments = json!([{"id":701,"body":format!("Synthetic prose.\n```json\n{proposal}\n```\n"),
        "issue_url":"https://api.github.com/repos/synthetic-owner/synthetic-repo/issues/901",
        "created_at":"1970-01-01T00:00:01Z","updated_at":"1970-01-01T00:00:02Z"}]);
    private_file(
        &f.root.join("populated.json"),
        json!({"issues":issues,"comments":comments}).to_string(),
    );
}

fn configured_cockpit(f: &Fixture) {
    let cockpit = read(f, "/api/v1/cockpit");
    assert_eq!(cockpit["schema"], "openwiz.cockpit.v1");
    let projects = cockpit["projects"]["items"].as_array().unwrap();
    let selected = projects.iter().find(|p| p["id"] == "prj_syn_0001").unwrap();
    assert_eq!(
        selected["orchestrator"]["target"],
        json!({"known":"thr_syn_0001"}),
        "{cockpit}"
    );
}

fn populated_sources_case(collision_wake: Option<usize>) {
    let mut f = Fixture::new();
    github(&f);
    bind_repository(&f);
    populated(&f);
    let original = fs::read(f.root.join("service/config.json")).unwrap();
    for wake in 0..2 {
        // Hold a real, newly allocated loopback port for the selected start.
        // Fixture::start must take its existing bind-refusal recovery path.
        let occupied = collision_wake
            .filter(|expected| *expected == wake)
            .map(|_| {
                let listener = TcpListener::bind(("127.0.0.1", 0)).unwrap();
                f.port = listener.local_addr().unwrap().port();
                let path = f.root.join("service/config.json");
                let mut configured: Value =
                    serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
                configured["server"]["port"] = json!(f.port);
                private_file(&path, configured.to_string());
                listener
            });
        let running = f.start();
        // Permit only the existing startup recovery's port rewrite; compare
        // every other field against the preserved pre-start document.
        let mut expected: Value = serde_json::from_slice(&original).unwrap();
        expected["server"]["port"] = json!(f.port);
        if let Some(listener) = &occupied {
            assert_ne!(
                f.port,
                listener.local_addr().unwrap().port(),
                "bind refusal must actually recover"
            );
        }
        let plan = read(&f, "/api/v1/plan");
        assert_eq!(plan["coverage"], json!({"state":"complete","gaps":[]}));
        assert_eq!(plan["tickets"].as_array().unwrap().len(), 1, "{plan}");
        assert_eq!(plan["tickets"][0]["number"], 902);
        assert_eq!(
            plan["tickets"][0]["title"],
            json!({"known":"Synthetic issue 902"})
        );
        assert_eq!(plan["tickets"][0]["spec"], json!({"known":901}));
        let decisions = read(&f, "/api/v1/decisions");
        assert_eq!(
            decisions["items"].as_array().unwrap().len(),
            1,
            "{decisions}"
        );
        assert_eq!(
            decisions["items"][0]["subject"],
            json!({"repository":"synthetic-owner/synthetic-repo","kind":"pull_request","number":901})
        );
        assert_eq!(decisions["items"][0]["request"]["id"], "synthetic-open");
        assert_eq!(
            decisions["items"][0]["request"]["questions"][0]["context"],
            "Exact context 合成."
        );
        assert_eq!(
            decisions["items"][0]["request"]["questions"][0]["recommendation"],
            "Keep spaces. "
        );
        assert!(decisions["items"][0]["current"]["unknown"].is_string());
        assert_eq!(
            decisions["coverage"]["state"], "partial",
            "saved proposal verification remains unsupported"
        );
        assert_eq!(decisions["coverage"]["gaps"][0]["kind"], "unsupported");
        assert_eq!(
            decisions["orchestrator"]["target"],
            json!({"known":"thr_syn_0001"})
        );
        configured_cockpit(&f);
        assert_eq!(
            fs::read(f.root.join("service/config.json")).unwrap(),
            expected.to_string().into_bytes()
        );
        drop(running);
    }
}

#[test]
fn populated_embedded_sources_and_cockpit_keep_configured_target_across_restart() {
    populated_sources_case(None);
}

#[test]
fn populated_reads_preserve_config_after_initial_bind_refusal() {
    populated_sources_case(Some(0));
}

#[test]
fn populated_reads_preserve_config_after_restart_bind_refusal() {
    populated_sources_case(Some(1));
}

#[test]
fn embedded_source_failure_keeps_uncertainty_and_withholds_diagnostics_after_restart() {
    let mut f = Fixture::new();
    github(&f);
    private_file(&f.root.join("read-failure"), "Synthetic failed source");
    for _ in 0..2 {
        let running = f.start();
        for route in ["/api/v1/plan", "/api/v1/decisions", "/api/v1/cockpit"] {
            let body = read(&f, route);
            assert!(!body.to_string().contains("SYNTHETIC_PRIVATE_DIAGNOSTIC"));
            assert!(!body.to_string().contains("/synthetic/private"));
            if route == "/api/v1/cockpit" {
                assert_eq!(body["projects"]["coverage"]["state"], "partial", "{body}");
            } else {
                assert_eq!(body["coverage"]["state"], "partial", "{body}");
            }
            if route == "/api/v1/decisions" {
                assert_eq!(
                    body["orchestrator"]["target"],
                    json!({"known":"thr_syn_0001"})
                );
                assert_eq!(body["orchestrator"]["coverage"]["state"], "complete");
            }
        }
        drop(running);
        let log = fs::read_to_string(f.root.join("stderr.log")).unwrap();
        assert!(!log.contains("SYNTHETIC_PRIVATE_DIAGNOSTIC"));
        assert!(!log.contains("/synthetic/private"));
    }
    let calls = fs::read_to_string(f.root.join("embedded-reads.jsonl")).unwrap();
    assert!(!calls.is_empty());
    for line in calls.lines() {
        let args: Vec<String> = serde_json::from_str(line).unwrap();
        assert!(!args.iter().any(|arg| matches!(
            arg.as_str(),
            "comment" | "edit" | "merge" | "close" | "spawn" | "tell"
        )));
    }
}

// Fixture programs are placed by a separate `cp` (#811), shared.
#[path = "../support/place.rs"]
mod place;
use place::place_script;
