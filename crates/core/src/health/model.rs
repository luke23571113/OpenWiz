//! The kept health types: a GitHub number, a CloudRoom id, the configured
//! repository and one row of `room-cli loop list`. Data only: anything read
//! from outside goes through a hand-written strict reader first.

use std::fmt;
use std::num::NonZeroU64;

use serde::Serialize;

/// A GitHub issue's number (a spec's), or a comment's id: 1 or more.
pub type Number = NonZeroU64;

/// A CloudRoom id (a loop's or a thread's): 1 to 128 ASCII letters,
/// digits, `_` or `-`, not starting with `-` (the adapter's rule).
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize)]
#[serde(transparent)]
pub struct Id(String);

impl Id {
    /// The longest id there is.
    pub const MAX_LEN: usize = 128;

    /// `id`, only when it keeps the rule.
    pub fn parse(id: &str) -> Option<Self> {
        let valid = !id.is_empty()
            && id.len() <= Self::MAX_LEN
            && !id.starts_with('-')
            && id
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || b == b'_' || b == b'-');
        valid.then(|| Self(id.to_owned()))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

/// The repository the fleets run on, as the config names it.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Repository {
    owner: String,
    name: String,
}

impl Repository {
    /// `owner/name`, only when each keeps the config's rule: an owner is
    /// ASCII letters, digits and `-`, starting with a letter or digit; a
    /// name is ASCII letters, digits, `-`, `_` and `.`; neither is empty.
    pub fn parse(owner: &str, name: &str) -> Option<Self> {
        let owner_ok = owner
            .bytes()
            .next()
            .is_some_and(|b| b.is_ascii_alphanumeric())
            && owner
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || b == b'-');
        let name_ok = !name.is_empty()
            && name
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'-' | b'_' | b'.'));
        (owner_ok && name_ok).then(|| Self {
            owner: owner.to_owned(),
            name: name.to_owned(),
        })
    }
}

impl fmt::Display for Repository {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}/{}", self.owner, self.name)
    }
}

/// One loop in `room-cli loop list`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SeenLoop {
    pub id: Id,
    pub name: String,
    pub paused: bool,
}
