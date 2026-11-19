# CW10 (#1151): the surviving tools' second test pass

The bolder rule (`tools/test-value/README.md`, from CW1 #1142) over every test
in the `tools/` folders the CW7 table keeps, except `tools/war-room/` and
`tools/collector/` (#979). The [ledger](ledger.md) has one row for each of
the base's 1,136 tests: 950 kept, 186 deleted.

## What went

| File | Tests | Lines | Why |
| --- | ---: | ---: | --- |
| `skills-eval/test.py` | 74 | 1,063 | Unreachable: every skills-eval entry first reads `.claude-plugin/plugin.json`, retired in #555. 13 already failed at the base |
| `skills-eval/weekly/test_weekly.py` | 47 | 992 | The same; 37 already failed at the base |
| `skills-eval/test_openrouter.py` | 7 | 167 | The same; its spend caps guard paid runs that stop at `check` before any request |
| `skills-eval/test_parallel.py` | 2 | 59 | The same, through `parallel.py`'s `E.check` |
| `fleet-load/test.py` | 12 | 253 | Measures WizSkills' launch-fleet at 50 threads for #77 (closed, not planned) |
| `fleet-load/scale-50/test_report.py` | 7 | 178 | #77's internal scale report format; no CI job ran it |
| `test-value/test_count.py` | 1 | 78 | A maintainer measure; no CI job ran it |
| `stall-alarm/test.py`, class `Alarm` and its helpers | 35 | 621 | The factory alarm's own detection, for the maintainer |
| `github-app/test.py`, `LiveCheckDocumentationTests` | 1 | 67 | A runbook snippet's shell, not the product |

Helpers read only by deleted tests went with them: the stall alarm's `pull`,
`comment`, `SHA`, `OTHER` and `Harness.once_clear_recur`, and the
`tools/fleet-load/test.py` line in `tools/fleet-load/ci.sh`. The
`tools/test-value/test_count.py` row in `tools/open-import/paths.json` went
with its file. `tools/skills-eval/precheck/test_contract.py` stays untouched:
WizRoom's `experiments/controls.py` loads it as a module.

## Test lines (the counter)

`python3 -I tools/test-value/count.py <commit>`; full results in
[count-before.json](count-before.json) and [count-after.json](count-after.json).

| Area | Before (`e817c9a`) | After (`8b66e33`) | Change |
| --- | ---: | ---: | ---: |
| `tools/` | 35,276 | 33,802 | −1,474 |
| All test lines | 193,452 | 191,978 | −1,474 |
| Share of tracked lines | 36.23% | 36.19% | −0.04 points |

The counter's classifier counts `test_*.py` but not files named `test.py`.
Counting every one of this pass's 59 test files by `wc -l`: 29,251 lines
before, 25,773 after (−3,478), and 7 files fewer.

## Coverage

- **The kit's measure (`measure.py`)** runs `cargo test` targets and measures
  Rust crates only. This pass changes no Rust test, so its numbers can't
  change. It was not rerun.
- **The stall alarm**, the one cut whose tool keeps running: Python's own
  `trace`, with `alarm.py` run through the suite's `STALL_ALARM_SCRIPT` seam
  ([coverage-stall-alarm.txt](coverage-stall-alarm.txt)). Before: 258 of 264
  statement lines (97.7%). After: 217 (82.2%). Each line lost belongs to one
  of these factory-only behaviours, none a user-visible behaviour, a contract
  another repository relies on, or a safety gate:
  - `read` 96–100: killing a timed-out `gh` or `room-cli` read.
  - `loop_cadence` 118–126 and `loop_stalls` 139–163: the fleet loop's
    cadence, and whether it is missing, disabled, errored, never run or stale.
  - `collector` 173–175: the default collector path. The kept tests name the
    collector explicitly.
  - `load_state` 264–282: the alarm's saved state between ticks, including the
    old check-name upgrade.
  - `main` 338–350: read-failure lines, clearing alarms and the 30-minute
    escalation to Jake.
  - The module's 364–365: the configuration-failure line.
- **skills-eval:** every test is gone. The tool can't run at the base (above),
  so no reachable line loses a test.
- **fleet-load:** `load.py`'s `run`, `verify` and `plant`, and `scale.py`'s
  `report` and `verify`, lose their only test: the #77 measurement.
  `test_seams.py` still loads `load.py` and `scale.py`. The full simulation
  was not traced: it takes about 11 minutes uninstrumented in CI
  (`ci/shard/lanes.tsv`).
- **`count.py`** loses its only test. **github-app's** deleted test ran the
  runbook's shell against a fake `python3`, so no line of the App tool loses
  coverage.

## Kept without one of the three reasons

`tools/fleet-load/test_seams.py` and the three test-value suites
(`test_budget.py`, `test_measure.py`, `test_unread_fixtures.py`) test
measurement tools. Their behaviour is none of the three reasons. CI steps
outside this ticket's owned paths run each file: `ci.yml`'s always lane and
budget step, and `run.py`'s `release:test-value` lanes. An emptied unittest
file fails its step on Python 3.12 or later. They stay whole for CW11 (#1152),
which owns those steps, to cut with them.

## New tests

No new test: this pass only deletes.
