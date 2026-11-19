# CW11 (#1152): CI's own tests, second pass

The bolder rule (`tools/test-value/README.md`, from CW1 #1142) over every test
in CI's own suites at the base `e817c9a`: the test files under `ci/` (but
`ci/wizroom/`), under `.github/actions/`, and `.github/workflows/ci.test.mjs`.
The [ledger](ledger.md) has one row for each of the base's 743 tests and shell
cases: 572 kept, 171 deleted, none moved or merged.

CI's job graph and selection safety stay guarded: every selector, planner,
gate, receipt, shard exactly-once, fork-routing and pinned-setup case stays.

## What went

- **Observation and unreachable admission (main-batch):** `shadow.py`'s
  capture and reconcile are non-authoritative, and `admit.py` has no supported
  mechanism and no caller. 50 of their 54 tests went. Four owning tests stay:
  per-push full CI with no mechanism, refusal of claimed switch authority, and
  the two that keep the shadow steps from touching `ci`'s required result. The files stay because `run.py`, `plan.py` and
  `ci/shard/lanes.tsv` register them, and a suite with no test exits 5.
- **An unrun file:** `ci/test_rust_tests.py`. No workflow, script or registry
  runs it.
- **The unused `--alongside` path** of `ci/rust-tests.sh` (no CI caller passes
  it), `--can-run-at-once` (run time only) and the test-thread count. The two
  kept failure cases now call the runner as CI does, without `--alongside`:
  the release lane's `release:ci-runner` drops from about 93 s to under 1 s.
- **Run time and balance:** shard balance quality, the timing table builder
  (`shard.py times`, run by hand), cache partitions, timeouts, first-member
  steps and build scope.
- **Mutation proofs of the tests themselves:** `test_pick.py` and
  `test_trace.py`'s planted breaks. Each break was run at the base against the
  kept cases first: every one is caught by a kept case ([keepers.txt](keepers.txt)).
- **Copied inventories and pins:** per-suite registration cases, `planted.py`'s
  case table, retry flags, the pins consistency check, historical workflow
  bytes.
- **No subject:** the checkout's private-blob proofs. OpenWiz tracks no
  `private/` file and is public. The prune, the sparse-checkout pin and the
  skip proof stay.
- **Setup robustness and usage errors:** APT source handling, architecture and
  argument refusals. Fatal APT update, signature and install failures stay.

Fixtures read only by deleted tests went with them:
`ci/main-batch/fixtures/shadow/github.json` and `ci-before.sha256`, with their
rows in `tools/open-import/paths.json`. The shadow red logs were never read by
a test; they are left for CW19 (#1160).

## Test lines (the counter)

`python3 -I tools/test-value/count.py <commit>`; full results in
[count-before.json](count-before.json) and [count-after.json](count-after.json).

| Area | Before (`e817c9a`) | After | Change |
| --- | ---: | ---: | ---: |
| `ci/` | 3,353 | 2,245 | −1,108 |
| `.github/` | 2,144 | 1,889 | −255 |
| All test lines | 193,452 | 192,089 | −1,363 |
| Share of tracked lines | 36.23% | 36.06% | −0.17 points |

The counter's classifier does not see `test.sh` or `test.py` files. All lines
of this pass's files (`wc -l`), including those and the two deleted fixtures:
8,545 before, 6,107 after (−2,438).

## Coverage

- **The kit's measure (`measure.py`)** runs `cargo test` targets and measures
  Rust crates only. No CI test is one of its targets, so its numbers can't
  change; it was not rerun.
- **CI's Python modules, under CI's Python tests:** the standard library's
  `trace` module ([coverage.py](coverage.py), no dependency), each of the 17
  (base) or 16 (head) Python test files in its own interpreter, same sandbox,
  Python 3.11. It counts lines run in-process only, on both sides alike:
  scripts the tests start as subprocesses don't count. Every suite passed.
  [Before](coverage-before.json): 2,298 of 4,003 lines.
  [After](coverage-after.json): 1,776 of 2,669 lines. Every lost line is in
  [coverage-compare.txt](coverage-compare.txt), explained here:
  - `ci/main-batch/shadow.py` (347) and 11 `admit.py` refusal lines: the
    non-authoritative observation and the unreachable admission above.
  - `.github/actions/docs-only/run.py` (60), `ci/shard/lanes.py` (21),
    `ci/shard/shard.py` (33), `tools/collector/required.py` (42): import-time
    lines only, reached through `shadow.py`'s imports. `run.py` and `shard.py`
    still run as subprocesses in the kept execution, lane and shard tests.
  - `ci/escapes/escapes.py` L134, L197, L209: the deleted schema-keyword check,
    and two schema branches only the deleted main-batch plans reached.
    Duplicate items are still refused by rules 6, 8 and 9 (kept
    `Plans::test_every_invalid_plan_is_refused_for_its_reason`).
  - `ci/select/map.py` L50-51, `resolve.py` L266 and L286, `trace.py` L158,
    `units.py` L77: reached only inside the deleted mutation proofs' broken
    copies (compiled under the real file names). No assertion checked these
    lines on the real code before or after.
- **Shell suites** (`test.sh`, `test_rust_runner.sh`, `ci/hosted/test.sh`)
  have no line-coverage tool here. Each deleted case names its keeper or why
  it is gone in the ledger. Ok-case counts: `test.sh` (with the runner suite
  it calls) 517 to 372; `test_rust_runner.sh` 170 to 43; `ci/hosted/test.sh`
  98 to 71.

## New tests

No new test: this pass only deletes. The two runner cases that lost the unused
`--alongside` argument keep their assertions.

## Gaps

- `ci/main-batch/README.md` still names the two deleted shadow fixtures. It
  is outside this ticket's owned paths.
- `ci/rust-tests.sh`'s main-only skips (only a pull request to main skips four
  proofs) have no running test, as before this pass: the deleted file never
  ran in CI.
