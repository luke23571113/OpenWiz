//! Execute the documented setup blocks only against synthetic files and tools.
use std::{
    fs,
    os::unix::fs::{DirBuilderExt, PermissionsExt},
    path::{Path, PathBuf},
    process::{Command, Output},
    sync::atomic::{AtomicU64, Ordering},
};

const README: &str = include_str!("../../deploy/pc/README.md");
fn block(index: usize) -> &'static str {
    README
        .split("```sh\n")
        .nth(index + 1)
        .unwrap()
        .split("```")
        .next()
        .unwrap()
}
fn dir(path: &Path) {
    fs::DirBuilder::new()
        .recursive(true)
        .mode(0o700)
        .create(path)
        .unwrap();
}
fn file(path: &Path, body: impl AsRef<[u8]>, mode: u32) {
    dir(path.parent().unwrap());
    // Every file goes through `place`, so no fake program is written here.
    place_script(path, std::str::from_utf8(body.as_ref()).unwrap());
    fs::set_permissions(path, fs::Permissions::from_mode(mode)).unwrap();
}
struct Setup(PathBuf);
impl Setup {
    fn new() -> Self {
        static NEXT: AtomicU64 = AtomicU64::new(0);
        let root = std::env::temp_dir().join(format!(
            "ow-t4-setup-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        dir(&root.join("home"));
        dir(&root.join("work"));
        dir(&root.join("tools"));
        let setup = Self(root);
        file(
            &setup.0.join("tools/git"),
            "#!/bin/sh\nprintf '0123456789abcdef0123456789abcdef01234567\\n'\n",
            0o700,
        );
        file(
            &setup.0.join("work/target/release/openwiz-service"),
            "synthetic program",
            0o700,
        );
        file(
            &setup.0.join("work/apps/web/out/index.html"),
            "synthetic page",
            0o600,
        );
        file(
            &setup.0.join("work/deploy/pc/config.example.json"),
            include_bytes!("../../deploy/pc/config.example.json"),
            0o600,
        );
        file(
            &setup.0.join("work/deploy/pc/openwiz.service"),
            include_bytes!("../../deploy/pc/openwiz.service"),
            0o600,
        );
        for tool in ["loginctl", "systemctl"] {
            file(
                &setup.0.join("tools").join(tool),
                "#!/bin/sh\n{ printf '%s' \"${0##*/}\"; printf ' <%s>' \"$@\"; printf '\\n'; } >> \"$T4_CALLS\"\n",
                0o700,
            );
        }
        file(&setup.0.join("tools/sleep"), "#!/bin/sh\nexit 0\n", 0o700);
        setup
    }
    fn home(&self, path: &str) -> PathBuf {
        self.0.join("home").join(path)
    }
    fn run(&self, script: &str, fail: bool) -> Output {
        Command::new("/bin/bash")
            .args(["-c", script])
            .current_dir(self.0.join("work"))
            .env("HOME", self.0.join("home"))
            .env("USER", "synthetic-owner")
            .env(
                "PATH",
                format!("{}:/usr/bin:/bin", self.0.join("tools").display()),
            )
            .env("T4_CALLS", self.0.join("setup-calls"))
            .env("T4_COUNT", self.0.join("status-count"))
            .env("T4_ALWAYS_FAIL", if fail { "1" } else { "0" })
            .output()
            .unwrap()
    }
}
impl Drop for Setup {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.0).unwrap();
    }
}

