//! `openwiz loop validate|export|plan|apply`: loop files in the pinned WizLoops
//! format (`contracts/wizloops-loop.v1.md`), with Cloudroom as the adapter
//! (`contracts/wizloops-cloudroom.v1.md`). The arguments, results and exits
//! are `contracts/loop-cli.v1.md`'s.
//!
//! LC1 (#789) ships [`parse`], the contract's argument rules, and stubs: each
//! command parses its arguments, then refuses with the `not_built` result,
//! reading nothing and changing nothing. LC2 to LC5 (#790 to #793) each
//! replace one stub in [`run`]. `loop off|on` stay in `loops.rs`, unchanged.

use std::ffi::OsString;
use std::io::Write;

use crate::response;

#[path = "loop_export.rs"]
mod loop_export;

pub const USAGE: &str = "  openwiz loop validate <path>... [--catalog] [--json]
  openwiz loop export --project <project> [--out <dir>] [--json]
  openwiz loop plan <path>... --project <project> [--adopt <id>=<loop>]... [--json]
  openwiz loop apply <id> --project <project> [--from <path>] [--adopt <id>=<loop>] [--json]
";
pub const HELP: &str = "loop validate/export/plan/apply
  Loop files in the WizLoops format, with Cloudroom as the adapter
  (contracts/loop-cli.v1.md). Not built yet: each command refuses with exit 5
  and reads and changes nothing.
";

/// The four loop-file commands.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Command {
    Validate,
    Export,
    Plan,
    Apply,
}

impl Command {
    pub fn from_word(word: &str) -> Option<Self> {
        Some(match word {
            "validate" => Self::Validate,
            "export" => Self::Export,
            "plan" => Self::Plan,
            "apply" => Self::Apply,
            _ => return None,
        })
    }

    pub fn word(self) -> &'static str {
        match self {
            Self::Validate => "validate",
            Self::Export => "export",
            Self::Plan => "plan",
            Self::Apply => "apply",
        }
    }

    /// The ticket that builds this command.
    pub fn ticket(self) -> u32 {
        match self {
            Self::Validate => 790,
            Self::Export => 791,
            Self::Plan => 792,
            Self::Apply => 793,
        }
    }

    /// The options this command accepts, besides `--json` and `--help`.
    fn options(self) -> &'static [&'static str] {
        match self {
            Self::Validate => &["--catalog"],
            Self::Export => &["--project", "--out"],
            Self::Plan => &["--project", "--adopt"],
            Self::Apply => &["--project", "--from", "--adopt"],
        }
    }
}

/// One parsed run, as the contract's "Arguments" pins it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Args {
    pub command: Command,
    /// `validate` and `plan`: the paths; `apply`: the one id; `export`: none.
    pub operands: Vec<String>,
    pub catalog: bool,
    pub project: Option<String>,
    pub out: Option<String>,
    pub file: Option<String>,
    /// `--adopt <id>=<loop>` bindings, in the order given.
    pub adopt: Vec<(String, String)>,
    pub json: bool,
}

/// What the arguments ask for.
#[derive(Debug, PartialEq, Eq)]
pub enum Parsed {
    Run(Args),
    Help { json: bool },
}

/// Whether `word` is one of this module's commands, for the dispatcher.
pub fn handles(word: Option<&str>) -> bool {
    word.and_then(Command::from_word).is_some()
}

/// Whether `--json` selects JSON: an exact token before `--`. No value may
/// start with `-`, so this is the same answer [`parse`] gives.
fn json_selected(args: &[OsString]) -> bool {
    args.iter()
        .take_while(|a| *a != "--")
        .any(|a| a == "--json")
}

