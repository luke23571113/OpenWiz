//! A private source directory and state directory for each test, outside
//! the repository, the store opened on it, and a faked free-space measure.
//! The store's part of `tests/attachments/bench.rs`, which the CLI proofs
//! keep.

#![allow(dead_code)]

use std::fs::{self, DirBuilder};
use std::os::unix::fs::{DirBuilderExt, PermissionsExt};
use std::path::{Path, PathBuf};
use std::sync::{Mutex, OnceLock};
use std::time::{SystemTime, UNIX_EPOCH};

use openwiz_core::model::Timestamp;
use openwiz_store::AttachmentStore;
use openwiz_store::attachments::FreeSpace;

/// The fixed time of every staging, unless a test moves it.
pub const T0: Timestamp = Timestamp(1_800_000_000_000);

/// Free space no test reaches.
pub const PLENTY: u64 = 1 << 50;

/// What every synthetic text file holds.
pub const CONTENT: &str = "SYNTHETIC-CONTENT, reply ok.\n";

pub const PNG: &[u8] = b"\x89PNG\r\n\x1a\n\0\0\0\x0dIHDR";

/// A synthetic file: `magic`, padded with `0x5a` to exactly `len` bytes.
pub fn padded(magic: &[u8], len: u64) -> Vec<u8> {
    let mut bytes = magic.to_vec();
    bytes.resize(usize::try_from(len).unwrap().max(magic.len()), 0x5a);
    bytes
}

/// Makes `dir` and any missing parents, each 0700, never the umask's mode
/// (the store refuses a state directory others can use).
fn private_dir_all(dir: &Path) {
    DirBuilder::new()
        .recursive(true)
        .mode(0o700)
        .create(dir)
        .expect("a private test directory");
}

/// This run's own directory, under the system's temporary directory, so
/// never inside the repository (the store would refuse it).
pub fn run_root() -> &'static Path {
    static ROOT: OnceLock<PathBuf> = OnceLock::new();
    ROOT.get_or_init(|| {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_or(0, |d| d.as_nanos());
        let root = std::env::temp_dir()
            .join("openwiz-store-attachments-tests")
            .join(format!("{}-{nanos}", std::process::id()));
        private_dir_all(&root);
        root
    })
}

/// A free-space measure that answers `free` and records where it was asked.
pub struct Free {
    pub free: u64,
    pub asked: Mutex<Vec<PathBuf>>,
}

impl Free {
    pub fn new(free: u64) -> Self {
        Self {
            free,
            asked: Mutex::new(vec![]),
        }
    }
}

impl FreeSpace for Free {
    fn free_bytes(&self, dir: &Path) -> Result<u64, String> {
        self.asked.lock().unwrap().push(dir.to_path_buf());
        Ok(self.free)
    }
}

/// A private source directory and state directory for one test.
pub struct Bench {
    pub root: PathBuf,
    pub sources: PathBuf,
    pub state: PathBuf,
}

impl Bench {
    pub fn new(test: &str) -> Self {
        let root = run_root().join(test);
        let _ = fs::remove_dir_all(&root);
        let sources = root.join("sources");
        private_dir_all(&sources);
        Self {
            state: root.join("state"),
            root,
            sources,
        }
    }

    /// Writes a source file the owner might choose.
    pub fn source(&self, name: &str, bytes: &[u8]) -> PathBuf {
        let path = self.sources.join(name);
        fs::write(&path, bytes).expect("write a source");
        path
    }

    pub fn store(&self) -> AttachmentStore {
        AttachmentStore::open(&self.state).expect("open the attachment store")
    }

    pub fn attachments(&self) -> PathBuf {
        self.state.join("attachments")
    }

    /// The names in `attachments/`, sorted.
    pub fn entries(&self) -> Vec<String> {
        let Ok(read) = fs::read_dir(self.attachments()) else {
            return vec![];
        };
        let mut names: Vec<String> = read
            .map(|e| e.unwrap().file_name().to_string_lossy().into_owned())
            .collect();
        names.sort();
        names
    }

    /// The attachment directories in `attachments/`.
    pub fn ids(&self) -> Vec<String> {
        self.entries()
            .into_iter()
            .filter(|n| !n.starts_with('.'))
            .collect()
    }
}

impl Drop for Bench {
    fn drop(&mut self) {
        if !std::thread::panicking() {
            // The staged copies are read-only; their directories are not.
            let _ = fs::remove_dir_all(&self.root);
        }
    }
}

/// The SHA-256 of a file, read whole: the tests' own check.
pub fn sha256_of(path: &Path) -> String {
    openwiz_core::messaging::sha256_hex(&fs::read(path).expect("read"))
}

/// Every file under `dir`, as paths relative to it, sorted.
pub fn walk(dir: &Path) -> Vec<String> {
    fn go(base: &Path, dir: &Path, out: &mut Vec<String>) {
        let Ok(read) = fs::read_dir(dir) else {
            return;
        };
        for entry in read {
            let path = entry.unwrap().path();
            out.push(
                path.strip_prefix(base)
                    .unwrap()
                    .to_string_lossy()
                    .into_owned(),
            );
            if fs::symlink_metadata(&path).unwrap().is_dir() {
                go(base, &path, out);
            }
        }
    }
    let mut out = Vec::new();
    go(dir, dir, &mut out);
    out.sort();
    out
}

/// The permission bits of a path, not following a symlink.
pub fn mode(path: &Path) -> u32 {
    fs::symlink_metadata(path).unwrap().permissions().mode() & 0o777
}
