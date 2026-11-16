# TV6 (#808): the new-thread group's evidence

The new-thread group of the test-value campaign (spec #787), measured with
the kit (`tools/test-value/README.md`). The ledger is [ledger.md](ledger.md).

## Coverage before and after

- **Before:** `measure.py --json before.json new-thread` on the pull
  request's base, `20a5100`, in a separate worktree.
- **After:** in a worktree of this branch at `a2636d7` (as the before was:
  see "Size and time"), `measure.py --json after.json new-thread
  openwiz-core:new_thread_project_names
  openwiz-adapter-cloudroom:new_thread_readers` on the branch: the old
  target and the two crate targets the moved tests now live in, measured
  together.
- Same Linux aarch64 sandbox, Rust 1.99.1, `cargo-llvm-cov` 0.9.1.

[`compare.txt`](compare.txt):

```text
before: openwiz-tests:new-thread
after: openwiz-tests:new-thread, openwiz-core:new_thread_project_names, openwiz-adapter-cloudroom:new_thread_readers
tests: 113 -> 108 (-5)
size files: 40 -> 40 (+0)
size bytes: 398274 -> 378815 (-19459)
size lines: 11083 -> 10530 (-553)
coverage openwiz-adapter-cloudroom: 1319/3180 (41.48%) -> 1319/3180 (41.48%), covered +0
coverage openwiz-adapter-github: 0/4948 (0.00%) -> 0/4948 (0.00%), covered +0
coverage openwiz-cli: 1047/9360 (11.19%) -> 1047/9360 (11.19%), covered +0
coverage openwiz-core: 2869/9032 (31.76%) -> 2869/9032 (31.76%), covered +0
coverage openwiz-server: 584/6140 (9.51%) -> 584/6140 (9.51%), covered +0
coverage openwiz-service: 0/5276 (0.00%) -> 0/5276 (0.00%), covered +0
coverage openwiz-store: 1060/3647 (29.06%) -> 1060/3647 (29.06%), covered +0
coverage openwiz-terminal: 0/5093 (0.00%) -> 0/5093 (0.00%), covered +0
seconds: 4.5 -> 4.7 (not compared exactly)
drops: none
```

Coverage is the same in every crate: no drop to explain. Two things
showed on the way, and both are in the evidence:

- **The moves carry ten adapter lines.** Measured alone, the `new-thread`
  target covers 10 fewer `openwiz-adapter-cloudroom` lines (the strict
  reader's float visitor and `parse_projects`' mistyped kind and remote):
  only the moved receipt table and reader case reach them, and the after
  run measures them in their new targets, as the kit says.
- **One line in llvm's summary.** With the moved tests, llvm-cov's per-line
  report matched the base line for line, but its per-file summary showed
  `new_thread.rs` one line short: it counts each function by its best
  instantiation, and the reader's closure now has two (the CLI tests' and
  the crate test's), neither alone reaching all 20 lines. The missing one
  was `parse_projects` skipping a row with an empty id, which only the CLI
  tests reached. The moved reader case gained that drift row (red first,
  [`red.txt`](red.txt)), and the summary is whole again.

## Size and time

9 `#[test]`s fewer in the target (113 to 104; with the 4 moved tests,
113 to 108 for the group), 553 lines and 19.5 kB less test source; 40
compiled files before and after (one file deleted, one new crate test file;
the moved `project_names.rs` still counts).

Run time is unchanged: 4.5 s before and 4.7 s after, and three plain
`cargo test -p openwiz-tests --test new-thread` runs of each, alternating
on the same machine, took 4.5 s, 4.5 s, 4.7 s (base) and 4.3 s, 4.6 s,
4.4 s (head). Most of it is the real-time proofs (timeouts, hung reads,
races), which all stay. This pull request claims no time saving.

Both trees were measured in worktrees. In a main checkout the target takes
about 20 s, because `crates/cli/build.rs` watches `.git/commondir`, which
only a worktree has, so the release fixture `openwiz` the tests build is
rebuilt on every run. That is outside this group's paths: see the pull
request's Gaps.

## What went

- **`n01_exact_invocation.rs`, the whole file (6 cases):** the argument
  builder's unit checks, each repeated by a stronger proof. The exact
  shape, each setting once and no excluded flag are
  `n01_end_to_end.rs::one_create_makes_one_spawn_in_exactly_the_shape`
  (the spawn the release build really sent, against a literal argv); the
  chosen settings are `every_setting_is_passed_as_chosen_and_none_is_omitted`;
  the request id is `n11_op_id_binding.rs::synthetic_request_id_matches_contract_at_spawn`
  (an independently computed hash); the unsafe values are
  `n16_allowlist.rs`'s `a_spawn_can_only_be_built_with_safe_arguments`
  (the same `SpawnArgs::new`, 20 shapes). Its byte-for-byte texts merged
  into `n01_end_to_end.rs::the_text_is_one_argument_byte_for_byte`, which
  gained the two it lacked (shell syntax, a bare `--`). Its
  `EXCLUDED_SPAWN_FLAGS` was a copy of `n01_end_to_end.rs`'s `NEVER`, and
  one of its checks only asserted that list held its own literals.
- **Tests of the fake `room-cli` alone:** `n10`'s request-id table (no
  product path sends a request id twice) and `n16`'s refusal of every other
  shape (the product's one shape is the keeper's).
