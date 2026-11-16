//! Loop files and Cloudroom loops, by the pinned WizLoops adapter rules
//! (`contracts/wizloops-cloudroom.v1.md`) and the loop file format
//! (`contracts/wizloops-loop.v1.md`). OpenWiz's `openwiz loop` commands
//! (`contracts/loop-cli.v1.md`) call these.
//!
//! LC3 (#791), export: [`read_list`] makes the one `room-cli loop list
//! --json` read, and [`export_project`] maps each of a project's loops back
//! to a loop file and its check, or refuses it. [`marker_id`],
//! [`derive_id`] and [`render_script`] are the adapter's identity and
//! params rules, which plan and apply use in the other direction.

use std::collections::{BTreeMap, BTreeSet};
use std::time::Instant;

use openwiz_core::source::SourceError;
use serde_json::{Map, Value};

use crate::{allowlist::Invocation, process, source::CloudRoomSource};

/// The preamble's first line, after the check's first line.
pub const PREAMBLE_START: &str = "# wizloop: params from the loop file, as data";
/// The line that ends the preamble.
pub const PREAMBLE_END: &str = "# wizloop: the check";
/// The only check timeout Cloudroom runs ("Limits the adapter reports").
pub const CHECK_TIMEOUT: u64 = 60;
/// The first lines a check with params may start with.
const SHELLS: [&str; 4] = [
    "#!/bin/sh\n",
    "#!/bin/bash\n",
    "#!/usr/bin/env sh\n",
    "#!/usr/bin/env bash\n",
];

/// The `list` keys the adapter maps to a file.
const MAPPED: [&str; 11] = [
    "name",
    "cron",
    "timezone",
    "run_at",
    "webhook",
    "script",
    "new_thread",
    "agent",
    "secrets",
    "priority",
    "prompt",
];
/// The `list` keys the adapter reads but never writes: run state, and
/// Cloudroom's own identifiers.
const NOT_MAPPED: [&str; 8] = [
    "enabled",
    "last_error",
    "last_run_at",
    "next_run_at",
    "runs",
    "id",
    "project_id",
    "session_id",
];
const AGENT_KEYS: [&str; 3] = ["provider", "model", "reasoning"];

/// One refusal: the contract's `{"file", "code", "field", "message"}`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Refusal {
    pub file: String,
    pub code: String,
    pub field: String,
    pub message: String,
}

/// A param's value: a one-line string or an integer.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Param {
    Text(String),
    Integer(i64),
}

impl Param {
    fn json(&self) -> String {
        match self {
            Self::Text(s) => string(s),
            Self::Integer(n) => n.to_string(),
        }
    }
}

/// One of the project's loops, exported or refused.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Exported {
    /// The Cloudroom loop id.
    pub loop_id: String,
    /// The Cloudroom loop's name: a refusal's `file`.
    pub name: String,
    /// The loop file's id, or `None` when refused before one exists.
    pub id: Option<String>,
    /// Each file to write, as its path relative to the export folder and its
    /// text: `<id>.md`, then `<id>/check` for a loop with a script. Empty
    /// when refused.
    pub files: Vec<(String, String)>,
    /// For an unmarked loop, the file id an `--adopt` binds to this loop.
    pub binding: Option<String>,
    /// Empty when exported.
    pub refusals: Vec<Refusal>,
    /// Each key of the `list` item the adapter rules do not name
    /// (`agent.<key>` inside the agent), in byte order: a recorded gap, not
    /// a refusal. The file does not carry it.
    pub unmapped: Vec<String>,
}

fn malformed(detail: &str) -> SourceError {
    SourceError::Malformed {
        detail: format!("loop list is not the adapter's loop list: {detail}"),
    }
}

