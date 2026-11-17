//! The setup state (#1105): `<state>/setup/state.json`, `openwiz.setup-state.v1`.
//!
//! The setup tools (`tools/install/setup/store.py`) write it, owner-only and
//! atomically under `setup/.lock`; the server only reads it here. It holds
//! the explicitly selected project settings, the App's public ids, one
//! observation code per checked component and the setup operations of
//! `contracts/setup.v1.md`. Never a credential: every string has a bounded,
//! fixed shape. Unknown or duplicate keys, an unsafe file and a bad shape
//! all refuse the whole file.

use crate::{Area, StoreError, io_error};
use serde::{Deserialize, Serialize};
use std::fs;
use std::io::Read;
use std::os::unix::fs::{MetadataExt, OpenOptionsExt};
use std::path::Path;

/// The setup store's area: `setup/`, with the store's directory checks.
pub struct Setup;
impl Area for Setup {
    const DIR: &'static str = "setup";
    const WHAT: &'static str = "setup state";
}

pub const SCHEMA: &str = "openwiz.setup-state.v1";
const MAX_BYTES: u64 = 256 * 1024;
const MAX_OPERATIONS: usize = 64;

/// The components a setup check observes. T4 adds `engine` and T5
/// `remote_access`, each its own line.
pub const COMPONENTS: [&str; 7] = [
    "cloudroom",
    "harness",
    "personal_github",
    "github_app",
    "project",
    "engine",
    "remote_access",
];
pub const KINDS: [&str; 4] = [
    "connect_app",
    "prepare_project",
    "activate_engine",
    "configure_access",
];
pub const PHASES: [&str; 4] = ["proposed", "applied", "refused", "uncertain"];

#[derive(Clone, Debug, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SetupState {
    pub schema: String,
    /// Bumped whenever the selection (project or App ids) changes.
    pub revision: u64,
    /// Setup-check generations (security R3): a check saves only if no
    /// later-started check saved first.
    pub checks: Checks,
    pub project: Option<Project>,
    pub app: Option<AppIds>,
    pub observations: Observations,
    pub operations: Vec<Operation>,
    #[serde(default)]
    pub engine: Option<Engine>,
    /// #633 (setup.v1's 0.0.16 expansion): the owner's identity choice for
    /// one repository. Absent in an old state: no selection, so the App rule.
    #[serde(default)]
    pub identity: Option<Identity>,
    /// #635: where settings consumers find the brain (setup-onboard.v1's
    /// `brain`). Absent or null is an existing project: no brain is inferred.
    #[serde(default)]
    pub brain: Option<Brain>,
}

/// `personal_login` exactly when the owner explicitly skipped the App, naming
/// the acting login; `store.py`'s `check_identity` refuses the same values.
#[derive(Clone, Debug, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Identity {
    pub selected: Selected,
    pub app_choice: AppChoice,
    pub acting_login: Option<String>,
    pub repository: String,
}

/// setup.v1's `selected`, read only as its plain string (the shape check in
/// `read` refuses a tagged object).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Selected {
    App,
    PersonalLogin,
    Unselected,
}

/// setup.v1's `app_choice`, the same way.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AppChoice {
    Create,
    Reuse,
    Skip,
    Undecided,
}

#[derive(Clone, Debug, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Brain {
    pub location: String,
    pub code_repository: String,
    pub code_visibility: String,
    pub brain_repository: String,
    pub brain_visibility: KnownVisibility,
    pub visibility_basis: String,
    pub folder: String,
    pub setting: String,
    pub decision_repositories: Option<DecisionPair>,
}

#[derive(Clone, Debug, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct KnownVisibility {
    pub known: String,
}

/// decisions.v1's existing public/private pair setting.
#[derive(Clone, Debug, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DecisionPair {
    pub public: PairRole,
    pub private: PairRole,
}

#[derive(Clone, Debug, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PairRole {
    pub owner: String,
    pub name: String,
}

