//! OpenWiz integration with the pinned WizSkills install (#555, #814).
//! Keep harness links, local release/installation contracts and wrappers
//! without a green CI replacement. Portable checks belong to WizSkills;
//! see tools/test-value/evidence/tv12/ledger.md for each disposition.

use std::collections::BTreeSet;
use std::fs;
use std::os::unix::fs::symlink;
use std::path::{Path, PathBuf};

use serde_json::{Value, json};

const ROOT: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/..");

const SKILLS: [&str; 21] = [
    "grill",
    "plan-graph",
    "launch-fleet",
    "build-ticket",
    "review-ticket",
    "handoff",
    "setup",
    "triage",
    "wayfind",
    "where-are-we",
    "image",
    "research",
    "overnight",
    "huntr",
    "hill-climb",
    "diagnose",
    "ask-wiz",
    "onboard",
    "feedback-triage",
    "feedback",
    "install",
];

/// The skills not adapted from Matt Pocock's (spec ClosedWiz#205), each with
/// the source line its `SKILL.md` carries, exactly and on a line of its own,
/// stub or written, in place of his notice, which it must never carry.
/// Every other skill adapts his.
const NOT_MATTS: [(&str, &str); 9] = [
    (
        "hill-climb",
        "**Source:** new, original to OpenWiz. Not adapted from Matt Pocock's skills.",
    ),
    (
        "huntr",
        "**Source:** new, original to OpenWiz. Not adapted from Matt Pocock's skills.",
    ),
    (
        "where-are-we",
        "**Source:** dot-context's written plan. Not adapted from Matt Pocock's skills.",
    ),
    (
        "image",
        "**Source:** new, original to OpenWiz. Not adapted from Matt Pocock's skills.",
    ),
    (
        "overnight",
        "**Source:** new, original to OpenWiz. Not adapted from Matt Pocock's skills.",
    ),
    (
        "onboard",
        "**Source:** new, original to OpenWiz. Not adapted from Matt Pocock's skills.",
    ),
    (
        "feedback-triage",
        "**Source:** new, original to OpenWiz. Not adapted from Matt Pocock's skills.",
    ),
    (
        "feedback",
        "**Source:** new, original to OpenWiz. Not adapted from Matt Pocock's skills.",
    ),
    (
        "install",
        "**Source:** new, original to OpenWiz. Not adapted from Matt Pocock's skills.",
    ),
];

/// The source line a skill not adapted from Matt Pocock's carries, if `name`
/// is one.
fn source_line(name: &str) -> Option<&'static str> {
    NOT_MATTS
        .iter()
        .find(|(skill, _)| *skill == name)
        .map(|&(_, line)| line)
}

/// Where agents look for skills inside a repository.
const LINK_DIRS: [&str; 2] = [".claude/skills", ".agents/skills"];

/// The whole body of a skill that is not written yet.
const STUB: &str = "**Not written yet.** This file only fixes the skill's name and path; \
its build ticket writes it. Stop here, and tell whoever invoked it that this skill \
is not ready.";

fn problems(root: &Path) -> Vec<String> {
    let mut out = Vec::new();
    check_links(root, &mut out);
    out
}

fn check_links(root: &Path, out: &mut Vec<String>) {
    for dir in LINK_DIRS {
        for name in SKILLS {
            let link = root.join(dir).join(name);
            let at = format!("{dir}/{name}");
            let expected = Path::new("../../skills").join(name);
            match fs::read_link(&link) {
                Ok(target) if target == expected => {}
                Ok(target) => out.push(format!(
                    "{at} points at `{}`, not `{}`",
                    target.display(),
                    expected.display()
                )),
                Err(_) => {
                    out.push(format!("{at} must be a link to `{}`", expected.display()));
                    continue;
                }
            }
            let real = fs::canonicalize(root.join("skills").join(name)).ok();
            if real.is_none() || fs::canonicalize(&link).ok() != real {
                out.push(format!(
                    "{at} does not resolve to the real folder skills/{name}"
                ));
            }
        }
        let Ok(entries) = fs::read_dir(root.join(dir)) else {
            continue;
        };
        for entry in entries {
            let entry = entry.expect("entry");
            let name = entry.file_name().to_string_lossy().into_owned();
            if SKILLS.contains(&name.as_str()) {
                continue;
            }
            if entry.file_type().expect("file type").is_symlink() {
                out.push(format!(
                    "{dir}/{name} is a link, but not to one of the listed skills"
                ));
            } else if dir == ".agents/skills" {
                out.push(format!(
                    "{dir}/{name}: only the links to the listed skills belong here"
                ));
            }
        }
    }
}

