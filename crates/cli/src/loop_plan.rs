//! `openwiz loop plan <path>... --project <project> [--adopt <id>=<loop>]...
//! [--json]` (LC4, #792): a dry run. It reads the files and one `room-cli
//! loop list`, prints each file's exact `room-cli loop create` or `update`
//! and its differences against the managed loop, and changes nothing.
//! The rules are the adapter's (`openwiz_adapter_cloudroom::loop_files`);
//! the result and exits are `contracts/loop-cli.v1.md`'s.

use std::io::Write;
use std::time::{Instant, SystemTime, UNIX_EPOCH};

use openwiz_adapter_cloudroom::loop_files::{self, Plan, PlanItem, RoomCommand};
use openwiz_adapter_cloudroom::source::CloudRoomSource;
use serde_json::{Value, json};

use super::{Args, escape_untrusted as esc};

/// Runs a parsed `loop plan`.
pub fn run(args: &Args, stdout: &mut dyn Write, stderr: &mut dyn Write) -> i32 {
    let fail =
        |stdout: &mut dyn Write, stderr: &mut dyn Write, code: i32, kind: &str, message: String| {
            let _ = writeln!(stderr, "openwiz: loop plan: {}", esc(&message));
            if args.json {
                let doc = json!({
                    "schema": "openwiz.cli-error.v1", "command": "loop.plan", "exit_code": code,
                    "error": {"kind": kind, "message": message},
                });
                let _ = writeln!(stdout, "{doc}");
            }
            code
        };
    let files = match loop_files::read_paths(&args.operands) {
        Ok(files) => files,
        Err(why) => {
            return fail(
                stdout,
                stderr,
                1,
                "read_failed",
                format!("{why}; nothing was planned"),
            );
        }
    };
    // A binding must name a file being planned; checked before any read.
    if let Some((id, _)) = args
        .adopt
        .iter()
        .find(|(id, _)| !files.iter().any(|(_, f)| f.id.as_deref() == Some(id)))
    {
        return fail(
            stdout,
            stderr,
            2,
            "usage",
            format!("--adopt names the id {id}, which no file given has; nothing was read"),
        );
    }
    let deadline = Instant::now() + openwiz_core::limits::READ_TIMEOUT;
    let live = match CloudRoomSource::from_path().loop_files_list(deadline) {
        Ok(live) => live,
        Err(e) => {
            return fail(
                stdout,
                stderr,
                1,
                "read_failed",
                format!("room-cli loop list {e}; nothing was planned"),
            );
        }
    };
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |d| i64::try_from(d.as_secs()).unwrap_or(i64::MAX));
    let project = args.project.as_deref().unwrap_or_default();
    let plan = loop_files::plan(&files, &live, project, &args.adopt, now);
    let code = if plan.items.iter().any(|i| !i.refusals.is_empty()) {
        5
    } else {
        0
    };
    let written = if args.json {
        writeln!(stdout, "{}", report(&plan, project, code))
    } else {
        stdout.write_all(text(&plan).as_bytes())
    };
    if written.is_err() {
        let _ = writeln!(
            stderr,
            "openwiz: loop plan: the output could not be written"
        );
        return 1;
    }
    code
}

/// The `openwiz.loop-plan.v1` document.
fn report(plan: &Plan, project: &str, code: i32) -> Value {
    let items: Vec<Value> = plan.items.iter().map(item_json).collect();
    json!({
        "schema": "openwiz.loop-plan.v1", "command": "plan", "exit_code": code,
        "project": project, "items": items,
        "unmanaged": plan.unmanaged.iter().map(|(l, name)| json!({"loop": l, "name": name})).collect::<Vec<_>>(),
        "orphans": plan.orphans.iter().map(|(l, id)| json!({"loop": l, "id": id})).collect::<Vec<_>>(),
    })
}

fn item_json(item: &PlanItem) -> Value {
    json!({
        "file": item.file, "id": item.id, "action": item.action_word(), "loop": item.loop_id,
        "paused": item.paused,
        "commands": item.commands.iter().map(RoomCommand::to_json).collect::<Vec<_>>(),
        "differences": item.differences.iter().map(|d| json!({"field": d.field, "file": d.file, "live": d.live})).collect::<Vec<_>>(),
        "refusals": item.refusals.iter().map(|r| json!({"file": item.file, "code": r.code, "field": r.field, "message": r.message})).collect::<Vec<_>>(),
        "notes": item.notes,
    })
}

/// A word for `sh` that reads back byte for byte, with nothing a terminal
/// acts on: safe text single-quoted (line breaks included, so a prompt stays
/// readable), and each other character as `"$(printf '\ooo')"`, the octal of
/// its UTF-8 bytes. The value itself is never changed.
fn quoted(word: &str) -> String {
    let mut out = String::from("'");
    for c in word.chars() {
        let s = c.to_string();
        if c == '\n' || esc(&s) == s {
            out.push_str(&s.replace('\'', "'\\''"));
        } else {
            let octal: String = s.bytes().map(|b| format!("\\{b:03o}")).collect();
            out.push_str(&format!("'\"$(printf '{octal}')\"'"));
        }
    }
    out.push('\'');
    out
}

/// A block of untrusted text, escaped line by line so its breaks stay.
fn block(text: &str) -> String {
    text.split('\n').map(esc).collect::<Vec<_>>().join("\n")
}

/// The text for people: one block per file, then the loops left alone.
/// Every untrusted string goes through [`esc`]; JSON keeps the originals.
fn text(plan: &Plan) -> String {
    let mut out = String::new();
    for item in &plan.items {
        let file = esc(&item.file);
        let what = match &item.loop_id {
            Some(l) if item.action == loop_files::Action::None => {
                format!("no change to {}", esc(l))
            }
            Some(l) => format!("{} {}", item.action_word(), esc(l)),
            None => item.action_word(),
        };
        let paused = if item.paused { " (paused)" } else { "" };
        out.push_str(&format!("{file}: {what}{paused}\n"));
        for r in &item.refusals {
            out.push_str(&format!("{file}: {}: {}\n", esc(&r.field), esc(&r.message)));
        }
        for d in &item.differences {
            out.push_str(&format!(
                "{file}: {}: {} -> {}\n",
                d.field,
                esc(&d.live.to_string()),
                esc(&d.file.to_string())
            ));
        }
        for command in &item.commands {
            let argv: Vec<String> = command.argv().iter().map(|a| quoted(a)).collect();
            out.push_str(&format!("  room-cli {}\n", argv.join(" ")));
            for (name, text) in &command.files {
                out.push_str(&format!("  {name}:\n{}", block(text)));
                if !text.ends_with('\n') {
                    out.push('\n');
                }
            }
        }
        for note in &item.notes {
            out.push_str(&format!("{file}: note: {}\n", esc(note)));
        }
    }
    for (l, name) in &plan.unmanaged {
        out.push_str(&format!("unmanaged: {}: {}\n", esc(l), esc(name)));
    }
    for (l, id) in &plan.orphans {
        out.push_str(&format!("no file: {}: {}\n", esc(l), esc(id)));
    }
    out.push_str("Nothing was changed.\n");
    out
}
