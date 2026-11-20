pub mod loops;

use std::collections::HashMap;
use std::ffi::{OsStr, OsString};
use std::fs::{self, DirBuilder, File, OpenOptions};
use std::io::{self, Read, Write};
use std::marker::PhantomData;
use std::os::unix::fs::{DirBuilderExt, OpenOptionsExt, PermissionsExt};
use std::path::{Component, Path, PathBuf};
use std::sync::Mutex;

use openwiz_core::messaging::OpId;
use openwiz_core::messaging::record::StoreError;
use openwiz_core::model::Timestamp;

pub mod owner;
pub mod starts;

pub use starts::{StartFileStore, Starts};

pub const STATE_DIR_ENV: &str = "OPENWIZ_STATE_DIR";

pub fn default_state_dir(var: &dyn Fn(&str) -> Option<OsString>) -> Result<PathBuf, StoreError> {
    let absolute = |name: &str| {
        var(name)
            .filter(|v| !v.is_empty())
            .map(PathBuf::from)
            .filter(|p| p.is_absolute())
    };
    if let Some(dir) = var(STATE_DIR_ENV).filter(|v| !v.is_empty()) {
        let dir = PathBuf::from(dir);
        if !dir.is_absolute() {
            return Err(StoreError(format!(
                "{STATE_DIR_ENV} must be an absolute path"
            )));
        }
        return Ok(dir);
    }
    let home = absolute("HOME").ok_or_else(|| {
        StoreError(format!(
            "no state directory: HOME is not an absolute path, and {STATE_DIR_ENV} is not set"
        ))
    })?;
    if cfg!(target_os = "macos") {
        return Ok(home.join("Library/Application Support/openwiz"));
    }
    Ok(absolute("XDG_STATE_HOME")
        .unwrap_or_else(|| home.join(".local/state"))
        .join("openwiz"))
}

type SyncDir<'a> = dyn Fn(&Path) -> io::Result<()> + 'a;

pub trait Area: Send + Sync + 'static {
    const DIR: &'static str;
    const WHAT: &'static str;
}

pub trait Kind: Area {
    type Record: Clone + PartialEq;
    fn op_id(record: &Self::Record) -> &OpId;
    fn is_finished(record: &Self::Record) -> bool;
    fn is_claimed(record: &Self::Record) -> bool;
    fn recover(record: &Self::Record, now: Timestamp) -> Self::Record;
    fn read(text: &str) -> Result<Self::Record, String>;
    fn body(record: &Self::Record) -> Result<Vec<u8>, String>;
}

struct ClaimLock(File);

impl Drop for ClaimLock {
    fn drop(&mut self) {
        let _ = self.0.unlock();
    }
}

pub struct Store<K: Area> {
    dir: PathBuf,
    held: Mutex<HashMap<OpId, ClaimLock>>,
    read_only: bool,
    kind: PhantomData<K>,
}

impl<K: Area> std::fmt::Debug for Store<K> {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Store")
            .field("dir", &self.dir)
            .field("read_only", &self.read_only)
            .finish_non_exhaustive()
    }
}

fn create_dir_synced(dir: &Path, sync: &dyn Fn(&Path) -> io::Result<()>) -> Result<(), StoreError> {
    let create_dir = |d: &Path| DirBuilder::new().mode(0o700).create(d);
    let mut missing = Vec::new();
    let mut next = Some(dir);
    while let Some(d) = next.filter(|d| !d.as_os_str().is_empty() && !d.exists()) {
        missing.push(d);
        next = d.parent();
    }
    for d in missing.into_iter().rev() {
        match create_dir(d) {
            Ok(()) => {}
            Err(e) if e.kind() == io::ErrorKind::AlreadyExists => {}
            Err(e) => return Err(io_error("make", d, &e)),
        }
        let parent = d
            .parent()
            .filter(|p| !p.as_os_str().is_empty())
            .unwrap_or(Path::new("."));
        sync(parent).map_err(|e| io_error("sync", parent, &e))?;
    }
    Ok(())
}

fn fsync_dir(dir: &Path) -> io::Result<()> {
    File::open(dir)?.sync_all()
}

