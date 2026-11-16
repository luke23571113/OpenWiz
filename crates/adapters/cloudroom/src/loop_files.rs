//! Loop files in the pinned WizLoops format (`contracts/wizloops-loop.v1.md`,
//! WizLoops c7c2ed4), for `openwiz loop` (`contracts/loop-cli.v1.md`).
//!
//! LC2 (#790) owns the reader: [`read_loop`] checks one file's bytes as the
//! format's "Reading a file" says, [`read_loop_path`] reads one file from
//! disk, and [`read_loop_folder`] a folder, with its "Folders" and
//! "Catalogs" refusals. Each refusal's code, field and message are the
//! format's, exactly. A valid file also gives its [`LoopFile`]: the parsed
//! frontmatter with every default filled in, the body and the check's text,
//! which the plan and export (LC3, LC4) map to and from `room-cli`.
//!
//! The frontmatter's one-line JSON values are parsed here, not with
//! `serde_json`, because the format refuses a repeated key inside an object
//! and tells `2` from `2.0`, which a parse into `serde_json::Value` loses.
//!
//! LC3 (#791), export, by the adapter rules
//! (`contracts/wizloops-cloudroom.v1.md`): [`read_list`] makes the one `room-cli loop list
//! --json` read, and [`export_project`] maps each of a project's loops back
//! to a loop file and its check, or refuses it. [`marker_id`],
//! [`derive_id`] and [`render_script`] are the adapter's identity and
//! params rules, which plan and apply use in the other direction.

use std::collections::{BTreeMap, BTreeSet};
use std::io;
use std::path::Path;
use std::time::Instant;

use openwiz_core::source::SourceError;
use serde_json::{Map, Value};

use crate::{allowlist::Invocation, process, source::CloudRoomSource};

/// One refusal, as the format's tables write it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Refusal {
    pub code: &'static str,
    pub field: String,
    pub message: String,
}

impl Refusal {
    fn new(code: &'static str, field: impl Into<String>, message: impl Into<String>) -> Self {
        Self {
            code,
            field: field.into(),
            message: message.into(),
        }
    }
}

/// A valid loop file.
#[derive(Debug, Clone, PartialEq)]
pub struct LoopFile {
    /// The frontmatter as JSON, with `secrets`, `priority` and `params`
    /// filled in when left out (the format's defaults).
    pub frontmatter: Map<String, Value>,
    /// The prompt, as written: its placeholders are not replaced.
    pub body: String,
    /// The check script's text, when the file has a check.
    pub check: Option<String>,
}

/// One file's result.
#[derive(Debug, Clone, PartialEq)]
pub struct FileRead {
    /// The file's `id`, when it has one that passed `bad-id`.
    pub id: Option<String>,
    /// Every refusal, in the format's report order; empty when valid.
    pub refusals: Vec<Refusal>,
    /// The parsed file, only when it has no refusal.
    pub file: Option<LoopFile>,
}

/// A folder's result.
#[derive(Debug, Clone, PartialEq)]
pub struct FolderRead {
    /// Each `*.md` file directly inside, except `README.md`, in byte order
    /// of name.
    pub files: Vec<(String, FileRead)>,
    /// `duplicate-id`, then (in a catalog) `catalog-all-secrets`, each with
    /// the refused file's name.
    pub refusals: Vec<(String, Refusal)>,
}

/// What a check path names, for [`read_loop`].
pub enum CheckText {
    /// A regular file of UTF-8 text with no NUL.
    Text(String),
    /// Anything else: no file, a symlink, a folder or other bytes.
    NotFound,
}

/// Checks one loop file's bytes. `check` reads the text of a `check.run`
/// path that passed `bad-check-path`, relative to the loop file's folder.
pub fn read_loop(bytes: &[u8], check: &mut dyn FnMut(&str) -> CheckText) -> FileRead {
    let stop = |refusal| FileRead {
        id: None,
        refusals: vec![refusal],
        file: None,
    };
    // Step 1: encoding.
    let text = match std::str::from_utf8(bytes) {
        Ok(text) if !text.starts_with('\u{feff}') && !text.contains(['\0', '\r']) => text,
        _ => {
            return stop(Refusal::new(
                "encoding",
                "file",
                "must be UTF-8 with LF line ends, no byte order mark and no NUL",
            ));
        }
    };
    // Steps 2 and 3: the frontmatter's two `---` lines.
    let Some(rest) = text.strip_prefix("---\n") else {
        return stop(Refusal::new(
            "frontmatter-start",
            "file",
            "must start with a line of exactly ---",
        ));
    };
    let mut lines = Vec::new();
    let mut body = None;
    let mut at = 0;
    while at < rest.len() {
        let end = rest[at..].find('\n').map_or(rest.len(), |n| at + n);
        let line = &rest[at..end];
        if line == "---" {
            body = Some(rest.get(end + 1..).unwrap_or(""));
            break;
        }
        lines.push(line);
        at = end + 1;
    }
    let Some(body) = body else {
        return stop(Refusal::new(
            "frontmatter-end",
            "file",
            "frontmatter has no closing line of exactly ---",
        ));
    };
    // Step 4: each line is one `key: value`.
    let mut refusals = Vec::new();
    let mut fields: Vec<(&str, Json)> = Vec::new();
    for (n, line) in lines.iter().enumerate() {
        match read_line(line) {
            Ok((key, value)) => {
                if fields.iter().any(|(k, _)| *k == key) {
                    refusals.push(Refusal::new("duplicate-key", key, "appears more than once"));
                } else {
                    fields.push((key, value));
                }
            }
            Err(LineError::Syntax) => refusals.push(Refusal::new(
                "line-syntax",
                format!("line {}", n + 2),
                "must be \"key: value\" with one JSON value",
            )),
            Err(LineError::Json(key)) => {
                refusals.push(Refusal::new("json", key, "value is not one JSON value"));
            }
            Err(LineError::Duplicate(path)) => {
                refusals.push(Refusal::new(
                    "duplicate-key",
                    path,
                    "appears more than once",
                ));
            }
        }
    }
    if !refusals.is_empty() {
        return FileRead {
            id: None,
            refusals,
            file: None,
        };
    }
    Fields::new(fields, body, check).read()
}