fn collapse(text: &str) -> String {
    text.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn fixture(case: &str) -> PathBuf {
    let root = Path::new(env!("CARGO_TARGET_TMPDIR"))
        .join("skills-check")
        .join(case);
    let _ = fs::remove_dir_all(&root);
    for name in SKILLS {
        write(&root, &format!("skills/{name}/SKILL.md"), &stub(name));
        for dir in LINK_DIRS {
            crate::dirs::private_dir_all(root.join(dir)).expect("link dir");
            symlink(
                Path::new("../../skills").join(name),
                root.join(dir).join(name),
            )
            .expect("link");
        }
    }
    write(
        &root,
        "skills/README.md",
        "# Synthetic skills\n\nSee [grill](grill/SKILL.md) and `[code](not/a/link.md)`.\n",
    );
    root
}

fn write(root: &Path, rel: &str, text: &str) {
    let path = root.join(rel);
    crate::dirs::private_dir_all(path.parent().expect("parent")).expect("dir");
    fs::write(path, text).expect("write");
}

fn write_json(root: &Path, rel: &str, value: &Value) {
    write(
        root,
        rel,
        &serde_json::to_string_pretty(value).expect("json"),
    );
}

fn stub(name: &str) -> String {
    let source = source_line(name).map_or_else(String::new, |line| format!("\n{line}\n"));
    let invocation = if name == "ask-wiz" {
        "disable-model-invocation: true\n"
    } else {
        ""
    };
    format!(
        "---\nname: {name}\ndescription: Synthetic description of {name}.\n{invocation}---\n\n{STUB}\n{source}"
    )
}

fn assert_clean(root: &Path) {
    let found = problems(root);
    assert!(
        found.is_empty(),
        "expected no problems, got:\n{}",
        found.join("\n")
    );
}

fn assert_catches(root: &Path, expected: &str) {
    let found = problems(root);
    assert!(
        found.iter().any(|p| p.contains(expected)),
        "expected a problem containing {expected:?}, got:\n{}",
        found.join("\n")
    );
}

fn release_instruction(skill: &str, prefix: &str, required: &[&str]) {
    let text = fs::read_to_string(Path::new(ROOT).join(format!(".claude/skills/{skill}/SKILL.md")))
        .expect("local release skill");
    let paragraphs: Vec<_> = text
        .split("\n\n")
        .map(collapse)
        .filter(|paragraph| paragraph.starts_with(prefix))
        .collect();
    assert_eq!(paragraphs.len(), 1, "{skill}: one operative {prefix} rule");
    for rule in required {
        assert!(paragraphs[0].contains(rule), "{skill}: missing {rule}");
    }
}

#[test]
fn the_skills_folder_passes_the_static_check() {
    let found = problems(Path::new(ROOT));
    assert!(
        found.is_empty(),
        "the skills folder breaks the static check:\n{}",
        found.join("\n")
    );
}

#[test]
fn a_dangling_or_wrong_link_fails() {
    let relink = |root: &Path, rel: &str, target: &str| {
        let link = root.join(rel);
        let _ = fs::remove_file(&link);
        symlink(target, link).expect("link");
    };

    let root = fixture("link-dangling");
    relink(&root, ".agents/skills/grill", "../../skills/gril");
    assert_catches(&root, ".agents/skills/grill points at `../../skills/gril`");
    assert_catches(&root, ".agents/skills/grill does not resolve");

    let root = fixture("link-missing");
    fs::remove_file(root.join(".claude/skills/setup")).expect("remove");
    assert_catches(
        &root,
        ".claude/skills/setup must be a link to `../../skills/setup`",
    );

    let root = fixture("link-other-skill");
    relink(&root, ".claude/skills/triage", "../../skills/setup");
    assert_catches(
        &root,
        ".claude/skills/triage points at `../../skills/setup`",
    );

    let root = fixture("link-absolute");
    let absolute = fs::canonicalize(root.join("skills/handoff")).expect("real");
    relink(
        &root,
        ".claude/skills/handoff",
        absolute.to_str().expect("utf-8"),
    );
    assert_catches(&root, ".claude/skills/handoff points at");

    let root = fixture("link-copied");
    fs::remove_file(root.join(".agents/skills/handoff")).expect("remove");
    write(&root, ".agents/skills/handoff/SKILL.md", &stub("handoff"));
    assert_catches(&root, ".agents/skills/handoff must be a link");

    let root = fixture("link-extra");
    relink(&root, ".claude/skills/old-skill", "../../skills/old-skill");
    assert_catches(
        &root,
        ".claude/skills/old-skill is a link, but not to one of the listed skills",
    );

    let root = fixture("link-extra-file");
    write(&root, ".agents/skills/notes.md", "Synthetic.\n");
    assert_catches(
        &root,
        ".agents/skills/notes.md: only the links to the listed skills",
    );

    // The repository's own older skills stay real folders in .claude/skills.
    let root = fixture("link-older-skill");
    write(&root, ".claude/skills/older/SKILL.md", &stub("older"));
    assert_clean(&root);
}

#[test]
fn plan_graph_relies_on_form() {
    use std::io::Write;
    use std::process::{Command, Stdio};

    let root = fixture("relies-on-form");
    write(&root, "contracts/widget.v1.md", "Synthetic contract.\n");
    write(&root, "contracts/widget.v1.schema.json", "{}\n");
    write(&root, "skills/launch-fleet/SKILL.md", "Synthetic rules.\n");
    write(&root, "GLOSSARY.md", "Synthetic words.\n");
    symlink(root.join("GLOSSARY.md"), root.join("contracts/alias.md")).expect("synthetic link");
    symlink(&root, root.join("contracts/alias-dir")).expect("synthetic directory link");
    let cases = [
        ("nothing", "**Relies on:** nothing\n", None, true),
        (
            "embedded-cr-duplicate",
            "**Relies \ron:** `contracts/widget.v1.md`\n**Relies on:** `contracts/widget.v1.schema.json`\n",
            None,
            false,
        ),
        (
            "crlf",
            "**Relies on:** `contracts/widget.v1.md`\r\n",
            None,
            true,
        ),
        (
            "bare-cr-boundary",
            "Synthetic title\r**Relies on:** `contracts/widget.v1.md`\n",
            None,
            false,
        ),
        (
            "unicode-boundary",
            "Synthetic title\u{2028}**Relies on:** `contracts/widget.v1.md`\n",
            None,
            false,
        ),
        (
            "one",
            "**Relies on:** `contracts/widget.v1.md`\n",
            None,
            true,
        ),
        (
            "two",
            "**Relies on:** `contracts/widget.v1.md`, `contracts/widget.v1.schema.json`\n",
            None,
            true,
        ),
        ("root-file", "**Relies on:** `GLOSSARY.md`\n", None, true),
        (
            "rules-file",
            "**Relies on:** `skills/launch-fleet/SKILL.md`\n",
            None,
            true,
        ),
        (
            "planned",
            "**Relies on:** `contracts/future.v1.md`\n",
            Some("contracts/future.v1.md"),
            true,
        ),
        (
            "historical-118",
            "**Relies on:** `contracts/fleet-tick.v1.*` (B1); 0.0.5's `launch-fleet` rules (#102)\n",
            None,
            false,
        ),
        (
            "prose",
            "**Relies on:** the review report format (0.0.5 #101)\n",
            None,
            false,
        ),
        (
            "partial-name",
            "**Relies on:** `launch-fleet`\n",
            None,
            false,
        ),
        (
            "partial-file",
            "**Relies on:** `widget.v1.md`\n",
            None,
            false,
        ),
        (
            "mixed",
            "**Relies on:** `contracts/widget.v1.md`; review rules\n",
            None,
            false,
        ),
        (
            "annotation",
            "**Relies on:** `contracts/widget.v1.md` (#110)\n",
            None,
            false,
        ),
        ("folder", "**Relies on:** `contracts/`\n", None, false),
        (
            "glob",
            "**Relies on:** `contracts/widget.v1.*`\n",
            None,
            false,
        ),
        (
            "triple-star-duplicate",
            "***Relies on: `contracts/widget.v1.md`\n**Relies on:** `contracts/widget.v1.schema.json`\n",
            None,
            false,
        ),
        (
            "planned-file-parent",
            "**Relies on:** `contracts/widget.v1.md/future.md`\n",
            Some("contracts/widget.v1.md/future.md"),
            false,
        ),
        ("directory", "**Relies on:** `contracts`\n", None, false),
        (
            "symlink",
            "**Relies on:** `contracts/alias.md`\n",
            None,
            false,
        ),
        (
            "symlink-parent",
            "**Relies on:** `contracts/alias-dir/GLOSSARY.md`\n",
            None,
            false,
        ),
        (
            "planned-symlink",
            "**Relies on:** `contracts/alias-dir/future.md`\n",
            Some("contracts/alias-dir/future.md"),
            false,
        ),
        (
            "missing",
            "**Owned paths:** `contracts/widget.v1.md`\n",
            None,
            false,
        ),
        ("empty", "**Relies on:**\n", None, false),
        (
            "section",
            "## Relies on\n\n`contracts/widget.v1.md`\n",
            None,
            false,
        ),
        (
            "multiline",
            "**Relies on:** `contracts/widget.v1.md`\n`contracts/widget.v1.schema.json`\n",
            None,
            false,
        ),
        (
            "duplicate",
            "**Relies on:** nothing\n**Relies on:** `contracts/widget.v1.md`\n",
            None,
            false,
        ),
        (
            "duplicate-heading",
            "**Relies on:** nothing\n## Relies on\n\n`contracts/widget.v1.md`\n",
            None,
            false,
        ),
        ("empty-ticks", "**Relies on:** ``\n", None, false),
        (
            "unclosed",
            "**Relies on:** `contracts/widget.v1.md\n",
            None,
            false,
        ),
        (
            "double-ticks",
            "**Relies on:** ``contracts/widget.v1.md``\n",
            None,
            false,
        ),
        (
            "nothing-and-file",
            "**Relies on:** nothing, `contracts/widget.v1.md`\n",
            None,
            false,
        ),
        ("quoted-nothing", "**Relies on:** `nothing`\n", None, false),
        ("wrong-case", "**Relies on:** Nothing\n", None, false),
        (
            "absolute",
            "**Relies on:** `/contracts/widget.v1.md`\n",
            None,
            false,
        ),
        (
            "parent",
            "**Relies on:** `../contracts/widget.v1.md`\n",
            None,
            false,
        ),
        (
            "dot",
            "**Relies on:** `./contracts/widget.v1.md`\n",
            None,
            false,
        ),
        (
            "double-slash",
            "**Relies on:** `contracts//widget.v1.md`\n",
            None,
            false,
        ),
        (
            "non-ascii",
            "**Relies on:** `contracts/widgét.md`\n",
            None,
            false,
        ),
        (
            "unknown-file",
            "**Relies on:** `contracts/missing.md`\n",
            None,
            false,
        ),
        (
            "wrong-planned",
            "**Relies on:** `contracts/other.md`\n",
            Some("contracts/future.v1.md"),
            false,
        ),
        (
            "fenced",
            "```md\n**Relies on:** nothing\n```\n",
            None,
            false,
        ),
        (
            "commented",
            "<!--\n**Relies on:** nothing\n-->\n",
            None,
            false,
        ),
    ];
    // CI's Rust phase has sh and jq but no Python; the later skills phase
    // bootstraps Python separately. Keep this public check independent of it.
    let tools = root.join("checker-tools");
    crate::dirs::private_dir_all(&tools).expect("checker tools");
    for name in ["sh", "jq"] {
        let program = std::env::split_paths(&std::env::var_os("PATH").expect("PATH"))
            .map(|dir| dir.join(name))
            .find(|path| path.is_file())
            .expect("existing fleet tool");
        symlink(program, tools.join(name)).expect("tool link");
    }
    let mut wrong = Vec::new();
    for (case, body, planned, valid) in cases {
        let mut command = Command::new("sh");
        command
            .env("PATH", &tools)
            .arg(Path::new(ROOT).join("skills/plan-graph/check-relies.sh"))
            .arg("--root")
            .arg(&root);
        if let Some(path) = planned {
            command.arg("--planned").arg(path);
        }
        let mut child = command
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .expect("run the public checker");
        // The next heading bounds the declaration. A continuation path before
        // it is part of the same declaration and must not escape the check.
        let ticket = format!(
            "# Synthetic ticket\n\n{body}\n## Acceptance criteria\n\n- [ ] Synthetic proof.\n"
        );
        child
            .stdin
            .take()
            .expect("stdin")
            .write_all(ticket.as_bytes())
            .expect("ticket body");
        let output = child.wait_with_output().expect("checker result");
        if output.status.code() != Some(if valid { 0 } else { 1 }) {
            wrong.push(format!(
                "{case}: expected {}, got {:?}: {}",
                if valid { 0 } else { 1 },
                output.status.code(),
                String::from_utf8_lossy(&output.stderr)
            ));
            continue;
        }
        assert!(
            output.stdout.is_empty(),
            "{case}: a check prints no payload"
        );
        if !valid {
            assert!(
                String::from_utf8_lossy(&output.stderr).starts_with("Relies on: "),
                "{case}: diagnostic"
            );
        }
    }
    assert!(wrong.is_empty(), "unexpected checker verdicts: {wrong:?}");
}

#[test]
fn research_worker_github_check() {
    use std::os::unix::fs::PermissionsExt;
    use std::process::Command;

    let root = fixture("research-github-check");
    let tools = root.join("tools");
    crate::dirs::private_dir_all(&tools).expect("tools");
    for name in ["sh", "jq", "mktemp", "rm", "cat"] {
        let program = std::env::split_paths(&std::env::var_os("PATH").expect("PATH"))
            .map(|dir| dir.join(name))
            .find(|path| path.is_file())
            .expect("existing tool");
        symlink(program, tools.join(name)).expect("tool link");
    }
    write(
        &root,
        "tools/gh",
        r#"#!/bin/sh
printf '%s\n' "$*" >> "$RESEARCH_FIXTURE/reads"
[ "$#" = 6 ] && [ "$1 $2 $3 $4 $5" = 'api --method GET --paginate --slurp' ] || exit 90
case "$6" in
  'repos/example/widgets/branches?per_page=100') cat "$RESEARCH_FIXTURE/branches" ;;
  'repos/example/widgets/pulls?state=all&per_page=100') cat "$RESEARCH_FIXTURE/pulls" ;;
  'repos/example/widgets/issues/comments?per_page=100') cat "$RESEARCH_FIXTURE/comments" ;;
  'repos/example/widgets/pulls/comments?per_page=100') cat "$RESEARCH_FIXTURE/review-comments" ;;
  *) exit 91 ;;