/// The one `room-cli loop list --json` read: every item of `automations`,
/// each an object with a string `id` and `project_id`. A duplicate key
/// anywhere refuses the whole read.
pub fn read_list(
    source: &CloudRoomSource,
    deadline: Instant,
) -> Result<Vec<Map<String, Value>>, SourceError> {
    let out = process::run(source.program(), &Invocation::LoopList, deadline)?;
    serde_json::from_slice::<openwiz_core::new_thread::read::StrictJson>(&out)
        .map_err(|_| malformed("not one JSON document with each key once"))?;
    let doc: Value =
        serde_json::from_slice(&out).map_err(|_| malformed("not one JSON document"))?;
    let items = doc
        .get("automations")
        .and_then(Value::as_array)
        .ok_or_else(|| malformed("no automations array"))?;
    items
        .iter()
        .map(|item| {
            let object = item
                .as_object()
                .filter(|o| {
                    ["id", "project_id"].iter().all(|k| {
                        o.get(*k)
                            .and_then(Value::as_str)
                            .is_some_and(|s| !s.is_empty())
                    })
                })
                .ok_or_else(|| malformed("an item has no id or project_id"))?;
            Ok(object.clone())
        })
        .collect()
}

/// The id a name's marker carries, and the name before it: a name that ends
/// with one space and `[wizloop:<id>]`, with a valid id.
pub fn marker_id(name: &str) -> Option<(&str, &str)> {
    let rest = name.strip_suffix(']')?;
    let at = rest.rfind(" [wizloop:")?;
    let id = &rest[at + " [wizloop:".len()..];
    valid_id(id).then_some((id, &name[..at]))
}

/// The id export derives from an unmarked loop's name, or `None` when that
/// is not a valid id: lowercase it, turn each run of characters other than
/// `a-z` and `0-9` into one `-`, trim `-` from both ends, keep at most 64
/// characters and trim a trailing `-`.
pub fn derive_id(name: &str) -> Option<String> {
    let mut id = String::new();
    for c in name.to_lowercase().chars() {
        if c.is_ascii_lowercase() || c.is_ascii_digit() {
            id.push(c);
        } else if !id.ends_with('-') {
            id.push('-');
        }
    }
    let id: String = id.trim_matches('-').chars().take(64).collect();
    let id = id.trim_end_matches('-').to_owned();
    valid_id(&id).then_some(id)
}

/// The format's `id`: `^[a-z0-9][a-z0-9-]{0,63}$`.
pub fn valid_id(id: &str) -> bool {
    (1..=64).contains(&id.len())
        && id
            .bytes()
            .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'-')
        && !id.starts_with('-')
}

/// The names of the params a check uses, in upper case: each reference
/// `WIZLOOP_PARAM_<run>`, where the text just before is not a letter, digit
/// or `_`, gives its whole run, in order (the format's "Params").
fn references(check: &str) -> Vec<&str> {
    const PREFIX: &str = "WIZLOOP_PARAM_";
    let word = |b: u8| b.is_ascii_alphanumeric() || b == b'_';
    let bytes = check.as_bytes();
    let mut out = Vec::new();
    let mut from = 0;
    while let Some(at) = check[from..].find(PREFIX).map(|i| i + from) {
        let start = at + PREFIX.len();
        if at == 0 || !word(bytes[at - 1]) {
            let len = bytes[start..].iter().take_while(|b| word(**b)).count();
            out.push(&check[start..start + len]);
        }
        from = start;
    }
    out
}

/// Each `{{name}}` placeholder in `text`, in order, and whether any `{{`
/// does not start one.
fn placeholders(text: &str) -> (Vec<&str>, bool) {
    let (mut names, mut bad) = (Vec::new(), false);
    let mut from = 0;
    while let Some(at) = text[from..].find("{{").map(|i| i + from) {
        let rest = &text[at + 2..];
        let len = rest
            .bytes()
            .take_while(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || *b == b'_')
            .count();
        let name = &rest[..len];
        if name.starts_with(|c: char| c.is_ascii_lowercase()) && rest[len..].starts_with("}}") {
            names.push(name);
            from = at + 2 + len + 2;
        } else {
            bad = true;
            from = at + 2;
        }
    }
    (names, bad)
}

fn param_name(name: &str) -> bool {
    name.starts_with(|c: char| c.is_ascii_lowercase())
        && name
            .bytes()
            .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'_')
}

