//! Test-only verified bundle and job injection. Production has no fixture settings.
#[path = "../../../tests/fixture-entrypoints/fixture.rs"]
mod fixture;

fn main() -> std::process::ExitCode {
    let bundle = fixture::Bundle::from_environment();
    let mut jobs = openwiz_service::scheduler::Scheduler::default();
    if let Some(path) = std::env::var_os("OPENWIZ_FIXTURE_JOB_LOG") {
        jobs.register(
            "synthetic-held-job",
            std::num::NonZeroU64::new(1).unwrap(),
            move || {
                use std::io::Write;
                use std::os::unix::fs::OpenOptionsExt;
                let mut file = std::fs::OpenOptions::new()
                    .append(true)
                    .create(true)
                    .mode(0o600)
                    .open(&path)
                    .unwrap();
                file.write_all(b"synthetic job started\n").unwrap();
                file.sync_all().unwrap();
                // Hold this run until the fixture process is killed. The runtime
                // must continue serving HTTP and local status while a job is held.
                loop {
                    std::thread::park();
                }
            },
        )
        .unwrap();
    }
    openwiz_service::dispatch_with_jobs(bundle.discovery(), jobs)
}
