use std::fs::{self, File, Metadata, OpenOptions};
use std::io::{ErrorKind, Read};
use std::os::unix::fs::{MetadataExt, OpenOptionsExt};
use std::path::{Component, Path};
use std::time::{Duration, Instant};

pub fn inspect(root: &Path) -> Result<(), String> {
    bounded(|| inspect_once(root).map(|_| ()))
}

const ATTEMPTS: usize = 8;
const RETRY_TIME: Duration = Duration::from_millis(100);

pub(crate) enum Failure {
    Refused(String),
    Changed(String),
}
impl Failure {
    fn reason(self) -> String {
        match self {
            Self::Refused(reason) | Self::Changed(reason) => reason,
        }
    }
}
impl From<String> for Failure {
    fn from(reason: String) -> Self {
        Self::Refused(reason)
    }
}
fn bounded<T>(inspect: impl FnMut() -> Result<T, Failure>) -> Result<T, String> {
    retried(RETRY_TIME, inspect).map_err(Failure::reason)
}
fn retried<T>(
    budget: Duration,
    mut inspect: impl FnMut() -> Result<T, Failure>,
) -> Result<T, Failure> {
    let started = Instant::now();
    let mut reason = "private state inspection: retry time limit reached".to_owned();
    for attempt in 0..ATTEMPTS {
        if attempt > 0 && started.elapsed() >= budget {
            return Err(Failure::Changed(reason));
        }
        match inspect() {
            Ok(value) => return Ok(value),
            Err(Failure::Refused(reason)) => return Err(Failure::Refused(reason)),
            Err(Failure::Changed(changed)) => {
                reason = changed;
                if attempt + 1 < ATTEMPTS {
                    let remaining = budget.saturating_sub(started.elapsed());
                    let pause = Duration::from_micros(50) * 3_u32.pow(attempt as u32);
                    std::thread::sleep(remaining.min(pause));
                }
            }
        }
    }
    Err(Failure::Changed(reason))
}

pub fn read_service_state(root: &Path) -> Result<Option<String>, String> {
    let file = bounded(|| {
        let Some(meta) = inspect_once(root)? else {
            return Ok(None);
        };
        open_checked(&root.join("service/state.json"), &meta).map(Some)
    })?;
    file.map(|mut file| {
        let mut body = String::new();
        file.read_to_string(&mut body)
            .map_err(|_| "service/state.json: cannot read state".to_owned())?;
        Ok(body)
    })
    .transpose()
}

fn open_checked(path: &Path, checked: &Metadata) -> Result<File, Failure> {
    let flags = if cfg!(target_vendor = "apple") {
        0x0100 | 0x0004
    } else if cfg!(any(target_arch = "arm", target_arch = "aarch64")) {
        0o100000 | 0o4000
    } else {
        0o400000 | 0o4000
    };
    let file = OpenOptions::new()
        .read(true)
        .custom_flags(flags)
        .open(path)
        .map_err(|_| {
            Failure::Refused("service/state.json: cannot open checked state".to_owned())
        })?;
    let opened = file.metadata().map_err(|_| {
        Failure::Refused("service/state.json: cannot inspect opened state".to_owned())
    })?;
    if opened.nlink() > 1 {
        return Err(Failure::Refused(
            "service/state.json: must be a regular file".to_owned(),
        ));
    }
    if !opened.is_file()
        || opened.dev() != checked.dev()
        || opened.ino() != checked.ino()
        || opened.nlink() != 1
        || opened.uid() != checked.uid()
        || opened.mode() != checked.mode()
    {
        return Err(Failure::Changed(
            "service/state.json: checked state changed before reading".to_owned(),
        ));
    }
    Ok(file)
}

