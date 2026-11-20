//! #1853 (KN20): the roster contract's fixtures agree with its rules.
//! `contracts/roster.v1.md` is the contract; this file is registered in
//! `tests/cli-agent/main.rs` and kept beside the fixtures it checks, so a
//! later reader (KN21's launch-fleet pick, KN22's setup check) has one place
//! to compare itself against. All values are synthetic.
//!
//! The reader below is the contract's reference reading of a `fleet.md`'s
//! Roster, and its pick rule. It ships nowhere.
use std::collections::BTreeSet;
use std::fs;
use std::path::{Path, PathBuf};

use serde_json::{Value, json};

use super::ROOT;

const HEADER: [&str; 5] = ["Name", "Kind", "Driver", "Roles", "Writes as"];
const KINDS: [&str; 3] = ["harness", "host", "bot"];
const ROLES: [&str; 4] = ["orchestrator", "builder", "reviewer", "helper"];
const CASES: [&str; 5] = [
    "mixed",
    "role-not-allowed",
    "other-user",
    "starting",
    "no-roster",
];
const CODES: [&str; 15] = [
    "headings",
    "no-table",
    "header",
    "empty",
    "cells",
    "name",
    "duplicate-name",
    "kind",
    "driver",
    "no-role",
    "role",
    "repeated-role",
    "writes-as",
    "person",
    "label",
];

fn dir() -> PathBuf {
    Path::new(ROOT).join("contracts/fixtures/roster")
}

fn text(rel: &str) -> String {
    let path = dir().join(rel);
    fs::read_to_string(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()))
}

fn load(rel: &str) -> Value {
    serde_json::from_str(&text(rel)).unwrap_or_else(|e| panic!("{rel}: {e}"))
}

/// The names in a fixture folder, or none when it is missing.
fn listing(rel: &str) -> BTreeSet<String> {
    match fs::read_dir(dir().join(rel)) {
        Ok(entries) => entries
            .map(|e| e.unwrap().file_name().into_string().unwrap())
            .collect(),
        Err(_) => BTreeSet::new(),
    }
}

// ---- The reference reading ------------------------------------------------

#[derive(Debug)]
struct Entry {
    name: String,
    kind: String,
    driver: String,
    roles: Vec<String>,
    person: String,
}

impl Entry {
    fn label(&self) -> String {
        format!("{} via {}", self.name, self.person)
    }

    fn to_json(&self) -> Value {
        json!({
            "name": self.name,
            "kind": self.kind,
            "driver": self.driver,
            "roles": self.roles,
            "writes_as": format!("{}'s App", self.person),
            "label": self.label(),
        })
    }
}

fn cells(line: &str) -> Option<Vec<String>> {
    let line = line.trim();
    let inner = line.strip_prefix('|')?.strip_suffix('|')?;
    Some(inner.split('|').map(|c| c.trim().to_owned()).collect())
}

fn is_heading(line: &str) -> bool {
    line.starts_with("# ") || line.starts_with("## ")
}

fn word_ok(s: &str, max: usize, ok: impl Fn(char) -> bool, sep: char) -> bool {
    let b = s.as_bytes();
    !s.is_empty()
        && s.len() <= max
        && s.chars().all(|c| ok(c) || c == sep)
        && b[0] as char != sep
        && b[b.len() - 1] as char != sep
        && !s.contains(&format!("{sep}{sep}"))
}

fn name_ok(s: &str) -> bool {
    let first_last = |c: Option<char>| c.is_some_and(|c| c.is_ascii_alphanumeric());
    word_ok(
        s,
        40,
        |c| c.is_ascii_alphanumeric() || matches!(c, '.' | '_' | '-'),
        ' ',
    ) && first_last(s.chars().next())
        && first_last(s.chars().last())
}

fn driver_ok(s: &str) -> bool {
    word_ok(s, 40, |c| c.is_ascii_lowercase() || c.is_ascii_digit(), '-')
}