/// The rendered script for a check `check` with `params` (the adapter's
/// "Params: the body and the check's preamble"): the check byte for byte
/// when it uses no param, else its first line, the preamble exporting each
/// param it uses in byte order of name, and the rest. `Err` is the
/// adapter's refusal code: `cf-check-preamble` or `cf-check-shell`.
pub fn render_script(
    check: &str,
    params: &BTreeMap<String, Param>,
) -> Result<String, &'static str> {
    let (first, rest) = match check.find('\n') {
        Some(end) => check.split_at(end + 1),
        None => (check, ""),
    };
    if rest.split('\n').next() == Some(PREAMBLE_START) {
        return Err("cf-check-preamble");
    }
    let used: BTreeSet<&str> = references(check).into_iter().collect();
    let carried: Vec<(&String, &Param)> = params
        .iter()
        .filter(|(name, _)| used.contains(name.to_ascii_uppercase().as_str()))
        .collect();
    if carried.is_empty() {
        return Ok(check.to_owned());
    }
    if !SHELLS.contains(&first) {
        return Err("cf-check-shell");
    }
    let mut script = format!("{first}{PREAMBLE_START}\n");
    for (name, value) in carried {
        let value = match value {
            Param::Text(s) => format!("'{}'", s.replace('\'', "'\\''")),
            Param::Integer(n) => n.to_string(),
        };
        script.push_str(&format!(
            "export WIZLOOP_PARAM_{}={value}\n",
            name.to_ascii_uppercase()
        ));
    }
    script.push_str(PREAMBLE_END);
    script.push('\n');
    script.push_str(rest);
    Ok(script)
}

/// Reads a script's preamble back ("Reading the preamble back"): the check
/// and the params it carries, or `None` when the script is not exactly what
/// [`render_script`] writes for them (`cf-export-preamble`).
pub fn read_script(script: &str) -> Option<(String, BTreeMap<String, Param>)> {
    let Some(end) = script.find('\n') else {
        return Some((script.to_owned(), BTreeMap::new()));
    };
    let (first, rest) = script.split_at(end + 1);
    if rest.split('\n').next() != Some(PREAMBLE_START) {
        return Some((script.to_owned(), BTreeMap::new()));
    }
    let mut lines = rest.split_inclusive('\n');
    if lines.next() != Some(&format!("{PREAMBLE_START}\n")) {
        return None;
    }
    let mut params = BTreeMap::new();
    let mut consumed = first.len() + PREAMBLE_START.len() + 1;
    let mut ended = false;
    for line in lines {
        consumed += line.len();
        if line == format!("{PREAMBLE_END}\n") {
            ended = true;
            break;
        }
        let (name, value) = line
            .strip_prefix("export WIZLOOP_PARAM_")?
            .strip_suffix('\n')?
            .split_once('=')?;
        let lower = name.to_ascii_lowercase();
        if !param_name(&lower) {
            return None;
        }
        let value = if let Some(inner) = value.strip_prefix('\'').and_then(|v| v.strip_suffix('\''))
        {
            Param::Text(inner.replace("'\\''", "'"))
        } else {
            let digits = value.strip_prefix('-').unwrap_or(value);
            let integer = digits == "0"
                || (digits.starts_with(|c: char| ('1'..='9').contains(&c))
                    && digits.bytes().all(|b| b.is_ascii_digit()));
            if !integer {
                return None;
            }
            Param::Integer(value.parse().ok()?)
        };
        params.insert(lower, value);
    }
    if !ended {
        return None;
    }
    let check = format!("{first}{}", &script[consumed..]);
    (render_script(&check, &params).ok()? == script).then_some((check, params))
}

/// A JSON string, as the format's one-line value.
fn string(s: &str) -> String {
    Value::from(s).to_string()
}

/// A JSON object in the given key order, written as the format's examples
/// write one: `{"a": 1, "b": 2}`.
fn json_object(pairs: &[(&str, String)]) -> String {
    let body: Vec<String> = pairs
        .iter()
        .map(|(k, v)| format!("{}: {v}", string(k)))
        .collect();
    format!("{{{}}}", body.join(", "))
}

fn control(c: char) -> bool {
    c <= '\u{1f}' || c == '\u{7f}'
}

