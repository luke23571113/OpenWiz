use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::{Instant, SystemTime, UNIX_EPOCH};

use openwiz_adapter_cloudroom::loop_files::{
    self, Action, Difference, PlanItem, Refusal, RoomCommand, Written,
};
use openwiz_adapter_cloudroom::source::CloudRoomSource;
use serde_json::{Value, json};

use super::{Args, escape_untrusted as esc, loop_plan};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Outcome {
    Created,
    Updated,
    Unchanged,
    Different,
    Refused,
    Failed,
    Unknown,
}

impl Outcome {
    fn word(self) -> &'static str {
        match self {
            Self::Created => "created",
            Self::Updated => "updated",
            Self::Unchanged => "unchanged",
            Self::Different => "different",
            Self::Refused => "refused",
            Self::Failed => "failed",
            Self::Unknown => "unknown",
        }
    }

    fn exit_code(self) -> i32 {
        match self {
            Self::Created | Self::Updated | Self::Unchanged => 0,
            Self::Different | Self::Refused | Self::Failed => 5,
            Self::Unknown => 6,
        }
    }
}

struct Report {
    file: String,
    action: String,
    loop_id: Option<String>,
    commands: Vec<RoomCommand>,
    outcome: Outcome,
    read_back: Option<Vec<Difference>>,
    refusals: Vec<Refusal>,
    webhook_address: Option<String>,
    notes: Vec<String>,
    unclear: Option<String>,
    previewed: bool,
}