impl Brain {
    /// The same rules as `check_brain` in `tools/install/setup/store.py`.
    fn valid(&self) -> bool {
        let same = |a: &str, b: &str| a.eq_ignore_ascii_case(b);
        let fixed = repository(&self.code_repository)
            && repository(&self.brain_repository)
            && self.brain_visibility.known == "private"
            && self.visibility_basis == "github_repository_read"
            && self.folder == ".openwiz/brain"
            && self.setting == "brain_location";
        let role = |r: &PairRole, full: &str| same(&format!("{}/{}", r.owner, r.name), full);
        fixed
            && match (self.location.as_str(), &self.decision_repositories) {
                ("in_repository", None) => {
                    self.code_visibility == "private"
                        && same(&self.code_repository, &self.brain_repository)
                }
                ("companion", Some(pair)) => {
                    self.code_visibility == "public"
                        && !same(&self.code_repository, &self.brain_repository)
                        && role(&pair.public, &self.code_repository)
                        && role(&pair.private, &self.brain_repository)
                }
                _ => false,
            }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Engine {
    pub location: String,
    pub revision: u64,
    pub runtime: String,
    pub operation_id: String,
    pub fingerprint: String,
    pub cost: Option<EngineCost>,
}

#[derive(Clone, Debug, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct EngineCost {
    pub source: String,
    pub provenance: String,
    pub credits: serde_json::Number,
    pub window_s: serde_json::Number,
    pub free_allowance: serde_json::Number,
    pub observed_at: u64,
    pub allowance_at: u64,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Checks {
    pub started: u64,
    pub committed: u64,
}

#[derive(Clone, Debug, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Project {
    pub repository: String,
    pub project: String,
    pub operator: String,
    pub service_issue: u64,
    pub answer_thread: String,
    pub harness: String,
    pub model: String,
    pub effort: String,
    /// The pinned packaged runtime: `<version> <40-hex source>`.
    pub runtime: Option<String>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AppIds {
    pub app_id: u64,
    pub installation_id: Option<u64>,
}

#[derive(Clone, Debug, Default, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Observations {
    pub cloudroom: Option<Observation>,
    pub harness: Option<Observation>,
    pub personal_github: Option<Observation>,
    pub github_app: Option<Observation>,
    pub project: Option<Observation>,
    pub engine: Option<Observation>,
    pub remote_access: Option<Observation>,
}

impl Observations {
    pub fn get(&self, component: &str) -> Option<&Observation> {
        match component {
            "cloudroom" => self.cloudroom.as_ref(),
            "harness" => self.harness.as_ref(),
            "personal_github" => self.personal_github.as_ref(),
            "github_app" => self.github_app.as_ref(),
            "project" => self.project.as_ref(),
            "engine" => self.engine.as_ref(),
            "remote_access" => self.remote_access.as_ref(),
            _ => None,
        }
    }
}

/// One check's result code, bound to the selection revision it checked and
/// when (Unix milliseconds). The server maps codes to fixed public text.
#[derive(Clone, Debug, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Observation {
    pub code: String,
    pub revision: u64,
    pub at: u64,
}

#[derive(Clone, Debug, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Operation {
    pub operation_id: String,
    pub kind: String,
    pub phase: String,
    pub fingerprint: String,
    pub effects: Vec<String>,
    pub reason: String,
}

fn text(value: &str) -> bool {
    (1..=300).contains(&value.chars().count())
        && value.trim() == value
        && !value.chars().any(char::is_control)
}

fn hex(value: &str, length: usize) -> bool {
    value.len() == length
        && value
            .bytes()
            .all(|b| matches!(b, b'0'..=b'9' | b'a'..=b'f'))
}

fn word(value: &str, max: usize, extra: &[u8]) -> bool {
    (1..=max).contains(&value.len())
        && value
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || extra.contains(&b))
}

/// C-S1 (#2865): a credential shape at a word start, the same list as
/// `CREDENTIAL` in `tools/install/setup/store.py`: `gh[pousr]_`,
/// `github_pat_`, `sk-`, `xox[abprs]-`, `AKIA` and a JWT's `eyJ`.
fn credential_shaped(value: &str) -> bool {
    let b = value.as_bytes();
    (0..b.len()).any(|i| {
        let rest = &b[i..];
        (i == 0 || !b[i - 1].is_ascii_alphanumeric())
            && ((rest.len() > 3
                && rest.starts_with(b"gh")
                && b"pousr".contains(&rest[2])
                && rest[3] == b'_')
                || (rest.len() > 4
                    && rest.starts_with(b"xox")
                    && b"abprs".contains(&rest[3])
                    && rest[4] == b'-')
                || [&b"github_pat_"[..], b"sk-", b"AKIA", b"eyJ"]
                    .iter()
                    .any(|p| rest.starts_with(p)))
    })
}

