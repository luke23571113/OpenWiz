//! The plan links contract, v1 (#1315, U1 of spec #1313): every fixture in
//! `skills/plan-graph/test/links/` validates against
//! `contracts/plan-links.v1.schema.json`, has its expected checker report and
//! board numbers beside it, and each expectation agrees with its graph read
//! by the contract's cross-record rules and definitions. Planted invalid
//! fixtures are refused. U4 (#1318): the link checker,
//! `skills/plan-graph/check-links.sh`, gives each fixture's expected reports
//! exactly, refuses each planted reason line, refuses a bad graph read, and
//! reads a spec through a fake `gh`, refusing a failed or partial read.

use serde_json::{Value, json};
use std::collections::BTreeSet;
use std::fs;
use std::io::Write;
use std::os::unix::fs::symlink;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

const ROOT: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/..");
const FIXTURES: &str = "skills/plan-graph/test/links";
const CASE_FILES: [&str; 5] = [
    "board.json",
    "graph.json",
    "report.json",
    "report.txt",
    "stderr.txt",
];

fn path(relative: &str) -> PathBuf {
    Path::new(ROOT).join(relative)
}

fn text(at: &Path) -> String {
    fs::read_to_string(at).unwrap_or_else(|e| panic!("{}: {e}", at.display()))
}

fn json_file(at: &Path) -> Value {
    serde_json::from_str(&text(at)).unwrap_or_else(|e| panic!("{}: {e}", at.display()))
}

fn schema() -> Value {
    json_file(&path("contracts/plan-links.v1.schema.json"))
}

fn errors(value: &Value) -> Vec<String> {
    crate::pattern::validate(&schema(), value)
}

fn assert_valid(value: &Value, kind: &str, at: &str) {
    assert_eq!(value["kind"], kind, "{at}: kind");
    assert_eq!(errors(value), Vec::<String>::new(), "{at}");
}

/// Each case folder, by name.
fn cases() -> Vec<(String, PathBuf)> {
    let mut out: Vec<_> = fs::read_dir(path(FIXTURES))
        .expect("the fixtures folder")
        .map(|e| e.expect("entry"))
        .filter(|e| e.file_type().expect("type").is_dir() && e.file_name() != "history")
        .map(|e| (e.file_name().to_string_lossy().into_owned(), e.path()))
        .collect();
    out.sort();
    out
}

fn history(name: &str) -> Vec<Value> {
    let at = path(&format!("{FIXTURES}/history/{name}"));
    text(&at)
        .lines()
        .map(|line| serde_json::from_str(line).unwrap_or_else(|e| panic!("{name}: {e}")))
        .collect()
}

#[test]
fn plan_links_every_fixture_has_its_expectations_and_validates() {
    // Merged (CW4): the checker knows every keyword and refuses bad roots.
    let schema = schema();
    assert_eq!(schema["title"], "openwiz.plan-links.v1");
    assert_eq!(crate::pattern::lint(&schema), Vec::<String>::new());
    for malformed in [
        json!(null),
        json!([]),
        json!({}),
        json!("Synthetic"),
        json!({"schema": "openwiz.plan-links.v1", "kind": "synthetic"}),
    ] {
        assert!(!errors(&malformed).is_empty(), "{malformed}");
    }
    let mut top: Vec<String> = fs::read_dir(path(FIXTURES))
        .expect("the fixtures folder")
        .map(|e| e.expect("entry").file_name().to_string_lossy().into_owned())
        .collect();
    top.sort();
    for name in &top {
        let at = path(&format!("{FIXTURES}/{name}"));
        assert!(
            name == "README.md" || at.is_dir(),
            "{FIXTURES}/{name}: only README.md and case folders belong here"
        );
    }
    let mut codes = BTreeSet::new();
    let mut low = false;
    for (name, dir) in cases() {
        let mut files: Vec<String> = fs::read_dir(&dir)
            .expect("case folder")
            .map(|e| e.expect("entry").file_name().to_string_lossy().into_owned())
            .collect();
        files.sort();
        assert_eq!(
            files, CASE_FILES,
            "{name}: a graph read and its expectations"
        );
        assert_valid(&json_file(&dir.join("graph.json")), "graph", &name);
        let report = json_file(&dir.join("report.json"));
        assert_valid(&report, "report", &name);
        let board = json_file(&dir.join("board.json"));
        assert_valid(&board, "measures", &name);
        codes.extend(
            report["refusals"]
                .as_array()
                .unwrap()
                .iter()
                .map(|r| r["code"].as_str().unwrap().to_owned()),
        );
        low |= board["low_stock"] == true;
    }
    for name in ["history.jsonl", "daily.jsonl"] {
        for (i, row) in history(name).iter().enumerate() {
            assert_valid(row, "history", &format!("history/{name} line {}", i + 1));
        }
    }
    // The ticket's coverage: each refusal, and a low-stock board.
    let every = [
        "duplicate",
        "file_without_file",
        "malformed",
        "no_reason",
        "not_a_blocker",
        "real_without_behaviour",
    ];
    assert_eq!(codes, every.iter().map(|c| c.to_string()).collect());
    assert!(low, "a low-stock board");
    for case in [
        "clean-wide",
        "real-and-file",
        "external-blockers",
        "closed-blocker",
        "low-stock",
        "this-spec",
    ] {
        assert!(path(&format!("{FIXTURES}/{case}")).is_dir(), "{case}");
    }
}

