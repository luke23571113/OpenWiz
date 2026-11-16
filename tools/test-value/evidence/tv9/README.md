# TV9 (#811): the checks, cli-agent and support group's evidence

The group's tests measured with the kit (`tools/test-value/README.md`).
The ledger is [ledger.md](ledger.md); the keeper checks are
[keepers.txt](keepers.txt); the red run of the one new test is
[red-place.txt](red-place.txt).

## Coverage before and after

- **Targets:** `checks` and `cli-agent`, measured together. The support
  tests' other copies ran in other groups' targets; the one support file
  with product code under test, `cloudroom_process_tests.rs`, runs as the
  CloudRoom adapter's unit tests, which the kit cannot name as a target
  (gap, below).
- **Before:** the base, `20a5100`, failed its measure twice on the same
  flake: `tests/cli-agent/init.rs` hit "Text file busy" (ETXTBSY) starting a
  program it had just written, and a red run is never measured. So the
  before is the base plus only this pull request's placement fix,
  [before-fix.patch](before-fix.patch) (`tests/support/place.rs` and the
  six fixture lines that use it; no cut and no move), in a separate
  worktree. The compare then shows only this group's cuts and moves.
- **After:** this branch, the same two targets.
- Same Linux aarch64 sandbox, Rust 1.99.1, `cargo-llvm-cov` 0.9.1.

[`compare.txt`](compare.txt):

```text
before: openwiz-tests:checks, openwiz-tests:cli-agent
after: openwiz-tests:checks, openwiz-tests:cli-agent
tests: 210 -> 206 (-4)
size files: 36 -> 38 (+2)
size bytes: 797620 -> 809329 (+11709)
size lines: 21671 -> 21950 (+279)
coverage openwiz-adapter-cloudroom: 848/3180 (26.67%) -> 848/3180 (26.67%), covered +0
coverage openwiz-adapter-github: 1326/4948 (26.80%) -> 1326/4948 (26.80%), covered +0
coverage openwiz-cli: 2192/9360 (23.42%) -> 2192/9360 (23.42%), covered +0
coverage openwiz-core: 1477/9032 (16.35%) -> 1477/9032 (16.35%), covered +0
coverage openwiz-server: 0/6140 (0.00%) -> 0/6140 (0.00%), covered +0
coverage openwiz-service: 0/5276 (0.00%) -> 0/5276 (0.00%), covered +0
coverage openwiz-store: 276/3643 (7.58%) -> 276/3643 (7.58%), covered +0
coverage openwiz-terminal: 59/5093 (1.16%) -> 59/5093 (1.16%), covered +0
seconds: 225.4 -> 216.6 (not compared exactly)
drops: none
```

Coverage is the same in every crate: no drop to explain.

## Size, count and time

- **Tests in the group's targets:** 210 to 206. Six tests deleted in
  `checks` and one merged; the `schema.rs` test ran in both targets and now
  runs once; three support tests moved in from other targets; one new test.
- **Size:** the group's own compiled sources grow (36 to 38 files, +279
  lines), because `tests/support/forks.rs` and `real_time.rs` are now
  compiled into `checks` for their moved tests. Across `tests/` this pull
  request changes 17 files, +374 and -361 lines: the cuts, net of the
  placement helper and its proof.
- **Runs elsewhere:** each support test ran once per including target (from
  source: `schema.rs` has 12 include sites, `forks.rs` 4, `real_time.rs`
  3); each now runs once. Those targets were not measured here.
- **Time:** 225.4 s to 216.6 s on the same machine, the two runs one after
  the other; the kit reports time outside its repeat check. No time saving
  is claimed.

## Keeper checks

Each cut with a keeper was checked by breaking the code it guarded in a
scratch worktree and running the keeper alone ([keepers.txt](keepers.txt)):
11 breaks, 11 keepers failed. The two dependency-direction cuts were checked
the same way: a dependency pointing back is refused by Cargo itself. Two cuts
have nothing to break: the `SKILL.md` wording pin and the unreachable
directory destination.

## Helpers

Six read-only scouts (Claude Code, Haiku 5.5, High; shared sandbox), each on
one slice of the group at `20a5100`, each returning one line per test (what
it asserts, what it reaches, a duplicate if any, single-crate or not). I
checked every item I used against the code.

| Role | Slice | Result | Used | Ignored | Wrong |
| --- | --- | --- | --- | --- | --- |
| scout 1 | `fixture_scan.rs`, `limits.rs`, `public_tree.rs`, `evidence_outside_crates.rs` (22) | ISSUES | 4 cuts (fake gh merge, limits, ci-reads, on-disk evidence) | the scenario-assumption and GitHub-scenario metadata cuts (an AGENTS.md rule and the scanner's own refusals) | 0 |
| scout 2 | `plan_decisions_schema_conformance.rs`, `plan_links.rs` (29) | ISSUES | 1 cut (the SKILL.md wording pin) | the source-row, route-row and record-helper cuts (contract-to-schema drift guards and the record check's own planted breaks) | 2 (two keepers named a private repository's tests, which public CI never runs) |
| scout 3 | the other seven `checks` files (31) | ISSUES | 0 cuts (the dependency cuts are my own reading) | the `ci_selection.rs` cuts (its Python keeper runs in a workflow that is not a required check), the loops number cut (it checks the real schema) | 1 (`loops_schema_numbers_…` does test the contract's schema) |
| scout 4 | `github_token.rs`, `process.rs` (34) | ISSUES | the move reading for `r3_…` | the `process.rs` duplicate cuts (each keeps a JSON-mode exit or schema check its named keeper lacks, or names a keeper ER6 deletes) | 0 |
| scout 5 | the other six `cli-agent` files (27) | ISSUES | 0 cuts | the `ui.rs` cuts (#776 removes the file), the catalogue "source mirroring" cuts (the catalogue is the agents' contract) | 0 |
| scout 6 | `tests/support/` (12) | ISSUES | 2 cuts (the polling merge, the directory case), the include sites | the collector and held-process cuts (their keepers are service tests a later group may cut) | 0 |

No-push check after the swarm: clean (no branch, comment or pull request
write by any helper).

## Gaps

- **The adapter's unit tests are not in the measure:** `measure.py` names
  only `[[test]]` targets, and `cloudroom_process_tests.rs` runs in the
  CloudRoom adapter's lib test. Its two cuts are a merge into a test that
  asserts the same 5 ms, and a fixture case no caller reaches; neither
  touched product code. They ran green locally
  (`cargo test -p openwiz-adapter-cloudroom --lib`).
- **No test moved into a crate (W1-7):** none of the kept tests exercises
  one crate alone; see the ledger's "Where the kept tests live". No allowlist
  guard was involved.
