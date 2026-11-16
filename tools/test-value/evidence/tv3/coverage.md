# TV3 coverage before and after (#805)

`measure.py` on one Linux sandbox, Rust 1.99.1, `cargo-llvm-cov` 0.9.1:
`before.json` is `proof` at the base (`f95a553`), `after.json` is `proof`
and `openwiz-core:inventory` (the 12 moved tests) at `ce2e063`, measured
together as the README says. Both were measured from a `git worktree`: see
"Run time" for why that matters.

```text
before: openwiz-tests:proof
after: openwiz-tests:proof, openwiz-core:inventory
tests: 125 -> 105 (-20)
size files: 26 -> 28 (+2)
size bytes: 557089 -> 545466 (-11623)
size lines: 14969 -> 14621 (-348)
coverage openwiz-adapter-cloudroom: 856/3221 (26.58%) -> 856/3221 (26.58%), covered +0
coverage openwiz-adapter-github: 0/4948 (0.00%) -> 0/4948 (0.00%), covered +0
coverage openwiz-cli: 507/9178 (5.52%) -> 507/9178 (5.52%), covered +0
coverage openwiz-core: 782/9035 (8.66%) -> 780/9035 (8.63%), covered -2
coverage openwiz-server: 0/6145 (0.00%) -> 0/6145 (0.00%), covered +0
coverage openwiz-service: 0/5276 (0.00%) -> 0/5276 (0.00%), covered +0
coverage openwiz-store: 0/3643 (0.00%) -> 0/3643 (0.00%), covered +0
coverage openwiz-terminal: 0/5093 (0.00%) -> 0/5093 (0.00%), covered +0
seconds: 15.3 -> 15.7 (not compared exactly)
drops: openwiz-core
```

## The `openwiz-core` drop: no line lost

The 2 lines are in `crates/core/src/ops.rs` (625 to 623 of 702 covered in
`cargo llvm-cov report`'s file summary). No behaviour went, and no line went
from covered to uncovered:

- **Line by line, nothing changed.** `cargo llvm-cov report --text` (every
  binary's profile merged into one view per line) lists the same 980 lines
  of `ops.rs` at the base and at the head, and every line has the same zero
  or non-zero count. `--show-missing-lines` gives the identical missing set
  at both: `159-162, 164-165, 169-173, 175-176, 178-179, 181, 195-196,
  201-204, 207, 281-289, 365-373, 533-538, 602-605, 607, 670, 705-708, 710,
  720, 726, 841-845, 961-967, 976-978`.
- **Where the 2 come from.** The head has one more binary,
  `openwiz-core`'s `inventory` test, with its own copy of every `ops.rs`
  function. Its 12 tests list through `ops::list` only, so its copies of the
  `show` and detail paths never run: for example the functions starting at
  lines 738, 867, 876, 878 and 879 had only executed instantiations at
  the base (two each) and gain one unexecuted one at the head. The file
  summary counts those unexecuted copies; the merged line view does not.
- **So the deletions caused none of it.** All 18 deleted tests' bugs are
  still caught (`keepers.log`), and the 4 merged tests' assertions are
  unchanged in their keeper.

## Run time

`seconds` is wall clock under libtest's parallel threads. The `proof`
target's is bounded by its 15-second read-timeout proof
(`p04_partial_failures::a_read_that_never_answers_is_stopped_after_15_seconds_and_not_retried`),
which this ticket keeps, so 20 fewer tests barely move it (15.3 s, then
15.7 s; the core target adds 0.5 s). Cutting it was not this ticket's to
do: it is the only proof of the adapter's fixed `READ_TIMEOUT`.

Measure both sides from the same checkout layout. In a plain clone (no
`.git/commondir`), the `openwiz-server` and `openwiz-cli` build scripts mark
themselves dirty on every build, so `the_release_build_prints_schema_valid_json`
rebuilds the release fixture (about 13 s) on every run; in a worktree it does
not. A head measured in the clone beside a base measured in a worktree read
34.0 s against 15.3 s for that reason alone.
