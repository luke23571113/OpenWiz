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

/// #1089: an upload cancelled part way deletes its own folder while it
/// still holds its reservation (its staging ends), and another upload
/// measuring the room the stagings in progress still need can be looking
/// at that folder at that moment. The other upload must still stage:
/// before the fix it failed with a store error, which the web API answers
/// `500 store_unavailable`.
///
/// The cancelled staging is played here as another process's would be: a
/// folder whose reservation this test holds locked, then deletes, as the
/// staging's own clean-up does. The reservation is a FIFO only so the test
/// sees the moment the other upload is reading it (the full pipe drains)
/// and holds that read until the folder is gone: no sleep and no retry.
#[test]
fn an_upload_cancelled_while_another_reserves_room_never_fails_it() {
    use std::fs::{self, DirBuilder, OpenOptions};
    use std::io::{ErrorKind, Write};
    use std::os::unix::fs::{DirBuilderExt, OpenOptionsExt};
    use std::process::Command;
    use std::time::{Duration, Instant};

    use crate::bench::PLENTY;

    // O_NONBLOCK: 0x800 on Linux, 0x4 on macOS.
    const NONBLOCK: i32 = if cfg!(target_vendor = "apple") {
        0x4
    } else {
        0x800
    };
    // A reservation of zeros: any count of them reads as 0 bytes.
    const ZEROS: [u8; 4096] = [b'0'; 4096];

    let bench = Bench::new("ap07_cancelled_race");
    let store = bench.store();
    let cancelled = bench.attachments().join("att-syn1089cancelled");
    DirBuilder::new().mode(0o700).create(&cancelled).unwrap();
    let reserve = cancelled.join(".reserve");
    let made = Command::new("mkfifo")
        .arg(&reserve)
        .status()
        .expect("mkfifo");
    assert!(made.success(), "mkfifo failed");
    // Read and write, so it opens at once; it keeps the FIFO open for
    // writing, so the other upload's read waits for this test.
    let held = OpenOptions::new()
        .read(true)
        .write(true)
        .custom_flags(NONBLOCK)
        .open(&reserve)
        .unwrap();
    held.lock()
        .expect("hold the cancelled staging's reservation");
    let mut fill = &held;
    loop {
        match fill.write(&ZEROS) {
            Ok(_) => {}
            Err(e) if e.kind() == ErrorKind::WouldBlock => break,
            Err(e) => panic!("fill the reservation: {e}"),
        }
    }

    let bytes = padded(PNG, 1_000);
    let racing = std::thread::spawn(move || {
        store.stage_stream(
            "syn-1089-photo.png",
            1_000,
            &mut &bytes[..],
            T0,
            &Free::new(PLENTY),
        )
    });

    // The pipe has room again only once the racing upload has found the
    // reservation locked and is reading it.
    let deadline = Instant::now() + Duration::from_secs(20);
    loop {
        match fill.write(&ZEROS[..1]) {
            Ok(_) => break,
            Err(e) if e.kind() == ErrorKind::WouldBlock => {}
            Err(e) => panic!("watch the reservation: {e}"),
        }
        assert!(Instant::now() < deadline, "the racing upload never read");
        assert!(!racing.is_finished(), "the racing upload ended unread");
        std::thread::yield_now();
    }

    // The cancelled staging cleans up, still holding its reservation, then
    // lets go: the racing upload's read ends.
    fs::remove_dir_all(&cancelled).unwrap();
    drop(held);

    let staged = racing.join().unwrap();
    assert!(
        matches!(staged, Ok(Staged::Ready(_))),
        "the racing upload failed: {staged:?}"
    );
    assert_eq!(bench.ids().len(), 1, "{:?}", bench.entries());
}