fn inside_repository(dir: &Path) -> Option<PathBuf> {
    let mut existing = dir;
    while !existing.exists() {
        existing = existing.parent()?;
    }
    let resolved = existing.canonicalize().ok()?;
    resolved
        .ancestors()
        .find(|a| a.join(".git").exists())
        .map(Path::to_path_buf)
}

fn io_error(what: &str, path: &Path, e: &io::Error) -> StoreError {
    StoreError(format!("could not {what} {}: {e}", path.display()))
}

impl<K: Area> Store<K> {
    pub fn open(state_dir: &Path) -> Result<Self, StoreError> {
        Self::open_with_sync(state_dir, &fsync_dir)
    }

    pub fn open_with_sync(
        state_dir: &Path,
        sync: &dyn Fn(&Path) -> io::Result<()>,
    ) -> Result<Self, StoreError> {
        let dir = Self::checked_sends(state_dir, Some(sync))?
            .ok_or_else(|| StoreError(format!("{} was not made", state_dir.display())))?;
        Ok(Self::new(dir, false))
    }

    pub fn open_read_only(state_dir: &Path) -> Result<Option<Self>, StoreError> {
        Ok(Self::checked_sends(state_dir, None)?.map(|dir| Self::new(dir, true)))
    }

    fn new(dir: PathBuf, read_only: bool) -> Self {
        Self {
            dir,
            held: Mutex::new(HashMap::new()),
            read_only,
            kind: PhantomData,
        }
    }

    fn checked_sends(
        state_dir: &Path,
        sync: Option<&SyncDir<'_>>,
    ) -> Result<Option<PathBuf>, StoreError> {
        let what = K::WHAT;
        let plain = state_dir.is_absolute()
            && state_dir
                .components()
                .all(|c| matches!(c, Component::RootDir | Component::Normal(_)));
        if !plain {
            return Err(StoreError(format!(
                "{} must be an absolute path with no . or .. component",
                state_dir.display()
            )));
        }
        let in_repository = |dir: &Path| {
            inside_repository(dir).map(|repo| {
                StoreError(format!(
                    "{} is inside the repository at {}; the {what} must be outside every \
                     repository",
                    dir.display(),
                    repo.display()
                ))
            })
        };
        if let Some(refused) = in_repository(state_dir) {
            return Err(refused);
        }
        let records = state_dir.join(K::DIR);
        for dir in [state_dir, &records] {
            if let Some(sync) = sync {
                create_dir_synced(dir, sync)?;
            }
            let meta = match fs::metadata(dir) {
                Ok(meta) => meta,
                Err(e) if sync.is_none() && e.kind() == io::ErrorKind::NotFound => {
                    return Ok(None);
                }
                Err(e) => return Err(io_error("read", dir, &e)),
            };
            if !meta.is_dir() {
                return Err(StoreError(format!("{} is not a directory", dir.display())));
            }
            let mode = meta.permissions().mode() & 0o777;
            if mode & 0o077 != 0 {
                return Err(StoreError(format!(
                    "{} is open to other users (mode {mode:o}); the {what} must be \
                     readable by its owner only (0700)",
                    dir.display()
                )));
            }
        }
        let records_meta =
            fs::symlink_metadata(&records).map_err(|e| io_error("read", &records, &e))?;
        if records_meta.file_type().is_symlink() {
            return Err(StoreError(format!(
                "{} is a symlink; the {what}'s directory must be a real directory",
                records.display()
            )));
        }
        let resolved = records
            .canonicalize()
            .map_err(|e| io_error("resolve", &records, &e))?;
        for dir in resolved.ancestors() {
            if let Some(refused) = in_repository(dir) {
                return Err(refused);
            }
        }
        if let Some(sync) = sync {
            for dir in resolved.ancestors() {
                sync(dir).map_err(|e| io_error("sync", dir, &e))?;
            }
        }
        Ok(Some(records))
    }

    pub fn dir(&self) -> &Path {
        &self.dir
    }

    fn refuse_if_read_only(&self) -> Result<(), StoreError> {
        if self.read_only {
            return Err(StoreError(format!(
                "the {} was opened for reading only",
                K::WHAT
            )));
        }
        Ok(())
    }
}

impl<K: Kind> Store<K> {
    pub fn record_path(&self, op_id: &OpId) -> PathBuf {
        self.dir.join(format!("{op_id}.json"))
    }

