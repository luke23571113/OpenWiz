# Test selection inside the CI jobs (#432, K15)

Each code PR runs only the tests its change can reach, from a measured map of which test reads which file. Anything in doubt runs every test. Source: the research on `research/ci-test-selection` (`private/research/2026-11-01-ci-test-selection.md`), spec #330 (K15), and the orchestrator's rulings on #432.

## Tests

`units.py` lists them from the tree, by the [CI selection record's](../../contracts/ci-selection.v1.md) ids:

| Id | Runs |
| --- | --- |
| `rust:lib:<package>` | `cargo test -p <package>`: every test of one workspace crate other than `openwiz-tests` |
| `rust:test:<target>` | `cargo test -p openwiz-tests --test <target>` |

The record's `web:` ids name no test since the web view went (#1264).

The step and skill rules added by K16 (#433) are described below. The pending list and non-skill tool suites keep their existing coverage.

## The map

On every push to `main` and every nightly run, the rust job runs every test under `strace --seccomp-bpf` (`trace.py`), each test on its own and as CI runs it. It keeps every repository path it, or anything it started, opened, looked for (a missing file counts), executed or listed.

`resolve.py` turns those paths into repository files:
- **A Rust build product under `target/`** becomes its dep-info sources.
- **`node_modules`** becomes the lockfile.

A test touching anything else it can't account for (git's index, an unknown build product) is left out of the map, and so always runs. So is a test that failed under strace: it runs again without strace, and that run decides the job.

`select-map` (`map.py`) merges the records into one map. It refuses to build one if any test has no record. A push or the nightly run on `main` then asks GitHub for an OIDC token whose audience is the map's SHA-256 (`job.py sign`), and keeps both in GitHub's cache. That job never fails the run.

[`map.json`](map.json) is a committed copy of one traced run's map. It is the acceptance proof and the real map that `test_pick.py` checks; CI never selects from it.

## Selection

In web-build's docs-only step, before its prune (`job.py select`, `pick.py`):

1. **Only decide.sh's plain case narrows the tests:** a ready PR's first attempt against `main`, the event's base and head the live ones, not `ready_for_review`. Every other run runs everything: a push to `main`, the nightly run, a rerun, `release-*`, a merge group, a stale event.
2. **The newest map from GitHub's cache is used only if its token checks out:**
   - GitHub's OIDC signature checks against its published keys.
   - The token is bound to exactly these bytes, for this repository.
   - It comes from a `push` or `schedule` run of `.github/workflows/ci.yml` on `refs/heads/main`.
   - Its `sha` is the map's commit, and that commit is an ancestor of the tested commit.

   A PR's run can't produce such a token: GitHub signs its ref and event.
3. **The change is every path between the map's commit and the tested merge commit,** so drift on `main` since the trace counts too.
4. **The rules** are listed in `pick.py`'s docstring:
   - **Everything** for any CI or toolchain change, an unknown path, or a new file a test names.
   - **Its readers** for a modified file.
   - **Its readers and the tests that listed a folder above it** for a new or deleted file.
   - **Always** for a test the map doesn't know, and for the always-run `rust:test:checks`.
5. **Anything missing, untrusted, unreadable or failing** runs everything.

The rust job reads the answer:
- **`rust-tests`:** `sh ci/rust-tests.sh --only IDS`.

An empty or missing output is `all`.

## Run by hand

```sh
python3 -I ci/select/test_pick.py     # the selector: every rule, the research's five broken selectors, every link of map.json
python3 -I ci/select/test_trace.py    # the tracer, resolver and map builder, with planted breaks
python3 -I ci/select/test_job.py      # provenance, drift, each job's answer, which runs trace
python3 -I ci/select/units.py         # the tests here
python3 -I ci/select/pick.py --map ci/select/map.json   # what this checkout's change selects
```

`trace.py ready` installs strace through `sudo -n` when it can. A runner that can't trace (the PC's image has no sudo) runs its tests the usual way and makes no map, so pull requests run everything.

## Limits

