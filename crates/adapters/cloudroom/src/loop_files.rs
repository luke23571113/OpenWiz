//! Loop files in the pinned WizLoops format (`contracts/wizloops-loop.v1.md`)
//! and the Cloudroom adapter rules (`contracts/wizloops-cloudroom.v1.md`).
//! Shared by `openwiz loop validate|export|plan|apply` (LC2 to LC5); each
//! ticket owns its own functions here.
//!
//! LC4 (#792, plan): the reader ([`read_paths`], format steps 1 to 6 and
//! folders), the read of `room-cli loop list` ([`parse_loop_list`]) and
//! [`plan`], which maps each file to its `room-cli loop create` or `update`
//! command and compares it with its managed loop. Nothing here writes.

use std::collections::{BTreeMap, BTreeSet};
use std::fs;
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

// ---------------------------------------------------------------- refusals

/// One refusal, as the format and the adapter write them.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Refusal {
    pub file: String,
    pub code: String,
    pub field: String,
    pub message: String,
}

impl Refusal {
    fn new(file: &str, code: &str, field: &str, message: impl Into<String>) -> Self {
        Self {
            file: file.to_owned(),
            code: code.to_owned(),
            field: field.to_owned(),
            message: message.into(),
        }
    }

    pub fn to_json(&self) -> Value {
        json!({"file": self.file, "code": self.code, "field": self.field, "message": self.message})
    }
}

/// The format's field refusals in its table order, which orders one line's
/// refusals ("for one line, in the order of the refusal tables").
const FIELD_CODES: [&str; 22] = [
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

// -------------------------------------------- JSON, ordered and duplicate-aware

/// One JSON value with its object keys in the order written. A reader must
/// refuse duplicate keys before it builds an object, and report params in
/// their written order, so `serde_json`'s map is not used here.
#[derive(Debug, Clone, PartialEq)]
pub enum Json {
    Null,
    Bool(bool),
    /// The number as written; `integer` when it has no fraction or exponent.
    Number {
        text: String,
        integer: bool,
    },
    String(String),
    Array(Vec<Json>),
    Object(Vec<(String, Json)>),
}

#[derive(Debug, PartialEq)]
enum JsonError {
    Syntax,
    /// A repeated key: its path from the value's root.
    Duplicate(Vec<String>),
}

impl Json {
    fn get(&self, key: &str) -> Option<&Json> {
        match self {
            Json::Object(members) => members.iter().find(|(k, _)| k == key).map(|(_, v)| v),
            _ => None,
        }
    }

    fn as_str(&self) -> Option<&str> {
        match self {
            Json::String(s) => Some(s),
            _ => None,
        }
    }

    fn as_int(&self) -> Option<&str> {
        match self {
            Json::Number {
                text,
                integer: true,
            } => Some(text),
            _ => None,
        }
    }
}

/// Parses exactly one JSON value, with no whitespace around it.
fn parse_json(text: &str) -> Result<Json, JsonError> {
    let mut parser = JsonParser {
        bytes: text.as_bytes(),
        at: 0,
        depth: 0,
    };
    let value = parser.value()?;
    if parser.at != parser.bytes.len() {
        return Err(JsonError::Syntax);
    }
    Ok(value)
}

/// Parses one JSON document, whitespace allowed around it (`loop list`).
fn parse_json_document(bytes: &[u8]) -> Result<Json, JsonError> {
    let text = std::str::from_utf8(bytes).map_err(|_| JsonError::Syntax)?;
    parse_json(text.trim_matches(|c| matches!(c, ' ' | '\t' | '\n' | '\r')))
}

struct JsonParser<'a> {
    bytes: &'a [u8],
    at: usize,
    depth: usize,
}