    fn lock_path(&self, op_id: &OpId) -> PathBuf {
        self.dir.join(format!("{op_id}.lock"))
    }

    fn lock_file(&self, op_id: &OpId) -> Result<File, StoreError> {
        self.refuse_if_read_only()?;
        let path = self.lock_path(op_id);
        OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .mode(0o600)
            .open(&path)
            .map_err(|e| io_error("open", &path, &e))
    }

    pub fn record(&self, op_id: &OpId) -> Result<Option<K::Record>, StoreError> {
        self.read_record(&self.record_path(op_id))
    }

    fn read_record(&self, path: &Path) -> Result<Option<K::Record>, StoreError> {
        // SECURITY: a FIFO substituted before open must not wait for a writer.
        let nonblock = if cfg!(target_vendor = "apple") {
            0x0004
        } else {
            0o4000
        };
        let mut file = match OpenOptions::new()
            .read(true)
            .custom_flags(nonblock)
            .open(path)
        {
            Ok(file) => file,
            Err(e) if e.kind() == io::ErrorKind::NotFound => return Ok(None),
            Err(e) => return Err(io_error("read", path, &e)),
        };
        let metadata = file.metadata().map_err(|e| io_error("read", path, &e))?;
        if !metadata.is_file() {
            return Err(StoreError(format!(
                "{} is not a regular {} file",
                path.display(),
                K::WHAT
            )));
        }
        // SECURITY: inspect and read the same descriptor: a later path swap cannot
        // replace the file whose type was checked above.
        let mut text = String::new();
        file.read_to_string(&mut text)
            .map_err(|e| io_error("read", path, &e))?;
        let record = K::read(&text).map_err(|why| {
            let why = if why.is_empty() {
                String::new()
            } else {
                format!(" ({why})")
            };
            StoreError(format!("{} is not a {}{why}", path.display(), K::WHAT))
        })?;
        if path.file_name() != Some(OsStr::new(&format!("{}.json", K::op_id(&record)))) {
            return Err(StoreError(format!(
                "{} holds the record of another op id",
                path.display()
            )));
        }
        Ok(Some(record))
    }

    fn write_record(&self, record: &K::Record) -> Result<(), StoreError> {
        self.refuse_if_read_only()?;
        let op_id = K::op_id(record);
        let path = self.record_path(op_id);
        let temp = self.dir.join(format!(".{op_id}.json.tmp"));
        let mut body = K::body(record)
            .map_err(|_| StoreError(format!("a {} could not be serialized", K::WHAT)))?;
        body.push(b'\n');
        let _ = fs::remove_file(&temp);
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .open(&temp)
            .map_err(|e| io_error("make", &temp, &e))?;
        file.write_all(&body)
            .and_then(|()| file.sync_all())
            .map_err(|e| io_error("write", &temp, &e))?;
        drop(file);
        fs::rename(&temp, &path).map_err(|e| io_error("replace", &path, &e))?;
        File::open(&self.dir)
            .and_then(|dir| dir.sync_all())
            .map_err(|e| io_error("sync", &self.dir, &e))
    }

    fn held_by_me(&self, op_id: &OpId) -> bool {
        self.held
            .lock()
            .unwrap_or_else(|p| p.into_inner())
            .contains_key(op_id)
    }

    fn update_record(&self, record: &K::Record) -> Result<(), StoreError> {
        self.refuse_if_read_only()?;
        if !self.held_by_me(K::op_id(record)) {
            return Err(StoreError(format!(
                "op {} is not claimed by this process",
                K::op_id(record)
            )));
        }
        self.write_record(record)
    }

    fn release_claim(&self, op_id: &OpId) {
        self.held
            .lock()
            .unwrap_or_else(|p| p.into_inner())
            .remove(op_id);
    }
}

#[cfg(not(any(
    target_vendor = "apple",
    all(
        target_os = "linux",
        any(
            target_arch = "x86",
            target_arch = "x86_64",
            target_arch = "arm",
            target_arch = "aarch64",
            target_arch = "riscv64"
        )
    )
)))]
compile_error!("O_NONBLOCK's value isn't recorded for this target (crates/cli/src/state/mod.rs)");
