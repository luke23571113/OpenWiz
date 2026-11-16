//! `openwiz loop validate <path>... [--catalog] [--json]` (LC2, #790): checks
//! loop files against the pinned WizLoops format with the Cloudroom
//! adapter's reader, and prints every refusal by file and field, as
//! `contracts/loop-cli.v1.md` says. It reads only the named files and
//! folders: no `room-cli`, no state.

use std::io::Write;
use std::path::Path;

use openwiz_adapter_cloudroom::loop_files::{self, FileRead, Refusal};
use serde_json::{Value, json};

use super::Args;

/// One loop file in the report.
struct Entry {
    file: String,
    read: FileRead,
}

/// Runs `validate` on the parsed arguments.
pub fn run(args: &Args, stdout: &mut dyn Write, stderr: &mut dyn Write) -> i32 {
    let mut files = Vec::new();
    let mut folder_refusals = Vec::new();
    for given in &args.operands {
        let path = Path::new(given);
        let read = if path.is_dir() {
            loop_files::read_loop_folder(path, args.catalog).map(|folder| {
                // Inside a folder: the folder's path, then `/` and the name.
                let base = given.strip_suffix('/').unwrap_or(given);
                for (name, read) in folder.files {
                    let file = format!("{base}/{name}");
                    files.push(Entry { file, read });
                }
                for (name, refusal) in folder.refusals {
                    folder_refusals.push((format!("{base}/{name}"), refusal));
                }
            })
        } else {
            loop_files::read_loop_path(path).map(|read| {
                files.push(Entry {
                    file: given.clone(),
                    read,
                });
            })
        };
        if let Err(error) = read {
            return unreadable(given, &error, args.json, stdout, stderr);
        }
    }
    let refused = !folder_refusals.is_empty() || files.iter().any(|e| !e.read.refusals.is_empty());
    let code = if refused { 5 } else { 0 };
    let written = if args.json {
        let doc = json!({
            "schema": "openwiz.loop-validate.v1",
            "command": "validate",
            "exit_code": code,
            "files": files.iter().map(|e| json!({
                "file": e.file,
                "id": e.read.id,
                "result": if e.read.refusals.is_empty() { "valid" } else { "refused" },
                "refusals": e.read.refusals.iter().map(|r| refusal(&e.file, r)).collect::<Vec<_>>(),
            })).collect::<Vec<_>>(),
            "folder_refusals": folder_refusals.iter().map(|(f, r)| refusal(f, r)).collect::<Vec<_>>(),
        });
        writeln!(stdout, "{doc}")
    } else {
        text(&files, &folder_refusals, stdout)
    };
    if written.is_err() {
        return 1;
    }
    code
}

fn refusal(file: &str, r: &Refusal) -> Value {
    json!({"file": file, "code": r.code, "field": r.field, "message": r.message})
}

/// The text form: each refusal as `<file>: <field>: <message>`, the
/// format's line form, and `<file>: valid` for each valid file.
fn text(
    files: &[Entry],
    folder_refusals: &[(String, Refusal)],
    out: &mut dyn Write,
) -> std::io::Result<()> {
    for entry in files {
        if entry.read.refusals.is_empty() {
            writeln!(out, "{}: valid", entry.file)?;
        }
        for r in &entry.read.refusals {
            writeln!(out, "{}: {}: {}", entry.file, r.field, r.message)?;
        }
    }
    for (file, r) in folder_refusals {
        writeln!(out, "{file}: {}: {}", r.field, r.message)?;
    }
    Ok(())
}

/// A path that could not be read: no report, the contract's error, exit 1.
fn unreadable(
    given: &str,
    error: &std::io::Error,
    json: bool,
    stdout: &mut dyn Write,
    stderr: &mut dyn Write,
) -> i32 {
    let message = format!("Could not read {given}: {error}.");
    let _ = writeln!(stderr, "openwiz: loop validate: {message}");
    if json {
        let doc = json!({
            "schema": "openwiz.cli-error.v1", "command": "loop.validate", "exit_code": 1,
            "error": {"kind": "read_failed", "message": message},
        });
        let _ = writeln!(stdout, "{doc}");
    }
    1
}
