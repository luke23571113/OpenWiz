//! EP1 and EP3's contract halves (#651). These checks use the existing
//! dependency-free schema checker, not a producer or a live GitHub read.
//! All fixtures are synthetic. Semantics follow the ruling on #651.

use serde_json::{Value, json};

const ROOT: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../contracts");

fn schema(name: &str) -> Value {
    let text = std::fs::read_to_string(format!("{ROOT}/{name}.v1.schema.json"))
        .unwrap_or_else(|error| panic!("{name}.v1 schema must exist: {error}"));
    serde_json::from_str(&text).expect("schema must be JSON")
}

fn checked_schema(name: &str, id: &str) {
    let schema = schema(name);
    assert_eq!(schema["title"], id);
    assert_eq!(lint(&schema), Vec::<String>::new());
    for malformed in [
        json!(null),
        json!(false),
        json!(1),
        json!("Synthetic non-record"),
        json!([]),
        json!([901, "Synthetic positional record"]),
        json!({}),
    ] {
        let errors = validate(&schema, &malformed);
        assert!(
            !errors.is_empty(),
            "{name} must refuse malformed root {malformed}"
        );
        assert!(
            errors.iter().all(|error| !error.contains("unresolvable")),
            "{errors:#?}"
        );
    }
}

// maxItems is standard JSON Schema; the shared checker does not implement it.
// Check its form everywhere, then apply it at the same resolved schema nodes.
fn without_max_items(node: &Value, errors: &mut Vec<String>) -> Value {
    match node {
        Value::Object(map) => {
            if let Some(bound) = map.get("maxItems")
                && (map.get("type") != Some(&json!("array")) || bound.as_u64().is_none())
            {
                errors.push("maxItems must be an unsigned integer on an array".into());
            }
            Value::Object(
                map.iter()
                    .filter(|(key, _)| key.as_str() != "maxItems")
                    .map(|(key, value)| (key.clone(), without_max_items(value, errors)))
                    .collect(),
            )
        }
        Value::Array(items) => {
            Value::Array(items.iter().map(|v| without_max_items(v, errors)).collect())
        }
        other => other.clone(),
    }
}

fn lint(schema: &Value) -> Vec<String> {
    let mut errors = vec![];
    let stripped = without_max_items(schema, &mut errors);
    errors.extend(crate::pattern::lint(&stripped));
    errors
}

fn validate(schema: &Value, value: &Value) -> Vec<String> {
    let mut errors = vec![];
    let stripped = without_max_items(schema, &mut errors);
    errors.extend(crate::pattern::validate(&stripped, value));
    if !errors.is_empty() {
        return errors;
    }
    fn walk(root: &Value, node: &Value, at: &str, value: &Value, errors: &mut Vec<String>) {
        if let Some(reference) = node.get("$ref").and_then(Value::as_str) {
            let pointer = reference.strip_prefix('#').unwrap();
            walk(root, root.pointer(pointer).unwrap(), pointer, value, errors);
        }
        if let (Some(max), Some(items)) = (
            node.get("maxItems").and_then(Value::as_u64),
            value.as_array(),
        ) && items.len() as u64 > max
        {
            errors.push(format!("{at}: {} items exceeds {max}", items.len()));
        }
        if let (Some(props), Some(object)) = (
            node.get("properties").and_then(Value::as_object),
            value.as_object(),
        ) {
            for (key, child) in object {
                if let Some(next) = props.get(key) {
                    walk(root, next, &format!("{at}/properties/{key}"), child, errors);
                }
            }
        }
        if let (Some(items), Some(values)) = (node.get("items"), value.as_array()) {
            for item in values {
                walk(root, items, &format!("{at}/items"), item, errors);
            }
        }
        if let Some(branches) = node.get("oneOf").and_then(Value::as_array) {
            for (i, branch) in branches.iter().enumerate() {
                let pointer = format!("{at}/oneOf/{i}");
                let probe = json!({"$defs": root["$defs"], "$ref": format!("#{pointer}")});
                let stripped = without_max_items(&probe, &mut vec![]);
                if crate::pattern::validate(&stripped, value).is_empty() {
                    walk(root, branch, &pointer, value, errors);
                }
            }
        }
    }
    walk(schema, schema, "", value, &mut errors);
    errors
}