/// Reads one loop file from disk. Its check is looked up beside it.
pub fn read_loop_path(path: &Path) -> io::Result<FileRead> {
    let bytes = std::fs::read(path)?;
    let folder = path.parent().unwrap_or(Path::new(""));
    Ok(read_loop(&bytes, &mut |run| check_text(folder, run)))
}

/// Reads a folder: every `*.md` file directly inside it, except
/// `README.md`, then the folder's refusals; with `catalog`, as a catalog.
pub fn read_loop_folder(dir: &Path, catalog: bool) -> io::Result<FolderRead> {
    let mut names = Vec::new();
    for entry in std::fs::read_dir(dir)? {
        let entry = entry?;
        let name = entry.file_name();
        let Some(name) = name.to_str() else {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "a file name is not UTF-8",
            ));
        };
        // A selected name whose metadata cannot be read fails the read,
        // never drops the file; a folder named `*.md` is not a loop file.
        if name.ends_with(".md")
            && name != "README.md"
            && std::fs::metadata(entry.path())?.is_file()
        {
            names.push(name.to_owned());
        }
    }
    names.sort_unstable();
    let mut files = Vec::new();
    for name in names {
        let read = read_loop_path(&dir.join(&name))?;
        files.push((name, read));
    }
    let mut refusals = Vec::new();
    for (i, (name, read)) in files.iter().enumerate() {
        let Some(id) = &read.id else { continue };
        if let Some((first, _)) = files[..i].iter().find(|(_, r)| r.id.as_ref() == Some(id)) {
            refusals.push((
                name.clone(),
                Refusal::new(
                    "duplicate-id",
                    "id",
                    format!("{id} is also the id of {first}"),
                ),
            ));
        }
    }
    if catalog {
        for (name, read) in &files {
            let all = read
                .file
                .as_ref()
                .is_some_and(|f| f.frontmatter.get("secrets") == Some(&Value::from("all")));
            if all {
                refusals.push((
                    name.clone(),
                    Refusal::new(
                        "catalog-all-secrets",
                        "secrets",
                        "must name each secret in a catalog file, never \"all\"",
                    ),
                ));
            }
        }
    }
    Ok(FolderRead { files, refusals })
}

/// The check script at `run` inside `folder`: a regular file, reached
/// through no symlink, of UTF-8 text with no NUL.
fn check_text(folder: &Path, run: &str) -> CheckText {
    let mut path = folder.to_path_buf();
    for segment in run.split('/') {
        path.push(segment);
        match std::fs::symlink_metadata(&path) {
            Ok(meta) if !meta.file_type().is_symlink() => {}
            _ => return CheckText::NotFound,
        }
    }
    if !path.is_file() {
        return CheckText::NotFound;
    }
    match std::fs::read(&path).map(String::from_utf8) {
        Ok(Ok(text)) if !text.contains('\0') => CheckText::Text(text),
        _ => CheckText::NotFound,
    }
}

// ---- The frontmatter subset ----

enum LineError {
    Syntax,
    Json(String),
    Duplicate(String),
}

fn is_name(s: &str) -> bool {
    let mut chars = s.chars();
    chars.next().is_some_and(|c| c.is_ascii_lowercase())
        && chars.all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == '_')
}

fn read_line(line: &str) -> Result<(&str, Json), LineError> {
    let (key, value) = line.split_once(": ").ok_or(LineError::Syntax)?;
    if !is_name(key) {
        return Err(LineError::Syntax);
    }
    if value.starts_with([' ', '\t']) || value.ends_with([' ', '\t']) {
        return Err(LineError::Syntax);
    }
    let mut parser = Parser {
        s: value.as_bytes(),
        i: 0,
        duplicate: None,
    };
    let parsed = parser.value(key);
    match parsed {
        Some(json) if parser.i == parser.s.len() => match parser.duplicate {
            Some(path) => Err(LineError::Duplicate(path)),
            None => Ok((key, json)),
        },
        _ => Err(LineError::Json(key.to_owned())),
    }
}

/// One JSON value, keeping each object's keys in order and whether a
/// number is an integer.
#[derive(Debug, Clone, PartialEq)]
enum Json {
    Null,
    Bool(bool),
    Number { text: String, integer: bool },
    String(String),
    Array(Vec<Json>),
    Object(Vec<(String, Json)>),
}

