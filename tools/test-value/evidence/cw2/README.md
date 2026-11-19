# CW2 (#1143): the fleet, service and loops groups' evidence

The bolder test pass (spec #1141, DL4) over `tests/fleet/`, `tests/service/` and
`tests/loops/`, measured with the kit (`tools/test-value/README.md`).

- [ledger.md](ledger.md): all 514 tests, kept 469, deleted 45.
- [callers.txt](callers.txt): the product-caller search behind the "no product
  caller since #800" gone reasons.
- [keepers.txt](keepers.txt): the keeper check.
- [drops.txt](drops.txt): every product line the cut leaves uncovered.

## Coverage before and after

- **Targets:** the group's 16, measured together: `openwiz-tests:fleet`,
  `openwiz-tests:service`, `openwiz-tests:loops` and the 13 `openwiz-service`
  targets whose files live in `tests/service/` and `tests/loops/`.
- **Before:** the base, `9d86900`, in a separate worktree ([before.json](before.json)).
  **After:** this branch at `cbabf46`, whose test code is the hand-back head's ([after.json](after.json)).
  Both with `RUST_TEST_THREADS=1`, on one Linux aarch64 sandbox, Rust 1.99.1,
  `cargo-llvm-cov` 0.9.1. The before run needed `apps/web/out` for the cut
  `t2_docs.rs`.

[compare.txt](compare.txt), without its sandbox `seconds` line:

```text
tests: 508 -> 463 (-45)
size files: 89 -> 85 (-4)
size bytes: 1481129 -> 1384784 (-96345)
size lines: 40817 -> 38001 (-2816)
coverage openwiz-adapter-cloudroom: 2402/5744 (41.82%) -> 2312/5744 (40.25%), covered -90
coverage openwiz-adapter-github: 2949/4948 (59.60%) -> 2946/4948 (59.54%), covered -3
coverage openwiz-cli: 2040/6756 (30.20%) -> 2040/6756 (30.20%), covered +0
coverage openwiz-core: 6483/9047 (71.66%) -> 6160/9047 (68.09%), covered -323
coverage openwiz-server: 719/6140 (11.71%) -> 718/6140 (11.69%), covered -1
coverage openwiz-service: 4028/5356 (75.21%) -> 4028/5356 (75.21%), covered +0
coverage openwiz-store: 1961/3650 (53.73%) -> 1955/3650 (53.56%), covered -6
drops: openwiz-adapter-cloudroom, openwiz-adapter-github, openwiz-core, openwiz-server, openwiz-store
```

(The kit counts 508 tests where the ledger has 514 rows. Seven rowed tests
compile only into crate unit tests, outside these targets:
`tests/service/t7_transport.rs` (into `openwiz-adapter-github`),
`install_engine_target.rs` and `install_engine_record_factory.rs` (into
`openwiz-service`'s library tests). One counted test is the new-thread group's:
`l3-runner` also compiles `tests/new-thread/pattern.rs`. 514 - 7 + 1 = 508; none
of the eight is cut.)

## Every drop explained

From [drops.txt](drops.txt), line by line:

- **`openwiz-core`, `crates/core/src/fleet/starts.rs`, 145 lines:** the start
  path (`start_agent`, `retried`, `next_step`, `preview_start`, `binds`, the
  start lock). It has no product caller since the executing tick was retired
  (#800; [callers.txt](callers.txt)). The behaviour is gone; the code stays,
  as this ticket changes no product file.
- **`openwiz-core`, `crates/core/src/new_thread/{mod,operation,outcome,start,status}.rs`,
  174 lines; `openwiz-adapter-cloudroom`, `new_thread.rs` and `process.rs`,
  80 lines; `openwiz-store`, `lib.rs` 493-499, 4 lines:** the
  new-thread create, reconcile and record paths that `start_agent` reached.
  `openwiz new` still uses them, and the kept `new-thread` target covers every
  one of these lines on this branch ([new-thread-after.json](new-thread-after.json);
  drops.txt's last column).
- **`openwiz-adapter-github`, `crates/adapters/github/src/writes.rs` 453, 458, 759:**
  the close's not-an-issue refusal and the merge's queue check. `Write::Merge`
  and `Write::CloseIssue` have no product caller ([callers.txt](callers.txt)).
- **`openwiz-store`, `crates/store/src/lib.rs` 237; `openwiz-server`,
  `crates/server/src/http.rs` 350:** timing-dependent lines: a directory another
  process made first, and the socket read the kit already lists as a race (#892).
  `lib.rs` 237 is covered by the `new-thread` target too.
- **`openwiz-service`, `crates/service/src/loops/check.rs` 66:** a child-poll
  line whose execution depends on timing; the crate's covered count is
  unchanged (+0), so another timing line was hit instead.

## Size and count

45 tests fewer, 4 compiled files fewer, 2,816 lines and 96 kB less test source.
Test lines by `count.py` (`9d86900` to this branch): `tests/fleet` 21,272 to
18,764, `tests/service` 17,359 to 17,051, `tests/loops` 1,571 unchanged;
repository test share 36.06% to 35.70%. Run time is not compared: the sandbox
ran both measures at once under shared load.