fn plan() -> Value {
    json!({
        "schema": "openwiz.plan.v1", "snapshot_at": 1700000100000_u64,
        "coverage": {"state": "complete", "gaps": []},
        "freshness": {"state": "fresh", "snapshot_at": {"known": 1700000090000_u64}},
        "lanes": [
            {"kind": "version", "number": 1, "title": {"known": "0.0.91"}},
            {"kind": "side_spec", "number": 940, "title": {"known": "Synthetic side spec"}}
        ],
        "tickets": [
            {"number": 902, "title": {"known": "Synthetic owner gate"},
             "url": {"known": "https://github.com/synthetic-owner/synthetic-project/issues/902"},
             "spec": {"known": 901}, "lane": {"known": {"kind": "version", "number": 1}},
             "state": {"unknown": "Human ticket has no fleet state"},
             "column": {"known": "needs_you"}, "labels": {"known": ["ready-for-human"]},
             "yours": {"known": true}, "blockers": {"known": []},
             "dependents": {"known": [942]}, "pr": {"known": null}},
            {"number": 942, "title": {"known": "Synthetic dependent"},
             "url": {"known": "https://github.com/synthetic-owner/synthetic-project/issues/942"},
             "spec": {"known": 940}, "lane": {"known": {"kind": "side_spec", "number": 940}},
             "state": {"known": "blocked"}, "column": {"known": "waiting"},
             "labels": {"known": ["ready-for-agent"]}, "yours": {"known": false},
             "blockers": {"known": [902]}, "dependents": {"known": []}, "pr": {"known": null}}
        ],
        "critical_chain": {"known": {"root": 902, "blocked_count": 1, "path": [902, 942]}}
    })
}

fn records() -> Vec<Value> {
    let common = json!({"schema": "openwiz.decisions.v1", "id": "decision-syn-1",
        "status": "open", "risk": "ordinary", "fingerprint": "a".repeat(64)});
    [
        json!({"kind": "grill_round", "grill_file": "docs/grills/synthetic.md", "round": 1,
            "questions": [{"id": "G1", "decides": "Synthetic first choice",
                "context": "Synthetic context", "recommendation": "Use the synthetic option."}], "answered": []}),
        json!({"kind": "grill_confirmation", "grill_file": "docs/grills/synthetic.md",
            "summary": ["Synthetic summary decision."]}),
        json!({"kind": "spec_confirmation", "spec": 901, "summary": ["Synthetic spec summary."],
            "headline": "A synthetic capability.", "tickets": [], "graph": []}),
        json!({"kind": "plan_approval", "spec": 901, "summary": ["Synthetic plan summary."],
            "headline": "A synthetic capability.",
            "tickets": [{"number": 902, "title": "Synthetic first ticket", "blockers": []},
                {"number": 903, "title": "Synthetic second ticket", "blockers": [902]}],
            "graph": [{"blocker": 902, "ticket": 903}]})
    ].into_iter().enumerate().map(|(i, details)| {
        let mut record = common.clone();
        record.as_object_mut().unwrap().extend(details.as_object().unwrap().clone());
        record["id"] = json!(format!("decision-syn-{}", i + 1));
        record
    }).collect()
}

fn decisions() -> Value {
    json!({
        "schema": "openwiz.decisions.v1", "kind": "response", "snapshot_at": 1700000100000_u64,
        "coverage": {"state": "complete", "gaps": []},
        "freshness": {"state": "fresh", "snapshot_at": {"known": 1700000090000_u64}},
        "orchestrator": {
            "coverage": {"state": "complete", "gaps": []},
            "freshness": {"state": "fresh", "snapshot_at": {"known": 1700000090000_u64}},
            "target": {"known": "thr_syn_0001"}
        },
        "items": records().into_iter().enumerate().map(|(i, request)| json!({
            "comment_id": 100 + i, "subject": {"repository":"synthetic-owner/synthetic-repo", "kind": if i < 2 {"pull_request"} else {"issue"}, "number": 901},
            "created_at": 1700000000000_u64, "updated_at": 1700000090000_u64,
            "current": {"known": true}, "request": request
        })).collect::<Vec<_>>()
    })
}