esac
"#,
    );
    fs::set_permissions(tools.join("gh"), fs::Permissions::from_mode(0o700)).expect("mode");
    let branch = json!({"name": "main", "commit": {"sha": "a".repeat(40)}});
    let pull = json!({"number": 17, "state": "open", "merged_at": null,
        "title": "Synthetic report", "body": "Synthetic evidence", "draft": false,
        "head": {"ref": "research/widgets", "sha": "b".repeat(40), "repo": {"full_name": "example/widgets"}},
        "base": {"ref": "main", "repo": {"full_name": "example/widgets"}}});
    let comment = json!({"id": 23, "body": "Synthetic note", "updated_at": "2026-01-01T00:00:00Z"});
    let script = Path::new(ROOT).join("skills/research/scripts/check-workers.sh");
    let run = |args: &[&str]| {
        Command::new("sh")
            .arg(&script)
            .args(args)
            .env("PATH", &tools)
            .env("GH_REPO", "example/widgets")
            .env("RESEARCH_FIXTURE", &root)
            .output()
            .expect("run research guard")
    };
    let reset = || {
        write_json(&root, "branches", &json!([[branch.clone()], []]));
        write_json(&root, "pulls", &json!([[pull.clone()]]));
        write_json(&root, "comments", &json!([[comment.clone()]]));
        write_json(&root, "review-comments", &json!([[]]));
    };
    reset();
    let before = run(&["snapshot"]);
    assert!(
        before.status.success(),
        "snapshot: {}",
        String::from_utf8_lossy(&before.stderr)
    );
    write(
        &root,
        "before.json",
        &String::from_utf8(before.stdout).expect("JSON"),
    );
    let snapshot = root.join("before.json");
    let snapshot = snapshot.to_str().expect("path");
    let clean = run(&["check", snapshot]);
    assert_eq!(clean.status.code(), Some(0));
    assert_eq!(
        clean.stdout,
        b"clean research: no unexplained changes in checked GitHub surfaces\n"
    );
    assert!(clean.stderr.is_empty());
    let reads = fs::read_to_string(root.join("reads")).expect("reads");
    assert_eq!(reads.lines().count(), 8);
    for endpoint in [
        "branches?per_page=100",
        "pulls?state=all&per_page=100",
        "issues/comments?per_page=100",
        "pulls/comments?per_page=100",
    ] {
        assert_eq!(
            reads
                .lines()
                .filter(|line| line.ends_with(endpoint))
                .count(),
            2
        );
    }
    // Every mutation is independent, with literal expected finding names.
    let moved = json!({"name": "main", "commit": {"sha": "c".repeat(40)}});
    let new = json!({"name": "room/research-worker", "commit": {"sha": "d".repeat(40)}});
    let mut cases = vec![
        (
            "branches",
            json!([[branch.clone()], [new.clone()]]),
            "branch room/research-worker",
        ),
        ("branches", json!([[moved]]), "branch main"),
        ("branches", json!([[]]), "branch main"),
        ("pulls", json!([[]]), "pull request #17"),
        ("comments", json!([[]]), "comment 23"),
        (
            "review-comments",
            json!([[comment.clone()]]),
            "review comment 23",
        ),
    ];
    for (field, value) in [
        ("state", json!("closed")),
        ("merged_at", json!("2026-01-01T00:00:00Z")),
        ("title", json!("Unexpected edit")),
        ("body", json!("Unexpected body")),
        ("draft", json!(true)),
    ] {
        let mut changed = pull.clone();
        changed[field] = value;
        cases.push(("pulls", json!([[changed]]), "pull request #17"));
    }
    let mut extra_pull = pull.clone();
    extra_pull["number"] = json!(18);
    cases.push((
        "pulls",
        json!([[pull.clone()], [extra_pull]]),
        "pull request #18",
    ));
    for (side, field, value) in [
        ("head", "sha", json!("f".repeat(40))),
        ("head", "ref", json!("research/other")),
        ("base", "ref", json!("release-example")),
    ] {
        let mut changed = pull.clone();
        changed[side][field] = value;
        cases.push(("pulls", json!([[changed]]), "pull request #17"));
    }
    let mut edited_comment = comment.clone();
    edited_comment["body"] = json!("Unexpected edit");
    cases.push(("comments", json!([[edited_comment]]), "comment 23"));
    for (file, value, finding) in cases {
        reset();
        write_json(&root, file, &value);
        let result = run(&["check", snapshot]);
        assert_eq!(
            result.status.code(),
            Some(1),
            "{file}: {}",
            String::from_utf8_lossy(&result.stderr)
        );
        let output = String::from_utf8(result.stdout).expect("output");
        assert_eq!(output, format!("hit research: {finding}\n"));
        assert!(result.stderr.is_empty());
    }
    // Only an exact, explicitly acknowledged resulting value is exempted.
    reset();
    write_json(&root, "branches", &json!([[branch.clone(), new]]));
    write_json(
        &root,
        "allow.json",
        &json!({"branch room/research-worker": "d".repeat(40)}),
    );
    let allow = root.join("allow.json");
    let result = run(&["check", snapshot, "--allow", allow.to_str().expect("path")]);
    assert_eq!(result.status.code(), Some(0));
    write_json(
        &root,
        "allow.json",
        &json!({"branch room/research-worker": "e".repeat(40)}),
    );
    let result = run(&["check", snapshot, "--allow", allow.to_str().expect("path")]);
    assert_eq!(result.status.code(), Some(2));
    assert!(result.stdout.is_empty());
    // #990: `null` allows the deletion of any item: a branch, a PR or a comment.
    for (file, value, key) in [
        ("branches", json!([[]]), "branch main"),
        ("pulls", json!([[]]), "pull request #17"),
        ("comments", json!([[]]), "comment 23"),
    ] {
        reset();
        write_json(&root, file, &value);
        write_json(&root, "allow.json", &json!({ key: null }));
        let result = run(&["check", snapshot, "--allow", allow.to_str().expect("path")]);
        assert_eq!(result.status.code(), Some(0), "{key}");
        assert_eq!(
            result.stdout,
            b"clean research: no unexplained changes in checked GitHub surfaces\n"
        );
    }
    // `null` allows only a deletion, never an edit of the same item.
    reset();
    let mut edited = pull.clone();
    edited["title"] = json!("Unexpected edit");
    write_json(&root, "pulls", &json!([[edited]]));
    write_json(&root, "allow.json", &json!({"pull request #17": null}));
    let result = run(&["check", snapshot, "--allow", allow.to_str().expect("path")]);
    assert_eq!(result.status.code(), Some(2));
    assert!(result.stdout.is_empty());
    // #991: an allowance must name an actual change, even with the current value.
    reset();
    write_json(&root, "allow.json", &json!({"branch main": "a".repeat(40)}));
    let result = run(&["check", snapshot, "--allow", allow.to_str().expect("path")]);
    assert_eq!(result.status.code(), Some(2));
    assert!(result.stdout.is_empty());
    assert_eq!(
        result.stderr,
        b"check-workers.sh: allowance does not match observed changes\n"
    );
    // #991: only the snapshot validation refuses these; each would otherwise be read.
    let saved: Value =
        serde_json::from_str(&fs::read_to_string(root.join("before.json")).expect("snapshot"))
            .expect("snapshot JSON");
    let mut invalid = Vec::new();
    let mut unknown_key = saved.clone();
    unknown_key["items"]["tag v1"] = json!("a".repeat(40));
    invalid.push(("unknown item key", unknown_key));
    let mut not_sha = saved.clone();
    not_sha["items"]["branch main"] = json!("main");
    invalid.push(("non-SHA branch value", not_sha));
    let mut version = saved;
    version["version"] = json!(2);
    invalid.push(("unknown version", version));
    for (case, value) in invalid {
        reset();
        write_json(&root, "invalid.json", &value);
        let path = root.join("invalid.json");
        let result = run(&["check", path.to_str().expect("path")]);
        assert_eq!(result.status.code(), Some(2), "{case}");
        assert!(result.stdout.is_empty(), "{case}");
        assert_eq!(
            result.stderr, b"check-workers.sh: invalid snapshot\n",
            "{case}"
        );
    }
    // Broken, missing and partial reads never produce a clean result.
    for file in ["branches", "pulls", "comments", "review-comments"] {
        for bad in ["", "{}", "[]", "[[], {}]", "[[{}]]", "[[{}]", "[[], []"] {
            reset();
            write(&root, file, bad);
            let result = run(&["check", snapshot]);
            assert_eq!(result.status.code(), Some(2), "{file}: {bad}");
            assert!(result.stdout.is_empty());
            assert!(!result.stderr.is_empty());
        }
        reset();
        fs::remove_file(root.join(file)).expect("remove fake response");
        let result = run(&["check", snapshot]);
        assert_eq!(result.status.code(), Some(2));
        assert!(result.stdout.is_empty());
    }
    reset();
    write_json(&root, "branches", &json!([[branch.clone()], [branch]]));
    assert_eq!(run(&["snapshot"]).status.code(), Some(2), "duplicate ref");
    for bad in ["{}", "null", "[]", "{\"version\":1}"] {
        write(&root, "bad.json", bad);
        let path = root.join("bad.json");
        assert_eq!(
            run(&["check", path.to_str().expect("path")]).status.code(),
            Some(2)
        );
    }
}

