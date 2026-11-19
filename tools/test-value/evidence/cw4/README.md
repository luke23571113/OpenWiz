# CW4: checks, proof and cli-agent, second pass

[Ledger](ledger.md): one row for each of the 290 tests in `tests/checks`,
`tests/proof`, `tests/cli-agent` and `tests/support/cloudroom_process_tests.rs`
(241 kept, 7 merged, 42 deleted). Base:
`9d8690064b17ecbb18ef0ca17ecda178e8bc113d`.

## Counter

`python3 -I tools/test-value/count.py <commit>` at the base
([count-before.txt](count-before.txt)) and at the head
([count-after.txt](count-after.txt)):

| Area | Before | After | Change |
| --- | ---: | ---: | ---: |
| `tests/checks` | 8,219 | 5,570 | -2,649 |
| `tests/proof` | 7,375 | 7,234 | -141 |
| `tests/cli-agent` | 7,151 | 7,106 | -45 |
| `tests/support` | 1,227 | 1,157 | -70 |
| `tests/fake-room-cli`, `tests/fake-gh`, `tests/fixture-entrypoints` | 1,227 | 1,227 | 0 |
| All test lines | 203,732 | 200,827 | -2,905 |
| Test share of tracked text | 36.06% | 35.71% | -0.35 points |

## Coverage

`measure.py checks proof` at the base (its own detached worktree and target
folder) and at the head, on the same machine and toolchain:
[before.json](before.json), [after.json](after.json),
[compare.txt](compare.txt). Tests 188 -> 143; size 22,294 -> 19,441 lines.

**One drop, `openwiz-core` -77:** all 77 lines are
`crates/core/src/messaging/sha256.rs` (per-file `cargo llvm-cov report`,
both runs). Only the deleted WizSkills plan-graph revision tests in
`plan_decisions_schema_conformance.rs` called `sha256_hex`, as a tool to hash
skill output, not to test it. The function's own behaviour keeps its keeper,
`crates/core/tests/attachment/sha256_stream.rs::sha256_stream_contracts_preserve_original_cases`
(known digests), in the core crate's own tests. No other crate changed.

**cli-agent is not measured.** Under instrumentation, the fixture binary that
`loop_plan::export_then_plan_shows_no_difference` starts with a cleared
environment writes `.profraw` files into the folder that test lists, so the
kit's instrumented run fails at the base (the plain run passes). The kit
never measures a red run. The two deleted cli-agent tests ran only
`openwiz ls --json` and `openwiz fleets --json` against recording traps
(`cp1_zero_call_traps_...`), which many kept cli-agent tests also run, and a
schema lint with no product code (`the_stubs_print_...`).

Rust 1.99.1, cargo-llvm-cov 0.9.1, three build jobs. Seconds are not compared.