- **The map knows what the tests did on the traced commit.** A test that reads a file only on some runs, or only through something strace can't see, can be missed. The full runs on `main` and the nightly run still run everything, and X6 (#1264) will report a test a PR skipped that then fails there.
- **A newly published GitHub signing key needs the next map.** Until a map signed with a key GitHub publishes exists, PRs run everything.
- **The runner kit's static checks are not updated.** `ci/runner/test.sh` counts three jobs and allows no cache writer but Namespace's. It is not run in CI and already fails on `main`; see the pull request.

## Step and skill selection (#433, K16)

`job.py` now also exports these requirements, from the **same signed map and
map-to-head diff**, before pruning:

| Output | Required when |
| --- | --- |
| `lint-rust` | A Rust source, crate input or Cargo manifest/lockfile changed; gates fmt, clippy and explicit workspace/release builds |
| `build-site` | The existing classifier's release rows reach the change; gates the release proofs |
| `skill-tests` | Space-separated changed skill folders that have CI suites, or `all` / `none` |
| `image-skills` | The image suite runs; gates its npm/Chromium dependencies |

The web export, its build and the `build-web`, `export-rust` and `export-web`
requirements went with the web view (#1264). A docs change can skip all
explicit build/lint steps.

`skills.py` runs the existing seven skill commands in their existing order,
including both plan-graph commands and triage followed by where-are-we in a
full run. A modified skill folder selects its suite; a folder without a CI
suite adds no command. Unrelated changes select none. Every conservative full
run (including selector/CI changes) runs all suites. The four tools suites in
`SKILLS_TESTS` still run as before. `ci/rust-tests.sh` still builds its fixture
program and runs the selected Rust tests; this ticket does not change it.

The action runs `job.py validate` on the complete answer: missing, duplicate,
unknown or malformed fields restore **all tests and every step**. Missing step
outputs in the workflow also mean run. `skills.py` independently defaults an
unknown/empty selection to all and propagates a selected suite's first failure.
No shell evaluation of a selected suite name occurs.

Run the added workflow-boundary proofs with `python3 -I ci/select/test_steps.py`.
They execute the actual workflow dispatch and action validation script using
fake commands only. X5 (#1262) can consume the named requirements and the skill
dispatcher when moving these existing steps into lanes.

## The deliberate proof (#783, CI3 C5)

A one-line behaviour change was caught by a test selected through the map.

- **The edit:** `tools/install/setup/setup.py` records each setup check's
  observations at `bound + 1` instead of `bound`. The reader rejects the
  mismatched revision, reporting `unknown` where `missing` is expected.
  The browser catcher is reached through the map's measured file reads,
  rather than a skill-folder rule or a tools suite.
- **The PR:** [#1050](https://github.com/openwizdev/OpenWiz/pull/1050), head
  `24f385db400836704d7b894906fffb73f5a4524f`, changed only that line. The
  [ready-PR exception](https://github.com/openwizdev/OpenWiz/issues/783#issuecomment-6904479822)
  allowed selection to run; a draft fails before planning. The PR is closed
  unmerged and must not be reopened or pushed again.
- **The selected red run:** [43973090712, attempt 1](https://github.com/openwizdev/OpenWiz/actions/runs/43973090712/attempts/1).
  The [changes job](https://github.com/openwizdev/OpenWiz/actions/runs/43973090712/job/133670033141)
  says `CI selection: selected` and plans `web:browser:install-connections`.
  The [web-export job](https://github.com/openwizdev/OpenWiz/actions/runs/43973090712/job/133670740222)
  executes it: `test/browser/install-connections.test.mjs:164` fails at the
  assertion on line 183, observing `unknown` for components expected to be
  `missing`. [Independent verification](https://github.com/openwizdev/OpenWiz/issues/783#issuecomment-6941059608)
  records the same evidence.
- **The offline case:** the `tools/install/setup/setup.py` row of `CASES` in
  `planted.py` planted exactly that edit and required the web lane to catch
  it; it went with the web lane in #1264. Local red/green evidence, now in the private records,
  records the catcher failing with the edit and passing after restoration.

Option (b), manual dispatch signing, remains dropped and unmerged under
[revision 3](https://github.com/openwizdev/OpenWiz/issues/780#issuecomment-6934511268).
Push signing in [C7, #1055](https://github.com/openwizdev/OpenWiz/issues/1055)
is separate work.