#[test]
fn research_snapshot_path_survives_fresh_shells() {
    let skill = fs::read_to_string(Path::new(ROOT).join("skills/research/SKILL.md"))
        .expect("research skill");
    let dispatch = skill
        .split("## 2. Dispatch fresh workers\n")
        .nth(1)
        .expect("dispatch section")
        .split("## Worker:")
        .next()
        .expect("dispatch body");
    let blocks: Vec<&str> = dispatch
        .split("```sh\n")
        .skip(1)
        .map(|rest| rest.split_once("\n```").expect("sh block closes").0)
        .collect();
    assert!(!blocks.is_empty(), "the dispatch section has sh blocks");
    for block in &blocks {
        let assigned: BTreeSet<&str> = block
            .lines()
            .filter_map(|line| line.trim().split_once('='))
            .map(|(name, _)| name)
            .filter(|name| name.chars().all(|c| c.is_ascii_alphanumeric() || c == '_'))
            .collect();
        for (at, _) in block.match_indices('$') {
            let name: String = block[at + 1..]
                .trim_start_matches('{')
                .chars()
                .take_while(|c| c.is_ascii_alphanumeric() || *c == '_')
                .collect();
            assert!(
                name.is_empty() || assigned.contains(name.as_str()),
                "dispatch block reads ${name}, set in another shell:\n{block}"
            );
        }
    }
    let commands: Vec<&str> = blocks.iter().flat_map(|block| block.lines()).collect();
    assert!(
        commands.contains(&"mktemp"),
        "mktemp runs alone and prints the path"
    );
    let prose = dispatch.split_whitespace().collect::<Vec<_>>().join(" ");
    assert!(
        prose.contains("Record that literal path in your notes"),
        "the asker records the printed path"
    );

    // #989 R1: a TMPDIR with spaces (or a quote) must still reach the checker
    // as one argument. Run the skill's own commands, each in a fresh `sh -c`,
    // with a fake checker that prints its arguments, after filling the
    // placeholders exactly as the skill says.
    let checker = "sh \"<research-skill-folder>/scripts/check-workers.sh\" ";
    let find = |verb: &str| -> String {
        let found: Vec<&&str> = commands
            .iter()
            .filter(|line| line.starts_with(&format!("{checker}{verb} ")))
            .collect();
        assert_eq!(found.len(), 1, "one `{verb}` command:\n{dispatch}");
        (*found[0]).to_owned()
    };
    let snapshot_command = find("snapshot");
    let check_command = find("check");
    let root = Path::new(env!("CARGO_TARGET_TMPDIR"))
        .join("skills-check")
        .join("research-snapshot-quoting");
    let _ = fs::remove_dir_all(&root);
    let folder = root.join("skill folder");
    write(
        &folder,
        "scripts/check-workers.sh",
        "for arg in \"$@\"; do printf 'arg:%s\\n' \"$arg\"; done\n",
    );
    let snapshot = root.join("tmp dir/it's a snapshot");
    let allow = root.join("tmp dir/exact changes.json");
    crate::dirs::private_dir_all(snapshot.parent().expect("parent")).expect("tmp dir");
    let quote = |path: &Path| path.to_str().expect("path").replace('\'', "'\\''");
    let shell = |command: &str| {
        let filled = command
            .replace("<research-skill-folder>", folder.to_str().expect("folder"))
            .replace("<snapshot-path>", &quote(&snapshot))
            .replace("<exact-changes.json>", &quote(&allow));
        let output = std::process::Command::new("sh")
            .arg("-c")
            .arg(&filled)
            .current_dir(&root)
            .output()
            .expect("run sh");
        assert!(
            output.status.success(),
            "{filled}\n{}",
            String::from_utf8_lossy(&output.stderr)
        );
        String::from_utf8(output.stdout).expect("utf-8")
    };
    let snap = snapshot.to_str().expect("path");
    assert_eq!(shell(&snapshot_command), "");
    assert_eq!(
        fs::read_to_string(&snapshot).expect("snapshot at the recorded path"),
        "arg:snapshot\n"
    );
    assert_eq!(shell(&check_command), format!("arg:check\narg:{snap}\n"));
    let rerun = "`check '<snapshot-path>' --allow '<exact-changes.json>'`";
    assert_eq!(prose.matches(rerun).count(), 1, "the allowance rerun");
    let rerun_command = format!("{checker}{}", rerun.trim_matches('`'));
    assert!(
        prose.contains(
            "replace `<snapshot-path>` inside its single quotes with the path, \
             writing each `'` in it as `'\\''`"
        ),
        "the skill says how to quote the recorded path"
    );
    assert_eq!(
        shell(&rerun_command),
        format!(
            "arg:check\narg:{snap}\narg:--allow\narg:{}\n",
            allow.to_str().expect("path")
        )
    );
    assert_eq!(
        snapshot_command,
        format!("{checker}snapshot > '<snapshot-path>'")
    );
    assert_eq!(check_command, format!("{checker}check '<snapshot-path>'"));
}