impl JsonParser<'_> {
    fn peek(&self) -> Option<u8> {
        self.bytes.get(self.at).copied()
    }

    fn space(&mut self) {
        while matches!(self.peek(), Some(b' ' | b'\t' | b'\n' | b'\r')) {
            self.at += 1;
        }
    }

    fn eat(&mut self, byte: u8) -> Result<(), JsonError> {
        if self.peek() == Some(byte) {
            self.at += 1;
            Ok(())
        } else {
            Err(JsonError::Syntax)
        }
    }

    fn literal(&mut self, word: &str, value: Json) -> Result<Json, JsonError> {
        if self.bytes[self.at..].starts_with(word.as_bytes()) {
            self.at += word.len();
            Ok(value)
        } else {
            Err(JsonError::Syntax)
        }
    }

    fn value(&mut self) -> Result<Json, JsonError> {
        match self.peek().ok_or(JsonError::Syntax)? {
            b'{' => self.nested(Self::object),
            b'[' => self.nested(Self::array),
            b'"' => self.string().map(Json::String),
            b't' => self.literal("true", Json::Bool(true)),
            b'f' => self.literal("false", Json::Bool(false)),
            b'n' => self.literal("null", Json::Null),
            b'-' | b'0'..=b'9' => self.number(),
            _ => Err(JsonError::Syntax),
        }
    }

    fn nested(
        &mut self,
        parse: fn(&mut Self) -> Result<Json, JsonError>,
    ) -> Result<Json, JsonError> {
        self.depth += 1;
        if self.depth > 64 {
            return Err(JsonError::Syntax);
        }
        let value = parse(self);
        self.depth -= 1;
        value
    }

    fn object(&mut self) -> Result<Json, JsonError> {
        self.eat(b'{')?;
        let mut members: Vec<(String, Json)> = Vec::new();
        self.space();
        if self.peek() == Some(b'}') {
            self.at += 1;
            return Ok(Json::Object(members));
        }
        loop {
            self.space();
            let key = self.string()?;
            self.space();
            self.eat(b':')?;
            self.space();
            let value = self.value().map_err(|e| match e {
                JsonError::Duplicate(mut path) => {
                    path.insert(0, key.clone());
                    JsonError::Duplicate(path)
                }
                e => e,
            })?;
            if members.iter().any(|(k, _)| *k == key) {
                return Err(JsonError::Duplicate(vec![key]));
            }
            members.push((key, value));
            self.space();
            match self.peek() {
                Some(b',') => self.at += 1,
                Some(b'}') => {
                    self.at += 1;
                    return Ok(Json::Object(members));
                }
                _ => return Err(JsonError::Syntax),
            }
        }
    }

    fn array(&mut self) -> Result<Json, JsonError> {
        self.eat(b'[')?;
        let mut items = Vec::new();
        self.space();
        if self.peek() == Some(b']') {
            self.at += 1;
            return Ok(Json::Array(items));
        }
        loop {
            self.space();
            items.push(self.value()?);
            self.space();
            match self.peek() {
                Some(b',') => self.at += 1,
                Some(b']') => {
                    self.at += 1;
                    return Ok(Json::Array(items));
                }
                _ => return Err(JsonError::Syntax),
            }
        }
    }

    fn digits(&mut self) -> usize {
        let start = self.at;
        while matches!(self.peek(), Some(b'0'..=b'9')) {
            self.at += 1;
        }
        self.at - start
    }

    fn number(&mut self) -> Result<Json, JsonError> {
        let start = self.at;
        if self.peek() == Some(b'-') {
            self.at += 1;
        }
        match self.peek() {
            Some(b'0') => self.at += 1,
            Some(b'1'..=b'9') => {
                self.digits();
            }
            _ => return Err(JsonError::Syntax),
        }
        let mut integer = true;
        if self.peek() == Some(b'.') {
            self.at += 1;
            integer = false;
            if self.digits() == 0 {
                return Err(JsonError::Syntax);
            }
        }
        if matches!(self.peek(), Some(b'e' | b'E')) {
            self.at += 1;
            integer = false;
            if matches!(self.peek(), Some(b'+' | b'-')) {
                self.at += 1;
            }
            if self.digits() == 0 {
                return Err(JsonError::Syntax);
            }
        }
        let text = std::str::from_utf8(&self.bytes[start..self.at])
            .map_err(|_| JsonError::Syntax)?
            .to_owned();
        Ok(Json::Number { text, integer })
    }

    fn hex4(&mut self) -> Result<u32, JsonError> {
        let hex = self
            .bytes
            .get(self.at..self.at + 4)
            .and_then(|h| std::str::from_utf8(h).ok())
            .filter(|h| h.bytes().all(|b| b.is_ascii_hexdigit()))
            .ok_or(JsonError::Syntax)?;
        self.at += 4;
        u32::from_str_radix(hex, 16).map_err(|_| JsonError::Syntax)
    }

    fn string(&mut self) -> Result<String, JsonError> {
        self.eat(b'"')?;
        let mut out = String::new();
        loop {
            let rest =
                std::str::from_utf8(&self.bytes[self.at..]).map_err(|_| JsonError::Syntax)?;
            let c = rest.chars().next().ok_or(JsonError::Syntax)?;
            self.at += c.len_utf8();
            match c {
                '"' => return Ok(out),
                '\\' => {
                    let escape = self.peek().ok_or(JsonError::Syntax)?;
                    self.at += 1;
                    out.push(match escape {
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
                            let code = if (0xD800..0xDC00).contains(&high) {
                                self.eat(b'\\')?;
                                self.eat(b'u')?;
                                let low = self.hex4()?;
                                if !(0xDC00..0xE000).contains(&low) {
                                    return Err(JsonError::Syntax);
                                }
                                0x10000 + ((high - 0xD800) << 10) + (low - 0xDC00)
                            } else {
                                high
                            };
                            char::from_u32(code).ok_or(JsonError::Syntax)?
                        }
                        _ => return Err(JsonError::Syntax),
                    });
                }
                c if (c as u32) < 0x20 => return Err(JsonError::Syntax),
                c => out.push(c),
            }
        }
    }
}

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

/// One valid loop file.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LoopFile {
    pub id: String,
    pub name: String,
    pub trigger: Trigger,
    pub check: Option<Check>,
    /// `thread`: `"new"` is true, `"same"` false.
    pub new_thread: bool,
    pub agent: Option<Agent>,
    pub secrets: Secrets,
    pub priority: i64,
    /// In the order the file lists them.
    pub params: Vec<(String, Param)>,
    pub body: String,
}

/// One loop file as read: valid, or refused with every refusal in order.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ReadFile {
    /// The path as given; inside a folder, the folder's path, `/` and the name.
    pub file: String,
    /// The parsed `id`, when it is a valid id.
    pub id: Option<String>,
    pub result: Result<LoopFile, Vec<Refusal>>,
}

// ---------------------------------------------------------------- the reader

