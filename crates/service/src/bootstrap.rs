//! Installed startup gate. Existing source deployments keep their prior path.
//! Packaged starts require a private, verified installation.
pub fn check(executable: &std::path::Path) -> Result<(), String> {
    use openwiz_core::messaging::sha256_hex;
    use std::{
        collections::BTreeSet,
        fs,
        os::unix::fs::MetadataExt,
        path::{Component, Path, PathBuf},
    };
    const TARGETS: [&str; 3] = [
        "aarch64-apple-darwin",
        "x86_64-apple-darwin",
        "x86_64-unknown-linux-gnu",
    ];
    const PROGRAMS: [&str; 3] = ["openwiz", "openwiz-service", "openwiz-server"];
    // tools/install/install.py REQUIRED; the t12 proof reads the installer's list.
    const REQUIRED: [&str; 22] = [
        "openwiz",
        "openwiz-service",
        "openwiz-server",
        "web/openwiz-build.txt",
        "runtime/openwiz-build.txt",
        "web/index.html",
        "web/setup.html",
        "runtime/install.py",
        "runtime/pull.py",
        "runtime/skills/setup/SKILL.md",
        "runtime/skills/grill/SKILL.md",
        "runtime/skills/plan-graph/SKILL.md",
        "runtime/skills/launch-fleet/SKILL.md",
        "runtime/skills/launch-fleet/scripts/fleet.sh",
        "runtime/setup/setup.py",
        "runtime/setup/store.py",
        "runtime/setup/github_login.py",
        "runtime/github-app/setup.py",
        "runtime/github-app/app.py",
        "runtime/github-app/manifest.json",
        "runtime/cloudroom/cloudroom.py",
        "runtime/setup/init.py",
    ];
    #[derive(serde::Deserialize)]
    #[serde(deny_unknown_fields)]
    struct Manifest {
        schema: String,
        version: String,
        source: String,
        target: String,
        setup_api: u64,
        archive: String,
        archive_sha256: String,
        archive_bytes: u64,
        assets: Vec<Asset>,
    }
    #[derive(serde::Deserialize)]
    #[serde(deny_unknown_fields)]
    struct Asset {
        path: String,
        sha256: String,
        bytes: u64,
        mode: String,
    }
    let refuse = |why: &str| Err(format!("Packaged startup refused: {why}; login: unknown"));
    let missing = |path: &Path| matches!(fs::symlink_metadata(path), Err(e) if e.kind() == std::io::ErrorKind::NotFound);
    let build = executable
        .parent()
        .ok_or("cannot locate the service package")?;
    // A damaged/missing manifest must not reclassify a packaged build as a
    // source deployment. Source updater builds have no packaged runtime.
    let packaged = ["install-manifest.json", "runtime"]
        .iter()
        .any(|marker| !missing(&build.join(marker)));
    if !packaged {
        return Ok(());
    }
    let Ok(owner) = openwiz_store::attachments::effective_uid() else {
        return refuse("the effective owner is unreadable");
    };
    // Owner-held, not group/other accessible, the expected kind, singly linked.
    let private = |path: &Path, directory: bool| {
        fs::symlink_metadata(path).is_ok_and(|m| {
            m.uid() == owner
                && m.mode() & 0o077 == 0
                && if directory {
                    m.is_dir()
                } else {
                    m.is_file() && m.nlink() == 1
                }
        })
    };
    let read = |path: &Path, limit: u64| -> Option<Vec<u8>> {
        let bytes = private(path, false)
            .then(|| fs::read(path).ok())
            .flatten()?;
        (bytes.len() as u64 <= limit).then_some(bytes)
    };
    let hex = |text: &str, n: usize| {
        text.len() == n
            && text
                .bytes()
                .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
    };
    let charset = |text: &str, extra: &[u8]| {
        text.bytes()
            .all(|b| b.is_ascii_alphanumeric() || extra.contains(&b))
    };
    let version = |text: &str| {
        let parts: Vec<_> = text.split('.').collect();
        parts.len() == 3
            && parts[0] == "0"
            && parts[1..]
                .iter()
                .all(|p| !p.is_empty() && p.bytes().all(|b| b.is_ascii_digit()))
    };
    // install.path_guard: absolute and plain, every existing ancestor a real dir.
    let plain = |path: &Path| {
        path.is_absolute()
            && path
                .components()
                .all(|c| matches!(c, Component::RootDir | Component::Normal(_)))
            && path.ancestors().all(|p| match fs::symlink_metadata(p) {
                Ok(m) => m.is_dir(),
                Err(e) => e.kind() == std::io::ErrorKind::NotFound,
            })
    };
    // The selected build and its installer-valid manifest.
    let name = build.file_name().and_then(|n| n.to_str()).unwrap_or("");
    let Some(builds) = build.parent().filter(|p| p.ends_with("service/builds")) else {
        return refuse("the build is outside an installed state root");
    };
    let Some(state) = builds.parent().and_then(Path::parent) else {
        return refuse("the build is outside an installed state root");
    };
    if executable
        .file_name()
        .is_none_or(|name| name != "openwiz-service")
    {
        return refuse("the running executable does not belong to the installed package");
    }
    if !hex(name, 40) || !plain(build) || !private(build, true) {
        return refuse("the installed build is not a private verified selection");
    }

    // Check the state actually used by the runtime. Setup state is optional;
    // when present it must still be a real, owner-private directory.
    let Ok(runtime_state) = openwiz_store::default_state_dir(&|n| std::env::var_os(n)) else {
        return refuse("the runtime state directory is unavailable");
    };
    let setup = state.join("setup");
    if runtime_state != state
        || ![state, &state.join("service"), builds]
            .iter()
            .all(|path| private(path, true))
        || (!missing(&setup) && !private(&setup, true))
    {
        return refuse("the runtime state is not this installation's private state");
    }

    // An installed build must be selected by an identifiable, private root.
    // The standard root and the installer's implicit <root>/state are the only
    // locations where the existing layout identifies that root.
    let selected = |root: &Path| {
        let current = root.join("current");
        plain(root)
            && private(root, true)
            && fs::symlink_metadata(&current)
                .is_ok_and(|m| m.file_type().is_symlink() && m.uid() == owner)
            && fs::read_link(current).is_ok_and(|target| target == build)
    };
    let standard =
        std::env::var_os("HOME").map(|home| PathBuf::from(home).join(".local/lib/openwiz"));
    let default = state.parent().filter(|_| state.ends_with("state"));
    if !standard.as_deref().is_some_and(selected) && !default.is_some_and(selected) {
        return refuse("cannot identify the private install root selecting this build");
    }

    let Some(manifest) = read(&build.join("install-manifest.json"), 4 * 1024 * 1024)
        .and_then(|b| serde_json::from_slice::<Manifest>(&b).ok())
    else {
        return refuse("the installed manifest is unreadable");
    };
    let bundle_ok = manifest
        .archive
        .strip_suffix(".tar.gz")
        .is_some_and(|stem| !stem.is_empty() && charset(stem, b"_.-"));
    if manifest.schema != "openwiz.install.v1"
        || manifest.source != name
        || !version(&manifest.version)
        || !TARGETS.contains(&manifest.target.as_str())
        || manifest.setup_api != 1
        || !bundle_ok
        || !hex(&manifest.archive_sha256, 64)
        || manifest.archive_bytes == 0
        || manifest.assets.is_empty()
    {
        return refuse("the installed manifest is not an installer-valid package");
    }
    let identity = format!(
        "openwiz.package.v1\n{}\n{}\n{}\n",
        manifest.version, manifest.source, manifest.target
    );
    let mut listed = BTreeSet::new();
    for asset in &manifest.assets {
        let program = PROGRAMS.contains(&asset.path.as_str());
        let safe = charset(&asset.path, b"_+./-")
            && !asset.path.starts_with('/')
            && asset
                .path
                .split('/')
                .all(|p| !p.is_empty() && !p.starts_with('.'))
            && (program || asset.path.starts_with("web/") || asset.path.starts_with("runtime/"));
        let overlaps = listed.iter().any(|p: &String| {
            p == &asset.path
                || asset.path.starts_with(&format!("{p}/"))
                || p.starts_with(&format!("{}/", asset.path))
        });
        let mode = if program || asset.path.ends_with(".sh") {
            "0700"
        } else {
            "0600"
        };
        let path = build.join(&asset.path);
        let matches = safe
            && !overlaps
            && hex(&asset.sha256, 64)
            && asset.mode == mode
            && fs::symlink_metadata(&path)
                .is_ok_and(|m| format!("{:04o}", m.mode() & 0o7777) == asset.mode)
            && read(&path, asset.bytes).is_some_and(|data| {
                data.len() as u64 == asset.bytes && sha256_hex(&data) == asset.sha256
            });
        if !matches {
            return refuse("an installed asset differs from the verified manifest");
        }
        listed.insert(asset.path.clone());
    }
    if !REQUIRED.iter().all(|r| listed.contains(*r)) {
        return refuse("the installed package lacks a required asset");
    }
    let stamp = (sha256_hex(identity.as_bytes()), identity.len() as u64);
    if manifest
        .assets
        .iter()
        .filter(|a| a.path == "web/openwiz-build.txt" || a.path == "runtime/openwiz-build.txt")
        .any(|a| (a.sha256.clone(), a.bytes) != stamp)
    {
        return refuse("the web/runtime build identity differs");
    }
    let mut found = BTreeSet::new();
    let mut pending = vec![build.to_path_buf()];
    while let Some(directory) = pending.pop() {
        let Ok(entries) = fs::read_dir(&directory) else {
            return refuse("the installed build is unreadable");
        };
        for entry in entries {
            let Ok(path) = entry.map(|e| e.path()) else {
                return refuse("the installed build is unreadable");
            };
            if private(&path, true) {
                pending.push(path);
            } else if let Some(relative) = path
                .strip_prefix(build)
                .ok()
                .and_then(Path::to_str)
                .filter(|_| private(&path, false))
            {
                found.insert(relative.to_owned());
            } else {
                return refuse("the installed build holds an unverified entry");
            }
        }
    }
    found.remove("install-manifest.json");
    if found != listed {
        return refuse("the installed build holds an unlisted asset");
    }

    eprintln!("openwiz-service: installed package verified; login: unknown");
    Ok(())
}