#[test]
fn adr0019_live_smoke_and_hands_on_timing() {
    // ADR 0020 keeps ADR 0019's smoke and post-publication feedback decisions.
    release_instruction(
        "live-quick-check",
        "**Release gate:**",
        &[
            "CI, privacy/claims, verified products and an agent-run live smoke on the same combined build must pass",
            "exercise every included version's promise end to end",
            "Changed sending, thread creation, App permissions and spending also need their relevant bounded live checks before publication",
            "Unknown/missing risk or evidence refuses",
            "Jake's actual ship instruction and exact changelog approval are the only human release actions for this path",
            "no per-step live/publish prompt, export-plan, final-diff, standalone Sol-export or mandatory hands-on/device gate",
            "Ordinary code review/CI remain",
            "Hands-on feedback follows publication",
        ],
    );
    release_instruction(
        "live-quick-check",
        "2. **Restrict before effects.**",
        &[
            "kit's own throwaway targets within existing counts, room-cli allowlist and spending bounds",
            "reviewed-plan `--expect-plan` restriction before effects, including refusal of pending-start recovery",
            "Refuse if the restriction or any authority is uncertain",
            "An approved kit covers its steps without another human prompt",
            "No automatic retry",
            "persist consumed attempts and completed steps",
        ],
    );
    release_instruction(
        "live-quick-check",
        "5. **Keep device limits explicit.**",
        &[
            "approved headless emulation",
            "WebKit and real radios stay unverified",
            "Mac-only checks stay on the Mac within existing authority",
            "A required promise left unproved blocks its gate",
            "Optional hands-on/device feedback follows publication",
        ],
    );
}

