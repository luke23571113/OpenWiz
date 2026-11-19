# Cleanup wave 1 scaffolding inventory

CW7 (#1148) supplies the table for Jake's CW8 decision (#1149). CW9 (#1150) can
act on the approved rows after explicit go. The **Done** column is for CW9.

- OpenWiz `8653e417df2ae9c36ae081401163553a10adbdbe` was `origin/main` at inventory time.
  WizSkills main was `89fc285ce551f341b8d308732bcd8d4467ace353`. OpenWiz's `wizskills.lock` pins
  `c112b993d0ec582d2aae370cf8011810fde9aea2`. Caller checks include that installed release.
- **30,872 lines deleted** across 37 proposed delete rows.
  2 move rows relocate 686 lines with zero net removals.
  70 keep rows remove zero lines. The inventory contains
  109 rows and 185,520 text lines. Counts are for the listed
  directories at the pin. CW9 will measure caller edits and actual removals.
- WizRoom (#979) owns `tools/war-room/`, `tools/collector/` and
  `ci/wizroom/`. Their trees are excluded from rows and totals. References
  inside them were read only to establish dependencies on in-scope folders.

## How to verify

List the trees recursively, including nested fixture and evidence directories.

```sh
base=8653e417df2ae9c36ae081401163553a10adbdbe
git ls-tree -dr --name-only "$base" -- tools ci .github/actions |
  awk '$0 != ".github" && $0 !~ /^(tools\/(war-room|collector)|ci\/wizroom)(\/|$)/'
```

Count tracked UTF-8 blobs with no NUL using their bytes at that commit. Count
newline characters and one final line if the last line lacks a newline. Skip
symlinks and binary blobs. Each row counts only files directly in that directory.
This lets a child have its own decision and avoids counting its lines twice.
The two tracked Python cache folders each contain a binary blob and contribute
zero text lines.

Caller search used `git grep -n` at the OpenWiz and WizSkills pins for directory
paths and entrypoint names, followed by imports, shell invocations and workflow
dispatches. Job references use the workflow filename and job ID. A path filter,
manifest entry, historical README or a retired tool's own tests alone do not
count as callers. Fixture rows identify the proof of a surviving behaviour or
contract that reads them. Documented maintainer entrypoints and currently
assigned test passes count as consumers where named. The search covers
checked-in sources. Unversioned invocations and deployment state are unverified.

## Decisions for CW8

- Removing the old GitHub reader affects the OpenWiz parity check and the three
  release units `release:ci2-read-contract`, `release:ci2-shared-reads` and
  `release:ci2-read-consumers`. Check coverage against the carried WizSkills
  reader before removing those units. The installer's GitHub App setup and the
  carried WizSkills binaries still have callers.
- Removing the completed CI2 kit leaves `ci.yml#ci`'s main-shadow capture in
  use. Drop its retired-kit assertion from `ci/main-batch/test_shadow.py` only
  with a keeper or a gone-reason. Removing the ticket mover also requires
  removing its dispatcher and shard registrations, including the explicit
  `release:open-tickets` expansion in `run.py`.
- Before agreeing to remove the ops kit or relay, settle open #439, #548, #659,
  and #190 and check whether either still has an external invocation. Check
  the router and inbox proofs in `ci.yml#always`, `#release` and
  `#launch-fleet` for protection worth retaining. The replay and promotion
  rows also need a #979 dependency check. The replay fixture directory stays
  because the collector reads it, even if its parent loses its direct files.
- The scale report move preserves its validator, report contract and tests.
  Repoint `tools/fleet-load/scale.py`, its workload-source fingerprint and
  the open scale tickets' references. The source-path edits outside selected
  directories need to be covered by CW9's approved scope before any move.
- For any approved removal, trace and clear dispatch, path ownership and
  surviving reader references and name the keeper or gone-reason for each
  deleted test. Some references above sit in files CW9 does not explicitly
  own. Settle those exact paths before CW9 edits them. Protected #979 paths
  remain with WizRoom.

## Inventory

| Folder | Purpose | Caller evidence | Proposed verdict | Direct text lines | Net lines removed | Done |
| --- | --- | --- | --- | ---: | ---: | --- |
| `.github/actions` | Local composite actions | The two workflow callers in the child rows | **keep** | 0 | 0 | |
| `.github/actions/changelog` | Changelog entry and exemption check | `changelog.yml#changelog` uses this composite action | **keep** | 419 | 0 | |
| `.github/actions/docs-only` | CI classification, plans, pruning, lane execution and receipts | `ci.yml#changes` runs `plan.py` and `ci.yml#ci` runs `run.py finish`. The pre-push hook also runs `test.sh` at this pin | **keep** | 4,007 | 0 | |
| `.github/actions/docs-only/setup` | Pinned toolchain, dependency and cache setup | `ci.yml#always`, `#web-build`, `#rust`, `#rust-export`, `#web`, `#web-export`, `#site`, `#release`, `#skills`, `#launch-fleet` use this composite action | **keep** | 154 | 0 | |
| `ci` | Shared Rust test driver and bounded retry | `ci.yml#rust` and `#rust-export` call `rust-tests.sh`. `ci.yml#changes` (through `plan.py`) and the setup action call `retry.sh` | **keep** | 612 | 0 | |
| `ci/escapes` | Finds merged PRs whose omitted tests later fail | `ci-escapes.yml#find` runs `escapes.py find` | **keep** | 1,756 | 0 | |
| `ci/escapes/fixtures` | Synthetic GitHub executable for the escape detector | `ci-escapes.yml#proof` runs `ci/escapes/test.py`, which drives the live detector's CLI with the fake | **keep** | 48 | 0 | |
| `ci/hosted` | Runner guard and hosted prerequisites | `ci.yml#changes` runs `guard.sh` and `ci.yml#always` calls `setup.sh` through the setup action | **keep** | 608 | 0 | |
| `ci/main-batch` | Main-batch observation and old admission tooling | `ci.yml#ci` runs `shadow.py capture` on eligible main pushes and merge groups. The old `admit.py` gate ended with #1055 | **keep** | 2,087 | 0 | |
| `ci/main-batch/fixtures` | Synthetic observations and contract cases | `ci.yml#release` runs `release:ci2-batch-shadow` and `release:ci2-batch-contract` for the surviving main-batch observation path | **keep** | 0 | 0 | |
| `ci/main-batch/fixtures/contract` | Coverage and supersession cases | `ci.yml#release` → `release:ci2-batch-contract` → `test_contract.py` | **keep** | 1,652 | 0 | |
| `ci/main-batch/fixtures/shadow` | Synthetic GitHub state and shadow proof records | `ci.yml#release` → `release:ci2-batch-shadow` → `test_shadow.py` | **keep** | 775 | 0 | |
| `ci/runner` | Trusted CI cache restore and save | `ci.yml#always` calls `cache.sh restore` through setup and runs `cache.sh save` | **keep** | 84 | 0 | |
| `ci/select` | Signed map, recorded reads and job selection | `ci.yml#changes` imports the selector and `ci.yml#select-map` runs `map.py` and `job.py sign` | **keep** | 50,875 | 0 | |
| `ci/selection` | Shared CI-selection contract examples | `ci-escapes.yml#proof` reads `ci/selection/README.md` and all three fixture sets to check the detector's contract | **keep** | 112 | 0 | |
| `ci/selection/invalid` | Plans the detector must refuse | `ci-escapes.yml#proof` → `test_every_invalid_plan_is_refused_for_its_reason` in `ci/escapes/test.py` | **keep** | 5,560 | 0 | |
| `ci/selection/reads` | Artifact-read outcomes for historical plans | `ci-escapes.yml#proof` → `ci/escapes/test.py` exercises the detector's plan lookup | **keep** | 409 | 0 | |
| `ci/selection/valid` | Plans the detector and dispatcher must accept | `ci-escapes.yml#proof` → `test_every_valid_plan_is_accepted`. `ci.yml#always` → docs-only `test_gate.py`, `test_execution.py` and `test_lanes.py` through the classifier proof | **keep** | 1,728 | 0 | |
| `ci/shard` | Timing tables, shard allocation and exact-once checks | `ci.yml#rust` and `#rust-export` run `shard.py share`. `ci.yml#ci` runs `shard.py check`. The release and launch-fleet lane dispatcher uses `lanes.py` | **keep** | 1,814 | 0 | |
| `tools` | Tool entrypoints grouped by owner | The callers in the child rows. No tracked files directly in this directory | **keep** | 0 | 0 | |
| `tools/ci-overload` | Queue and API admission guard and observation supplier | WizSkills `launch-fleet` → `fleet.sh overload` accepts `LAUNCH_FLEET_OVERLOAD_SUPPLY` pointing at `supply.py` | **keep** | 1,159 | 0 | |
| `tools/ci-overload/evidence` | Saved build and review proofs | None found. The guard reads a fresh observation and private pause state | **delete** | 218 | 218 | Deleted (218 text lines) |
| `tools/ci-overload/fixtures` | Queue and rate-limit scenarios | `ci.yml#release` → `release:ci2-overload` → `test.py` guards overload admission. `ci.yml#always` → `tools/fleet-load/test_carried.py` checks `healthy.json` against WizSkills | **keep** | 23 | 0 | |
| `tools/ci2-live` | CI2 main-batch observation campaign kit | None found. #463 is closed. `ci/main-batch/test_shadow.py` calls its offline kit check, which only checks the retired procedure | **delete** | 140 | 140 | Deleted (140 text lines) |
| `tools/fleet-load` | Fleet workload model and WizSkills consumer harness | `ci.yml#release` → `release:fleet-load` runs `ci.sh` and requires the measured workload receipt. `ci.yml#always` runs `test_carried.py` and `test_seams.py` | **keep** | 2,358 | 0 | |
| `tools/fleet-load/evidence` | Saved fleet load reports and comparison inputs | None found in the measured CI run. The saved comparisons are historical; `scale.py` consumes `tools/scale-50/fixtures/workload-v1.json` and the current source and settings | **delete** | 3,575 | 3,575 | Deleted (3,575 text lines) |
| `tools/fleet-load/evidence/1132` | Saved release-shard budget and comparison evidence | Referenced by #1132 and the load README. `ci.yml#release` runs `ci.sh` and measures a fresh workload without these files | **delete** | 344 | 344 | Deleted (344 text lines) |
| `tools/fleet-load/standalone` | One-off WizSkills migration dry-run comparison | None found. `dry_run_report.py` is the WZ-P3/P4 comparison entrypoint described in this tool's README | **delete** | 47 | 47 | Deleted (47 text lines) |
| `tools/github-app` | Setup and packaging for GitHub App credentials | WizSkills `setup` calls the installed App setup tool. `packages.yml#package` packages `setup.py`, `app.py`, `mint-token.py` and `manifest.json` through `build_products.py` | **keep** | 3,102 | 0 | |
| `tools/github-reads` | Pre-move GitHub read helper and its parity checks | No live checkout invocation found. WizSkills `launch-fleet` and `where-are-we` both call the carried `launch-fleet/scripts/carried/read.py`. `ci.yml#always` and `#release` still check the old source and parity | **delete** | 2,882 | 2,882 | Deleted (2,882 text lines) |
| `tools/github-reads/fixtures` | Retained helper contract and read fixtures | Only the retired checkout reader's release tests, apart from the carried-source checks above | **delete** | 0 | 0 | Deleted (0 text lines) |
| `tools/github-reads/fixtures/contract` | Contract cases for the old checkout reader | Parent delete. `release:ci2-read-contract` checks the original reader | **delete** | 391 | 391 | Deleted (391 text lines) |
| `tools/github-reads/fixtures/reads` | HTTP and cache cases for the old checkout reader | Parent delete. `release:ci2-shared-reads` checks the original reader | **delete** | 826 | 826 | Deleted (826 text lines) |
| `tools/install` | Verified product installer, pull and setup tools | WizSkills `install` invokes `install preflight`, `download`, `install` and `open` | **keep** | 1,700 | 0 | |
| `tools/install/__pycache__` | Tracked compiled installer cache | None found. The skill invokes the tracked Python source | **delete** | 0 | 0 | Deleted (0 text lines) |
| `tools/install/access` | Product Access client and setup interface | `packages.yml#package` packages `access/access.py` through `build_products.py`. WizSkills `setup` uses the installed Access tool | **keep** | 1,138 | 0 | |
| `tools/install/cloudroom` | Cloudroom prerequisite setup tool | `packages.yml#package` packages `cloudroom/cloudroom.py` through `build_products.py` | **keep** | 1,974 | 0 | |
| `tools/install/cloudroom/fixtures` | Synthetic Cloudroom downloads and sign-in state | `ci.yml#web` and `#web-export` → `apps/web/test/browser/cloudroom-setup.test.mjs` → `test_cloudroom.py` | **keep** | 124 | 0 | |
| `tools/install/completion` | Completion checkpoint verifier | `ci.yml#release` → `release:install` → `test_install.py::FirstHourContract.test_completion_checkpoint` checks the first-hour completion contract | **keep** | 1,360 | 0 | |
| `tools/install/platform` | Runtime manager and platform security helper | `packages.yml#package` packages `runtime.py`. The OpenWiz CLI GitHub App adapter compiles in `security.py` | **keep** | 779 | 0 | |
| `tools/install/setup` | Project init, store, GitHub login and setup API | `packages.yml#package` packages these through `build_products.py`. WizSkills `setup` calls the installed setup API and GitHub login | **keep** | 2,514 | 0 | |
| `tools/install/tests` | Installer and onboarding scenario suites | `ci.yml#release` runs the setup/onboard contract, init, journey and release-security units below | **keep** | 0 | 0 | |
| `tools/install/tests/first-hour` | First-hour and first-merge acceptance and receipt tools | `ci.yml#release` → `release:setup-onboard-journey` runs `test_first_merge.py` for the product's first-merge flow | **keep** | 2,861 | 0 | |
| `tools/install/tests/first-hour-contract` | First-hour receipt validator and contract cases | `ci.yml#release` → `release:setup-onboard-journey` uses the first-hour acceptance path that imports `first-hour-contract/check.py` | **keep** | 502 | 0 | |
| `tools/install/tests/first-hour-contract/evidence` | First-hour contract proof records | None found outside the proof history | **delete** | 2,545 | 2,545 | Deleted (2,545 text lines) |
| `tools/install/tests/first-hour/evidence` | First-hour scenario run records | None found outside the proof history | **delete** | 524 | 524 | Deleted (524 text lines) |
| `tools/install/tests/first-hour/providers` | Recording and fault-code producers for first-hour proofs | `ci.yml#release` → `release:setup-onboard-journey` → `test_first_merge.py` uses `journey.py`, which loads `providers/codes.py` | **keep** | 577 | 0 | |
| `tools/install/tests/first-hour/providers/evidence` | Saved first-hour provider proofs | None found outside the proof history | **delete** | 131 | 131 | Deleted (131 text lines) |
| `tools/install/tests/init` | Project init contract and fake GitHub | `ci.yml#release` → `release:setup-onboard-init` runs `test_init.py` for the installed init tool | **keep** | 582 | 0 | |
| `tools/install/tests/init/evidence` | Saved init fixture runs | None found outside the proof history | **delete** | 427 | 427 | Deleted (427 text lines) |
| `tools/install/tests/journey` | Synthetic installer-to-product journey | `ci.yml#always` → `always:checks` → `tests/checks/skills.rs::install_journey_and_live_kit_pass` runs `test_journey.py` | **keep** | 888 | 0 | |
| `tools/install/tests/onboard` | Onboarding journey fixture and fakes | `ci.yml#always` → `always:checks` → `tests/checks/skills.rs::onboard_journey_fixtures_pass` runs `test_journey.py` against WizSkills `onboard` | **keep** | 1,248 | 0 | |
| `tools/install/tests/onboard/evidence` | Historical onboard journey runs | None found outside the proof history | **delete** | 342 | 342 | Deleted (342 text lines) |
| `tools/install/tests/onboard/journeys` | Synthetic first-fleet journey fixture | `ci.yml#always` → `always:checks` → `onboard_journey_fixtures_pass` → `tools/install/tests/onboard/test_journey.py` reads the fixture | **keep** | 59 | 0 | |
| `tools/install/tests/public-release-security` | Public release security boundary checks | `ci.yml#release` → `release:security-baseline` and `release:security-candidate` guard public packaging | **keep** | 515 | 0 | |
| `tools/install/tests/public-release-security/baseline` | Public-only claims-scan regression suite | `ci.yml#release` → `release:security-baseline` runs `test_baseline.py` | **keep** | 433 | 0 | |
| `tools/install/tests/setup-onboard-contract` | Setup and onboarding receipt validators | `ci.yml#release` → `release:setup-onboard-contract` runs `test_contract.py`. The first-merge and init tests also import `check.py` | **keep** | 796 | 0 | |
| `tools/install/tests/setup-onboard-contract/evidence` | Historical setup/onboard contract runs | None found outside the proof history | **delete** | 2,263 | 2,263 | Deleted (2,263 text lines) |
| `tools/live-smoke` | Combined release smoke runner and receipt verifier | Product release check `tools/release/candidate.py` imports `receipt.py` and checks the candidate's agent-run smoke receipt | **keep** | 4,063 | 0 | |
| `tools/live-smoke/evidence` | Saved combined smoke implementation proofs | None found in the release gate. It verifies the current candidate's receipt and preserved run state | **delete** | 0 | 0 | Deleted (0 text lines) |
| `tools/live-smoke/evidence/772` | Release smoke scope proof archive | Parent delete. No current release gate reads these records | **delete** | 431 | 431 | Deleted (431 text lines) |
| `tools/live-smoke/evidence/828` | Engine-retirement smoke proof archive | Parent delete. No current release gate reads these records | **delete** | 167 | 167 | Deleted (167 text lines) |
| `tools/open-import` | Public import and frozen repository guards | `ci.yml#changes` runs `guard.py` and uses `import.py` for public tree inspection. `frozen.yml#frozen` runs `frozen.py` | **keep** | 2,520 | 0 | |
| `tools/open-import/fixtures` | Saved grill-index red run | None found. The only tracked file is `grill-index-red.txt`. `ci.yml#changes` runs `test_guard.py` with its own inputs | **delete** | 39 | 39 | Deleted (39 text lines) |
| `tools/open-settings` | Public cut-over settings apply and recovery tool | None found in a workflow, skill or product. Only the cut-over runbook and offline tests were found | **delete** | 2,070 | 2,070 | Deleted (2,070 text lines) |
| `tools/open-settings/fixtures` | Synthetic settings and recovery inputs | Parent delete. Only the cut-over settings tool's tests | **delete** | 135 | 135 | Deleted (135 text lines) |
| `tools/open-tickets` | ClosedWiz ticket and PR migration tooling | None found beyond tests and test enumeration. `ci.yml#release` still runs `release:open-tickets`, and the dispatcher and shard fixtures enumerate it | **delete** | 5,755 | 5,755 | Deleted (5,755 text lines) |
| `tools/ops-live` | Prepared bounded operations acceptance kit | No executing caller found. `ci.yml#release` runs offline acceptance tests. #439 and open follow-ups #548 and #659 still refer to the kit | **delete** | 1,843 | 1,843 | Deleted (1,843 text lines) |
| `tools/ops-live/controls` | Evidence limits and bindings for the proposed ops kit | Parent delete. The acceptance kit and `release:ops-live-controls` are the only found consumers | **delete** | 681 | 681 | Deleted (681 text lines) |
| `tools/ops-live/controls/evidence` | Saved control-kit proof records | Parent delete. No executing caller found | **delete** | 118 | 118 | Deleted (118 text lines) |
| `tools/ops-live/controls/fixtures` | Synthetic valid and refused control kits | Parent delete. `test_kit.py` is the fixture consumer | **delete** | 47 | 47 | Deleted (47 text lines) |
| `tools/privacy-check` | Privacy checks for commits, trees and PR text | `privacy.yml#privacy` runs `ci.py`. Git's `pre-push` hook runs `hook.py` | **keep** | 2,174 | 0 | |
| `tools/release` | Build, review, approval and publishing entrypoints | `packages.yml#package` runs `build_products.py`, `product_identity.py` and `package.py`. The ADR 0020 release procedure uses `tools/release/release` | **keep** | 13,727 | 0 | |
| `tools/release/__pycache__` | Tracked compiled export-review test cache | None found. Release CI runs the Python test source | **delete** | 0 | 0 | Deleted (0 text lines) |
| `tools/release/evidence` | Saved release and packaging proof records | None found in the active candidate verifier or package job | **delete** | 0 | 0 | Deleted (0 text lines) |
| `tools/release/evidence/1281` | Export-plan and review proof archive | Parent delete. The candidate verifier uses current release evidence | **delete** | 500 | 500 | Deleted (500 text lines) |
| `tools/release/evidence/739` | Release package proof archive | Parent delete. `packages.yml#package` generates its own artifact evidence | **delete** | 420 | 420 | Deleted (420 text lines) |
| `tools/release/public` | Public release instructions template used as a negative fixture | `ci.yml#release` → `release:test` → `test_backfill.py::test_r3_historical_keeps_the_published_releasing_not_the_current_template` reads it to guard immutable release backfills | **keep** | 119 | 0 | |
| `tools/review-relay` | Legacy minute relay and prepared ops inbox adapter | No enabled route established by repository search. `ci.yml#always`, `#release` and `#launch-fleet` run router or inbox fixtures. The skills' finite wakes read GitHub independently when inbox delivery is absent | **delete** | 2,037 | 2,037 | Deleted (2,037 text lines) |
| `tools/review-relay/fixtures` | Synthetic relay and inbox inputs | Parent delete. Relay and router fixtures are the readers | **delete** | 73 | 73 | Deleted (73 text lines) |
| `tools/roadmap` | Release roadmap generator | `tools/release/entry.py` calls `roadmap.py --public` for the product release check. `loops/README.md` also documents standalone private and public regeneration | **keep** | 1,507 | 0 | |
| `tools/roadmap/fixtures` | Synthetic issue, milestone and tag reads | The product's `tools/release/entry.py` invokes `roadmap.py`, which is covered by `tools/roadmap/test.py` with these fixtures | **keep** | 244 | 0 | |
| `tools/scale-50` | Scale-report schema, validator and comparison CLI | `ci.yml#release` → `release:fleet-load` → `tools/fleet-load/scale.py` loads `report.py`. #81 and #85 reference the report contract | **move** to `tools/fleet-load/scale-50/` | 516 | 0 | Moved (0 text lines removed) |
| `tools/scale-50/fixtures` | Scale-report and workload inputs | `ci.yml#release` → `release:fleet-load` → `scale.py` reads `workload-v1.json`. The moved validator tests use the other cases | **move** to `tools/fleet-load/scale-50/fixtures/` | 170 | 0 | Moved (0 text lines removed) |
| `tools/skills-eval` | Skill evaluation runner, records and scoring | `war-room.yml#preview` and `#publish` reach the collector's `sources.py`, which loads `records.py` for scored metrics | **keep** | 6,013 | 0 | |
| `tools/skills-eval/cases` | Canonical evaluation cases and required coverage | The `tools/skills-eval/weekly/run.py` loop entrypoint reads this directory. The evaluator's `eval.py` loads and hashes these cases | **keep** | 12,120 | 0 | |
| `tools/skills-eval/precheck` | Experiment eligibility checker | `tools/war-room/experiments/controls.py` loads `test_contract.py` for the precheck assessment. Preserve this dependency under #979 | **keep** | 531 | 0 | |
| `tools/skills-eval/precheck/contract-fixtures` | Synthetic precheck records | The retained War Room controls proof `tools/war-room/experiments/test_controls.py` reads these inputs for the assessment path | **keep** | 417 | 0 | |
| `tools/skills-eval/promotions` | Standalone weights promotion command | No current workflow, product or skill invocation found. The promotion fixture and #979 dependency checks exercise or inspect it | **delete** | 361 | 361 | Deleted (361 text lines) |
| `tools/skills-eval/replay` | Replay experiment and score examiner | No workflow or skill invocation of `run.py` or `score.py` found. Keep the contract fixtures below for the collector proof and check the #979 experiment split before dropping these runners | **delete** | 1,332 | 1,332 | Deleted (1,332 text lines) |
| `tools/skills-eval/replay/contract-fixtures` | Paired and incomplete replay records | `war-room-proof.yml#proof` → `tools/collector/test_experiment_contract.py` reads this contract corpus | **keep** | 277 | 0 | |
| `tools/skills-eval/weekly` | Weekly evaluation collection and routing loop | The documented Cloudroom loop `Skills-eval weekly mistakes (CF4 E3)` reads the weekly runbook and uses `run.py` and `collect.py`. The checked-in definition names the caller. Deployment was unverified | **keep** | 2,359 | 0 | |
| `tools/stall-alarm` | Factory stall detector used by the collector | `war-room.yml#preview` and `#publish` reach `tools/collector/collect_factory.py`, which imports `alarm.py`. The stall-alarm runbook also defines a Local loop that invokes it | **keep** | 1,455 | 0 | |
| `tools/stall-alarm/evidence` | Saved stall alarm red/green records | None found. The loop and collector read the current observation | **delete** | 96 | 96 | Deleted (96 text lines) |
| `tools/test-value` | Coverage measurements and unread-fixture detection | CW1 and CW19 name this kit for the current cleanup. `ci.yml#release` runs `release:test-value` and `release:test-value-unread-fixtures` for these two live maintainer tools | **keep** | 1,103 | 0 | |
| `tools/test-value/evidence` | Tracked ledgers and measurements from the preceding test-value campaign | CW2–CW6 and CW10–CW11 extend the test-value ledger work. Keep the historical keeper decisions and baselines available during this wave | **keep** | 0 | 0 | |
| `tools/test-value/evidence/baseline` | Previous campaign's per-target baseline | The current test-value pass uses it as comparison context. `tools/test-value/README.md#the-baseline` enumerates the results | **keep** | 930 | 0 | |
| `tools/test-value/evidence/red` | Historical kit implementation red logs | None found. Current measurements and fixture sweeps do not read the red logs | **delete** | 112 | 112 | Deleted (112 text lines) |
| `tools/test-value/evidence/tv10` | Historical test dispositions and measurements | CW2 can reuse the prior loops dispositions from this ledger under spec #1141's testing decisions. Its caller is the current test pass | **keep** | 361 | 0 | |
| `tools/test-value/evidence/tv11` | Historical test dispositions and measurements | CW2 can reuse the prior service dispositions from this ledger under spec #1141's testing decisions. Its caller is the current test pass | **keep** | 713 | 0 | |
| `tools/test-value/evidence/tv12` | Historical test dispositions and measurements | CW11 can reuse the prior WizSkills and CI classifier dispositions from this ledger under spec #1141's testing decisions. Its caller is the current test pass | **keep** | 625 | 0 | |
| `tools/test-value/evidence/tv3` | Historical test dispositions and measurements | CW4 can reuse the prior P1–P12 dispositions from this ledger under spec #1141's testing decisions. Its caller is the current test pass | **keep** | 498 | 0 | |
| `tools/test-value/evidence/tv4` | Historical test dispositions and measurements | CW2 can reuse the prior fleet dispositions from this ledger under spec #1141's testing decisions. Its caller is the current test pass | **keep** | 676 | 0 | |
| `tools/test-value/evidence/tv5` | Historical test dispositions and measurements | CW3 can reuse the prior web API dispositions from this ledger under spec #1141's testing decisions. Its caller is the current test pass | **keep** | 709 | 0 | |
| `tools/test-value/evidence/tv6` | Historical test dispositions and measurements | CW3 can reuse the prior new-thread dispositions from this ledger under spec #1141's testing decisions. Its caller is the current test pass | **keep** | 663 | 0 | |
| `tools/test-value/evidence/tv7` | Historical test dispositions and measurements | CW3 can reuse the prior messaging dispositions from this ledger under spec #1141's testing decisions. Its caller is the current test pass | **keep** | 620 | 0 | |
| `tools/test-value/evidence/tv8` | Historical test dispositions and measurements | CW3 can reuse the prior attachments dispositions from this ledger under spec #1141's testing decisions. Its caller is the current test pass | **keep** | 440 | 0 | |
| `tools/test-value/evidence/tv9` | Historical test dispositions and measurements | CW4 can reuse the prior checks and CLI-agent dispositions from this ledger under spec #1141's testing decisions. Its caller is the current test pass | **keep** | 644 | 0 | |
| `tools/wizskills` | Pinned WizSkills release installer and contract checks | `ci.yml#always` checks the installed skill contracts. `packages.yml#package` installs the pinned skill release before packaging it | **keep** | 1,062 | 0 | |
