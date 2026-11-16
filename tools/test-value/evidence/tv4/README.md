# TV4 (#806): the fleet group's evidence

The pilot group of the test-value campaign (spec #787), measured with the
kit (`tools/test-value/README.md`). The ledger is [ledger.md](ledger.md).

## Coverage before and after

- **Before:** `measure.py --json before.json fleet` on the pull request's
  base, `f95a553`, in a separate worktree.
- **After:** `measure.py --json after.json fleet` on the branch. No test
  moved (below), so the after run is the same one target.
- Same Linux aarch64 sandbox, Rust 1.99.1, `cargo-llvm-cov` 0.9.1.

[`compare.txt`](compare.txt):

```text
before: openwiz-tests:fleet
after: openwiz-tests:fleet
tests: 294 -> 280 (-14)
size files: 38 -> 38 (+0)
size bytes: 865194 -> 849440 (-15754)
size lines: 24109 -> 23624 (-485)
coverage openwiz-adapter-cloudroom: 1745/3221 (54.18%) -> 1745/3221 (54.18%), covered +0
coverage openwiz-adapter-github: 2163/4948 (43.71%) -> 2163/4948 (43.71%), covered +0
coverage openwiz-cli: 517/9178 (5.63%) -> 517/9178 (5.63%), covered +0
coverage openwiz-core: 5483/9047 (60.61%) -> 5483/9047 (60.61%), covered +0
coverage openwiz-server: 0/6145 (0.00%) -> 0/6145 (0.00%), covered +0
coverage openwiz-service: 0/5276 (0.00%) -> 0/5276 (0.00%), covered +0
coverage openwiz-store: 457/3643 (12.54%) -> 457/3643 (12.54%), covered +0
coverage openwiz-terminal: 0/5093 (0.00%) -> 0/5093 (0.00%), covered +0
seconds: 58.0 -> 74.0 (not compared exactly)
drops: none
```

Coverage is the same in every crate: no drop to explain.

## Size and time

14 `#[test]`s fewer (294 to 280), 485 lines and 15.8 kB less test
source, in the same 38 compiled files. Run time went from 58.0 s to 74.0 s on the same machine; the kit
reports time outside its repeat check, and the target's time is mostly its
real-time proofs (timeouts and hung reads), which all stay. This pull
request claims no time saving.

## Moves held back (W1-7 gap)

Five kept tests exercise one crate alone and run no program:
`a6_reads.rs::cloudroom_read_contracts_preserve_original_cases`,
`b3_writes.rs`'s three tests and
`b4_archive.rs::the_archive_is_built_in_exactly_its_one_shape`. Moved to
`crates/adapters/{cloudroom,github}/tests/`, they failed CI's protected
allowlist guards, `tests/proof/p08a_allowlist_static.rs`
(`allowlist_source_contracts_preserve_original_cases`) and
`tests/messaging/m12_allowlist.rs`
(`no_product_source_spells_an_excluded_flag_or_another_write`): both read
every file under `crates/` as product source, and these tests spell the
flags and words those guards refuse there (`delete`, `--work-status`,
`archive`). So they stay in `tests/fleet/` until the guards skip
`crates/*/tests/`, which is the orchestrator's question; no guard is
edited here.

## Keeper checks

Each cut test names a keeper. For the cuts whose keeper is a different
test, the code the cut test guarded was broken in a scratch worktree, and
the keeper run alone: [`keepers.txt`](keepers.txt).

- **9 breaks, 9 keepers failed:** both dispatch arms, `fleet`'s help
  section, the fake `gh`'s `extends` and `hang`, the no-checks
  diagnostic's branch check, the `cloud thread-workspace` and `thread
  archive` argv, and a write form.
- **1 cut withdrawn:** for `a3_fake_gh.rs::it_answers_byte_for_byte`, two
  breaks of the fake's output (ESC bytes dropped; JSON re-serialized)
  passed every keeper tried, so it stays, kept.
- **Not broken, by reading:** `a4_edges.rs::closed_merge_both_facts_fail_discovery`
  (the reader's `merge.is_some() || merged_at.is_some()` is fully reached
  by the two one-fact keepers), `a7_scale_unbounded_transport_count` (its
  run and both assertions are the keeper's fast form), the three compiler
  re-checks of `a3_seams.rs` (a build failure fails every keeper), and the
  fake's `PATH` and no-scenario tests (the keepers' call logs).

## Helpers

Seven read-only scouts (Claude Code, Haiku 5.5, High; shared sandbox), each
on one slice of `tests/fleet/` at `f95a553`, each returning one line per
test (what it asserts, how it reaches the code, red flags, duplicates). I
checked every item I used against the code.

| Role | Slice | Result | Used | Ignored | Wrong |
| --- | --- | --- | --- | --- | --- |
| scout 1 | `a3_*`, `al1_titles`, `lock_release`, `c10_*` (29 tests) | ISSUES | 8 cuts | 5 cut ideas (`a3_commands`' help test; the fake's byte-for-byte and malformed-scenario tests; `a3_model`'s checker tests, kept as the oracle's own proofs) | 0 |
| scout 2 | `a4_*` (45) | ISSUES | 2 cuts | 3 move ideas (`a4_allowlist`, the `a7` batch tests: they share `batch_argv` or need the fake `gh`) | 0 |
| scout 3 | `a5_*` (36) | ISSUES | 2 cuts | the small-world baseline cut and the near-twin merges | 0 |
| scout 4 | `a6_*` (36) | ISSUES | 2 cuts (its move held back) | the vacuous-pass flag on `discovery_failure_fixture` (its parent runs it by exact name) | 0 |
| scout 5 | `b2_*`, `b3_*` (61) | ISSUES | 1 merge (its move held back) | the source-grep cuts (kept: a safety rule the allowlist alone doesn't prove) | 1 (`b2_manual_merge_row_means_none` is not a duplicate: it reads another input) |
| scout 6 | `b4_*` (29) | ISSUES | 1 cut (its move held back) | the `b4_record` move (needs `b4_fake.rs`), duplicates with ER6's tick tests (ER6 deletes those, so these stay) | 0 |
| scout 7 | `b5_*` without the executing tick (41) | ISSUES | the ledger rows | its cut ideas (ruling 1: the `b5_*` files stay unchanged) | 0 |

No-push check after the swarm: clean (no branch, comment or pull request
write by any helper).