fn repository(value: &str) -> bool {
    value.split_once('/').is_some_and(|(owner, name)| {
        word(owner, 39, b"-") && word(name, 100, b"_.-") && name != "." && name != ".."
    })
}

fn runtime(value: &str) -> bool {
    value.split_once(' ').is_some_and(|(version, source)| {
        let mut parts = version.split('.');
        parts.next() == Some("0")
            && parts.clone().count() == 2
            && parts.all(|p| word(p, 10, b"") && p.bytes().all(|b| b.is_ascii_digit()))
            && hex(source, 40)
    })
}

const ID_MAX: u64 = (1 << 53) - 1;

impl SetupState {
    fn validate(&self) -> Result<(), &'static str> {
        if self.schema != SCHEMA {
            return Err("unsupported setup state schema");
        }
        if self.revision > ID_MAX {
            return Err("invalid revision");
        }
        if self.checks.started > ID_MAX || self.checks.committed > self.checks.started {
            return Err("invalid check generations");
        }
        if let Some(p) = &self.project {
            let ok = repository(&p.repository)
                && word(&p.project, 128, b"_-")
                && word(&p.answer_thread, 128, b"_-")
                && text(&p.operator)
                && p.operator.chars().count() <= 100
                && (1..=ID_MAX).contains(&p.service_issue)
                && [&p.harness, &p.model, &p.effort]
                    .iter()
                    .all(|v| word(v, 128, b"_.:/-") && !credential_shaped(v))
                && p.runtime.as_deref().is_none_or(runtime);
            if !ok {
                return Err("invalid project settings");
            }
        }
        if let Some(i) = &self.identity {
            let skipped = i.selected == Selected::PersonalLogin;
            let ok = skipped == (i.app_choice == AppChoice::Skip)
                && repository(&i.repository)
                && match &i.acting_login {
                    Some(login) => skipped && word(login, 39, b"-"),
                    None => !skipped,
                };
            if !ok {
                return Err("invalid identity choice");
            }
        }
        if let Some(app) = &self.app
            && (!(1..=ID_MAX).contains(&app.app_id)
                || app
                    .installation_id
                    .is_some_and(|id| !(1..=ID_MAX).contains(&id)))
        {
            return Err("invalid App ids");
        }
        for component in COMPONENTS {
            if let Some(o) = self.observations.get(component) {
                let code = o.code.len() <= 40
                    && o.code.starts_with(|c: char| c.is_ascii_lowercase())
                    && o.code.bytes().all(|b| b.is_ascii_lowercase() || b == b'_');
                if !code || o.revision > ID_MAX || !(1..=ID_MAX).contains(&o.at) {
                    return Err("invalid observation");
                }
            }
        }
        if self.operations.len() > MAX_OPERATIONS {
            return Err("too many operations");
        }
        for (at, o) in self.operations.iter().enumerate() {
            let ok = hex(&o.operation_id, 32)
                && KINDS.contains(&o.kind.as_str())
                && PHASES.contains(&o.phase.as_str())
                && hex(&o.fingerprint, 64)
                && (1..=8).contains(&o.effects.len())
                && o.effects.iter().all(|e| text(e))
                && text(&o.reason)
                && !self.operations[..at]
                    .iter()
                    .any(|p| p.operation_id == o.operation_id);
            if !ok {
                return Err("invalid operation");
            }
        }
        if self.brain.as_ref().is_some_and(|b| !b.valid()) {
            return Err("invalid brain reference");
        }
        if let Some(e) = &self.engine {
            if !["cloud", "local"].contains(&e.location.as_str())
                || e.revision > ID_MAX
                || !runtime(&e.runtime)
                || !hex(&e.operation_id, 32)
                || !hex(&e.fingerprint, 64)
                || !self.operations.iter().any(|o| {
                    o.operation_id == e.operation_id
                        && o.kind == "activate_engine"
                        && o.fingerprint == e.fingerprint
                })
            {
                return Err("invalid engine binding");
            }
            if let Some(c) = &e.cost {
                let numbers = [&c.credits, &c.window_s, &c.free_allowance];
                if c.source != "cloudroom_usage"
                    || !["measured", "estimated"].contains(&c.provenance.as_str())
                    || c.observed_at > ID_MAX
                    || c.allowance_at > ID_MAX
                    || numbers.iter().enumerate().any(|(i, n)| {
                        n.as_f64().is_none_or(|v| {
                            !v.is_finite() || if i == 1 { v <= 0.0 } else { v < 0.0 }
                        })
                    })
                {
                    return Err("invalid engine cost");
                }
            }
        }
        Ok(())
    }
}