fn login_ok(s: &str) -> bool {
    word_ok(s, 39, |c| c.is_ascii_alphanumeric(), '-')
}

/// The Roster of a `fleet.md`: `Ok(None)` with no Roster heading, or the
/// refusal line of the first broken rule.
fn read(fleet: &str) -> Result<Option<Vec<Entry>>, String> {
    let lines: Vec<&str> = fleet.lines().map(str::trim_end).collect();
    let at: Vec<usize> = (0..lines.len())
        .filter(|&i| lines[i] == "## Roster")
        .collect();
    if at.len() > 1 {
        return Err("Roster refused: more than one ## Roster heading".into());
    }
    let Some(&start) = at.first() else {
        return Ok(None);
    };
    let section: Vec<&str> = lines[start + 1..]
        .iter()
        .copied()
        .take_while(|l| !is_heading(l))
        .collect();
    let Some(first) = section.iter().position(|l| l.trim_start().starts_with('|')) else {
        return Err("Roster refused: the Roster section has no table".into());
    };
    let table: Vec<&str> = section[first..]
        .iter()
        .copied()
        .take_while(|l| l.trim_start().starts_with('|'))
        .collect();
    let header_ok = cells(table[0]).is_some_and(|c| c == HEADER)
        && table.get(1).and_then(|l| cells(l)).is_some_and(|c| {
            c.len() == 5
                && c.iter()
                    .all(|c| c.len() >= 3 && c.chars().all(|c| c == '-'))
        });
    if !header_ok {
        return Err(
            "Roster refused: the header is not Name, Kind, Driver, Roles, Writes as".into(),
        );
    }
    if table.len() == 2 {
        return Err("Roster refused: the table has no entries".into());
    }
    let mut entries: Vec<Entry> = Vec::new();
    for (i, line) in table[2..].iter().enumerate() {
        let n = i + 1;
        let row = cells(line).unwrap_or_default();
        if row.len() != 5 {
            return Err(format!(
                "Roster refused: row {n} has {} cells, not 5",
                row.len()
            ));
        }
        let name = row[0].clone();
        if !name_ok(&name) {
            return Err(format!("Roster refused: row {n}: bad name: {name}"));
        }
        if entries.iter().any(|e| e.name.eq_ignore_ascii_case(&name)) {
            return Err(format!(
                "Roster refused: row {n}: {name} is already an entry"
            ));
        }
        let at = format!("Roster refused: row {n} ({name})");
        if !KINDS.contains(&row[1].as_str()) {
            return Err(format!("{at}: unknown kind: {}", row[1]));
        }
        if !driver_ok(&row[2]) {
            return Err(format!("{at}: bad driver: {}", row[2]));
        }
        if row[3].is_empty() {
            return Err(format!("{at}: no roles"));
        }
        let mut roles: Vec<String> = Vec::new();
        for role in row[3].split(',').map(str::trim) {
            if !ROLES.contains(&role) {
                return Err(format!("{at}: unknown role: {role}"));
            }
            if roles.iter().any(|r| r == role) {
                return Err(format!("{at}: role listed twice: {role}"));
            }
            roles.push(role.to_owned());
        }
        let person = match row[4].strip_suffix("'s App") {
            Some(p) if login_ok(p) => p.to_owned(),
            _ => return Err(format!("{at}: writes as {}, not <person>'s App", row[4])),
        };
        if let Some(first) = entries.first()
            && first.person != person
        {
            return Err(format!(
                "{at}: writes as {}, not {}'s App like row 1",
                row[4], first.person
            ));
        }
        let entry = Entry {
            name,
            kind: row[1].clone(),
            driver: row[2].clone(),
            roles,
            person,
        };
        if entry.label().chars().count() > 60 {
            return Err(format!(
                "{at}: {} is longer than 60 characters",
                entry.label()
            ));
        }
        entries.push(entry);
    }
    Ok(Some(entries))
}

