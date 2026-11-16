//! AP2 Provider limits only, the store and CLI half: the store stages 200
//! small files in one `add`, and the store's and the CLI's attachment
//! modules declare no count or size cap. The model's limits, the extension
//! table and the core's constants are proved in `openwiz-core`'s own
//! `attachment` target (`crates/core/tests/attachment/ap02_limits.rs`).

use std::fs;
use std::path::Path;

use crate::support::*;

/// Phase 2: the store stages 200 small files and images in one `add`, each
/// under its own id. Nothing counts them.
#[test]
fn two_hundred_small_files_all_become_ready_in_the_store() {
    let bench = crate::bench::Bench::new("ap02_two_hundred");
    let paths: Vec<String> = (0..200)
        .map(|i| {
            let path = if i % 2 == 0 {
                bench.source(&format!("syn-ap02-{i:03}.txt"), TEXT)
            } else {
                bench.source(&format!("syn-ap02-{i:03}.png"), &padded(PNG, 64))
            };
            path.to_str().unwrap().to_owned()
        })
        .collect();
    let mut args = vec!["add", "--json"];
    args.extend(paths.iter().map(String::as_str));
    let run = bench.cli(&args);
    assert_eq!(run.code, 0, "{}", run.err);
    let json = run.json();
    assert_eq!(json["ready"].as_array().unwrap().len(), 200);
    assert!(json["failed"].as_array().unwrap().is_empty());
    assert_eq!(bench.ids().len(), 200);
}

/// Phase 2: the store's attachment module and the CLI's declare only these
/// constants: names, a buffer size, exit codes and schema ids. No count or
/// size cap.
#[test]
fn the_store_and_the_cli_add_no_cap() {
    for (file, allowed) in [
        (
            "crates/store/src/attachments.rs",
            &[
                "COPY_CHUNK_BYTES",
                // `Area`'s: the directory's name and what it is called.
                "DIR",
                "WHAT",
                "META",
                "PARTIAL_SUFFIX",
                "STAGING_LOCK",
                "ID_ATTEMPTS",
                // macOS caches the private probe's owner UID, not a limit (#1102).
                "PROCESS_OWNER",
                // An open flag's value, not a limit.
                "O_NONBLOCK",
                // The free-space measure: its program, arguments and header.
                "DF_ARGS",
                "DF_HEADER",
                "DF_PROGRAM",
                // B2 (ClosedWiz#15): the claims lock and the claim file.
                "CLAIMS_LOCK",
                "CLAIM",
                // Moved here from the CLI's list for #16 (B3) with this
                // reason (the orchestrator, 2026-10-31, #16 Q4): the three
                // attachment reports live in the store now (`report`), one
                // implementation for the CLI and the web server, so their
                // schema ids are defined here; the CLI re-exports them.
                "ADD_SCHEMA_ID",
                "LIST_SCHEMA_ID",
                "REMOVE_SCHEMA_ID",
            ][..],
        ),
        (
            "crates/cli/src/attachment.rs",
            &[
                "EXIT_ATTACHMENT_FAILED",
                "EXIT_ATTACHMENT_NOT_FOUND",
                "EXIT_ATTACHMENT_REFUSED",
                "EXIT_ATTACHMENT_STORE_UNAVAILABLE",
            ][..],
        ),
    ] {
        let text = fs::read_to_string(Path::new(ROOT).join(file)).unwrap();
        let mut found: Vec<String> = Vec::new();
        for line in text.lines() {
            let line = line.trim_start();
            let line = line
                .strip_prefix("pub(crate) ")
                .or_else(|| line.strip_prefix("pub "))
                .unwrap_or(line);
            for keyword in ["const ", "static "] {
                if let Some(rest) = line.strip_prefix(keyword) {
                    let ident: String = rest
                        .chars()
                        .take_while(|c| c.is_ascii_alphanumeric() || *c == '_')
                        .collect();
                    found.push(ident);
                }
            }
        }
        found.sort();
        let mut allowed: Vec<String> = allowed.iter().map(|s| (*s).to_owned()).collect();
        allowed.sort();
        assert_eq!(found, allowed, "{file}");
        for word in [
            "MAX_ATTACHMENTS",
            "ATTACHMENTS_MAX",
            "MAX_FILES",
            "TOTAL_BYTES",
            "MAX_BYTES",
        ] {
            assert!(!text.contains(word), "{file} names {word}");
        }
    }
}
