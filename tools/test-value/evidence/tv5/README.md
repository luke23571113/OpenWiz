# TV5 (#807): the web-api group's evidence

The web-api group of the test-value campaign (spec #787), measured with the
kit (`tools/test-value/README.md`). The ledger is [ledger.md](ledger.md).

## Coverage before and after

- **Before:** `measure.py --json before.json web-api` on the pull request's
  base, `20a5100`, in a separate worktree.
- **After:** `measure.py --json after.json web-api openwiz-server:host_names`
  on the branch: the old target and the new one the two moved tests run in,
  measured together.
- Same Linux aarch64 sandbox, Rust 1.99.1, `cargo-llvm-cov` 0.9.1.

[`compare.txt`](compare.txt):

```text
before: openwiz-tests:web-api
after: openwiz-tests:web-api, openwiz-server:host_names
tests: 354 -> 330 (-24)
size files: 73 -> 74 (+1)
size bytes: 947904 -> 924214 (-23690)
size lines: 26164 -> 25463 (-701)
coverage openwiz-adapter-cloudroom: 1731/3180 (54.43%) -> 1731/3180 (54.43%), covered +0
coverage openwiz-adapter-github: 2468/4957 (49.79%) -> 2468/4957 (49.79%), covered +0
coverage openwiz-cli: 1457/9360 (15.57%) -> 1457/9360 (15.57%), covered +0
coverage openwiz-core: 5550/9122 (60.84%) -> 5550/9122 (60.84%), covered +0
coverage openwiz-server: 5160/6140 (84.04%) -> 5160/6140 (84.04%), covered +0
coverage openwiz-service: 0/5276 (0.00%) -> 0/5276 (0.00%), covered +0
coverage openwiz-store: 1860/3643 (51.06%) -> 1861/3643 (51.08%), covered +1
coverage openwiz-terminal: 0/5093 (0.00%) -> 0/5093 (0.00%), covered +0
drops: none
```

(`compare.txt` also holds the measure's sandbox `seconds` line; it is no
run-time claim, below.)

No crate lost a covered line, so there is no drop to explain. The store's
`+1` is one of the kit's known race lines (a concurrent request in the
store, `tools/test-value/README.md`, "Repeatable"), not new coverage.

## Size and count

24 tests fewer (354 to 330, two of them now in
`crates/server/tests/host_names.rs`), 701 lines and 23.7 kB less test
source; one more compiled file (`host_names.rs`). This pull request claims
no run time: run time is judged only from CI's own job durations, before and
after, on the same lane (the orchestrator's ruling on #787).

## What was cut

- **Route-table duplicates (6):** W1, U1, AW1, C3, E11 decisions and E11
  plan each re-pinned their slice of `ROUTES` with length arithmetic; A4
  already pins the whole table, in order.
- **Contract wording pins (7):** six of `contract.rs`'s sentence checks, and
  its check that `untested_version` is gone from the document (#37). The
  contract's own check, that every route, status, header and limit the code
  has is documented, stays.
- **Source greps with a behavioural keeper (5):** "the server has no send
  logic" and "no new-thread logic" (the CLI-equality tests catch a server
  that works out its own answer), "the send path has no single flight" (the
  concurrent-send test counts two calls), "the reports have one
  implementation" (the upload CLI-equality test) and W2's cookie scan (AW2
  runs the same scan of the whole server).
- **Duplicates (5):** A8's W6/W7 header loop (W5 runs the same check on
  every GET of the same tree), `get_never_sends` (W5's preview and lookup
  tests count the tells), U4's constant pins, AW3's long-name test and E11's
  self-hash test (its fingerprint was the default record's own).
- **A help wording pin (1):** A3's sentence check of `--help`.

The source greps that guard a safety rule with no behavioural keeper stay:
A3's single loopback bind, A4's "the server calls only the core's list and
show" (its file-access list has none), AW2's access-header scan and AW4's
two rules over the server and the web app.

## Keeper checks

Each cut test names a keeper. For every cut whose keeper is another test, the
code the cut test guarded was broken in a scratch worktree and the keeper run
alone: [`keepers.txt`](keepers.txt).

- **12 breaks, 12 keepers failed,** each at its own assertion: the route
  table (one extra route; two routes swapped), the contract document (the
  loop and fleet rows), a cookie name in the server, the send and new-thread
  answers worked out by the server, the upload report reworked, the name cap,
  a page header, the create cap, and a self-hash counted as current.
- **Not broken, by reading:** `get_never_sends` (W5's previews assert zero
  tells and its lookups exactly two after two sends), the help wording pin,
  and the doc sentences whose routes the contract check requires.

## Helpers

Ten read-only scouts (Claude Code, Haiku 5.5, High; shared sandbox), each on
one slice of `tests/web-api/` at `20a5100`, each returning one line per test
(what it asserts, cut or keep, keeper with its asserting line). I checked
every item I used against the code.

| Role | Slice | Result | Used | Ignored | Wrong |
| --- | --- | --- | --- | --- | --- |
| scout 1 | `a3`, `a4`, `a5` (36 tests) | ISSUES | 1 cut (help pin) | the bind and list-and-show source cuts (kept: safety rules), constant-pin trims | 0 |
| scout 2 | `a6`, `a7`, `http`, `main` (28) | ISSUES | the ledger rows | its 4 cuts (the comparator's and the client's own proofs and the binary partition stay, as oracles; the failed-version test checks a 200 envelope's withheld detail, which the planted-variant test doesn't) | 0 |
| scout 3 | `a8`, `contract` (24) | ISSUES | 8 cuts (7 contract pins, W6/W7) | the contract-sync cut (kept: a contract), the W9 checker cut and sub-block trims | 0 |
| scout 4 | `w1` to `w6`, `w15` (35) | ISSUES | 5 cuts | the preflight cut (other route than A7's), the framing trim | 0 |
| scout 5 | `u01` to `u09` (31) | ISSUES | 3 cuts | the sequential-creates cut (it catches a dedupe after completion the concurrent test misses) | 0 |
| scout 6 | `aw01` to `aw05` (43) | ISSUES | 2 cuts, plus the AW1 table cut | the mid-body drain cut (its 3 MiB body is the drain), AW2's and AW4's source scans (safety rules) | 1 (the mid-body test does send a body the server must drain) |
| scout 7 | `c3`, `c10` (44) | ISSUES | 1 cut | the oracle self-tests (kept, as TV4's ruling 4) | 0 |
| scout 8 | `e11_decisions_*` (49) | ISSUES | 2 cuts | the guards cut (other route), the fork-load and non-ASCII cuts, the saved-risk cut (its gap kind is unique) | 0 |
| scout 9 | `e11_plan_*` (37) | ISSUES | 1 cut | the helper self-tests and the fork-wrapper probe (oracles), sub-case trims | 0 |
| scout 10 | `lp6`, `ready_stock` (22) | ISSUES | the ledger rows | its cuts (other seams than the keepers it named) | 1 (`lp6_get_loops_is_busy_while_a_pass_holds_the_state` is not dead: `main.rs`'s `a0_lock_wait` runs it) |

No-push check after the swarm: clean (no branch, comment or pull request
write by any helper).
