# The test-value kit (#803)

The kit every group of the test-value campaign (spec #787) uses: the ledger
form, what a group's pull request carries, and the coverage method with its
script, `measure.py`. This README is the contract; a group that needs it
changed asks on its ticket.

The bar is the test rule (#687): a test protects a supported behaviour, a
contract others rely on or a safety invariant, adds something not already
covered, and names the bug it catches. Never mock-returns-stub, source
mirroring, compiler re-checks, quota tests or unreachable cases.

## The ledger

One row for **every test the group touches or reviews**, in the group's
evidence folder as `tools/test-value/evidence/tv<N>/ledger.md`. A test is
named `path::name`: its file from the repository root and its function, with
any module path inside the file (`tests/fleet/a4_board.rs::board::orders_by_spec`).

| Test | Outcome | Keeper | Catches |
| --- | --- | --- | --- |
| `tests/fleet/a4_board.rs::orders_by_spec` | kept | itself | a board that lists specs out of order |
| `tests/fleet/a5_detail.rs::detail_reads_once` | moved | `crates/cli/tests/fleet_detail.rs::detail_reads_once` | a detail view that reads `gh` twice per issue |
| `tests/fleet/a5_detail.rs::detail_reads_once_twice` | merged | `crates/cli/tests/fleet_detail.rs::detail_reads_once` | (as its keeper) |
| `tests/fleet/a3_seams.rs::fake_gh_prints_help` | deleted | `tests/fleet/a3_fake_gh.rs::fake_gh_refuses_unknown_args` | a fake `gh` that accepts calls the real one refuses |
| `tests/fleet/b2_legacy.rs::legacy_flag_still_parses` | deleted | behaviour gone: `--legacy` removed by #612 | |

(Synthetic rows: they show the form, not real tests.)

The four outcomes, and what each row must carry:

- **kept:** the test stays where it is. Keeper: `itself`. Catches: the bug, in one line.
- **moved:** the test is kept at a new place, normally its crate's own
  `tests/` folder. Keeper: its new `path::name`. Catches: the bug.
- **merged:** its case now lives in another test, which checks it. Keeper:
  that test's `path::name`. Catches: the bug, or `(as its keeper)`.
- **deleted:** Keeper: an existing test, by `path::name`, that still
  catches the same bug at the pull request's head; or `behaviour gone:
  <the behaviour> removed by <issue, pull request or commit>`. Catches stays
  empty.

A keeper is checked, not assumed: the reviewer can break the code the
deleted test guarded and see the keeper fail. "Covered elsewhere" without a
`path::name` is not a keeper.

## What a group's pull request carries

1. **The ledger**, as above, with a row for every test in the group.
2. **Coverage before and after**: `measure.py`'s two results (the JSON
   files, in the group's evidence folder) and the `compare` output in the
   description.
3. **Every drop explained**: each crate on the `drops:` line names the
   behaviour that no longer exists and where it went. A drop that can't be
   explained that way undoes the deletion that caused it.
4. **Size, count and time**: the `compare` lines for tests, size and seconds.
5. **Per new test**, `catches: <the bug>`; or `no new test: <why>`.
6. **Where tests live**: each kept test that exercises one crate moves to
   that crate's `tests/` folder; each one that stays in `tests/` has a
   one-line reason in its ledger row's Catches cell or beside the table.

## The coverage method

```sh
python3 -I tools/test-value/measure.py [--json FILE] TARGET...   # one group
python3 -I tools/test-value/measure.py --all --json-dir DIR       # each target of tests/, the baseline
python3 -I tools/test-value/measure.py compare BEFORE.json AFTER.json
python3 -I tools/test-value/test_measure.py                       # the script's own tests
```

`TARGET` is a `[[test]]` name of `openwiz-tests` (`fleet`) or
`PACKAGE:NAME` for a target in a crate's own `tests/` folder
(`openwiz-cli:fleet_detail`). A group's targets are measured together, in one
coverage report, so a group that moves tests lists its old and new targets
in the after run.

- **The tool:** `cargo-llvm-cov` 0.9.1 (LLVM source-based coverage), with
  rustup's `llvm-tools-preview` component. The script installs both itself
  when missing, into `${XDG_CACHE_HOME:-$HOME/.cache}/openwiz-test-value`; it
  is never a project dependency and touches no `Cargo.toml` or lock file. It
  needs `rustup`, Rust 1.99.1 and network access the first time.
- **The same toolchain:** each result records `rustc --version` and
  `cargo llvm-cov --version`; `compare` refuses two results whose toolchains
  differ.
- **The run:** the builds CI runs before its tests (`cargo build --workspace
  --bins`, and `ci/rust-tests.sh`'s fixture release `openwiz`), plus the debug
  fixture examples, then each
  target under `cargo test --locked -p PACKAGE --test NAME`, instrumented in
  its own folder, `target/test-value-cov/`. Binaries the tests run as child
  processes are instrumented too, so their lines count. One exception: a
  service test runs `<repo>/target/debug/examples/openwiz-server` by its
  documented path, which is the plain build, so that one child process's
  lines don't count; nor do those of children a test starts with a cleared
  environment, whose raw profiles land in the checkout and are deleted after
  the run. A failed test stops the measure: a red run is never a number.
- **Prerequisites,** as for the tests themselves (`AGENTS.md`): zsh, Node
  24.22.1, a user other than root, and for `web-api` the web export
  (`cd apps/web && npm ci --ignore-scripts && npm run build`).
- **Line coverage** per workspace crate: covered and total lines from
  `cargo llvm-cov report --json --summary-only`, product sources only. The
  whole `openwiz-tests` package, and every crate's `tests/`, `examples/` and
  `benches/`, are test code and never count, so moving a test changes no
  number. Dependencies and the standard library never count. A crate's
  total depends on which of its functions the measured binaries contain, so
  it differs between targets: compare a group's before with its own after,
  never one target's numbers with another's, and never add targets' numbers
  up (measure a group's targets together instead).
- **Test count:** passed plus ignored, from every libtest result line.
- **Size:** the target's own sources: its folder when its root is `main.rs`
  or `mod.rs`, otherwise its one file; files, bytes and lines.
- **Run time:** the plain, uninstrumented `cargo test` of each target after
  its build, as CI runs it, in seconds. It is the one number that varies
  between runs, so it is reported, but outside the repeat check below; compare
  times only from the same machine.
- **Before and after:** measure the pull request's base commit in a separate
  worktree (`git worktree add ../before <base>`), never beside another Cargo
  command in the same checkout (`docs/agents/fleet.md`), then the head, on the
  same machine.
- **Repeatable:** on an unchanged tree, two runs print the same coverage,
  test count and size. The baseline below was measured twice to show it.

## The baseline

[`evidence/baseline/`](evidence/baseline/README.md) holds one result for
every test target in `tests/`, measured before any group changed anything:
the campaign's starting numbers. Each group still measures its own before
at its pull request's base, since earlier groups move the numbers.

`unread_fixtures.py` and its test, when present, are TV2's (#804), not this kit's.