impl Json {
    fn to_value(&self) -> Value {
        match self {
            Self::Null => Value::Null,
            Self::Bool(b) => Value::Bool(*b),
            Self::Number { text, .. } => serde_json::from_str(text).unwrap_or(Value::Null),
            Self::String(s) => Value::String(s.clone()),
            Self::Array(items) => items.iter().map(Self::to_value).collect(),
            Self::Object(pairs) => Value::Object(
                pairs
                    .iter()
                    .map(|(k, v)| (k.clone(), v.to_value()))
                    .collect(),
            ),
        }
    }

    /// The integer's value; `None` for any other value. An integer too big
    /// for `i64` reads as `i64::MAX` or `i64::MIN`, outside every range.
    fn integer(&self) -> Option<i64> {
        match self {
            Self::Number {
                text,
                integer: true,
            } => Some(text.parse().unwrap_or(if text.starts_with('-') {
                i64::MIN
            } else {
                i64::MAX
            })),
            _ => None,
        }
    }
}

/// A strict RFC 8259 parser for one line's value. It records the first
/// repeated object key's dotted path instead of keeping either copy.
struct Parser<'a> {
    s: &'a [u8],
    i: usize,
    duplicate: Option<String>,
}

impl Parser<'_> {
    fn peek(&self) -> Option<u8> {
        self.s.get(self.i).copied()
    }

    fn space(&mut self) {
        while matches!(self.peek(), Some(b' ' | b'\t')) {
            self.i += 1;
        }
    }

    fn eat(&mut self, word: &[u8]) -> Option<()> {
        self.s[self.i..]
            .starts_with(word)
            .then(|| self.i += word.len())
    }

    fn value(&mut self, path: &str) -> Option<Json> {
        match self.peek()? {
            b'{' => {
                self.i += 1;
                let mut pairs: Vec<(String, Json)> = Vec::new();
                self.space();
                if self.eat(b"}").is_some() {
                    return Some(Json::Object(pairs));
                }
                loop {
                    self.space();
                    let key = self.string()?;
                    self.space();
                    self.eat(b":")?;
                    self.space();
                    let child = format!("{path}.{key}");
                    let value = self.value(&child)?;
                    if pairs.iter().any(|(k, _)| *k == key) {
                        self.duplicate.get_or_insert(child);
                    } else {
                        pairs.push((key, value));
                    }
                    self.space();
                    if self.eat(b",").is_none() {
                        self.eat(b"}")?;
                        return Some(Json::Object(pairs));
                    }
                }
            }
            b'[' => {
                self.i += 1;
                let mut items = Vec::new();
                self.space();
                if self.eat(b"]").is_some() {
                    return Some(Json::Array(items));
                }
                loop {
                    self.space();
                    items.push(self.value(path)?);
                    self.space();
                    if self.eat(b",").is_none() {
                        self.eat(b"]")?;
                        return Some(Json::Array(items));
                    }
                }
            }
            b'"' => self.string().map(Json::String),
            b't' => self.eat(b"true").map(|()| Json::Bool(true)),
            b'f' => self.eat(b"false").map(|()| Json::Bool(false)),
            b'n' => self.eat(b"null").map(|()| Json::Null),
            _ => self.number(),
        }
    }

    fn digits(&mut self) -> usize {
        let start = self.i;
        while self.peek().is_some_and(|c| c.is_ascii_digit()) {
            self.i += 1;
        }
        self.i - start
    }

    fn number(&mut self) -> Option<Json> {
        let start = self.i;
        let _ = self.eat(b"-");
        match self.peek()? {
            b'0' => self.i += 1,
            b'1'..=b'9' => {
                self.digits();
            }
            _ => return None,
        }
        let mut integer = true;
        if self.eat(b".").is_some() {
            integer = false;
            (self.digits() > 0).then_some(())?;
        }
        if matches!(self.peek(), Some(b'e' | b'E')) {
            integer = false;
            self.i += 1;
            if matches!(self.peek(), Some(b'+' | b'-')) {
                self.i += 1;
            }
            (self.digits() > 0).then_some(())?;
        }
        let text = std::str::from_utf8(&self.s[start..self.i]).ok()?.to_owned();
        Some(Json::Number { text, integer })
    }

    fn hex4(&mut self) -> Option<u32> {
        let hex = self.s.get(self.i..self.i + 4)?;
        self.i += 4;
        u32::from_str_radix(std::str::from_utf8(hex).ok()?, 16).ok()
    }

    fn string(&mut self) -> Option<String> {
        self.eat(b"\"")?;
        let mut out = Vec::new();
        loop {
            let c = self.peek()?;
            self.i += 1;
            match c {
                b'"' => return String::from_utf8(out).ok(),
                0..=0x1f => return None,
                b'\\' => {
                    let e = self.peek()?;
                    self.i += 1;
                    let ch = match e {
                        b'"' => '"',
                        b'\\' => '\\',
                        b'/' => '/',
                        b'b' => '\u{8}',
                        b'f' => '\u{c}',
                        b'n' => '\n',
                        b'r' => '\r',
                        b't' => '\t',
                        b'u' => {
                            let high = self.hex4()?;
                            let code = if (0xd800..0xdc00).contains(&high) {
                                self.eat(b"\\u")?;
                                let low = self.hex4()?;
                                (0xdc00..0xe000).contains(&low).then_some(())?;
                                0x10000 + ((high - 0xd800) << 10) + (low - 0xdc00)
                            } else {
                                high
                            };
                            char::from_u32(code)?
                        }
                        _ => return None,
                    };
                    out.extend_from_slice(ch.encode_utf8(&mut [0; 4]).as_bytes());
                }
                _ => out.push(c),
            }
        }
    }
}