/// The format's `name`.
fn valid_name(name: &str) -> bool {
    (1..=100).contains(&name.chars().count())
        && !name.chars().any(control)
        && name.chars().any(|c| !c.is_whitespace())
}

/// A number with no sign and no leading zero, in `range`.
fn cron_number(s: &str, range: (u32, u32)) -> Option<u32> {
    if s.is_empty() || !s.bytes().all(|b| b.is_ascii_digit()) || (s.len() > 1 && s.starts_with('0'))
    {
        return None;
    }
    s.parse().ok().filter(|n| (range.0..=range.1).contains(n))
}

/// The format's five cron fields.
fn valid_cron(cron: &str) -> bool {
    const RANGES: [(u32, u32); 5] = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)];
    let fields: Vec<&str> = cron.split(' ').collect();
    fields.len() == 5
        && fields.iter().zip(RANGES).all(|(field, range)| {
            *field == "*"
                || field.split(',').all(|item| {
                    let (base, step) = match item.split_once('/') {
                        Some((base, step)) => (base, Some(step)),
                        None => (item, None),
                    };
                    let step_ok = step.is_none_or(|s| {
                        !s.starts_with('0') && !s.is_empty() && s.bytes().all(|b| b.is_ascii_digit()) && s.parse::<u32>().is_ok()
                    });
                    let base_ok = (base == "*" && step.is_some())
                        || cron_number(base, range).is_some()
                        || base.split_once('-').is_some_and(|(a, b)| {
                            matches!((cron_number(a, range), cron_number(b, range)), (Some(a), Some(b)) if a <= b)
                        });
                    step_ok && base_ok
                })
        })
}

/// The format's `timezone`: `UTC` or `Area/City`.
fn valid_timezone(zone: &str) -> bool {
    let part = |s: &str| {
        !s.is_empty()
            && s.bytes()
                .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'_' | b'+' | b'-'))
    };
    if zone == "UTC" {
        return true;
    }
    let mut parts = zone.split('/');
    let first = parts.next().unwrap_or_default();
    let rest: Vec<&str> = parts.collect();
    first.starts_with(|c: char| c.is_ascii_alphabetic())
        && part(first)
        && !rest.is_empty()
        && rest.iter().all(|p| part(p))
}

/// The format's `at`: an RFC 3339 time with seconds and an explicit offset.
fn valid_at(at: &str) -> bool {
    let b = at.as_bytes();
    let digits = |r: std::ops::Range<usize>| {
        b.get(r.clone())
            .is_some_and(|s| s.iter().all(u8::is_ascii_digit))
    };
    let num = |r: std::ops::Range<usize>| at[r].parse::<u32>().unwrap_or(99);
    if b.len() < 20
        || !(digits(0..4)
            && b[4] == b'-'
            && digits(5..7)
            && b[7] == b'-'
            && digits(8..10)
            && b[10] == b'T')
        || !(digits(11..13) && b[13] == b':' && digits(14..16) && b[16] == b':' && digits(17..19))
    {
        return false;
    }
    if !((1..=12).contains(&num(5..7))
        && (1..=31).contains(&num(8..10))
        && num(11..13) <= 23
        && num(14..16) <= 59
        && num(17..19) <= 60)
    {
        return false;
    }
    let mut rest = &at[19..];
    if let Some(fraction) = rest.strip_prefix('.') {
        let len = fraction.bytes().take_while(u8::is_ascii_digit).count();
        if len == 0 {
            return false;
        }
        rest = &fraction[len..];
    }
    rest == "Z"
        || (rest.len() == 6
            && matches!(rest.as_bytes()[0], b'+' | b'-')
            && rest.as_bytes()[3] == b':'
            && rest[1..3].bytes().all(|b| b.is_ascii_digit())
            && rest[4..6].bytes().all(|b| b.is_ascii_digit())
            && rest[1..3].parse::<u32>().is_ok_and(|h| h <= 23)
            && rest[4..6].parse::<u32>().is_ok_and(|m| m <= 59))
}

fn valid_secret(s: &str) -> bool {
    s == ".env"
        || (s.starts_with(|c: char| c.is_ascii_uppercase())
            && s.bytes()
                .all(|b| b.is_ascii_uppercase() || b.is_ascii_digit() || b == b'_'))
}