/// Reads each path: a loop file, or a folder read as the format's "Folders"
/// says. `Err` names the first path that can't be read.
pub fn read_paths(paths: &[String]) -> Result<Vec<ReadFile>, String> {
    let mut files = Vec::new();
    for path in paths {
        let meta = fs::metadata(path).map_err(|e| format!("{path}: {e}"))?;
        if !meta.is_dir() {
            files.push(read_loop_file(Path::new(path), path)?);
            continue;
        }
        let mut names: Vec<String> = Vec::new();
        for entry in fs::read_dir(path).map_err(|e| format!("{path}: {e}"))? {
            let entry = entry.map_err(|e| format!("{path}: {e}"))?;
            let Ok(name) = entry.file_name().into_string() else {
                continue;
            };
            if name.ends_with(".md") && name != "README.md" && entry.path().is_file() {
                names.push(name);
            }
        }
        names.sort();
        let folder = path.strip_suffix('/').unwrap_or(path);
        let mut read: Vec<ReadFile> = Vec::new();
        for name in &names {
            let shown = format!("{folder}/{name}");
            read.push(read_loop_file(&Path::new(path).join(name), &shown)?);
        }
        // duplicate-id: on each file after the first, naming the first.
        let mut first: BTreeMap<String, String> = BTreeMap::new();
        for (file, name) in read.iter_mut().zip(&names) {
            let Some(id) = file.id.clone() else { continue };
            match first.get(&id) {
                Some(other) => {
                    let refusal = Refusal::new(
                        &file.file,
                        "duplicate-id",
                        "id",
                        format!("{id} is also the id of {other}"),
                    );
                    match &mut file.result {
                        Ok(_) => file.result = Err(vec![refusal]),
                        Err(refusals) => refusals.push(refusal),
                    }
                }
                None => {
                    first.insert(id, name.clone());
                }
            }
        }
        files.extend(read);
    }
    Ok(files)
}

/// Reads one loop file, as the format's "Reading a file" says. `Err` only
/// when the file itself can't be read.
pub fn read_loop_file(path: &Path, shown: &str) -> Result<ReadFile, String> {
    let bytes = fs::read(path).map_err(|e| format!("{shown}: {e}"))?;
    let folder = path.parent().unwrap_or(Path::new("."));
    Ok(read_bytes(&bytes, folder, shown))
}

fn refused(file: &str, refusals: Vec<Refusal>) -> ReadFile {
    ReadFile {
        file: file.to_owned(),
        id: None,
        result: Err(refusals),
    }
}

fn read_bytes(bytes: &[u8], folder: &Path, file: &str) -> ReadFile {
    // Step 1: encoding.
    let text = match std::str::from_utf8(bytes) {
        Ok(text) if !text.starts_with('\u{feff}') && !text.contains(['\0', '\r']) => text,
        _ => {
            return refused(
                file,
                vec![Refusal::new(
                    file,
                    "encoding",
                    "file",
                    "must be UTF-8 with LF line ends, no byte order mark and no NUL",
                )],
            );
        }
    };
    // Steps 2 and 3: the frontmatter's start and end.
    let Some(rest) = text
        .strip_prefix("---\n")
        .or(if text == "---" { Some("") } else { None })
    else {
        return refused(
            file,
            vec![Refusal::new(
                file,
                "frontmatter-start",
                "file",
                "must start with a line of exactly ---",
            )],
        );
    };
    let mut lines: Vec<&str> = Vec::new();
    let mut body = None;
    let mut remaining = rest;
    while !remaining.is_empty() {
        let (line, after) = match remaining.split_once('\n') {
            Some((line, after)) => (line, after),
            None => (remaining, ""),
        };
        if line == "---" {
            body = Some(after);
            break;
        }
        lines.push(line);
        remaining = after;
    }
    let Some(body) = body else {
        return refused(
            file,
            vec![Refusal::new(
                file,
                "frontmatter-end",
                "file",
                "frontmatter has no closing line of exactly ---",
            )],
        );
    };
    // Step 4: each line is one `key: value`.
    let mut line_refusals = Vec::new();
    let mut fields: Vec<(String, Json)> = Vec::new();
    for (index, line) in lines.iter().enumerate() {
        let number = index + 2;
        match read_line(line) {
            Ok((key, value)) => {
                if fields.iter().any(|(k, _)| *k == key) {
                    line_refusals.push(Refusal::new(
                        file,
                        "duplicate-key",
                        &key,
                        "appears more than once",
                    ));
                } else {
                    fields.push((key, value));
                }
            }
            Err(LineError::Syntax) => line_refusals.push(Refusal::new(
                file,
                "line-syntax",
                &format!("line {number}"),
                "must be \"key: value\" with one JSON value",
            )),
            Err(LineError::Json(key)) => line_refusals.push(Refusal::new(
                file,
                "json",
                &key,
                "value is not one JSON value",
            )),
            Err(LineError::Duplicate(path)) => line_refusals.push(Refusal::new(
                file,
                "duplicate-key",
                &path,
                "appears more than once",
            )),
        }
    }
    if !line_refusals.is_empty() {
        return refused(file, line_refusals);
    }
    let mut checker = Checker {
        file,
        folder,
        refusals: Vec::new(),
    };
    let loop_file = checker.fields(&fields, body);
    let id = fields
        .iter()
        .find(|(k, _)| k == "id")
        .and_then(|(_, v)| v.as_str())
        .filter(|id| valid_id(id))
        .map(str::to_owned);
    ReadFile {
        file: file.to_owned(),
        id,
        result: match loop_file {
            Some(loop_file) if checker.refusals.is_empty() => Ok(loop_file),
            _ => Err(checker.refusals),
        },
    }
}

enum LineError {
    Syntax,
    Json(String),
    Duplicate(String),
}

