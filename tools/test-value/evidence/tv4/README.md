# TV4 (#806): the fleet group's evidence

The pilot group of the test-value campaign (spec #787), measured with the
kit (`tools/test-value/README.md`). The ledger is [ledger.md](ledger.md).

## Coverage before and after

- **Before:** `measure.py --json before.json fleet` on the pull request's
  base, `f95a553`, in a separate worktree.
- **After:** `measure.py --json after.json fleet
  openwiz-adapter-github:writes openwiz-adapter-cloudroom:fleet_reads
  openwiz-adapter-cloudroom:archive` on the branch: the old target and the
  three new crate targets the moved tests went to, in one coverage report.
- Same Linux aarch64 sandbox, Rust 1.99.1, `cargo-llvm-cov` 0.9.1. Run
  times are from that one machine.

[`compare.txt`](compare.txt):

```text
tests: 294 -> 280 (-14)
size files: 38 -> 40 (+2)
size bytes: 865194 -> 852252 (-12942)
size lines: 24109 -> 23718 (-391)
coverage openwiz-adapter-cloudroom: 1745/3221 (54.18%) -> 1745/3221 (54.18%), covered +0
coverage openwiz-adapter-github: 2163/4948 (43.71%) -> 2162/4948 (43.69%), covered -1
coverage openwiz-cli: 517/9178 (5.63%) -> 517/9178 (5.63%), covered +0
coverage openwiz-core: 5483/9047 (60.61%) -> 5483/9047 (60.61%), covered +0
coverage openwiz-store: 457/3643 (12.54%) -> 457/3643 (12.54%), covered +0
seconds: 58.0 -> 76.3 (not compared exactly)
drops: openwiz-adapter-github
```

(`openwiz-server`, `openwiz-service` and `openwiz-terminal` are 0 before
and after.)

### The one drop: no source line lost

`openwiz-adapter-github`'s one line is in
`crates/adapters/github/src/decisions.rs` (14 covered lines, then 13), and
no behaviour went with it:

- **Every line and region is covered the same.** `cargo llvm-cov report
  --lcov` on the two runs' saved profiles gives identical `DA` records for
  all 43,838 line records in the report, and the JSON report's segments for
  `decisions.rs` are identical.
- **One function, now in two builds.** `decisions::allows` ran 5,482
  times in the fleet binary before. After the move it runs 290 times in the
  fleet binary and 5,192 times in `crates/adapters/github/tests/writes.rs`,
  whose build of the crate has another crate hash (it is the package under
  test there, a dependency in the fleet binary). `--summary-only` counts
  the two copies as two functions, and that shifts one line in its count.
- So the drop is the move of `b3_writes.rs`, not a deletion. Moving it back
  would only restore the count.

## Size and time

14 `#[test]`s fewer in total (19 fewer in the fleet target, 5 more in
crate targets), 391 lines and 12.9 kB less test source. The run time is
not comparable: the after run is four targets, each with its own `cargo
test` start, against one before. The kit reports time outside its repeat
check. Size and count are exact.

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
| scout 4 | `a6_*` (36) | ISSUES | 2 cuts, 1 move (5 readers) | the vacuous-pass flag on `discovery_failure_fixture` (its parent runs it by exact name) | 0 |
| scout 5 | `b2_*`, `b3_*` (61) | ISSUES | 1 merge, 1 move | the source-grep cuts (kept: a safety rule the allowlist alone doesn't prove) | 1 (`b2_manual_merge_row_means_none` is not a duplicate: it reads another input) |
| scout 6 | `b4_*` (29) | ISSUES | 1 cut, 1 move | the `b4_record` move (needs `b4_fake.rs`), duplicates with ER6's tick tests (ER6 deletes those, so these stay) | 0 |
| scout 7 | `b5_*` without the executing tick (41) | ISSUES | the ledger rows | its cut ideas (ruling 1: the `b5_*` files stay unchanged) | 0 |

No-push check after the swarm: clean (no branch, comment or pull request
write by any helper).
