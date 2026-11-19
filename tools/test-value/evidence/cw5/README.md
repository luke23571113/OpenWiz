# CW5 (#1146): the apps' second test pass

The bolder rule (`tools/test-value/README.md`, from CW1 #1142) over every test
in `apps/web/` and `apps/site/`. The [ledger](ledger.md) has one row for each
of the base's 460 tests: 436 kept, 24 deleted.

## What went

- **Tests of the test harness:** `clock.test.mjs`, `clock_setup.test.mjs`
  (paused Playwright clocks), `fixture-stop.test.mjs` (fixture server
  teardown), `unit/runner.test.ts` (`run-browser.mjs` ordering and pool) and
  `unit/soak-skip.test.ts` (CI's soak selection).
- **Measurements that assert nothing:** V11's P5, P1 and P3 recorded numbers
  only. P4 stays: it fails on a layout shift during a refresh.
  `unit/v11-refresh.test.ts` checked P4's byte arithmetic, and
  `v11-marks-bounded.test.mjs` pinned how many performance marks are retained.
- **Pixel and style pins:** six `design-pass.test.mjs` checks (row heights,
  label lines, header alignment and fonts, glyph offsets, title x, heading
  height), the site's changelog colours and font sizes, and the Plan page's
  screenshot writer.
- **A quota:** the landing's character count must stay under 3594.
- **CI's own checks in the site:** its classifier case and the token and font
  byte pin. The workflow case in `ci.test.mjs` stays: it is the one site test
  that proves CI runs the site and release proofs.

Helpers and fixtures read only by deleted tests went with them:
`test/fixtures/449/` (v11-refresh's hook), `landingCharsBefore1190` in
`approved-copy.mjs`, V11's `pct`, design-pass's `plainRowHeights`, the Plan
page's `OPENWIZ_PLAN_SHOTS` writer, and the deleted files' rows in
`test/file-times.tsv`.

## Test lines (the counter)

`python3 -I tools/test-value/count.py <commit>`; full results in
[count-before.json](count-before.json) and [count-after.json](count-after.json).

| Area | Before (`9d86900`) | After | Change |
| --- | ---: | ---: | ---: |
| `apps/web` | 20,396 | 19,390 | −1,006 |
| `apps/site` | 637 | 563 | −74 |
| All test lines | 203,732 | 202,652 | −1,080 |
| Share of tracked lines | 36.06% | 35.94% | −0.12 points |

## Coverage

- **The kit's measure (`measure.py`)** runs `cargo test` targets and measures
  Rust crates only. No apps test is one of its targets, and this pass changes
  no Rust test, so its numbers cannot change; it was not rerun.
- **The apps' own source, under the unit suite:** Node's built-in coverage
  (no dependency), `apps/web/src/**`, the whole `test/unit` suite at the base
  and at the head, same sandbox, Node 24.22.1:

  ```sh
  node --test --test-concurrency=2 --experimental-test-coverage \
    --test-coverage-include='src/**' "test/unit/**/*.test.ts"
  ```

  [Before](unit-coverage-before.txt): 164 tests, all pass, lines 81.35%,
  branches 83.64%, functions 76.82%. [After](unit-coverage-after.txt): 160
  tests, all pass, lines 81.35%, branches 83.67%, functions 76.82%. Every
  file's line and function coverage is identical. The one branch difference,
  `api.ts` 74.36% to 74.84%, is a rise, from timing: the deleted unit tests
  import only test tooling (`run-browser.mjs`, `soak-skip.mjs`) and never
  `src/`.
- **Browser deletions:** the browser suite drives the static export, which no
  coverage tool here maps back to source lines. Each deleted browser test
  either asserted nothing, pinned pixels or styles, or tested the harness;
  every behaviour it also touched names its keeper in the ledger.

## New tests

No new test: this pass only deletes.
