//! AP2 Provider limits only, the store and CLI half: the store stages 200
//! small files in one `add`, and the store's and the CLI's attachment
//! modules declare no count or size cap. The model's limits, the extension
//! table and the core's constants are proved in `openwiz-core`'s own
//! `attachment` target (`crates/core/tests/attachment/ap02_limits.rs`).

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