/// The choices a one-table Models section writes, as `choice` objects.
fn model_choices(fleet: &str) -> Vec<Value> {
    let mut out = Vec::new();
    let mut inside = false;
    for line in fleet.lines() {
        if is_heading(line) {
            inside = line.trim_end() == "## Models";
            continue;
        }
        let Some(c) = cells(line).filter(|c| inside && c.len() == 5) else {
            continue;
        };
        let flags: Vec<&str> = c[4].trim_matches('`').split(' ').collect();
        if let [
            "--provider",
            provider,
            "--model",
            model,
            "--reasoning-level",
            effort,
        ] = flags.as_slice()
        {
            out.push(json!({
                "harness": c[1], "provider": provider, "model": model, "effort": effort,
            }));
        }
    }
    out
}

/// The harness name models.v1 writes for a provider.
fn harness_name(provider: &str) -> &str {
    match provider {
        "claude-code" => "Claude Code",
        "codex" => "Codex",
        other => other,
    }
}

/// The harness word a driver's `start` takes for a provider.
fn driver_harness(provider: &str) -> &str {
    match provider {
        "claude-code" => "claude",
        other => other,
    }
}

/// The contract's pick for one start: role R, choice C (null when models.v1
/// waits), on `repository#ticket`.
fn pick(entries: &[Entry], repository: &str, ticket: u64, role: &str, choice: &Value) -> Value {
    let base = json!({"ticket": ticket, "role": role, "choice": choice});
    let with = |mut v: Value, extra: Value| {
        for (k, x) in extra.as_object().unwrap() {
            v[k] = x.clone();
        }
        v
    };
    if choice.is_null() {
        return with(base, json!({"pick": null, "waits": "models", "look": null}));
    }
    let provider = choice["provider"].as_str().unwrap();
    let harness = harness_name(provider);
    let found = entries
        .iter()
        .find(|e| e.roles.iter().any(|r| r == role) && (e.kind != "harness" || e.name == harness));
    let Some(e) = found else {
        let look = format!("roster: no entry may take the {role} role with {harness}");
        return with(base, json!({"pick": null, "waits": "roster", "look": look}));
    };
    let picked = json!({
        "name": e.name,
        "kind": e.kind,
        "driver": e.driver,
        "start": {"harness": driver_harness(provider), "model": choice["model"]},
        "label": e.label(),
        "writes_as": format!("{}'s App", e.person),
        "token": {
            "service": e.person,
            "requester": format!("{role}-{ticket}"),
            "repositories": [repository],
        },
    });
    with(base, json!({"pick": picked, "waits": null, "look": null}))
}

// ---- The tests ------------------------------------------------------------

// catches: a reader that picks an entry for a role it may not take, ignores
// table order, gives a harness entry another harness's choice, mislabels an
// entry, or treats a project without a Roster as anything but today's.
#[test]
fn every_case_reads_and_picks_as_its_fixture_says() {
    let present = listing("");
    let missing: Vec<_> = CASES.iter().filter(|c| !present.contains(**c)).collect();
    assert!(missing.is_empty(), "missing fixture cases: {missing:?}");
    for case in CASES {
        let fleet = text(&format!("{case}/fleet.md"));
        let want = load(&format!("{case}/case.json"));
        let entries = read(&fleet).unwrap_or_else(|e| panic!("{case}: {e}"));
        let Some(entries) = entries else {
            assert_eq!(want, json!({"roster": null, "starts": "today"}), "{case}");
            continue;
        };
        let roster: Vec<Value> = entries.iter().map(Entry::to_json).collect();
        assert_eq!(want["roster"], json!(roster), "{case}: the roster as read");
        assert_eq!(
            want["person"].as_str(),
            Some(entries[0].person.as_str()),
            "{case}"
        );
        let repository = want["repository"].as_str().unwrap();
        let picks = want["picks"].as_array().unwrap();
        assert!(!picks.is_empty(), "{case}: no picks");
        for p in picks {
            let got = pick(
                &entries,
                repository,
                p["ticket"].as_u64().unwrap(),
                p["role"].as_str().unwrap(),
                &p["choice"],
            );
            assert_eq!(&got, p, "{case}: ticket {} {}", p["ticket"], p["role"]);
        }
    }
}

