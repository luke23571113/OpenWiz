# CW3 (#1144): the web-api, attachments, messaging, new-thread, notifications and send-harness groups

The second test pass (spec #1141, DL4) over these groups, using the kit
(`tools/test-value/README.md`). See the [ledger](ledger.md) for one row per
test at the base commit. Coverage was measured before
([before.json](before.json)) and after ([after.json](after.json)), with
[compare.txt](compare.txt) holding the `compare` output. The counter's
results are in [count-before.json](count-before.json) and
[count-after.json](count-after.json).

## What went

34 of the 646 tests, and one case inside a kept table test. Each one fits one of these:

- **Test-harness self-checks** (19): they exercise only test code
  (comparison and log helpers, the schema and pattern checkers, the HTTP
  client's retry, the zsh probe, a fork-load probe). They guard no
  behaviour of OpenWiz.
- **Source greps and doc mirroring** (6): a word, call-site or constant-name
  count in source text, or `contracts/web-api.v1.md` spelling the code's
  names. A behavioural keeper is named for each one that guarded behaviour.
- **Internal crate layout** (2): which crates a manifest depends on. This is
  none of the three keep reasons.
- **Duplicates** (3): the notifications target's pure ready-stock cases that
  the cockpit route's tests (`tests/web-api/ready_stock.rs`) already prove
  end to end.
- **Narrower duplicates of kept cases** (4): one timeout tolerance, one
  schema lint, one C-shim wrapper probe, one fixture-process start.

Helpers that only those tests read went with them. That includes
`tests/attachments/pattern.rs`, a 215-line older copy of
`tests/new-thread/pattern.rs`. The attachments target now includes the
newer copy, which the checks and web-api targets already share. The
`[[test]]` targets in `tests/Cargo.toml` are unchanged, because that file is
outside this ticket's paths.

## What stayed, on purpose

The kept tests cover the product's two writes (`send`, `new`) and their
attachments, the loopback HTTP API the web app calls, and the attachment
store. Nearly every one is either a user-visible answer or a safety gate:
duplicate-send and duplicate-create prevention, owner-only records,
cross-site and host refusal, bounds, diagnostics that must not leak, and
the allowlist. Static checks that guard the allowlist, loopback binding or
the write boundary were kept, because the build skill keeps allowlist and
security checks even when they are static. That covers
`ad11_one_attachment_args_and_no_other_place_builds_file_or_image`,
`the_source_binds_only_one_loopback_address`,
`the_server_calls_only_the_cores_list_and_show`, m12 and AP10. The
documented-value checks for the API's bounds (`a5`, `w4`, `aw03`) were
also kept. They are the only tests that pin the published numbers, because
the behavioural bound tests are written in terms of the same constants.

**Where tests live:** every kept test except `tests/notifications/stock.rs`
drives more than one crate: the CLI or server binary, the core, the
adapter and the fake `room-cli`. `tests/notifications/stock.rs` exercises
only `openwiz-core`. It stays here because `crates/core/tests/` is outside
this ticket's owned paths, and moving the crates' tests is CW6's (#1147).

## Keeper checks

See [keepers.txt](keepers.txt). For each candidate duplicate deletion, I
broke the code the test guarded and ran the named keeper. Three keepers
failed, as they should, and those deletions stand. The fourth (M4, a
future discovery time accepted) left the cockpit keeper passing. So
`tests/notifications/stock.rs::stock_review_future_discovery_time_cannot_be_hidden_by_older_project`
was restored and kept, and it fails under that mutation.
