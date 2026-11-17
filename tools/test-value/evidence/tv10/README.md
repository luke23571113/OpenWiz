# TV10 (#812): the loops group's evidence

The loops group of the test-value campaign (spec #787), measured with the
kit (`tools/test-value/README.md`), following TV4's method (#806). The
ledger is [ledger.md](ledger.md); the keeper checks are
[keepers.txt](keepers.txt).

## What changed

- **Moved:** the core planner's tables (LP1, LP2: `capacity.rs`,
  `deferred.rs`, `dispatch.rs`, `guards.rs`, `load.rs`, `missed.rs`,
  `schedules.rs`, and `main.rs`'s helpers) from `tests/loops/` to
  `crates/core/tests/loops/`, the core's own test target `loops`. They use
  only `openwiz-core` and `std`. Both allowlist guards (P8(a)'s
  `allowlist_source_contracts_preserve_original_cases`, M12's
  `no_product_source_spells_an_excluded_flag_or_another_write`) pass with them
  there.
- **Fixture split:** the service crate's `l6-switches` target
  (`tests/loops/l6_executor.rs`) included `l6_switches.rs` as its fixture
  module, so it ran that file's 6 tests a second time. The fixture now lives
  in `tests/loops/fixture.rs`, which has no tests; `l6_switches.rs` keeps its
  tests and `ExpiredClock`.
- **Cut:** `l6_api.rs::route_inventory_appends_exactly_the_two_local_switch_writes`
  (a copy of the route table's last two rows; its keeper checks the whole
  table) and `dispatch.rs::lp1_settled_outcomes_never_repeat_a_dispatch` (a
  proof whose 9 cases are all in `schedules.rs`'s once-occurrence proof,
  which also checks `Checking` and a revision change).

## Coverage before and after

- **Before:** `measure.py --json before.json loops openwiz-service:l6-switches`
  at the pull request's base, `20a5100`, in a separate worktree.
- **After:** `measure.py --json after.json loops openwiz-core:loops
  openwiz-service:l6-switches` on the branch: the old targets and the new one,
  measured together.
- Same Linux aarch64 sandbox, Rust 1.99.1, `cargo-llvm-cov` 0.9.1.

[`compare.txt`](compare.txt):

```text
before: openwiz-tests:loops, openwiz-service:l6-switches
after: openwiz-tests:loops, openwiz-core:loops, openwiz-service:l6-switches
tests: 42 -> 35 (-7)
size files: 13 -> 15 (+2)
size bytes: 111390 -> 110829 (-561)
size lines: 3512 -> 3480 (-32)
coverage openwiz-adapter-cloudroom: 23/3180 (0.72%) -> 23/3180 (0.72%), covered +0
coverage openwiz-adapter-github: 0/4948 (0.00%) -> 0/4948 (0.00%), covered +0
coverage openwiz-cli: 224/9360 (2.39%) -> 224/9360 (2.39%), covered +0
coverage openwiz-core: 478/9032 (5.29%) -> 478/9032 (5.29%), covered +0
coverage openwiz-server: 625/6140 (10.18%) -> 624/6140 (10.16%), covered -1
coverage openwiz-service: 415/5276 (7.87%) -> 415/5276 (7.87%), covered +0
coverage openwiz-store: 1174/3643 (32.23%) -> 1173/3643 (32.20%), covered -1
coverage openwiz-terminal: 0/5093 (0.00%) -> 0/5093 (0.00%), covered +0
seconds: 1.7 -> 5.7 (not compared exactly)
drops: openwiz-server, openwiz-store
```

### The two drops

- **`openwiz-server` −1: timing, not real.** The kit names the server's
  socket-read race lines under `loops` (#892). A second after run on the same
  head gave `openwiz-server: 625/6140 -> 625/6140, covered +0`.
- **`openwiz-store` −1: the doubled run that no longer exists.** It holds on
  rerun, all in `crates/store/src/loops/mod.rs` (150/151 → 149/151). The
  line-level report (`cargo llvm-cov report --text`) shows every line of that
  file executed both before and after. In the full JSON report, the file's
  functions have one copy per test binary. The `openwiz-tests` `loops`
  binary's copies run exactly as often as before: `SwitchError`'s
  `From<String>` 63, `From<&str>` 2, `Display` 56, and `Context::switch`'s
  closure at line 98 47 times. Only the service binary's copies of those four
  went from 29, 1, 30 and 30 runs to 0, because that binary no longer runs
  `l6_switches.rs`'s 6 tests a second time. The behaviour that no longer
  exists is that second run, not any product code path.

## Size and time

7 runs fewer (42 to 35): 6 doubled runs and 1 deleted test. 32 lines and
561 bytes less test source. Files go from 13 to 15: the new core entrypoint
`crates/core/tests/loops/main.rs` and `tests/loops/fixture.rs`. Run time went
from 1.7 s to 5.7 s (5.8 s on the rerun) on the same machine. The kit reports
time outside its repeat check, and it sums each target's plain `cargo test`,
so a third target adds its own start-up. The tests' own time is under a
second in every target. This pull request claims no time saving.

## Keeper checks

Each cut names a keeper, and each was checked by breaking the code the cut
test guarded and running only the keeper ([`keepers.txt`](keepers.txt)):

- **settled-redispatch:** the planner treats every non-`Checking` run as a
  dispatch candidate. The keeper
  `schedules.rs::lp1_once_occurrences_are_not_repeated_across_results_or_revisions`
  failed.
- **route-off-missing:** `POST /api/v1/loops/{name}/off` was removed from
  `ROUTES`. The keeper
  `tests/web-api/a4_no_mutation.rs::the_route_table_is_the_read_routes_the_send_and_the_create`
  failed.

## Helpers

None. The group is 13 files and 36 tests, which one reader covered
directly, so no swarm and no no-push check.