/// A planted change to a valid fixture: what it breaks, the fixture, the change.
type Planted = (&'static str, Value, fn(&mut Value));

#[test]
fn plan_links_planted_invalid_fixtures_are_refused() {
    let dir = path(&format!("{FIXTURES}/real-and-file"));
    let graph = json_file(&dir.join("graph.json"));
    let report = json_file(&dir.join("report.json"));
    let board = json_file(&dir.join("board.json"));
    let rows = history("history.jsonl");
    let planted: Vec<Planted> = vec![
        ("ticket state", graph.clone(), |v| {
            v["tickets"][0]["state"] = json!("MERGED")
        }),
        ("blocker without state", graph.clone(), |v| {
            v["tickets"][2]["blocked_by"][0] = json!({"number": 9001})
        }),
        ("extra ticket key", graph.clone(), |v| {
            v["tickets"][0]["comments"] = json!([])
        }),
        ("repo", graph.clone(), |v| v["repo"] = json!("synthetic")),
        ("read_at", graph.clone(), |v| {
            v["read_at"] = json!("2026-11-05 23:50")
        }),
        ("labels twice", graph.clone(), |v| {
            v["tickets"][0]["labels"] = json!(["held", "held"])
        }),
        ("source", graph.clone(), |v| {
            v["source"] = json!({"kind": "spec"})
        }),
        ("link kind", report.clone(), |v| {
            v["links"][0]["kind"] = json!("soft")
        }),
        ("file link without files", report.clone(), |v| {
            v["links"][1]["files"] = json!([])
        }),
        ("real link with files", report.clone(), |v| {
            v["links"][0]["files"] = json!(["synthetic/a.md"])
        }),
        ("result", report.clone(), |v| v["result"] = json!("ok")),
        (
            "refusal code",
            report.clone(),
            |v| {
                v["refusals"] = json!([{"ticket": 9003, "number": 9001, "code": "soft", "message": "Synthetic"}])
            },
        ),
        ("malformed with a number", report.clone(), |v| {
            v["refusals"] = json!([{"ticket": 9003, "number": 9001, "code": "malformed",
                "message": "malformed section: no lines"}])
        }),
        ("negative count", board.clone(), |v| {
            v["ready_stock"] = json!(-1)
        }),
        ("ratio as text", board.clone(), |v| {
            v["fed_ratio"] = json!("3.0")
        }),
        ("no flag", board.clone(), |v| {
            v.as_object_mut().unwrap().remove("low_stock");
        }),
        ("run row not measured", rows[1].clone(), |v| {
            v["file_links"] = Value::Null
        }),
        ("baseline row measured", rows[0].clone(), |v| {
            v["ready_stock"] = json!(1)
        }),
        ("day with a time", rows[1].clone(), |v| {
            v["day"] = json!("2026-11-06T00:00:00Z")
        }),
    ];
    for (what, mut value, plant) in planted {
        assert!(errors(&value).is_empty(), "{what}: valid before planting");
        plant(&mut value);
        assert!(!errors(&value).is_empty(), "{what}: must be refused");
    }
}

// The link checker (U4, #1318).

const CHECKER: &str = "skills/plan-graph/check-links.sh";

/// A fresh, empty folder for one test, outside every other test's.
fn scratch(name: &str) -> PathBuf {
    let dir = Path::new(env!("CARGO_TARGET_TMPDIR"))
        .join("plan-links")
        .join(name);
    let _ = fs::remove_dir_all(&dir);
    crate::dirs::private_dir_all(&dir).expect("scratch folder");
    dir
}

/// A fake `gh` that answers only `gh api graphql` reads, from the pages in
/// `$FAKE_GH_DIR`: `<issues|prs>-<cursor or first>.json`, and an exit status
/// in `.code` beside it; and the one raw read of `docs/agents/fleet.md`
/// (#717), from `fleet.md` and `fleet.code`. It logs every call, any other call exits 91, and
/// it answers no more than 50 calls (exit 92), so a looping reader stops.
/// Shell builtins only, so the checker's `PATH` holds nothing else.
const FAKE_GH: &str = r#"#!/bin/sh
printf '%s\n' "$*" >> "$FAKE_GH_DIR/calls"
calls=0
while IFS= read -r line; do calls=$((calls + 1)); done < "$FAKE_GH_DIR/calls"
[ "$calls" -le 50 ] || exit 92
if [ "$#" -eq 4 ] && [ "$1" = api ] && [ "$2" = -H ] && [ "$3" = 'Accept: application/vnd.github.raw+json' ] \
  && [ "$4" = 'repos/{owner}/{repo}/contents/docs/agents/fleet.md' ]; then
  page="$FAKE_GH_DIR/fleet"
  while IFS= read -r line || [ -n "$line" ]; do printf '%s\n' "$line"; done < "$page.md"
  code=0
  [ ! -f "$page.code" ] || read -r code < "$page.code"
  exit "$code"
fi
[ "$1 $2" = "api graphql" ] || exit 91
shift 2
kind='' after=first
for arg do
  case $arg in
    -X | --method | --input | --paginate | *mutation*) exit 91 ;;
    query=*subIssues*) kind=issues ;;
    query=*pullRequests*) kind=prs ;;
    after=*) after=${arg#after=} ;;
  esac
done
page="$FAKE_GH_DIR/$kind-$after"
[ -n "$kind" ] && [ -f "$page.json" ] || exit 91
while IFS= read -r line || [ -n "$line" ]; do printf '%s\n' "$line"; done < "$page.json"
code=0
[ ! -f "$page.code" ] || read -r code < "$page.code"
exit "$code"
"#;

/// The checker's tools: `sh`, `jq` and `date` from `PATH`, and the fake `gh`.
fn tools(dir: &Path) -> PathBuf {
    let tools = dir.join("tools");
    crate::dirs::private_dir_all(&tools).expect("tools");
    for name in ["sh", "jq", "date"] {
        let program = std::env::split_paths(&std::env::var_os("PATH").expect("PATH"))
            .map(|d| d.join(name))
            .find(|p| p.is_file())
            .unwrap_or_else(|| panic!("{name} on PATH"));
        symlink(program, tools.join(name)).expect("tool link");
    }
    crate::place::place_script(&tools.join("gh"), FAKE_GH);
    tools
}

struct Run {
    code: Option<i32>,
    stdout: String,
    stderr: String,
}

/// Runs the checker in `dir/work`, with `dir/tmp` as `TMPDIR` and the fake
/// `gh` reading `dir/gh`.
fn check(dir: &Path, args: &[&str], stdin: &str) -> Run {
    let mut child = Command::new("sh")
        .arg(path(CHECKER))
        .args(args)
        .env_clear()
        .env("PATH", dir.join("tools"))
        .env("TMPDIR", dir.join("tmp"))
        .env("HOME", dir.join("tmp"))
        .env("FAKE_GH_DIR", dir.join("gh"))
        .current_dir(dir.join("work"))
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("run the checker");
    // The checker may refuse its arguments before it reads standard input.
    let _ = child
        .stdin
        .take()
        .expect("stdin")
        .write_all(stdin.as_bytes());
    let out = child.wait_with_output().expect("checker result");
    Run {
        code: out.status.code(),
        stdout: String::from_utf8(out.stdout).expect("UTF-8 stdout"),
        stderr: String::from_utf8(out.stderr).expect("UTF-8 stderr"),
    }
}

/// A test's folder: tools, an empty working folder, `TMPDIR` and `gh` pages.
fn bench(name: &str) -> PathBuf {
    let dir = scratch(name);
    tools(&dir);
    for sub in ["work", "tmp", "gh"] {
        crate::dirs::private_dir_all(dir.join(sub)).expect("bench folder");
    }
    dir
}

fn empty(dir: &Path) -> bool {
    fs::read_dir(dir).expect("folder").next().is_none()
}

/// No `gh` call, and nothing written in the working folder or `TMPDIR`.
fn assert_quiet(dir: &Path, what: &str) {
    assert!(empty(&dir.join("gh")), "{what}: no gh call");
    assert!(empty(&dir.join("work")), "{what}: writes nothing");
    assert!(empty(&dir.join("tmp")), "{what}: writes nothing");
}

#[test]
fn plan_links_checker_gives_every_fixtures_reports_exactly() {
    let dir = bench("fixtures");
    for (name, case) in cases() {
        let graph = text(&case.join("graph.json"));
        let want_err = text(&case.join("stderr.txt"));
        let want_code = Some(if want_err.is_empty() { 0 } else { 1 });

        let run = check(&dir, &["--graph", "-"], &graph);
        assert_eq!(run.code, want_code, "{name}: exit; stderr: {}", run.stderr);
        assert_eq!(run.stdout, text(&case.join("report.txt")), "{name}: text");
        assert_eq!(run.stderr, want_err, "{name}: stderr");

        let run = check(&dir, &["--json", "--graph", "-"], &graph);
        assert_eq!(run.code, want_code, "{name}: exit; stderr: {}", run.stderr);
        let report: Value = serde_json::from_str(&run.stdout)
            .unwrap_or_else(|e| panic!("{name}: JSON report: {e}: {}", run.stdout));
        assert_eq!(report, json_file(&case.join("report.json")), "{name}: JSON");
        assert_eq!(run.stdout, text(&case.join("report.json")), "{name}: bytes");
        assert_eq!(run.stderr, want_err, "{name}: stderr");
        assert_quiet(&dir, &name);
    }
}

/// One planted reason line on #9002, blocked by #9001: the link's kind and
/// files in the JSON report, and standard error (empty on a pass).
type PlantedLine = (
    &'static str,
    &'static str,
    &'static str,
    &'static [&'static str],
    &'static str,
);