#[test]
fn adr0019_combined_release_gate() {
    release_instruction(
        "export-review",
        "1. **Prepare one checked candidate.**",
        &[
            "public repository's own history",
            "clean selected commit/build and complete matching products for all supported targets",
            "ordered individual changelog sections for every included version",
            "all seven for the settled 0.0.6–0.0.12 combined release",
            "Bind exact UTF-8 notes, complete artifact/manifest/checksum/alias hashes",
            "Ordinary development plan approval, code review, protected-source and merge CI remain",
        ],
    );
    release_instruction(
        "export-review",
        "3. **Require every automatic gate.**",
        &[
            "Resolve exact-candidate CI, full public source/history/artifact privacy, honest claim evidence and compiled-product verification",
            "Require the combined live smoke to exercise every included promise end to end",
            "live checks for changed sending, thread creation, App permissions or spending",
            "only within existing approved kit targets/counts, allowlists, App grants, host and spending",
            "Unknown risk, unreadable/missing, failed, stale, fixture, dry-run or uncertain required evidence blocks",
            "automatic release gates, not an additional human export approval",
        ],
    );
    let contract = fs::read_to_string(Path::new(ROOT).join("contracts/release-candidate.v1.md"))
        .expect("release candidate contract");
    let coverage: Vec<_> = contract
        .split("\n\n")
        .map(collapse)
        .filter(|paragraph| paragraph.starts_with("`coverage` in smoke is"))
        .collect();
    assert_eq!(coverage.len(), 1, "one operative smoke coverage rule");
    assert!(coverage[0].contains(
        "A smoke coverage row passes only when its live evidence proves the complete user flow for that promise was exercised end to end on the combined candidate"
    ));
    assert!(coverage[0].contains("A partial check cannot satisfy the row"));
}