fn inspect_once(root: &Path) -> Result<Option<Metadata>, Failure> {
    if !root.is_absolute()
        || !root
            .components()
            .all(|c| matches!(c, Component::RootDir | Component::Normal(_)))
    {
        return Err(
            "state directory must be absolute, with no . or .. components"
                .to_owned()
                .into(),
        );
    }
    #[cfg(target_os = "macos")]
    let uid = crate::state::owner::owner_uid_from_private_state(root)?;
    #[cfg(not(target_os = "macos"))]
    let uid = crate::state::owner::effective_uid()?;
    for ancestor in root.ancestors() {
        let meta = fs::symlink_metadata(ancestor)
            .map_err(|_| "cannot inspect state directory ancestors".to_owned())?;
        if meta.file_type().is_symlink() {
            return Err("state directory must not have a symlink ancestor"
                .to_owned()
                .into());
        }
        match fs::symlink_metadata(ancestor.join(".git")) {
            Ok(_) => {
                return Err("state directory must be outside every repository"
                    .to_owned()
                    .into());
            }
            Err(e) if e.kind() == ErrorKind::NotFound => {}
            Err(_) => {
                return Err("cannot check whether state directory is in a repository"
                    .to_owned()
                    .into());
            }
        }
    }
    checked(root, "state directory", true, true, uid)?;
    let mut state = None;
    for (suffix, directory, required) in [
        ("service", true, true),
        ("service/config.json", false, true),
        ("service/state.json", false, false),
        ("service/app", true, false),
        ("service/app/private-key.pem", false, false),
        ("service/clone", true, false),
        ("service/builds", true, false),
    ] {
        let path = root.join(suffix);
        let meta = checked(&path, suffix, directory, required, uid)?;
        if suffix == "service/state.json" {
            state = meta;
        }
        if matches!(suffix, "service" | "service/app") {
            match fs::symlink_metadata(path.join(".git")) {
                Ok(_) => {
                    return Err("private service state must be outside every repository"
                        .to_owned()
                        .into());
                }
                Err(e) if e.kind() == ErrorKind::NotFound => {}
                Err(_) => {
                    return Err("cannot inspect private service repository boundary"
                        .to_owned()
                        .into());
                }
            }
        }
    }
    Ok(state)
}

fn checked(
    path: &Path,
    label: &str,
    directory: bool,
    required: bool,
    uid: u32,
) -> Result<Option<Metadata>, Failure> {
    let fail = |rule: &str| Err(Failure::Refused(format!("{label}: {rule}")));
    let meta = match fs::symlink_metadata(path) {
        Ok(meta) => meta,
        Err(e) if !required && e.kind() == ErrorKind::NotFound => return Ok(None),
        Err(_) => return fail("cannot inspect the required path"),
    };
    if meta.file_type().is_symlink() {
        return fail("symlinks are refused");
    }
    if meta.uid() != uid {
        return fail("must be owned by the service's user");
    }
    if meta.mode() & 0o077 != 0 {
        return fail("must not be open to group or others");
    }
    if !directory && meta.is_file() && meta.nlink() == 0 {
        return Err(Failure::Changed(format!("{label}: must be a regular file")));
    }
    if (directory && !meta.is_dir()) || (!directory && (!meta.is_file() || meta.nlink() != 1)) {
        return fail(if directory {
            "must be a directory"
        } else {
            "must be a regular file"
        });
    }
    Ok(Some(meta))
}

#[cfg(all(test, target_os = "linux"))]
mod tests {
    use super::*;
    use std::os::fd::AsRawFd;
    use std::os::unix::fs::{DirBuilderExt, FileTypeExt, PermissionsExt, symlink};
    use std::sync::atomic::{AtomicU64, Ordering};

    struct Fixture(std::path::PathBuf);
    impl Fixture {
        fn new() -> Self {
            static NEXT: AtomicU64 = AtomicU64::new(0);
            let root = std::env::temp_dir().join(format!(
                "openwiz-checked-state-{}-{}",
                std::process::id(),
                NEXT.fetch_add(1, Ordering::Relaxed)
            ));
            fs::DirBuilder::new().mode(0o700).create(&root).unwrap();
            Self(root)
        }
        fn file(&self, name: &str, body: &[u8]) -> std::path::PathBuf {
            let path = self.0.join(name);
            OpenOptions::new()
                .write(true)
                .create_new(true)
                .mode(0o600)
                .open(&path)
                .unwrap();
            fs::write(&path, body).unwrap();
            path
        }
    }
    impl Drop for Fixture {
        fn drop(&mut self) {
            fs::remove_dir_all(&self.0).unwrap();
        }
    }