// ---- Fields (step 5), body and params (step 6) ----

/// The refusal codes of the format's fields table, in its order: one
/// line's refusals are reported in this order.
const FIELD_ORDER: &[&str] = &[
    "unknown-field",
    "missing-field",
    "wrong-type",
    "bad-id",
    "bad-name",
    "trigger-kind",
    "bad-cron",
    "bad-timezone",
    "bad-at",
    "bad-in",
    "bad-webhook",
    "bad-check-path",
    "check-not-found",
    "bad-timeout",
    "bad-thread",
    "bad-agent",
    "bad-secret",
    "duplicate-secret",
    "same-thread-secrets",
    "bad-priority",
    "bad-param-name",
    "multiline-param",
];

const REQUIRED: [&str; 4] = ["id", "name", "trigger", "thread"];

struct Fields<'a, 'c> {
    fields: Vec<(&'a str, Json)>,
    body: &'a str,
    check: &'c mut dyn FnMut(&str) -> CheckText,
    refusals: Vec<Refusal>,
    id: Option<String>,
    /// The check's text, once read; `None` with `check_unread` when a check
    /// is given but could not be read.
    check_text: Option<String>,
    check_unread: bool,
}

fn wrong_type(field: &str, kind: &str) -> Refusal {
    Refusal::new("wrong-type", field, format!("must be {kind}"))
}

fn unknown(field: String) -> Refusal {
    Refusal::new("unknown-field", field, "is not a field of loop v1")
}

fn missing(field: impl Into<String>) -> Refusal {
    Refusal::new("missing-field", field, "is required")
}

impl<'a, 'c> Fields<'a, 'c> {
    fn new(
        fields: Vec<(&'a str, Json)>,
        body: &'a str,
        check: &'c mut dyn FnMut(&str) -> CheckText,
    ) -> Self {
        Self {
            fields,
            body,
            check,
            refusals: Vec::new(),
            id: None,
            check_text: None,
            check_unread: false,
        }
    }

    fn get(&self, key: &str) -> Option<&Json> {
        self.fields.iter().find(|(k, _)| *k == key).map(|(_, v)| v)
    }

    fn read(mut self) -> FileRead {
        let same_thread = self.get("thread") == Some(&Json::String("same".into()));
        let fields = std::mem::take(&mut self.fields);
        for (key, value) in &fields {
            let mut line = self.field(key, value, same_thread);
            line.sort_by_key(|r| FIELD_ORDER.iter().position(|c| *c == r.code));
            self.refusals.append(&mut line);
        }
        self.fields = fields;
        self.params_in_text();
        for key in REQUIRED {
            if self.get(key).is_none() {
                self.refusals.push(missing(key));
            }
        }
        let file = self.refusals.is_empty().then(|| {
            let mut frontmatter: Map<String, Value> = self
                .fields
                .iter()
                .map(|(k, v)| ((*k).to_owned(), v.to_value()))
                .collect();
            frontmatter
                .entry("secrets")
                .or_insert_with(|| Value::Array(Vec::new()));
            frontmatter.entry("priority").or_insert(Value::from(3));
            frontmatter
                .entry("params")
                .or_insert_with(|| Value::Object(Map::new()));
            LoopFile {
                frontmatter,
                body: self.body.to_owned(),
                check: self.check_text.clone(),
            }
        });
        FileRead {
            id: self.id,
            refusals: self.refusals,
            file,
        }
    }

    /// One frontmatter line's refusals, in any order.
    fn field(&mut self, key: &str, value: &Json, same_thread: bool) -> Vec<Refusal> {
        let mut out = Vec::new();
        let string = match value {
            Json::String(s) => Some(s.as_str()),
            _ => None,
        };
        match key {
            "id" => match string {
                None => out.push(wrong_type(key, "a string")),
                Some(id) if is_id(id) => self.id = Some(id.to_owned()),
                Some(_) => out.push(Refusal::new(
                    "bad-id",
                    key,
                    "must be 1 to 64 lowercase letters, digits and hyphens, starting with a letter or digit",
                )),
            },
            "name" => match string {
                None => out.push(wrong_type(key, "a string")),
                Some(name) => {
                    let count = name.chars().count();
                    if !(1..=100).contains(&count)
                        || name.chars().all(char::is_whitespace)
                        || name.chars().any(|c| c < ' ' || c == '\u{7f}')
                    {
                        out.push(Refusal::new(
                            "bad-name",
                            key,
                            "must be 1 to 100 characters, not all whitespace, with no control characters",
                        ));
                    }
                }
            },
            "trigger" => trigger(value, &mut out),
            "check" => self.check_field(value, &mut out),
            "thread" => match string {
                None => out.push(wrong_type(key, "a string")),
                Some("same" | "new") => {}
                Some(_) => out.push(Refusal::new("bad-thread", key, "must be \"same\" or \"new\"")),
            },
            "agent" => agent(value, &mut out),
            "secrets" => secrets(value, same_thread, &mut out),
            "priority" => match value.integer() {
                None => out.push(wrong_type(key, "an integer")),
                Some(n) if (1..=4).contains(&n) => {}
                Some(_) => out.push(Refusal::new("bad-priority", key, "must be 1 to 4")),
            },
            "params" => params(value, &mut out),
            _ => out.push(unknown(key.to_owned())),
        }
        out
    }

    fn check_field(&mut self, value: &Json, out: &mut Vec<Refusal>) {
        self.check_unread = true;
        let Json::Object(pairs) = value else {
            out.push(wrong_type("check", "an object"));
            return;
        };
        for (k, _) in pairs {
            if k != "run" && k != "timeout" {
                out.push(unknown(format!("check.{k}")));
            }
        }
        let get = |name: &str| pairs.iter().find(|(k, _)| k == name).map(|(_, v)| v);
        match get("run") {
            None => out.push(missing("check.run")),
            Some(Json::String(run)) => {
                let path_ok = !run.starts_with('/')
                    && !run.contains('\\')
                    && run
                        .split('/')
                        .all(|s| !s.is_empty() && s != "." && s != "..");
                if !path_ok {
                    out.push(Refusal::new(
                        "bad-check-path",
                        "check.run",
                        "must be a relative path inside the loop's folder, with no . or .. segments",
                    ));
                } else {
                    match (self.check)(run) {
                        CheckText::Text(text) => {
                            self.check_text = Some(text);
                            self.check_unread = false;
                        }
                        CheckText::NotFound => out.push(Refusal::new(
                            "check-not-found",
                            "check.run",
                            "must name an existing regular file of UTF-8 text",
                        )),
                    }
                }
            }
            Some(_) => out.push(wrong_type("check.run", "a string")),
        }
        match get("timeout").map(|t| (t, t.integer())) {
            None => out.push(missing("check.timeout")),
            Some((_, None)) => out.push(wrong_type("check.timeout", "an integer")),
            Some((_, Some(n))) if (1..=900).contains(&n) => {}
            Some(_) => out.push(Refusal::new(
                "bad-timeout",
                "check.timeout",
                "must be 1 to 900 seconds",
            )),
        }
    }

    /// Step 6: the body's placeholders, the check's text and unused params.
    fn params_in_text(&mut self) {
        // With `params` of the wrong type, its names are unknown, so no use
        // or declaration is checked against it.
        let declared: Option<Vec<String>> = match self.get("params") {
            None => Some(Vec::new()),
            Some(Json::Object(pairs)) => Some(
                pairs
                    .iter()
                    .map(|(k, _)| k.clone())
                    .filter(|k| is_name(k))
                    .collect(),
            ),
            Some(_) => None,
        };
        if self.body.chars().all(char::is_whitespace) {
            self.refusals.push(Refusal::new(
                "empty-body",
                "body",
                "the prompt must not be empty",
            ));
        }
        let mut used: Vec<String> = Vec::new();
        let body = self.body;
        let mut at = 0;
        while let Some(n) = body[at..].find("{{") {
            let start = at + n;
            match placeholder(&body[start..]) {
                Some(name) => {
                    if declared
                        .as_ref()
                        .is_some_and(|d| !d.iter().any(|k| k == name))
                    {
                        self.refusals.push(Refusal::new(
                            "undeclared-param",
                            "body",
                            format!("uses {{{{{name}}}}}, which params does not declare"),
                        ));
                    }
                    used.push(name.to_owned());
                    at = start + name.len() + 4;
                }
                None => {
                    self.refusals.push(Refusal::new(
                        "bad-placeholder",
                        "body",
                        "{{ must start a placeholder {{name}}",
                    ));
                    at = start + 2;
                }
            }
        }
        if let Some(text) = self.check_text.clone() {
            for found in check_uses(&text) {
                match found {
                    CheckUse::Placeholder(name) => self.refusals.push(Refusal::new(
                        "param-in-check",
                        "check",
                        format!(
                            "uses {{{{{name}}}}}; a check reads it as $WIZLOOP_PARAM_{}",
                            name.to_ascii_uppercase()
                        ),
                    )),
                    CheckUse::Reference(run) => {
                        let known = declared
                            .as_ref()
                            .map(|d| d.iter().find(|k| k.to_ascii_uppercase() == run).cloned());
                        match known {
                            Some(Some(name)) => used.push(name),
                            Some(None) => self.refusals.push(Refusal::new(
                                "undeclared-param",
                                "check",
                                format!("uses $WIZLOOP_PARAM_{run}, which params does not declare"),
                            )),
                            None => {}
                        }
                    }
                }
            }
        }
        // A check that could not be read may use any param, so only a
        // readable check (or none) lets a param be called unused.
        if !self.check_unread {
            for name in declared.unwrap_or_default() {
                if !used.contains(&name) {
                    self.refusals.push(Refusal::new(
                        "unused-param",
                        format!("params.{name}"),
                        "is declared but never used",
                    ));
                }
            }
        }
    }
}

fn is_id(s: &str) -> bool {
    let b = s.as_bytes();
    (1..=64).contains(&b.len())
        && (b[0].is_ascii_lowercase() || b[0].is_ascii_digit())
        && b.iter()
            .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || *c == b'-')
}

/// The param name of the placeholder `text` starts with, if it is one.
fn placeholder(text: &str) -> Option<&str> {
    let inner = text.strip_prefix("{{")?;
    let end = inner.find("}}")?;
    let name = &inner[..end];
    is_name(name).then_some(name)
}

enum CheckUse {
    Placeholder(String),
    Reference(String),
}

/// The check's placeholders and `WIZLOOP_PARAM_` references, in text order.
fn check_uses(text: &str) -> Vec<CheckUse> {
    const PREFIX: &str = "WIZLOOP_PARAM_";
    let word = |c: u8| c.is_ascii_alphanumeric() || c == b'_';
    let bytes = text.as_bytes();
    let mut out = Vec::new();
    let mut at = 0;
    while let Some(n) = text[at..].find("{{") {
        let start = at + n;
        if let Some(name) = placeholder(&text[start..]) {
            out.push((start, CheckUse::Placeholder(name.to_owned())));
            at = start + name.len() + 4;
        } else {
            at = start + 2;
        }
    }
    for (start, _) in text.match_indices(PREFIX) {
        if start > 0 && word(bytes[start - 1]) {
            continue;
        }
        let run_start = start + PREFIX.len();
        let run_end = bytes[run_start..]
            .iter()
            .position(|c| !word(*c))
            .map_or(bytes.len(), |n| run_start + n);
        out.push((
            start,
            CheckUse::Reference(text[run_start..run_end].to_owned()),
        ));
    }
    out.sort_by_key(|(place, _)| *place);
    out.into_iter().map(|(_, found)| found).collect()
}

fn trigger(value: &Json, out: &mut Vec<Refusal>) {
    let Json::Object(pairs) = value else {
        out.push(wrong_type("trigger", "an object"));
        return;
    };
    const KINDS: [&str; 4] = ["cron", "at", "in", "webhook"];
    let kinds: Vec<&str> = pairs
        .iter()
        .map(|(k, _)| k.as_str())
        .filter(|k| KINDS.contains(k))
        .collect();
    // `timezone` is unknown only beside one kind that is not `cron`.
    let lone_cron = kinds.len() == 1 && kinds[0] == "cron";
    for (k, _) in pairs {
        let known =
            KINDS.contains(&k.as_str()) || (k == "timezone" && (lone_cron || kinds.len() != 1));
        if !known {
            out.push(unknown(format!("trigger.{k}")));
        }
    }
    if kinds.len() != 1 {
        out.push(Refusal::new(
            "trigger-kind",
            "trigger",
            "must have exactly one of cron, at, in or webhook",
        ));
        return;
    }
    let get = |name: &str| pairs.iter().find(|(k, _)| k == name).map(|(_, v)| v);
    let kind = kinds[0];
    let field = format!("trigger.{kind}");
    let value = get(kind).expect("the kind's key");
    if kind == "webhook" {
        if *value != Json::Bool(true) {
            out.push(Refusal::new("bad-webhook", field, "must be true"));
        }
        return;
    }
    let Json::String(text) = value else {
        out.push(wrong_type(&field, "a string"));
        if kind == "cron" {
            timezone(get("timezone"), out);
        }
        return;
    };
    match kind {
        "cron" => {
            if !is_cron(text) {
                out.push(Refusal::new(
                    "bad-cron",
                    field,
                    "must be five cron fields: minute hour day-of-month month day-of-week",
                ));
            }
            timezone(get("timezone"), out);
        }
        "at" => {
            if !is_rfc3339(text) {
                out.push(Refusal::new(
                    "bad-at",
                    field,
                    "must be an RFC 3339 time with seconds and an offset",
                ));
            }
        }
        _ => {
            let digits = text.strip_suffix(['m', 'h', 'd']).unwrap_or("");
            if !is_number(digits) || digits == "0" {
                out.push(Refusal::new(
                    "bad-in",
                    field,
                    "must be a whole number from 1 followed by m, h or d",
                ));
            }
        }
    }
}

fn timezone(value: Option<&Json>, out: &mut Vec<Refusal>) {
    match value {
        None => out.push(missing("trigger.timezone")),
        Some(Json::String(zone)) => {
            if zone != "UTC" && !is_area_city(zone) {
                out.push(Refusal::new(
                    "bad-timezone",
                    "trigger.timezone",
                    "must be UTC or an IANA zone such as Area/City",
                ));
            }
        }
        Some(_) => out.push(wrong_type("trigger.timezone", "a string")),
    }
}

/// `^[A-Za-z][A-Za-z0-9_+-]*(/[A-Za-z0-9_+-]+)+$`.
fn is_area_city(zone: &str) -> bool {
    let part = |s: &str| {
        !s.is_empty()
            && s.bytes()
                .all(|c| c.is_ascii_alphanumeric() || b"_+-".contains(&c))
    };
    let mut parts = zone.split('/');
    let area = parts.next().unwrap_or("");
    let rest: Vec<&str> = parts.collect();
    area.as_bytes().first().is_some_and(u8::is_ascii_alphabetic)
        && part(area)
        && !rest.is_empty()
        && rest.iter().all(|p| part(p))
}

/// A decimal number with no sign and no leading zero (`0` itself is fine).
fn is_number(s: &str) -> bool {
    !s.is_empty() && s.bytes().all(|c| c.is_ascii_digit()) && (s == "0" || !s.starts_with('0'))
}

fn is_cron(cron: &str) -> bool {
    const RANGES: [(u32, u32); 5] = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)];
    let fields: Vec<&str> = cron.split(' ').collect();
    fields.len() == 5
        && fields.iter().zip(RANGES).all(|(field, (lo, hi))| {
            let number = |s: &str| {
                is_number(s)
                    .then(|| s.parse::<u32>().ok())
                    .flatten()
                    .filter(|n| (lo..=hi).contains(n))
            };
            let base = |s: &str| match s.split_once('-') {
                Some((a, b)) => matches!((number(a), number(b)), (Some(a), Some(b)) if a <= b),
                None => number(s).is_some(),
            };
            *field == "*"
                || field.split(',').all(|item| match item.split_once('/') {
                    Some((b, step)) => {
                        (b == "*" || base(b))
                            && is_number(step)
                            && step.parse::<u32>().is_ok_and(|n| n >= 1)
                    }
                    None => base(item),
                })
        })
}