fn read_line(line: &str) -> Result<(String, Json), LineError> {
    let key_end = line
        .char_indices()
        .find(|&(i, c)| !(c.is_ascii_lowercase() || (i > 0 && (c.is_ascii_digit() || c == '_'))))
        .map_or(line.len(), |(i, _)| i);
    if key_end == 0 {
        return Err(LineError::Syntax);
    }
    let key = &line[..key_end];
    let value = line[key_end..]
        .strip_prefix(": ")
        .ok_or(LineError::Syntax)?;
    if value.starts_with([' ', '\t']) || value.ends_with([' ', '\t']) {
        return Err(LineError::Syntax);
    }
    match parse_json(value) {
        Ok(value) => Ok((key.to_owned(), value)),
        Err(JsonError::Syntax) => Err(LineError::Json(key.to_owned())),
        Err(JsonError::Duplicate(path)) => Err(LineError::Duplicate(
            std::iter::once(key.to_owned())
                .chain(path)
                .collect::<Vec<_>>()
                .join("."),
        )),
    }
}

fn valid_id(id: &str) -> bool {
    let bytes = id.as_bytes();
    !bytes.is_empty()
        && bytes.len() <= 64
        && (bytes[0].is_ascii_lowercase() || bytes[0].is_ascii_digit())
        && bytes
            .iter()
            .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || *b == b'-')
}

fn valid_param_name(name: &str) -> bool {
    let mut chars = name.chars();
    chars.next().is_some_and(|c| c.is_ascii_lowercase())
        && chars.all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == '_')
}

fn is_control(c: char) -> bool {
    (c as u32) < 0x20 || c == '\u{7f}'
}

struct Checker<'a> {
    file: &'a str,
    folder: &'a Path,
    refusals: Vec<Refusal>,
}

/// One frontmatter line's refusals, ordered by the format's table.
struct LineRefusals<'a> {
    file: &'a str,
    list: Vec<Refusal>,
}

impl LineRefusals<'_> {
    fn push(&mut self, code: &str, field: &str, message: impl Into<String>) {
        self.list
            .push(Refusal::new(self.file, code, field, message));
    }

    fn wrong_type(&mut self, field: &str, kind: &str) {
        self.push("wrong-type", field, format!("must be {kind}"));
    }

    fn missing(&mut self, field: &str) {
        self.push("missing-field", field, "is required");
    }

    fn unknown(&mut self, field: &str) {
        self.push("unknown-field", field, "is not a field of loop v1");
    }

    fn sorted(mut self) -> Vec<Refusal> {
        self.list.sort_by_key(|r| {
            FIELD_CODES
                .iter()
                .position(|c| *c == r.code)
                .unwrap_or(FIELD_CODES.len())
        });
        self.list
    }
}