#[test]
fn plan_links_checker_reads_each_reason_line_by_the_contract() {
    const NO_REASON: &str = "Links: #9002: #9001 has no reason line\n";
    const NOT_LINK: &str = "Links: #9002: malformed section: a line is not a link line or none\n";
    const NO_BEHAVIOUR: &str = "Links: #9002: the real line for #9001 names no behaviour\n";
    const NO_FILE: &str = "Links: #9002: the file line for #9001 names no file in backticks\n";
    let cases: Vec<PlantedLine> = vec![
        (
            "crlf and trailing blanks",
            "## Links \t\r\n\r\n- #9001 real: the synthetic contract's form \t\r\n",
            "real",
            &[],
            "",
        ),
        (
            "fenced heading is not a section",
            "```md\n## Links\n\n- #9001 real: needs the synthetic form\n```\n",
            "unlabelled",
            &[],
            NO_REASON,
        ),
        (
            "tilde fence, then the section",
            "~~~~\n## Links\n~~~~\n\n## Links\n\n- #9001 real: needs the synthetic form\n",
            "real",
            &[],
            "",
        ),
        (
            "a short fence line does not close",
            "````\n```\n## Links\n````\n\n## Links\n\n- #9001 real: needs the synthetic form\n",
            "real",
            &[],
            "",
        ),
        (
            "commented heading, then the section",
            "<!--\n## Links\n-->\n## Links\n\n- #9001 real: needs the synthetic form\n",
            "real",
            &[],
            "",
        ),
        (
            "heading inside a comment",
            "<!-- planned\n## Links\n- #9001 real: needs the synthetic form\nlater -->\n",
            "unlabelled",
            &[],
            NO_REASON,
        ),
        (
            "another level",
            "### Links\n\n- #9001 real: needs the synthetic form\n",
            "unlabelled",
            &[],
            NO_REASON,
        ),
        (
            "other words on the line",
            "## Links here\n\n- #9001 real: needs the synthetic form\n",
            "unlabelled",
            &[],
            NO_REASON,
        ),
        (
            "ends at the next heading",
            "## Links\n\n- #9001 real: needs the synthetic form\n## Acceptance criteria\n\n- [ ] Synthetic.\n",
            "real",
            &[],
            "",
        ),
        (
            "ends at a bare #",
            "## Links\n\n- #9001 real: needs the synthetic form\n#\nSynthetic prose.\n",
            "real",
            &[],
            "",
        ),
        (
            "an indented line",
            "## Links\n\n  - #9001 real: needs the synthetic form\n",
            "unlabelled",
            &[],
            NOT_LINK,
        ),
        (
            "an uppercase kind",
            "## Links\n\n- #9001 Real: needs the synthetic form\n",
            "unlabelled",
            &[],
            NOT_LINK,
        ),
        (
            "a leading zero",
            "## Links\n\n- #09001 real: needs the synthetic form\n",
            "unlabelled",
            &[],
            NOT_LINK,
        ),
        (
            "no space before the kind",
            "## Links\n\n- #9001real: needs the synthetic form\n",
            "unlabelled",
            &[],
            NOT_LINK,
        ),
        (
            "a fence inside the section",
            "## Links\n\n```\n- #9001 real: needs the synthetic form\n```\n",
            "unlabelled",
            &[],
            NOT_LINK,
        ),
        (
            "none twice",
            "## Links\n\nnone\nnone\n",
            "unlabelled",
            &[],
            "Links: #9002: malformed section: none must be the only line\n",
        ),
        (
            "no lines before the next heading",
            "## Links\n\n\n## Acceptance criteria\n",
            "unlabelled",
            &[],
            "Links: #9002: malformed section: no lines\n",
        ),
        (
            "no space after the colon",
            "## Links\n\n- #9001 real:needs the synthetic form\n",
            "real",
            &[],
            "",
        ),
        (
            "words around a path",
            "## Links\n\n- #9001 real: reads `contracts/plan-links.v1.md`, checker's measures'\n",
            "real",
            &[],
            "",
        ),
        (
            "a path and a span are not words",
            "## Links\n\n- #9001 real: `the synthetic form` contracts/plan-links.v1.md (x)\n",
            "unlabelled",
            &[],
            NO_BEHAVIOUR,
        ),
        (
            "punctuation is stripped",
            "## Links\n\n- #9001 real: (needs), [the] \"form\"!\n",
            "real",
            &[],
            "",
        ),
        (
            "numbers are not words",
            "## Links\n\n- #9001 real: needs 2 forms\n",
            "unlabelled",
            &[],
            NO_BEHAVIOUR,
        ),
        (
            "an empty real reason",
            "## Links\n\n- #9001 real:\n",
            "unlabelled",
            &[],
            NO_BEHAVIOUR,
        ),
        (
            "a folder",
            "## Links\n\n- #9001 file: `docs/agents/`\n",
            "file",
            &["docs/agents/"],
            "",
        ),
        (
            "files once each, other spans kept out",
            "## Links\n\n- #9001 file: `STATUS.md` and `STATUS.md`, `not a path`, `docs/a.md`\n",
            "file",
            &["STATUS.md", "docs/a.md"],
            "",
        ),
        (
            "a dot segment",
            "## Links\n\n- #9001 file: `./STATUS.md`\n",
            "unlabelled",
            &[],
            NO_FILE,
        ),
        (
            "a parent segment",
            "## Links\n\n- #9001 file: `docs/../STATUS.md`\n",
            "unlabelled",
            &[],
            NO_FILE,
        ),
        (
            "an absolute path",
            "## Links\n\n- #9001 file: `/etc/synthetic`\n",
            "unlabelled",
            &[],
            NO_FILE,
        ),
        (
            "an empty segment",
            "## Links\n\n- #9001 file: `docs//a.md`\n",
            "unlabelled",
            &[],
            NO_FILE,
        ),
        (
            "a pattern",
            "## Links\n\n- #9001 file: `docs/*.md`\n",
            "unlabelled",
            &[],
            NO_FILE,
        ),
        (
            "an unpaired backtick",
            "## Links\n\n- #9001 file: `STATUS.md\n",
            "unlabelled",
            &[],
            NO_FILE,
        ),
        (
            "a number named twice, refused once",
            "## Links\n\n- #9001 real: needs the synthetic form\n- #9005 real: needs another form\n- #9005 file: `a.md`\n",
            "real",
            &[],
            "Links: #9002: #9005 is not a native blocker\n",
        ),
        (
            "refusals by number",
            "## Links\n\n- #9001 real: needs the synthetic form\n- #9001 file: `a.md`\n- #9000 real: needs the spec itself\n",
            "unlabelled",
            &[],
            "Links: #9002: #9000 is not a native blocker\nLinks: #9002: #9001 has more than one line\n",
        ),
    ];
    let base = json_file(&path(&format!("{FIXTURES}/clean-wide/graph.json")));
    let dir = bench("reason-lines");
    for (what, body, kind, files, err) in cases {
        let mut graph = base.clone();
        graph["tickets"] = json!([
            {"number": 9001, "title": "Synthetic ticket 9001", "state": "OPEN",
             "labels": ["ready-for-agent"], "milestone": null, "parent": 9000,
             "blocked_by": [], "body": "## Links\n\nnone\n",
             "start_recorded": false, "pull_requests": []},
            {"number": 9002, "title": "Synthetic ticket 9002", "state": "OPEN",
             "labels": ["ready-for-agent"], "milestone": null, "parent": 9000,
             "blocked_by": [{"number": 9001, "state": "OPEN"}],
             "body": format!("## Owned paths\n\n- `synthetic/9002.md`\n\n{body}"),
             "start_recorded": false, "pull_requests": []},
        ]);
        let run = check(&dir, &["--json", "--graph", "-"], &graph.to_string());
        let want = Some(if err.is_empty() { 0 } else { 1 });
        assert_eq!(run.code, want, "{what}: exit; stderr: {}", run.stderr);
        assert_eq!(run.stderr, err, "{what}: stderr");
        let report: Value = serde_json::from_str(&run.stdout)
            .unwrap_or_else(|e| panic!("{what}: JSON report: {e}: {}", run.stdout));
        assert_eq!(
            report["links"],
            json!([{"ticket": 9002, "blocker": 9001, "blocker_state": "OPEN",
                    "kind": kind, "files": files}]),
            "{what}: the link"
        );
        assert_eq!(
            report["result"],
            if err.is_empty() { "pass" } else { "refused" }
        );
        assert_valid(&report, "report", what);
        assert_quiet(&dir, what);
    }
}