/// `YYYY-MM-DDTHH:MM:SS[.f]` then `Z` or `±HH:MM`, a real date and time.
fn is_rfc3339(at: &str) -> bool {
    let b = at.as_bytes();
    let num = |range: std::ops::Range<usize>| -> Option<u32> {
        let s = at.get(range)?;
        s.bytes()
            .all(|c| c.is_ascii_digit())
            .then(|| s.parse().ok())
            .flatten()
    };
    let shape = b.len() >= 20
        && b[4] == b'-'
        && b[7] == b'-'
        && b[10] == b'T'
        && b[13] == b':'
        && b[16] == b':';
    if !shape {
        return false;
    }
    let (Some(year), Some(month), Some(day), Some(hour), Some(minute), Some(second)) = (
        num(0..4),
        num(5..7),
        num(8..10),
        num(11..13),
        num(14..16),
        num(17..19),
    ) else {
        return false;
    };
    let leap = year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
    let days = match month {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 if leap => 29,
        2 => 28,
        _ => return false,
    };
    if !(1..=days).contains(&day) || hour > 23 || minute > 59 || second > 59 {
        return false;
    }
    let mut rest = &at[19..];
    if let Some(fraction) = rest.strip_prefix('.') {
        let n = fraction.bytes().take_while(u8::is_ascii_digit).count();
        if n == 0 {
            return false;
        }
        rest = &fraction[n..];
    }
    if rest == "Z" {
        return true;
    }
    let ob = rest.as_bytes();
    ob.len() == 6
        && (ob[0] == b'+' || ob[0] == b'-')
        && ob[3] == b':'
        && rest[1..3].bytes().all(|c| c.is_ascii_digit())
        && rest[4..6].bytes().all(|c| c.is_ascii_digit())
        && rest[1..3].parse::<u32>().is_ok_and(|h| h <= 23)
        && rest[4..6].parse::<u32>().is_ok_and(|m| m <= 59)
}

