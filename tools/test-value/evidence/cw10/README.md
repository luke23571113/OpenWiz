# CW10 (#1151): the surviving tools' second test pass

The bolder rule (`tools/test-value/README.md`, from CW1 #1142) over every test
in the `tools/` folders the CW7 table keeps, except `tools/war-room/` and
`tools/collector/` (#979). The [ledger](ledger.md) has one row for each of
the base's 1,136 tests: 964 kept, 172 deleted.

## What went

| File | Deleted | Kept | Lines | Why |
| --- | ---: | ---: | ---: | --- |
| `skills-eval/test.py` | 72 | 2 | 1,063 → 65 | The paid run, its fake tool world and the shipped-skill check stop at `check`, which reads `.claude-plugin/plugin.json`, retired in #555. Scoring, records and token counts are maintainer measures. The case privacy scan stays |
| `skills-eval/weekly/test_weekly.py` | 43 | 4 + 1 new | 992 → 220 | Checkpoint, routing and promotion of skill fixes are maintainer logic. The report's identifier refusal, the candidate refusal and the fail-closed GitHub and handoff reads stay, and one new test drives the handoff command on an unreadable issue |
| `skills-eval/test_openrouter.py` | 7 | 0 | 167 → 0 | The paid OpenRouter run stops at `check` before any request |
| `skills-eval/test_parallel.py` | 2 | 0 | 59 → 0 | The same, through `parallel.py`'s `E.check` |
| `fleet-load/test.py` | 4 | 8 | 253 → 181 | #77's scale target, budgets and report format (closed, not planned), and a harness self-check. The routing, planted-violation, head and target proofs stay |
| `fleet-load/scale-50/test_report.py` | 7 | 0 | 178 → 0 | #77's internal scale report format; no CI job ran it |
| `test-value/test_count.py` | 1 | 0 | 78 → 0 | A maintainer measure; no CI job ran it |
| `stall-alarm/test.py`, class `Alarm` and its helpers | 35 | 3 | 839 → 218 | The factory alarm's own detection, for the maintainer |
| `github-app/test.py`, `LiveCheckDocumentationTests` | 1 | 53 | 1,780 → 1,713 | A runbook snippet's shell, not the product |

Each deleted test's own reason is its ledger row.

Helpers read only by deleted tests went with them: the stall alarm's `pull`,
`comment`, `SHA`, `OTHER` and `Harness.once_clear_recur`; the weekly suite's
checkpoint, routing and report fixtures; skills-eval's fake-world, scoring and
query fixtures; and `fleet-load/test.py`'s re-run of `test_seams`' classes,
which `ci.sh` already runs. The
`tools/test-value/test_count.py` row in `tools/open-import/paths.json` went
with its file. `tools/skills-eval/precheck/test_contract.py` stays untouched:
WizRoom's `experiments/controls.py` loads it as a module.

## Test lines (the counter)

`python3 -I tools/test-value/count.py <commit>`; full results in
[count-before.json](count-before.json) and [count-after.json](count-after.json).

| Area | Before (`e817c9a`) | After (`30a77e2`) | Change |
| --- | ---: | ---: | ---: |
| `tools/` | 35,276 | 34,022 | −1,254 |
| All test lines | 193,452 | 192,198 | −1,254 |
| Share of tracked lines | 36.23% | 36.10% | −0.13 points |

The counter's classifier counts `test_*.py` but not files named `test.py`.
Counting every one of this pass's 59 test files by `wc -l`: 29,251 lines
before, 26,239 after (−3,012), and 4 files fewer.

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
- **skills-eval:** what can still run keeps its safety tests. These cover the
  case privacy scan (`cases.privacy_problems`), the weekly result's
  identifier refusal (`render`), and the fail-closed GitHub and handoff-issue
  reads (`gh_reader`, `gh_issue`). [r1-weekly-mutations.txt](r1-weekly-mutations.txt)
  shows each failing when its guard is removed, and
  [r1-handoff-red.txt](r1-handoff-red.txt) shows the handoff command's proof
  failing when an unreadable issue is read as empty. The paid run's lines (`run`,
  `parallel`, `driver`, the fake world) can't be reached past `check`.
  Scoring, compare, token counts and the weekly checkpoint and routing lose
  their tests as maintainer measures.
- **fleet-load:** every routing line keeps its test. `load.py`'s `run`,
  `verify` and `plant` stay under the kept lifecycle and planted-violation
  proofs. Only `scale.py`'s budget and report checks lose the #77 measurement
  cases. [r2-routing-plants.txt](r2-routing-plants.txt) shows the verifier
  catching a finding sent to the wrong agent and a re-check sent to the wrong
  role. The full simulation was not traced: it takes about 11 minutes
  uninstrumented in CI (`ci/shard/lanes.tsv`).
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

One, for R1's re-check: `tools/skills-eval/weekly/test_weekly.py::HandoffCommand::test_unreadable_issue_posts_nothing_and_stays_pending`.
It runs `run.py handoff` through `main()` with a fake `gh` runner whose issue read fails (exit 1) or is
malformed, for a queued and an unresolved action. It asserts the refusal, that the only `gh` call was the
read (no POST), that the ledger file is byte-for-byte unchanged and that `pending` still lists the action.
catches: a handoff that treats a failed or partial issue read as "no earlier handoff" and posts the
routing instruction again. [r1-handoff-red.txt](r1-handoff-red.txt) is its red run against that mutant,
committed before the green head. It is the keeper for the deleted `test_r11_unreadable_source_posts_nothing`
and `test_r13_unreadable_issue_posts_nothing_and_says_uncertain`.