#[test]
fn adr0019_automatic_export_and_one_final_approval() {
    // The successor removes export approval; it does not activate shipping.
    release_instruction(
        "export-review",
        "**Activation gate:**",
        &[
            "preparation can happen before cut-over, but shipping requires verified O17 after O16 with their existing authorization, prerequisites and holds intact",
            "This skill authorizes neither step, no live run or publication now",
            "Private-to-public release copying remains stopped except specifically assigned O16 work",
            "`release/openwiz/` stays frozen",
        ],
    );
    release_instruction(
        "export-review",
        "2. **Resolve the two actual decisions.**",
        &[
            "Jake's ship instruction and approval of the exact changelog are the only human release actions",
            "approval may precede ship",
            "Verify the existing private decision comments, author, scope, current revision, hashes and candidate/notes bindings",
            "A supplied flag, invented pointer or old decision for another candidate refuses",
            "Store original ship time before effects",
            "No export-plan, final-diff, mandatory Sol-export, mandatory hands-on/ device or second publish instruction",
        ],
    );
    release_instruction(
        "export-review",
        "4. **Invalidate changed inputs.**",
        &[
            "Recompute bindings when source/build, notes, artifacts, kit or risk changes",
            "Recheck current external holds, permissions and gate inputs before each effect",
            "Keep original ship time across resumes, completed steps and consumed attempts",
            "Return blocked/incomplete",
            "no watcher, poll loop or sleep",
        ],
    );
    release_instruction(
        "export-review",
        "5. **Publish and read back when authorized.**",
        &[
            "only after verified cut-over, both actual decisions and every required passing gate",
            "immutable-release and required-check settings",
            "no new settings approval",
            "no-force-push and version order",
            "Read back the annotated tag/peeled public commit, exact approved notes, complete asset bytes/manifests/checksums/aliases and immutable pre-release state",
            "Partial publication is incomplete",
            "never repeat a potentially consumed write automatically",
            "Historical backfill keeps its own explicit gate",
        ],
    );
    release_instruction(
        "export-review",
        "6. **Verify user delivery and report.**",
        &[
            "normal install/update on an already approved test machine",
            "Stop the clock only after matching installation and remote publication verification",
            "Include all time after the original ship instruction: changelog waits, queue, checks/builds, publication and download/update",
            "report preparation separately",
            "Under 30 minutes meets the light target; otherwise record a miss or block",
        ],
    );
}

