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
//! LC4 (#792, plan) builds on that reader: [`read_paths`] reads the paths
//! `plan` is given, [`parse_loop_list`] reads `room-cli loop list` with the
//! same strict JSON parser, and [`plan`] maps each valid file to its
//! `room-cli loop create` or `update` command and compares it with its
//! managed loop, as `contracts/wizloops-cloudroom.v1.md` says. Nothing here
//! writes.

use std::collections::{BTreeMap, BTreeSet};
use std::io;
use std::path::Path;
use std::time::Instant;

use openwiz_core::source::SourceError;
use serde_json::{Map, Value, json};

use crate::{
    allowlist::{
        Invocation, LoopAgentArgs, LoopCreateArgs, LoopReschedule, LoopTrigger, LoopUpdateArgs,
        ThreadId,
    },
    process,
    source::CloudRoomSource,
};

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

    /// JSON's whitespace. A frontmatter line never holds a line feed (lines
    /// end there) or a carriage return (step 1 refuses it), so only `loop
    /// list`'s document (LC4) meets those two.
    fn space(&mut self) {
        while matches!(self.peek(), Some(b' ' | b'\t' | b'\n' | b'\r')) {
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

// ---- LC4 (#792): plan ----

// ------------------------------------------------------------ the loop model

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Trigger {
    Cron { cron: String, timezone: String },
    At(String),
    In(String),
    Webhook,
}

impl Trigger {
    /// The trigger in the loop file's shape.
    pub fn to_json(&self) -> Value {
        match self {
            Trigger::Cron { cron, timezone } => json!({"cron": cron, "timezone": timezone}),
            Trigger::At(at) => json!({"at": at}),
            Trigger::In(delay) => json!({"in": delay}),
            Trigger::Webhook => json!({"webhook": true}),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Check {
    pub run: String,
    pub timeout: i64,
    /// The check script's text, read from beside the loop file.
    pub text: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Agent {
    pub provider: String,
    pub model: String,
    pub reasoning: String,
}

impl Agent {
    fn to_json(&self) -> Value {
        json!({"provider": self.provider, "model": self.model, "reasoning": self.reasoning})
    }
}

/// `secrets`: every secret, or the names listed (empty for none).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Secrets {
    All,
    List(Vec<String>),
}

impl Secrets {
    fn to_json(&self) -> Value {
        match self {
            Secrets::All => json!("all"),
            Secrets::List(items) => json!(items),
        }
    }

    /// `--secrets`' value: `none`, `all`, or the names joined by `,`.
    fn flag(&self) -> String {
        match self {
            Secrets::All => "all".into(),
            Secrets::List(items) if items.is_empty() => "none".into(),
            Secrets::List(items) => items.join(","),
        }
    }

    /// Equal as the adapter compares: a list as a set; `all` only to `all`.
    fn same(&self, other: &Secrets) -> bool {
        match (self, other) {
            (Secrets::All, Secrets::All) => true,
            (Secrets::List(a), Secrets::List(b)) => {
                a.iter().collect::<BTreeSet<_>>() == b.iter().collect::<BTreeSet<_>>()
            }
            _ => false,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Param {
    Str(String),
    /// An integer, as its decimal digits.
    Int(String),
}

/// One valid loop file in the adapter's terms, from LC2's [`LoopFile`]:
/// what plan maps to `room-cli` and compares with a [`LiveLoop`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Loop {
    pub id: String,
    pub name: String,
    pub trigger: Trigger,
    pub check: Option<Check>,
    /// `thread`: `"new"` is true, `"same"` false.
    pub new_thread: bool,
    pub agent: Option<Agent>,
    pub secrets: Secrets,
    pub priority: i64,
    /// In byte order of name.
    pub params: Vec<(String, Param)>,
    pub body: String,
}

/// A file LC2's reader accepted, as a [`Loop`]. `None` only for a shape
/// the reader refuses, which a valid file never has.
fn adapter_loop(file: &LoopFile) -> Option<Loop> {
    let get = |key: &str| file.frontmatter.get(key);
    let text = |v: &Value| v.as_str().map(str::to_owned);
    let trigger = get("trigger")?;
    let trigger = if let Some(cron) = trigger.get("cron") {
        Trigger::Cron {
            cron: text(cron)?,
            timezone: text(trigger.get("timezone")?)?,
        }
    } else if let Some(at) = trigger.get("at") {
        Trigger::At(text(at)?)
    } else if let Some(delay) = trigger.get("in") {
        Trigger::In(text(delay)?)
    } else {
        trigger.get("webhook")?;
        Trigger::Webhook
    };
    let check = match get("check") {
        None => None,
        Some(check) => Some(Check {
            run: text(check.get("run")?)?,
            timeout: check.get("timeout")?.as_i64()?,
            text: file.check.clone()?,
        }),
    };
    let agent = match get("agent") {
        None => None,
        Some(agent) => Some(Agent {
            provider: text(agent.get("provider")?)?,
            model: text(agent.get("model")?)?,
            reasoning: text(agent.get("reasoning")?)?,
        }),
    };
    let secrets = match get("secrets")? {
        Value::Array(items) => Secrets::List(items.iter().map(text).collect::<Option<_>>()?),
        _ => Secrets::All,
    };
    let params = get("params")?
        .as_object()?
        .iter()
        .map(|(name, value)| match value {
            Value::String(s) => Some((name.clone(), Param::Str(s.clone()))),
            Value::Number(n) => Some((name.clone(), Param::Int(n.to_string()))),
            _ => None,
        })
        .collect::<Option<_>>()?;
    Some(Loop {
        id: text(get("id")?)?,
        name: text(get("name")?)?,
        trigger,
        check,
        new_thread: get("thread")?.as_str()? == "new",
        agent,
        secrets,
        priority: get("priority")?.as_i64()?,
        params,
        body: file.body.clone(),
    })
}

/// Reads each path `plan` is given with LC2's reader: a loop file, or a
/// folder, whose files are shown as the folder's path, `/` and the name,
/// each with its folder refusals. `Err` names the first path that can't be
/// read.
pub fn read_paths(paths: &[String]) -> Result<Vec<(String, FileRead)>, String> {
    let mut files = Vec::new();
    for path in paths {
        let failed = |e: io::Error| format!("{path}: {e}");
        if !std::fs::metadata(path).map_err(failed)?.is_dir() {
            files.push((
                path.clone(),
                read_loop_path(Path::new(path)).map_err(failed)?,
            ));
            continue;
        }
        let mut folder = read_loop_folder(Path::new(path), false).map_err(failed)?;
        for (name, refusal) in folder.refusals {
            if let Some((_, read)) = folder.files.iter_mut().find(|(n, _)| *n == name) {
                read.refusals.push(refusal);
                read.file = None;
            }
        }
        let shown = path.strip_suffix('/').unwrap_or(path);
        files.extend(
            folder
                .files
                .into_iter()
                .map(|(name, read)| (format!("{shown}/{name}"), read)),
        );
    }
    Ok(files)
}

impl Json {
    fn get(&self, key: &str) -> Option<&Json> {
        match self {
            Json::Object(pairs) => pairs.iter().find(|(k, _)| k == key).map(|(_, v)| v),
            _ => None,
        }
    }

    fn as_str(&self) -> Option<&str> {
        match self {
            Json::String(s) => Some(s),
            _ => None,
        }
    }
}

/// One whole JSON document (`loop list`), keys in order, or `None` for
/// anything else or a repeated key. `serde_json` checks it first, so its
/// nesting limit bounds the order-keeping parser's recursion.
fn parse_document(bytes: &[u8]) -> Option<Json> {
    serde_json::from_slice::<Value>(bytes).ok()?;
    let mut parser = Parser {
        s: bytes,
        i: 0,
        duplicate: None,
    };
    parser.space();
    let value = parser.value("")?;
    parser.space();
    (parser.i == bytes.len() && parser.duplicate.is_none()).then_some(value)
}

/// Each cron field's allowed values, or `None` when the cron is not the
/// format's five fields.
fn cron_fields(cron: &str) -> Option<Vec<BTreeSet<u32>>> {
    let fields: Vec<&str> = cron.split(' ').collect();
    if fields.len() != 5 {
        return None;
    }
    let ranges = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)];
    fields
        .iter()
        .zip(ranges)
        .map(|(field, (min, max))| cron_field(field, min, max))
        .collect()
}

fn cron_number(text: &str, min: u32, max: u32) -> Option<u32> {
    if text.is_empty()
        || !text.bytes().all(|b| b.is_ascii_digit())
        || (text.len() > 1 && text.starts_with('0'))
    {
        return None;
    }
    text.parse().ok().filter(|n| (min..=max).contains(n))
}

fn cron_field(field: &str, min: u32, max: u32) -> Option<BTreeSet<u32>> {
    if field == "*" {
        return Some((min..=max).collect());
    }
    let mut values = BTreeSet::new();
    for item in field.split(',') {
        let (base, step) = match item.split_once('/') {
            Some((base, step)) => (base, Some(cron_number(step, 1, u32::MAX)?)),
            None => (item, None),
        };
        let (from, to) = if base == "*" {
            step?;
            (min, max)
        } else if let Some((a, b)) = base.split_once('-') {
            let (a, b) = (cron_number(a, min, max)?, cron_number(b, min, max)?);
            if a > b {
                return None;
            }
            (a, b)
        } else {
            let n = cron_number(base, min, max)?;
            (n, if step.is_some() { max } else { n })
        };
        let step = step.unwrap_or(1) as usize;
        values.extend((from..=to).step_by(step));
    }
    Some(values)
}

/// An RFC 3339 time with seconds and an offset, as seconds since the epoch
/// and its fraction's digits (trailing zeros dropped), so that two
/// spellings of one instant are equal.
pub fn instant(time: &str) -> Option<(i64, String)> {
    let b = time.as_bytes();
    let digits = |range: std::ops::Range<usize>| -> Option<i64> {
        let part = b.get(range)?;
        if !part.iter().all(u8::is_ascii_digit) {
            return None;
        }
        std::str::from_utf8(part).ok()?.parse().ok()
    };
    if b.len() < 20
        || b[4] != b'-'
        || b[7] != b'-'
        || !matches!(b[10], b'T' | b't')
        || b[13] != b':'
        || b[16] != b':'
    {
        return None;
    }
    let (year, month, day) = (digits(0..4)?, digits(5..7)?, digits(8..10)?);
    let (hour, minute, second) = (digits(11..13)?, digits(14..16)?, digits(17..19)?);
    let mut at = 19;
    let mut fraction = String::new();
    if b[at] == b'.' {
        at += 1;
        let start = at;
        while b.get(at).is_some_and(u8::is_ascii_digit) {
            at += 1;
        }
        if at == start {
            return None;
        }
        fraction = time[start..at].trim_end_matches('0').to_owned();
    }
    let offset = match b.get(at..)? {
        [b'Z' | b'z'] => 0,
        [sign @ (b'+' | b'-'), _, _, b':', _, _] => {
            let hh = digits(at + 1..at + 3)?;
            let mm = digits(at + 4..at + 6)?;
            if hh > 23 || mm > 59 {
                return None;
            }
            let minutes = hh * 60 + mm;
            if *sign == b'+' { minutes } else { -minutes }
        }
        _ => return None,
    };
    let leap = (year % 4 == 0 && year % 100 != 0) || year % 400 == 0;
    let month_days = [
        31,
        if leap { 29 } else { 28 },
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ];
    if !(1..=12).contains(&month)
        || day < 1
        || day > month_days[(month - 1) as usize]
        || hour > 23
        || minute > 59
        || second > 60
    {
        return None;
    }
    // Days from the civil date (Howard Hinnant's algorithm).
    let y = if month <= 2 { year - 1 } else { year };
    let era = y.div_euclid(400);
    let yoe = y - era * 400;
    let mp = (month + 9) % 12;
    let doy = (153 * mp + 2) / 5 + day - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    let days = era * 146_097 + doe - 719_468;
    let seconds = days * 86_400 + hour * 3600 + minute * 60 + second - offset * 60;
    Some((seconds, fraction))
}

// ------------------------------------------------------- the adapter's maps

/// The marker the adapter writes at the end of a managed loop's name.
pub fn marker(id: &str) -> String {
    format!("[wizloop:{id}]")
}

/// A Cloudroom name's id and display name, when it ends with a marker.
pub fn split_marker(name: &str) -> Option<(&str, &str)> {
    let open = name.rfind(" [wizloop:")?;
    let id = name[open + " [wizloop:".len()..].strip_suffix(']')?;
    is_id(id).then(|| (id, &name[..open]))
}

/// The id export derives from an unmarked loop's name.
pub fn derived_id(name: &str) -> String {
    let mut id = String::new();
    for c in name.to_lowercase().chars() {
        if c.is_ascii_lowercase() || c.is_ascii_digit() {
            id.push(c);
        } else if !id.ends_with('-') {
            id.push('-');
        }
    }
    let id: String = id.trim_matches('-').chars().take(64).collect();
    id.trim_end_matches('-').to_owned()
}

fn param_text(param: &Param) -> &str {
    match param {
        Param::Str(s) | Param::Int(s) => s,
    }
}

/// The body with its placeholders replaced: Cloudroom's `prompt`.
pub fn rendered_body(file: &Loop) -> String {
    let mut out = String::new();
    let mut at = 0;
    while let Some(start) = file.body[at..].find("{{").map(|i| at + i) {
        out.push_str(&file.body[at..start]);
        match placeholder(&file.body[start..]).and_then(|name| {
            let end = start + name.len() + 4;
            Some((file.params.iter().find(|(n, _)| n == name)?, end))
        }) {
            Some(((_, param), end)) => {
                out.push_str(param_text(param));
                at = end;
            }
            None => {
                out.push_str("{{");
                at = start + 2;
            }
        }
    }
    out.push_str(&file.body[at..]);
    out
}

pub const PREAMBLE_START: &str = "# wizloop: params from the loop file, as data";
pub const PREAMBLE_END: &str = "# wizloop: the check";
const SHELLS: [&str; 4] = [
    "#!/bin/sh\n",
    "#!/bin/bash\n",
    "#!/usr/bin/env sh\n",
    "#!/usr/bin/env bash\n",
];

/// The params a check uses, in byte order of their names.
fn carried_params(file: &Loop, check: &Check) -> Vec<(String, Param)> {
    let runs: BTreeSet<String> = check_uses(&check.text)
        .into_iter()
        .filter_map(|r| match r {
            CheckUse::Reference(run) => Some(run),
            CheckUse::Placeholder(_) => None,
        })
        .collect();
    let mut carried: Vec<(String, Param)> = file
        .params
        .iter()
        .filter(|(name, _)| runs.contains(&name.to_ascii_uppercase()))
        .cloned()
        .collect();
    carried.sort_by(|a, b| a.0.cmp(&b.0));
    carried
}

/// The check with its params preamble: Cloudroom's `script`. Call it only
/// for a check the adapter accepts (see [`file_refusals`]).
pub fn rendered_script(file: &Loop, check: &Check) -> String {
    let carried = carried_params(file, check);
    if carried.is_empty() {
        return check.text.clone();
    }
    let (first, rest) = check.text.split_once('\n').unwrap_or((&check.text, ""));
    let mut out = format!("{first}\n{PREAMBLE_START}\n");
    for (name, param) in carried {
        let value = match param {
            Param::Int(digits) => digits,
            Param::Str(s) => format!("'{}'", s.replace('\'', "'\\''")),
        };
        out.push_str(&format!(
            "export WIZLOOP_PARAM_{}={value}\n",
            name.to_ascii_uppercase()
        ));
    }
    out.push_str(PREAMBLE_END);
    out.push('\n');
    out.push_str(rest);
    out
}

/// Minutes of the day a cron's minute and hour fields allow, checked for
/// two runs less than 15 minutes apart (across midnight too).
fn too_frequent(cron: &str) -> bool {
    let Some(fields) = cron_fields(cron) else {
        return false;
    };
    let minutes: Vec<u32> = fields[1]
        .iter()
        .flat_map(|h| fields[0].iter().map(move |m| h * 60 + m))
        .collect();
    let gaps = minutes.windows(2).map(|w| w[1] - w[0]);
    let wrap = minutes
        .first()
        .zip(minutes.last())
        .map(|(first, last)| first + 1440 - last);
    gaps.chain(wrap).any(|gap| gap < 15)
}

/// The adapter's refusals of a file, whatever the live loop: its limits.
pub fn file_refusals(file: &Loop) -> Vec<Refusal> {
    let mut refusals = Vec::new();
    if let Trigger::Cron { cron, .. } = &file.trigger
        && file.check.is_none()
        && too_frequent(cron)
    {
        refusals.push(Refusal::new(
            "cf-too-frequent",
            "trigger.cron",
            "Cloudroom runs a loop without a check at most every 15 minutes",
        ));
    }
    if let Some(check) = &file.check {
        if !carried_params(file, check).is_empty()
            && !SHELLS.iter().any(|s| check.text.starts_with(s))
        {
            refusals.push(Refusal::new("cf-check-shell", "check.run", "Cloudroom passes params to a check through a shell preamble; its first line must be #!/bin/sh, #!/bin/bash, #!/usr/bin/env sh or #!/usr/bin/env bash"));
        }
        if check.text.split('\n').nth(1) == Some(PREAMBLE_START) {
            refusals.push(Refusal::new(
                "cf-check-preamble",
                "check.run",
                "the check's second line is the adapter's preamble line; change that line",
            ));
        }
        if check.timeout != 60 {
            refusals.push(Refusal::new(
                "cf-check-timeout",
                "check.timeout",
                "Cloudroom runs a check for exactly 60 seconds; set the timeout to 60",
            ));
        }
    }
    if !file.new_thread && file.agent.is_some() {
        refusals.push(Refusal::new(
            "cf-agent-same-thread",
            "agent",
            "Cloudroom sets an agent only for new-thread loops",
        ));
    }
    refusals
}

/// One `room-cli` call, built by the allowlist and never run here. Its
/// `@prompt` and `@script` operands stand for the files apply writes;
/// `files` holds their text.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RoomCommand {
    pub invocation: Invocation,
    pub files: Vec<(String, String)>,
}

impl RoomCommand {
    /// The arguments after `room-cli`, exactly as the allowlist builds them.
    pub fn argv(&self) -> Vec<String> {
        self.invocation.argv()
    }

    pub fn to_json(&self) -> Value {
        let files: Map<String, Value> = self
            .files
            .iter()
            .map(|(k, v)| (k.clone(), Value::String(v.clone())))
            .collect();
        json!({"argv": self.argv(), "files": files})
    }
}

fn agent_args(agent: &Agent) -> LoopAgentArgs {
    LoopAgentArgs {
        provider: agent.provider.clone(),
        model: agent.model.clone(),
        reasoning: agent.reasoning.clone(),
    }
}

/// The adapter's `room-cli loop create` for a file.
pub fn create_command(file: &Loop) -> RoomCommand {
    let mut files = vec![("@prompt".to_owned(), rendered_body(file))];
    let script_file = file.check.as_ref().map(|check| {
        files.push(("@script".into(), rendered_script(file, check)));
        "@script".to_owned()
    });
    let trigger = match &file.trigger {
        Trigger::Cron { cron, timezone } => LoopTrigger::Cron {
            cron: cron.clone(),
            timezone: timezone.clone(),
        },
        Trigger::At(at) => LoopTrigger::At(at.clone()),
        Trigger::In(delay) => LoopTrigger::In(delay.clone()),
        Trigger::Webhook => LoopTrigger::Webhook,
    };
    let invocation = Invocation::LoopCreate(LoopCreateArgs {
        name: format!("{} {}", file.name, marker(&file.id)),
        prompt_file: "@prompt".into(),
        trigger,
        new_thread: file.new_thread,
        script_file,
        agent: file.agent.as_ref().map(agent_args),
        priority: file.priority.to_string(),
        secrets: file.secrets.flag(),
    });
    RoomCommand { invocation, files }
}

// ------------------------------------------------------- `room-cli loop list`

/// One Cloudroom loop from `loop list`, with the keys the adapter maps.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LiveLoop {
    pub loop_id: String,
    /// The same id, as `room-cli loop update` takes it.
    pub address: ThreadId,
    pub project_id: String,
    pub name: String,
    /// The trigger in the file's shape, or the `cf-export-trigger` case.
    pub trigger: Option<Trigger>,
    pub new_thread: bool,
    pub script: Option<String>,
    pub agent: Option<Agent>,
    pub secrets: Secrets,
    pub priority: i64,
    pub prompt: String,
    pub enabled: bool,
    /// Keys `list` gave that the adapter neither maps nor knows as run
    /// state (`agent.<key>` inside the agent), in the order given.
    pub unmapped: Vec<String>,
}

/// Every key of a `list` loop the adapter knows: the mapped ones, its own
/// identifiers and the run state it leaves out of a file.
const LIST_KEYS: [&str; 19] = [
    "id",
    "project_id",
    "session_id",
    "name",
    "cron",
    "timezone",
    "run_at",
    "webhook",
    "new_thread",
    "script",
    "agent",
    "secrets",
    "priority",
    "prompt",
    "enabled",
    "last_error",
    "last_run_at",
    "next_run_at",
    "runs",
];

impl CloudRoomSource {
    /// `room-cli loop list --json`, read once: every loop on the account.
    pub fn loop_files_list(&self, deadline: Instant) -> Result<Vec<LiveLoop>, SourceError> {
        let out = process::run(self.program(), &Invocation::LoopList, deadline)?;
        parse_loop_list(&out).map_err(|detail| SourceError::Malformed { detail })
    }
}

/// `{"automations": [...]}`, each loop with every key the adapter maps.
/// Strict: a duplicate key, a missing key or a wrong type refuses the whole
/// list, so plan never compares against part of an account.
pub fn parse_loop_list(stdout: &[u8]) -> Result<Vec<LiveLoop>, String> {
    let bad = |what: &str| {
        format!("loop list is not the expected {{\"automations\": [...]}} JSON: {what}")
    };
    let doc =
        parse_document(stdout).ok_or_else(|| bad("not one JSON document with unique keys"))?;
    let Some(Json::Array(items)) = doc.get("automations") else {
        return Err(bad("no automations array"));
    };
    let mut seen = BTreeSet::new();
    items
        .iter()
        .map(|item| {
            let loop_id = item
                .get("id")
                .and_then(Json::as_str)
                .filter(|s| !s.is_empty())
                .ok_or_else(|| bad("a loop without an id"))?;
            if !seen.insert(loop_id.to_owned()) {
                return Err(bad("two loops with one id"));
            }
            let field = |key: &str| {
                item.get(key)
                    .ok_or_else(|| bad(&format!("{loop_id} has no {key}")))
            };
            let string = |key: &str| {
                field(key)?
                    .as_str()
                    .map(str::to_owned)
                    .ok_or_else(|| bad(&format!("{loop_id}'s {key} is not a string")))
            };
            let optional = |key: &str| match field(key)? {
                Json::Null => Ok(None),
                Json::String(s) => Ok(Some(s.clone())),
                _ => Err(bad(&format!("{loop_id}'s {key} is not a string or null"))),
            };
            let boolean = |key: &str| match field(key)? {
                Json::Bool(b) => Ok(*b),
                _ => Err(bad(&format!("{loop_id}'s {key} is not a boolean"))),
            };
            let cron = optional("cron")?;
            let timezone = optional("timezone")?;
            let run_at = optional("run_at")?;
            let webhook = boolean("webhook")?;
            let trigger = match (cron, run_at, webhook) {
                (Some(cron), None, false) => {
                    timezone.map(|timezone| Trigger::Cron { cron, timezone })
                }
                (None, Some(at), false) => Some(Trigger::At(at)),
                (None, None, true) => Some(Trigger::Webhook),
                _ => None,
            };
            let agent = match field("agent")? {
                Json::Null => None,
                agent @ Json::Object(_) => {
                    let part = |key: &str| {
                        agent
                            .get(key)
                            .and_then(Json::as_str)
                            .map(str::to_owned)
                            .ok_or_else(|| bad(&format!("{loop_id}'s agent has no {key}")))
                    };
                    Some(Agent {
                        provider: part("provider")?,
                        model: part("model")?,
                        reasoning: part("reasoning")?,
                    })
                }
                _ => return Err(bad(&format!("{loop_id}'s agent is not an object or null"))),
            };
            let secrets = match field("secrets")? {
                Json::Null => Secrets::All,
                Json::Array(items) => Secrets::List(
                    items
                        .iter()
                        .map(|s| s.as_str().map(str::to_owned))
                        .collect::<Option<_>>()
                        .ok_or_else(|| bad(&format!("{loop_id}'s secrets are not strings")))?,
                ),
                _ => return Err(bad(&format!("{loop_id}'s secrets are not a list or null"))),
            };
            let priority = field("priority")?
                .integer()
                .ok_or_else(|| bad(&format!("{loop_id}'s priority is not an integer")))?;
            let mut unmapped: Vec<String> = Vec::new();
            if let Json::Object(members) = item {
                for (key, _) in members {
                    if !LIST_KEYS.contains(&key.as_str()) {
                        unmapped.push(key.clone());
                    }
                }
            }
            if let Some(Json::Object(members)) = item.get("agent") {
                for (key, _) in members {
                    if !["provider", "model", "reasoning"].contains(&key.as_str()) {
                        unmapped.push(format!("agent.{key}"));
                    }
                }
            }
            Ok(LiveLoop {
                unmapped,
                loop_id: loop_id.to_owned(),
                address: ThreadId::parse(loop_id).map_err(|_| {
                    bad(&format!("{loop_id} is not an id that can be passed safely"))
                })?,
                project_id: string("project_id")?,
                name: string("name")?,
                trigger,
                new_thread: boolean("new_thread")?,
                script: optional("script")?,
                agent,
                secrets,
                priority,
                prompt: string("prompt")?,
                enabled: boolean("enabled")?,
            })
        })
        .collect()
}

// ------------------------------------------------------------------- plan

/// One difference: the field, the file's value and the live value, both in
/// the loop file's shape.
#[derive(Debug, Clone, PartialEq)]
pub struct Difference {
    pub field: &'static str,
    pub file: Value,
    pub live: Value,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    Create,
    Update,
    None,
    Refused,
}

impl Action {
    /// `none` or `refused`; `create` and `update` are their command's
    /// subcommand, as the allowlist spells it (see [`PlanItem::action_word`]).
    fn quiet_word(self) -> Option<&'static str> {
        match self {
            Action::None => Some("none"),
            Action::Refused => Some("refused"),
            Action::Create | Action::Update => None,
        }
    }
}

/// One file's plan.
#[derive(Debug, Clone, PartialEq)]
pub struct PlanItem {
    pub file: String,
    pub id: Option<String>,
    pub action: Action,
    pub loop_id: Option<String>,
    pub paused: bool,
    pub commands: Vec<RoomCommand>,
    pub differences: Vec<Difference>,
    pub refusals: Vec<Refusal>,
    pub notes: Vec<String>,
}

impl PlanItem {
    /// The contract's `action`: a create or an update is named by its one
    /// command's subcommand, so the word is spelled once, in the allowlist.
    pub fn action_word(&self) -> String {
        match (self.action.quiet_word(), self.commands.first()) {
            (Some(word), _) => word.to_owned(),
            (None, Some(command)) => command.argv()[1].clone(),
            (None, None) => "refused".to_owned(),
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct Plan {
    pub items: Vec<PlanItem>,
    /// `(loop, name)` for each loop of the project with no marker and no binding.
    pub unmanaged: Vec<(String, String)>,
    /// `(loop, id)` for each managed loop with no file.
    pub orphans: Vec<(String, String)>,
}

const SAME_THREAD_NOTE: &str =
    "a same-thread run keeps its thread's own environment, whatever secrets says";

/// Plans every file against the project's loops, as the adapter's "How plan
/// compares" says. `now` is the current time in seconds since the epoch,
/// for `cf-at-past`. Reads and writes nothing.
pub fn plan(
    files: &[(String, FileRead)],
    live: &[LiveLoop],
    project: &str,
    bindings: &[(String, String)],
    now: i64,
) -> Plan {
    let in_project: Vec<&LiveLoop> = live.iter().filter(|l| l.project_id == project).collect();
    let managed = |id: &str| -> Vec<&LiveLoop> {
        in_project
            .iter()
            .copied()
            .filter(|l| split_marker(&l.name).is_some_and(|(m, _)| m == id))
            .collect()
    };
    // Earlier files claim an id; a later file with the same id is refused.
    let mut claimed: BTreeMap<String, String> = BTreeMap::new();
    let mut bound: BTreeSet<String> = BTreeSet::new();
    let mut items = Vec::new();
    for (shown, read) in files {
        let mut item = PlanItem {
            file: shown.clone(),
            id: read.id.clone(),
            action: Action::Refused,
            loop_id: None,
            paused: false,
            commands: Vec::new(),
            differences: Vec::new(),
            refusals: Vec::new(),
            notes: Vec::new(),
        };
        let Some(file) = read.file.as_ref().and_then(adapter_loop) else {
            item.refusals = read.refusals.clone();
            items.push(item);
            continue;
        };
        let file = &file;
        if let Some(other) = claimed.get(&file.id) {
            item.refusals.push(Refusal::new(
                "duplicate-id",
                "id",
                format!("{} is also the id of {other}", file.id),
            ));
            items.push(item);
            continue;
        }
        claimed.insert(file.id.clone(), shown.clone());
        let marked = managed(&file.id);
        let binding: Vec<&String> = bindings
            .iter()
            .filter(|(id, _)| *id == file.id)
            .map(|(_, l)| l)
            .collect();
        let adopt_refusal = |loop_id: &str, reason: &str| {
            Refusal::new(
                "cf-adopt-binding",
                "id",
                format!("the binding to Cloudroom loop {loop_id} cannot be used: {reason}"),
            )
        };
        let mut adopted = false;
        let target: Option<&LiveLoop> = if marked.len() > 1 {
            item.refusals.push(Refusal::new(
                "cf-duplicate-marker",
                "id",
                format!(
                    "two Cloudroom loops in this project carry {}",
                    marker(&file.id)
                ),
            ));
            None
        } else if let Some(loop_id) = binding.first() {
            let subject = in_project.iter().find(|l| l.loop_id == **loop_id);
            let reason = if binding.len() > 1 {
                Some("the id is bound more than once")
            } else if bindings.iter().filter(|(_, l)| l == *loop_id).count() > 1 {
                Some("another binding names the same loop")
            } else if subject.is_none() {
                Some("it is not a loop in this project")
            } else if subject.is_some_and(|l| split_marker(&l.name).is_some()) {
                Some("it already carries a marker")
            } else if !marked.is_empty() {
                Some("a loop in this project already carries this file's marker")
            } else {
                None
            };
            match reason {
                Some(reason) => {
                    item.refusals.push(adopt_refusal(loop_id, reason));
                    None
                }
                None => {
                    adopted = true;
                    bound.insert((*loop_id).clone());
                    subject.copied()
                }
            }
        } else {
            marked.first().copied()
        };
        if !item.refusals.is_empty() {
            items.push(item);
            continue;
        }
        if target.is_none()
            && in_project
                .iter()
                .any(|l| split_marker(&l.name).is_none() && derived_id(&l.name) == file.id)
        {
            item.refusals.push(Refusal::new("cf-unmarked-match", "id", "an unmarked Cloudroom loop in this project has this name; adopt it or choose another id"));
            items.push(item);
            continue;
        }
        if !file.new_thread {
            item.notes.push(SAME_THREAD_NOTE.into());
        }
        match target {
            None => plan_create(&mut item, file, now),
            Some(live) => plan_update(&mut item, file, live, adopted),
        }
        items.push(item);
    }
    let ids: BTreeSet<&str> = files.iter().filter_map(|(_, f)| f.id.as_deref()).collect();
    let unmanaged = in_project
        .iter()
        .filter(|l| split_marker(&l.name).is_none() && !bound.contains(&l.loop_id))
        .map(|l| (l.loop_id.clone(), l.name.clone()))
        .collect();
    let orphans = in_project
        .iter()
        .filter_map(|l| split_marker(&l.name).map(|(id, _)| (l, id)))
        .filter(|(_, id)| !ids.contains(id))
        .map(|(l, id)| (l.loop_id.clone(), id.to_owned()))
        .collect();
    Plan {
        items,
        unmanaged,
        orphans,
    }
}

fn plan_create(item: &mut PlanItem, file: &Loop, now: i64) {
    let mut refusals = Vec::new();
    if let Trigger::At(at) = &file.trigger
        && instant(at).is_some_and(|(seconds, _)| seconds < now)
    {
        refusals.push(Refusal::new(
            "cf-at-past",
            "trigger.at",
            "the time has passed",
        ));
    }
    refusals.extend(file_refusals(file));
    if !refusals.is_empty() {
        item.refusals = refusals;
        return;
    }
    if matches!(file.trigger, Trigger::In(_)) {
        item.notes.push("an in trigger becomes a fixed run time when the loop is created; plan it again with that at time".into());
    }
    item.action = Action::Create;
    item.commands.push(create_command(file));
}

fn same_trigger(file: &Trigger, live: &Trigger) -> bool {
    match (file, live) {
        (Trigger::At(a), Trigger::At(b)) => instant(a).is_some() && instant(a) == instant(b),
        _ => file == live,
    }
}

fn plan_update(item: &mut PlanItem, file: &Loop, live: &LiveLoop, adopted: bool) {
    item.loop_id = Some(live.loop_id.clone());
    item.paused = !live.enabled;
    let mut refusals = Vec::new();
    if matches!(file.trigger, Trigger::In(_)) {
        refusals.push(Refusal::new(
            "cf-in-existing",
            "trigger.in",
            "an in trigger can only create a loop; write the at time instead",
        ));
    }
    refusals.extend(file_refusals(file));
    let Some(live_trigger) = &live.trigger else {
        refusals.push(Refusal::new(
            "cf-export-trigger",
            "trigger",
            "the loop has no cron, run time or webhook",
        ));
        item.refusals = refusals;
        return;
    };
    if (file.trigger == Trigger::Webhook) != (*live_trigger == Trigger::Webhook) {
        refusals.push(Refusal::new(
            "cf-update-webhook",
            "trigger",
            "Cloudroom cannot change a loop to or from a webhook",
        ));
    }
    if file.new_thread != live.new_thread {
        refusals.push(Refusal::new(
            "cf-update-thread",
            "thread",
            "Cloudroom cannot change a loop's thread",
        ));
    }
    if file.check.is_none() && live.script.is_some() {
        refusals.push(Refusal::new(
            "cf-update-remove-check",
            "check",
            "Cloudroom cannot remove a loop's check",
        ));
    }
    if file.agent.is_none() && live.agent.is_some() {
        refusals.push(Refusal::new(
            "cf-update-remove-agent",
            "agent",
            "Cloudroom cannot return a loop to the caller's agent",
        ));
    }
    if !refusals.is_empty() {
        item.refusals = refusals;
        return;
    }
    let live_name = if adopted {
        live.name.as_str()
    } else {
        split_marker(&live.name).map_or(live.name.as_str(), |(_, name)| name)
    };
    let body = rendered_body(file);
    let script = file.check.as_ref().map(|c| rendered_script(file, c));
    let thread = |new: bool| json!(if new { "new" } else { "same" });
    let agent = |a: &Option<Agent>| a.as_ref().map_or(Value::Null, Agent::to_json);
    let mut differences = Vec::new();
    let mut differ = |field: &'static str, same: bool, file: Value, live: Value| {
        if !same {
            differences.push(Difference { field, file, live });
        }
    };
    differ(
        "name",
        file.name == live_name,
        json!(file.name),
        json!(live_name),
    );
    differ(
        "trigger",
        same_trigger(&file.trigger, live_trigger),
        file.trigger.to_json(),
        live_trigger.to_json(),
    );
    differ(
        "thread",
        file.new_thread == live.new_thread,
        thread(file.new_thread),
        thread(live.new_thread),
    );
    differ(
        "agent",
        file.agent == live.agent,
        agent(&file.agent),
        agent(&live.agent),
    );
    differ(
        "priority",
        file.priority == live.priority,
        json!(file.priority),
        json!(live.priority),
    );
    differ(
        "secrets",
        file.secrets.same(&live.secrets),
        file.secrets.to_json(),
        live.secrets.to_json(),
    );
    differ("body", body == live.prompt, json!(body), json!(live.prompt));
    differ(
        "check",
        script == live.script,
        json!(script),
        json!(live.script),
    );
    let has = |field: &str| differences.iter().any(|d| d.field == field);
    let mut files = Vec::new();
    let script_file = match script {
        Some(script) if has("check") => {
            files.push(("@script".to_owned(), script));
            Some("@script".to_owned())
        }
        _ => None,
    };
    let update = LoopUpdateArgs {
        loop_id: live.address.clone(),
        name: (has("name") || adopted).then(|| format!("{} {}", file.name, marker(&file.id))),
        priority: has("priority").then(|| file.priority.to_string()),
        prompt: has("body").then_some(body),
        trigger: match &file.trigger {
            _ if !has("trigger") => None,
            Trigger::Cron { cron, timezone } => Some(LoopReschedule::Cron {
                cron: cron.clone(),
                timezone: timezone.clone(),
            }),
            Trigger::At(at) => Some(LoopReschedule::At(at.clone())),
            // Refused above: an `in` file, and a change to or from a webhook.
            Trigger::In(_) | Trigger::Webhook => None,
        },
        script_file,
        agent: file.agent.as_ref().filter(|_| has("agent")).map(agent_args),
        secrets: has("secrets").then(|| file.secrets.flag()),
    };
    let changes = update.name.is_some()
        || update.priority.is_some()
        || update.prompt.is_some()
        || update.trigger.is_some()
        || update.script_file.is_some()
        || update.agent.is_some()
        || update.secrets.is_some();
    item.differences = differences;
    if !live.unmapped.is_empty() {
        item.notes.push(format!(
            "Cloudroom loop {} carries settings the adapter does not map, so plan cannot compare them and the file does not hold them: {}",
            live.loop_id,
            live.unmapped.join(", ")
        ));
    }
    if adopted {
        item.notes.push(format!(
            "adopts Cloudroom loop {}: its name gains the marker {}",
            live.loop_id,
            marker(&file.id)
        ));
    }
    if changes {
        item.action = Action::Update;
        item.commands.push(RoomCommand {
            invocation: Invocation::LoopUpdate(update),
            files,
        });
    } else {
        item.action = Action::None;
    }
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

#[cfg(test)]
mod plan_tests {
    use super::*;

    // catches: a JSON reader that collapses a repeated key, accepts a value
    // that is not exactly one JSON value, or reads 2.0 as an integer.
    #[test]
    fn the_strict_json_reader_keeps_order_and_refuses_duplicates() {
        assert_eq!(
            parse_document(r#"{"b": 1, "a": [2.0, "xé"]}"#.as_bytes()),
            Some(Json::Object(vec![
                (
                    "b".into(),
                    Json::Number {
                        text: "1".into(),
                        integer: true
                    }
                ),
                (
                    "a".into(),
                    Json::Array(vec![
                        Json::Number {
                            text: "2.0".into(),
                            integer: false
                        },
                        Json::String("xé".into()),
                    ])
                ),
            ]))
        );
        assert_eq!(parse_document(br#"{"a": {"b": 1, "b": 2}}"#), None);
        for bad in [
            "",
            "01",
            "[1,]",
            "\"a\" \"b\"",
            "{'a': 1}",
            "1.",
            "tru",
            "\"\t\"",
        ] {
            assert_eq!(parse_document(bad.as_bytes()), None, "{bad}");
        }
    }

    // catches: two spellings of one instant compared as different, or an
    // invalid date taken as a time.
    #[test]
    fn instants_compare_across_spellings() {
        assert_eq!(
            instant("2030-01-02T03:04:05Z"),
            instant("2030-01-02T03:04:05.000+00:00")
        );
        assert_eq!(
            instant("2030-01-02T03:04:05Z"),
            instant("2030-01-01T19:04:05-08:00")
        );
        assert_eq!(instant("1970-01-01T00:00:00Z"), Some((0, String::new())));
        assert_ne!(
            instant("2030-01-02T03:04:05.5Z"),
            instant("2030-01-02T03:04:05Z")
        );
        for bad in [
            "2030-01-02T03:04:05",
            "2030-02-30T03:04:05Z",
            "2030-01-02T03:04Z",
            "2030-01-02 03:04:05Z",
        ] {
            assert_eq!(instant(bad), None, "{bad}");
        }
    }

    // catches: the 15-minute rule missing a gap across midnight or an
    // hour boundary, or refusing a loop that is due rarely enough.
    #[test]
    fn the_fifteen_minute_rule_reads_minute_and_hour() {
        for (cron, refused) in [
            ("*/5 * * * *", true),
            ("*/15 * * * *", false),
            ("0,50 * * * *", true),
            ("59 23 * * *", false),
            ("50 * * * *", false),
            ("0,10 9 * * *", true),
            ("55 23,0 * * *", false),
            ("0 0,23 * * *", false),
            ("50 23 * * *", false),
            ("5,55 0,23 * * *", true),
        ] {
            assert_eq!(too_frequent(cron), refused, "{cron}");
        }
    }
}