impl Checker<'_> {
    fn line(&self) -> LineRefusals<'_> {
        LineRefusals {
            file: self.file,
            list: Vec::new(),
        }
    }

    /// Steps 5 and 6. The loop, when every field it needs was read; the
    /// refusals are in `self.refusals`.
    fn fields(&mut self, fields: &[(String, Json)], body: &str) -> Option<LoopFile> {
        let get = |key: &str| fields.iter().find(|(k, _)| k == key).map(|(_, v)| v);
        let thread_same = get("thread").and_then(Json::as_str) == Some("same");
        let mut id = None;
        let mut name = None;
        let mut trigger = None;
        let mut check: Option<Option<Check>> = Some(None);
        let mut check_text: Option<String> = None;
        let mut new_thread = None;
        let mut agent: Option<Option<Agent>> = Some(None);
        let mut secrets = Some(Secrets::List(Vec::new()));
        let mut priority = Some(3);
        let mut params: Option<Vec<(String, Param)>> = Some(Vec::new());
        // Params whose names are valid, for the body's and the check's use.
        let mut declared: Vec<String> = Vec::new();
        for (key, value) in fields {
            let mut line = self.line();
            match key.as_str() {
                "id" => {
                    id = string_field(
                        &mut line,
                        "id",
                        value,
                        valid_id,
                        "bad-id",
                        "must be 1 to 64 lowercase letters, digits and hyphens, starting with a letter or digit",
                    )
                }
                "name" => {
                    name = string_field(
                        &mut line,
                        "name",
                        value,
                        |n| {
                            let count = n.chars().count();
                            (1..=100).contains(&count)
                                && !n.chars().all(char::is_whitespace)
                                && !n.chars().any(is_control)
                        },
                        "bad-name",
                        "must be 1 to 100 characters, not all whitespace, with no control characters",
                    )
                }
                "trigger" => trigger = read_trigger(&mut line, value),
                "check" => {
                    let (read, text) = self.read_check(&mut line, value);
                    check = read.map(Some);
                    check_text = text;
                }
                "thread" => {
                    new_thread = match value.as_str() {
                        Some("new") => Some(true),
                        Some("same") => Some(false),
                        Some(_) => {
                            line.push("bad-thread", "thread", "must be \"same\" or \"new\"");
                            None
                        }
                        None => {
                            line.wrong_type("thread", "a string");
                            None
                        }
                    }
                }
                "agent" => agent = read_agent(&mut line, value).map(Some),
                "secrets" => secrets = read_secrets(&mut line, value, thread_same),
                "priority" => {
                    priority = match value.as_int() {
                        Some(text) => match text.parse::<i64>() {
                            Ok(p) if (1..=4).contains(&p) => Some(p),
                            _ => {
                                line.push("bad-priority", "priority", "must be 1 to 4");
                                None
                            }
                        },
                        None => {
                            line.wrong_type("priority", "an integer");
                            None
                        }
                    }
                }
                "params" => params = read_params(&mut line, value, &mut declared),
                other => line.unknown(other),
            }
            self.refusals.extend(line.sorted());
        }
        // Step 6: the body, then the check's text, then unused params.
        let mut used: BTreeSet<String> = BTreeSet::new();
        if !body.chars().any(|c| !c.is_whitespace()) {
            self.push("empty-body", "body", "the prompt must not be empty");
        }
        for found in placeholders(body) {
            match found {
                Placeholder::Bad => {
                    self.push(
                        "bad-placeholder",
                        "body",
                        "{{ must start a placeholder {{name}}",
                    );
                }
                Placeholder::Name(n) if declared.contains(&n) => {
                    used.insert(n);
                }
                Placeholder::Name(n) => self.push(
                    "undeclared-param",
                    "body",
                    format!("uses {{{{{n}}}}}, which params does not declare"),
                ),
            }
        }
        if let Some(text) = &check_text {
            for found in check_references(text) {
                match found {
                    CheckRef::Placeholder(n) => self.push(
                        "param-in-check",
                        "check",
                        format!(
                            "uses {{{{{n}}}}}; a check reads it as $WIZLOOP_PARAM_{}",
                            n.to_ascii_uppercase()
                        ),
                    ),
                    CheckRef::Env(run) => {
                        match declared.iter().find(|d| d.to_ascii_uppercase() == run) {
                            Some(d) => {
                                used.insert(d.clone());
                            }
                            None => self.push(
                                "undeclared-param",
                                "check",
                                format!("uses $WIZLOOP_PARAM_{run}, which params does not declare"),
                            ),
                        }
                    }
                }
            }
        }
        for name in &declared {
            if !used.contains(name) {
                self.push(
                    "unused-param",
                    &format!("params.{name}"),
                    "is declared but never used",
                );
            }
        }
        for field in ["id", "name", "trigger", "thread"] {
            if get(field).is_none() {
                self.push("missing-field", field, "is required");
            }
        }
        Some(LoopFile {
            id: id?,
            name: name?,
            trigger: trigger?,
            check: check?,
            new_thread: new_thread?,
            agent: agent?,
            secrets: secrets?,
            priority: priority?,
            params: params?,
            body: body.to_owned(),
        })
    }

    fn push(&mut self, code: &str, field: &str, message: impl Into<String>) {
        self.refusals
            .push(Refusal::new(self.file, code, field, message));
    }

    /// The check, and its script's text whenever the script was read, so
    /// that its params are checked even when its timeout is refused.
    fn read_check(
        &self,
        line: &mut LineRefusals<'_>,
        value: &Json,
    ) -> (Option<Check>, Option<String>) {
        let Json::Object(members) = value else {
            line.wrong_type("check", "an object");
            return (None, None);
        };
        for (key, _) in members {
            if key != "run" && key != "timeout" {
                line.unknown(&format!("check.{key}"));
            }
        }
        let run = match value.get("run") {
            None => {
                line.missing("check.run");
                None
            }
            Some(Json::String(run)) => {
                let segments_ok = !run.is_empty()
                    && !run.starts_with('/')
                    && !run.contains('\\')
                    && run
                        .split('/')
                        .all(|s| !s.is_empty() && s != "." && s != "..");
                if !segments_ok {
                    line.push(
                        "bad-check-path",
                        "check.run",
                        "must be a relative path inside the loop's folder, with no . or .. segments",
                    );
                    None
                } else {
                    match read_check_text(&self.folder.join(run)) {
                        Some(text) => Some((run.clone(), text)),
                        None => {
                            line.push(
                                "check-not-found",
                                "check.run",
                                "must name an existing regular file of UTF-8 text",
                            );
                            None
                        }
                    }
                }
            }
            Some(_) => {
                line.wrong_type("check.run", "a string");
                None
            }
        };
        let timeout = match value.get("timeout") {
            None => {
                line.missing("check.timeout");
                None
            }
            Some(t) => match t.as_int() {
                Some(text) => match text.parse::<i64>() {
                    Ok(t) if (1..=900).contains(&t) => Some(t),
                    _ => {
                        line.push("bad-timeout", "check.timeout", "must be 1 to 900 seconds");
                        None
                    }
                },
                None => {
                    line.wrong_type("check.timeout", "an integer");
                    None
                }
            },
        };
        let Some((run, text)) = run else {
            return (None, None);
        };
        let Some(timeout) = timeout else {
            return (None, Some(text));
        };
        let check = Check {
            run,
            timeout,
            text: text.clone(),
        };
        (Some(check), Some(text))
    }
}

/// A regular file, not a symlink, of UTF-8 text with no NUL.
fn read_check_text(path: &Path) -> Option<String> {
    let meta = fs::symlink_metadata(path).ok()?;
    if !meta.file_type().is_file() {
        return None;
    }
    String::from_utf8(fs::read(path).ok()?)
        .ok()
        .filter(|t| !t.contains('\0'))
}

fn string_field(
    line: &mut LineRefusals<'_>,
    field: &str,
    value: &Json,
    ok: impl Fn(&str) -> bool,
    code: &str,
    message: &str,
) -> Option<String> {
    match value.as_str() {
        Some(s) if ok(s) => Some(s.to_owned()),
        Some(_) => {
            line.push(code, field, message);
            None
        }
        None => {
            line.wrong_type(field, "a string");
            None
        }
    }
}