/// Reads the setup state, for the read-only setup route. `None` when setup
/// has never written it. Creates, syncs and writes nothing.
pub fn read(state_dir: &Path) -> Result<Option<SetupState>, StoreError> {
    let Some(store) = crate::Store::<Setup>::open_read_only(state_dir)? else {
        return Ok(None);
    };
    let dir = store.dir();
    let path = dir.join("state.json");
    let mut file = match fs::OpenOptions::new()
        .read(true)
        .custom_flags(no_follow_nonblock())
        .open(&path)
    {
        Ok(file) => file,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(e) => return Err(io_error("open", &path, &e)),
    };
    let meta = file.metadata().map_err(|e| io_error("read", &path, &e))?;
    let owner = fs::metadata(dir)
        .map_err(|e| io_error("read", dir, &e))?
        .uid();
    if !meta.is_file()
        || meta.uid() != owner
        || meta.mode() & 0o077 != 0
        || meta.nlink() != 1
        || meta.len() > MAX_BYTES
    {
        return Err(StoreError(format!(
            "{} must be an owner-only (0600) regular file of at most 256 KiB",
            path.display()
        )));
    }
    let mut data = Vec::new();
    file.by_ref()
        .take(MAX_BYTES + 1)
        .read_to_end(&mut data)
        .map_err(|e| io_error("read", &path, &e))?;
    if data.len() as u64 > MAX_BYTES {
        return Err(StoreError(format!("{} is too large", path.display())));
    }
    let state: SetupState = serde_json::from_slice(&data)
        .map_err(|_| StoreError(format!("{} is not a valid setup state", path.display())))?;
    // Derived struct readers also accept positional arrays. The shared writer
    // requires objects even when engine is absent/null; retain duplicate-field checking
    // from the typed parse, then check its original JSON representation.
    let shape: serde_json::Value =
        serde_json::from_slice(&data).map_err(|_| StoreError("invalid setup JSON".to_owned()))?;
    let object_or_null = |v: &serde_json::Value| v.is_object() || v.is_null();
    let complete_root = shape.as_object().is_some_and(|o| {
        [
            "schema",
            "revision",
            "checks",
            "project",
            "app",
            "observations",
            "operations",
        ]
        .iter()
        .all(|key| o.contains_key(*key))
    });
    let objects = complete_root
        && shape["checks"].is_object()
        && object_or_null(&shape["project"])
        && object_or_null(&shape["app"])
        && (shape["project"].is_null() || shape["project"].get("runtime").is_some())
        && (shape["app"].is_null() || shape["app"].get("installation_id").is_some())
        && shape["observations"]
            .as_object()
            .is_some_and(|o| o.values().all(serde_json::Value::is_object))
        && shape["operations"]
            .as_array()
            .is_some_and(|a| a.iter().all(serde_json::Value::is_object))
        && object_or_null(&shape["identity"])
        && (shape["identity"].is_null()
            || (shape["identity"].get("acting_login").is_some()
                && shape["identity"]["selected"].is_string()
                && shape["identity"]["app_choice"].is_string()))
        && object_or_null(&shape["engine"])
        && (shape["engine"].is_null()
            || (shape["engine"].get("cost").is_some() && object_or_null(&shape["engine"]["cost"])))
        && object_or_null(&shape["brain"])
        && (shape["brain"].is_null()
            || (shape["brain"]["brain_visibility"].is_object()
                && shape["brain"]
                    .get("decision_repositories")
                    .is_some_and(object_or_null)));
    if !objects {
        return Err(StoreError(
            "engine setup state requires JSON objects".to_owned(),
        ));
    }
    state
        .validate()
        .map_err(|why| StoreError(format!("{}: {why}", path.display())))?;
    Ok(Some(state))
}

