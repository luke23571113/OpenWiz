//! The loops watchdog's health job (LP4): one report-only pass that saves
//! its incidents before it posts their records and sends their Needs you.
pub mod loops;
mod records;
mod watchdog;

/// Trusted embedding supplies complete observations, including authoritative
/// failure-disable provenance when such a producer exists.
pub type WatchdogRead = dyn Fn(u64) -> loops::Evidence<Vec<loops::Observation>> + Send + Sync;
use crate::{
    document::{self, Document},
    state::State,
};
use openwiz_adapter_cloudroom::source::CloudRoomSource;
use openwiz_adapter_github::{process::Executor, tick::TickReads};
use openwiz_core::{
    health::model::*,
    messaging::{
        OpId,
        send::{self, SendRequest, Status},
        sha256_hex,
    },
    model::SessionId,
};
use serde_json::{Value, json};
use std::{
    path::{Path, PathBuf},
    sync::{Arc, Mutex},
    time::Instant,
};
pub struct Sources {
    pub room: CloudRoomSource,
    pub github: Executor,
}
impl Sources {
    /// Lazy App execution, pinned to this config. A missing key never falls
    /// back to the user's personal gh login or prevents local status startup.
    pub fn production(root: &Path, config: &Value) -> Self {
        let root = root.to_owned();
        let config = config.to_string();
        let client = Mutex::new(None::<crate::app::Client>);
        let github = Executor::supplied(Arc::new(move |call, deadline| {
            let unavailable = || openwiz_core::source::SourceError::Unavailable {
                detail: "health App request failed (details withheld)".into(),
            };
            let app = {
                let mut slot = client.lock().map_err(|_| unavailable())?;
                if slot.is_none() {
                    *slot = Some(
                        crate::app::Client::from_config(&root, &config)
                            .map_err(|_| unavailable())?,
                    );
                }
                slot.as_ref().unwrap().clone()
            };
            app.execute(call, deadline).map_err(|_| unavailable())
        }));
        Self {
            room: CloudRoomSource::from_path(),
            github,
        }
    }
}
pub struct Health {
    root: PathBuf,
    config: Value,
    state: Arc<Mutex<State>>,
    room: CloudRoomSource,
    github: Executor,
    watchdog: Arc<WatchdogRead>,
}
struct PassLock(std::fs::File);
impl Drop for PassLock {
    fn drop(&mut self) {
        let _ = self.0.unlock();
    }
}
impl Health {
    pub fn new(
        root: &Path,
        config: Value,
        state: Arc<Mutex<State>>,
        room: CloudRoomSource,
        github: Executor,
    ) -> Result<Self, String> {
        document::read(Document::Config, &config.to_string())?;
        Ok(Self {
            root: root.to_owned(),
            config: config.clone(),
            state,
            room,
            github,
            watchdog: watchdog::installed(root, &config),
        })
    }
    /// Supply an authoritative observer for an embedded service. This grants
    /// no scheduler/write authority; absent provenance remains Unknown.
    pub fn with_watchdog_source(mut self, source: Arc<WatchdogRead>) -> Self {
        self.watchdog = source;
        self
    }
    pub fn register(
        self: Arc<Self>,
        scheduler: &mut crate::scheduler::Scheduler,
        now: impl Fn() -> u64 + Send + Sync + 'static,
    ) -> Result<(), String> {
        let every =
            std::num::NonZeroU64::new(self.config["health"]["every_s"].as_u64().unwrap()).unwrap();
        scheduler
            .register("health", every, move || {
                if self.pass(now()).is_err() {
                    eprintln!("openwiz-service: health pass incomplete (details withheld)");
                }
            })
            .map_err(str::to_owned)
    }
    fn snapshot(&self) -> Result<Value, String> {
        Ok(self
            .state
            .lock()
            .map_err(|_| "health state is unavailable")?
            .snapshot()
            .clone())
    }
    fn change(&self, change: impl FnOnce(&mut Value) -> Result<(), String>) -> Result<(), String> {
        let mut state = self
            .state
            .lock()
            .map_err(|_| "health state is unavailable")?;
        let mut value = state.snapshot().clone();
        change(&mut value)?;
        state.save(value)
    }
    fn repository(&self) -> Repository {
        Repository::parse(
            self.config["repository"]["owner"].as_str().unwrap(),
            self.config["repository"]["name"].as_str().unwrap(),
        )
        .unwrap()
    }
    fn patch(&self, id: &str, change: impl Fn(&mut Value)) -> Result<(), String> {
        self.change(|v| {
            let mut found = false;
            for field in ["incidents", "watchdog_deliveries"] {
                if let Some(rows) = v.get_mut(field).and_then(Value::as_array_mut) {
                    for incident in rows.iter_mut().filter(|i| i["id"] == id) {
                        change(incident);
                        found = true;
                    }
                }
            }
            if !found {
                return Err("health incident disappeared".into());
            }
            Ok(())
        })
    }
    /// The watchdog pass: deliver what an earlier pass saved, save this
    /// pass's watchdog incidents and result, then deliver again.
    pub fn pass(&self, now: u64) -> Result<(), String> {
        let _lock = PassLock(records::lock(&self.root)?);
        let deadline = Instant::now() + openwiz_core::limits::RUN_BUDGET;
        let gh = TickReads::with_executor(self.github.clone());
        if !gh
            .repository(deadline)
            .map_err(|_| "health repository is unread")?
            .name
            .eq_ignore_ascii_case(&self.repository().to_string())
        {
            return Err("health repository does not match the service config".into());
        }
        let delivery_pending =
            self.flush_records(deadline)? | records::reconcile(&self.root, &self.github, deadline)?;
        let snapshot = self.snapshot()?;
        let repository = self.repository();
        let next_incident = snapshot["next_incident"].clone();
        let mut counter = 0;
        let mut new_id = || {
            counter += 1;
            OpId::parse(&sha256_hex(
                format!(
                    "openwiz.health.needs-you.v1\n{}\n{}\n{}\n{now}\n{counter}",
                    repository, self.config["service_issue"], next_incident
                )
                .as_bytes(),
            ))
            .unwrap()
        };
        let loop_observations = (self.watchdog)(now);
        self.change(|v| {
            v["incidents"] = json!([]);
            v["last_pass"] = json!({"at":now,"results":[],"fixes":[],"needs_you":[]});
            watchdog::apply(v, &snapshot, loop_observations, now, &mut new_id)
        })?;
        if self.flush_records(deadline)? || delivery_pending {
            return Err("health record or notification delivery remains unconfirmed; saved identities are retained".into());
        }
        Ok(())
    }
    fn flush_records(&self, deadline: Instant) -> Result<bool, String> {
        let mut pending = false;
        let snapshot = self.snapshot()?;
        let deliveries = snapshot
            .get("watchdog_deliveries")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default();
        let issue = Number::new(self.config["service_issue"].as_u64().unwrap()).unwrap();
        for i in &deliveries {
            let id = i["id"].as_str().unwrap();
            if i["needs_you"].is_null() {
                continue;
            }
            let Some(body) = records::frozen(
                &self.root,
                &format!("{issue}/{}", i["needs_you"]["op_id"]),
                &records::render(i, None)?,
            )?
            else {
                pending = true;
                continue;
            };
            if i["needs_you"]["comment"].is_null() {
                match records::post(&self.root, &self.github, issue, &body, deadline) {
                    Ok(comment) => {
                        self.patch(id, |v| v["needs_you"]["comment"] = json!(comment))?
                    }
                    Err(_) => {
                        pending = true;
                        continue;
                    }
                }
            }
            let first = body.lines().next().ok_or("missing health record line")?;
            let message = format!(
                "Needs you:{} Recorded on #{issue}.",
                first
                    .strip_prefix("**Needs you:**")
                    .ok_or("invalid notification record")?
            );
            let op = OpId::parse(i["needs_you"]["op_id"].as_str().unwrap())
                .map_err(|_| "invalid saved notification id")?;
            let store = openwiz_store::FileStore::open(&self.root)
                .map_err(|_| "health notification store unavailable")?;
            let mut request = SendRequest::new(
                SessionId(
                    self.config["orchestrator_thread"]
                        .as_str()
                        .unwrap()
                        .to_owned(),
                ),
                message,
                op,
            );
            request.budget = deadline.saturating_duration_since(Instant::now());
            let report = send::send(
                &self.room.project_messenger(
                    Id::parse(self.config["project"].as_str().unwrap()).unwrap(),
                ),
                &store,
                &openwiz_server::SystemClock,
                &request,
            );
            if !matches!(report,Ok(ref report) if matches!(report.status,Status::Queued|Status::Accepted))
            {
                pending = true;
            } else {
                self.change(|v| {
                    v["watchdog_deliveries"]
                        .as_array_mut()
                        .unwrap()
                        .retain(|row| row["id"] != i["id"]);
                    Ok(())
                })?;
            }
        }
        Ok(pending)
    }
}
