//! Shared native App fixture; no live exchange or account operations.
#![allow(dead_code)]
use super::{service, update};
use openwiz_adapter_github::app::{Clock, Error, Exchange};
use serde_json::{Value, json};
use service::app::Client;
use std::{
    fs::{self, OpenOptions},
    io::Write,
    os::unix::fs::{DirBuilderExt, OpenOptionsExt, PermissionsExt, symlink},
    path::{Path, PathBuf},
    process::Command,
    sync::{
        Arc,
        atomic::{AtomicU64, Ordering},
    },
    time::Instant,
};
pub(super) const OLD: &str = "1111111111111111111111111111111111111111";
pub(super) const NEW: &str = "2222222222222222222222222222222222222222";
const TOKEN: &str = "synthetic-engine-app-token";

struct FixedTime;
impl Clock for FixedTime {
    fn now_s(&self) -> u64 {
        1_893_456_000
    }
}
/// The repository name, and its owner for the owner-bound reads (#606 review R3).
struct Tokens(String, String);
impl Exchange for Tokens {
    /// #606 review R3: the service mint's owner-bound reads, answered with this
    /// fixture's synthetic App (1001), the configured owner and installation (2002).
    fn github(
        &self,
        call: &openwiz_adapter_github::app::Call<'_>,
        _: &str,
        _: std::time::Instant,
    ) -> Result<(u16, Vec<u8>), Error> {
        match call {
            openwiz_adapter_github::app::Call::App => Ok((
                200,
                json!({"id":1001,"owner":{"login":self.1}}).to_string().into_bytes(),
            )),
            openwiz_adapter_github::app::Call::Installation { .. } => Ok((
                200,
                json!({"id":2002,"app_id":1001,"account":{"login":self.1},"repository_selection":"selected"})
                    .to_string()
                    .into_bytes(),
            )),
            _ => Err(Error),
        }
    }
    fn exchange(
        &self,
        installation: u64,
        jwt: &str,
        body: &[u8],
        _: Instant,
    ) -> Result<Vec<u8>, Error> {
        assert_eq!(installation, 2002);
        assert_eq!(jwt.split('.').count(), 3);
        assert_eq!(
            serde_json::from_slice::<Value>(body).unwrap()["repositories"],
            json!([self.0])
        );
        Ok(json!({"token":TOKEN,"expires_at":"2030-01-01T01:00:00Z","permissions":{
            "metadata":"read","contents":"write","issues":"write","pull_requests":"write","checks":"read","actions":"read"}}).to_string().into_bytes())
    }
}
pub(super) struct Private(pub(super) PathBuf);
impl Drop for Private {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}
pub(super) fn rows(root: &Path) -> Vec<Value> {
    fs::read_to_string(root.join("endpoint-calls.jsonl"))
        .unwrap_or_default()
        .lines()
        .map(|line| serde_json::from_str(line).unwrap())
        .collect()
}
pub(super) fn config() -> Value {
    json!({"schema":"openwiz.service-config.v1","repository":{"owner":"synthetic-owner","name":"synthetic-repo"},
        "operator":"synthetic-owner","project":"prj_syn_engine","orchestrator_thread":"thr_syn_answer",
        "service_issue":901,"github_app":{"app_id":1001,"installation_id":2002},
        "tick":{"every_s":300},"health":{"every_s":60},"server":{"port":7370,"allowed_host":null,"probe_timeout_s":10}})
}
pub(super) fn records(root: &Path) -> update::Records {
    let client = client(root, &config().to_string()).unwrap();
    update::app_record_sink(
        901,
        "synthetic-owner/synthetic-repo",
        Arc::new(move |call, deadline| {
            client
                .execute(call, deadline)
                .map_err(|_| update::RecordError::Uncertain)
        }),
    )
    .unwrap()
}

