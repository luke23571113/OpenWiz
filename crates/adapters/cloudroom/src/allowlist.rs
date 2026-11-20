use openwiz_core::attachment::{Kind, StagedAttachment};
use openwiz_core::messaging::{Mode, validate_text};
use openwiz_core::prompt::attachment_allowance;

use crate::new_thread::{CLI_REASONING_LEVELS, HARNESS_PROVIDERS};

pub const PC_BUNDLE_ROOT: &str = "/tmp";
pub const PC_BUNDLE_PREFIX: &str = ".mount_";
pub const PC_BUNDLE_CLI: &str =
    "resources/app.asar.unpacked/node_modules/bb-app/host-daemon/dist/room-cli";

pub const MAC_BUNDLE_CLI: &str = "/Applications/Cloudroom.app/Contents/Resources/app.asar.unpacked/node_modules/bb-app/host-daemon/dist/room-cli";

pub const SETUP_LAUNCHER: &str = ".local/bin/room-cli";
pub const SETUP_CALLS: [&[&str]; 2] = [
    &["cloud", "status", "--json"],
    &["cloud", "sign-in", "--json"],
];

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct ThreadId(String);

pub const THREAD_ID_MAX_LEN: usize = 128;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct InvalidThreadId(pub String);

impl ThreadId {
    pub fn parse(id: &str) -> Result<Self, InvalidThreadId> {
        let valid = !id.is_empty()
            && id.len() <= THREAD_ID_MAX_LEN
            && !id.starts_with('-')
            && id
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || b == b'_' || b == b'-');
        if valid {
            Ok(Self(id.to_owned()))
        } else {
            Err(InvalidThreadId(id.to_owned()))
        }
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct InvalidSpawn(pub String);

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SpawnArgs {
    project: ThreadId,
    provider: String,
    model: String,
    effort: String,
    request_id: String,
    prompt: String,
    attachments: Vec<StagedAttachment>,
}

impl SpawnArgs {
    pub fn new(
        project_id: &str,
        provider: &str,
        model: &str,
        effort: &str,
        request_id: &str,
        prompt: &str,
    ) -> Result<Self, InvalidSpawn> {
        let refuse = |why: &str| Err(InvalidSpawn(why.to_owned()));
        let Ok(project) = ThreadId::parse(project_id) else {
            return refuse("the project id is not safe to pass as one argument");
        };
        if !HARNESS_PROVIDERS.iter().any(|(_, p)| *p == provider) {
            return refuse("the provider is not a verified spawn provider");
        }
        let model_ok = !model.is_empty()
            && model.len() <= MODEL_MAX_LEN
            && !model.starts_with('-')
            && model.bytes().all(|b| b.is_ascii_graphic());
        if !model_ok {
            return refuse("the model is not safe to pass as one argument");
        }
        if !CLI_REASONING_LEVELS.contains(&effort) {
            return refuse("the effort is not a level thread spawn lists");
        }
        let request_id_ok = request_id.strip_prefix("ow1-").is_some_and(|hex| {
            hex.len() == 40 && hex.bytes().all(|b| matches!(b, b'0'..=b'9' | b'a'..=b'f'))
        });
        if !request_id_ok {
            return refuse("the request id is not ow1- and 40 lowercase hex digits");
        }
        if validate_text(prompt).is_err() {
            return refuse("the prompt does not follow the text rules");
        }
        Ok(Self {
            project,
            provider: provider.to_owned(),
            model: model.to_owned(),
            effort: effort.to_owned(),
            request_id: request_id.to_owned(),
            prompt: prompt.to_owned(),
            attachments: vec![],
        })
    }

