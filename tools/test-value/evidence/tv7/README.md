# TV7 (#809): the messaging group's evidence

The messaging group of the test-value campaign (spec #787), measured with
the kit (`tools/test-value/README.md`) and following the fleet pilot's method
(TV4, #806). The ledger is [ledger.md](ledger.md).

## Coverage before and after

- **Before:** `measure.py --json before.json messaging` on the pull
  request's base, `20a5100`, in a separate worktree.
- **After:** `measure.py --json after.json messaging openwiz-core:send_effects
  openwiz-store:state_dir` on this branch's tests (`f16a7b2`), also from a
  worktree: the old target and the two new ones the moved tests run in,
  measured together.
- Same Linux aarch64 sandbox, Rust 1.99.1, `cargo-llvm-cov` 0.9.1.

[`compare.txt`](compare.txt):

```text
before: openwiz-tests:messaging
after: openwiz-tests:messaging, openwiz-core:send_effects, openwiz-store:state_dir
tests: 189 -> 173 (-16)
size files: 28 -> 29 (+1)
size bytes: 395635 -> 383742 (-11893)
size lines: 11045 -> 10742 (-303)
coverage openwiz-adapter-cloudroom: 1053/3180 (33.11%) -> 1053/3180 (33.11%), covered +0
coverage openwiz-adapter-github: 0/4948 (0.00%) -> 0/4948 (0.00%), covered +0
coverage openwiz-cli: 1081/9360 (11.55%) -> 1081/9360 (11.55%), covered +0
coverage openwiz-core: 2175/9032 (24.08%) -> 2171/9032 (24.04%), covered -4
coverage openwiz-server: 0/6140 (0.00%) -> 0/6140 (0.00%), covered +0
coverage openwiz-service: 0/5276 (0.00%) -> 0/5276 (0.00%), covered +0
coverage openwiz-store: 1145/3647 (31.40%) -> 1135/3647 (31.12%), covered -10
coverage openwiz-terminal: 0/5093 (0.00%) -> 0/5093 (0.00%), covered +0
seconds: 8.1 -> 7.2 (not compared exactly)
drops: openwiz-core, openwiz-store
```

## The drops: one line, and its keeper

`drops:` names `openwiz-core` (4 lines) and `openwiz-store` (10). Line by
line, only one line went from covered to uncovered.

- **The method.** `cargo llvm-cov report --lcov` over each side's saved
  profiles merges every binary into one count per line. The covered lines of
  `crates/core/src` and `crates/store/src` are the same set at the base and
  at the head, except one.
- **The one line:** `crates/store/src/attachments.rs:1338`, the copy loop's
  `Ok(n) => piece.truncate(n)`, reached only when a staged file is longer
  than one copy piece. In this group only `b8_memory.rs`'s 1 to 25 MiB files
  reached it. The behaviour stays and has its keeper in the attachments
  group: `tests/attachments/ap04_ready.rs::each_step_is_durable_before_the_next_and_ready_comes_last`
  stages a file of three pieces and more. Breaking that line made the keeper
  fail ([`keepers.txt`](keepers.txt), `staging-short-read`).
- **The other 13 are the new binaries, not lost lines.** The per-file
  summaries differ in `crates/core/src/messaging/effects.rs` (77 to 73 of 80
  covered lines), `crates/store/src/lib.rs` (480 to 471 of 549) and
  `attachments.rs` (665 to 664 of 1150, the line above). The head has two
  more test binaries, `openwiz-core`'s `send_effects` and `openwiz-store`'s
  `state_dir`, each with its own copy of those crates' functions, and the
  moved tests run only some of them. The file summary counts the unexecuted
  copies; the merged line view shows no line lost. TV3 (#805) recorded the
  same effect for its move (`tools/test-value/evidence/tv3/coverage.md`).

## Size and time

16 `#[test]`s fewer (189 to 173), 303 lines and 11.9 kB less test source:
15 cut, 1 merged into its keeper, and 8 moved to their crates (the moved
files count in the after size: 29 files against 28).

Time: the target is about as fast as before: the measure's plain runs took
8.1 s and 7.2 s. Checked again by hand, the plain `cargo test -p
openwiz-tests --test messaging`, run twice on each side on a quiet machine,
each from a worktree, took 7.8 and 8.0 s at the base and 7.8 and 7.6 s at
the head (libtest's own times). The deleted tests were mostly cheap; the one
slow one, `b8`, ran beside slower real-time proofs, which all stay. A head
run from the plain clone took 20 s: in a clone without `.git/commondir` the
release fixture rebuilds on every run, as TV3 found, so compare times only
between worktrees. This pull request claims no time saving.

The after measure ran twice on the same tree: once from the plain clone
(beside the keeper breaks in another worktree) and once from a worktree.
Coverage, test count and size were identical; only the time differed
(31.2 s, then 7.2 s). `after.json` is the worktree run. The line view
above comes from the first run's profiles.

## Moves

Eight kept tests exercise one crate alone and moved next to it:

- `crates/store/tests/state_dir.rs` (target `openwiz-store:state_dir`): the
  six store-only M10 cases: the default state directory (with the relative
  `OPENWIZ_STATE_DIR` refusal merged in), the sync tripwires for records and
  directories, and the three repository refusals. Its run directory is under
  the system temp directory, as before: the target directory is inside the
  repository, where the store refuses every state directory, so the
  repository refusals would pass there for the wrong reason.
- `crates/core/tests/send_effects.rs` (target `openwiz-core:send_effects`):
  M5's core effects rule (the two-case wrapper, unchanged) and the core's
  no-I/O rule.

Both files pass the protected allowlist guards, `tests/proof/p08a_allowlist_static.rs`
and `tests/messaging/m12_allowlist.rs`, locally; neither guard was edited.
The tests that stay and why are under the ledger's "Where the kept tests
live".

## Keeper checks

Each deleted test names a keeper. For every cut whose guarded code can be
broken, it was broken in a scratch worktree and the keeper run alone:
[`keepers.txt`](keepers.txt).

- **13 breaks, 13 keepers failed:** the observed-sent receipt arm, the
  `not_reported` wait reason's name, send's tested version, a record's own
  `version_tested` trusted on replay, the help's `Live-tested:` line, an
  extra preview read, the lookup's no-record and other-target answers, the
  duplicate acknowledgement ignored, uncertain copies deleted, a body
  `target` key accepted, a store that falls back to nothing in flight, and
  the staging copy loop's short read.
- **By reading, not a break:** `m11::the_inventory_api_keeps_its_signatures`
  (a compiler re-check: a changed signature fails the build of every
  caller), `m16::only_the_preview_works_out_effects` (a source grep with no
  behaviour of its own; the behaviour, effects equal to send's, is its
  keeper's), and `b8`'s send of staged attachments (`ad01`'s same
  `send_with` path).
- **Proposed cuts withdrawn after reading** (kept, as their ledger rows
  say): `m01::the_cli_refuses_invalid_text_with_no_call` (the only test of
  invalid text through the CLI's exit 2 and from stdin), `m06`'s reconcile
  and metadata tests (the code stays, so a cut would drop real coverage),
  `m07::a_recorded_failure_is_returned_not_retried`,
  `m08::racing_on_one_op_id_with_different_texts_still_sends_once`,
  `m09::an_abandoned_record_is_recovered_by_the_duplicate_check_too` (the
  only test that the scan writes the abandoned record back as finished),
  `m10::a_state_directory_inside_a_repository_is_refused` (moved instead: it
  also covers a nested path and a symlinked repository),
  `m14::missing_op_id_value_must_not_swallow_check_and_dispatch`,
  `m16::a_preview_names_each_refusal`, `m18::many_new_op_ids_racing_on_one_send_make_at_most_one_tell`,
  `ad02` and every test of `m12` (the protected guard).

## Helpers

Six read-only scouts (Claude Code, Haiku 5.5, High; shared sandbox), each on
one slice of `tests/messaging/` at `20a5100`, each returning one line per
test (what it asserts, what it reaches, a verdict with a keeper, single
crate or not). I checked every item I used against the code and broke the
code for each keeper I relied on.

| Role | Slice | Result | Used | Ignored | Wrong |
| --- | --- | --- | --- | --- | --- |
| scout 1 | `m01`, `m02`, `m03`, `m06` to `m09` (30 tests) | ISSUES | the ledger rows | 6 cuts (kept: see above) | 2 (`m01`'s CLI refusal and `m09`'s abandoned record are not duplicates) |
| scout 2 | `m04`, `m05` (33) | ISSUES | 2 cuts, 1 move | the in-test trims | 0 |
| scout 3 | `m10`, `m11`, `m12`, `m15`, `b8`, `structure` (39) | ISSUES | 2 cuts, 7 moves | the `m12` cut (protected guard), the `m15` fold | 0 |
| scout 4 | `m13`, `m14` (28) | ISSUES | 3 cuts | the `m14` op-id cut | 0 |
| scout 5 | `m16`, `m17` (24) | ISSUES | 4 cuts | the `m16` refusal-wording cut | 0 |
| scout 6 | `m18`, `ad_send_attachments` (33) | ISSUES | 2 cuts | the `m18` race and `ad02` cuts | 0 |

The two `structure.rs` cuts (the schema wording pin and the no-default
source grep) are mine: scout 3 kept them for want of a keeper, and the
breaks above found one for each.

No-push check after the swarm: clean (no branch, comment or pull request
write by any helper).