fn verdict(schema: &Value, value: &Value, good: bool, label: &str) {
    let errors = validate(schema, value);
    assert_eq!(errors.is_empty(), good, "{label}: {errors:#?}");
}

#[test]
fn plan_valid_partial_stale_and_empty_fixtures() {
    // Merged (CW4): the checker knows every keyword and refuses bad roots.
    checked_schema("plan", "openwiz.plan.v1");
    let schema = schema("plan");
    let good = plan();
    let building = building_plan();
    let mut partial = good.clone();
    partial["coverage"] = json!({"state": "partial", "gaps": [{"kind": "timed_out", "detail": "Synthetic unavailable prerequisites"}]});
    partial["tickets"][1]["blockers"] = json!({"unknown": "Synthetic incomplete read"});
    partial["tickets"][0]["dependents"] = json!({"unknown": "Synthetic incomplete read"});
    partial["critical_chain"] = json!({"unknown": "Synthetic incomplete graph"});
    let mut stale = good.clone();
    stale["freshness"] = json!({"state": "stale", "snapshot_at": {"known": 1700000000000_u64}});
    let mut empty = good.clone();
    empty["lanes"] = json!([]);
    empty["tickets"] = json!([]);
    empty["critical_chain"] = json!({"known": null});
    for (label, fixture) in [
        ("valid", good),
        ("building", building),
        ("partial", partial),
        ("stale", stale),
        ("empty", empty),
    ] {
        verdict(&schema, &fixture, true, label);
    }
}

fn building_plan() -> Value {
    let mut building = plan();
    building["tickets"][0]["state"] = json!({"known": "building"});
    building["tickets"][0]["column"] = json!({"known": "building"});
    building["tickets"][0]["pr"] = json!({"known": {"number": 950, "url": "https://github.com/synthetic-owner/synthetic-project/pull/950"}});
    building
}

#[test]
fn decisions_all_variants_lifecycle_risks_and_empty_responses() {
    // Merged (CW4): the checker knows every keyword and refuses bad roots.
    checked_schema("decisions", "openwiz.decisions.v1");
    let schema = schema("decisions");
    assert_eq!(records().len(), 4);
    for record in records() {
        for status in ["open", "resolved", "superseded"] {
            for risk in ["ordinary", "live", "release", "publish", "unknown"] {
                let mut fixture = record.clone();
                fixture["status"] = json!(status);
                fixture["risk"] = json!(risk);
                if fixture["kind"] == "grill_round" && status == "resolved" {
                    fixture["answered"] = json!(["G1"]);
                }
                verdict(&schema, &fixture, true, &format!("{status}/{risk}"));
            }
        }
    }
    let good = decisions();
    let mut stale = good.clone();
    stale["freshness"] = json!({"state": "stale", "snapshot_at": {"known": 1700000000000_u64}});
    stale["items"][0]["current"] = json!({"known": false});
    let mut partial = good.clone();
    partial["coverage"] = json!({"state": "partial", "gaps": [{"kind": "malformed", "detail": "Synthetic malformed record omitted"}]});
    partial["items"][0]["current"] = json!({"unknown": "Synthetic fingerprint not checked"});
    let mut empty = good.clone();
    empty["items"] = json!([]);
    empty["orchestrator"]["target"] = json!({"known": null});
    for (label, fixture) in [
        ("valid", good),
        ("stale", stale),
        ("partial", partial),
        ("empty", empty),
    ] {
        verdict(&schema, &fixture, true, label);
    }
}