fn agent(value: &Json, out: &mut Vec<Refusal>) {
    let Json::Object(pairs) = value else {
        out.push(wrong_type("agent", "an object"));
        return;
    };
    const KEYS: [&str; 3] = ["provider", "model", "reasoning"];
    for (k, _) in pairs {
        if !KEYS.contains(&k.as_str()) {
            out.push(unknown(format!("agent.{k}")));
        }
    }
    for key in KEYS {
        let field = format!("agent.{key}");
        match pairs.iter().find(|(k, _)| k == key).map(|(_, v)| v) {
            None => out.push(missing(field)),
            Some(Json::String(s)) => {
                let count = s.chars().count();
                if !(1..=100).contains(&count)
                    || s.chars().any(|c| c.is_whitespace() || c.is_control())
                {
                    out.push(Refusal::new(
                        "bad-agent",
                        field,
                        "must be 1 to 100 characters with no whitespace",
                    ));
                }
            }
            Some(_) => out.push(wrong_type(&field, "a string")),
        }
    }
}

fn secrets(value: &Json, same_thread: bool, out: &mut Vec<Refusal>) {
    let items = match value {
        Json::String(s) if s == "all" => return,
        Json::Array(items) => items,
        _ => {
            out.push(wrong_type("secrets", "an array or \"all\""));
            return;
        }
    };
    let before = out.len();
    let mut seen: Vec<&str> = Vec::new();
    for item in items {
        let ok = match item {
            Json::String(s) => {
                let named = s == ".env"
                    || (s.as_bytes().first().is_some_and(u8::is_ascii_uppercase)
                        && s.bytes()
                            .all(|c| c.is_ascii_uppercase() || c.is_ascii_digit() || c == b'_'));
                if seen.contains(&s.as_str()) {
                    out.push(Refusal::new(
                        "duplicate-secret",
                        "secrets",
                        format!("names {s} more than once"),
                    ));
                }
                seen.push(s);
                named
            }
            _ => false,
        };
        if !ok {
            out.push(Refusal::new(
                "bad-secret",
                "secrets",
                "each item must be an environment variable name or \".env\"",
            ));
        }
    }
    if same_thread && out.len() == before && !items.is_empty() {
        out.push(Refusal::new(
            "same-thread-secrets",
            "secrets",
            "must be [] or \"all\" when thread is \"same\": a same-thread run keeps its thread's environment",
        ));
    }
}

