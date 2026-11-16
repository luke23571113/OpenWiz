# TV8 (#810): the attachments group's evidence

The attachments group of the test-value campaign (spec #787), measured with
the kit (`tools/test-value/README.md`) and following the pilot's method
(TV4, #806). The ledger is [ledger.md](ledger.md).

## What changed

- **Moved, 14 tests:** 7 that need only `openwiz-core` (AP1, AP2's model
  half, AP3, the readiness, retention and free-disk rules, the streaming
  SHA-256) to `crates/core/tests/attachment/`, and 7 that need only
  `openwiz-store` (AP4's durable steps and what is never ready, AP5's
  swapped source, AP7's floor and `df` reader) to
  `crates/store/tests/attachments/`. Both targets run under
  `rust:lib:openwiz-core` and `rust:lib:openwiz-store` (`cargo test -p
  <package>`), so CI's selection needs no new row. Each moved file passes
  P8(a)'s and M12's allowlist guards (run locally; CI runs both on every
  pull request), so no move was held back.
- **Cut:** 1 test, 1 sub-proof and 1 unrun script, each with a keeper
  checked by breaking the code it guarded ([keepers.txt](keepers.txt)); 1
  sub-proof merged into parity's table (three rows added).
- **Kept where it was:** 52 tests. Each one's reason is in its ledger
  row. In short, they run `openwiz attachment` through `openwiz-cli`, a
  child process or another program (`mkfifo`, `/bin/df`, the release
  `openwiz`), read several crates' sources, or need the shared schema
  checker and `serde_json`.
- **Not cut, though static:** the AP proof cases (the test rule keeps every
  AP case, static or slow) and AD8/AD11. A cut was made only where another
  test makes the same assertion.

## Coverage before and after

- **Before:** `measure.py --json before.json attachments` on the pull
  request's base, `20a5100`, in a separate worktree.
- **After:** `measure.py --json after.json attachments openwiz-core:attachment
  openwiz-store:attachments` on the branch, the old target and the two new
  ones together in one report.
- Same Linux aarch64 sandbox, Rust 1.99.1, `cargo-llvm-cov` 0.9.1.

[`compare.txt`](compare.txt):

```text
before: openwiz-tests:attachments
after: openwiz-tests:attachments, openwiz-core:attachment, openwiz-store:attachments
tests: 67 -> 66 (-1)
size files: 26 -> 34 (+8)
size bytes: 259813 -> 268121 (+8308)
size lines: 7235 -> 7479 (+244)
coverage openwiz-adapter-cloudroom: 0/3180 (0.00%) -> 0/3180 (0.00%), covered +0
coverage openwiz-adapter-github: 0/4948 (0.00%) -> 0/4948 (0.00%), covered +0
coverage openwiz-cli: 461/9360 (4.93%) -> 461/9360 (4.93%), covered +0
coverage openwiz-core: 789/9063 (8.71%) -> 789/9063 (8.71%), covered +0
coverage openwiz-server: 0/6140 (0.00%) -> 0/6140 (0.00%), covered +0
coverage openwiz-service: 0/5276 (0.00%) -> 0/5276 (0.00%), covered +0
coverage openwiz-store: 882/3643 (24.21%) -> 880/3643 (24.16%), covered -2
coverage openwiz-terminal: 0/5093 (0.00%) -> 0/5093 (0.00%), covered +0
seconds: 4.7 -> 16.6 (not compared exactly)
drops: openwiz-store
```

**The one drop, `openwiz-store` −2, is not a lost line.** It sits in
`crates/store/src/attachments.rs` (754 to 752 of 1150 in the JSON
summary). In `cargo llvm-cov report --text`, that file's merged line view is
the same before and after, line by line, whether each line is reached or
not: 729 lines reached, 347 not, in both. So the same lines run. The
summary also counts per instantiation. AP4's and AP5's test `Durability`
types now build the store's generic `stage_with` into the new
`openwiz-store` test binary instead of `openwiz-tests`, which is the likely
cause. A second after run on the same head gave the same 880 of 3643, so
it is not one of the kit's timing races either. No behaviour was removed: the only deleted test and sub-proof
assert what their keepers assert.

## Size, count and time

- **Tests:** 67 to 66 (one deleted; the others are in three targets now).
- **The shared folder `tests/attachments/`:** 25 files, 238,627 bytes and
  6,655 lines before; 20 files, 169,015 bytes and 4,651 lines after (−29%
  lines). The moved tests are 1,377 lines in `crates/core/tests/attachment/`
  and 803 lines in `crates/store/tests/attachments/`.
- **All of the group's test source,** as the kit counts it (every compiled
  file, the shared `tests/support/` modules included): 7,235 to 7,479 lines
  (+244). The crate targets can't use the shared `tests/support/`, so each
  carries its own copy of the synthetic bytes and the store's part of the
  bench (about 240 lines).
- **Run time:** 4.7 s to 16.6 s on the same machine, outside the kit's
  repeat check. The after time is three targets, each its own binary, and
  the kit's times vary between runs; this pull request claims no time
  saving.

## Keeper checks

Each cut names a keeper. Each break was applied alone in a scratch worktree
of the branch, then only the keeper was run, then the break was undone:
[`keepers.txt`](keepers.txt). 7 breaks, 7 keepers failed.

- **ap10's allowlist test** → AD11: a second `"--file"` beside
  `attachment_args`.
- **ap11_schema's checker sub-proof** → parity: an empty safe name, and a
  short hash, let through by the schema.
- **ap03's display-name sub-proof** → AP11's schema test: `display_name`
  serialized as the safe name.
- **`check_oldest_first.py`** → `ls_lists_ready_attachments_oldest_first`:
  the script's own two mutants (no sort; sort by id alone).
- **Withdrawn cut:** ap03's `serde_json` line (`"../x"` refused as a
  `SafeName`) was first to be covered by parity, but its break
  (`SafeName`'s serde path unchecked) passed parity, because the
  reference reader parses names itself. So the line stays, moved with ap03,
  through serde's own string reader, and it fails on that break.

## Helpers

None. The group is one folder (6,655 lines). I read every test whole
myself, and the keeper checks were 9 scripted runs in one worktree, so
a swarm would have added briefs and checks without covering a separate
slice. No helper was started, so there is no swarm to no-push check.
