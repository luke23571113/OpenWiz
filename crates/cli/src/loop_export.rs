//! `openwiz loop export --project <project> [--out <dir>] [--json]` (LC3,
//! #791; `contracts/loop-cli.v1.md`). One `room-cli loop list --json` read,
//! then one loop file (and its check) per loop of the project, by the
//! adapter's rules. A file that already exists is never replaced: the same
//! bytes are `unchanged`, other bytes refuse that loop with `export-exists`.
//! A loop the adapter cannot represent is reported with its refusals, and
//! the others are still written.

use std::fs;
use std::io::{ErrorKind, Write};
use std::path::{Path, PathBuf};
use std::time::Instant;

use openwiz_adapter_cloudroom::loop_files::{self, Exported, Refusal};
use openwiz_adapter_cloudroom::source::CloudRoomSource;
use openwiz_core::limits::RUN_BUDGET;
use serde_json::{Value, json};

use crate::loop_files::{Args, escape_untrusted};

/// One loop's result in the report.
struct Outcome {
    exported: Exported,
    result: &'static str,
    files: Vec<String>,
}

/// Runs export with parsed `args`; returns the exit code.
pub fn run(args: &Args, stdout: &mut dyn Write, stderr: &mut dyn Write) -> i32 {
    let project = args.project.as_deref().unwrap_or_default();
    let out = args.out.as_deref().unwrap_or(".");
    let source = CloudRoomSource::from_path();
    let read = loop_files::read_list(&source, Instant::now() + RUN_BUDGET)
        .and_then(|items| loop_files::export_project(&items, project));
    let exports = match read {
        Ok(exports) => exports,
        Err(why) => {
            return failed(
                args.json,
                &format!("room-cli loop list failed: {why}; nothing was written"),
                "The loop list could not be read; nothing was written.",
                stdout,
                stderr,
            );
        }
    };
    let mut outcomes = Vec::new();
    for exported in exports {
        match write(Path::new(out), exported) {
            Ok(outcome) => outcomes.push(outcome),
            Err(why) => {
                return failed(
                    args.json,
                    &format!("could not write to {out}: {why}; the loops before it were written"),
                    "The export folder could not be written; the loops before it were written.",
                    stdout,
                    stderr,
                );
            }
        }
    }
    let code = if outcomes.iter().any(|o| o.result == "refused") {
        5
    } else {
        0
    };
    let printed = if args.json {
        let loops: Vec<Value> = outcomes.iter().map(entry).collect();
        let doc = json!({
            "schema": "openwiz.loop-export.v1", "command": "export", "exit_code": code,
            "project": project, "out": out, "loops": loops,
        });
        writeln!(stdout, "{doc}")
    } else {
        text(&outcomes, project, out, stdout, stderr)
    };
    if printed.is_err() { 1 } else { code }
}

/// Writes one loop's files under `out`, never replacing one with other
/// bytes. Every file is checked before any is written, so a refused loop
/// writes nothing.
fn write(out: &Path, mut exported: Exported) -> std::io::Result<Outcome> {
    if !exported.refusals.is_empty() {
        return Ok(Outcome {
            exported,
            result: "refused",
            files: Vec::new(),
        });
    }
    let mut missing = Vec::new();
    let mut exists = Vec::new();
    for (rel, text) in &exported.files {
        let path = out.join(rel);
        // A check's folder must be a real folder or nothing yet: never a
        // file, and never a link that would put the check elsewhere.
        if let Some((folder, _)) = rel.split_once('/') {
            match fs::symlink_metadata(out.join(folder)) {
                Err(e) if e.kind() == ErrorKind::NotFound => {}
                Err(e) => return Err(e),
                Ok(meta) if meta.is_dir() => {}
                Ok(_) => {
                    exists.push(out.join(folder));
                    continue;
                }
            }
        }
        match fs::symlink_metadata(&path) {
            Err(e) if e.kind() == ErrorKind::NotFound => missing.push(rel.clone()),
            Err(e) => return Err(e),
            Ok(meta) if meta.is_file() && fs::read(&path)? == text.as_bytes() => {}
            Ok(_) => exists.push(path),
        }
    }
    for path in exists {
        exported.refusals.push(Refusal {
            file: exported.name.clone(),
            code: "export-exists".into(),
            field: "file".into(),
            message: format!(
                "{} already exists with other bytes; nothing was written for this loop",
                path.display()
            ),
        });
    }
    if !exported.refusals.is_empty() {
        return Ok(Outcome {
            exported,
            result: "refused",
            files: Vec::new(),
        });
    }
    for (rel, text) in exported
        .files
        .iter()
        .filter(|(rel, _)| missing.contains(rel))
    {
        let path = out.join(rel);
        fs::create_dir_all(out)?;
        if let Some((folder, _)) = rel.split_once('/') {
            match fs::create_dir(out.join(folder)) {
                Err(e) if e.kind() != ErrorKind::AlreadyExists => return Err(e),
                _ => {}
            }
        }
        // `create_new`: never through a file or link that appeared meanwhile.
        fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&path)?
            .write_all(text.as_bytes())?;
    }
    let files = exported.files.iter().map(|(rel, _)| rel.clone()).collect();
    let result = if missing.is_empty() {
        "unchanged"
    } else {
        "written"
    };
    Ok(Outcome {
        exported,
        result,
        files,
    })
}

