# Docs table: every Markdown file, and the before score

DS1 (#1299) of the docs cleanup spec (#1293). One row per Markdown file in the pinned tree, with keep, rewrite, move or delete and the reason. Jake reads it before anything moves or goes (DS2, #1300); DS3 to DS7 do their rows; DS8 (#1306) adds the after score and completes **Where it went**.

## Pins

| What | Pin |
| --- | --- |
| OpenWiz tree measured | `main` at `a361f5f7f8b7c0d2991abe9afc050886e0ad86fd`, tree `83a5be3517f2dda5290ec2441356622f2f743d2d` (2026-11-19) |
| Skills an OpenWiz agent gets | WizSkills 0.1.2, `c112b993d0ec582d2aae370cf8011810fde9aea2` (`wizskills.lock`) |
| Measurement harness | WizSkills `tools/measure/static-count.cjs` at `2beb7476f09bb01f0d2956890cba01805f6a66dc` (sha256 `e0aa8fa1…0eb2c15`); it reproduces `tools/measure/evidence/static-baseline.json` byte for byte |
| Tokenizer | `js-tiktoken` 1.0.21, `o200k_base` (MIT), installed in a temporary directory outside the checkout, as the harness README says |
| Line count | Python `splitlines()` on each blob at the pin, the harness README's rule |
| OpenWiz tree measured after (DS8) | `main` at `d5cf339f29d952853bcfcda6a5bcde0a026b131f`, tree `8ed5a01fd651036a30ff246938177687d65c606f` (2026-11-20), after DS3 to DS7 merged; the same pin `wizskills.lock`, harness (same sha256), tokenizer and line rule |

## The before score

**Representative ticket: #1299** (this ticket), started under the pinned `build-ticket`. It loads no folder instructions, so it is the floor every ticket pays. DS8 measures the same two cases at its own pin.

- **Required at start:** AGENTS.md; what AGENTS.md says to read or check before work (STATUS.md, the open development contract); the settings the pinned `build-ticket` reads first (`docs/agents/` fleet, helpers, issue-tracker, triage-labels, domain); and GLOSSARY.md, which `domain.md` says to read before exploring.
- **Every AGENTS.md link:** the required set plus every other repository Markdown file AGENTS.md links. An upper bound: most are "read when relevant". Its non-Markdown links (`ci.yml`, `ci-reads.txt`, `.githooks/pre-push`) are code, outside the metric.

| File | Tokens |
| --- | ---: |
| `AGENTS.md` | 4,839 |
| `STATUS.md` | 9,106 |
| `contracts/open-development.v1.md` | 10,781 |
| `docs/agents/fleet.md` | 10,941 |
| `docs/agents/helpers.md` | 3,396 |
| `docs/agents/issue-tracker.md` | 1,379 |
| `docs/agents/triage-labels.md` | 241 |
| `docs/agents/domain.md` | 715 |
| `GLOSSARY.md` | 1,389 |
| `apps/web/AGENTS.md` (link only) | 1,425 |
| `contracts/ci-selection.v1.md` (link only) | 3,829 |
| `contracts/review-loops.v2.md` (link only) | 2,272 |
| `contracts/web-api.v1.md` (link only) | 18,989 |
| `docs/adr/0015-live-tests-on-the-pc.md` (link only) | 332 |
| `docs/adr/0020-release-on-demand.md` (link only) | 670 |
| `release/openwiz/RELEASING.md` (link only) | 1,092 |
| `release/openwiz/docs/architecture.md` (link only) | 3,887 |
| `release/openwiz/docs/workflow.md` (link only) | 2,493 |
| `tests/fixtures/README.md` (link only) | 1,907 |
| `tools/wizskills/README.md` (link only) | 445 |
| **Required at start** | **42,787** |
| **Every AGENTS.md link** | **80,128** |

| Score | Before (this pin) | After (DS8) |
| --- | ---: | ---: |
| Tokens at ticket start, required | 42,787 | 18,487 |
| Tokens at ticket start, every AGENTS.md link | 80,128 | 20,406 |
| Markdown files | 612 | 495 |
| Markdown lines | 42,739 | 27,982 |

The after numbers and why each kept section stays are in [The after score](#the-after-score-ds8).

Outside the score, for context only: the pinned `skills/build-ticket/SKILL.md` itself is 9,389 tokens (WizSkills, out of this spec's scope). Not measured: what a host injects (system prompt, tool schemas), and actual delivered tokens from a live run; both stay unknown. The spec's 609 files and 41,798 lines were counted earlier; at this pin there are 612 and 42,739 (`wc -l` gives 42,737, because two files end without a newline).

### Markdown lines by folder

| Folder | Files | Lines | Files after | Lines after |
| --- | ---: | ---: | ---: | ---: |
| `contracts/` | 30 | 9,969 | 28 | 8,412 |
| `tools/test-value/` | 33 | 6,559 | 6 | 2,214 |
| `docs/evidence/` | 48 | 3,693 | 2 | 59 |
| `tests/fixtures/` | 17 | 3,304 | 17 | 3,305 |
| `tools/collector/` | 18 | 2,600 | 17 | 2,078 |
| `tools/war-room/` | 28 | 2,095 | 20 | 773 |
| `release/` | 10 | 1,482 | 10 | 1,482 |
| `docs/agents/` | 10 | 1,341 | 9 | 786 |
| `docs/` | 10 | 1,124 | 6 | 617 |
| `changes/` | 233 | 1,045 | 242 | 1,072 |
| `tools/skills-eval/` | 7 | 991 | 7 | 728 |
| `tools/release/` | 3 | 982 | 2 | 216 |
| `apps/web/` | 19 | 975 | 0 | 0 |
| `(root files)` | 7 | 816 | 4 | 423 |
| `tools/install/` | 8 | 737 | 15 | 807 |
| `contracts/fixtures/` | 64 | 602 | 64 | 602 |
| `tools/fleet-load/` | 4 | 445 | 4 | 206 |
| `ci/` | 8 | 440 | 7 | 236 |
| `docs/cleanup/` | 2 | 356 | 5 | 2,492 |
| `tools/live-smoke/` | 1 | 347 | 1 | 60 |
| `tools/stall-alarm/` | 1 | 301 | 1 | 67 |
| `.claude/` | 4 | 240 | 4 | 240 |
| `docs/spikes/` | 2 | 240 | 0 | 0 |
| `tools/open-import/` | 1 | 236 | 1 | 38 |
| `deploy/` | 1 | 218 | 0 | 0 |
| `docs/decisions/` | 3 | 204 | 0 | 0 |
| `docs/security/` | 1 | 181 | 0 | 0 |
| `docs/adr/` | 20 | 163 | 6 | 62 |
| `tests/fleet/` | 1 | 156 | 0 | 0 |
| `tools/ci-overload/` | 1 | 148 | 1 | 25 |
| `apps/site/` | 2 | 143 | 0 | 0 |
| `tools/privacy-check/` | 1 | 129 | 1 | 28 |
| `docs/live-checks/` | 4 | 127 | 0 | 0 |
| `tools/roadmap/` | 3 | 113 | 1 | 30 |
| `tools/wizskills/` | 2 | 96 | 1 | 40 |
| `loops/` | 1 | 55 | 1 | 55 |
| `.github/` | 1 | 34 | 1 | 34 |
| `tests/checks/` | 1 | 25 | 1 | 25 |
| `tests/service/` | 1 | 16 | 0 | 0 |
| `docs/brand/` | 1 | 11 | 1 | 11 |
| `kernel/` | 0 | 0 | 6 | 687 |
| `tools/owned-paths/` | 0 | 0 | 2 | 48 |
| `adapters/` | 0 | 0 | 1 | 24 |
| **Total** | **612** | **42,739** | **495** | **27,982** |

This table itself (`docs/cleanup/docs-table.md`) is not in the pinned tree, so it has no row; DS8's after count includes it.

## The after score (DS8)

Same representative ticket (#1299's two cases), harness, tokenizer and line rule as the before, at the after pin. The skills are still the pinned WizSkills 0.1.2 `build-ticket`, because WS14 (#1187, the WizSkills 0.2.0 pin) has not landed. There is no fixed target (J215, revised), so this reports what was measured.

| File | Before | After | Why it is still required |
| --- | ---: | ---: | --- |
| `AGENTS.md` | 4,839 | 996 | the pinned `build-ticket` reads the project's instructions |
| `STATUS.md` | 9,106 | gone | deleted (DS3) |
| `contracts/open-development.v1.md` | 10,781 | 10,781 | the pin says to read it "when present"; it is WizSkills' carried copy, byte for byte |
| `docs/agents/fleet.md` | 10,941 | 3,183 | the pin reads it first |
| `docs/agents/helpers.md` | 3,396 | absent | deleted (DS7), but the pin still names it: a builder on the pin is sent to a missing file |
| `docs/agents/issue-tracker.md` | 1,379 | 1,379 | the pin fetches the ticket "as `issue-tracker.md` says" |
| `docs/agents/triage-labels.md` | 241 | 241 | the pin reads it for the `needs-info` label |
| `docs/agents/domain.md` | 715 | 715 | the pin reads it for the glossary and ADRs |
| `GLOSSARY.md` | 1,389 | 1,192 | `domain.md` and `AGENTS.md` say to read it |
| **Required at start** | **42,787** | **18,487** | down 24,300 (57%) |
| `changes/README.md` (link only) | not linked | 1,396 | the one AGENTS.md link outside required reading, with ADR 0020 |
| `docs/adr/0020-release-on-demand.md` (link only) | 670 | 523 | |
| **Every AGENTS.md link** | **80,128** | **20,406** | down 59,722 (75%) |

Two more cases at the after pin, for the gap (not in the before):

| Case | Tokens | Files |
| --- | ---: | --- |
| WizSkills `main`'s `build-ticket` (0.2.0, which WS14 would pin) | 17,108 | the required set without `issue-tracker.md`; it still reads `fleet.md` and, before the first public write, the full open development contract |
| Revision 3's aim: AGENTS.md and GLOSSARY.md only | 2,188 | `AGENTS.md`, `GLOSSARY.md` |

**The gap.** Required reading is 18,487 tokens against revision 3's 2,188. The extra 16,299 tokens are five files the pinned skill reads, and 10,781 of them (66%) are the open development contract. The fix is in WizSkills, not here. WS14 (#1187) moves the pin, but WizSkills `main` still reads the contract and `fleet.md`, so the pin move alone leaves 17,108. The fix needs a builder-sized privacy summary, or a skill that sends builders only to the sections they need.

**Markdown.** Files went from 612 to 495 (117 fewer, 19%) and lines from 42,739 to 27,982 (14,757 fewer, 35%), counted at the after pin before this pull request. The 37 Markdown files added since the DS1 pin have no table rows. They are in `kernel/`, `adapters/template/`, `tools/owned-paths/`, `changes/`, this folder and the install fixtures, plus new evidence in `docs/evidence/1335/`, `docs/evidence/1595/` and `tools/test-value/evidence/cw*/`. Lines by folder are in the table above.

**Beside the code cleanup**, at the same two pins and under the same `splitlines()` rule (other text means every other tracked file except symlinks and binary blobs):

| Lines | Before | After | Change |
| --- | ---: | ---: | ---: |
| Markdown | 42,739 (612 files) | 27,982 (495 files) | -35% |
| Other text | 488,646 (2,000 files) | 293,657 (1,443 files) | -40% |
| Markdown's share | 8.0% | 8.7% | the code shrank a little faster |

Still unknown: what a host injects, and the tokens actually delivered in a live run, as in the before. The pinned `build-ticket` SKILL.md is unchanged at 9,389 tokens.

### Why each section stays

Tokens per `##` section, using the same tokenizer.

- **`AGENTS.md`** (996): the opening (79) says what OpenWiz is and points to the glossary. **Start here** (131) installs the pinned skills and the privacy hook; without it, no `skills/` path resolves. **Public and private** (196) has the privacy rules every public write needs. **Where things are** (313) is the map: each row names a path an agent would otherwise search for. **Commands** (159) gives the one test command and two traps no check catches before CI: CI deletes `private/`, and a retargeted pull request. **Live work and approvals** (118) says what needs Jake first; no check enforces it.
- **`GLOSSARY.md`** (1,192): **Work** (501), **Agents** (184) and **Decisions** (275) are the terms the skills use without defining them. **Ops records** (192) is used only by ops-dispatch work, so it could move into that contract.
- **`docs/agents/fleet.md`** (3,183): skills parse the **Builder**, **Builder for small tickets**, **Reviewer** and **Fixer** tables (783), so their headings, columns and rows stay. A builder uses **Supporting edits** (234), **Test commands** (487), **CI checks** (333) and **GitHub identity** (246). **Loop** (106), **Labels** (280) and **Standing merge rules** (666) are for `launch-fleet` and `plan-graph`, which share this file.
- **`docs/agents/issue-tracker.md`** (1,379): **Commands** (521) holds the `gh` forms every skill uses. **Where things live** (179) and **Private records and approval forms** (330) are for `plan-graph` and `triage`. A builder on the pin needs only **Read an issue**. WizSkills `main`'s `ticket.py read` replaces that read. Line 19 now names `openwizdev/OpenWiz` as the development tracker (fixed here, under the fleet's grant).
- **`docs/agents/triage-labels.md`** (241): the five label names, one table.
- **`docs/agents/domain.md`** (715): **Before exploring** (222) points to the glossary, ADRs and grills. **Private storage** (183) says where private records live. **Use the glossary's words** (155) and **Flag ADR conflicts** (42) are short rules. Line 15 now says development is on `openwizdev/OpenWiz` and private records stay private (fixed here).
- **`contracts/open-development.v1.md`** (10,781) stays byte for byte, because `tools/wizskills/check_contracts.py` requires the carried copy to match WizSkills. A builder needs **Words** (230), **What is private** (625), **The pointer** (333) and **Decision sources in documents** (177): about 1,400 tokens, 13% of the file. **Fleet records** (1,721) is for whoever writes records. **The privacy check** (2,306), **The mapping file** (561), **What the importer carries** (352), **What the ticket mover carries** (654), **Repository identity and discovery** (545), **Public approval records** (713) and **What changes for existing readers** (890) serve tools and other skills.

## Totals by action

| Action | Files | Lines |
| --- | ---: | ---: |
| keep | 443 | 16,313 |
| rewrite | 43 | 14,034 |
| move | 123 | 12,130 |
| delete | 3 | 262 |

- **keep:** stays as it is. Fixtures, changelog lines and contracts the code follows stay byte for byte. Each kept contract and tool README says what a reader needs from it.
- **rewrite:** stays, rewritten for the fewest tokens: no history, no repeated rules, no "updated for" notes. Settings a script or skill parses stay byte for byte.
- **move:** goes to the private records at the path in **Where it went**. Every move goes to ClosedWiz `private/openwiz-docs/` under its OpenWiz path, so it can be found again. DS4 owns that folder.
- **delete:** goes; any line still needed folds into the file the reason names.
- **Owner** is the ticket whose owned paths hold the file. `none` means no DS ticket owns it. 9 non-keep rows have no owner: `.claude/skills/export-review/evidence/1845-proof.md`, `.claude/skills/live-quick-check/SKILL.md`, `.claude/skills/live-spike/SKILL.md`, `apps/site/README.md`, `apps/site/test/evidence-1114.md`, `apps/web/docs/evidence/1030/README.md`, `apps/web/docs/evidence/1030/review-1/README.md`, `apps/web/docs/evidence/1030/review-2/README.md`, `ci/select/README.md`. DS2 decides who does each one: a DS ticket widens to it, or #1264 (AP11) removes it with the old web view. Until then, a move that one of these files waits on stays put.
- **Readers first.** A move or delete row that something still links to or names in code says **Waits** and lists those readers. The file moves only after each reader has been updated in the same pass or earlier: its link replaced by the guidance the reader needs, by a working link, or by a private-record pointer. A reader that otherwise stays as it is becomes **rewrite**, and its reason says the link edit is the only change. Code that names a path is listed without judging whether it reads the file or only uses the name as a test sample; the ticket doing the move checks each one. Rows for files #1264 (AP11) or #1160 (CW19) delete first need no DS action.

## ADRs: the three tests

An ADR is kept only when its decision is **non-obvious**, **a real trade-off** and **hard to reverse**. Kept: 0001, 0004, 0007, 0008. Kept and rewritten: 0011 (to its current rule) and 0020. The other 14 fail at least one test and move. Each ADR's row below says which test decided it.

## Readers of removed files

At the pin, 25 Markdown links in files that stay point to a file this table moves or deletes. The links were found by resolving every relative link in each staying file against the tree. Code that names a removed path (full path, outside evidence and import lists) is grouped by target below. The table rows carry the same facts.

| Reader (stays) | Line | Links to | Target action | Reader owner |
| --- | ---: | --- | --- | --- |
| `.claude/skills/live-quick-check/SKILL.md` | 12 | `docs/adr/0016-agents-run-live-tests.md` | move | none |
| `.claude/skills/live-spike/SKILL.md` | 10 | `docs/adr/0015-live-tests-on-the-pc.md` | move | none |
| `AGENTS.md` | 7 | `STATUS.md` | delete | DS3 |
| `AGENTS.md` | 22 | `STATUS.md` | delete | DS3 |
| `AGENTS.md` | 92 | `docs/adr/0015-live-tests-on-the-pc.md` | move | DS3 |
| `README.md` | 9 | `STATUS.md` | delete | DS3 |
| `apps/site/README.md` | 51 | `docs/decisions/public-offer.md` | move | none |
| `ci/select/README.md` | 143 | `docs/evidence/783/planted-red-green.md` | move | none |
| `contracts/feedback.v1.md` | 6 | `docs/decisions/public-feedback.md` | move | DS6 |
| `contracts/fleet.v1.md` | 5 | `STATUS.md` | delete | DS6 |
| `contracts/public-cloudroom-setup.v1.md` | 6 | `docs/decisions/public-cloudroom-setup.md` | move | DS6 |
| `contracts/service.v1.md` | 300 | `docs/adr/0002-no-artificial-cap-on-builders.md` | move | DS6 |
| `docs/adr/0020-release-on-demand.md` | 25 | `docs/adr/0019-agent-live-smoke-gates-publishing.md` | move | DS4 |
| `docs/adr/0020-release-on-demand.md` | 34 | `docs/adr/0016-agents-run-live-tests.md` | move | DS4 |
| `docs/adr/0020-release-on-demand.md` | 36 | `docs/adr/0018-live-checks-early-publish-in-order.md` | move | DS4 |
| `docs/agents/fleet.md` | 72 | `docs/adr/0014-huntr-approves-by-risk-tier.md` | move | DS7 |
| `docs/agents/fleet.md` | 136 | `docs/adr/0002-no-artificial-cap-on-builders.md` | move | DS7 |
| `docs/agents/huntr.md` | 3 | `docs/adr/0014-huntr-approves-by-risk-tier.md` | move | DS7 |
| `docs/first-hour.md` | 35 | `docs/fleets.md` | move | DS4 |
| `tests/fixtures/first-hour/README.md` | 23 | `docs/decisions/public-offer.md` | move | DS7 |
| `tools/install/tests/first-hour/README.md` | 49 | `docs/decisions/public-offer.md` | move | DS5 |
| `tools/release/README.md` | 437 | `tools/release/findings.md` | move | DS5 |
| `tools/test-value/README.md` | 197 | `tools/test-value/evidence/baseline/README.md` | move | DS5 |
| `tools/war-room/README.md` | 736 | `tools/war-room/design/brief.md` | move | DS5 |
| `tools/war-room/README.md` | 961 | `docs/evidence/1097/measurements.md` | move | DS5 |

| Removed file | Code files that name it |
| --- | --- |
| `RELEASING.md` (delete) | `tools/release/review_rules.py`, `tools/release/test_backfill.py`, `tools/release/test_export_review.py` |
| `STATUS.md` (delete) | `.github/actions/changelog/check.py`, `.github/actions/changelog/test_check.py`, `.github/actions/docs-only/test.sh`, `.github/actions/docs-only/test_release_prune.py`, `ci/select/pick.py`, `ci/select/test_pick.py`, `tests/checks/plan_links.rs`, `tools/release/test_review.py`, `tools/roadmap/roadmap.py`, `tools/roadmap/test.py`, `tools/skills-eval/required-text.json`, `tools/skills-eval/test.py` |
| `docs/ROADMAP.md` (move) | `.github/actions/docs-only/test_plan.py`, `tools/github-app/test.py`, `tools/roadmap/roadmap.py`, `tools/roadmap/test.py` |
| `docs/adr/0010-infra-work-has-no-version.md` (move) | `.github/actions/docs-only/test.sh` |
| `docs/decisions/public-offer.md` (move) | `apps/site/test/approved-copy.mjs`, `apps/web/src/components/Setup.tsx` |
| `docs/evidence/1097/measurements.md` (move) | `tools/war-room/budgets.tsv` |
| `docs/evidence/ci2-batch-proof.md` (move) | `ci/main-batch/admit.py` |
| `docs/evidence/ci2-pr-cuts.md` (move) | `tools/open-import/test_import.py` |
| `docs/fleets.md` (move) | `tools/release/test_backfill.py` |
| `docs/security/public-release-review.md` (move) | `tools/open-import/test_import.py` |
| `docs/spikes/ops-dispatch.md` (move) | `tools/open-import/test_import.py` |
| `tools/test-value/evidence/tv12/ledger.md` (move) | `tests/checks/skills.rs` |

## Comments and doc blocks that teach rejected patterns

Rejected patterns, by the decision that rejected them: 2 + 1 reviews (review-loops v2: 1 + 1); Codex fast mode and Terra (Jake, 2026-11-06 and 2026-11-07, in `docs/agents/fleet.md`); per-step live approval (ADR 0016); the private export and its final-diff gate (ADR 0020); the terminal app (#776); helper agents (WizSkills `build-ticket` at `2beb747` makes them future ideas to benchmark before adoption; this spec's ticket briefs say no helper agents; the 0.1.2 pin still describes them). Comments that only repeat the code are out of scope.

| Where | Action | Reason | Owner |
| --- | --- | --- | --- |
| `tools/live-smoke/smoke.py:44-45` | rewrite | "The no-argument TUI always connects there" in the present tense; the terminal app was removed (#776) | DS8 |
| `tests/checks/skills.rs:4` | rewrite | points to `tools/test-value/evidence/tv12/ledger.md`, which moves | DS8 |
| `contracts/fleet-tick.v1.md:153,162` | rewrite | "2 + 1 diagnoses" | DS6 |
| `contracts/ops-dispatch.v1.md:197,306` | rewrite | "2 + 1 correction counts" | DS6 |
| `docs/adr/0017-codex-reviews-small-polish-prs.md` | move | Codex fast mode and Terra reviewers | DS4 |
| `docs/live-checks/0.0.12.md`, `0.0.12-parts/answer.md`, `send.md` | move | steps drive `openwiz ui`, which was removed | DS4 |
| `release/openwiz/docs/workflow.md`, `architecture.md`, `decisions.md`, `overview.md` | keep (frozen) | old 2 + 1 wording; AGENTS.md stops pointing agents to them (DS3) | DS3 |
| `docs/agents/fleet.md:27,76,97-139` | rewrite | Haiku helper profiles and swarm sizes; WizSkills main defers helpers. Machine-read tables stay byte for byte unless a skill stops reading them | DS7 |
| `docs/agents/helpers.md` | rewrite | the helper procedure; the 0.1.2 pin still reads it, WizSkills main defers it | DS7 |
| 20 comment lines in 14 test files, e.g. `tests/proof/p04_partial_failures.rs:337` ("after the internal Haiku review") | keep | review-round history, not a rule an agent would copy; out of scope | none |
| `ci/main-batch/admit.py:2-10` (C12 "switch gate" docstring) | unknown | `docs/agents/fleet.md` says it no longer gates main pushes; whether the docstring still describes a live path is not established | DS8 |

`crates/core/src/fleet/model.rs:123` and `tests/messaging/m13_drift.rs:2` state the current rule (the `room-cli` version is never a gate) and stay.

## The after sweep (DS8)

The DS8 rows above, and a search of every kept file outside `release/openwiz/`, `changes/`, `CHANGELOG.md` and this folder for each rejected pattern: `2 + 1`, `Haiku`, `swarm`, helper agents, `fast mode` or `service-tier`, `Terra`, `openwiz ui` or `TUI` or `terminal app`, `final-diff`, `private export`, and `STATUS.md`.

| Where | Outcome |
| --- | --- |
| `tools/live-smoke/smoke.py:44-45` and the `refuse_reserved_port` docstring | rewritten here: the terminal app is described as removed (#776), and why its launch forms still refuse stays |
| `tests/checks/skills.rs:4` | already fixed by DS5 (PR #1492): it points to the private records |
| `ci/main-batch/admit.py:2-10` | keep: the docstring says what the offline script does when run. No workflow runs it, only its own test, and its default answer is today's per-push behaviour. No decision rejects it; whether `ci/main-batch/` stays is code cleanup |
| `contracts/fleet-tick.v1.md` "2 + 1" | fixed by DS6 (PR #1494) |
| `contracts/ops-dispatch.v1.md:197,306` "2 + 1" | still here: WizSkills' carried copy, byte for byte. WizSkills `main` already drops both, so they go when WS14 (#1187) moves the pin |
| `contracts/open-development.v1.md` example "every Codex thread runs in fast mode" | still here: a synthetic example of a source line that names a rejected setting; carried, and WizSkills `main` still has it. A WizSkills follow-up |
| `docs/agents/fleet.md` helper profiles, `docs/agents/helpers.md` | gone (DS7, PR #1491) |
| `docs/agents/issue-tracker.md:19`, `docs/agents/domain.md:15` | rewritten here (the fleet's grant on #1306): they named ClosedWiz as the development checkout from before the cut-over; development is on `openwizdev/OpenWiz`, and private records stay private |
| `docs/agents/huntr.md:44` `gpt-6.1-terra` | keep: Terra hunters are huntr's current setting; the rejected use was Terra reviewers |
| Test comments naming the internal Haiku review | keep, as DS1 found: round history, out of scope |
| `STATUS.md` | `tools/roadmap/README.md` no longer names it, and `tools/roadmap/fixtures/STATUS.md` went with DS4 (PR #1708). What remains are classifier and test sample paths, not readers |

### Links

Every relative Markdown link in every tracked `.md` file is resolved as GitHub renders it (folders, `README.md`, heading anchors; `skills/` against the installed pin), with fenced and inline code skipped through `tools/release/scans.py`'s `prose` and `markdown_links`. At the after pin: 346 links (348 at this head, with this table's two anchor links), 8 unresolved. At the DS1 pin: 590 links, 30 unresolved. None of the 8 points to a file this cleanup removed, and all 8 were already there at the DS1 pin. Five are in the carried WizLoops contracts (`contracts/wizloops-*.v1.md`), relative to WizLoops' own tree. One is a fixture's link into its synthetic release tree (`tests/fixtures/release/export-review/l2/README.md`). Two are in `tools/release/public/RELEASING.md`, a template copied to a public root, where they resolve.

## Reproduce

```sh
# the table against the tree: every Markdown file exactly once
git ls-tree -r --name-only a361f5f7f8b7c0d2991abe9afc050886e0ad86fd | grep '\.md$' | sort > /tmp/tree.txt
grep -oE '^\| `[^`]+\.md` \| [0-9]+ \| (keep|rewrite|move|delete) \|' docs/cleanup/docs-table.md | cut -d'`' -f2 | sort > /tmp/rows.txt
diff /tmp/tree.txt /tmp/rows.txt && uniq -d /tmp/rows.txt   # no output: each file once

# the before score: manifest below saved as manifest.json, run from the OpenWiz checkout
tok=$(mktemp -d)
npm install --prefix "$tok" --no-save --ignore-scripts --package-lock=false js-tiktoken@1.0.21
node <WizSkills>/tools/measure/static-count.cjs manifest.json "$tok/node_modules/js-tiktoken"

# readers of removed files: every staying file's relative links that land on a move or delete row
python3 -I - <<'PY'
import re, subprocess, posixpath
C = 'a361f5f7f8b7c0d2991abe9afc050886e0ad86fd'
rows = re.findall(r'^\| `([^`]+\.md)` \| \d+ \| (\w+) \|', open('docs/cleanup/docs-table.md').read(), re.M)
gone = {p for p, a in rows if a in ('move', 'delete')}
for p, a in rows:
    if p in gone: continue
    text = subprocess.run(['git', 'cat-file', 'blob', f'{C}:{p}'], capture_output=True).stdout.decode()
    for n, line in enumerate(text.splitlines(), 1):
        for u in re.findall(r'\]\(([^)\s#]+)', line):
            t = u[1:] if u.startswith('/') else posixpath.normpath(posixpath.join(posixpath.dirname(p), u))
            if not re.match(r'^[a-z]+:', u) and t in gone: print(f'{p}:{n} -> {t}')
PY
```

```json
{
  "commit": "a361f5f7f8b7c0d2991abe9afc050886e0ad86fd",
  "workflows": {
    "ticket-start.1299.required": [
      "AGENTS.md",
      "STATUS.md",
      "contracts/open-development.v1.md",
      "docs/agents/fleet.md",
      "docs/agents/helpers.md",
      "docs/agents/issue-tracker.md",
      "docs/agents/triage-labels.md",
      "docs/agents/domain.md",
      "GLOSSARY.md"
    ],
    "ticket-start.1299.all-links": [
      "AGENTS.md",
      "STATUS.md",
      "contracts/open-development.v1.md",
      "docs/agents/fleet.md",
      "docs/agents/helpers.md",
      "docs/agents/issue-tracker.md",
      "docs/agents/triage-labels.md",
      "docs/agents/domain.md",
      "GLOSSARY.md",
      "apps/web/AGENTS.md",
      "contracts/ci-selection.v1.md",
      "contracts/review-loops.v2.md",
      "contracts/web-api.v1.md",
      "docs/adr/0015-live-tests-on-the-pc.md",
      "docs/adr/0020-release-on-demand.md",
      "release/openwiz/RELEASING.md",
      "release/openwiz/docs/architecture.md",
      "release/openwiz/docs/workflow.md",
      "tests/fixtures/README.md",
      "tools/wizskills/README.md"
    ]
  }
}
```

## Reproduce the after (DS8)

Run from the OpenWiz checkout at the after pin, with `$tok` and `<WizSkills>` as above; every check prints nothing wrong and exits 0, except the links check, which lists the 8 known links in [Links](#links) and exits 1.

```sh
# the after score: the after manifest below saved as after.json; the same harness and tokenizer as the before
node <WizSkills>/tools/measure/static-count.cjs after.json "$tok/node_modules/js-tiktoken"
! grep -nE '^\| (Tokens at ticket start|Markdown).* \| unknown \|$' docs/cleanup/docs-table.md   # no After is unknown

# Markdown files and lines at a commit (Python splitlines() on each blob, as the before), and other text beside them
python3 -I - d5cf339f29d952853bcfcda6a5bcde0a026b131f <<'PY'
import subprocess, sys
rows = subprocess.run(['git', 'ls-tree', '-r', sys.argv[1]], capture_output=True, text=True).stdout.split('\n')
paths = [r.split('\t', 1)[1] for r in rows if r.startswith('100')]   # files, not symlinks
md, other = [0, 0], [0, 0]
for p in paths:
    b = subprocess.run(['git', 'cat-file', 'blob', f'{sys.argv[1]}:{p}'], capture_output=True).stdout
    if b'\0' in b[:8000]: continue
    try: n = len(b.decode().splitlines())
    except UnicodeDecodeError: continue
    c = md if p.endswith('.md') else other
    c[0] += 1; c[1] += n
print('markdown', md, 'other text', other)   # [files, lines]
PY

# where it went: a row still in the tree says nothing (or "not moved"); a gone row says where it went.
# CLOSEDWIZ=<private checkout at main> also checks each moved file against its last OpenWiz blob, byte for byte.
python3 -I - <<'PY'
import re, os, subprocess, sys
rows = re.findall(r'^\| `([^`]+\.md)` \| \d+ \| (\w+) \| .*? \| (.*?) \| \S+ \|$', open('docs/cleanup/docs-table.md').read(), re.M)
cw = os.environ.get('CLOSEDWIZ')
def git(*a, cwd='.'): return subprocess.run(['git', '-C', cwd, *a], capture_output=True, text=True).stdout.strip()
bad = 0
for p, a, w in rows:
    here = os.path.exists(p)
    if here:
        ok = w == '' or w.startswith('not moved')
    elif w.startswith('ClosedWiz'):
        ok = w.startswith(f'ClosedWiz `private/openwiz-docs/{p}`')
        if ok and cw:
            last = git('log', '-1', '--format=%H', 'HEAD', '--', p)
            ok = git('rev-parse', f'{last}^:{p}') == git('hash-object', f'private/openwiz-docs/{p}', cwd=cw)
    else:
        ok = w.startswith('deleted by')
    if not ok:
        bad += 1; print(f'{p}: {a}, {"present" if here else "gone"}, where: {w or "(empty)"}')
print(f'where-it-went: {len(rows)} rows, {bad} wrong')
sys.exit(1 if bad else 0)
PY

# links: every relative link in every tracked .md resolves (run python3 -I tools/wizskills/install.py first, so skills/ resolves)
python3 -I - <<'PY'
"""Every relative Markdown link in every tracked .md file resolves, as GitHub renders it.
Reuses tools/release/scans.py's prose (skip fenced code), markdown_links and anchors."""
import sys, subprocess, posixpath, re, os
from urllib.parse import urlsplit, unquote
from html import unescape
root = '.'
sys.path.insert(0, root + '/tools/release')
import scans
files = set(subprocess.run(['git','-C',root,'ls-files'],capture_output=True,text=True,check=True).stdout.split('\n'))-{''}
texts = {}
def text(p):
    if p not in texts: texts[p] = open(f'{root}/{p}', encoding='utf-8').read()
    return texts[p]
bad = 0; n = 0
for p in sorted(f for f in files if f.endswith('.md')):
    t = re.sub(r'(`+)[^`\n].*?\1', '', scans.prose(text(p)))   # inline code is never a link
    refs, inline, _ = scans.markdown_links(t)
    for url in inline + list(refs.values()):
        u = urlsplit(unescape(url))
        if u.scheme or u.netloc or url.startswith('<') or url.startswith('mailto'): continue
        name = unquote(u.path)
        if '<' in name or '{' in name: continue   # placeholders such as <N>
        n += 1
        tgt = posixpath.normpath(name[1:] if name.startswith('/') else posixpath.join(posixpath.dirname(p), name)) if name else p
        ok = tgt in files or any(f.startswith(tgt.rstrip('/') + '/') for f in files) or os.path.exists(f'{root}/{tgt}')   # skills/ is the installed pin
        if ok and u.fragment and os.path.isfile(f'{root}/{tgt}') and tgt.endswith('.md'):
            ok = unquote(u.fragment) in scans.anchors(text(tgt) if tgt in files else open(f'{root}/{tgt}').read()) or bool(re.fullmatch(r'L\d+(-L\d+)?', u.fragment))
        if not ok:
            bad += 1; print(f'broken: {p} -> {url}')
print(f'links checked: {n}; broken: {bad}')
sys.exit(1 if bad else 0)
PY

# the sweep's own lines: no present-tense terminal app left in the live-smoke comments
! git grep -nE 'TUI always connects|would fall back to' -- tools/live-smoke/smoke.py
```

```json
{
  "commit": "d5cf339f29d952853bcfcda6a5bcde0a026b131f",
  "workflows": {
    "ticket-start.1299.required": [
      "AGENTS.md",
      "contracts/open-development.v1.md",
      "docs/agents/fleet.md",
      "docs/agents/issue-tracker.md",
      "docs/agents/triage-labels.md",
      "docs/agents/domain.md",
      "GLOSSARY.md"
    ],
    "ticket-start.1299.all-links": [
      "AGENTS.md",
      "contracts/open-development.v1.md",
      "docs/agents/fleet.md",
      "docs/agents/issue-tracker.md",
      "docs/agents/triage-labels.md",
      "docs/agents/domain.md",
      "GLOSSARY.md",
      "changes/README.md",
      "docs/adr/0020-release-on-demand.md"
    ],
    "ticket-start.1299.revision-3": [
      "AGENTS.md",
      "GLOSSARY.md"
    ],
    "ticket-start.1299.wizskills-main": [
      "AGENTS.md",
      "contracts/open-development.v1.md",
      "docs/agents/fleet.md",
      "docs/agents/triage-labels.md",
      "docs/agents/domain.md",
      "GLOSSARY.md"
    ]
  }
}
```

## The table

| Path | Lines | Action | Reason | Where it went | Owner |
| --- | ---: | --- | --- | --- | --- |
| `.claude/skills/export-review/SKILL.md` | 81 | keep | local skill; CI classifier keeps it for its Rust reader |  | none |
| `.claude/skills/export-review/evidence/1845-proof.md` | 46 | move | proof record of #1845 | not moved: still at this path; no DS ticket owns it (Owner `none`) | none |
| `.claude/skills/live-quick-check/SKILL.md` | 74 | rewrite | local skill; CI classifier keeps it for its Rust reader; only change: its links to removed files (line 12 → `docs/adr/0016-agents-run-live-tests.md`) get the needed guidance or a working link, before those files move |  | none |
| `.claude/skills/live-spike/SKILL.md` | 39 | rewrite | local skill agents run before live claims; only change: its links to removed files (line 10 → `docs/adr/0015-live-tests-on-the-pc.md`) get the needed guidance or a working link, before those files move |  | none |
| `.github/actions/changelog/README.md` | 34 | keep | reader needs: how to run the changelog check |  | none |
| `AGENTS.md` | 123 | rewrite | under 60 lines: what, where, one test command, skill pointers; drop enforced rules and history; also its links to removed files (line 7 → `STATUS.md`, line 22 → `STATUS.md`, line 92 → `docs/adr/0015-live-tests-on-the-pc.md`) |  | DS3 |
| `CHANGELOG.md` | 251 | keep | release artifact; site and release tests read it |  | none |
| `CONTRIBUTING.md` | 53 | delete | "Updated for" history; fold any needed line into README | deleted by DS3 #1301 (PR #1490); its needed lines folded into `README.md` | DS3 |
| `GLOSSARY.md` | 126 | rewrite | kept: makes short instructions mean one thing; tighten |  | DS3 |
| `README.md` | 54 | rewrite | what OpenWiz is and how to start, briefly; 100+ code readers check its words; also its links to removed files (line 9 → `STATUS.md`) |  | DS3 |
| `RELEASING.md` | 81 | delete | fold needed lines into README; ADR 0020 and `tools/release/` carry the path; `tools/release/review_rules.py` names it. **Waits** until these readers are updated: named in code by `tools/release/review_rules.py`, `tools/release/test_backfill.py`, `tools/release/test_export_review.py` | deleted by DS3 #1301 (PR #1490); its needed lines folded into `README.md` | DS3 |
| `STATUS.md` | 128 | delete | app and spec pages show status (spec); `tools/roadmap/roadmap.py` writes it, so that reader goes first. **Waits** until these readers are updated: linked from `AGENTS.md:7`, `AGENTS.md:22`, `README.md:9`, `contracts/fleet.v1.md:5`; named in code by `.github/actions/changelog/check.py`, `.github/actions/changelog/test_check.py`, `.github/actions/docs-only/test.sh`, `.github/actions/docs-only/test_release_prune.py`, `ci/select/pick.py`, `ci/select/test_pick.py`, `tests/checks/plan_links.rs`, `tools/release/test_review.py`, `tools/roadmap/roadmap.py`, `tools/roadmap/test.py`, `tools/skills-eval/required-text.json`, `tools/skills-eval/test.py` | deleted by DS3 #1301 (PR #1490); status is read from the app and the spec pages | DS3 |
| `apps/site/README.md` | 62 | rewrite | how to build and test the site; #1264 may delete the site copy; only change: its links to removed files (line 51 → `docs/decisions/public-offer.md`) get the needed guidance or a working link, before those files move | deleted by #1264 AP11 (PR #1404), with the old web view | none |
| `apps/site/test/evidence-1114.md` | 81 | move | proof record of #1114 | deleted by #1264 AP11 (PR #1404), with the old web view | none |
| `apps/web/AGENTS.md` | 28 | keep | folder instructions; #1264 deletes the old web view first | deleted by #1264 AP11 (PR #1404), with the old web view | none |
| `apps/web/docs/design-rules.md` | 435 | keep | rules the web code cites; #1264 deletes the old web view first | deleted by #1264 AP11 (PR #1404), with the old web view | none |
| `apps/web/docs/evidence/1030/README.md` | 72 | move | evidence record | deleted by #1264 AP11 (PR #1404), with the old web view | none |
| `apps/web/docs/evidence/1030/review-1/README.md` | 29 | move | evidence record | deleted by #1264 AP11 (PR #1404), with the old web view | none |
| `apps/web/docs/evidence/1030/review-2/README.md` | 55 | move | evidence record | deleted by #1264 AP11 (PR #1404), with the old web view | none |
| `apps/web/test/fixtures/cloudroom-setup/README.md` | 7 | keep | test fixture | deleted by #1264 AP11 (PR #1404), with the old web view | none |
| `apps/web/test/fixtures/cockpit/README.md` | 8 | keep | test fixture | deleted by #1264 AP11 (PR #1404), with the old web view | none |
| `apps/web/test/fixtures/decisions/README.md` | 9 | keep | test fixture | deleted by #1264 AP11 (PR #1404), with the old web view | none |
| `apps/web/test/fixtures/first-hour-pages/README.md` | 16 | keep | test fixture | deleted by #1264 AP11 (PR #1404), with the old web view | none |
| `apps/web/test/fixtures/install-access/README.md` | 35 | keep | test fixture | deleted by #1264 AP11 (PR #1404), with the old web view | none |
| `apps/web/test/fixtures/install-connections/consumer/README.md` | 5 | keep | test fixture | deleted by #1264 AP11 (PR #1404), with the old web view | none |
| `apps/web/test/fixtures/install-connections/consumer/docs/agents/fleet.md` | 45 | keep | test fixture | deleted by #1264 AP11 (PR #1404), with the old web view | none |
| `apps/web/test/fixtures/install-connections/fleet-empty.md` | 11 | keep | test fixture | deleted by #1264 AP11 (PR #1404), with the old web view | none |
| `apps/web/test/fixtures/install-connections/fleet-merge-scaffold.md` | 46 | keep | test fixture | deleted by #1264 AP11 (PR #1404), with the old web view | none |
| `apps/web/test/fixtures/install-connections/fleet-small-builder-placeholder.md` | 55 | keep | test fixture | deleted by #1264 AP11 (PR #1404), with the old web view | none |
| `apps/web/test/fixtures/install-connections/fleet-template.md` | 95 | keep | test fixture | deleted by #1264 AP11 (PR #1404), with the old web view | none |
| `apps/web/test/fixtures/loops/README.md` | 10 | keep | test fixture | deleted by #1264 AP11 (PR #1404), with the old web view | none |
| `apps/web/test/fixtures/plan/README.md` | 8 | keep | test fixture | deleted by #1264 AP11 (PR #1404), with the old web view | none |
| `apps/web/test/fixtures/ready-stock/README.md` | 6 | keep | test fixture | deleted by #1264 AP11 (PR #1404), with the old web view | none |
| `changes/1007.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1009.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1010.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1012.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1013.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1014.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1027.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1029.md` | 3 | keep | changelog line; `changes/README.md` contract | deleted by #1671 (PR #1728): a changelog line for a feature removed in 0.1.0 | none |
| `changes/1030.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1036.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1037.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1044.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1049.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1050.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1060.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1064.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1074.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1089.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1096.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1097.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1098.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1099.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1100.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1101.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1102.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1103.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1105.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1106.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1107.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1109.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1114.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1196.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1205.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/121.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1262.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1274.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1336.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1451.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1580.md` | 3 | keep | changelog line; `changes/README.md` contract | deleted by #1671 (PR #1728): a changelog line for a feature removed in 0.1.0 | none |
| `changes/1834.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1859.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1881.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1887.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1889.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1892.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1903.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1905.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1914.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1955.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/1998.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2032.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2033.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2034.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2035.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2036.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2038.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2039.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2098.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2134.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2136.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2168.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2200.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2201.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2202.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2203.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2205.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2223.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2229.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2230.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2259.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2262.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2263.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2264.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2292.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2293.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2294.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2376.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2377.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2379.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2514.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2516.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/269.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/270.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/271.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/272.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2786.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2805.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2831.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2847.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2849.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2852.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2857.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2858.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2859.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2860.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2862.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2863.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2865.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2911.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2955.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/2986.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/412.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/413.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/456.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/509.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/516.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/518.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/531.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/535.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/536.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/537.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/539.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/544.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/545.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/546.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/547.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/548.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/549.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/558.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/571.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/591.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/602.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/603.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/606.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/607.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/608.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/610.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/617.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/618.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/619.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/620.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/625.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/626.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/628.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/632.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/633.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/635.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/636.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/637.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/652.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/653.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/654.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/655.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/656.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/659.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/660.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/661.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/662.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/663.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/665.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/677.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/678.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/679.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/713.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/714.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/716.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/717.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/718.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/719.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/720.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/721.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/723.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/732.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/740.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/748.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/749.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/751.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/753.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/770.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/775.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/776.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/778.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/779.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/785.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/786.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/789.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/790.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/791.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/792.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/793.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/796.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/797.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/798.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/799.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/800.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/801.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/805.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/823.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/824.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/825.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/829.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/834.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/835.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/839.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/844.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/848.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/852.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/853.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/854.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/856.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/863.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/864.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/866.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/870.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/873.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/874.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/876.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/888.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/889.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/896.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/904.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/912.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/921.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/935.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/941.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/945.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/949.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/962.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/983.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/988.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/README.md` | 101 | keep | the changelog contract |  | none |
| `changes/closedwiz-1096.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/closedwiz-1285.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/closedwiz-636.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/closedwiz-718.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/closedwiz-789.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/closedwiz-790.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/closedwiz-793.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/closedwiz-797.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/closedwiz-799.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/closedwiz-800.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/closedwiz-874.md` | 3 | keep | changelog line; `changes/README.md` contract |  | none |
| `changes/notes/0.0.12.md` | 251 | keep | release note input |  | none |
| `ci/escapes/README.md` | 46 | keep | reader needs: how to find selector escapes |  | none |
| `ci/main-batch/README.md` | 83 | keep | reader needs: the combined-main observation record |  | none |
| `ci/select/README.md` | 149 | rewrite | reader needs: how test selection works and how to test it; only change: its links to removed files (line 143 → `docs/evidence/783/planted-red-green.md`) get the needed guidance or a working link, before those files move | deleted by #1486 CW2-3 (PR #1612), with `ci/select/` | none |
| `ci/selection/README.md` | 112 | keep | reader needs: what the selection fixtures cover |  | none |
| `ci/shard/README.md` | 40 | keep | reader needs: how to run the Rust shards |  | none |
| `ci/wizroom/fixtures/contract/contracts/review.v1.md` | 4 | keep | test fixture |  | none |
| `ci/wizroom/fixtures/contract/tools/war-room/collector.v1.md` | 3 | keep | test fixture |  | none |
| `ci/wizroom/fixtures/none/README.md` | 3 | keep | test fixture |  | none |
| `contracts/agent-github-reads.v1.md` | 199 | keep | reader needs: the routed GitHub read grammar and refusals `read.py` enforces |  | DS6 |
| `contracts/attachment-mime-types.v1.md` | 20 | keep | reader needs: the image MIME extensions `attachment.rs` allows |  | DS6 |
| `contracts/ci-selection.v1.md` | 163 | keep | reader needs: the CI plan record every lane reads, and its ids |  | DS6 |
| `contracts/ci3.v1.md` | 141 | keep | reader needs: the time-to-result measure and cohort the collector computes |  | DS6 |
| `contracts/cli.v1.md` | 276 | keep | reader needs: the commands, flags, JSON and exit codes `openwiz` keeps compatible |  | DS6 |
| `contracts/cockpit.v1.md` | 213 | keep | reader needs: the cockpit read shape; #1264 decides the old web view | deleted by #1264 AP11 (PR #1404), with the old web view | DS6 |
| `contracts/decisions.v1.md` | 406 | keep | reader needs: the decision request and `GET /api/v1/decisions` shapes |  | DS6 |
| `contracts/feedback.v1.md` | 284 | rewrite | reader needs: what feedback sends and what sharing exposes; only change: its links to removed files (line 6 → `docs/decisions/public-feedback.md`) get the needed guidance or a working link, before those files move |  | DS6 |
| `contracts/fixtures/wizloops/README.md` | 113 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/catalog/all-secrets.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid-folder/duplicate-id/a.md` | 7 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid-folder/duplicate-id/b.md` | 7 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/agent-space.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/at-no-offset.md` | 7 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/bad-id.md` | 7 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/bad-param-name.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/bad-placeholder.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/bad-thread.md` | 7 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/bad-timezone.md` | 7 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/blank-line.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/blank-name.md` | 7 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/check-missing.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/check-parent.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/comment-line.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/crlf.md` | 7 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/cron-names.md` | 7 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/cron-out-of-range.md` | 7 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/cron-six-fields.md` | 7 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/duplicate-key.md` | 9 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/duplicate-nested-key.md` | 7 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/duplicate-secret.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/empty-body.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/in-seconds.md` | 7 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/missing-thread.md` | 6 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/missing-timezone.md` | 7 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/multiline-param.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/no-frontmatter.md` | 7 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/no-space.md` | 7 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/null-check.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/param-float.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/param-in-check.md` | 9 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/priority-five.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/priority-float.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/priority-string.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/same-thread-secrets.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/secrets-all.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/secrets-none-string.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/timeout-too-long.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/timezone-only.md` | 7 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/two-triggers.md` | 7 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/unclosed.md` | 6 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/undeclared-param-check.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/undeclared-param-env.md` | 9 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/undeclared-param.md` | 7 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/unknown-agent-key.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/unknown-field.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/unquoted-string.md` | 7 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/unused-param.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/invalid/webhook-false.md` | 7 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/valid/all-secrets-new.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/valid/all-secrets-same.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/valid/at-same.md` | 7 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/valid/cron-check.md` | 12 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/valid/fast-no-check.md` | 7 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/valid/in-same.md` | 9 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/valid/long-check.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/valid/params-env.md` | 9 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/valid/python-check.md` | 9 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/valid/same-thread-agent.md` | 9 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/valid/script-only.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/valid/short-check.md` | 8 | keep | fixture loop tests read |  | DS6 |
| `contracts/fixtures/wizloops/valid/webhook-new.md` | 9 | keep | fixture loop tests read |  | DS6 |
| `contracts/fleet-tick.v1.md` | 539 | rewrite | teaches 2 + 1 diagnoses (review-loops v2 is 1 + 1); keep what the tick code follows |  | DS6 |
| `contracts/fleet.v1.md` | 1456 | rewrite | 1,456 lines with ticket status history; keep only what `openwiz fleet` prints; also its links to removed files (line 5 → `STATUS.md`) |  | DS6 |
| `contracts/github-identity.v1.md` | 296 | keep | reader needs: the App identity, token minting and record authors |  | DS6 |
| `contracts/install.v1.md` | 83 | keep | reader needs: the install bundle: version, source, targets |  | DS6 |
| `contracts/loop-cli.v1.md` | 288 | keep | reader needs: `openwiz loop` arguments, outputs and exit codes |  | DS6 |
| `contracts/loops.v1.md` | 223 | keep | reader needs: the loop definition and run record shapes |  | DS6 |
| `contracts/open-development.v1.md` | 583 | rewrite | 583 lines; keep the privacy rules the checker enforces, drop ticket plan prose |  | DS6 |
| `contracts/ops-dispatch.v1.md` | 307 | rewrite | teaches "2 + 1 correction counts" (now 1 + 1); keep what code follows |  | DS6 |
| `contracts/plan-links.v1.md` | 254 | keep | reader needs: link reasons in ticket bodies and the checker interface |  | DS6 |
| `contracts/plan.v1.md` | 234 | keep | reader needs: the `GET /api/v1/plan` response shape |  | DS6 |
| `contracts/public-cloudroom-setup.v1.md` | 250 | rewrite | reader needs: the CloudRoom setup step: reuse, install, sign-in; only change: its links to removed files (line 6 → `docs/decisions/public-cloudroom-setup.md`) get the needed guidance or a working link, before those files move |  | DS6 |
| `contracts/release-candidate.v1.md` | 239 | keep | reader needs: the checked public build record the release path binds |  | DS6 |
| `contracts/review-loops.v1.md` | 284 | rewrite | v2 supersedes its rounds; keep only the shapes `tools/war-room/review_loops.py` reads, or move |  | DS6 |
| `contracts/review-loops.v2.md` | 183 | keep | reader needs: the 1 + 1 review rule, VERDICT and ruling lines |  | DS6 |
| `contracts/service.v1.md` | 611 | rewrite | 611 lines with ticket status; keep shapes the service prints; #1264 may delete the service; also its links to removed files (line 300 → `docs/adr/0002-no-artificial-cap-on-builders.md`) |  | DS6 |
| `contracts/setup-onboard.v1.md` | 368 | keep | reader needs: install to first merge: steps and records |  | DS6 |
| `contracts/setup.v1.md` | 97 | keep | reader needs: the resumable `GET /api/v1/setup` read |  | DS6 |
| `contracts/web-api.v1.md` | 590 | rewrite | revision history per version; keep routes the server serves; #1264 may delete the server | deleted by #1264 AP11 (PR #1404), with the old web view | DS6 |
| `contracts/wizloops-cloudroom.v1.md` | 395 | keep | reader needs: how a loop file maps to a Cloudroom loop and back |  | DS6 |
| `contracts/wizloops-loop.v1.md` | 376 | keep | reader needs: the loop file format |  | DS6 |
| `contracts/wizroom.v1.md` | 297 | keep | reader needs: what stays public when the war room splits; `ci/wizroom/split.py` checks it |  | DS6 |
| `contracts/wizskills.v1.md` | 314 | keep | reader needs: the WizSkills package and installer interface `install.py` follows |  | DS6 |
| `deploy/pc/README.md` | 218 | keep | PC service setup; `tests/service/t4_setup.rs` reads it; #1264 may delete the service | deleted by #1264 AP11 (PR #1404), with the old web view | none |
| `docs/ROADMAP.md` | 75 | move | marked Private: themes, not specs; `tools/roadmap/roadmap.py` and `tools/github-app/test.py` read it, so those readers change first. **Waits** until these readers are updated: named in code by `.github/actions/docs-only/test_plan.py`, `tools/github-app/test.py`, `tools/roadmap/roadmap.py`, `tools/roadmap/test.py` | ClosedWiz `private/openwiz-docs/docs/ROADMAP.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/adr/0001-one-orchestrator-per-project-one-fleet-per-spec.md` | 5 | keep | non-obvious (parent chain rejected), real trade-off, hard to reverse: fleets are found agent → branch → PR → ticket → spec |  | DS4 |
| `docs/adr/0002-no-artificial-cap-on-builders.md` | 5 | move | real trade-off but easy to reverse: a cap is one setting. **Waits** until these readers are updated: linked from `contracts/service.v1.md:300`, `docs/agents/fleet.md:136` | ClosedWiz `private/openwiz-docs/docs/adr/0002-no-artificial-cap-on-builders.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/adr/0003-skills-first-then-code.md` | 5 | move | done history (0.0.5 to 0.0.6); nothing left to reverse | ClosedWiz `private/openwiz-docs/docs/adr/0003-skills-first-then-code.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/adr/0004-github-layout-for-versions-specs-tickets.md` | 3 | keep | non-obvious (labels and files rejected), real trade-off, hard to reverse: every record uses milestones and sub-issues |  | DS4 |
| `docs/adr/0005-skills-any-harness-agent-invokable.md` | 5 | move | the skills moved to WizSkills; the decision is theirs now | ClosedWiz `private/openwiz-docs/docs/adr/0005-skills-any-harness-agent-invokable.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/adr/0006-rolling-plans-across-versions.md` | 7 | move | superseded in part by 0012; release order is easy to reverse | ClosedWiz `private/openwiz-docs/docs/adr/0006-rolling-plans-across-versions.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/adr/0007-the-fleet-loop-is-separate-from-the-orchestrator.md` | 5 | keep | non-obvious, real trade-off (orchestrator context), hard to reverse: the tick code reads state only from GitHub |  | DS4 |
| `docs/adr/0008-openwiz-merges-tickets-jake-approves-plans.md` | 5 | keep | non-obvious, real trade-off (speed against control), hard to reverse: the merge authority model; `tools/skills-eval/test.py` reads it |  | DS4 |
| `docs/adr/0009-live-tests-run-while-jake-works.md` | 5 | move | a process rule, easy to reverse | ClosedWiz `private/openwiz-docs/docs/adr/0009-live-tests-run-while-jake-works.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/adr/0010-infra-work-has-no-version.md` | 5 | move | a process rule, easy to reverse. **Waits** until these readers are updated: named in code by `.github/actions/docs-only/test.sh` | ClosedWiz `private/openwiz-docs/docs/adr/0010-infra-work-has-no-version.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/adr/0011-one-fleet-thread-per-spec.md` | 7 | rewrite | keep only the current rule (the admitted generation claim); drop the superseded thread-ownership history |  | DS4 |
| `docs/adr/0012-plan-as-far-ahead-as-useful.md` | 5 | move | a planning rule, easy to reverse | ClosedWiz `private/openwiz-docs/docs/adr/0012-plan-as-far-ahead-as-useful.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/adr/0013-huntr-approves-work-of-approved-kinds.md` | 5 | move | superseded by 0014 | ClosedWiz `private/openwiz-docs/docs/adr/0013-huntr-approves-work-of-approved-kinds.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/adr/0014-huntr-approves-by-risk-tier.md` | 5 | move | a policy setting (the tier ceiling), easy to reverse; `docs/agents/fleet.md` and `huntr.md` link it. **Waits** until these readers are updated: linked from `docs/agents/fleet.md:72`, `docs/agents/huntr.md:3` | ClosedWiz `private/openwiz-docs/docs/adr/0014-huntr-approves-by-risk-tier.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/adr/0015-live-tests-on-the-pc.md` | 15 | move | superseded by 0016 (per-step approval); where tests run is easy to reverse; AGENTS.md links it. **Waits** until these readers are updated: linked from `.claude/skills/live-spike/SKILL.md:10`, `AGENTS.md:92` | ClosedWiz `private/openwiz-docs/docs/adr/0015-live-tests-on-the-pc.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/adr/0016-agents-run-live-tests.md` | 11 | move | a live-test policy, easy to reverse. **Waits** until these readers are updated: linked from `.claude/skills/live-quick-check/SKILL.md:12`, `docs/adr/0020-release-on-demand.md:34` | ClosedWiz `private/openwiz-docs/docs/adr/0016-agents-run-live-tests.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/adr/0017-codex-reviews-small-polish-prs.md` | 11 | move | teaches Codex fast mode and Terra, both rejected (2026-11-06 and 11-07); easy to reverse | ClosedWiz `private/openwiz-docs/docs/adr/0017-codex-reviews-small-polish-prs.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/adr/0018-live-checks-early-publish-in-order.md` | 5 | move | a release-order rule, easy to reverse. **Waits** until these readers are updated: linked from `docs/adr/0020-release-on-demand.md:36` | ClosedWiz `private/openwiz-docs/docs/adr/0018-live-checks-early-publish-in-order.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/adr/0019-agent-live-smoke-gates-publishing.md` | 3 | move | superseded in part by 0020. **Waits** until these readers are updated: linked from `docs/adr/0020-release-on-demand.md:25` | ClosedWiz `private/openwiz-docs/docs/adr/0019-agent-live-smoke-gates-publishing.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/adr/0020-release-on-demand.md` | 46 | rewrite | keep: non-obvious, real trade-off (speed against gates), hard to reverse (immutable public releases); drop the status and history lines; also its links to removed files (line 25 → `docs/adr/0019-agent-live-smoke-gates-publishing.md`, line 34 → `docs/adr/0016-agents-run-live-tests.md`, line 36 → `docs/adr/0018-live-checks-early-publish-in-order.md`) |  | DS4 |
| `docs/agents/domain.md` | 49 | keep | settings the skills read (pinned build-ticket) |  | DS7 |
| `docs/agents/fleet.md` | 293 | rewrite | settings the skills and scripts read stay byte for byte; drop source history prose; teaches Haiku helpers (see Comments); also its links to removed files (line 72 → `docs/adr/0014-huntr-approves-by-risk-tier.md`, line 136 → `docs/adr/0002-no-artificial-cap-on-builders.md`) |  | DS7 |
| `docs/agents/github-app.md` | 154 | keep | `tools/github-app/setup.py` reads it; the person's App checklist |  | DS7 |
| `docs/agents/helpers.md` | 118 | rewrite | pinned build-ticket 0.1.2 reads it; WizSkills main defers helpers and ticket briefs say no helper agents; shrink, go when the pin moves | deleted by DS7 #1305 (PR #1491): helpers left required reading (revision 3) | DS7 |
| `docs/agents/huntr.md` | 404 | rewrite | huntr settings stay; 404 lines of prose shrink; also its links to removed files (line 3 → `docs/adr/0014-huntr-approves-by-risk-tier.md`) |  | DS7 |
| `docs/agents/issue-tracker.md` | 55 | keep | settings the skills read (pinned build-ticket) |  | DS7 |
| `docs/agents/roads.md` | 9 | keep | 9 lines: the three roads |  | DS7 |
| `docs/agents/skills-ab.md` | 220 | rewrite | `tools/war-room/experiments/analysis.py` reads its settings; prose shrinks |  | DS7 |
| `docs/agents/skills-eval.md` | 22 | keep | 22 lines: the weekly eval loop setting |  | DS7 |
| `docs/agents/triage-labels.md` | 17 | keep | settings the skills read (pinned build-ticket) |  | DS7 |
| `docs/brand/README.md` | 11 | keep | 11 lines: which logo file to use |  | DS4 |
| `docs/ci3.md` | 196 | keep | `tools/collector/ci3_check.py` parses its BEFORE record |  | DS4 |
| `docs/cleanup/wave1-contracts.md` | 172 | keep | table for open cleanup wave #1141; DS4 and DS7 do not own it; move after #1141 closes | ClosedWiz `private/openwiz-docs/docs/cleanup/wave1-contracts.md` (DS8 #1306, PR #1738) | DS8 |
| `docs/cleanup/wave1-scaffolding.md` | 184 | keep | table for open cleanup wave #1141; DS4 and DS7 do not own it; move after #1141 closes | ClosedWiz `private/openwiz-docs/docs/cleanup/wave1-scaffolding.md` (DS8 #1306, PR #1738) | DS8 |
| `docs/cli.md` | 14 | rewrite | drop the removed terminal app history (#776); keep the command guide |  | DS4 |
| `docs/decisions/public-cloudroom-setup.md` | 48 | move | old decision record. **Waits** until these readers are updated: linked from `contracts/public-cloudroom-setup.v1.md:6` | ClosedWiz `private/openwiz-docs/docs/decisions/public-cloudroom-setup.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/decisions/public-feedback.md` | 78 | move | old decision record. **Waits** until these readers are updated: linked from `contracts/feedback.v1.md:6` | ClosedWiz `private/openwiz-docs/docs/decisions/public-feedback.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/decisions/public-offer.md` | 78 | move | old decision record; `apps/site/test/approved-copy.mjs` and `Setup.tsx` name it. **Waits** until these readers are updated: linked from `apps/site/README.md:51`, `tests/fixtures/first-hour/README.md:23`, `tools/install/tests/first-hour/README.md:49`; named in code by `apps/site/test/approved-copy.mjs`, `apps/web/src/components/Setup.tsx` | ClosedWiz `private/openwiz-docs/docs/decisions/public-offer.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/1026/README.md` | 59 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/1026/README.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/1044/README.md` | 85 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/1044/README.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/1044/red-80dd129.md` | 67 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/1044/red-80dd129.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/1046/init/README.md` | 33 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/1046/init/README.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/1046/login.md` | 35 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/1046/login.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/1049/proof.md` | 57 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/1049/proof.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/1055/README.md` | 126 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/1055/README.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/1058/README.md` | 170 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/1058/README.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/1089/README.md` | 45 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/1089/README.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/1093/README.md` | 80 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/1093/README.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/1093/review-r1.md` | 70 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/1093/review-r1.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/1097/measurements.md` | 165 | move | evidence record. **Waits** until these readers are updated: linked from `tools/war-room/README.md:961`; named in code by `tools/war-room/budgets.tsv` | ClosedWiz `private/openwiz-docs/docs/evidence/1097/measurements.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/783/planted-red-green.md` | 181 | move | evidence record. **Waits** until these readers are updated: linked from `ci/select/README.md:143` | ClosedWiz `private/openwiz-docs/docs/evidence/783/planted-red-green.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/791/green.md` | 22 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/791/green.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/791/red.md` | 145 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/791/red.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/794/README.md` | 41 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/794/README.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/797/README.md` | 39 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/797/README.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/800/README.md` | 136 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/800/README.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/873/screenshots/README.md` | 6 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/873/screenshots/README.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/873/target/brief.md` | 39 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/873/target/brief.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/873/target/generated-prompts.md` | 100 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/873/target/generated-prompts.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/873/target/prompt.md` | 23 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/873/target/prompt.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/874/README.md` | 28 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/874/README.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/936/README.md` | 53 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/936/README.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/946/README.md` | 65 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/946/README.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/ci2-app-installation.md` | 46 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/ci2-app-installation.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/ci2-batch-proof.md` | 410 | move | evidence record. **Waits** until these readers are updated: named in code by `ci/main-batch/admit.py` | ClosedWiz `private/openwiz-docs/docs/evidence/ci2-batch-proof.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/ci2-pr-cuts.md` | 389 | move | evidence record. **Waits** until these readers are updated: named in code by `tools/open-import/test_import.py` | ClosedWiz `private/openwiz-docs/docs/evidence/ci2-pr-cuts.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/github-identity/live-run.md` | 56 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/github-identity/live-run.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/github-identity/red-run.md` | 15 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/github-identity/red-run.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/github-identity/review-1.md` | 44 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/github-identity/review-1.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/openwiz-0.0.16/app-key-handoff.md` | 157 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/openwiz-0.0.16/app-key-handoff.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/openwiz-0.0.16/cloudroom-save-secret.md` | 61 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/openwiz-0.0.16/cloudroom-save-secret.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/openwiz-0.0.16/recording.md` | 90 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/openwiz-0.0.16/recording.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/openwiz-0.0.16/setup-github-login/README.md` | 61 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/openwiz-0.0.16/setup-github-login/README.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/openwiz-0.0.16/setup-github-login/prompts.md` | 37 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/openwiz-0.0.16/setup-github-login/prompts.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/openwiz-0.0.16/setup-onboard-continuation/red-launch-engine.md` | 26 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/openwiz-0.0.16/setup-onboard-continuation/red-launch-engine.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/openwiz-0.0.16/setup-onboard-continuation/red-malformed-store.md` | 11 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/openwiz-0.0.16/setup-onboard-continuation/red-malformed-store.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/openwiz-0.0.16/setup-onboard-continuation/red-not-ready-setup.md` | 16 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/openwiz-0.0.16/setup-onboard-continuation/red-not-ready-setup.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/openwiz-0.0.16/setup-onboard-continuation/red-onboard.md` | 70 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/openwiz-0.0.16/setup-onboard-continuation/red-onboard.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/openwiz-0.0.16/setup-onboard-continuation/red-review-r1-r5.md` | 29 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/openwiz-0.0.16/setup-onboard-continuation/red-review-r1-r5.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/openwiz-0.0.16/setup-onboard-continuation/red-review-r5-writer.md` | 14 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/openwiz-0.0.16/setup-onboard-continuation/red-review-r5-writer.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/openwiz-0.0.16/setup-onboard-continuation/red-review-r6.md` | 14 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/openwiz-0.0.16/setup-onboard-continuation/red-review-r6.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/openwiz-0.0.16/setup-onboard-continuation/targets/README.md` | 20 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/openwiz-0.0.16/setup-onboard-continuation/targets/README.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/public-release-free-only.md` | 75 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/public-release-free-only.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/release-on-demand.md` | 81 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/release-on-demand.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/tv14/proof.md` | 52 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/tv14/proof.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/evidence/war-room-gather-ci-reads.md` | 49 | move | evidence record | ClosedWiz `private/openwiz-docs/docs/evidence/war-room-gather-ci-reads.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/first-hour.md` | 54 | rewrite | user guide; the app links it; only change: its links to removed files (line 35 → `docs/fleets.md`) get the needed guidance or a working link, before those files move |  | DS4 |
| `docs/fleets.md` | 128 | move | 0.0.5 design note, "Status: being grilled"; GLOSSARY and skills carry the words now. **Waits** until these readers are updated: linked from `docs/first-hour.md:35`; named in code by `tools/release/test_backfill.py` | ClosedWiz `private/openwiz-docs/docs/fleets.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/github-app.md` | 197 | keep | user guide; `tools/github-app/test.py` reads it |  | DS4 |
| `docs/how-openwiz-works.md` | 16 | keep | 16-line user overview with its picture |  | DS4 |
| `docs/install.md` | 47 | keep | user install guide; journey test reads it |  | DS4 |
| `docs/live-checks/0.0.12-parts/answer.md` | 15 | move | 0.0.12 live-check kit record; teaches the removed `openwiz ui` | ClosedWiz `private/openwiz-docs/docs/live-checks/0.0.12-parts/answer.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/live-checks/0.0.12-parts/new-thread.md` | 39 | move | 0.0.12 live-check kit record; teaches the removed `openwiz ui` | ClosedWiz `private/openwiz-docs/docs/live-checks/0.0.12-parts/new-thread.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/live-checks/0.0.12-parts/send.md` | 43 | move | 0.0.12 live-check kit record; teaches the removed `openwiz ui` | ClosedWiz `private/openwiz-docs/docs/live-checks/0.0.12-parts/send.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/live-checks/0.0.12.md` | 30 | move | 0.0.12 live-check kit record; teaches the removed `openwiz ui` | ClosedWiz `private/openwiz-docs/docs/live-checks/0.0.12.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/security/public-release-review.md` | 181 | move | release security review record (spec: security notes move). **Waits** until these readers are updated: named in code by `tools/open-import/test_import.py` | ClosedWiz `private/openwiz-docs/docs/security/public-release-review.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/service-install.md` | 116 | rewrite | user guide to the packaged runtime; drop internals; #1264 may delete the service | deleted by #1264 AP11 (PR #1404), with the old web view | DS4 |
| `docs/spikes/0.0.15-notifications.md` | 32 | move | spike record | ClosedWiz `private/openwiz-docs/docs/spikes/0.0.15-notifications.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/spikes/ops-dispatch.md` | 208 | move | spike record. **Waits** until these readers are updated: named in code by `tools/open-import/test_import.py` | ClosedWiz `private/openwiz-docs/docs/spikes/ops-dispatch.md` (DS4 #1302, PR #1708) | DS4 |
| `docs/web-access.md` | 281 | rewrite | security model a user needs; drop version history; `tests/service/t2_docs.rs` reads it | deleted by #1264 AP11 (PR #1404), with the old web view | DS4 |
| `loops/README.md` | 55 | keep | loop definitions folder; three tests read it |  | none |
| `release/openwiz/CHANGELOG.md` | 34 | keep | frozen 0.0.0 release; AGENTS.md: changing it needs Jake |  | none |
| `release/openwiz/CONTRIBUTING.md` | 28 | keep | frozen 0.0.0 release; AGENTS.md: changing it needs Jake |  | none |
| `release/openwiz/README.md` | 108 | keep | frozen 0.0.0 release; AGENTS.md: changing it needs Jake |  | none |
| `release/openwiz/RELEASING.md` | 73 | keep | frozen 0.0.0 release; AGENTS.md: changing it needs Jake |  | none |
| `release/openwiz/docs/architecture.md` | 294 | keep | frozen 0.0.0 release; AGENTS.md: changing it needs Jake; teaches old 2 + 1, so AGENTS.md stops pointing to it (DS3) |  | none |
| `release/openwiz/docs/decisions.md` | 72 | keep | frozen 0.0.0 release; AGENTS.md: changing it needs Jake; teaches old 2 + 1, so AGENTS.md stops pointing to it (DS3) |  | none |
| `release/openwiz/docs/interface.md` | 112 | keep | frozen 0.0.0 release; AGENTS.md: changing it needs Jake |  | none |
| `release/openwiz/docs/overview.md` | 122 | keep | frozen 0.0.0 release; AGENTS.md: changing it needs Jake; teaches old 2 + 1, so AGENTS.md stops pointing to it (DS3) |  | none |
| `release/openwiz/docs/pacp/v0.1.md` | 477 | keep | frozen 0.0.0 release; AGENTS.md: changing it needs Jake |  | none |
| `release/openwiz/docs/workflow.md` | 162 | keep | frozen 0.0.0 release; AGENTS.md: changing it needs Jake; teaches old 2 + 1, so AGENTS.md stops pointing to it (DS3) |  | none |
| `tests/checks/dependencies.md` | 25 | keep | `tests/checks/dependencies.rs` reads the ledger |  | DS7 |
| `tests/fixtures/README.md` | 62 | keep | fixture provenance; the fixture scan names it |  | DS7 |
| `tests/fixtures/first-hour/README.md` | 2276 | rewrite | fixture document two tests read; only change: its links to removed files (line 23 → `docs/decisions/public-offer.md`) get the needed guidance or a working link, before those files move |  | DS7 |
| `tests/fixtures/first-hour/setup-onboard/README.md` | 755 | keep | fixture documents `test_first_merge.py` reads |  | DS7 |
| `tests/fixtures/github/fleets/README.md` | 10 | keep | 10-line fixture note |  | DS7 |
| `tests/fixtures/release/candidate/README.md` | 65 | keep | fixture examples `test_receipt.py` reads |  | DS7 |
| `tests/fixtures/release/clean/README.md` | 111 | keep | fixture tree `tools/release/test.py` materializes |  | DS7 |
| `tests/fixtures/release/export-review/comment-evidence/README.md` | 1 | keep | test fixture |  | DS7 |
| `tests/fixtures/release/export-review/comment-extension/README.md` | 1 | keep | test fixture |  | DS7 |
| `tests/fixtures/release/export-review/comment-history/README.md` | 1 | keep | test fixture |  | DS7 |
| `tests/fixtures/release/export-review/comment-punctuation/README.md` | 1 | keep | test fixture |  | DS7 |
| `tests/fixtures/release/export-review/l1/README.md` | 3 | keep | test fixture |  | DS7 |
| `tests/fixtures/release/export-review/l2/README.md` | 3 | keep | test fixture |  | DS7 |
| `tests/fixtures/release/export-review/l3/README.md` | 4 | keep | test fixture |  | DS7 |
| `tests/fixtures/release/export-review/l4/README.md` | 2 | keep | test fixture |  | DS7 |
| `tests/fixtures/release/export-review/m1/README.md` | 3 | keep | test fixture |  | DS7 |
| `tests/fixtures/release/export-review/m2/README.md` | 3 | keep | test fixture |  | DS7 |
| `tests/fixtures/release/export-review/prose-punctuation/README.md` | 3 | keep | test fixture |  | DS7 |
| `tests/fleet/evidence-1272/README.md` | 156 | move | proof record of O4/P4 (#1272) | ClosedWiz `private/openwiz-docs/tests/fleet/evidence-1272/README.md` (DS7 #1305, PR #1491) | DS7 |
| `tests/service/fixtures/t4-completion-approval.md` | 16 | keep | fixture `l4b_composition.rs` reads | deleted by #1264 AP11 (PR #1404), with the old web view | DS7 |
| `tools/ci-overload/README.md` | 148 | rewrite | 148 lines; keep how to run the guard |  | DS5 |
| `tools/collector/README.md` | 22 | keep | reader needs: where the shared readers live and who uses them |  | DS5 |
| `tools/collector/collector.v1.md` | 501 | keep | reader needs: the collector record the alarm, guard and CI3 read |  | DS5 |
| `tools/collector/contract.md` | 267 | rewrite | legacy v1 contract; keep the shapes saved v1 reads need |  | DS5 |
| `tools/collector/contract.v2.md` | 185 | keep | reader needs: the v2 snapshot record `health.py` writes |  | DS5 |
| `tools/collector/experiment-contract.md` | 268 | keep | reader needs: the bottleneck experiment records `experiment_contract.py` validates |  | DS5 |
| `tools/collector/factory-numbers.md` | 331 | rewrite | 331 lines; keep how to run `metrics.py` and the numbers it defines |  | DS5 |
| `tools/collector/fixtures/activity/proof.md` | 38 | move | WR8 proof plan record | ClosedWiz `private/openwiz-docs/tools/collector/fixtures/activity/proof.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/collector/fixtures/bottlenecks-contract/README.md` | 24 | keep | fixture note the tests cite |  | DS5 |
| `tools/collector/fixtures/ci3-weekly/README.md` | 25 | keep | fixture note the tests cite |  | DS5 |
| `tools/collector/fixtures/ci3-weekly/record.md` | 23 | keep | fixture `test_ci3.py` reads |  | DS5 |
| `tools/collector/fixtures/ci3/README.md` | 48 | keep | fixture note the tests cite |  | DS5 |
| `tools/collector/fixtures/collector-ci/README.md` | 92 | keep | fixture note the tests cite |  | DS5 |
| `tools/collector/fixtures/collector-factory/README.md` | 22 | keep | fixture note the tests cite |  | DS5 |
| `tools/collector/fixtures/collector/README.md` | 113 | keep | fixture note the tests cite |  | DS5 |
| `tools/collector/fixtures/flow/README.md` | 29 | keep | fixture note the tests cite |  | DS5 |
| `tools/collector/fixtures/stage-waits/README.md` | 18 | keep | fixture note the tests cite |  | DS5 |
| `tools/collector/journey-contract.md` | 512 | keep | reader needs: the ticket journey record `journey.py` writes |  | DS5 |
| `tools/collector/limits-contract.md` | 82 | keep | reader needs: the stage-limit settings seam |  | DS5 |
| `tools/fleet-load/README.md` | 276 | rewrite | 276 lines; keep how to run the load tests |  | DS5 |
| `tools/fleet-load/scale-50/README.md` | 10 | keep | reader needs: what the scale-50 kit tests |  | DS5 |
| `tools/fleet-load/scale-50/fixtures/README.md` | 11 | keep | fixture note the tests cite |  | DS5 |
| `tools/fleet-load/scale-50/report-format.md` | 148 | keep | reader needs: the scale report `report.py` validates |  | DS5 |
| `tools/install/access/README.md` | 160 | rewrite | 160 lines; keep the verification steps |  | DS5 |
| `tools/install/cloudroom/fixtures/README.md` | 15 | keep | fixture note the tests cite |  | DS5 |
| `tools/install/cloudroom/fixtures/setup.md` | 34 | keep | fixture note the tests cite |  | DS5 |
| `tools/install/completion/checkpoint.v1.md` | 149 | keep | reader needs: the CP1 checkpoint JSON the code checks |  | DS5 |
| `tools/install/first-hour-live-kit.md` | 165 | keep | reader needs: the first-hour live steps `kit.py` dry-runs |  | DS5 |
| `tools/install/live-kit.md` | 51 | keep | reader needs: the 0.0.13 kit steps `live-kit-test.py` dry-runs |  | DS5 |
| `tools/install/tests/first-hour/README.md` | 120 | rewrite | 120 lines; keep how to run the journey; also its links to removed files (line 49 → `docs/decisions/public-offer.md`) |  | DS5 |
| `tools/install/tests/first-hour/providers/README.md` | 43 | keep | reader needs: what the recording and fault providers inject |  | DS5 |
| `tools/live-smoke/README.md` | 347 | rewrite | 347 lines; keep how to run the one live-check runner |  | DS5 |
| `tools/open-import/README.md` | 236 | rewrite | 236 lines; keep how to run the import |  | DS5 |
| `tools/privacy-check/README.md` | 129 | rewrite | 129 lines; keep how to run the check |  | DS5 |
| `tools/release/README.md` | 791 | rewrite | 791 lines; keep how to run `release check`; also its links to removed files (line 437 → `tools/release/findings.md`) |  | DS5 |
| `tools/release/findings.md` | 72 | move | record of past export findings; the private export retired. **Waits** until these readers are updated: linked from `tools/release/README.md:437` | ClosedWiz `private/openwiz-docs/tools/release/findings.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/release/public/RELEASING.md` | 119 | keep | reader needs: the public RELEASING template `test_backfill.py` reads |  | DS5 |
| `tools/roadmap/README.md` | 72 | rewrite | 72 lines; writes STATUS.md, which goes (DS3) |  | DS5 |
| `tools/roadmap/fixtures/ROADMAP.md` | 26 | keep | fixture note the tests cite | deleted by DS4 #1302 (PR #1708): no roadmap test reads it | DS5 |
| `tools/roadmap/fixtures/STATUS.md` | 15 | keep | fixture note the tests cite | deleted by DS4 #1302 (PR #1708): no roadmap test reads it | DS5 |
| `tools/skills-eval/README.md` | 66 | rewrite | 66 lines; keep how to run it |  | DS5 |
| `tools/skills-eval/contract.md` | 298 | keep | reader needs: cases, fake-tool boundary and scoring the eval runs |  | DS5 |
| `tools/skills-eval/precheck/contract-fixtures/README.md` | 36 | keep | fixture note the tests cite |  | DS5 |
| `tools/skills-eval/precheck/contract.md` | 209 | keep | reader needs: the builder precheck interface |  | DS5 |
| `tools/skills-eval/replay-contract.md` | 113 | keep | reader needs: the paired replay record |  | DS5 |
| `tools/skills-eval/replay/contract-fixtures/README.md` | 14 | keep | fixture note the tests cite |  | DS5 |
| `tools/skills-eval/weekly/README.md` | 255 | rewrite | 255 lines; keep how to run the weekly core |  | DS5 |
| `tools/stall-alarm/README.md` | 301 | rewrite | 301 lines; keep how to run it |  | DS5 |
| `tools/test-value/README.md` | 202 | rewrite | reader needs: the ledger form and coverage method; wave #1141 relies on it; only change: its links to removed files (line 197 → `tools/test-value/evidence/baseline/README.md`) get the needed guidance or a working link, before those files move |  | DS5 |
| `tools/test-value/evidence/baseline/README.md` | 66 | move | evidence record. **Waits** until these readers are updated: linked from `tools/test-value/README.md:197` | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/baseline/README.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/cw11/README.md` | 116 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/cw11/README.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/cw11/ledger.md` | 756 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/cw11/ledger.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/cw3/README.md` | 67 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/cw3/README.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/cw3/ledger.md` | 663 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/cw3/ledger.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/cw4/README.md` | 48 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/cw4/README.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/cw4/ledger.md` | 307 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/cw4/ledger.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/cw5/README.md` | 72 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/cw5/README.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/cw5/ledger.md` | 473 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/cw5/ledger.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/cw6/README.md` | 47 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/cw6/README.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/cw6/ledger.md` | 194 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/cw6/ledger.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/tv10/README.md` | 103 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/tv10/README.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/tv10/ledger.md` | 113 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/tv10/ledger.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/tv11/README.md` | 163 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/tv11/README.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/tv11/ledger.md` | 351 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/tv11/ledger.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/tv12/README.md` | 67 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/tv12/README.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/tv12/ledger.md` | 97 | move | TV12 ledger record; a comment in `tests/checks/skills.rs` points to it. **Waits** until these readers are updated: named in code by `tests/checks/skills.rs` | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/tv12/ledger.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/tv12/plan.md` | 65 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/tv12/plan.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/tv3/coverage.md` | 66 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/tv3/coverage.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/tv3/ledger.md` | 164 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/tv3/ledger.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/tv4/README.md` | 100 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/tv4/README.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/tv4/ledger.md` | 380 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/tv4/ledger.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/tv5/README.md` | 112 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/tv5/README.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/tv5/ledger.md` | 395 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/tv5/ledger.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/tv6/README.md` | 161 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/tv6/README.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/tv6/ledger.md` | 260 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/tv6/ledger.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/tv7/README.md` | 157 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/tv7/README.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/tv7/ledger.md` | 232 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/tv7/ledger.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/tv8/README.md` | 115 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/tv8/README.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/tv8/ledger.md` | 132 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/tv8/ledger.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/tv9/README.md` | 104 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/tv9/README.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/test-value/evidence/tv9/ledger.md` | 211 | move | evidence record | ClosedWiz `private/openwiz-docs/tools/test-value/evidence/tv9/ledger.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/war-room/README.md` | 973 | rewrite | 973 lines of ticket seams; keep how to run it; also its links to removed files (line 736 → `tools/war-room/design/brief.md`, line 961 → `docs/evidence/1097/measurements.md`) |  | DS5 |
| `tools/war-room/assets/README.md` | 41 | keep | reader needs: what each embedded page asset is |  | DS5 |
| `tools/war-room/charts/contract.md` | 173 | keep | reader needs: the chart build inputs and outputs `publish.py` uses |  | DS5 |
| `tools/war-room/dependencies.md` | 67 | keep | reader needs: which locked packages the chart build uses, and why |  | DS5 |
| `tools/war-room/design/brief.md` | 120 | move | frozen design brief for WRD3 (#631). **Waits** until these readers are updated: linked from `tools/war-room/README.md:736` | ClosedWiz `private/openwiz-docs/tools/war-room/design/brief.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/war-room/design/site/after/README.md` | 7 | move | design hill-climb record (#883) | ClosedWiz `private/openwiz-docs/tools/war-room/design/site/after/README.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/war-room/design/site/prototype/README.md` | 26 | move | throwaway prototypes record (#883) | ClosedWiz `private/openwiz-docs/tools/war-room/design/site/prototype/README.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/war-room/fixtures/answer-time/README.md` | 28 | keep | fixture note the tests cite |  | DS5 |
| `tools/war-room/fixtures/charts/proof.md` | 39 | move | proof plan record | ClosedWiz `private/openwiz-docs/tools/war-room/fixtures/charts/proof.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/war-room/fixtures/cost/README.md` | 52 | keep | expected arithmetic `test_cost.py` cites |  | DS5 |
| `tools/war-room/fixtures/cost/checks.md` | 34 | move | review check record | ClosedWiz `private/openwiz-docs/tools/war-room/fixtures/cost/checks.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/war-room/fixtures/cost/delivery-checks.md` | 43 | move | review check record | ClosedWiz `private/openwiz-docs/tools/war-room/fixtures/cost/delivery-checks.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/war-room/fixtures/cost/review-1-checks.md` | 41 | move | review round record | ClosedWiz `private/openwiz-docs/tools/war-room/fixtures/cost/review-1-checks.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/war-room/fixtures/health/proof.md` | 118 | move | proof plan record | ClosedWiz `private/openwiz-docs/tools/war-room/fixtures/health/proof.md` (DS5 #1303, PR #1492) | DS5 |
| `tools/war-room/fixtures/page-history/README.md` | 25 | keep | fixture note the tests cite |  | DS5 |
| `tools/war-room/fixtures/page-history/checkpoint.md` | 27 | keep | fixture folder `test_page_history.py` reads; per-file read unknown |  | DS5 |
| `tools/war-room/fixtures/page-history/handback.md` | 31 | keep | fixture folder `test_page_history.py` reads; per-file read unknown |  | DS5 |
| `tools/war-room/fixtures/page-history/review-1.md` | 25 | keep | fixture folder `test_page_history.py` reads; per-file read unknown |  | DS5 |
| `tools/war-room/fixtures/review-loops/description-v2.md` | 14 | keep | fixture `test_review_loops.py` reads |  | DS5 |
| `tools/war-room/fixtures/review-loops/report-ok.md` | 15 | keep | fixture `test_review_loops.py` reads |  | DS5 |
| `tools/war-room/fixtures/review-loops/report-today.md` | 14 | keep | fixture `test_review_loops.py` reads |  | DS5 |
| `tools/war-room/fixtures/review-loops/report-v2-builder.md` | 20 | keep | fixture `test_review_loops.py` reads |  | DS5 |
| `tools/war-room/fixtures/review-loops/report-v2-fresh.md` | 15 | keep | fixture `test_review_loops.py` reads |  | DS5 |
| `tools/war-room/fixtures/review-loops/report-v2-merge.md` | 14 | keep | fixture `test_review_loops.py` reads |  | DS5 |
| `tools/war-room/fixtures/review-loops/report-v2-park.md` | 14 | keep | fixture `test_review_loops.py` reads |  | DS5 |
| `tools/war-room/fixtures/rework/README.md` | 27 | keep | fixture note the tests cite |  | DS5 |
| `tools/war-room/fixtures/weekly/README.md` | 11 | keep | fixture note the tests cite |  | DS5 |
| `tools/war-room/web/contract.md` | 81 | keep | reader needs: the six published files and how they are served |  | DS5 |
| `tools/wizskills/README.md` | 40 | keep | reader needs: how to install the pinned WizSkills release |  | DS5 |
| `tools/wizskills/fixtures/contract/proof.md` | 56 | move | WZ-P1 proof plan record | ClosedWiz `private/openwiz-docs/tools/wizskills/fixtures/contract/proof.md` (DS5 #1303, PR #1492) | DS5 |
