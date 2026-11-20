use crate::{
    allowlist::{Invocation, ThreadId},
    process,
    source::CloudRoomSource,
};
use openwiz_core::{
    health::{
        is_openwiz_loop,
        model::{Id, Repository, SeenLoop},
    },
    source::SourceError,
};
use serde_json::Value;
use std::{collections::BTreeSet, time::Instant};
fn malformed() -> SourceError {
    SourceError::Malformed {
        detail: "loop list is not a complete, unambiguous loop inventory".to_owned(),
    }
}
pub fn recorded_fleet_loop(record: &str, thread: &Id) -> Result<Id, SourceError> {
    record
        .strip_prefix("launch-fleet: fleet thread ")
        .and_then(|s| s.split_once(", loop "))
        .filter(|(owner, _)| *owner == thread.as_str())
        .and_then(|(_, id)| Id::parse(id))
        .ok_or_else(|| SourceError::Unavailable {
            detail: "fleet record does not name one exact old thread and loop".into(),
        })
}
impl CloudRoomSource {
    pub fn pause_fleet_loop(
        &self,
        record: &str,
        thread: &Id,
        repository: &Repository,
        deadline: Instant,
    ) -> Result<Id, SourceError> {
        let id = recorded_fleet_loop(record, thread)?;
        let owned_paused = |rows: &[SeenLoop]| {
            rows.iter()
                .find(|row| row.id == id && is_openwiz_loop(&row.name, repository))
                .map(|row| row.paused)
        };
        match owned_paused(&self.health_loops(deadline)?) {
            Some(true) => return Ok(id),
            Some(false) => {}
            None => {
                return Err(SourceError::Unavailable {
                    detail: "recorded fleet loop is not owned by OpenWiz".into(),
                });
            }
        }
        let outcome = process::run(
            self.program(),
            &Invocation::LoopPause(ThreadId::parse(id.as_str()).map_err(|_| malformed())?),
            deadline,
        );
        if owned_paused(&self.health_loops(deadline)?) == Some(true) {
            return Ok(id);
        }
        outcome?;
        Err(SourceError::Unavailable {
            detail: "recorded fleet loop pause was not confirmed".into(),
        })
    }

    pub fn health_loops(&self, deadline: Instant) -> Result<Vec<SeenLoop>, SourceError> {
        let out = process::run(self.program(), &Invocation::LoopList, deadline)?;
        serde_json::from_slice::<openwiz_core::new_thread::read::StrictJson>(&out)
            .map_err(|_| malformed())?;
        let doc: Value = serde_json::from_slice(&out).map_err(|_| malformed())?;
        let rows = doc.as_array().ok_or_else(malformed)?;
        let mut ids = BTreeSet::new();
        rows.iter()
            .map(|row| {
                let id = row
                    .get("id")
                    .and_then(Value::as_str)
                    .and_then(Id::parse)
                    .ok_or_else(malformed)?;
                if !ids.insert(id.clone()) {
                    return Err(malformed());
                }
                Ok(SeenLoop {
                    id,
                    name: row
                        .get("name")
                        .and_then(Value::as_str)
                        .ok_or_else(malformed)?
                        .to_owned(),
                    paused: row
                        .get("paused")
                        .and_then(Value::as_bool)
                        .ok_or_else(malformed)?,
                })
            })
            .collect()
    }
    pub fn resume_loop(
        &self,
        id: &Id,
        repository: &Repository,
        deadline: Instant,
    ) -> Result<(), SourceError> {
        let rows = self.health_loops(deadline)?;
        let subject = rows
            .iter()
            .find(|row| row.id == *id && is_openwiz_loop(&row.name, repository))
            .ok_or_else(|| SourceError::Unavailable {
                detail: "loop is not owned by OpenWiz".to_owned(),
            })?;
        if !subject.paused {
            return Ok(());
        }
        let outcome = process::run(
            self.program(),
            &Invocation::LoopResume(ThreadId::parse(id.as_str()).map_err(|_| malformed())?),
            deadline,
        );
        let after = self.health_loops(deadline)?;
        if after
            .iter()
            .any(|row| row.id == *id && is_openwiz_loop(&row.name, repository) && !row.paused)
        {
            return Ok(());
        }
        outcome?;
        Err(SourceError::Unavailable {
            detail: "loop resume was not confirmed".to_owned(),
        })
    }
}

