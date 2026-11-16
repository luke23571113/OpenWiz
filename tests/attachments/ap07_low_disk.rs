//! AP7 Low disk, the CLI's half and the real measure: `add` says "low disk"
//! and exits 5, free space that can't be measured stages nothing (fail
//! closed), and the real measure is `/bin/df`. The store's floor and its
//! `df` reader are proved in `openwiz-store`'s `attachments` target
//! (`crates/store/tests/attachments/ap07_low_disk.rs`).

use std::ffi::OsString;

use openwiz_core::attachment::FREE_DISK_FLOOR_BYTES;
use openwiz_store::attachments::{NoClaims, Staged};

use crate::bench::{Bench, Free, T0, Unmeasurable};
use crate::support::{PNG, padded};

#[test]
fn the_cli_says_low_disk_and_exits_5() {
    let bench = Bench::new("ap07_cli");
    let source = bench.source("syn-ap07-cli.png", &padded(PNG, 1_000));
    let args = [OsString::from("add"), source.clone().into_os_string()];
    let run = bench.cli_with(&args, T0, &Free::new(FREE_DISK_FLOOR_BYTES), &NoClaims);
    assert_eq!(run.code, 5, "{run:?}");
    assert!(run.out.contains("failed (low_disk)"), "{}", run.out);
    assert!(run.out.contains("less than 1 GiB free"), "{}", run.out);
    assert!(bench.ids().is_empty());
}

#[test]
fn free_space_that_cant_be_measured_stages_nothing() {
    let bench = Bench::new("ap07_unmeasurable");
    let source = bench.source("syn-ap07-unmeasured.png", &padded(PNG, 1_000));
    let store = bench.store();
    let error = store.stage(&source, T0, &Unmeasurable).unwrap_err();
    assert!(error.0.contains("free space"), "{error:?}");
    assert!(bench.ids().is_empty());

    let args = [OsString::from("add"), source.into_os_string()];
    let run = bench.cli_with(&args, T0, &Unmeasurable, &NoClaims);
    assert_eq!(run.code, 10, "{run:?}");
    assert!(run.out.contains("not staged"), "{}", run.out);
    assert!(bench.ids().is_empty());
}

#[test]
fn the_real_measure_is_bin_df_and_fails_closed() {
    use openwiz_store::attachments::{DF_ARGS, DF_PROGRAM, Df, FreeSpace, parse_df};
    assert_eq!(DF_PROGRAM, "/bin/df");
    assert_eq!(DF_ARGS, ["-P", "-k"]);
    let bench = Bench::new("ap07_real_measure");
    let store = bench.store();
    let free = Df
        .free_bytes(&bench.attachments())
        .expect("/bin/df measures the state volume");
    // The tests' own run of the same command, parsed the same way, agrees
    // within 1 GiB (other processes write meanwhile).
    let out = std::process::Command::new(DF_PROGRAM)
        .args(DF_ARGS)
        .arg(bench.attachments())
        .env_clear()
        .env("LC_ALL", "C")
        .output()
        .unwrap();
    assert!(out.status.success());
    let theirs = parse_df(&out.stdout).unwrap();
    assert!(
        free.abs_diff(theirs) < FREE_DISK_FLOOR_BYTES,
        "{free} vs {theirs}"
    );
    // A directory that isn't there: df fails, so nothing is measured.
    assert!(Df.free_bytes(&bench.root.join("syn-ap07-none")).is_err());
    // Staging through the real measure.
    let source = bench.source("syn-ap07-real.png", &padded(PNG, 1_000));
    assert!(matches!(
        store.stage(&source, T0, &Df).unwrap(),
        Staged::Ready(_)
    ));
}
