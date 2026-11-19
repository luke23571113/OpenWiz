# CW6: the crates' own tests (#1147)

The second test pass over every `#[test]` under `crates/`: the crates' own
`tests/` folders and the `#[cfg(test)]` modules in their sources. Base:
`9d8690064b17ecbb18ef0ca17ecda178e8bc113d`.

- [ledger.md](ledger.md): all 182 tests, 171 kept with a keep reason and 11
  deleted with a keeper or gone reason.
- [count-before.json](count-before.json): `count.py` at the base.
- [coverage-before.json](coverage-before.json),
  [coverage-after.json](coverage-after.json) and [compare.txt](compare.txt):
  `measure.py` over the twelve `[[test]]` targets whose files live in
  `crates/` (the service targets in `tests/service/` and `tests/loops/` are
  CW2's).

## Test lines (`count.py`)

| Area | Before | After |
| --- | ---: | ---: |
| `crates/core` | 4276 | 4105 |
| `crates/server` | 80 | 80 |
| `crates/service` | 793 | 793 |
| `crates/store` | 1079 | 1079 |
| crates' `tests/` total | 6228 | 6057 (-171) |
| whole tree test lines | 203732 | 203561 |

The counter puts inline `#[cfg(test)]` modules in no area; this pass also
removes 278 lines of them (`crates/core/src`: 127; `crates/adapters/github/src`: 151).

## Coverage

The kit's targets: 64 -> 61 tests, every crate's covered lines unchanged,
`drops: none` ([compare.txt](compare.txt)).

The kit measures `[[test]]` targets only, so the two changed library test
suites were measured the same way with `cargo llvm-cov --lib -p openwiz-core
-p openwiz-adapter-github`, counting product lines only (the source above
each file's first `#[cfg(test)]`): 1385 -> 1363 of 13224 covered. Every
one of the 22 lines is in `crates/adapters/github/src/process.rs`:
`Executor::program` (56-58), `Executor::program_for_fixtures` (61-69),
`Executor::run`'s program arm (76-77) and `Executor::checks` (82-91). The
deleted `x2_*` tests reached them through the test-only fixture executor.
All 22 still run under `openwiz-tests --test web-api` (its fifteen `c3_`
tests, which drive the GitHub fleet source through
`Executor::program_for_fixtures` and the fake `gh`), hit 34 to 259 times
each in an instrumented run at this pass's head. `openwiz-core`'s product
lines lost no coverage.