/// Exit 2, nothing on standard output, one line on standard error.
fn assert_refused_read(run: &Run, what: &str) {
    assert_eq!(run.code, Some(2), "{what}: exit; stderr: {}", run.stderr);
    assert_eq!(run.stdout, "", "{what}: stdout");
    assert!(
        run.stderr.starts_with("check-links: ")
            && run.stderr.ends_with('\n')
            && run.stderr.matches('\n').count() == 1,
        "{what}: one line on stderr: {:?}",
        run.stderr
    );
}

#[test]
fn plan_links_checker_refuses_bad_arguments_and_graph_reads() {
    let dir = bench("bad-reads");
    let good = text(&path(&format!("{FIXTURES}/clean-wide/graph.json")));
    let base: Value = serde_json::from_str(&good).expect("JSON");
    let run = check(&dir, &["--graph", "-"], &good);
    assert_eq!(run.code, Some(0), "the base graph passes: {}", run.stderr);

    for args in [
        &[][..],
        &["--graph"],
        &["--graph", "x"],
        &["--graph", "-", "9000"],
        &["9000", "--graph", "-"],
        &["9000", "9001"],
        &["09000"],
        &["0"],
        &["-1"],
        &["9a"],
        &["--json", "--json", "--graph", "-"],
        &["--graph", "-", "--graph", "-"],
        &["--bogus", "--graph", "-"],
        &[""],
    ] {
        let run = check(&dir, args, &good);
        assert_refused_read(&run, &format!("arguments {args:?}"));
        assert_quiet(&dir, &format!("arguments {args:?}"));
    }

    let edit = |plant: fn(&mut Value)| {
        let mut v = base.clone();
        plant(&mut v);
        v.to_string()
    };
    let reads: Vec<(&str, String)> = vec![
        ("empty", String::new()),
        ("not JSON", "Synthetic\n".to_owned()),
        ("truncated", good[..good.len() / 2].to_owned()),
        ("two values", format!("{good}{good}")),
        ("an array", "[]".to_owned()),
        (
            "a report",
            text(&path(&format!("{FIXTURES}/clean-wide/report.json"))),
        ),
        (
            "a repeated key",
            good.replacen('{', "{\"kind\": \"graph\",", 1),
        ),
        (
            "a repeated ticket key",
            good.replacen("\"title\"", "\"title\": \"Synthetic\", \"title\"", 1),
        ),
        ("an extra key", edit(|v| v["extra"] = json!(1))),
        (
            "another schema",
            edit(|v| v["schema"] = json!("openwiz.plan-links.v2")),
        ),
        ("a bad repo", edit(|v| v["repo"] = json!("synthetic"))),
        (
            "a bad time",
            edit(|v| v["read_at"] = json!("2026-11-05 23:50")),
        ),
        (
            "a source without its spec",
            edit(|v| v["source"] = json!({"kind": "spec"})),
        ),
        (
            "a board source with a spec",
            edit(|v| v["source"] = json!({"kind": "board", "spec": 1})),
        ),
        ("tickets not a list", edit(|v| v["tickets"] = json!({}))),
        (
            "a ticket twice",
            edit(|v| {
                let t = v["tickets"][0].clone();
                v["tickets"].as_array_mut().unwrap().push(t)
            }),
        ),
        (
            "a blocker twice",
            edit(|v| {
                v["tickets"][1]["blocked_by"] =
                    json!([{"number": 9001, "state": "OPEN"}, {"number": 9001, "state": "CLOSED"}])
            }),
        ),
        (
            "a missing ticket key",
            edit(|v| {
                v["tickets"][0].as_object_mut().unwrap().remove("body");
            }),
        ),
        (
            "an extra ticket key",
            edit(|v| v["tickets"][0]["comments"] = json!([])),
        ),
        (
            "number zero",
            edit(|v| v["tickets"][0]["number"] = json!(0)),
        ),
        (
            "a fractional number",
            edit(|v| v["tickets"][0]["number"] = json!(9001.5)),
        ),
        (
            "a number as text",
            edit(|v| v["tickets"][0]["number"] = json!("9001")),
        ),
        (
            "an empty title",
            edit(|v| v["tickets"][0]["title"] = json!("")),
        ),
        (
            "a merged state",
            edit(|v| v["tickets"][0]["state"] = json!("MERGED")),
        ),
        (
            "a label twice",
            edit(|v| v["tickets"][0]["labels"] = json!(["held", "held"])),
        ),
        (
            "an empty label",
            edit(|v| v["tickets"][0]["labels"] = json!([""])),
        ),
        (
            "an empty milestone",
            edit(|v| v["tickets"][0]["milestone"] = json!("")),
        ),
        (
            "a parent of zero",
            edit(|v| v["tickets"][0]["parent"] = json!(0)),
        ),
        (
            "a blocker without state",
            edit(|v| v["tickets"][1]["blocked_by"] = json!([{"number": 9001}])),
        ),
        (
            "a body of null",
            edit(|v| v["tickets"][0]["body"] = Value::Null),
        ),
        (
            "a start as text",
            edit(|v| v["tickets"][0]["start_recorded"] = json!("false")),
        ),
        (
            "a pull request twice",
            edit(|v| v["tickets"][0]["pull_requests"] = json!([9101, 9101])),
        ),
    ];
    for (what, input) in reads {
        let run = check(&dir, &["--graph", "-"], &input);
        assert_refused_read(&run, what);
        let run = check(&dir, &["--json", "--graph", "-"], &input);
        assert_refused_read(&run, what);
        assert_quiet(&dir, what);
    }
}

