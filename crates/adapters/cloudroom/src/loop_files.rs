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

use std::io;
use std::path::Path;

use serde_json::{Map, Value};

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
        if name.ends_with(".md") && name != "README.md" && entry.path().is_file() {
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