fn read_trigger(line: &mut LineRefusals<'_>, value: &Json) -> Option<Trigger> {
    let Json::Object(members) = value else {
        line.wrong_type("trigger", "an object");
        return None;
    };
    let kinds: Vec<&str> = members
        .iter()
        .map(|(k, _)| k.as_str())
        .filter(|k| ["cron", "at", "in", "webhook"].contains(k))
        .collect();
    let has_cron = kinds.contains(&"cron");
    for (key, _) in members {
        let known = ["cron", "at", "in", "webhook"].contains(&key.as_str())
            || (key == "timezone" && (has_cron || kinds.is_empty()));
        if !known {
            line.unknown(&format!("trigger.{key}"));
        }
    }
    if kinds.len() != 1 {
        line.push(
            "trigger-kind",
            "trigger",
            "must have exactly one of cron, at, in or webhook",
        );
        return None;
    }
    let string = |line: &mut LineRefusals<'_>, key: &str| match value.get(key) {
        Some(Json::String(s)) => Some(s.clone()),
        Some(_) => {
            line.wrong_type(&format!("trigger.{key}"), "a string");
            None
        }
        None => {
            line.missing(&format!("trigger.{key}"));
            None
        }
    };
    match kinds[0] {
        "cron" => {
            let cron = string(line, "cron").filter(|c| {
                let ok = cron_fields(c).is_some();
                if !ok {
                    line.push(
                        "bad-cron",
                        "trigger.cron",
                        "must be five cron fields: minute hour day-of-month month day-of-week",
                    );
                }
                ok
            });
            let timezone = string(line, "timezone").filter(|z| {
                let ok = valid_timezone(z);
                if !ok {
                    line.push(
                        "bad-timezone",
                        "trigger.timezone",
                        "must be UTC or an IANA zone such as Area/City",
                    );
                }
                ok
            });
            Some(Trigger::Cron {
                cron: cron?,
                timezone: timezone?,
            })
        }
        "at" => {
            let at = string(line, "at")?;
            if instant(&at).is_none() {
                line.push(
                    "bad-at",
                    "trigger.at",
                    "must be an RFC 3339 time with seconds and an offset",
                );
                return None;
            }
            Some(Trigger::At(at))
        }
        "in" => {
            let delay = string(line, "in")?;
            // The unit is one ASCII byte, so strip it as text: a delay ending in
            // a multibyte character is refused, never split inside it.
            let number = delay.strip_suffix(['m', 'h', 'd']).unwrap_or("");
            let ok = number.starts_with(|c: char| ('1'..='9').contains(&c))
                && number.bytes().all(|b| b.is_ascii_digit());
            if !ok {
                line.push(
                    "bad-in",
                    "trigger.in",
                    "must be a whole number from 1 followed by m, h or d",
                );
                return None;
            }
            Some(Trigger::In(delay))
        }
        _ => {
            if value.get("webhook") != Some(&Json::Bool(true)) {
                line.push("bad-webhook", "trigger.webhook", "must be true");
                return None;
            }
            Some(Trigger::Webhook)
        }
    }
}

fn valid_timezone(zone: &str) -> bool {
    if zone == "UTC" {
        return true;
    }
    let part = |s: &str| {
        !s.is_empty()
            && s.bytes()
                .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'_' | b'+' | b'-'))
    };
    let mut parts = zone.split('/');
    let area = parts.next().unwrap_or("");
    let rest: Vec<&str> = parts.collect();
    area.starts_with(|c: char| c.is_ascii_alphabetic())
        && part(area)
        && !rest.is_empty()
        && rest.iter().all(|p| part(p))
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

fn read_agent(line: &mut LineRefusals<'_>, value: &Json) -> Option<Agent> {
    let Json::Object(members) = value else {
        line.wrong_type("agent", "an object");
        return None;
    };
    for (key, _) in members {
        if !["provider", "model", "reasoning"].contains(&key.as_str()) {
            line.unknown(&format!("agent.{key}"));
        }
    }
    let mut read = |key: &str| {
        let field = format!("agent.{key}");
        match value.get(key) {
            None => {
                line.missing(&field);
                None
            }
            Some(Json::String(s)) => {
                let count = s.chars().count();
                if (1..=100).contains(&count)
                    && !s.chars().any(|c| c.is_whitespace() || is_control(c))
                {
                    Some(s.clone())
                } else {
                    line.push(
                        "bad-agent",
                        &field,
                        "must be 1 to 100 characters with no whitespace",
                    );
                    None
                }
            }
            Some(_) => {
                line.wrong_type(&field, "a string");
                None
            }
        }
    };
    let (provider, model, reasoning) = (read("provider"), read("model"), read("reasoning"));
    Some(Agent {
        provider: provider?,
        model: model?,
        reasoning: reasoning?,
    })
}

fn read_secrets(line: &mut LineRefusals<'_>, value: &Json, thread_same: bool) -> Option<Secrets> {
    let items = match value {
        Json::String(s) if s == "all" => return Some(Secrets::All),
        Json::Array(items) => items,
        _ => {
            line.wrong_type("secrets", "an array or \"all\"");
            return None;
        }
    };
    let mut names: Vec<String> = Vec::new();
    let mut bad = false;
    let mut repeated: Vec<String> = Vec::new();
    for item in items {
        let ok = item.as_str().filter(|s| {
            *s == ".env"
                || (s.starts_with(|c: char| c.is_ascii_uppercase())
                    && s.bytes()
                        .all(|b| b.is_ascii_uppercase() || b.is_ascii_digit() || b == b'_'))
        });
        match ok {
            Some(name) if names.iter().any(|n| n == name) => {
                if !repeated.iter().any(|r| r == name) {
                    repeated.push(name.to_owned());
                }
            }
            Some(name) => names.push(name.to_owned()),
            None => bad = true,
        }
    }
    if bad {
        line.push(
            "bad-secret",
            "secrets",
            "each item must be an environment variable name or \".env\"",
        );
    }
    for name in &repeated {
        line.push(
            "duplicate-secret",
            "secrets",
            format!("names {name} more than once"),
        );
    }
    if bad || !repeated.is_empty() {
        return None;
    }
    if thread_same && !names.is_empty() {
        line.push(
            "same-thread-secrets",
            "secrets",
            "must be [] or \"all\" when thread is \"same\": a same-thread run keeps its thread's environment",
        );
        return None;
    }
    Some(Secrets::List(names))
}