#[test]
fn plan_and_decisions_malformed_literals_fail() {
    for (name, good, mutations) in [
        (
            "plan",
            plan(),
            vec![
                ("/schema", json!("openwiz.plan.v2")),
                ("/snapshot_at", json!(-1)),
                ("/snapshot_at", json!(1.5)),
                ("/lanes/0/kind", json!("milestone")),
                ("/lanes/0/number", json!(0)),
                ("/tickets/0/title", json!("Synthetic title")),
                ("/tickets/0/title", json!({"known": ""})),
                ("/tickets/0/state", json!({"known": "done"})),
                ("/tickets/0/state", json!({"known": {"ready": null}})),
                ("/tickets/0/column", json!({"known": "yours"})),
                ("/tickets/0/yours", json!(true)),
                ("/tickets/0/labels", json!({"known": ["held", "held"]})),
                ("/tickets/1/blockers", json!({"known": [902, 902]})),
                (
                    "/critical_chain",
                    json!({"known": {"root": 902, "blocked_count": -1, "path": []}}),
                ),
                (
                    "/freshness",
                    json!({"state": "fresh", "snapshot_at": {"unknown": "Synthetic absent time"}}),
                ),
                ("/coverage", json!({"state": "partial", "gaps": []})),
                (
                    "/coverage/gaps",
                    json!([{"kind": "timed_out", "detail": "Synthetic gap"}]),
                ),
            ],
        ),
        (
            "decisions",
            decisions(),
            vec![
                ("/kind", json!("open")),
                ("/items/0/comment_id", json!(0)),
                ("/items/0/request/kind", json!({"grill_round": null})),
                ("/items/0/request/status", json!("resolved")),
                ("/items/0/request/risk", json!(false)),
                ("/items/0/request/fingerprint", json!("a".repeat(63))),
                ("/items/0/request/fingerprint", json!("a".repeat(65))),
                ("/items/0/request/fingerprint", json!("g".repeat(64))),
                ("/items/0/request/grill_file", json!("../synthetic.md")),
                ("/items/0/request/round", json!(0)),
                ("/items/0/request/questions", json!([])),
                ("/items/0/request/questions/0/context", json!("")),
                ("/items/0/request/answered", json!(["G1", "G1"])),
                ("/items/1/request/summary", json!([])),
                (
                    "/items/1/request/summary",
                    json!(["Synthetic line\nAnother line"]),
                ),
                (
                    "/items/2/request/tickets",
                    json!([{"number": 902, "title": "Synthetic ticket", "blockers": []}]),
                ),
                ("/items/3/request/spec", json!("901")),
                ("/orchestrator/target", json!({"known": "-bad"})),
                ("/orchestrator/target", json!({"known": "thr_\u{00e9}"})),
            ],
        ),
    ] {
        let schema = schema(name);
        for (pointer, replacement) in mutations {
            let mut bad = good.clone();
            *bad.pointer_mut(pointer).expect(pointer) = replacement;
            verdict(&schema, &bad, false, pointer);
        }
    }

    let schema = schema("plan");
    for (good, pointer, urls) in [
        (
            plan(),
            "/tickets/0/url/known",
            [
                "http://github.com/synthetic-owner/synthetic-project/issues/902",
                "https://example.test/synthetic-owner/synthetic-project/issues/902",
                "https://user@github.com/synthetic-owner/synthetic-project/issues/902",
                "https://github.com/synthetic-owner/synthetic-project/issues/902?q",
                "https://github.com/synthetic-owner/synthetic-project/issues/902#frag",
                "https://github.com/synthetic-owner/synthetic-project/../issues/902",
                "https://github.com/synthetic-owner/synthetic-project/pull/902",
                "https://github.com/synthetic-owner/synthetic-project/issues/0",
                "https://github.com/synthetic-owner/synthetic-project/issues/0902",
                "https://github.com/synthetic-owner/synthetic-project/issues/902/extra",
            ],
        ),
        (
            building_plan(),
            "/tickets/0/pr/known/url",
            [
                "http://github.com/synthetic-owner/synthetic-project/pull/950",
                "https://example.test/synthetic-owner/synthetic-project/pull/950",
                "https://user@github.com/synthetic-owner/synthetic-project/pull/950",
                "https://github.com/synthetic-owner/synthetic-project/pull/950?q",
                "https://github.com/synthetic-owner/synthetic-project/pull/950#frag",
                "https://github.com/synthetic-owner/synthetic-project/../pull/950",
                "https://github.com/synthetic-owner/synthetic-project/issues/950",
                "https://github.com/synthetic-owner/synthetic-project/pull/0",
                "https://github.com/synthetic-owner/synthetic-project/pull/0950",
                "https://github.com/synthetic-owner/synthetic-project/pull/950/extra",
            ],
        ),
    ] {
        verdict(&schema, &good, true, pointer);
        for url in urls {
            let mut bad = good.clone();
            *bad.pointer_mut(pointer).expect(pointer) = json!(url);
            let errors = validate(&schema, &bad);
            assert_eq!(errors.len(), 1, "{pointer}: {url}: {errors:#?}");
            assert!(
                errors[0].contains("does not match"),
                "{pointer}: {url}: {errors:#?}"
            );
        }
    }
}