// catches: a reader that guesses past a malformed Roster (an unknown role or
// kind, a repeated role, a row writing as another account or another
// person's App) instead of refusing it by name, with the contract's line.
#[test]
fn a_malformed_roster_is_refused_by_name() {
    let refusals = if listing("invalid").contains("refusals.json") {
        load("invalid/refusals.json")
    } else {
        json!({})
    };
    let refusals = refusals.as_object().unwrap();
    let missing: Vec<_> = CODES
        .iter()
        .filter(|c| !refusals.contains_key(&format!("{c}.md")))
        .collect();
    assert!(
        missing.is_empty(),
        "refusal codes without a fixture: {missing:?}"
    );
    let files: BTreeSet<String> = listing("invalid")
        .into_iter()
        .filter(|f| f.ends_with(".md"))
        .collect();
    let named: BTreeSet<String> = refusals.keys().cloned().collect();
    assert_eq!(files, named, "invalid/*.md and refusals.json differ");
    for (file, line) in refusals {
        let got = read(&text(&format!("invalid/{file}")));
        assert_eq!(got.err().as_deref(), line.as_str(), "invalid/{file}");
    }
}

// catches: a fixture whose choice is not one models.v1 could resolve from its
// own fleet.md, so a reader passing it would prove nothing about the Models
// table it reads.
#[test]
fn every_choice_is_a_row_of_its_cases_models_table() {
    for case in CASES {
        if !listing(case).contains("case.json") {
            continue;
        }
        let rows = model_choices(&text(&format!("{case}/fleet.md")));
        assert!(!rows.is_empty(), "{case}: no Models table");
        let want = load(&format!("{case}/case.json"));
        for p in want["picks"].as_array().into_iter().flatten() {
            let c = &p["choice"];
            assert!(
                c.is_null() || rows.contains(c),
                "{case}: {c} is no Models row"
            );
        }
    }
}

// catches: a per-entry or per-bot write rule: a token request, App or label
// that depends on an entry's kind, or a user project whose writes go
// anywhere but its own person's App and repositories.
#[test]
fn every_entry_writes_the_same_way() {
    let mut kinds = BTreeSet::new();
    let mut people = BTreeSet::new();
    for case in CASES {
        if !listing(case).contains("case.json") {
            continue;
        }
        let want = load(&format!("{case}/case.json"));
        let Some(picks) = want["picks"].as_array() else {
            continue;
        };
        let person = want["person"].as_str().unwrap();
        let repository = want["repository"].as_str().unwrap();
        assert_eq!(
            repository.split('/').next(),
            Some(person),
            "{case}: the person's own repository"
        );
        people.insert(person.to_owned());
        for p in picks.iter().filter(|p| !p["pick"].is_null()) {
            let e = &p["pick"];
            kinds.insert(e["kind"].as_str().unwrap().to_owned());
            let fixed = json!({
                "writes_as": format!("{person}'s App"),
                "label": format!("{} via {person}", e["name"].as_str().unwrap()),
                "token": {
                    "service": person,
                    "requester": format!("{}-{}", p["role"].as_str().unwrap(), p["ticket"]),
                    "repositories": [repository],
                },
            });
            for key in ["writes_as", "label", "token"] {
                assert_eq!(e[key], fixed[key], "{case}: ticket {} {key}", p["ticket"]);
            }
        }
    }
    assert_eq!(
        kinds,
        KINDS.iter().map(|k| k.to_string()).collect(),
        "every kind is picked somewhere"
    );
    assert!(
        people.len() >= 2,
        "a user project that isn't ours: {people:?}"
    );
}