/// `O_NOFOLLOW | O_NONBLOCK`, as `attachments::open_metadata` takes them:
/// XNU bsd/sys/fcntl.h (Darwin); Linux UAPI arch/{arm,arm64} for ARM, else
/// asm-generic (x86, x86_64, riscv64). A substituted symlink or FIFO refuses.
fn no_follow_nonblock() -> i32 {
    if cfg!(target_vendor = "apple") {
        0x0100 | 0x0004
    } else if cfg!(any(target_arch = "arm", target_arch = "aarch64")) {
        0o100000 | 0o4000
    } else {
        0o400000 | 0o4000
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::fs::{DirBuilderExt, PermissionsExt, symlink};

    struct Dir(std::path::PathBuf);
    impl Drop for Dir {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }
    fn state() -> Dir {
        use std::sync::atomic::{AtomicUsize, Ordering};
        static N: AtomicUsize = AtomicUsize::new(0);
        let dir = std::env::temp_dir().join(format!(
            "openwiz-setup-store-{}-{}",
            std::process::id(),
            N.fetch_add(1, Ordering::SeqCst)
        ));
        let _ = fs::remove_dir_all(&dir);
        fs::DirBuilder::new()
            .mode(0o700)
            .recursive(true)
            .create(dir.join("setup"))
            .unwrap();
        fs::set_permissions(&dir, fs::Permissions::from_mode(0o700)).unwrap();
        Dir(dir)
    }
    fn write(dir: &Path, text: &str, mode: u32) {
        let path = dir.join("setup/state.json");
        let _ = fs::remove_file(&path);
        fs::write(&path, text).unwrap();
        fs::set_permissions(&path, fs::Permissions::from_mode(mode)).unwrap();
    }
    pub(crate) const GOOD: &str = r#"{"schema":"openwiz.setup-state.v1","revision":2,"checks":{"started":3,"committed":2},"project":{"repository":"synthetic-owner/synthetic-consumer","project":"prj_synthetic","operator":"synthetic-owner","service_issue":7,"answer_thread":"thr_synthetic_answer","harness":"claude-code","model":"synthetic-model","effort":"high","runtime":"0.0.13 3333333333333333333333333333333333333333"},"app":{"app_id":1001,"installation_id":2002},"observations":{"github_app":{"code":"app_verified","revision":2,"at":1767225600000}},"operations":[{"operation_id":"0123456789abcdef0123456789abcdef","kind":"prepare_project","phase":"applied","fingerprint":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef","effects":["Save project settings."],"reason":"Saved."}]}"#;

    #[test]
    fn absent_state_is_none_and_nothing_is_created() {
        let dir = state();
        assert_eq!(read(&dir.0).unwrap(), None);
        let empty = dir.0.join("never");
        assert_eq!(read(&empty).unwrap(), None);
        assert!(!empty.exists());
    }

    #[test]
    fn reads_the_tools_state_exactly() {
        let dir = state();
        write(&dir.0, GOOD, 0o600);
        let value = read(&dir.0).unwrap().unwrap();
        assert_eq!(value.revision, 2);
        assert_eq!(
            value.app,
            Some(AppIds {
                app_id: 1001,
                installation_id: Some(2002)
            })
        );
        assert_eq!(
            value.observations.get("github_app").unwrap().code,
            "app_verified"
        );
        assert_eq!(value.operations[0].phase, "applied");
    }

    #[test]
    fn unsafe_files_and_bad_shapes_refuse_the_whole_state() {
        let dir = state();
        write(&dir.0, GOOD, 0o644);
        assert!(read(&dir.0).is_err(), "group-readable file");
        let link = dir.0.join("setup/state.json");
        let _ = fs::remove_file(&link);
        let target = dir.0.join("elsewhere.json");
        fs::write(&target, GOOD).unwrap();
        fs::set_permissions(&target, fs::Permissions::from_mode(0o600)).unwrap();
        symlink(&target, &link).unwrap();
        assert!(read(&dir.0).is_err(), "symlinked file");
        for bad in [
            GOOD.replace(r#""revision":2,"#, r#""revision":2,"revision":3,"#),
            GOOD.replace(r#""reason":"Saved.""#, r#""reason":"Saved.","token":"x""#),
            GOOD.replace("app_verified", "App Verified"),
            GOOD.replace("github_app", "remote_access")
                .replace("app_verified", "App Verified"),
            GOOD.replace(r#""phase":"applied""#, r#""phase":"started""#),
            GOOD.replace("synthetic-owner/synthetic-consumer", "../x"),
            GOOD.replace(r#""Save project settings.""#, "\"line\\nbreak\""),
            GOOD.replace("0.0.13 3333", "latest 3333"),
            GOOD.replace("openwiz.setup-state.v1", "openwiz.setup-state.v2"),
            GOOD.replace(r#""committed":2"#, r#""committed":4"#),
            GOOD.replace(r#","checks":{"started":3,"committed":2}"#, ""),
        ] {
            write(&dir.0, &bad, 0o600);
            assert!(read(&dir.0).is_err(), "{bad}");
        }
        fs::set_permissions(dir.0.join("setup"), fs::Permissions::from_mode(0o755)).unwrap();
        write(&dir.0, GOOD, 0o600);
        assert!(read(&dir.0).is_err(), "open setup directory");
    }

    /// #633: catches a saved identity choice the Python store refuses (no
    /// explicit skip, no acting login, a missing key) reaching the server, and
    /// an old state without the field no longer reading.
    #[test]
    fn identity_choice_reads_only_an_explicit_skip_or_nothing() {
        let dir = state();
        let skip = r#""identity":{"selected":"personal_login","app_choice":"skip","acting_login":"synthetic-owner","repository":"synthetic-owner/synthetic-consumer"},"#;
        let with = |identity: &str| {
            GOOD.replacen(r#""operations""#, &format!(r#"{identity}"operations""#), 1)
        };
        write(&dir.0, GOOD, 0o600);
        assert_eq!(
            read(&dir.0).unwrap().unwrap().identity,
            None,
            "an old state"
        );
        write(&dir.0, &with(skip), 0o600);
        let identity = read(&dir.0).unwrap().unwrap().identity.unwrap();
        assert_eq!(
            (identity.selected, identity.app_choice),
            (Selected::PersonalLogin, AppChoice::Skip)
        );
        assert_eq!(identity.acting_login.as_deref(), Some("synthetic-owner"));
        for good in [
            r#""identity":null,"#,
            r#""identity":{"selected":"unselected","app_choice":"undecided","acting_login":null,"repository":"synthetic-owner/synthetic-consumer"},"#,
        ] {
            write(&dir.0, &with(good), 0o600);
            assert!(read(&dir.0).is_ok(), "{good}");
        }
        for bad in [
            skip.replace(r#""skip""#, r#""reuse""#),
            skip.replace(r#""skip""#, r#""Skip""#),
            skip.replace(r#""skip""#, r#"{"skip":null}"#),
            skip.replace(r#""personal_login""#, r#""unselected""#),
            skip.replace(r#""personal_login""#, r#""app""#),
            skip.replace(r#""synthetic-owner","#, "null,"),
            skip.replace(r#""acting_login":"synthetic-owner","#, ""),
            skip.replace(r#""synthetic-owner","#, &format!(r#""ghp_{}","#, "A".repeat(36))),
            skip.replace(r#""synthetic-owner","#, r#""synthetic/owner","#),
            skip.replace(r#""synthetic-owner","#, &format!(r#""{}","#, "x".repeat(40))),
            skip.replace(r#""synthetic-owner/synthetic-consumer""#, r#""synthetic-owner/..""#),
            skip.replace(r#""repository""#, r#""token":"x","repository""#),
            skip.replace(r#""personal_login""#, r#""fallback""#),
            r#""identity":["personal_login","skip","synthetic-owner","synthetic-owner/synthetic-consumer"],"#.to_owned(),
            r#""identity":{"selected":"app","app_choice":"reuse","acting_login":"synthetic-owner","repository":"synthetic-owner/synthetic-consumer"},"#.to_owned(),
        ] {
            write(&dir.0, &with(&bad), 0o600);
            assert!(read(&dir.0).is_err(), "{bad}");
        }
    }

    /// #635: the optional brain reference. An existing state without it still
    /// reads as no brain; a valid in-repository or companion reference reads;
    /// a companion that is the code, a mismatched pair, a public brain, an
    /// in-repository brain elsewhere or a missing nullable key refuses.
    #[test]
    fn brain_references_read_and_unsafe_ones_refuse_the_whole_state() {
        let dir = state();
        write(&dir.0, GOOD, 0o600);
        assert_eq!(read(&dir.0).unwrap().unwrap().brain, None);
        let companion = r#""brain":{"location":"companion","code_repository":"synthetic-owner/synthetic-app","code_visibility":"public","brain_repository":"synthetic-owner/synthetic-app-brain","brain_visibility":{"known":"private"},"visibility_basis":"github_repository_read","folder":".openwiz/brain","setting":"brain_location","decision_repositories":{"public":{"owner":"synthetic-owner","name":"synthetic-app"},"private":{"owner":"synthetic-owner","name":"synthetic-app-brain"}}}"#;
        let in_repository = r#""brain":{"location":"in_repository","code_repository":"synthetic-owner/synthetic-app","code_visibility":"private","brain_repository":"synthetic-owner/synthetic-app","brain_visibility":{"known":"private"},"visibility_basis":"github_repository_read","folder":".openwiz/brain","setting":"brain_location","decision_repositories":null}"#;
        let with = |brain: &str| GOOD.replacen('{', &format!("{{{brain},"), 1);
        for good in [companion, in_repository, r#""brain":null"#] {
            write(&dir.0, &with(good), 0o600);
            assert!(read(&dir.0).is_ok(), "{good}");
        }
        let value = {
            write(&dir.0, &with(companion), 0o600);
            read(&dir.0).unwrap().unwrap().brain.unwrap()
        };
        assert_eq!(
            value.brain_repository,
            "synthetic-owner/synthetic-app-brain"
        );
        for bad in [
            companion.replace(
                r#""brain_repository":"synthetic-owner/synthetic-app-brain""#,
                r#""brain_repository":"Synthetic-Owner/Synthetic-App""#,
            ),
            companion.replace(r#"{"known":"private"}"#, r#"{"known":"public"}"#),
            companion.replace(
                r#""code_visibility":"public""#,
                r#""code_visibility":"private""#,
            ),
            companion.replace(r#""name":"synthetic-app-brain""#, r#""name":"other""#),
            in_repository.replace(
                r#""brain_repository":"synthetic-owner/synthetic-app""#,
                r#""brain_repository":"synthetic-owner/elsewhere""#,
            ),
            in_repository.replace(r#","decision_repositories":null"#, ""),
            in_repository.replace(r#""folder":".openwiz/brain""#, r#""folder":"brain""#),
            companion.replace(
                r#""setting":"brain_location""#,
                r#""setting":"brain_location","token":"x""#,
            ),
        ] {
            write(&dir.0, &with(&bad), 0o600);
            assert!(read(&dir.0).is_err(), "{bad}");
        }
    }

    /// C-S1 (#2865): a credential-shaped harness, model or effort refuses the
    /// whole state; ordinary agent settings, near misses included, still read.
    /// Every planted value is synthetic, built here so no token is a literal.
    #[test]
    fn credential_shaped_agent_settings_refuse_the_whole_state() {
        let dir = state();
        let a = |n| "A".repeat(n);
        let planted = [
            format!("ghp_{}", a(36)),
            format!("gho_{}", a(36)),
            format!("ghs_{}", a(36)),
            format!("ghu_{}", a(36)),
            format!("ghr_{}", a(36)),
            format!("github_pat_{}", a(30)),
            format!("sk-ant-synthetic{}", a(20)),
            format!("sk-{}", a(40)),
            format!("xoxb-{}", a(20)),
            format!("AKIA{}", a(16)),
            format!("eyJ{}.eyJ{}.{}", a(12), a(12), a(12)),
            format!("synthetic/ghp_{}", a(36)),
        ];
        let fields = [
            r#""harness":"claude-code""#,
            r#""model":"synthetic-model""#,
            r#""effort":"high""#,
        ];
        for field in fields {
            let key = field.split(':').next().unwrap();
            for value in &planted {
                write(
                    &dir.0,
                    &GOOD.replace(field, &format!(r#"{key}:"{value}""#)),
                    0o600,
                );
                assert!(read(&dir.0).is_err(), "{key} accepted a credential shape");
            }
            for value in [
                "claude-opus-5-5",
                "gpt-5.1-codex",
                "task-runner",
                "desk-ghp",
                "o3",
            ] {
                write(
                    &dir.0,
                    &GOOD.replace(field, &format!(r#"{key}:"{value}""#)),
                    0o600,
                );
                assert!(read(&dir.0).is_ok(), "{key} refused {value}");
            }
        }
    }
}