/// Parses the arguments after `loop`, starting with the command word.
pub fn parse(args: &[OsString]) -> Result<Parsed, String> {
    let strings: Vec<&str> = args
        .iter()
        .map(|a| a.to_str())
        .collect::<Option<_>>()
        .ok_or("an argument is not valid UTF-8")?;
    let (word, rest) = strings.split_first().ok_or("missing loop command")?;
    let command = Command::from_word(word).ok_or("unknown loop command")?;
    let json = json_selected(args);
    let options_end = rest.iter().position(|a| *a == "--").unwrap_or(rest.len());
    if rest[..options_end]
        .iter()
        .any(|a| *a == "--help" || *a == "-h")
    {
        return Ok(Parsed::Help { json });
    }
    let mut parsed = Args {
        command,
        operands: Vec::new(),
        catalog: false,
        project: None,
        out: None,
        file: None,
        adopt: Vec::new(),
        json,
    };
    let mut seen_json = false;
    let mut options = rest[..options_end].iter();
    while let Some(&token) = options.next() {
        if !token.starts_with('-') {
            parsed.operands.push(token.to_owned());
            continue;
        }
        if token == "--json" {
            if std::mem::replace(&mut seen_json, true) {
                return Err("--json appears more than once".into());
            }
            continue;
        }
        if !command.options().contains(&token) {
            return Err(format!("loop {word} has no option {token}"));
        }
        if token == "--catalog" {
            if std::mem::replace(&mut parsed.catalog, true) {
                return Err("--catalog appears more than once".into());
            }
            continue;
        }
        let value = *options
            .next()
            .filter(|v| !v.is_empty() && !v.starts_with('-') && !v.chars().any(char::is_control))
            .ok_or_else(|| format!("{token} needs a value"))?;
        let slot = match token {
            "--project" => &mut parsed.project,
            "--out" => &mut parsed.out,
            "--from" => &mut parsed.file,
            _ => {
                let (id, target) = value
                    .split_once('=')
                    .filter(|(id, target)| !id.is_empty() && !target.is_empty())
                    .ok_or("--adopt needs <id>=<loop>")?;
                if command == Command::Apply && !parsed.adopt.is_empty() {
                    return Err("--adopt appears more than once".into());
                }
                parsed.adopt.push((id.to_owned(), target.to_owned()));
                continue;
            }
        };
        if slot.replace(value.to_owned()).is_some() {
            return Err(format!("{token} appears more than once"));
        }
    }
    // Everything after `--` is an operand, even one that starts with `-`.
    parsed
        .operands
        .extend(rest.iter().skip(options_end + 1).map(|a| (*a).to_owned()));
    let operands_ok = match command {
        Command::Validate | Command::Plan => !parsed.operands.is_empty(),
        Command::Export => parsed.operands.is_empty(),
        Command::Apply => parsed.operands.len() == 1,
    };
    if !operands_ok {
        return Err(format!("wrong operands for loop {word}"));
    }
    if command != Command::Validate && parsed.project.is_none() {
        return Err(format!("loop {word} needs --project <project>"));
    }
    Ok(Parsed::Run(parsed))
}

/// Runs `openwiz loop <command> ...`; `args` starts with the command word.
pub fn run(args: &[OsString], stdout: &mut dyn Write, stderr: &mut dyn Write) -> i32 {
    let name = args
        .first()
        .and_then(|a| a.to_str())
        .and_then(Command::from_word)
        .map_or("unknown", |c| match c {
            Command::Validate => "loop.validate",
            Command::Export => "loop.export",
            Command::Plan => "loop.plan",
            Command::Apply => "loop.apply",
        });
    match parse(args) {
        Ok(Parsed::Help { json }) => {
            let text = format!("Usage:\n{USAGE}\n{HELP}");
            i32::from(
                stdout
                    .write_all(response::help(json, text).as_bytes())
                    .is_err(),
            )
        }
        Ok(Parsed::Run(args)) => not_built(&args, stdout, stderr),
        Err(why) => {
            let _ = writeln!(
                stderr,
                "openwiz: usage: {why}; nothing was read (see openwiz loop --help)"
            );
            if json_selected(args) {
                let doc = serde_json::json!({
                    "schema": "openwiz.cli-error.v1", "command": name, "exit_code": 2,
                    "error": {"kind": "usage", "message": format!("Invalid loop arguments: {why}.")}
                });
                let _ = writeln!(stdout, "{doc}");
            }
            2
        }
    }
}