fn entry(outcome: &Outcome) -> Value {
    let e = &outcome.exported;
    json!({
        "loop": e.loop_id,
        "id": e.id,
        "result": outcome.result,
        "files": outcome.files,
        "binding": e.binding.as_ref().map(|id| json!({"id": id, "loop": e.loop_id})),
        "refusals": e.refusals.iter().map(|r| json!({
            "file": r.file, "code": r.code, "field": r.field, "message": r.message,
        })).collect::<Vec<_>>(),
        "unmapped": e.unmapped,
    })
}

fn text(
    outcomes: &[Outcome],
    project: &str,
    out: &str,
    stdout: &mut dyn Write,
    stderr: &mut dyn Write,
) -> std::io::Result<()> {
    let done = outcomes.iter().filter(|o| o.result != "refused").count();
    line(
        stdout,
        &format!(
            "Exported {done} of {} loops of project {project} to {out}.",
            outcomes.len()
        ),
    )?;
    for o in outcomes {
        let e = &o.exported;
        let id = e.id.as_deref().unwrap_or("-");
        let files: Vec<String> = o
            .files
            .iter()
            .map(|f| PathBuf::from(out).join(f).display().to_string())
            .collect();
        line(
            stdout,
            &format!("  {} {id}: {} {}", e.loop_id, o.result, files.join(" ")),
        )?;
        if let Some(binding) = &e.binding {
            line(
                stdout,
                &format!(
                    "    unmarked: plan and apply need --adopt {binding}={}",
                    e.loop_id
                ),
            )?;
        }
        if !e.unmapped.is_empty() {
            line(
                stdout,
                &format!(
                    "    unmapped: the file does not carry {}, which Cloudroom returned and the adapter does not map",
                    e.unmapped.join(", ")
                ),
            )?;
        }
        for r in &e.refusals {
            line(stderr, &format!("{}: {}: {}", r.file, r.field, r.message))?;
        }
    }
    Ok(())
}

/// A failure before any result: one line on stderr, and with `--json` one
/// `openwiz.cli-error.v1` document that carries none of room-cli's text.
fn failed(
    json: bool,
    what: &str,
    message: &str,
    stdout: &mut dyn Write,
    stderr: &mut dyn Write,
) -> i32 {
    let _ = line(stderr, &format!("openwiz: loop export: {what}"));
    if json {
        let doc = json!({
            "schema": "openwiz.cli-error.v1", "command": "loop.export", "exit_code": 1,
            "error": {"kind": "read_failed", "message": message},
        });
        let _ = writeln!(stdout, "{doc}");
    }
    1
}

/// Prints one line of human output with every untrusted part escaped: no
/// line here carries a control of its own, so the whole line is escaped.
fn line(stream: &mut dyn Write, text: &str) -> std::io::Result<()> {
    writeln!(stream, "{}", escape_untrusted(text))
}