    #[test]
    fn checked_descriptor_rejects_replacement_and_retains_its_own_bytes() {
        let fixture = Fixture::new();
        let path = fixture.file("state", b"checked bytes");
        let meta = fs::symlink_metadata(&path).unwrap();
        let mut file = match open_checked(&path, &meta) {
            Ok(file) => file,
            Err(_) => panic!("stable checked inode must open"),
        };
        let info = fs::read_to_string(format!("/proc/self/fdinfo/{}", file.as_raw_fd())).unwrap();
        let flags = info
            .lines()
            .find_map(|line| line.strip_prefix("flags:"))
            .unwrap();
        let flags = u32::from_str_radix(flags.trim(), 8).unwrap();
        assert_ne!(flags & 0o4000, 0, "the descriptor must be nonblocking");
        assert_eq!(flags & 3, 0, "the descriptor must be read-only");
        fs::rename(fixture.file("replacement", b"replacement bytes"), &path).unwrap();
        assert!(matches!(
            open_checked(&path, &meta),
            Err(Failure::Changed(_))
        ));
        let mut bytes = String::new();
        file.read_to_string(&mut bytes).unwrap();
        assert_eq!(bytes, "checked bytes");
    }

    #[test]
    fn checked_descriptor_rejects_changed_modes_links_and_nonregular_replacements() {
        for case in ["mode", "hard link", "symlink", "directory", "socket"] {
            let fixture = Fixture::new();
            let path = fixture.file("state", b"synthetic bytes");
            let meta = fs::symlink_metadata(&path).unwrap();
            match case {
                "mode" => fs::set_permissions(&path, fs::Permissions::from_mode(0o400)).unwrap(),
                "hard link" => fs::hard_link(&path, fixture.0.join("alias")).unwrap(),
                "symlink" => {
                    fs::rename(&path, fixture.0.join("target")).unwrap();
                    symlink(fixture.0.join("target"), &path).unwrap();
                }
                "directory" => {
                    fs::remove_file(&path).unwrap();
                    fs::DirBuilder::new().mode(0o700).create(&path).unwrap();
                }
                "socket" => {
                    fs::remove_file(&path).unwrap();
                    let _socket = std::os::unix::net::UnixListener::bind(&path).unwrap();
                    assert!(fs::symlink_metadata(&path).unwrap().file_type().is_socket());
                    assert!(open_checked(&path, &meta).is_err());
                }
                _ => unreachable!(),
            }
            assert!(open_checked(&path, &meta).is_err(), "{case}");
        }
    }

    #[test]
    fn service_state_reader_preserves_optional_absence_and_refuses_unsafe_paths() {
        let fixture = Fixture::new();
        fs::DirBuilder::new()
            .mode(0o700)
            .create(fixture.0.join("service"))
            .unwrap();
        fixture.file("service/config.json", b"{}");
        assert_eq!(read_service_state(&fixture.0).unwrap(), None);
        let state = fixture.file("service/state.json", b"synthetic state bytes");
        assert_eq!(
            read_service_state(&fixture.0).unwrap().as_deref(),
            Some("synthetic state bytes")
        );
        fs::hard_link(&state, fixture.0.join("alias")).unwrap();
        assert!(read_service_state(&fixture.0).is_err());
        fs::remove_file(fixture.0.join("alias")).unwrap();
        fs::set_permissions(&state, fs::Permissions::from_mode(0o644)).unwrap();
        assert!(read_service_state(&fixture.0).is_err());
        fs::remove_file(&state).unwrap();
        symlink(fixture.0.join("missing"), &state).unwrap();
        assert!(read_service_state(&fixture.0).is_err());
    }

    #[test]
    fn retry_rechecks_the_complete_private_boundary() {
        let fixture = Fixture::new();
        fs::DirBuilder::new()
            .mode(0o700)
            .create(fixture.0.join("service"))
            .unwrap();
        let config = fixture.file("service/config.json", b"{}");
        fixture.file("service/state.json", b"{}");
        let checked = inspect_once(&fixture.0).unwrap_or_else(|_| panic!("safe fixture"));
        fs::set_permissions(&config, fs::Permissions::from_mode(0o644)).unwrap();
        let state = fixture.0.join("service/state.json");
        fs::rename(fixture.file("replacement", b"{}"), &state).unwrap();
        let mut attempts = 0;
        let result = bounded(|| {
            attempts += 1;
            if attempts == 1 {
                open_checked(&state, checked.as_ref().unwrap())
            } else {
                inspect_once(&fixture.0)?;
                panic!("unsafe config must refuse before opening state again");
            }
        });
        assert_eq!(
            result.err().unwrap(),
            "service/config.json: must not be open to group or others"
        );
        assert_eq!(attempts, 2);
    }