fn read_params(
    line: &mut LineRefusals<'_>,
    value: &Json,
    declared: &mut Vec<String>,
) -> Option<Vec<(String, Param)>> {
    let Json::Object(members) = value else {
        line.wrong_type("params", "an object");
        return None;
    };
    let mut params = Vec::new();
    let mut ok = true;
    for (name, value) in members {
        let name_ok = valid_param_name(name);
        if name_ok {
            declared.push(name.clone());
        } else {
            ok = false;
            line.push(
                "bad-param-name",
                "params",
                format!(
                    "name {name} must be lowercase letters, digits and underscores, starting with a letter"
                ),
            );
        }
        let field = format!("params.{name}");
        let param = match value {
            Json::String(s) => Some(Param::Str(s.clone())),
            Json::Number {
                text,
                integer: true,
            } => Some(Param::Int(text.clone())),
            _ => {
                line.wrong_type(&field, "a string or an integer");
                None
            }
        };
        match param {
            Some(Param::Str(s)) if s.contains(['\n', '\r', '\0']) => {
                if name_ok {
                    line.push(
                        "multiline-param",
                        &field,
                        "must be one line, with no line break or NUL",
                    );
                }
                ok = false;
            }
            Some(param) => params.push((name.clone(), param)),
            None => ok = false,
        }
    }
    ok.then_some(params)
}

enum Placeholder {
    Name(String),
    Bad,
}

/// Every `{{` in the body, in order: a placeholder's name, or a bad one.
fn placeholders(body: &str) -> Vec<Placeholder> {
    let mut found = Vec::new();
    let mut at = 0;
    while let Some(start) = body[at..].find("{{").map(|i| at + i) {
        match placeholder_at(body, start) {
            Some((name, end)) => {
                found.push(Placeholder::Name(name));
                at = end;
            }
            None => {
                found.push(Placeholder::Bad);
                at = start + 2;
            }
        }
    }
    found
}

/// The placeholder `{{name}}` at `start`, and where it ends.
fn placeholder_at(text: &str, start: usize) -> Option<(String, usize)> {
    let rest = &text[start + 2..];
    let end = rest.find("}}")?;
    let name = &rest[..end];
    valid_param_name(name).then(|| (name.to_owned(), start + 2 + end + 2))
}

enum CheckRef {
    Placeholder(String),
    /// A `WIZLOOP_PARAM_` reference's run, as written.
    Env(String),
}

