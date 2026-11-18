//! OpenWiz integration with the pinned WizSkills install (#555, #814).
//! Keep harness links, local release/installation contracts and wrappers
//! without a green CI replacement. Portable checks belong to WizSkills;
//! see tools/test-value/evidence/tv12/ledger.md for each disposition.

use std::fs;
use std::os::unix::fs::symlink;
use std::path::{Path, PathBuf};

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