fn prove_staging(script: &str) {
    for existing in [
        ".local/state/openwiz/service/config.json",
        ".config/systemd/user/openwiz.service",
        ".local/lib/openwiz/source",
    ] {
        let f = Setup::new();
        let path = f.home(existing);
        file(&path, b"existing synthetic owner file", 0o600);
        let out = f.run(script, false);
        assert!(
            !out.status.success(),
            "staging must refuse existing {existing}"
        );
        assert_eq!(fs::read(path).unwrap(), b"existing synthetic owner file");
        assert!(!f.home(".local/lib/openwiz/current").exists());
    }
    let f = Setup::new();
    let out = f.run(script, false);
    assert!(
        out.status.success(),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
    assert_eq!(
        fs::read(f.home(".local/state/openwiz/service/config.json")).unwrap(),
        include_bytes!("../../deploy/pc/config.example.json")
    );
    let unit = f.home(".config/systemd/user/openwiz.service");
    assert_eq!(
        fs::read(&unit).expect("fresh staging must install the user unit"),
        include_bytes!("../../deploy/pc/openwiz.service")
    );
    assert_eq!(
        fs::metadata(&unit).unwrap().permissions().mode() & 0o777,
        0o600,
        "staged user unit must be owner-only"
    );
    assert!(
        f.home(".local/lib/openwiz/current/web/index.html")
            .is_file()
    );
    assert_eq!(
        fs::read_link(f.home(".local/lib/openwiz/source")).unwrap(),
        f.0.join("work").canonicalize().unwrap()
    );
    assert_eq!(
        fs::metadata(f.home(".local/lib/openwiz/current/openwiz-service"))
            .unwrap()
            .permissions()
            .mode()
            & 0o777,
        0o700
    );
}

fn prove_bootstrap(script: &str) {
    for fail in [false, true] {
        let f = Setup::new();
        file(
            &f.home(".local/lib/openwiz/current/openwiz-service"),
            "#!/bin/sh\nn=$(cat \"$T4_COUNT\" 2>/dev/null || printf 0)\nn=$((n + 1))\nprintf '%s\\n' \"$n\" > \"$T4_COUNT\"\n[ \"$T4_ALWAYS_FAIL\" = 0 ] && [ \"$n\" -ge 3 ]\n",
            0o700,
        );
        let out = f.run(script, fail);
        assert_eq!(
            out.status.success(),
            !fail,
            "{}",
            String::from_utf8_lossy(&out.stderr)
        );
        assert_eq!(
            fs::read_to_string(f.0.join("setup-calls")).unwrap(),
            concat!(
                "loginctl <enable-linger> <synthetic-owner>\n",
                "systemctl <--user> <daemon-reload>\n",
                "systemctl <--user> <enable> <--now> <openwiz.service>\n",
            ),
            "bootstrap must enable lingering, reload, then enable the user service"
        );
        assert_eq!(
            fs::read_to_string(f.0.join("status-count")).unwrap().trim(),
            if fail { "30" } else { "3" }
        );
    }
}

#[test]
fn documented_staging_preserves_existing_config_and_unit() {
    prove_staging(block(1));
}

#[test]
fn documented_bootstrap_waits_for_status_and_fails_if_it_never_answers() {
    prove_bootstrap(block(2));
}

#[test]
fn staging_proof_rejects_missing_changed_or_public_unit() {
    let install =
        "install -m 600 deploy/pc/openwiz.service \"$HOME/.config/systemd/user/openwiz.service\"";
    for replacement in [
        "".to_string(),
        install.replace("deploy/pc/openwiz.service", "deploy/pc/config.example.json"),
        install.replace("-m 600", "-m 644"),
    ] {
        assert!(
            block(1).contains(install),
            "mutation must change the fixture"
        );
        let script = block(1).replace(install, &replacement);
        assert!(
            std::panic::catch_unwind(|| prove_staging(&script)).is_err(),
            "staging proof accepted unit install mutation: {replacement:?}"
        );
    }
}

#[test]
fn bootstrap_proof_rejects_missing_or_reordered_setup_calls() {
    let calls = [
        "loginctl enable-linger \"$USER\"\n",
        "systemctl --user daemon-reload\n",
        "systemctl --user enable --now openwiz.service\n",
    ];
    let mut rejected = Vec::new();
    for call in calls {
        assert!(block(2).contains(call), "mutation must change the fixture");
        let script = block(2).replace(call, "");
        rejected.push(std::panic::catch_unwind(|| prove_bootstrap(&script)).is_err());
    }
    let original = format!("{}{}", calls[0], calls[1]);
    assert!(block(2).contains(&original));
    let script = block(2).replace(&original, &format!("{}{}", calls[1], calls[0]));
    rejected.push(std::panic::catch_unwind(|| prove_bootstrap(&script)).is_err());
    assert_eq!(
        rejected,
        vec![true; 4],
        "missing calls, then reordered calls"
    );
}

// Fixture programs are placed by a separate `cp` (#811), shared.
#[path = "../support/place.rs"]
mod place;
use place::place_script;