#[test]
fn decisions_three_questions_and_ten_summary_lines_are_schema_bounds() {
    let schema = schema("decisions");
    let mut record = records().remove(0);
    let first = record["questions"][0].clone();
    record["questions"] = json!([first.clone(), {"id": "G2", "decides": "Synthetic second choice", "context": "Synthetic context", "recommendation": "Use it."}, {"id": "G3", "decides": "Synthetic third choice", "context": "Synthetic context", "recommendation": "Use it."}]);
    verdict(&schema, &record, true, "three questions");
    record["questions"].as_array_mut().unwrap().push(first);
    verdict(&schema, &record, false, "four questions");
    for mut summary in records().into_iter().skip(1) {
        let kind = summary["kind"].as_str().unwrap().to_owned();
        summary["summary"] = json!(vec!["Synthetic summary line."; 10]);
        verdict(&schema, &summary, true, &format!("ten lines for {kind}"));
        summary["summary"] = json!(vec!["Synthetic summary line."; 11]);
        verdict(
            &schema,
            &summary,
            false,
            &format!("eleven lines for {kind}"),
        );
    }
}

fn object_paths(value: &Value, path: &str, out: &mut Vec<String>) {
    match value {
        Value::Object(object) => {
            out.push(path.to_owned());
            for (key, child) in object {
                object_paths(child, &format!("{path}/{key}"), out);
            }
        }
        Value::Array(items) => {
            for (i, child) in items.iter().enumerate() {
                object_paths(child, &format!("{path}/{i}"), out);
            }
        }
        _ => {}
    }
}

#[test]
fn every_fixture_object_refuses_missing_extra_and_positional_keys() {
    for (name, fixtures) in [
        ("plan", vec![plan()]),
        ("decisions", {
            let mut fixtures = records();
            fixtures.push(decisions());
            fixtures
        }),
    ] {
        let schema = schema(name);
        for fixture in fixtures {
            verdict(&schema, &fixture, true, "unmodified fixture");
            let mut paths = vec![];
            object_paths(&fixture, "", &mut paths);
            for path in paths {
                let mut extra = fixture.clone();
                extra
                    .pointer_mut(&path)
                    .unwrap()
                    .as_object_mut()
                    .unwrap()
                    .insert("synthetic_extra".into(), json!(true));
                verdict(&schema, &extra, false, &format!("extra at {path}"));
                let mut positional = fixture.clone();
                *positional.pointer_mut(&path).unwrap() = json!([]);
                verdict(
                    &schema,
                    &positional,
                    false,
                    &format!("positional at {path}"),
                );
                for key in fixture.pointer(&path).unwrap().as_object().unwrap().keys() {
                    let mut missing = fixture.clone();
                    missing
                        .pointer_mut(&path)
                        .unwrap()
                        .as_object_mut()
                        .unwrap()
                        .remove(key);
                    verdict(&schema, &missing, false, &format!("missing {path}/{key}"));
                }
            }
        }
    }
}