pub fn run(args: &Args, stdout: &mut dyn Write, stderr: &mut dyn Write) -> i32 {
    let fail =
        |stdout: &mut dyn Write, stderr: &mut dyn Write, code: i32, kind: &str, message: String| {
            let _ = writeln!(stderr, "openwiz: loop apply: {}", esc(&message));
            if args.json {
                let doc = json!({
                    "schema": "openwiz.cli-error.v1", "command": "loop.apply", "exit_code": code,
                    "error": {"kind": kind, "message": message},
                });
                let _ = writeln!(stdout, "{doc}");
            }
            code
        };
    let id = args.operands[0].as_str();
    let project = args.project.as_deref().unwrap_or_default();
    if let Some((other, _)) = args.adopt.iter().find(|(bound, _)| bound != id) {
        return fail(
            stdout,
            stderr,
            2,
            "usage",
            format!("--adopt names the id {other}, not {id}; nothing was read"),
        );
    }
    let shown = args.file.clone().unwrap_or_else(|| format!("./{id}.md"));
    if Path::new(&shown).is_dir() {
        return fail(
            stdout,
            stderr,
            1,
            "read_failed",
            format!("{shown} is a folder, not one loop file; nothing was applied"),
        );
    }
    let files = match loop_files::read_paths(std::slice::from_ref(&shown)) {
        Ok(files) => files,
        Err(why) => {
            return fail(
                stdout,
                stderr,
                1,
                "read_failed",
                format!("{why}; nothing was applied"),
            );
        }
    };
    let read = &files[0].1;
    let mut report = Report {
        file: shown.clone(),
        action: "refused".into(),
        loop_id: None,
        commands: Vec::new(),
        outcome: Outcome::Refused,
        read_back: None,
        refusals: Vec::new(),
        webhook_address: None,
        notes: Vec::new(),
        unclear: None,
        previewed: false,
    };
    if let Some(file_id) = read.id.as_deref().filter(|f| *f != id) {
        report.refusals.push(Refusal {
            code: "apply-id-mismatch",
            field: "id".into(),
            message: format!("the file's id is {file_id}, not {id}"),
        });
        return finish(args, project, id, &report, stdout, stderr);
    }
    let source = CloudRoomSource::from_path();
    let deadline = || Instant::now() + openwiz_core::limits::READ_TIMEOUT;
    let live = match source.loop_files_list(deadline()) {
        Ok(live) => live,
        Err(e) => {
            return fail(
                stdout,
                stderr,
                1,
                "read_failed",
                format!("room-cli loop list {e}; nothing was applied"),
            );
        }
    };
    let now = || {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_or(0, |d| i64::try_from(d.as_secs()).unwrap_or(i64::MAX))
    };
    let item: PlanItem = loop_files::plan(&files, &live, project, &args.adopt, now())
        .items
        .remove(0);
    report.action = item.action_word();
    report.loop_id.clone_from(&item.loop_id);
    report.commands.clone_from(&item.commands);
    report.notes.clone_from(&item.notes);
    match item.action {
        Action::Refused => {
            report.refusals = item.refusals;
            return finish(args, project, id, &report, stdout, stderr);
        }
        Action::None => {
            report.outcome = Outcome::Unchanged;
            return finish(args, project, id, &report, stdout, stderr);
        }
        Action::Create | Action::Update => {}
    }
    if let Some(target) = live
        .iter()
        .find(|l| Some(&l.loop_id) == item.loop_id.as_ref())
        .filter(|l| !l.unmapped.is_empty())
    {
        report.refusals.push(Refusal {
            code: "apply-unmapped",
            field: "file".into(),
            message: format!(
                "Cloudroom loop {} carries settings the adapter does not map ({}), and nothing shows that a write keeps them; nothing was written",
                target.loop_id,
                target.unmapped.join(", ")
            ),
        });
        return finish(args, project, id, &report, stdout, stderr);
    }
    if !args.json && stdout.write_all(preview(&report).as_bytes()).is_err() {
        let _ = writeln!(
            stderr,
            "openwiz: loop apply: the output could not be written; nothing was applied"
        );
        return 1;
    }
    report.previewed = true;
    let dir = match private_folder() {
        Ok(dir) => dir,
        Err(e) => {
            return fail(
                stdout,
                stderr,
                1,
                "write_failed",
                format!("apply's temporary folder could not be made ({e}); nothing was applied"),
            );
        }
    };
    let clock = || {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
    };
    let seconds = |d: std::time::Duration| i64::try_from(d.as_secs()).unwrap_or(i64::MAX);
    let before = seconds(clock());
    let mut accepted = true;
    for command in &item.commands {
        let written = source.loop_files_write(command, &dir, deadline());
        match written {
            Ok(Written::Accepted(out)) => {
                if item.action == Action::Create {
                    report.webhook_address = loop_files::webhook_address(&out).map(str::to_owned);
                }
            }
            Ok(Written::Refused(message)) => {
                report.outcome = Outcome::Failed;
                report.refusals.push(Refusal {
                    code: "room-cli",
                    field: "file".into(),
                    message,
                });
                accepted = false;
                break;
            }
            Ok(Written::Unclear(why)) => {
                report.outcome = Outcome::Unknown;
                report.unclear = Some(why);
                accepted = false;
                break;
            }
            Err(e) => {
                let _ = std::fs::remove_dir_all(&dir);
                return fail(
                    stdout,
                    stderr,
                    1,
                    "write_failed",
                    format!("a file for room-cli could not be written ({e}); nothing was run"),
                );
            }
        }
    }
    let after = clock();
    let after = seconds(after).saturating_add(i64::from(after.subsec_nanos() > 0));
    let _ = std::fs::remove_dir_all(&dir);
    if accepted {
        let written = (before, after);
        read_back(
            &mut report,
            item.action,
            &source,
            &files,
            project,
            now(),
            written,
        );
    }
    finish(args, project, id, &report, stdout, stderr)
}

fn read_back(
    report: &mut Report,
    action: Action,
    source: &CloudRoomSource,
    files: &[(String, loop_files::FileRead)],
    project: &str,
    now: i64,
    written: (i64, i64),
) {
    let deadline = Instant::now() + openwiz_core::limits::READ_TIMEOUT;
    let live = match source.loop_files_list(deadline) {
        Ok(live) => live,
        Err(e) => {
            report.outcome = Outcome::Unknown;
            report.unclear = Some(format!(
                "room-cli loop list {e} after Cloudroom accepted the write"
            ));
            return;
        }
    };
    let (shown, read) = &files[0];
    let item = loop_files::read_back(shown, read, &live, project, now, written);
    match item.action {
        Action::None | Action::Update => {
            report.loop_id = item.loop_id;
            report.outcome = match (item.differences.is_empty(), action) {
                (false, _) => Outcome::Different,
                (true, Action::Create) => Outcome::Created,
                (true, _) => Outcome::Updated,
            };
            report.read_back = Some(item.differences);
        }
        Action::Create | Action::Refused => {
            report.outcome = Outcome::Unknown;
            report.refusals.extend(item.refusals);
            report.read_back = Some(Vec::new());
            report.unclear = Some(
                "Cloudroom accepted the write, and the read-back shows no one loop of this project with this file's marker to compare"
                    .into(),
            );
        }
    }
}

