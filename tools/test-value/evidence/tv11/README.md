# TV11 (#813): what remains of the service group's evidence

The service group of the test-value campaign (spec #787), after the engine
removals (#796, #797, #798, #800), measured with the kit
(`tools/test-value/README.md`) and following TV4's method (#806). The ledger
is [ledger.md](ledger.md); the keeper checks are [keepers.txt](keepers.txt).

## What changed

- **One placement helper, not seven.** Seven files carried their own copy
  of the ETXTBSY-safe fixture placement (`place`, `copier`, `placed`,
  `place_script`) and of its four proofs, with their FIFO harness, about 280
  lines each: `install_engine_app_support.rs`, `install_engine_reads.rs`,
  `l3_runner.rs`, `l5b_watchdog.rs`, `t2_process.rs`, `t4_setup.rs` and
  `t6_fixture.rs`. Each now loads the shared `tests/support/place.rs`
  (#811), whose writer proof lives in `tests/checks/support_proofs.rs`.
  One directory-destination proof stays, in `l3_runner.rs`, now testing the
  shared helper. `t6_fixture.rs` places compiled programs, so it writes their
  bytes and calls the shared `place` itself; its synthetic product copy now
  carries `tests/support/place.rs`, which the copied
  `install_engine_app_support.rs` includes. t6-update loads the helper twice
  (through `t6_fixture.rs` and `install_engine_app_support.rs`), so that one
  `mod` line allows `clippy::duplicate_mod`.
- **Cut:** `l3_capacity.rs::occupancy_is_sampled_once_per_pass`, the
  in-process copy of `install_engine_loops.rs`'s scheduled-process proof
  (same four statuses, same one read per pass; the keeper also checks the
  history and the spawn count), and `l4_relay.rs`'s wording pin on
  `contracts/fleet-tick.v1.md`.
- **Moved:** `t4_scheduler.rs`, `t4_paths.rs` and `l5_watchdog.rs` to
  `crates/service/tests/`, unchanged, under their old target names. Both
  allowlist guards pass with them there (P8(a)'s
  `allowlist_source_contracts_preserve_original_cases`, M12's
  `no_product_source_spells_an_excluded_flag_or_another_write`).
- **Manifest** (grant on #813, comment 6932060322): only the three moved
  targets' `path` values in `crates/service/Cargo.toml`; no target cut, no
  name changed. [targets.txt](targets.txt): `cargo metadata` lists the same
  19 `openwiz-service` targets at the base and on this branch, and
  `cargo test -p openwiz-service --no-run` builds them.

## Coverage before and after

- **Targets:** the group's 16, measured together: `openwiz-tests:service`
  and 15 `openwiz-service` targets (`t4-unit`, `t4-scheduler`, `t7-app`,
  `t4-reader`, `t4-paths`, `t4-service`, `l4-events`, `t6-update`,
  `l3-runner`, `l4b-intake`, `l5-watchdog`, `l5b-watchdog`, `l10-approval`,
  `l11-limits`, `l12-registration`). `l6-switches` reads `tests/loops/`:
  TV10's.
- **Before:** the base, `fe405cf`, in a separate worktree.
  **After:** this branch at `03e48d3`. Both with `RUST_TEST_THREADS=1`.
- Same Linux x86_64 sandbox, Rust 1.99.1, `cargo-llvm-cov` 0.9.1.

[`compare.txt`](compare.txt), without its sandbox `seconds` line (run time
is judged only from CI job durations, per the orchestrator's ruling on #787):

```text
tests: 319 -> 290 (-29)
size files: 51 -> 52 (+1)
size bytes: 804756 -> 727847 (-76909)
size lines: 21526 -> 19658 (-1868)
coverage openwiz-adapter-cloudroom: 2033/5619 (36.18%) -> 2033/5619 (36.18%), covered +0
coverage openwiz-adapter-github: 1995/4948 (40.32%) -> 1995/4948 (40.32%), covered +0
coverage openwiz-cli: 1562/6419 (24.33%) -> 1562/6419 (24.33%), covered +0
coverage openwiz-core: 3742/9032 (41.43%) -> 3742/9032 (41.43%), covered +0
coverage openwiz-server: 227/6140 (3.70%) -> 227/6140 (3.70%), covered +0
coverage openwiz-service: 4123/5297 (77.84%) -> 4124/5297 (77.86%), covered +1
coverage openwiz-store: 1680/3643 (46.12%) -> 1680/3643 (46.12%), covered +0
drops: none
```

The one size file more is `tests/support/place.rs`, which the group's
targets now read; it was already in the tree. The `+1` in `openwiz-service`
is not claimed as a gain: the kit's README names timing-dependent lines.

### Failed measures, all recorded

1. **Before, first try:** stopped at
   `t2_docs.rs::t2_documented_synthetic_server_uses_the_fixture_and_synthetic_inventory`
   ("cannot serve --web-root: it must be a directory with index.html"). A
   missing prerequisite, not this change: the kit lists the web export for
   tests that serve it. After `npm ci --ignore-scripts && npm run build` in
   `apps/web`, the before measure passed.
2. **After, first try (`0ce5115`):** 11 of t6-update's 38 tests failed with
   a `Utf8Error` at `t6_fixture.rs:27`. This change's own fault: the shared
   `place_script` takes text, and t6 places compiled programs. Fixed at
   `03e48d3` (bytes written, then the shared `place`); t6-update then passed
   38/38 on its own and in the measure.
3. **After, second try:** the shell passed the 16 target names as one
   argument (`measure.py: no test target …`); nothing was measured. Rerun
   with the names split; it passed.

## Where the kept tests live

Moved to the crate: the three targets above, which use only
`openwiz-service` and `std` and start no process. Every other kept test
stays in `tests/service/`, for one of these reasons:

- **It starts a process** (`Command::new`, `process::{`): P8(a) allows that
  only in named product files under `crates/`, so the file would trip it.
  `install_engine_app_support.rs`, `install_engine_loops.rs`,
  `install_engine_reads.rs`, `l10_approval.rs`, `l11_limits/runner.rs`,
  `l12_registration.rs`, `l3_runner.rs`, `l4_events.rs`, `l4b_auth.rs`,
  `l4b_composition.rs`, `l5b_observation.rs`, `l5b_watchdog.rs`,
  `t2_bundle_pair.rs`, `t2_docs.rs`, `t2_locate.rs`, `t2_process.rs`,
  `t4_service.rs`, `t4_setup.rs`, `t6_fixture.rs`, `t6_update.rs`,
  `t7_app.rs`, `t7_privacy.rs`, `t7_python.rs`, `t7_transport.rs`.
- **Its target includes such a file**, and a target moves whole:
  `l3_capacity.rs` and `l3_contract.rs` (l3-runner), `l4_relay.rs` and
  `l4_support.rs` (l4-events), `l4b_intake.rs` and `l4b_transport.rs`
  (l4b-intake), `l11_limits.rs` and `l11_limits/planner.rs` (l11-limits),
  `t4_unit.rs` (with `t4_setup.rs`), `t7_deadline.rs`, `t7_fake_gh.rs` and
  `t7_forms.rs` (t7-app), `install_engine_app.rs` (t6-update).
- **A product source names its path:** `install_engine_record_factory.rs`
  and `install_engine_target.rs` (`crates/service/src/update.rs`,
  `web_api.rs`) and `t7_transport.rs`
  (`crates/adapters/github/src/app.rs`) run as library unit tests through a
  `#[path]` in product code, outside this ticket's paths.
- **It crosses crates:** the `service` target (`main.rs` and the `t2_*`
  files) drives the CloudRoom adapter, the CLI and the server.
- **It trips a guard:** `t4_reader.rs` was moved, and both P8(a) and M12
  failed on it (`update is not the service JSON field`: its
  `kept_update_retains_the_old_running_build` indexes `status["update"]`), so it went back (W1-7 gap).

## Keeper checks

Each cut with a keeper was checked by breaking the code the cut test
guarded and running only the keeper ([keepers.txt](keepers.txt)):

- **occupancy:** the runner reads occupancy twice per pass. The keeper
  `install_engine_loops.rs::occupancy_is_sampled_once_in_each_fresh_scheduled_pass`
  failed (and the cut test, run as a control).
- **placement writer:** `place.rs` writes the program in-process. The keeper
  `tests/checks/support_proofs.rs::placing_a_program_leaves_no_writer_a_concurrent_fork_could_inherit`
  failed on its writer count (`left: 1, right: 0`). A first try of this
  break used `std::fs::copy`, which cannot read the FIFO, so the keeper
  failed on its timeout instead; it was redone with a plain read and write,
  so the keeper's own assertion is what fails.
- **directory destination:** `place.rs` without its directory check. The
  kept `l3_runner.rs::placing_onto_a_directory_destination_is_refused`
  failed.

The FIFO-harness self-tests (`the_fifo_proof_fails_…`,
`the_fifo_proof_reaps_…`) have nothing left to break: the harness copies
they tested are deleted. The wording pin has no behaviour to break.

## Size and time

29 test runs fewer (319 to 290) and 1,868 lines and 76,909 bytes less test
source in the measured targets. Outside them, the service library's unit
tests also stop running `install_engine_app_support.rs`'s four copied
proofs. No run time is claimed: the kit's `seconds` line is a sandbox
number, and run time is judged only from CI's job durations.

## Helpers

Five read-only scouts (Claude Code, Haiku 5.5, High, shared sandbox), one
slice of `tests/service/` each, at the base commit: each drafted one Catches
line per test from its assertions and listed overlaps. 297 lines were used
after reading, trimmed to their first sentence; the overlap leads gave one
cut (`occupancy_is_sampled_once_per_pass`, confirmed by a break) and one
already found (the wording pin). The rest were partial overlaps, each with
an assertion of its own, so they were kept, and one source-text check
(`t2_production_entrypoints_…`) guards the AGENTS.md rule that production
binaries have no fixture bypass, so it was kept too. No-push check: clean.