/// One sub-issue as GitHub's GraphQL API gives it.
fn gh_issue(number: u64, state: &str, blocked: &[(u64, &str)], body: &str, comment: &str) -> Value {
    json!({
        "number": number, "title": format!("Synthetic ticket {number}"), "state": state,
        "body": body,
        "labels": {"totalCount": 1, "nodes": [{"name": "ready-for-agent"}]},
        "milestone": {"title": "Synthetic"}, "parent": {"number": 9000},
        "blockedBy": {"totalCount": blocked.len(),
            "nodes": blocked.iter().map(|(n, s)| json!({"number": n, "state": s})).collect::<Vec<_>>()},
        "comments": {"nodes": [{"body": comment}]},
    })
}

fn gh_issues(total: u64, next: Option<&str>, nodes: Vec<Value>) -> Value {
    json!({"data": {"repository": {"nameWithOwner": "synthetic-owner/synthetic-repo",
        "issue": {"subIssues": {"totalCount": total,
            "pageInfo": {"hasNextPage": next.is_some(), "endCursor": next},
            "nodes": nodes}}}}})
}

/// The factory's identity: the Record authors row launch-fleet reads (#717).
const FLEET: &str = "# Fleet settings\n\n## GitHub identity\n\n| Setting | Value |\n| --- | --- |\n\
    | Record authors | `openwiz[bot]`, `synthetic-owner` |\n\n## Standing merge rules\n";