/// One item's keys, typed as the adapter maps them; `Err` names the key
/// that is missing or of another type.
struct Item<'a> {
    name: &'a str,
    cron: Option<&'a str>,
    timezone: Option<&'a str>,
    run_at: Option<&'a str>,
    webhook: bool,
    new_thread: bool,
    script: Option<&'a str>,
    agent: Option<&'a Map<String, Value>>,
    secrets: Option<&'a Vec<Value>>,
    priority: i64,
    prompt: &'a str,
}

impl<'a> Item<'a> {
    fn read(o: &'a Map<String, Value>) -> Result<Self, String> {
        let bad = |k: &str| format!("{k} is missing or not the type the adapter maps");
        let text = |k: &str| o.get(k).and_then(Value::as_str).ok_or_else(|| bad(k));
        let text_or_null = |k: &str| match o.get(k) {
            Some(Value::Null) => Ok(None),
            Some(Value::String(s)) => Ok(Some(s.as_str())),
            _ => Err(bad(k)),
        };
        let flag = |k: &str| o.get(k).and_then(Value::as_bool).ok_or_else(|| bad(k));
        Ok(Self {
            name: text("name")?,
            cron: text_or_null("cron")?,
            timezone: text_or_null("timezone")?,
            run_at: text_or_null("run_at")?,
            webhook: flag("webhook")?,
            new_thread: flag("new_thread")?,
            script: text_or_null("script")?,
            agent: match o.get("agent") {
                Some(Value::Null) => None,
                Some(Value::Object(a)) => Some(a),
                _ => return Err(bad("agent")),
            },
            secrets: match o.get("secrets") {
                Some(Value::Null) => None,
                Some(Value::Array(s)) => Some(s),
                _ => return Err(bad("secrets")),
            },
            priority: o
                .get("priority")
                .and_then(Value::as_i64)
                .ok_or_else(|| bad("priority"))?,
            prompt: text("prompt")?,
        })
    }
}

/// Maps each loop of `project`, in `list` order, to its files or its
/// refusals. `Err` when a loop of the project lacks a key the adapter maps,
/// or has one of another type: the list is not the one the rules describe.
pub fn export_project(
    items: &[Map<String, Value>],
    project: &str,
) -> Result<Vec<Exported>, SourceError> {
    let ours: Vec<&Map<String, Value>> = items
        .iter()
        .filter(|o| o.get("project_id").and_then(Value::as_str) == Some(project))
        .collect();
    let typed = ours
        .iter()
        .map(|o| Item::read(o))
        .collect::<Result<Vec<_>, _>>()
        .map_err(|why| malformed(&why))?;
    let mut markers: BTreeMap<&str, usize> = BTreeMap::new();
    let mut derived: BTreeMap<String, usize> = BTreeMap::new();
    for item in &typed {
        match marker_id(item.name) {
            Some((id, _)) => *markers.entry(id).or_default() += 1,
            None => {
                if let Some(id) = derive_id(item.name) {
                    *derived.entry(id).or_default() += 1;
                }
            }
        }
    }
    Ok(ours
        .iter()
        .zip(&typed)
        .map(|(object, item)| export_one(object, item, &markers, &derived))
        .collect())
}