    #[test]
    fn a_passing_inspection_survives_a_pause_beyond_the_retry_budget() {
        let fixture = Fixture::new();
        fs::DirBuilder::new()
            .mode(0o700)
            .create(fixture.0.join("service"))
            .unwrap();
        fixture.file("service/config.json", b"{}");
        fixture.file("service/state.json", b"{}");
        let mut attempts = 0;
        let result = bounded(|| {
            attempts += 1;
            let inspected = inspect_once(&fixture.0)?;
            std::thread::sleep(Duration::from_millis(200));
            Ok(inspected)
        });
        assert!(
            result.is_ok(),
            "a passing inspection was refused: {result:?}"
        );
        assert_eq!(attempts, 1);
    }

    #[test]
    fn a_zero_link_window_inside_the_retry_budget_is_not_refused() {
        let window = Duration::from_millis(30);
        let started = Instant::now();
        let mut attempts = 0;
        let result = bounded(|| {
            attempts += 1;
            if started.elapsed() < window {
                Err(Failure::Changed(
                    "service/state.json: must be a regular file".to_owned(),
                ))
            } else {
                Ok(())
            }
        });
        assert!(
            result.is_ok(),
            "a {window:?} zero-link window refused after {attempts} attempts in {:?}: {result:?}",
            started.elapsed()
        );
        assert!(attempts <= ATTEMPTS);
    }

    #[test]
    fn changed_descriptor_exhaustion_and_deadline_still_refuse() {
        let fixture = Fixture::new();
        let path = fixture.file("state", b"original");
        let meta = fs::symlink_metadata(&path).unwrap();
        fs::rename(fixture.file("replacement", b"replacement"), &path).unwrap();
        let mut attempts = 0;
        assert!(
            retried(Duration::MAX, || {
                attempts += 1;
                open_checked(&path, &meta)
            })
            .is_err()
        );
        assert_eq!(attempts, 8);
        let mut attempts = 0;
        assert!(
            bounded::<File>(|| {
                attempts += 1;
                std::thread::sleep(Duration::from_millis(200));
                open_checked(&path, &meta)
            })
            .is_err()
        );
        assert_eq!(
            attempts, 1,
            "the expired budget must stop before another attempt"
        );
    }

    #[test]
    fn inspect_never_refuses_private_state_during_atomic_replacement() {
        use std::io::Write;
        use std::sync::atomic::AtomicBool;
        use std::sync::{Arc, Barrier};
        let fixture = Fixture::new();
        fs::DirBuilder::new()
            .mode(0o700)
            .create(fixture.0.join("service"))
            .unwrap();
        fixture.file("service/config.json", b"{}");
        fixture.file("service/state.json", b"{}");
        let stop = Arc::new(AtomicBool::new(false));
        let start = Arc::new(Barrier::new(2));
        let writer = std::thread::spawn({
            let (root, stop, start) = (fixture.0.clone(), stop.clone(), start.clone());
            move || {
                let temporary = root.join("service/state.tmp");
                let state = root.join("service/state.json");
                start.wait();
                let mut replacements = 0_u64;
                while !stop.load(Ordering::Relaxed) {
                    OpenOptions::new()
                        .write(true)
                        .create_new(true)
                        .mode(0o600)
                        .open(&temporary)
                        .unwrap()
                        .write_all(b"{}")
                        .unwrap();
                    fs::rename(&temporary, &state).unwrap();
                    replacements += 1;
                }
                replacements
            }
        });
        start.wait();
        let began = Instant::now();
        let mut failures = std::collections::BTreeMap::<String, usize>::new();
        for _ in 0..100_000 {
            if let Err(failure) = retried(Duration::MAX, || inspect_once(&fixture.0).map(|_| ())) {
                *failures.entry(failure.reason()).or_default() += 1;
            }
        }
        stop.store(true, Ordering::Relaxed);
        let replacements = writer.join().unwrap();
        eprintln!(
            "100000 inspections in {:?}, {replacements} atomic replacements; refusals: {failures:?}",
            began.elapsed()
        );
        assert_eq!(
            read_service_state(&fixture.0).unwrap().as_deref(),
            Some("{}")
        );
        assert!(
            replacements > 0,
            "the writer must exercise atomic replacement"
        );
        assert!(
            failures.is_empty(),
            "safe atomic saves must never refuse: {failures:?}"
        );
    }
}
