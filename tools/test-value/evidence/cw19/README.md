# CW19 (#1160): unread fixtures and the wave's after count

## Measuring

- **Base:** `c02e5c615ced5d588f145f9bdfcbb5509f59576c` (`origin/main`).
- **Measuring commit:** `49edf2647db873f339934d05af3757ad2fa72107`, the
  deletions only; this README and the after files came later and are not
  in it.
- **Counter:** CW1's, unchanged: `python3 -I tools/test-value/count.py <commit>`
  (Git 2.56.1, `--attr-source`). Results: [count-before.json](count-before.json)
  (base) and [count-after.json](count-after.json) (measuring commit), compared
  with CW1's [baseline.json](../cw1/baseline.json) at `83931a4`.
- **Scanner:** TV2's, unchanged: `python3 -I tools/test-value/unread_fixtures.py
  [ROOT ...]`, over its default root and over every tracked outermost
  `fixtures/` folder outside WizRoom's paths. Output:
  [scan-before.txt](scan-before.txt) and [scan-after.txt](scan-after.txt).

## Removed fixture paths (14)

No test, CI step, workflow or script reads any of them. Each was checked by
name and by folder across the tree, and by reading the tests of its folder.

| Path | Why no test reads it |
| --- | --- |
| `ci/main-batch/fixtures/shadow/red-exact-plan-text.log` | A red-run log. `test_shadow.py` reads no file in `fixtures/shadow/` since CW11 (#1152) deleted its last two read fixtures and left these logs for CW19 |
| `ci/main-batch/fixtures/shadow/red-execution.log` | As above |
| `ci/main-batch/fixtures/shadow/red-independent-currentness.log` | As above |
| `ci/main-batch/fixtures/shadow/red-kit.log` | As above |
| `ci/main-batch/fixtures/shadow/red-missed-work-mutant.log` | As above |
| `ci/main-batch/fixtures/shadow/red-plan.log` | As above |
| `ci/main-batch/fixtures/shadow/red-r1-benchmark.log` | As above. The scanner keeps it only because `docs/evidence/827/search.sh`, an evidence script no CI runs, excludes it from a `git grep`; the exclusion is harmless without the file |
| `ci/main-batch/fixtures/shadow/red-shadow-only.log` | As above |
| `ci/main-batch/fixtures/shadow/red-shadow.log` | As above |
| `ci/main-batch/fixtures/contract/red-coverage.log` | A red-run log. `test_contract.py` and `test_admit.py` read only `complete.json`, `expected.json`, `superseded-pending*.json` there and the schema above it. The scanner keeps it only because the folder is named by path |
| `ci/main-batch/fixtures/contract/red-r1-superseded-pending.log` | As above |
| `ci/main-batch/fixtures/contract/red-registration.log` | As above |
| `ci/main-batch/fixtures/contract/red-required-attempt.log` | As above |
| `tools/install/cloudroom/fixtures/Cloudroom-v9001-x64.exe` | The Windows installer stand-in. `test_cloudroom.py` reads only the AppImage and the dmg (`for name in (APPIMAGE, DMG)`); Windows is refused as unsupported before any download. `SHA256SUMS.txt` and `release.json` still list it, as a release does |

Their 13 rows left `tools/open-import/paths.json` with them; the installer
stand-in was covered by `tools/install/**`.

## What the scanner still lists, and why each stays

After the deletions the default root (`tests/fixtures`) is empty, as are
`ci/escapes`, `ci/main-batch`, `contracts`, `tests/service`, `tools/ci-overload`,
`tools/fleet-load/scale-50`, `tools/install/tests/setup-onboard-contract` and
`tools/wizskills`. Four roots still list files. None is unread; the scanner is
static and does not see a path built at run time (`FIXTURES / name`, a
`load(name)` template). It was not changed.

| Listed | Real reader | Class |
| --- | --- | --- |
| `apps/web/test/fixtures/decisions/empty.json`, `summary.json` | `decisions.mjs` `load(name)` reads `./${name}.json`; `e11-decisions-states.test.mjs` calls `load('summary')`, `load('empty')` | read (scanner false positive) |
| `apps/web/test/fixtures/loops/empty.json`, `target.json` | `loops.mjs` `load(name)`; `lp-list.test.mjs` calls `load('empty')`, `load('target')` | read (scanner false positive) |
| `apps/web/test/fixtures/plan/README.md`, `ready-stock/README.md` | none; each holds its folder's `synthetic_assumptions`, which `AGENTS.md` requires for every shape not observed | protected: kept |
| `tools/install/cloudroom/fixtures/*` (9) | `test_cloudroom.py` via `FIXTURES / name` (`setup.md`, `release.json`, `SHA256SUMS.txt`, the AppImage and dmg, `cloud-sign-in.json`, `cloud-{status}.json` for signed-in, signed-out and signing-in); `cloudroom-setup.test.mjs` names the three `cloud-*` status files | read (scanner false positive) |
| `tools/roadmap/fixtures/ROADMAP.md`, `STATUS.md`, `world.json` | `tools/roadmap/test.py` via `FIX / name` | read (scanner false positive) |
| `tools/stall-alarm/fixtures/flow-read.json` | `tools/stall-alarm/test.py` (`HERE / "fixtures" / "flow-read.json"`), run by `war-room-proof.yml` | read (scanner false positive) |

Other files the scanner keeps that no test reads, left on purpose:

- `apps/web/test/fixtures/first-hour-pages/red.txt` and
  `tools/wizskills/fixtures/contract/red.txt`, `proof.md`: red-run and proof
  records named by the kept `README.md` and `proof.md` beside them (the last two
  were folded there by CW14). Ambiguous: deleting them needs edits to those
  notes. Kept.
- `contracts/fixtures/github-identity/red-*.txt`: read, since the identity
  suite's privacy scan walks that folder; named by the kept contract. Kept.

**WizRoom (#979) exclusions:** `ci/wizroom/fixtures`, `tools/collector/fixtures`
and `tools/war-room/fixtures` were left out of the scan and nothing there was touched.

## The after count against CW1's baseline

Test lines by area, from the counter's `by_area` (rows with zero in all three
columns omitted: `contracts/fixtures/`, the three adapter/cli crates, `other`):

| Area | CW1 baseline (`83931a4`) | Before CW19 (`c02e5c6`) | After (`49edf26`) | Wave change |
| --- | ---: | ---: | ---: | ---: |
| `.github/` | 2,314 | 1,889 | 1,889 | −425 |
| `apps/site` | 637 | 563 | 563 | −74 |
| `apps/web` | 20,396 | 19,390 | 19,390 | −1,006 |
| `ci/` | 3,361 | 2,245 | 2,245 | −1,116 |
| `crates/core` | 4,276 | 4,105 | 4,105 | −171 |
| `crates/server` | 80 | 80 | 80 | 0 |
| `crates/service` | 793 | 793 | 793 | 0 |
| `crates/store` | 1,079 | 1,079 | 1,079 | 0 |
| `tests/` | 125 | 125 | 125 | 0 |
| `tests/attachments` | 4,749 | 4,317 | 4,317 | −432 |
| `tests/checks` | 8,219 | 5,595 | 5,595 | −2,624 |
| `tests/cli-agent` | 7,151 | 7,122 | 7,122 | −29 |
| `tests/fake-gh` | 273 | 273 | 273 | 0 |
| `tests/fake-room-cli` | 811 | 811 | 811 | 0 |
| `tests/fixture-entrypoints` | 143 | 143 | 143 | 0 |
| `tests/fixtures` | 17,690 | 17,691 | 17,691 | +1 |
| `tests/fleet` | 21,272 | 18,710 | 18,710 | −2,562 |
| `tests/loops` | 1,571 | 1,571 | 1,571 | 0 |
| `tests/messaging` | 9,561 | 9,312 | 9,312 | −249 |
| `tests/new-thread` | 9,219 | 9,042 | 9,042 | −177 |
| `tests/notifications` | 254 | 158 | 158 | −96 |
| `tests/proof` | 7,375 | 7,234 | 7,234 | −141 |
| `tests/send-harness` | 188 | 188 | 188 | 0 |
| `tests/service` | 17,359 | 17,239 | 17,239 | −120 |
| `tests/support` | 1,227 | 1,157 | 1,157 | −70 |
| `tests/web-api` | 21,316 | 20,516 | 20,516 | −800 |
| `tools/` | 42,215 | 34,170 | 34,170 | −8,045 |
| **All test lines** | **203,654** | **185,518** | **185,518** | **−18,136 (−8.9%)** |
| All tracked text lines | 565,023 | 528,099 | 526,923 | −38,100 |
| **Test share** | **36.04%** | **35.13%** | **35.21%** | **−0.83 points** |

CW19's own deletions are not test lines under the counter's classifier (red
logs and an installer stub in `fixtures/` folders outside its test paths), so
its row change is zero. They remove 1,249 tracked lines (1,236 fixture lines
and 13 carriage rows); with this folder's 73 before-files the measuring commit
is 1,176 lines smaller, which nudges the share up by 0.08 points. Over the
wave, test lines fell 8.9% and their share from 36.04% to 35.21%: tests stay
the minority of tracked lines.

## Tests

No test was added or deleted: `no new test: deletion only; the deleted files
were read by no test`.