fn private_folder() -> std::io::Result<PathBuf> {
    use std::os::unix::fs::DirBuilderExt as _;
    let stamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |d| d.as_nanos());
    let mut n = 0u32;
    loop {
        let dir = std::env::temp_dir().join(format!(
            "openwiz-loop-apply-{}-{stamp}-{n}",
            std::process::id()
        ));
        match std::fs::DirBuilder::new().mode(0o700).create(&dir) {
            Ok(()) => return Ok(dir),
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists && n < 100 => n += 1,
            Err(e) => return Err(e),
        }
    }
}

fn finish(
    args: &Args,
    project: &str,
    id: &str,
    report: &Report,
    stdout: &mut dyn Write,
    stderr: &mut dyn Write,
) -> i32 {
    let code = report.outcome.exit_code();
    let written = if args.json {
        writeln!(stdout, "{}", document(report, project, id, code))
    } else {
        let mut text = if report.previewed {
            String::new()
        } else {
            preview(report)
        };
        text.push_str(&summary(report));
        stdout.write_all(text.as_bytes())
    };
    if written.is_err() {
        let _ = writeln!(
            stderr,
            "openwiz: loop apply: the output could not be written"
        );
        return 1;
    }
    code
}

fn document(report: &Report, project: &str, id: &str, code: i32) -> Value {
    let file = &report.file;
    let mut doc = json!({
        "schema": "openwiz.loop-apply.v1", "command": "apply", "exit_code": code,
        "project": project, "id": id, "file": file, "action": report.action,
        "loop": report.loop_id,
        "commands": report.commands.iter().map(RoomCommand::to_json).collect::<Vec<_>>(),
        "outcome": report.outcome.word(),
        "read_back": report.read_back.as_ref().map(|differences| json!({
            "differences": differences.iter().map(|d| json!({"field": d.field, "file": d.file, "live": d.live})).collect::<Vec<_>>(),
        })),
        "refusals": report.refusals.iter().map(|r| json!({"file": file, "code": r.code, "field": r.field, "message": r.message})).collect::<Vec<_>>(),
    });
    if let Some(address) = &report.webhook_address {
        doc["webhook_address"] = json!(address);
    }
    doc
}

fn preview(report: &Report) -> String {
    let file = esc(&report.file);
    let mut out = match &report.loop_id {
        Some(l) => format!("{file}: {} {}\n", report.action, esc(l)),
        None => format!("{file}: {}\n", report.action),
    };
    for command in &report.commands {
        let argv: Vec<String> = command
            .argv()
            .iter()
            .map(|a| loop_plan::quoted(a))
            .collect();
        out.push_str(&format!("  room-cli {}\n", argv.join(" ")));
        for (name, text) in &command.files {
            out.push_str(&format!("  {name}:\n{}", loop_plan::block(text)));
            if !text.ends_with('\n') {
                out.push('\n');
            }
        }
    }
    for note in &report.notes {
        out.push_str(&format!("{file}: note: {}\n", esc(note)));
    }
    out
}

fn summary(report: &Report) -> String {
    let file = esc(&report.file);
    let mut out = match &report.loop_id {
        Some(l) => format!("{file}: {} {}\n", report.outcome.word(), esc(l)),
        None => format!("{file}: {}\n", report.outcome.word()),
    };
    if let Some(why) = &report.unclear {
        out.push_str(&format!(
            "{file}: unknown: {}; it was not retried, so read the loop with openwiz loop plan before applying again\n",
            esc(why)
        ));
    }
    for r in &report.refusals {
        out.push_str(&format!("{file}: {}: {}\n", esc(&r.field), esc(&r.message)));
    }
    for d in report.read_back.iter().flatten() {
        out.push_str(&format!(
            "{file}: {}: {} -> {}\n",
            d.field,
            esc(&d.live.to_string()),
            esc(&d.file.to_string())
        ));
    }
    if let Some(address) = &report.webhook_address {
        out.push_str(&format!(
            "{file}: webhook address, shown this once: {}\n",
            esc(address)
        ));
    }
    out
}