fn params(value: &Json, out: &mut Vec<Refusal>) {
    let Json::Object(pairs) = value else {
        out.push(wrong_type("params", "an object"));
        return;
    };
    for (name, value) in pairs {
        let named = is_name(name);
        if !named {
            out.push(Refusal::new(
                "bad-param-name",
                "params",
                format!(
                    "name {name} must be lowercase letters, digits and underscores, starting with a letter"
                ),
            ));
        }
        match value {
            Json::String(s) => {
                if named && s.contains(['\n', '\r', '\0']) {
                    out.push(Refusal::new(
                        "multiline-param",
                        format!("params.{name}"),
                        "must be one line, with no line break or NUL",
                    ));
                }
            }
            _ if value.integer().is_some() => {}
            _ => out.push(wrong_type(
                &format!("params.{name}"),
                "a string or an integer",
            )),
        }
    }
}

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

/// One export refusal: the contract's `{"file", "code", "field", "message"}`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExportRefusal {
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
    pub refusals: Vec<ExportRefusal>,
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
    is_id(id).then_some((id, &name[..at]))
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
    is_id(&id).then_some(id)
}

/// The names of the params a check uses, in upper case: each reference
/// `WIZLOOP_PARAM_<run>`, where the text just before is not a letter, digit
/// or `_`, gives its whole run, in order (the format's "Params").
fn references(check: &str) -> Vec<String> {
    check_uses(check)
        .into_iter()
        .filter_map(|found| match found {
            CheckUse::Reference(name) => Some(name),
            CheckUse::Placeholder(_) => None,
        })
        .collect()
}

