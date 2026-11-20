use std::fmt;
use std::time::Instant;

use serde::Serialize;
use serde::de::{self, Deserialize, Deserializer, MapAccess, SeqAccess, Visitor};
use serde_json::Value;

use openwiz_core::source::SourceError;

use crate::allowlist::{Invocation, ThreadId};
use crate::process;
use crate::source::CloudRoomSource;

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum ArchiveOutcome {
    AlreadyArchived,
    Archived,
    NotFound,
    NotRead { words: String },
    NotArchived { words: String },
    Unconfirmed { words: String },
}

impl CloudRoomSource {
    pub fn archive_thread(&self, id: &ThreadId, deadline: Instant) -> ArchiveOutcome {
        match self.archived(id, deadline) {
            Ok(Some(true)) => return ArchiveOutcome::AlreadyArchived,
            Ok(Some(false)) => {}
            Ok(None) => return ArchiveOutcome::NotFound,
            Err(words) => return ArchiveOutcome::NotRead { words },
        }
        let call = process::run(
            self.program(),
            &Invocation::ThreadArchive(id.clone()),
            deadline,
        );
        match (self.archived(id, deadline), call) {
            (Ok(Some(true)), _) => ArchiveOutcome::Archived,
            (Ok(Some(false)), Ok(_)) => ArchiveOutcome::NotArchived {
                words: "thread archive exited 0, but thread show still shows it not archived"
                    .to_owned(),
            },
            (Ok(Some(false)), Err(e)) => ArchiveOutcome::NotArchived {
                words: format!("thread archive {e}; thread show still shows it not archived"),
            },
            (Ok(None), _) => ArchiveOutcome::Unconfirmed {
                words: "thread show no longer finds the thread after thread archive".to_owned(),
            },
            (Err(words), _) => ArchiveOutcome::Unconfirmed { words },
        }
    }

    fn archived(&self, id: &ThreadId, deadline: Instant) -> Result<Option<bool>, String> {
        match process::run(
            self.program(),
            &Invocation::ThreadShow(id.clone()),
            deadline,
        ) {
            Ok(out) => archived_at(&out, id).map(Some),
            Err(SourceError::CommandFailed { ref detail, .. })
                if detail.starts_with(process::NOT_FOUND_LINE) =>
            {
                Ok(None)
            }
            Err(e) => Err(format!("thread show {e}")),
        }
    }
}

fn archived_at(out: &[u8], id: &ThreadId) -> Result<bool, String> {
    serde_json::from_slice::<NoRepeatedKeys>(out)
        .map_err(|_| "thread show printed something that is not JSON, or a key twice".to_owned())?;
    let doc: Value =
        serde_json::from_slice(out).map_err(|_| "thread show is not JSON".to_owned())?;
    let Some(thread) = doc.get("thread").filter(|t| t.is_object()) else {
        return Err("thread show has no thread object".to_owned());
    };
    if thread.get("id").and_then(Value::as_str) != Some(id.as_str()) {
        return Err("thread show describes another thread".to_owned());
    }
    match thread.get("archivedAt") {
        Some(Value::Null) => Ok(false),
        Some(Value::Number(n)) if n.as_u64().is_some() => Ok(true),
        Some(_) => Err("thread show's archivedAt is neither a time nor null".to_owned()),
        None => Err("thread show has no archivedAt".to_owned()),
    }
}

struct NoRepeatedKeys;

impl<'de> Deserialize<'de> for NoRepeatedKeys {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        d.deserialize_any(NoRepeatedKeysVisitor)
    }
}

struct NoRepeatedKeysVisitor;

impl<'de> Visitor<'de> for NoRepeatedKeysVisitor {
    type Value = NoRepeatedKeys;

    fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("a JSON value with no key given twice")
    }

    fn visit_unit<E: de::Error>(self) -> Result<NoRepeatedKeys, E> {
        Ok(NoRepeatedKeys)
    }

    fn visit_bool<E: de::Error>(self, _: bool) -> Result<NoRepeatedKeys, E> {
        Ok(NoRepeatedKeys)
    }

    fn visit_i64<E: de::Error>(self, _: i64) -> Result<NoRepeatedKeys, E> {
        Ok(NoRepeatedKeys)
    }

    fn visit_u64<E: de::Error>(self, _: u64) -> Result<NoRepeatedKeys, E> {
        Ok(NoRepeatedKeys)
    }

    fn visit_f64<E: de::Error>(self, _: f64) -> Result<NoRepeatedKeys, E> {
        Ok(NoRepeatedKeys)
    }

    fn visit_str<E: de::Error>(self, _: &str) -> Result<NoRepeatedKeys, E> {
        Ok(NoRepeatedKeys)
    }

    fn visit_seq<A: SeqAccess<'de>>(self, mut seq: A) -> Result<NoRepeatedKeys, A::Error> {
        while seq.next_element::<NoRepeatedKeys>()?.is_some() {}
        Ok(NoRepeatedKeys)
    }

    fn visit_map<A: MapAccess<'de>>(self, mut map: A) -> Result<NoRepeatedKeys, A::Error> {
        let mut keys: Vec<String> = Vec::new();
        while let Some(key) = map.next_key::<String>()? {
            if keys.contains(&key) {
                return Err(de::Error::custom("a key given twice"));
            }
            map.next_value::<NoRepeatedKeys>()?;
            keys.push(key);
        }
        Ok(NoRepeatedKeys)
    }
}
