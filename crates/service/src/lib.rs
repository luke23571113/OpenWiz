//! OpenWiz's PC service: a registered-job scheduler and the embedded HTTP API.
//! #269's approved exception permits this crate alone to depend on
//! openwiz-server. All HTTP routes and guards remain the server's own.
pub mod app;
pub mod bootstrap;
pub mod document;
pub mod events;
pub mod health;
pub mod loops;
pub mod paths;
pub mod runtime;
pub mod scheduler;
pub mod state;
pub mod tick;
pub mod update;
mod web_api;

/// Injected event entry point. Production transport belongs to #805.
pub use events::route_next as route_event;

use std::{path::PathBuf, process::ExitCode};

/// The commit the service programs were built from, never a guessed identity.
pub const BUILD: &str = env!("OPENWIZ_SERVICE_BUILD");
/// RL4 (#1148): this program's compiled product identity, one record (prefix,
/// canonical JSON, LF) in its read-only data; the build script writes the JSON
/// (contracts/release-candidate.v1.md, "Minimum product identity").
pub static PRODUCT: [u8; IDENTITY.len() + 20] = product_record(IDENTITY);
const IDENTITY: &str = match option_env!("OPENWIZ_PRODUCT_IDENTITY") {
    Some(json) => json,
    None => "",
};

const fn product_record<const N: usize>(json: &str) -> [u8; N] {
    let (prefix, json) = (b"OPENWIZ_PRODUCT_V1:", json.as_bytes());
    let mut record = [b'\n'; N];
    let mut at = 0;
    while at < N - 1 {
        record[at] = if at < 19 { prefix[at] } else { json[at - 19] };
        at += 1;
    }
    record
}

/// `--build-identity`: print the compiled identity and nothing else. It reads
/// no state or account, calls no `room-cli` and binds nothing. An unknown
/// identity refuses.
fn build_identity() -> std::process::ExitCode {
    use std::io::Write;
    // Past the 19-byte prefix: naming the prefix again would add a second record.
    if !IDENTITY.is_empty() && std::io::stdout().write_all(&PRODUCT[19..]).is_ok() {
        return std::process::ExitCode::SUCCESS;
    }
    eprintln!("build identity is unavailable");
    std::process::ExitCode::FAILURE
}

const HELP: &str = "openwiz-service: OpenWiz's PC service\n\nUsage: openwiz-service\n       openwiz-service status [--json]\n       openwiz-service --help\n\nReads service/config.json under the OpenWiz state directory. Serves the running\nbuild's web/ on loopback only. No jobs register until their own tickets land.\nStatus queries the private local socket; an absent service exits 1 with no JSON.\n";

/// The real program and the test-only example share every dispatch path.
pub fn dispatch(discovery: openwiz_adapter_cloudroom::locate::Discovery) -> ExitCode {
    dispatch_with_jobs(discovery, scheduler::Scheduler::default())
}

/// Registered jobs join the same process runtime. Production starts with none.
pub fn dispatch_with_jobs(
    discovery: openwiz_adapter_cloudroom::locate::Discovery,
    jobs: scheduler::Scheduler,
) -> ExitCode {
    dispatch_with_binder(discovery, jobs, openwiz_server::bind)
}

/// Explicit Rust injection for fixture programs; ordinary dispatch always uses
/// the configured loopback port. No CLI or environment setting selects a binder.
pub fn dispatch_with_binder(
    discovery: openwiz_adapter_cloudroom::locate::Discovery,
    jobs: scheduler::Scheduler,
    bind: impl FnOnce(u16) -> std::io::Result<std::net::TcpListener>,
) -> ExitCode {
    std::panic::set_hook(Box::new(|_| eprintln!("openwiz-service: internal error")));
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    if args == ["--build-identity"] {
        return build_identity();
    }
    if args == ["--update-build"] {
        println!("{BUILD}");
        return ExitCode::SUCCESS;
    }
    if args == ["--help"] || args == ["-h"] {
        print!("{HELP}");
        return ExitCode::SUCCESS;
    }
    let query = args == ["status"] || args == ["status", "--json"];
    if !args.is_empty() && !query {
        eprintln!("openwiz-service: usage: openwiz-service [status [--json] | --help]");
        return ExitCode::from(2);
    }
    let result = (|| -> Result<(), String> {
        let root =
            openwiz_store::default_state_dir(&|name| std::env::var_os(name)).map_err(|e| e.0)?;
        if query {
            let status = runtime::status(&root)?;
            if args.len() == 2 {
                println!("{status}");
            } else {
                println!(
                    "OpenWiz service: running\nBuild: {}\nSince: {}\nServer: 127.0.0.1:{}",
                    status["service"]["build"].as_str().unwrap(),
                    status["service"]["since"],
                    status["server"]["port"]
                );
            }
            return Ok(());
        }
        openwiz_adapter_cloudroom::locate::install(discovery)
            .map_err(|_| "discovery already configured".to_owned())?;
        let exe =
            std::env::current_exe().map_err(|_| "cannot locate the running build".to_owned())?;
        bootstrap::check(&exe)?;
        let web = exe
            .parent()
            .map(|p| p.join("web"))
            .unwrap_or_else(PathBuf::new);
        runtime::run_with_binder(&root, &web, BUILD, jobs, bind)
    })();
    match result {
        Ok(()) => ExitCode::SUCCESS,
        Err(why) => {
            eprintln!("openwiz-service: {why}");
            ExitCode::FAILURE
        }
    }
}

#[cfg(test)]
mod product_identity {
    #[test]
    fn the_compiled_record_is_this_programs_canonical_identity() {
        let json = std::str::from_utf8(&super::PRODUCT)
            .unwrap()
            .strip_prefix("OPENWIZ_PRODUCT_V1:")
            .and_then(|r| r.strip_suffix('\n'))
            .unwrap();
        let value: std::collections::BTreeMap<String, String> = serde_json::from_str(json).unwrap();
        assert_eq!(
            serde_json::to_string(&value).unwrap(),
            json,
            "canonical JSON"
        );
        let keys: Vec<_> = value.keys().map(String::as_str).collect();
        assert_eq!(keys, ["product", "schema", "source", "target", "version"]);
        assert_eq!(value["product"], "service");
        assert_eq!(value["schema"], "openwiz.product.v1");
        assert_eq!(value["version"], env!("CARGO_PKG_VERSION"));
    }
}