/// Each `{{name}}` placeholder in `text`, in order, and whether any `{{`
/// does not start one.
fn placeholders(text: &str) -> (Vec<&str>, bool) {
    let (mut names, mut bad) = (Vec::new(), false);
    let mut from = 0;
    while let Some(at) = text[from..].find("{{").map(|i| i + from) {
        if let Some(name) = placeholder(&text[at..]) {
            names.push(name);
            from = at + name.len() + 4;
        } else {
            bad = true;
            from = at + 2;
        }
    }
    (names, bad)
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
    let used: BTreeSet<String> = references(check).into_iter().collect();
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
        if !is_name(&lower) {
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
            if !is_cron(cron) {
                r.invalid("trigger.cron", "bad-cron");
            }
            match item.timezone {
                None => r.invalid("trigger.timezone", "missing-field"),
                Some(zone) if zone != "UTC" && !is_area_city(zone) => {
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
        if references(text).iter().any(|r| !declared.contains(r)) {
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
    list: Vec<ExportRefusal>,
}

impl Refusals<'_> {
    fn refuse(&mut self, code: &str, field: &str, message: String) {
        let refusal = ExportRefusal {
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

#[cfg(test)]
mod tests {
    use super::*;

    fn read(text: &str) -> Vec<(&'static str, String)> {
        read_loop(text.as_bytes(), &mut |_| CheckText::NotFound)
            .refusals
            .into_iter()
            .map(|r| (r.code, r.field))
            .collect()
    }

    const HEAD: &str = "---\nid: \"a\"\nname: \"A\"\nthread: \"new\"\n";

    // catches: a reader that collapses `{"a":1,"a":2}` or reads `2.0` as an
    // integer, both of which serde_json would accept silently.
    #[test]
    fn repeated_keys_and_non_integers_are_refused() {
        assert_eq!(
            read(&format!(
                "{HEAD}trigger: {{\"webhook\": true}}\nparams: {{\"x\": {{\"y\": 1, \"y\": 2}}}}\n---\nGo.\n"
            )),
            [("duplicate-key", "params.x.y".to_owned())]
        );
        assert_eq!(
            read(&format!(
                "{HEAD}trigger: {{\"webhook\": true}}\npriority: 2e0\n---\nGo.\n"
            )),
            [("wrong-type", "priority".to_owned())]
        );
    }

    // catches: refusals from several fields reported out of the format's
    // order (frontmatter lines, then body, then missing fields last).
    #[test]
    fn several_refusals_come_in_report_order() {
        let got = read(
            "---\npriority: 9\nbudget: 1\ntrigger: {\"at\": \"soon\", \"timezone\": \"UTC\"}\n---\n {{x}} {{\n",
        );
        assert_eq!(
            got,
            [
                ("bad-priority", "priority".to_owned()),
                ("unknown-field", "budget".to_owned()),
                ("unknown-field", "trigger.timezone".to_owned()),
                ("bad-at", "trigger.at".to_owned()),
                ("undeclared-param", "body".to_owned()),
                ("bad-placeholder", "body".to_owned()),
                ("missing-field", "id".to_owned()),
                ("missing-field", "name".to_owned()),
                ("missing-field", "thread".to_owned()),
            ]
        );
    }
}
