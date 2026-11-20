use std::fmt;
use std::num::NonZeroU64;

use serde::Serialize;

pub type Number = NonZeroU64;

#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize)]
#[serde(transparent)]
pub struct Id(String);

impl Id {
    pub const MAX_LEN: usize = 128;

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

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Repository {
    owner: String,
    name: String,
}

impl Repository {
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

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SeenLoop {
    pub id: Id,
    pub name: String,
    pub paused: bool,
}