/// The stub's result: exit 5, nothing read or changed.
fn not_built(args: &Args, stdout: &mut dyn Write, stderr: &mut dyn Write) -> i32 {
    let (word, ticket) = (args.command.word(), args.command.ticket());
    if args.json {
        let doc = serde_json::json!({
            "schema": "openwiz.loop-not-built.v1", "command": word, "exit_code": 5,
            "status": "not_built", "ticket": ticket,
            "message": format!("openwiz loop {word} is not built yet; nothing was read or changed"),
        });
        if writeln!(stdout, "{doc}").is_err() {
            return 1;
        }
    } else {
        let _ = writeln!(
            stderr,
            "openwiz: loop {word} is not built yet (#{ticket}); nothing was read or changed"
        );
    }
    5
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::Value;

    fn run_args(args: &[&str]) -> (i32, String, String) {
        let args: Vec<OsString> = args.iter().map(OsString::from).collect();
        let (mut out, mut err) = (Vec::new(), Vec::new());
        let code = run(&args, &mut out, &mut err);
        (
            code,
            String::from_utf8(out).unwrap(),
            String::from_utf8(err).unwrap(),
        )
    }

    // catches: a stub that succeeds, reads, or prints a result that is not the
    // contract's `not_built` document, so a caller mistakes it for a report.
    #[test]
    fn each_stub_refuses_with_the_contracts_not_built_result() {
        for (args, command, ticket) in [
            (&["validate", "loops/a.md", "--json"][..], "validate", 790),
            (
                &["export", "--project", "prj_syn_0001", "--json"],
                "export",
                791,
            ),
            (
                &["plan", "loops", "--project", "prj_syn_0001", "--json"],
                "plan",
                792,
            ),
            (
                &["apply", "nightly", "--project", "prj_syn_0001", "--json"],
                "apply",
                793,
            ),
        ] {
            let (code, out, err) = run_args(args);
            assert_eq!(code, 5, "{args:?}");
            assert!(err.is_empty(), "{args:?}: {err}");
            assert!(out.ends_with('\n') && out.lines().count() == 1, "{out:?}");
            let doc: Value = serde_json::from_str(&out).unwrap();
            assert_eq!(
                doc,
                serde_json::json!({
                    "schema": "openwiz.loop-not-built.v1", "command": command,
                    "exit_code": 5, "status": "not_built", "ticket": ticket,
                    "message": format!("openwiz loop {command} is not built yet; nothing was read or changed"),
                })
            );
            let text: Vec<&str> = args.iter().copied().filter(|a| *a != "--json").collect();
            let (code, out, err) = run_args(&text);
            assert_eq!((code, out.as_str()), (5, ""));
            assert_eq!(
                err,
                format!(
                    "openwiz: loop {command} is not built yet (#{ticket}); nothing was read or changed\n"
                )
            );
        }
    }

    // catches: a parser that accepts a form the contract refuses (so a later
    // command acts on arguments nobody pinned) or refuses a pinned form.
    #[test]
    fn arguments_follow_the_contract() {
        let project = Some("prj_syn_0001".to_owned());
        let accepted: [(&[&str], Args); 5] = [
            (
                &["validate", "a.md", "--catalog", "b", "--", "-dash.md"],
                Args {
                    command: Command::Validate,
                    operands: vec!["a.md".into(), "b".into(), "-dash.md".into()],
                    catalog: true,
                    project: None,
                    out: None,
                    file: None,
                    adopt: vec![],
                    json: false,
                },
            ),
            (
                &[
                    "export",
                    "--out",
                    "exported",
                    "--project",
                    "prj_syn_0001",
                    "--json",
                ],
                Args {
                    command: Command::Export,
                    operands: vec![],
                    catalog: false,
                    project: project.clone(),
                    out: Some("exported".into()),
                    file: None,
                    adopt: vec![],
                    json: true,
                },
            ),
            (
                &[
                    "plan",
                    "a.md",
                    "--project",
                    "prj_syn_0001",
                    "--adopt",
                    "a=loop_syn_1",
                    "--adopt",
                    "b=loop_syn_2",
                    "--",
                    "--json",
                ],
                Args {
                    command: Command::Plan,
                    operands: vec!["a.md".into(), "--json".into()],
                    catalog: false,
                    project: project.clone(),
                    out: None,
                    file: None,
                    adopt: vec![
                        ("a".into(), "loop_syn_1".into()),
                        ("b".into(), "loop_syn_2".into()),
                    ],
                    json: false,
                },
            ),
            (
                &[
                    "apply",
                    "a",
                    "--project",
                    "prj_syn_0001",
                    "--from",
                    "x/a.md",
                    "--adopt",
                    "a=loop_syn_1",
                ],
                Args {
                    command: Command::Apply,
                    operands: vec!["a".into()],
                    catalog: false,
                    project: project.clone(),
                    out: None,
                    file: Some("x/a.md".into()),
                    adopt: vec![("a".into(), "loop_syn_1".into())],
                    json: false,
                },
            ),
            (
                &["apply", "--json", "--project", "prj_syn_0001", "a=b"],
                Args {
                    command: Command::Apply,
                    operands: vec!["a=b".into()],
                    catalog: false,
                    project,
                    out: None,
                    file: None,
                    adopt: vec![],
                    json: true,
                },
            ),
        ];
        for (args, expected) in accepted {
            let os: Vec<OsString> = args.iter().map(OsString::from).collect();
            assert_eq!(parse(&os), Ok(Parsed::Run(expected)), "{args:?}");
        }
        for args in [
            &["validate"][..],
            &["validate", "a.md", "--project", "prj_syn_0001"],
            &["validate", "a.md", "--catalog", "--catalog"],
            &["validate", "a.md", "--strict"],
            &["export"],
            &["export", "extra", "--project", "prj_syn_0001"],
            &["export", "--project=prj_syn_0001"],
            &["export", "--project", "--json"],
            &["export", "--project", ""],
            &[
                "export",
                "--project",
                "prj_syn_0001",
                "--project",
                "prj_syn_0002",
            ],
            &["export", "--project", "prj_syn_0001", "--out"],
            &["plan", "--project", "prj_syn_0001"],
            &["plan", "a.md"],
            &["plan", "a.md", "--project", "prj_syn_0001", "--adopt", "a"],
            &[
                "plan",
                "a.md",
                "--project",
                "prj_syn_0001",
                "--adopt",
                "=loop_syn_1",
            ],
            &[
                "plan",
                "a.md",
                "--project",
                "prj_syn_0001",
                "--from",
                "a.md",
            ],
            &["apply", "--project", "prj_syn_0001"],
            &["apply", "a", "b", "--project", "prj_syn_0001"],
            &["apply", "a"],
            &[
                "apply",
                "a",
                "--project",
                "prj_syn_0001",
                "--adopt",
                "a=l1",
                "--adopt",
                "a=l2",
            ],
            &["apply", "a", "--project", "prj_syn_0001", "--out", "x"],
            &[
                "apply",
                "a",
                "--project",
                "prj_syn_0001",
                "--from",
                "a\tb.md",
            ],
        ] {
            let (code, out, err) = run_args(args);
            assert_eq!(code, 2, "{args:?}");
            // `--json` is never a value, so `--project --json` still selects JSON.
            assert_eq!(out.is_empty(), !args.contains(&"--json"), "{args:?}");
            assert!(err.starts_with("openwiz: usage: "), "{args:?}: {err}");
            let mut json = args.to_vec();
            json.insert(1, "--json");
            let (code, out, _) = run_args(&json);
            assert_eq!(code, 2, "{json:?}");
            let doc: Value = serde_json::from_str(&out).unwrap();
            assert_eq!(doc["schema"], "openwiz.cli-error.v1", "{json:?}");
            assert_eq!(doc["command"], format!("loop.{}", args[0]));
            assert_eq!(
                (&doc["exit_code"], &doc["error"]["kind"]),
                (&2.into(), &"usage".into())
            );
        }
        let (code, out, _) = run_args(&["validate", "a.md", "--json", "--json"]);
        assert_eq!(code, 2);
        assert_eq!(
            serde_json::from_str::<Value>(&out).unwrap()["error"]["kind"],
            "usage"
        );
        let bad = [OsString::from("validate"), {
            use std::os::unix::ffi::OsStringExt;
            OsString::from_vec(vec![0xff])
        }];
        assert!(parse(&bad).is_err(), "not UTF-8");
    }

    // catches: help that reads, fails, or loses its JSON wrapper.
    #[test]
    fn help_lists_the_four_commands_and_reads_nothing() {
        let (code, out, err) = run_args(&["plan", "--help"]);
        assert_eq!((code, err.as_str()), (0, ""));
        for line in USAGE.lines() {
            assert!(out.contains(line), "{line}");
        }
        let (code, out, _) = run_args(&["export", "-h", "--json"]);
        assert_eq!(code, 0);
        let doc: Value = serde_json::from_str(&out).unwrap();
        assert_eq!(doc["schema"], "openwiz.cli-help.v1");
    }
}