/// Spec #9000's sub-issues on two pages, and its open pull requests.
fn gh_pages(dir: &Path) {
    let pages = dir.join("gh");
    let _ = fs::remove_dir_all(&pages);
    crate::dirs::private_dir_all(&pages).expect("gh pages");
    let first = gh_issues(
        3,
        Some("Y3Vyc29yOjI="),
        vec![
            gh_issue(9001, "OPEN", &[], "## Links\n\nnone\n", "Synthetic note"),
            gh_issue(
                9002,
                "OPEN",
                &[(9001, "OPEN"), (8999, "CLOSED")],
                "## Links\n\n- #9001 real: the synthetic contract's form for a public approval\n- #8999 file: `docs/agents/fleet.md`\n",
                "launch-fleet: start checked, synthetic",
            ),
        ],
    );
    let second = gh_issues(
        3,
        None,
        vec![gh_issue(
            9003,
            "CLOSED",
            &[(9001, "OPEN")],
            "Synthetic body, written before the rule.\n",
            "Synthetic note",
        )],
    );
    let prs = json!({"data": {"repository": {"pullRequests": {"totalCount": 2,
        "pageInfo": {"hasNextPage": false, "endCursor": null},
        "nodes": [{"number": 9102, "title": "#9002: Synthetic"}, {"number": 9103, "title": "#90021 Synthetic"}]}}}});
    fs::write(pages.join("fleet.md"), FLEET).expect("fleet settings");
    for (name, value) in [
        ("issues-first", first),
        ("issues-Y3Vyc29yOjI=", second),
        ("prs-first", prs),
    ] {
        fs::write(pages.join(format!("{name}.json")), value.to_string()).expect("page");
    }
}