#[test]
fn adr0019_release_skills_are_kept_for_rust_checks() {
    use std::io::Write;
    use std::process::{Command, Stdio};

    for skill in ["export-review", "live-quick-check"] {
        let path = format!(".claude/skills/{skill}/SKILL.md\n");
        for (args, expected) in [(vec![], "web-build rust\n"), (vec!["--skips", "rust"], "")] {
            let mut child = Command::new("sh")
                .arg(".github/actions/docs-only/classify.sh")
                .args(args)
                .current_dir(ROOT)
                .stdin(Stdio::piped())
                .stdout(Stdio::piped())
                .stderr(Stdio::piped())
                .spawn()
                .expect("run CI classifier");
            child
                .stdin
                .take()
                .expect("classifier stdin")
                .write_all(path.as_bytes())
                .expect("classify release skill");
            let output = child.wait_with_output().expect("classifier result");
            assert!(
                output.status.success(),
                "{}",
                String::from_utf8_lossy(&output.stderr)
            );
            assert_eq!(output.stdout, expected.as_bytes(), "{path}");
        }
    }
}

#[test]
fn onboard_journey_fixtures_pass() {
    let result = std::process::Command::new("python3")
        .args(["-I", "tools/install/tests/onboard/test_journey.py"])
        .current_dir(ROOT)
        .output()
        .expect("run the onboarding journey");
    assert!(
        result.status.success(),
        "onboarding journey failed: {}{}",
        String::from_utf8_lossy(&result.stdout),
        String::from_utf8_lossy(&result.stderr)
    );
}

#[test]
fn setup_onboard_contract_passes() {
    let result = std::process::Command::new("python3")
        .args([
            "-I",
            "tools/install/tests/setup-onboard-contract/test_contract.py",
        ])
        .current_dir(ROOT)
        .output()
        .expect("run the setup-onboard contract checks");
    assert!(
        result.status.success(),
        "setup-onboard contract checks failed: {}{}",
        String::from_utf8_lossy(&result.stdout),
        String::from_utf8_lossy(&result.stderr)
    );
}

#[test]
fn setup_onboard_init_passes() {
    let result = std::process::Command::new("python3")
        .args(["-I", "tools/install/tests/init/test_init.py"])
        .current_dir(ROOT)
        .output()
        .expect("run the init runtime proofs");
    assert!(
        result.status.success(),
        "init runtime proofs failed: {}{}",
        String::from_utf8_lossy(&result.stdout),
        String::from_utf8_lossy(&result.stderr)
    );
}

#[test]
fn setup_onboard_login_passes() {
    let result = std::process::Command::new("python3")
        .args(["-I", "-B", "tools/install/setup/test_github_login.py"])
        .current_dir(ROOT)
        .output()
        .expect("run the setup GitHub login proofs");
    assert!(
        result.status.success(),
        "setup GitHub login proofs failed: {}{}",
        String::from_utf8_lossy(&result.stdout),
        String::from_utf8_lossy(&result.stderr)
    );
}

#[test]
fn setup_onboard_journey_passes() {
    let result = std::process::Command::new("python3")
        .args(["-I", "tools/install/tests/first-hour/test_first_merge.py"])
        .current_dir(ROOT)
        .output()
        .expect("run the first-merge journey and kit proofs");
    assert!(
        result.status.success(),
        "first-merge journey and kit proofs failed: {}{}",
        String::from_utf8_lossy(&result.stdout),
        String::from_utf8_lossy(&result.stderr)
    );
}

#[test]
fn one_install_line_everywhere() {
    let read = |path: &str| fs::read_to_string(Path::new(ROOT).join(path)).expect(path);
    let line = "Install OpenWiz from github.com/openwizdev/OpenWiz";
    for path in ["skills/install/SKILL.md", "docs/install.md", "README.md"] {
        assert!(
            read(path).contains(&format!("> {line}\n")),
            "{path} quotes the install line"
        );
    }
    assert!(
        read("apps/web/src/components/Setup.tsx")
            .contains("export const CLOUDROOM_UPGRADE = 'cloudroom.dev/pricing';")
    );
    let guide = read("docs/install.md");
    assert!(guide.contains("](https://cloudroom.dev/pricing)"));
}

#[test]
fn install_journey_and_live_kit_pass() {
    for script in [
        "tools/install/tests/journey/test_journey.py",
        "tools/install/live-kit-test.py",
        "tools/install/tests/first-hour/test_journey.py",
        "tools/install/tests/first-hour/test_kit.py",
    ] {
        let result = std::process::Command::new("python3")
            .args(["-I", script])
            .current_dir(ROOT)
            .output()
            .expect("run python");
        assert!(
            result.status.success(),
            "{script} failed: {}{}",
            String::from_utf8_lossy(&result.stdout),
            String::from_utf8_lossy(&result.stderr)
        );
    }
}