    pub fn with_attachments(self, attachments: Vec<StagedAttachment>) -> Self {
        Self {
            attachments,
            ..self
        }
    }
}

pub fn attachment_args(staged: &[StagedAttachment]) -> Vec<String> {
    let mut tail = Vec::with_capacity(2 * staged.len());
    for a in staged {
        let flag = match a.attachment.kind {
            Kind::File => "--file",
            Kind::Image => "--image",
        };
        tail.push(flag.to_owned());
        tail.push(a.path.as_str().to_owned());
    }
    tail
}

fn allowance_of(staged: &[StagedAttachment]) -> std::time::Duration {
    let total = staged
        .iter()
        .map(|a| a.attachment.size_bytes)
        .fold(0, u64::saturating_add);
    attachment_allowance(total)
}

const MODEL_MAX_LEN: usize = 128;

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum LoopTrigger {
    Cron { cron: String, timezone: String },
    At(String),
    In(String),
    Webhook,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum LoopReschedule {
    Cron { cron: String, timezone: String },
    At(String),
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct LoopAgentArgs {
    pub provider: String,
    pub model: String,
    pub reasoning: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct LoopCreateArgs {
    pub name: String,
    pub prompt_file: String,
    pub trigger: LoopTrigger,
    pub new_thread: bool,
    pub script_file: Option<String>,
    pub agent: Option<LoopAgentArgs>,
    pub priority: String,
    pub secrets: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct LoopUpdateArgs {
    pub loop_id: ThreadId,
    pub name: Option<String>,
    pub priority: Option<String>,
    pub prompt: Option<String>,
    pub trigger: Option<LoopReschedule>,
    pub script_file: Option<String>,
    pub agent: Option<LoopAgentArgs>,
    pub secrets: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Invocation {
    Version,
    ThreadList {
        include_hidden: bool,
        include_archived: bool,
    },
    ProjectList {
        hidden: bool,
    },
    MachineList,
    ThreadShow(ThreadId),
    ThreadOutput(ThreadId),
    ThreadTell {
        id: ThreadId,
        mode: Mode,
        text: String,
        attachments: Vec<StagedAttachment>,
    },
    CloudStatus,
    ThreadSpawn(SpawnArgs),
    /// `room-cli cloud thread-workspace <id> --json`: one Cloud thread's
    /// current checkout and branch, for `openwiz fleet <spec>`'s verified
    /// chain (OpenWiz 0.0.6, A6, ClosedWiz#114). A read. Jake approved this
    /// one entry on #107, 2026-10-31
    /// ([private record](https://github.com/jparker2006/ClosedWiz/issues/1277#issuecomment-6704800036)). Observed: one call in
    /// A1's spike (`room-cli` v132, a flat `{branch, head, path}`), and its
    /// help on 0.43.1 (`Usage: room-cli cloud thread-workspace [options]
    /// <thread-id>`, `--json`); its error shapes are not.
    CloudThreadWorkspace(ThreadId),
    ThreadArchive(ThreadId),
    LoopList,
    LoopResume(ThreadId),
    LoopPause(ThreadId),
    LoopCreate(LoopCreateArgs),
    LoopUpdate(LoopUpdateArgs),
}

impl Invocation {
    fn staged(&self) -> &[StagedAttachment] {
        match self {
            Invocation::ThreadTell { attachments, .. } => attachments,
            Invocation::ThreadSpawn(args) => &args.attachments,
            _ => &[],
        }
    }

    pub fn allowance(&self) -> std::time::Duration {
        allowance_of(self.staged())
    }

    pub fn argv(&self) -> Vec<String> {
        let tail = attachment_args(self.staged());
        let words: Vec<&str> = match self {
            Self::Version => vec!["--version"],
            Self::LoopList => vec!["loop", "list", "--json"],
            Self::LoopResume(id) => vec!["loop", "resume", id.as_str(), "--json"],
            Self::LoopPause(id) => vec!["loop", "pause", id.as_str(), "--json"],
            Self::ThreadList {
                include_hidden,
                include_archived,
            } => {
                let mut w = vec!["thread", "list", "--json"];
                if *include_hidden {
                    w.push("--include-hidden");
                }
                if *include_archived {
                    w.push("--include-archived");
                }
                w
            }
            Self::ProjectList { hidden } => {
                let mut w = vec!["project", "list", "--json", "--include-personal"];
                if *hidden {
                    w.push("--hidden");
                }
                w
            }
            Self::MachineList => vec!["machine", "list", "--json"],
            Self::ThreadShow(id) => vec!["thread", "show", id.as_str(), "--json"],
            Self::ThreadOutput(id) => vec!["thread", "output", id.as_str(), "--json"],
            Self::ThreadTell { id, mode, text, .. } => {
                let mut w = vec![
                    "thread",
                    "tell",
                    id.as_str(),
                    "--mode",
                    mode.as_str(),
                    "--json",
                ];
                w.extend(tail.iter().map(String::as_str));
                w.extend(["--", text.as_str()]);
                w
            }
            Self::CloudStatus => vec!["cloud", "status", "--json"],
            Self::CloudThreadWorkspace(id) => {
                vec!["cloud", "thread-workspace", id.as_str(), "--json"]
            }
            Self::ThreadSpawn(a) => {
                let mut w = vec![
                    "thread",
                    "spawn",
                    "--project",
                    a.project.as_str(),
                    "--machine",
                    "cloud",
                    "--provider",
                    a.provider.as_str(),
                    "--model",
                    a.model.as_str(),
                    "--reasoning-level",
                    a.effort.as_str(),
                    "--request-id",
                    a.request_id.as_str(),
                    "--json",
                ];
                w.extend(tail.iter().map(String::as_str));
                w.extend(["--prompt", a.prompt.as_str()]);
                w
            }
            Self::ThreadArchive(id) => vec!["thread", "archive", id.as_str(), "--json"],
            Self::LoopCreate(a) => {
                let mut w = vec![
                    "loop",
                    "create",
                    "--name",
                    a.name.as_str(),
                    "--prompt-file",
                    a.prompt_file.as_str(),
                ];
                match &a.trigger {
                    LoopTrigger::Cron { cron, timezone } => {
                        w.extend(["--cron", cron.as_str(), "--timezone", timezone.as_str()]);
                    }
                    LoopTrigger::At(at) => w.extend(["--at", at.as_str()]),
                    LoopTrigger::In(delay) => w.extend(["--in", delay.as_str()]),
                    LoopTrigger::Webhook => w.push("--webhook"),
                }
                w.push(if a.new_thread {
                    "--new-thread"
                } else {
                    "--same-thread"
                });
                if let Some(script) = &a.script_file {
                    w.extend(["--script-file", script.as_str()]);
                }
                if let Some(g) = &a.agent {
                    w.extend([
                        "--provider",
                        g.provider.as_str(),
                        "--model",
                        g.model.as_str(),
                        "--reasoning",
                        g.reasoning.as_str(),
                    ]);
                }
                w.extend([
                    "--priority",
                    a.priority.as_str(),
                    "--secrets",
                    a.secrets.as_str(),
                ]);
                w
            }
            Self::LoopUpdate(a) => {
                let mut w = vec!["loop", "update", a.loop_id.as_str()];
                if let Some(name) = &a.name {
                    w.extend(["--name", name.as_str()]);
                }
                if let Some(priority) = &a.priority {
                    w.extend(["--priority", priority.as_str()]);
                }
                if let Some(prompt) = &a.prompt {
                    w.extend(["--prompt", prompt.as_str()]);
                }
                match &a.trigger {
                    Some(LoopReschedule::Cron { cron, timezone }) => {
                        w.extend(["--cron", cron.as_str(), "--timezone", timezone.as_str()]);
                    }
                    Some(LoopReschedule::At(at)) => w.extend(["--at", at.as_str()]),
                    None => {}
                }
                if let Some(script) = &a.script_file {
                    w.extend(["--script-file", script.as_str()]);
                }
                if let Some(g) = &a.agent {
                    w.extend([
                        "--provider",
                        g.provider.as_str(),
                        "--model",
                        g.model.as_str(),
                        "--reasoning",
                        g.reasoning.as_str(),
                    ]);
                }
                if let Some(secrets) = &a.secrets {
                    w.extend(["--secrets", secrets.as_str()]);
                }
                w
            }
        };
        words.into_iter().map(str::to_owned).collect()
    }

    pub fn is_read(&self) -> bool {
        match self {
            Self::Version
            | Self::ThreadList { .. }
            | Self::ProjectList { .. }
            | Self::MachineList
            | Self::ThreadShow(_)
            | Self::ThreadOutput(_)
            | Self::CloudStatus
            | Self::CloudThreadWorkspace(_)
            | Self::LoopList => true,
            Self::ThreadTell { .. }
            | Self::ThreadSpawn(_)
            | Self::ThreadArchive(_)
            | Self::LoopResume(_)
            | Self::LoopPause(_)
            | Self::LoopCreate(_)
            | Self::LoopUpdate(_) => false,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_variant_is_pinned_as_read_or_write() {
        let id = ThreadId::parse("thr_syn_0001").unwrap();
        let spawn = SpawnArgs::new(
            "prj_syn_0001",
            HARNESS_PROVIDERS[0].1,
            "syn-model",
            "low",
            &format!("ow1-{}", "0".repeat(40)),
            "x",
        )
        .unwrap();
        let cases = [
            (Invocation::Version, true),
            (
                Invocation::ThreadList {
                    include_hidden: false,
                    include_archived: false,
                },
                true,
            ),
            (
                Invocation::ThreadList {
                    include_hidden: true,
                    include_archived: true,
                },
                true,
            ),
            (Invocation::ProjectList { hidden: false }, true),
            (Invocation::ProjectList { hidden: true }, true),
            (Invocation::MachineList, true),
            (Invocation::ThreadShow(id.clone()), true),
            (Invocation::ThreadOutput(id.clone()), true),
            (Invocation::CloudStatus, true),
            (Invocation::CloudThreadWorkspace(id.clone()), true),
            (Invocation::LoopList, true),
            (
                Invocation::ThreadTell {
                    id: id.clone(),
                    mode: Mode::Queue,
                    text: "x".to_owned(),
                    attachments: vec![],
                },
                false,
            ),
            (
                Invocation::ThreadTell {
                    id: id.clone(),
                    mode: Mode::Steer,
                    text: "x".to_owned(),
                    attachments: vec![],
                },
                false,
            ),
            (Invocation::ThreadSpawn(spawn), false),
            (Invocation::ThreadArchive(id.clone()), false),
            (Invocation::LoopResume(id.clone()), false),
            (Invocation::LoopPause(id.clone()), false),
            (
                Invocation::LoopCreate(LoopCreateArgs {
                    name: "x".into(),
                    prompt_file: "@prompt".into(),
                    trigger: LoopTrigger::Webhook,
                    new_thread: true,
                    script_file: None,
                    agent: None,
                    priority: "3".into(),
                    secrets: "none".into(),
                }),
                false,
            ),
            (
                Invocation::LoopUpdate(LoopUpdateArgs {
                    loop_id: id,
                    name: None,
                    priority: Some("2".into()),
                    prompt: None,
                    trigger: None,
                    script_file: None,
                    agent: None,
                    secrets: None,
                }),
                false,
            ),
        ];
        for (invocation, read) in &cases {
            assert_eq!(invocation.is_read(), *read, "{invocation:?}");
        }
    }
}