pub(super) fn directory(path: &Path) {
    fs::DirBuilder::new()
        .recursive(true)
        .mode(0o700)
        .create(path)
        .unwrap();
}
pub(super) fn file(path: &Path, value: impl AsRef<[u8]>) {
    fs::write(path, value).unwrap();
    fs::set_permissions(path, fs::Permissions::from_mode(0o600)).unwrap();
}
pub(super) struct Fixture {
    pub root: Private,
    pub install: PathBuf,
    pub source: PathBuf,
    pub build: PathBuf,
}
impl Fixture {
    pub fn new(mode: &str, endpoint: &str) -> Self {
        static NEXT: AtomicU64 = AtomicU64::new(0);
        let root = Private(std::env::temp_dir().join(format!(
            "openwiz-engine-app-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        )));
        let install = root.0.join("install");
        let source = root.0.join("consumer");
        let build = root.0.join("service/builds").join(OLD);
        for path in [
            &install,
            &source,
            &build.join("runtime"),
            &root.0.join("service/app"),
        ] {
            directory(path);
        }
        file(&root.0.join("service/config.json"), config().to_string());
        file(&root.0.join("mode"), mode);
        file(
            &install.join("channel.json"),
            r#"{"schema":"openwiz.update-channel.v1","channel":"packaged"}"#,
        );
        file(
            &build.join("runtime/pull.py"),
            "Synthetic unused transport; executor records calls.",
        );
        file(
            &build.join("openwiz-service"),
            "Synthetic unexecuted selected build.",
        );
        symlink(&build, install.join("current")).unwrap();
        let key = root.0.join("service/app/private-key.pem");
        let keygen = Command::new("/usr/bin/openssl")
            .args([
                "genpkey",
                "-algorithm",
                "RSA",
                "-pkeyopt",
                "rsa_keygen_bits:2048",
                "-out",
            ])
            .arg(&key)
            .output()
            .unwrap();
        assert!(keygen.status.success());
        fs::set_permissions(key, fs::Permissions::from_mode(0o600)).unwrap();
        let quote = |p: &Path| format!("'{}'", p.to_str().unwrap().replace('\'', "'\\''"));
        let script = format!(
            "#!/bin/sh\nexport OPENWIZ_ENGINE_APP_ROOT={}\nexport OPENWIZ_ENGINE_APP_ARGS={}/args-$$\nprintf '%s\\0' \"$@\" > \"$OPENWIZ_ENGINE_APP_ARGS\"\nexec {} --exact {endpoint} --nocapture 3>&1 >/dev/null\n",
            quote(&root.0),
            quote(&root.0),
            quote(&std::env::current_exe().unwrap())
        );
        place_script(&root.0.join("gh"), &script);
        Self {
            root,
            install,
            source,
            build,
        }
    }
}
pub(super) fn app_endpoint_process() {
    let Some(root) = std::env::var_os("OPENWIZ_ENGINE_APP_ROOT") else {
        return;
    };
    let root = PathBuf::from(root);
    let input = PathBuf::from(std::env::var_os("OPENWIZ_ENGINE_APP_ARGS").unwrap());
    let bytes = fs::read(&input).unwrap();
    fs::remove_file(input).unwrap();
    assert_eq!(bytes.last(), Some(&0));
    let args: Vec<_> = bytes[..bytes.len() - 1]
        .split(|b| *b == 0)
        .map(|b| std::str::from_utf8(b).unwrap().to_owned())
        .collect();
    assert_eq!(std::env::var("GH_TOKEN").unwrap(), TOKEN);
    let repository = expected_repository(&root);
    let issue = fs::read_to_string(root.join("expected-issue")).unwrap_or_else(|_| "901".into());
    let url = format!("https://github.com/{repository}/issues/{issue}#issuecomment-123");
    assert_eq!(
        std::env::var("GH_REPO").unwrap(),
        format!("github.com/{repository}")
    );
    assert_eq!(std::env::var("GH_HOST").unwrap(), "github.com");
    let mode = fs::read_to_string(root.join("mode")).unwrap();
    let write = args.get(1).map(String::as_str) == Some("comment");
    OpenOptions::new()
        .create(true)
        .append(true)
        .mode(0o600)
        .open(root.join("endpoint-calls.jsonl"))
        .unwrap()
        .write_all(
            format!(
                "{}\n",
                json!({"write":write,"issue":args[2],"repo":std::env::var("GH_REPO").unwrap()})
            )
            .as_bytes(),
        )
        .unwrap();
    let answer = if write {
        assert_eq!(&args[..4], ["issue", "comment", issue.as_str(), "--body"]);
        assert_eq!(args.len(), 5);
        file(
            &root.join("posted.json"),
            json!({"body":args[4],"url":url}).to_string(),
        );
        if mode == "lost" {
            std::process::exit(97)
        }
        format!("{url}\n")
    } else {
        assert_eq!(
            args,
            ["issue", "view", issue.as_str(), "--json", "comments"]
        );
        let posted: Value =
            serde_json::from_slice(&fs::read(root.join("posted.json")).unwrap()).unwrap();
        let comments = if mode == "missing" {
            vec![]
        } else {
            vec![json!({"id":"synthetic-comment","author":null,
            "authorAssociation":"OWNER","body":if mode=="wrong" {json!("Synthetic wrong readback")} else {posted["body"].clone()},
            "createdAt":"2030-01-01T00:00:00Z","includesCreatedEdit":false,"isMinimized":false,"minimizedReason":"",
            "reactionGroups":[],"url":url,"viewerDidAuthor":true})]
        };
        json!({"comments":comments}).to_string()
    };
    let mut out = OpenOptions::new()
        .write(true)
        .open("/proc/self/fd/3")
        .unwrap();
    out.write_all(answer.as_bytes()).unwrap();
    std::process::exit(0);
}

pub(super) fn expected_repository(root: &Path) -> String {
    fs::read_to_string(root.join("expected-repository"))
        .unwrap_or_else(|_| "synthetic-owner/synthetic-repo".into())
}
pub(super) fn client(root: &Path, config: &str) -> Result<Client, Error> {
    let repository = expected_repository(root);
    let (owner, name) = repository.split_once('/').unwrap();
    let (owner, name) = (owner.to_owned(), name.to_owned());
    Client::with_exchange(
        root,
        config,
        root.join("gh"),
        Arc::new(Tokens(name, owner)),
        Arc::new(FixedTime),
    )
}

// Fixture programs are placed by a separate `cp` (#811), shared.
#[path = "../support/place.rs"]
mod place;
use place::place_script;
