//! The fleet tick's job name, sources and scheduler seam. The service no
//! longer registers the scheduled fleet tick (#796).
use crate::{scheduler::Scheduler, state::State};
use openwiz_adapter_cloudroom::source::CloudRoomSource;
use openwiz_adapter_github::process::Executor;
use serde_json::{Value, json};
use std::{
    num::NonZeroU64,
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, Ordering},
    },
};

pub const JOB: &str = "fleet-tick";

pub struct Sources {
    pub github: Executor,
    pub room: CloudRoomSource,
}

/// The scheduler and state seam used by fixture executors and controlled clocks.
/// The scheduler owns cadence and overlap; each invocation dispatches at most once.
pub fn register_with(
    scheduler: &mut Scheduler,
    every: NonZeroU64,
    state: Arc<Mutex<State>>,
    now: impl Fn() -> u64 + Send + Sync + 'static,
    execute: impl Fn() -> Result<(), String> + Send + Sync + 'static,
) -> Result<(), String> {
    register_with_control(scheduler, every, state, now, move |_| execute())
}

/// The stop flag belongs to the scheduler and is reset only after the old
/// handle has completed. An in-flight action keeps its durable outcome.
pub fn register_with_control(
    scheduler: &mut Scheduler,
    every: NonZeroU64,
    state: Arc<Mutex<State>>,
    now: impl Fn() -> u64 + Send + Sync + 'static,
    execute: impl Fn(Arc<AtomicBool>) -> Result<(), String> + Send + Sync + 'static,
) -> Result<(), String> {
    let stop = Arc::new(AtomicBool::new(false));
    let flag = Arc::clone(&stop);
    // If completion could not be persisted, retain it until the next schedule.
    // Repair that save before starting any new work; never replay the old run.
    let pending = Mutex::new(None::<Value>);
    let monitor = crate::scheduler::TickMonitor::default();
    let worker_monitor = monitor.clone();
    scheduler
        .register_tick(every, stop, monitor, move || {
            let result = (|| -> Result<(), String> {
                let mut pending = pending.lock().map_err(|_| "tick outcome unavailable")?;
                let started = now();
                {
                    let mut state = state.lock().map_err(|_| "tick state unavailable")?;
                    let mut value = state.snapshot().clone();
                    if let Some(ended) = pending.as_ref() {
                        value["tick"]["running"] = Value::Null;
                        value["tick"]["last_ended"] = ended.clone();
                        state.save(value.clone())?;
                        *pending = None;
                    }
                    if !value["tick"]["running"].is_null() {
                        return Err("previous tick outcome has not been saved".to_owned());
                    }
                    value["tick"]["running"] = json!({"started_at":started});
                    state.save(value)?;
                }
                let _run=worker_monitor.begin(started)?;
                let outcome = execute(Arc::clone(&flag));
                let ended = now().max(started);
                let mut state = state.lock().map_err(|_| "tick state unavailable")?;
                // Re-read under the lock: other jobs may have saved unrelated state.
                let mut value = state.snapshot().clone();
                value["tick"]["running"] = Value::Null;
                let ended = json!({
                    "started_at":started,"ended_at":ended,
                    "how":if flag.load(Ordering::SeqCst) { "stopped" } else if outcome.is_ok() { "finished" } else { "failed" }
                });
                value["tick"]["last_ended"] = ended.clone();
                *pending = Some(ended);
                state.save(value)?;
                *pending = None;
                outcome
            })();
            if result.is_err() {
                eprintln!("openwiz-service: scheduled fleet tick failed (details withheld)");
            }
        })
        .map_err(str::to_owned)
}