impl CloudRoomSource {
    pub fn health_thread_owned(
        &self,
        id: &Id,
        project: &Id,
        deadline: Instant,
    ) -> Result<bool, SourceError> {
        let thread = ThreadId::parse(id.as_str()).map_err(|_| malformed())?;
        let out = process::run(self.program(), &Invocation::ThreadShow(thread), deadline).map_err(
            |e| match e {
                SourceError::CommandFailed { ref detail, .. }
                    if detail == process::NOT_FOUND_LINE =>
                {
                    SourceError::NotFound {
                        subject: id.as_str().to_owned(),
                    }
                }
                other => other,
            },
        )?;
        serde_json::from_slice::<openwiz_core::new_thread::read::StrictJson>(&out)
            .map_err(|_| malformed())?;
        let doc: Value = serde_json::from_slice(&out).map_err(|_| malformed())?;
        let t = &doc["thread"];
        if t["id"].as_str() != Some(id.as_str())
            || t["projectId"].as_str() != Some(project.as_str())
        {
            return Err(SourceError::Unavailable {
                detail: "health target does not establish configured-project ownership".to_owned(),
            });
        }
        match t.get("archivedAt") {
            Some(Value::Null) => Ok(false),
            Some(Value::Number(n)) if n.as_u64().is_some() => Ok(true),
            _ => Err(SourceError::Malformed {
                detail: "health thread has no readable archive state".to_owned(),
            }),
        }
    }
}

pub struct ProjectMessenger<'a> {
    room: &'a CloudRoomSource,
    project: Id,
}
impl CloudRoomSource {
    pub fn project_messenger(&self, project: Id) -> ProjectMessenger<'_> {
        ProjectMessenger {
            room: self,
            project,
        }
    }
    pub fn archive_owned(
        &self,
        id: &Id,
        project: &Id,
        deadline: Instant,
    ) -> crate::archive::ArchiveOutcome {
        use crate::archive::ArchiveOutcome;
        match self.health_thread_owned(id, project, deadline) {
            Ok(true) => return ArchiveOutcome::AlreadyArchived,
            Ok(false) => {}
            Err(SourceError::NotFound { .. }) => return ArchiveOutcome::NotFound,
            Err(_) => {
                return ArchiveOutcome::NotRead {
                    words: "archive target does not establish configured-project ownership".into(),
                };
            }
        }
        let Some(thread) = ThreadId::parse(id.as_str()).ok() else {
            return ArchiveOutcome::NotRead {
                words: "invalid archive target".into(),
            };
        };
        let _call = process::run(self.program(), &Invocation::ThreadArchive(thread), deadline);
        match self.health_thread_owned(id, project, deadline) {
            Ok(true) => ArchiveOutcome::Archived,
            Ok(false) => ArchiveOutcome::NotArchived {
                words: "owned archive was not confirmed".into(),
            },
            Err(_) => ArchiveOutcome::Unconfirmed {
                words: "owned archive readback is unread".into(),
            },
        }
    }
}
impl ProjectMessenger<'_> {
    fn owned(
        &self,
        id: &openwiz_core::model::SessionId,
        deadline: Instant,
    ) -> Result<(), SourceError> {
        let id = Id::parse(&id.0).ok_or_else(|| SourceError::Unavailable {
            detail: "invalid service message target".into(),
        })?;
        self.room
            .health_thread_owned(&id, &self.project, deadline)
            .map(|_| ())
    }
}
impl openwiz_core::messaging::send::Messenger for ProjectMessenger<'_> {
    fn name(&self) -> &str {
        openwiz_core::messaging::send::Messenger::name(self.room)
    }
    fn tested_version(&self) -> &str {
        openwiz_core::messaging::send::Messenger::tested_version(self.room)
    }
    fn check_target_id(
        &self,
        id: &openwiz_core::model::SessionId,
    ) -> Result<(), openwiz_core::messaging::InvalidRequest> {
        self.room.check_target_id(id)
    }
    fn version(&self, deadline: Instant) -> Result<String, SourceError> {
        openwiz_core::messaging::send::Messenger::version(self.room, deadline)
    }
    fn read_target(
        &self,
        id: &openwiz_core::model::SessionId,
        deadline: Instant,
    ) -> Result<openwiz_core::messaging::effects::TargetRecord, SourceError> {
        self.owned(id, deadline)?;
        self.room.read_target(id, deadline)
    }
    fn tell(
        &self,
        id: &openwiz_core::model::SessionId,
        mode: openwiz_core::messaging::Mode,
        text: &str,
        deadline: Instant,
    ) -> openwiz_core::messaging::send::TellReply {
        if self.owned(id, deadline).is_err() {
            return openwiz_core::messaging::send::TellReply::NotStarted;
        }
        self.room.tell(id, mode, text, deadline)
    }
}