- **Source greps with a stronger keeper:** `structure.rs`'s three. Its
  allowlist word counts were a quota on a file that changed three times;
  its server words are a subset of `n15`'s grep; the derived-reader grep is
  the core's compile-time guard's (`new_thread::no_readers`); the scrub grep
  is `n02`'s behaviour proof that every call runs scrubbed. And `n10`'s
  retry grep, a tail of `there_is_no_retry` whose behaviour half stays.
- **Exact duplicates:** `record_store.rs`'s claimed-with-created-outcome
  case (one cell of the table in
  `synthetic_created_records_require_only_a_finished_phase`); `n11`'s
  attachments-digest unit (`ad04` proves the same refusal end to end);
  `n14`'s file-path-as-text case and `ad01`'s shared-tail case (the
  end-to-end keepers); `n14`'s prompt-schema case, merged into
  `contract_tables.rs`'s prompt table with the four rows it lacked.
- **A prose pin:** `n17`'s exact schema description; the property's type is
  validated by its keeper against the real preview and report.

## Moves

The kept tests that call one crate's public functions and run no program
moved to that crate's `tests/` folder:

- `project_names.rs` → `crates/core/tests/new_thread_project_names.rs`,
  unchanged.
- `n03_existing_projects.rs`'s two reader cases and `boundary_readers.rs`'s
  receipt table → `crates/adapters/cloudroom/tests/new_thread_readers.rs`,
  unchanged, with copies of their small helpers (`twice`, `with`,
  `without`, the fixture reader) and the five `project list` rows the
  reader case reads. The reader case gained one drift row, a project with
  an empty id (catches: a reader that names a project with an empty id;
  red first, [`red.txt`](red.txt)). Only the CLI tests reached that branch
  before, and the moved copy of the reader's closure would otherwise show
  one line fewer in llvm's per-file summary (below).

**Held back (W1-7 gap):** `n16_allowlist.rs` and `boundary_readers.rs`'s
catalogue table were moved too, then failed the protected guards locally:
`tests/proof/p08a_allowlist_static.rs`
(`allowlist_source_contracts_preserve_original_cases`) and
`tests/messaging/m12_allowlist.rs`
(`no_product_source_spells_an_excluded_flag_or_another_write`) read every
file under `crates/` as product source, and refuse `--model` and `steer`
there. They went back to `tests/new-thread/`, unchanged; no guard is edited.
With the two moves that stay, both guards pass.

The rest stay in `tests/new-thread/`: they run the CLI or a program against
the fake `room-cli`, or run the core through `support.rs`'s test client,
which answers through the adapter's parsers, so they cross crates; or they
check the contracts with this folder's schema checker. The ledger lists
each file under its reason.

## Keeper checks

Each deleted or merged case names a keeper. For the 12 whose keeper is
another test, the code the cut test guarded was broken in a scratch
worktree and only the keeper run: [`keepers.txt`](keepers.txt). All 12
keepers failed, each at its own assertion. The two fake-only tests, the
quota and server-word half of `structure.rs`'s first test, and the merged
schema case were checked by reading (listed at the end of `keepers.txt`).

## Helpers

Four read-only scouts (Claude Code, Haiku 5.5, High; shared sandbox), each
on one slice of `tests/new-thread/` at `20a5100`, each returning one line
per test (what it asserts, how it reaches the code, the crates it
exercises, cut, keep or move). I checked every item I used against the
code; cuts were then checked by a break (above).

| Role | Slice | Result | Used | Ignored | Wrong |
| --- | --- | --- | --- | --- | --- |
| scout 1 | `n01`–`n08` (21 tests, 39 cases) | ISSUES | the `n01_exact_invocation` cuts and merge; the move candidates (`n03`) | merges inside `n04`, `n05` and `n06` (near twins at other layers), count trims (`n04`, `n06`), the `n03` test-name nit | 0 |
| scout 2 | `n09`–`n14`, `inspect_claim_race`, `boundary_readers` (31 tests, 14 cases) | ISSUES | `n10`'s fake table and grep, `n11`'s digest, `n14`'s two cases; the receipt-table move | `n10`'s second test (its replay and conflict path through the CLI is not `n09`'s), line trims in `n11` and `n12`, the `n09` and `inspect` merges | 0 |
| scout 3 | `n15`–`n19`, `contract_tables` (28 tests, 26 cases) | ISSUES | `n16`'s fake test, `n17`'s prose pin; `n16`'s move (held back by the guards) | `n15`'s server grep (kept: the server's one guard that it builds no call), the zsh probe tests (kept: they stop the shell round trips passing vacuously without zsh), merges inside `n18_cli`, the reject rows of `contract_tables` | 0 |
| scout 4 | `record_store`, `record_load`, `structure`, `pattern`, `schema_parity`, `project_names`, `harness`, `ad_*`, two `tests/support` proofs (35 tests, 14 cases) | ISSUES | `record_store`'s duplicate, `structure.rs`'s three greps, `ad01`'s tail case; the `project_names` move | the `tests/support` proofs (TV9's), `pattern.rs`'s checker test (kept: it keeps the schema checks from passing vacuously), the `ad06`, `ad10`, `ad13` trims and `m10` overlaps | 0 |

No-push check after the swarm: clean (no branch, comment or pull request
write by any helper).