fn export_one(
    object: &Map<String, Value>,
    item: &Item,
    markers: &BTreeMap<&str, usize>,
    derived: &BTreeMap<String, usize>,
) -> Exported {
    let mut r = Refusals {
        file: item.name,
        list: Vec::new(),
    };

    // The file's id and name.
    let (id, name, binding) = match marker_id(item.name) {
        Some((id, name)) => {
            if markers.get(id).copied().unwrap_or(0) > 1 {
                r.refuse(
                    "cf-duplicate-marker",
                    "id",
                    format!("two Cloudroom loops in this project carry [wizloop:{id}]"),
                );
            }
            (Some(id.to_owned()), name, None)
        }
        None => match derive_id(item.name) {
            None => {
                r.invalid("id", "bad-id");
                (None, item.name, None)
            }
            Some(id) if derived.get(&id).copied().unwrap_or(0) > 1 => {
                r.refuse(
                    "cf-export-id",
                    "id",
                    "another unmarked loop in this project derives the same id".to_owned(),
                );
                (None, item.name, None)
            }
            Some(id) => (Some(id.clone()), item.name, Some(id)),
        },
    };

    // A key the adapter does not map, at the top or in the agent: named,
    // never refused, so a new Cloudroom setting is seen rather than lost.
    let mut unmapped: Vec<String> = object
        .keys()
        .filter(|k| !MAPPED.contains(&k.as_str()) && !NOT_MAPPED.contains(&k.as_str()))
        .cloned()
        .collect();
    if let Some(agent) = item.agent {
        unmapped.extend(
            agent
                .keys()
                .filter(|k| !AGENT_KEYS.contains(&k.as_str()))
                .map(|k| format!("agent.{k}")),
        );
    }
    unmapped.sort();

    // The file itself must be UTF-8 with LF line ends and no NUL.
    if item.prompt.contains(['\r', '\0']) {
        r.invalid("file", "encoding");
    }
    if !valid_name(name) {
        r.invalid("name", "bad-name");
    }

    // The trigger: exactly one of cron, run_at and webhook.
    let kinds = usize::from(item.cron.is_some())
        + usize::from(item.run_at.is_some())
        + usize::from(item.webhook);
    let trigger = match (kinds, item.cron, item.run_at) {
        (0, _, _) => {
            r.refuse(
                "cf-export-trigger",
                "trigger",
                "the loop has no cron, run time or webhook".to_owned(),
            );
            None
        }
        (2.., _, _) => {
            r.invalid("trigger", "trigger-kind");
            None
        }
        (_, Some(cron), _) => {
            if !valid_cron(cron) {
                r.invalid("trigger.cron", "bad-cron");
            }
            match item.timezone {
                None => r.invalid("trigger.timezone", "missing-field"),
                Some(zone) if !valid_timezone(zone) => {
                    r.invalid("trigger.timezone", "bad-timezone")
                }
                Some(_) => {}
            }
            Some(json_object(&[
                ("cron", string(cron)),
                ("timezone", string(item.timezone.unwrap_or_default())),
            ]))
        }
        (_, _, Some(at)) => {
            if !valid_at(at) {
                r.invalid("trigger.at", "bad-at");
            }
            Some(json_object(&[("at", string(at))]))
        }
        _ => Some(json_object(&[("webhook", "true".to_owned())])),
    };

    // The check and the params its preamble carries.
    let mut params = BTreeMap::new();
    let mut check = None;
    if let Some(script) = item.script {
        match read_script(script) {
            None => r.refuse(
                "cf-export-preamble",
                "check",
                "the script's params preamble is not one this adapter writes".to_owned(),
            ),
            Some((text, carried)) => {
                if text.contains('\0') {
                    r.invalid("check.run", "check-not-found");
                }
                for (name, value) in &carried {
                    if matches!(value, Param::Text(s) if s.contains(['\n', '\r', '\0'])) {
                        r.invalid(&format!("params.{name}"), "multiline-param");
                    }
                }
                params = carried;
                check = Some(text);
            }
        }
    }

    // The agent.
    let agent = item.agent.map(|agent| {
        let mut pairs = Vec::new();
        for key in AGENT_KEYS {
            match agent.get(key) {
                None => r.invalid(&format!("agent.{key}"), "missing-field"),
                Some(Value::String(v)) => {
                    if !(1..=100).contains(&v.chars().count())
                        || v.chars().any(|c| c.is_whitespace() || control(c))
                    {
                        r.invalid(&format!("agent.{key}"), "bad-agent");
                    }
                    pairs.push((key, string(v)));
                }
                Some(_) => r.invalid(&format!("agent.{key}"), "wrong-type"),
            }
        }
        json_object(&pairs)
    });

    // Secrets: null is every secret; a list is kept exactly.
    let secrets = match item.secrets {
        None => string("all"),
        Some(list) => {
            let mut seen = BTreeSet::new();
            let mut items = Vec::new();
            let mut ok = true;
            for secret in list {
                match secret.as_str() {
                    Some(s) if valid_secret(s) => {
                        if !seen.insert(s) {
                            ok = false;
                            r.invalid("secrets", "duplicate-secret");
                        }
                        items.push(string(s));
                    }
                    _ => {
                        ok = false;
                        r.invalid("secrets", "bad-secret");
                    }
                }
            }
            if ok && !item.new_thread && !items.is_empty() {
                r.invalid("secrets", "same-thread-secrets");
            }
            format!("[{}]", items.join(", "))
        }
    };
    if !(1..=4).contains(&item.priority) {
        r.invalid("priority", "bad-priority");
    }

    // The body: not empty, and no `{{`: export declares only the params the
    // check's preamble carries, so a placeholder could not read back.
    if item.prompt.chars().all(char::is_whitespace) {
        r.invalid("body", "empty-body");
    }
    let (names, bad) = placeholders(item.prompt);
    if bad {
        r.invalid("body", "bad-placeholder");
    }
    if !names.is_empty() {
        r.invalid("body", "undeclared-param");
    }

    // The check: no placeholder, and every reference set by the preamble.
    if let Some(text) = &check {
        if !placeholders(text).0.is_empty() {
            r.invalid("check", "param-in-check");
        }
        let declared: BTreeSet<String> = params.keys().map(|k| k.to_ascii_uppercase()).collect();
        if references(text).iter().any(|r| !declared.contains(*r)) {
            r.invalid("check", "undeclared-param");
        }
    }

    let (Some(id), Some(trigger), true) = (id.clone(), trigger, r.list.is_empty()) else {
        return Exported {
            loop_id: loop_id(object),
            name: item.name.to_owned(),
            id,
            files: Vec::new(),
            binding: None,
            refusals: r.list,
            unmapped,
        };
    };
    let mut lines = vec![
        format!("id: {}", string(&id)),
        format!("name: {}", string(name)),
        format!("trigger: {trigger}"),
    ];
    if check.is_some() {
        lines.push(format!(
            "check: {}",
            json_object(&[
                ("run", string(&format!("{id}/check"))),
                ("timeout", CHECK_TIMEOUT.to_string())
            ])
        ));
    }
    lines.push(format!(
        "thread: {}",
        string(if item.new_thread { "new" } else { "same" })
    ));
    if let Some(agent) = agent {
        lines.push(format!("agent: {agent}"));
    }
    lines.push(format!("secrets: {secrets}"));
    lines.push(format!("priority: {}", item.priority));
    if !params.is_empty() {
        let pairs: Vec<(&str, String)> =
            params.iter().map(|(k, v)| (k.as_str(), v.json())).collect();
        lines.push(format!("params: {}", json_object(&pairs)));
    }
    let mut files = vec![(
        format!("{id}.md"),
        format!("---\n{}\n---\n{}", lines.join("\n"), item.prompt),
    )];
    if let Some(text) = check {
        files.push((format!("{id}/check"), text));
    }
    Exported {
        loop_id: loop_id(object),
        name: item.name.to_owned(),
        id: Some(id),
        files,
        binding,
        refusals: r.list,
        unmapped,
    }
}

/// One loop's refusals, in the order found, each once.
struct Refusals<'a> {
    file: &'a str,
    list: Vec<Refusal>,
}

impl Refusals<'_> {
    fn refuse(&mut self, code: &str, field: &str, message: String) {
        let refusal = Refusal {
            file: self.file.to_owned(),
            code: code.to_owned(),
            field: field.to_owned(),
            message,
        };
        if !self.list.contains(&refusal) {
            self.list.push(refusal);
        }
    }

    /// `cf-export-invalid`: the mapped loop would break the format's `code`.
    fn invalid(&mut self, field: &str, code: &str) {
        self.refuse(
            "cf-export-invalid",
            field,
            format!("would be refused by the format as {code}"),
        );
    }
}

fn loop_id(object: &Map<String, Value>) -> String {
    object
        .get("id")
        .and_then(Value::as_str)
        .unwrap_or_default()
        .to_owned()
}
