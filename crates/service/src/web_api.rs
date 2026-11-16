//! Same server implementation, stores, providers and guards as openwiz-server.
use openwiz_adapter_cloudroom::source::CloudRoomSource;
use openwiz_adapter_github::{decisions::GitHubDecisions, fleets::GitHubFleets, tickets::Tickets};
use openwiz_core::{messaging::record::SendStore, new_thread::record::NewThreadStore};
use openwiz_server::{
    Attaching, Config, Creating, Decisions, FleetAgents, Fleets, Plan, SendHost, Sending,
    SystemClock, WebRoot,
};
use openwiz_store::{AttachmentStore, FileStore, NewThreadFileStore, attachments::Df};
use std::{net::TcpListener, path::Path, sync::Arc};

pub fn start(
    root: &Path,
    listener: TcpListener,
    host: Option<SendHost>,
    web: WebRoot,
) -> Result<openwiz_server::Server, String> {
    // The service's explicit answer target also governs the embedded decisions
    // and cockpit reads. A failed configuration read remains unknown; it must
    // never fall back to a different thread from the process environment.
    let target = configured_target(root);
    let sends = root.to_owned();
    let sends_read = root.to_owned();
    let creates = root.to_owned();
    let creates_read = root.to_owned();
    let attaches = root.to_owned();
    let attaches_read = root.to_owned();
    let config = Config {
        allowed_host: host.as_ref().map(|h| h.as_str().to_owned()),
        web_root: Some(web),
        sending: Some(Sending {
            messenger: Arc::new(CloudRoomSource::from_path()),
            open_store: Arc::new(move || {
                Ok(Box::new(FileStore::open(&sends)?) as Box<dyn SendStore>)
            }),
            open_store_read_only: Arc::new(move || {
                Ok(FileStore::open_read_only(&sends_read)?
                    .map(|s| Box::new(s) as Box<dyn SendStore>))
            }),
            host: host.clone(),
        }),
        creating: Some(Creating {
            client: Arc::new(CloudRoomSource::from_path()),
            open_store: Arc::new(move || {
                Ok(Box::new(NewThreadFileStore::open(&creates)?) as Box<dyn NewThreadStore>)
            }),
            open_store_read_only: Arc::new(move || {
                Ok(NewThreadFileStore::open_read_only(&creates_read)?
                    .map(|s| Box::new(s) as Box<dyn NewThreadStore>))
            }),
            host: host.clone(),
        }),
        attaching: Some(Attaching {
            open_store: Arc::new(move || AttachmentStore::open(&attaches)),
            open_store_read_only: Arc::new(move || AttachmentStore::open_read_only(&attaches_read)),
            free_space: Arc::new(Df),
            host,
        }),
        ..Config::default()
    };
    openwiz_server::start_with_loop_switches(
        listener,
        config,
        Arc::new(CloudRoomSource::from_path()),
        Arc::new(SystemClock),
        Arc::new(|line| eprintln!("openwiz-server: {line}")),
        openwiz_server::ReadSources {
            plan: Some(Plan::with_program(openwiz_adapter_github::PROGRAM)),
            fleets: Some(Fleets {
                list: Arc::new(GitHubFleets::from_path()),
                detail: Arc::new(Tickets::from_path()),
                agents: Arc::new(FleetAgents(CloudRoomSource::from_path())),
            }),
            decisions: Some(Decisions {
                github: GitHubDecisions::from_path()
                    .with_settings(&root.join("service/config.json")),
                target,
            }),
        },
        openwiz_server::loops::installed(root),
    )
    .map_err(|_| "cannot start the embedded HTTP server".to_owned())
}

fn configured_target(root: &Path) -> Result<Option<String>, ()> {
    std::fs::read_to_string(root.join("service/config.json"))
        .map_err(|_| ())
        .and_then(|text| {
            crate::document::read(crate::document::Document::Config, &text).map_err(|_| ())
        })
        .and_then(|config| {
            config["orchestrator_thread"]
                .as_str()
                .map(str::to_owned)
                .ok_or(())
        })
        .map(Some)
}

#[cfg(test)]
#[path = "../../../tests/service/install_engine_target.rs"]
mod target_tests;