/// A check's placeholders and references, in the order of their place.
fn check_references(text: &str) -> Vec<CheckRef> {
    const PREFIX: &str = "WIZLOOP_PARAM_";
    let word = |b: u8| b.is_ascii_alphanumeric() || b == b'_';
    let bytes = text.as_bytes();
    let mut found = Vec::new();
    let mut at = 0;
    while at < text.len() {
        if text[at..].starts_with("{{") {
            if let Some((name, end)) = placeholder_at(text, at) {
                found.push(CheckRef::Placeholder(name));
                at = end;
                continue;
            }
        } else if text[at..].starts_with(PREFIX) && (at == 0 || !word(bytes[at - 1])) {
            let start = at + PREFIX.len();
            let end = start + bytes[start..].iter().take_while(|b| word(**b)).count();
            found.push(CheckRef::Env(text[start..end].to_owned()));
            at = end;
            continue;
        }
        at += text[at..].chars().next().map_or(1, char::len_utf8);
    }
    found
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
    valid_id(id).then(|| (id, &name[..open]))
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
pub fn rendered_body(file: &LoopFile) -> String {
    let mut out = String::new();
    let mut at = 0;
    while let Some(start) = file.body[at..].find("{{").map(|i| at + i) {
        out.push_str(&file.body[at..start]);
        match placeholder_at(&file.body, start)
            .and_then(|(name, end)| Some((file.params.iter().find(|(n, _)| *n == name)?, end)))
        {
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
fn carried_params(file: &LoopFile, check: &Check) -> Vec<(String, Param)> {
    let runs: BTreeSet<String> = check_references(&check.text)
        .into_iter()
        .filter_map(|r| match r {
            CheckRef::Env(run) => Some(run),
            CheckRef::Placeholder(_) => None,
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
pub fn rendered_script(file: &LoopFile, check: &Check) -> String {
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
pub fn file_refusals(file: &LoopFile, shown: &str) -> Vec<Refusal> {
    let mut refusals = Vec::new();
    if let Trigger::Cron { cron, .. } = &file.trigger
        && file.check.is_none()
        && too_frequent(cron)
    {
        refusals.push(Refusal::new(
            shown,
            "cf-too-frequent",
            "trigger.cron",
            "Cloudroom runs a loop without a check at most every 15 minutes",
        ));
    }
    if let Some(check) = &file.check {
        if !carried_params(file, check).is_empty()
            && !SHELLS.iter().any(|s| check.text.starts_with(s))
        {
            refusals.push(Refusal::new(shown, "cf-check-shell", "check.run", "Cloudroom passes params to a check through a shell preamble; its first line must be #!/bin/sh, #!/bin/bash, #!/usr/bin/env sh or #!/usr/bin/env bash"));
        }
        if check.text.split('\n').nth(1) == Some(PREAMBLE_START) {
            refusals.push(Refusal::new(
                shown,
                "cf-check-preamble",
                "check.run",
                "the check's second line is the adapter's preamble line; change that line",
            ));
        }
        if check.timeout != 60 {
            refusals.push(Refusal::new(
                shown,
                "cf-check-timeout",
                "check.timeout",
                "Cloudroom runs a check for exactly 60 seconds; set the timeout to 60",
            ));
        }
    }
    if !file.new_thread && file.agent.is_some() {
        refusals.push(Refusal::new(
            shown,
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
pub fn create_command(file: &LoopFile) -> RoomCommand {
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
        parse_json_document(stdout).map_err(|_| bad("not one JSON document with unique keys"))?;
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
                .as_int()
                .and_then(|p| p.parse().ok())
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
    files: &[ReadFile],
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
    for read in files {
        let mut item = PlanItem {
            file: read.file.clone(),
            id: read.id.clone(),
            action: Action::Refused,
            loop_id: None,
            paused: false,
            commands: Vec::new(),
            differences: Vec::new(),
            refusals: Vec::new(),
            notes: Vec::new(),
        };
        let file = match &read.result {
            Ok(file) => file,
            Err(refusals) => {
                item.refusals = refusals.clone();
                items.push(item);
                continue;
            }
        };
        if let Some(other) = claimed.get(&file.id) {
            item.refusals.push(Refusal::new(
                &read.file,
                "duplicate-id",
                "id",
                format!("{} is also the id of {other}", file.id),
            ));
            items.push(item);
            continue;
        }
        claimed.insert(file.id.clone(), read.file.clone());
        let marked = managed(&file.id);
        let binding: Vec<&String> = bindings
            .iter()
            .filter(|(id, _)| *id == file.id)
            .map(|(_, l)| l)
            .collect();
        let adopt_refusal = |loop_id: &str, reason: &str| {
            Refusal::new(
                &read.file,
                "cf-adopt-binding",
                "id",
                format!("the binding to Cloudroom loop {loop_id} cannot be used: {reason}"),
            )
        };
        let mut adopted = false;
        let target: Option<&LiveLoop> = if marked.len() > 1 {
            item.refusals.push(Refusal::new(
                &read.file,
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
            item.refusals.push(Refusal::new(&read.file, "cf-unmarked-match", "id", "an unmarked Cloudroom loop in this project has this name; adopt it or choose another id"));
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
    let ids: BTreeSet<&str> = files.iter().filter_map(|f| f.id.as_deref()).collect();
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

fn plan_create(item: &mut PlanItem, file: &LoopFile, now: i64) {
    let mut refusals = Vec::new();
    if let Trigger::At(at) = &file.trigger
        && instant(at).is_some_and(|(seconds, _)| seconds < now)
    {
        refusals.push(Refusal::new(
            &item.file,
            "cf-at-past",
            "trigger.at",
            "the time has passed",
        ));
    }
    refusals.extend(file_refusals(file, &item.file));
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

fn plan_update(item: &mut PlanItem, file: &LoopFile, live: &LiveLoop, adopted: bool) {
    item.loop_id = Some(live.loop_id.clone());
    item.paused = !live.enabled;
    let mut refusals = Vec::new();
    if matches!(file.trigger, Trigger::In(_)) {
        refusals.push(Refusal::new(
            &item.file,
            "cf-in-existing",
            "trigger.in",
            "an in trigger can only create a loop; write the at time instead",
        ));
    }
    refusals.extend(file_refusals(file, &item.file));
    let Some(live_trigger) = &live.trigger else {
        refusals.push(Refusal::new(
            &item.file,
            "cf-export-trigger",
            "trigger",
            "the loop has no cron, run time or webhook",
        ));
        item.refusals = refusals;
        return;
    };
    if (file.trigger == Trigger::Webhook) != (*live_trigger == Trigger::Webhook) {
        refusals.push(Refusal::new(
            &item.file,
            "cf-update-webhook",
            "trigger",
            "Cloudroom cannot change a loop to or from a webhook",
        ));
    }
    if file.new_thread != live.new_thread {
        refusals.push(Refusal::new(
            &item.file,
            "cf-update-thread",
            "thread",
            "Cloudroom cannot change a loop's thread",
        ));
    }
    if file.check.is_none() && live.script.is_some() {
        refusals.push(Refusal::new(
            &item.file,
            "cf-update-remove-check",
            "check",
            "Cloudroom cannot remove a loop's check",
        ));
    }
    if file.agent.is_none() && live.agent.is_some() {
        refusals.push(Refusal::new(
            &item.file,
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

    // catches: a JSON reader that collapses a repeated key, accepts a value
    // that is not exactly one JSON value, or reads 2.0 as an integer.
    #[test]
    fn the_strict_json_reader_keeps_order_and_refuses_duplicates() {
        assert_eq!(
            parse_json(r#"{"b": 1, "a": [2.0, "xé"]}"#),
            Ok(Json::Object(vec![
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
        assert_eq!(
            parse_json(r#"{"a": {"b": 1, "b": 2}}"#),
            Err(JsonError::Duplicate(vec!["a".into(), "b".into()]))
        );
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
            assert_eq!(parse_json(bad), Err(JsonError::Syntax), "{bad}");
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