fn gh_calls(dir: &Path) -> Vec<String> {
    text(&dir.join("gh/calls"))
        .lines()
        .map(str::to_owned)
        .collect()
}

/// Rewrites one page of the fake `gh`'s.
fn gh_edit(dir: &Path, page: &str, plant: impl FnOnce(&mut Value)) {
    let at = dir.join(format!("gh/{page}.json"));
    let mut value = json_file(&at);
    plant(&mut value);
    fs::write(at, value.to_string()).expect("page");
}

#[test]
fn plan_links_checker_reads_a_spec_through_gh() {
    let dir = bench("spec-read");
    gh_pages(&dir);
    let run = check(&dir, &["9000"], "");
    assert_eq!(run.code, Some(0), "stderr: {}", run.stderr);
    assert_eq!(
        run.stdout,
        "pass spec #9000: tickets 2, links 2, real 1, file 1, unlabelled 0, refusals 0\n\
         file link: #9002 blocked by #8999: docs/agents/fleet.md\n"
    );
    assert_eq!(run.stderr, "");
    let calls = gh_calls(&dir);
    assert_eq!(
        calls.len(),
        4,
        "the record authors, two pages of tickets, one of pull requests: {calls:?}"
    );
    assert_eq!(
        calls[0],
        "api -H Accept: application/vnd.github.raw+json repos/{owner}/{repo}/contents/docs/agents/fleet.md"
    );
    let calls = &calls[1..];
    for call in calls {
        assert!(call.starts_with("api graphql -f query=query"), "{call}");
        assert!(call.contains(" -F owner={owner} -F name={repo}"), "{call}");
    }
    assert!(calls[0].contains(" -F spec=9000") && !calls[0].contains("after="));
    assert!(calls[1].ends_with(" -f after=Y3Vyc29yOjI="), "{}", calls[1]);
    assert!(calls[2].contains("pullRequests"), "{}", calls[2]);

    gh_pages(&dir);
    let run = check(&dir, &["--json", "9000"], "");
    assert_eq!(run.code, Some(0), "stderr: {}", run.stderr);
    let report: Value = serde_json::from_str(&run.stdout).expect("JSON report");
    assert_eq!(
        report,
        json!({"schema": "openwiz.plan-links.v1", "kind": "report",
            "repo": "synthetic-owner/synthetic-repo", "source": {"kind": "spec", "spec": 9000},
            "result": "pass",
            "counts": {"tickets": 2, "links": 2, "real": 1, "file": 1, "unlabelled": 0, "refusals": 0},
            "links": [
                {"ticket": 9002, "blocker": 8999, "blocker_state": "CLOSED", "kind": "file", "files": ["docs/agents/fleet.md"]},
                {"ticket": 9002, "blocker": 9001, "blocker_state": "OPEN", "kind": "real", "files": []}],
            "refusals": []})
    );

    // A refusal read through gh.
    gh_pages(&dir);
    gh_edit(&dir, "issues-first", |v| {
        v["data"]["repository"]["issue"]["subIssues"]["nodes"][1]["body"] =
            json!("Synthetic body, written before the rule.\n")
    });
    let run = check(&dir, &["9000"], "");
    assert_eq!(run.code, Some(1), "stderr: {}", run.stderr);
    assert_eq!(
        run.stdout,
        "refused spec #9000: tickets 2, links 2, real 0, file 0, unlabelled 2, refusals 2\n"
    );
    assert_eq!(
        run.stderr,
        "Links: #9002: #8999 has no reason line\nLinks: #9002: #9001 has no reason line\n"
    );
    assert!(
        empty(&dir.join("work")) && empty(&dir.join("tmp")),
        "writes nothing"
    );
}

/// A failed, partial or invalid read: what breaks, and how to plant it.
type BadPage = (&'static str, fn(&Path));

/// Makes one page's read fail, as `gh` does.
fn gh_fails(dir: &Path, page: &str) {
    fs::write(dir.join(format!("gh/{page}.code")), "1\n").expect("code");
}

fn issues_at(v: &mut Value) -> &mut Value {
    &mut v["data"]["repository"]["issue"]["subIssues"]
}

#[test]
fn plan_links_checker_refuses_a_failed_or_partial_gh_read() {
    let bad: Vec<BadPage> = vec![
        // #717: no record authors, no read: never trust everyone.
        ("the record authors fail", |d| gh_fails(d, "fleet")),
        ("no Record authors row", |d| {
            fs::write(
                d.join("gh/fleet.md"),
                FLEET.replace("| Record authors", "| Record writers"),
            )
            .expect("fleet settings")
        }),
        ("a malformed Record authors row", |d| {
            fs::write(
                d.join("gh/fleet.md"),
                FLEET.replace("`synthetic-owner`", "synthetic-owner"),
            )
            .expect("fleet settings")
        }),
        ("the first page fails", |d| gh_fails(d, "issues-first")),
        ("the second page fails", |d| {
            gh_fails(d, "issues-Y3Vyc29yOjI=")
        }),
        ("the pull requests fail", |d| gh_fails(d, "prs-first")),
        ("the second page is missing", |d| {
            fs::remove_file(d.join("gh/issues-Y3Vyc29yOjI=.json")).expect("remove")
        }),
        ("not JSON", |d| {
            fs::write(d.join("gh/issues-first.json"), "Synthetic\n").expect("page")
        }),
        ("GraphQL errors", |d| {
            gh_edit(d, "issues-first", |v| {
                v["errors"] = json!([{"message": "Synthetic"}])
            })
        }),
        ("no such spec", |d| {
            gh_edit(d, "issues-first", |v| {
                v["data"]["repository"]["issue"] = Value::Null
            })
        }),
        ("fewer tickets than counted", |d| {
            gh_edit(d, "issues-first", |v| issues_at(v)["totalCount"] = json!(4));
            gh_edit(d, "issues-Y3Vyc29yOjI=", |v| {
                issues_at(v)["totalCount"] = json!(4)
            });
        }),
        ("more tickets than counted", |d| {
            gh_edit(d, "issues-first", |v| issues_at(v)["totalCount"] = json!(2));
            gh_edit(d, "issues-Y3Vyc29yOjI=", |v| {
                issues_at(v)["totalCount"] = json!(2)
            });
        }),
        ("the count changes between pages", |d| {
            // Every record counted by the first page arrives; the second
            // page counts fewer.
            gh_edit(d, "issues-Y3Vyc29yOjI=", |v| {
                issues_at(v)["totalCount"] = json!(2)
            });
        }),
        ("an empty page with more to come", |d| {
            gh_edit(d, "issues-first", |v| {
                issues_at(v)["nodes"] = json!([]);
                issues_at(v)["totalCount"] = json!(1);
            })
        }),
        ("a next page without a cursor", |d| {
            gh_edit(d, "issues-first", |v| {
                issues_at(v)["pageInfo"]["endCursor"] = Value::Null
            })
        }),
        ("a ticket listed twice", |d| {
            gh_edit(d, "issues-Y3Vyc29yOjI=", |v| {
                issues_at(v)["nodes"][0]["number"] = json!(9001)
            });
        }),
        ("blockers partly read", |d| {
            gh_edit(d, "issues-first", |v| {
                issues_at(v)["nodes"][1]["blockedBy"]["totalCount"] = json!(3)
            })
        }),
        ("labels partly read", |d| {
            gh_edit(d, "issues-first", |v| {
                issues_at(v)["nodes"][0]["labels"]["totalCount"] = json!(101)
            })
        }),
        ("pull requests partly read", |d| {
            gh_edit(d, "prs-first", |v| {
                v["data"]["repository"]["pullRequests"]["totalCount"] = json!(3)
            })
        }),
        ("a ticket's state unknown", |d| {
            gh_edit(d, "issues-first", |v| {
                issues_at(v)["nodes"][0]["state"] = json!("MERGED")
            })
        }),
        ("a bad repository name", |d| {
            gh_edit(d, "issues-first", |v| {
                v["data"]["repository"]["nameWithOwner"] = json!("synthetic")
            })
        }),
    ];
    let dir = bench("gh-failures");

    // GitHub repeating a cursor on pages with records: the reader stops on
    // its own once the pages hold more than the count, never looping.
    for args in [&["9000"][..], &["--json", "9000"]] {
        gh_pages(&dir);
        gh_edit(&dir, "issues-Y3Vyc29yOjI=", |v| {
            issues_at(v)["pageInfo"] = json!({"hasNextPage": true, "endCursor": "Y3Vyc29yOjI="})
        });
        let run = check(&dir, args, "");
        assert_refused_read(&run, "a repeated cursor");
        let calls = gh_calls(&dir);
        assert!(
            calls.len() <= 4,
            "a repeated cursor: stops reading: {} calls",
            calls.len()
        );
    }

    for (what, plant) in bad {
        gh_pages(&dir);
        plant(&dir);
        for args in [&["9000"][..], &["--json", "9000"]] {
            let run = check(&dir, args, "");
            assert_refused_read(&run, what);
            assert!(
                empty(&dir.join("work")) && empty(&dir.join("tmp")),
                "{what}: writes nothing"
            );
        }
    }
}
