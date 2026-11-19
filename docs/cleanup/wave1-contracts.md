# Cleanup wave 1 contract inventory

CW12 (#1153), for proof CW-D in #1141. The inventory is every path returned by
`git ls-tree -r --name-only 8653e417df2ae9c36ae081401163553a10adbdbe -- contracts/`,
including schemas, fixture programs, and old proof logs.

I searched tracked sources for filenames, schema IDs, command invocations and
artifact or record names. The external sources were WizSkills at
`89fc285ce551f341b8d308732bcd8d4467ace353`, WizLoops at
`01c0bb2a63a4e35fdb5a012b09853a23ae6fc592` and at OpenWiz's format pin,
WizRoom at `95457f882b75289f68dea9800eff61436385e320`, and the ClosedWiz
default branch's tools and record formats. Private record contents stay private.
Paths under an external repository name refer to that repository. Unqualified
paths are in OpenWiz.

Keep rows name the consumer and the interface it relies on. An owner-facing
command, documented HTTP endpoint, or user-authored configuration counts.
Internal readers and tests help locate folds. Old proof logs can move with
their suites as evidence. Fold rows name the note or schema destination, or
the fixture directory beside the tests. CW13 (#1154) takes a–l and CW14 (#1155)
takes m–z, using the fixture family's name for paths under `contracts/fixtures/`.
The three #979 paths and the interfaces that require them are outside the folds.

| Path | Verdict | Dependency or internal use | Fold destination |
| --- | --- | --- | --- |
| `contracts/agent-github-reads.v1.md` | Keep | WizSkills `skills/launch-fleet/scripts/carried/read.py` implements the paged GitHub reads, refusal and freshness rules. | — |
| `contracts/agent-github-reads.v1.schema.json` | Keep | WizSkills' carried GitHub reader uses the shared request and cache records. OpenWiz `tools/github-app/test_identity_contract.py` checks the shared read permissions against this schema. | — |
| `contracts/attachment-mime-types.v1.md` | Keep | OpenWiz attachment users choose image types for staging and send/new. `crates/core/src/attachment.rs` enforces the type mapping used by the CLI and upload API. | — |
| `contracts/attachment.v1.schema.json` | Keep | CLI users script `openwiz attachment add/ls/rm --json`. The same envelopes serve HTTP clients documented in `web-api.v1.md`. | — |
| `contracts/ci-main-batch.v1.md` | Fold | Offline combined coverage and shadow admission rules for `ci/main-batch/admit.py`. Current main admission uses the selection plan and map age instead. | CW13 → `ci/main-batch/README.md` |
| `contracts/ci-main-batch.v1.schema.json` | Fold | Internal combined coverage record checked by `ci/main-batch/test_contract.py` and produced by `ci/main-batch/shadow.py`. Put the rules in `ci/main-batch/README.md`. The external CI selection schema is separate. | CW13 → `ci/main-batch/fixtures/combined-coverage.schema.json` |
| `contracts/ci-selection.v1.md` | Keep | WizRoom `tools/war-room/budgets.py` reads the latest attempt's persisted selection artifact. ClosedWiz `ci/escapes/escapes.py` also reads the PR selection plans. | — |
| `contracts/ci-selection.v1.schema.json` | Keep | WizRoom's `budgets.py` checks `openwiz.ci-selection.v1`, run identity and attempt; its `test_budgets.py` builds that artifact. | — |
| `contracts/ci3.v1.md` | Keep | WizRoom's `tools/war-room/test_gather.py` expects the collector's `ci3` snapshot, and OpenWiz's `docs/ci3.md` publishes the same measure for readers comparing results over time. | — |
| `contracts/cli.v1.md` | Keep | CLI users and agents use commands and exit codes. WizSkills carries the document in `check/wizskills.v1.json` and invokes the CLI from its onboard and launch-fleet skills. | — |
| `contracts/cli.v1.schema.json` | Keep | CLI agents consume the `openwiz agent-info` catalogue emitted from `crates/cli/src/agent-catalogue.json`. ClosedWiz's `tools/live-smoke/restriction.py` checks the CLI against that catalogue. | — |
| `contracts/cockpit.v1.md` | Keep | Users of the documented local `GET /api/v1/cockpit` read coverage, freshness and agent facts. The response is consumed by `apps/web/src/cockpit.ts`. | — |
| `contracts/cockpit.v1.schema.json` | Keep | Local API users receive the cockpit facts envelope. `apps/web/src/cockpit.ts` and `tests/checks/cockpit_schema_conformance.rs` read that shape. | — |
| `contracts/decisions.v1.md` | Keep | WizSkills `skills/grill/SKILL.md` and `skills/plan-graph/SKILL.md` write decision records. ClosedWiz stores private grill records in the same protocol. | — |
| `contracts/decisions.v1.schema.json` | Keep | WizSkills carries the schema in `check/wizskills.v1.json`; WizRoom's `tools/war-room/fixtures/page-history/decisions.json` exercises the decisions envelope. | — |
| `contracts/dependencies.v1.md` | Fold | Independent approved-crate ledger read by `tests/checks/dependencies.rs`. Move the approval rows intact so the check retains an independent source. | CW13 → `tests/checks/dependencies.md` |
| `contracts/engine-retirement.v1.md` | Fold | Completed retirement map. `tools/live-smoke/smoke.py` still uses the resulting restriction on what the smoke runner may invoke. | CW13 → `tools/live-smoke/README.md` |
| `contracts/feedback.v1.md` | Keep | WizSkills' `skills/feedback/scripts/feedback.py` writes feedback issues; `skills/feedback-triage/scripts/triage.py` reads and handles them. | — |
| `contracts/first-hour.v1.md` | Fold | Evidence and recovery rules for the first-hour journey and its providers under `tools/install/tests/first-hour/`. The user-facing setup and decisions stay under their own contracts. | CW13 → `tools/install/tests/first-hour/README.md` |
| `contracts/first-hour.v1.schema.json` | Fold | Offline result and recovery documents validated by `tools/install/tests/first-hour-contract/check.py` and produced by the first-hour journey. Put the rules in `tools/install/tests/first-hour/README.md`. | CW13 → `tools/install/tests/first-hour-contract/first-hour.schema.json` |
| `contracts/fleet-tick.v1.md` | Keep | Fleet operators consume the surviving dry-run planner CLI. WizSkills' `skills/launch-fleet/scripts/ops-starts.py` also follows the fleet-tick frontier and builder selection rules. | — |
| `contracts/fleet-tick.v1.schema.json` | Keep | Fleet operators consume `openwiz fleet tick --dry-run --json`. ClosedWiz's `tools/live-smoke/smoke.py` reads the tick envelope. | — |
| `contracts/fleet.v1.md` | Keep | WizSkills `skills/onboard/SKILL.md` reads `openwiz fleet <spec> --json` for progress. | — |
| `contracts/fleet.v1.schema.json` | Keep | WizSkills onboarding consumes the fleet states and counts; ClosedWiz's `tools/install/tests/onboard/test_journey.py` supplies the same fleet result. | — |
| `contracts/fixtures/github-identity/commit-identity.json` | Keep | Synthetic noreply identity example read by `tools/github-app/test_identity_contract.py`. Named by the kept `github-identity.v1.md`, whose WizSkills copy must match byte for byte at the OpenWiz pin. | — |
| `contracts/fixtures/github-identity/red-review-1.txt` | Keep | Archived failing run from `tools/github-app/test_identity_contract.py`; the suite's privacy scan walks the fixture directory. Named by the kept `github-identity.v1.md`, whose WizSkills copy must match byte for byte at the OpenWiz pin. | — |
| `contracts/fixtures/github-identity/red-run.txt` | Keep | Archived failing run from `tools/github-app/test_identity_contract.py`; the suite's privacy scan walks the fixture directory. Named by the kept `github-identity.v1.md`, whose WizSkills copy must match byte for byte at the OpenWiz pin. | — |
| `contracts/fixtures/github-identity/secret.json` | Keep | Synthetic secret descriptor read by `tools/github-app/test_identity_contract.py`. Named by the kept `github-identity.v1.md`, whose WizSkills copy must match byte for byte at the OpenWiz pin. | — |
| `contracts/fixtures/github-identity/token-exchange.json` | Keep | Synthetic exchange cases shared by `tests/cli-agent/github_token.rs` and `tools/github-app/test_identity_contract.py`. Named by the kept `github-identity.v1.md`, whose WizSkills copy must match byte for byte at the OpenWiz pin. | — |
| `contracts/fixtures/setup-onboard/cases.json` | Fold | Synthetic conformance cases loaded by `tools/install/tests/setup-onboard-contract/test_contract.py`. | CW14 → `tools/install/tests/setup-onboard-contract/fixtures/` |
| `contracts/fixtures/wizloops/README.md` | Keep | WizLoops owns the source format. `tests/cli-agent/loop_contract.rs` uses this pin record to check the carried WizLoops files. | — |
| `contracts/fixtures/wizloops/catalog/all-secrets.md` | Keep | WizLoops `format/fixtures/catalog/all-secrets.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/expected.json` | Keep | WizLoops `format/fixtures/expected.json` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid-folder/duplicate-id/a.md` | Keep | WizLoops `format/fixtures/invalid-folder/duplicate-id/a.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid-folder/duplicate-id/b.md` | Keep | WizLoops `format/fixtures/invalid-folder/duplicate-id/b.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/agent-space.md` | Keep | WizLoops `format/fixtures/invalid/agent-space.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/at-no-offset.md` | Keep | WizLoops `format/fixtures/invalid/at-no-offset.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/bad-id.md` | Keep | WizLoops `format/fixtures/invalid/bad-id.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/bad-param-name.md` | Keep | WizLoops `format/fixtures/invalid/bad-param-name.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/bad-placeholder.md` | Keep | WizLoops `format/fixtures/invalid/bad-placeholder.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/bad-thread.md` | Keep | WizLoops `format/fixtures/invalid/bad-thread.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/bad-timezone.md` | Keep | WizLoops `format/fixtures/invalid/bad-timezone.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/blank-line.md` | Keep | WizLoops `format/fixtures/invalid/blank-line.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/blank-name.md` | Keep | WizLoops `format/fixtures/invalid/blank-name.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/check-missing.md` | Keep | WizLoops `format/fixtures/invalid/check-missing.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/check-parent.md` | Keep | WizLoops `format/fixtures/invalid/check-parent.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/comment-line.md` | Keep | WizLoops `format/fixtures/invalid/comment-line.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/crlf.md` | Keep | WizLoops `format/fixtures/invalid/crlf.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/cron-names.md` | Keep | WizLoops `format/fixtures/invalid/cron-names.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/cron-out-of-range.md` | Keep | WizLoops `format/fixtures/invalid/cron-out-of-range.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/cron-six-fields.md` | Keep | WizLoops `format/fixtures/invalid/cron-six-fields.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/duplicate-key.md` | Keep | WizLoops `format/fixtures/invalid/duplicate-key.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/duplicate-nested-key.md` | Keep | WizLoops `format/fixtures/invalid/duplicate-nested-key.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/duplicate-secret.md` | Keep | WizLoops `format/fixtures/invalid/duplicate-secret.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/empty-body.md` | Keep | WizLoops `format/fixtures/invalid/empty-body.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/in-seconds.md` | Keep | WizLoops `format/fixtures/invalid/in-seconds.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/missing-thread.md` | Keep | WizLoops `format/fixtures/invalid/missing-thread.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/missing-timezone.md` | Keep | WizLoops `format/fixtures/invalid/missing-timezone.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/multiline-param.md` | Keep | WizLoops `format/fixtures/invalid/multiline-param.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/no-frontmatter.md` | Keep | WizLoops `format/fixtures/invalid/no-frontmatter.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/no-space.md` | Keep | WizLoops `format/fixtures/invalid/no-space.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/null-check.md` | Keep | WizLoops `format/fixtures/invalid/null-check.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/param-float.md` | Keep | WizLoops `format/fixtures/invalid/param-float.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/param-in-check.md` | Keep | WizLoops `format/fixtures/invalid/param-in-check.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/param-in-check/check.sh` | Keep | WizLoops `format/fixtures/invalid/param-in-check/check.sh` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/priority-five.md` | Keep | WizLoops `format/fixtures/invalid/priority-five.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/priority-float.md` | Keep | WizLoops `format/fixtures/invalid/priority-float.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/priority-string.md` | Keep | WizLoops `format/fixtures/invalid/priority-string.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/same-thread-secrets.md` | Keep | WizLoops `format/fixtures/invalid/same-thread-secrets.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/secrets-all.md` | Keep | WizLoops `format/fixtures/invalid/secrets-all.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/secrets-none-string.md` | Keep | WizLoops `format/fixtures/invalid/secrets-none-string.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/timeout-too-long.md` | Keep | WizLoops `format/fixtures/invalid/timeout-too-long.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/timeout-too-long/check.sh` | Keep | WizLoops `format/fixtures/invalid/timeout-too-long/check.sh` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/timezone-only.md` | Keep | WizLoops `format/fixtures/invalid/timezone-only.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/two-triggers.md` | Keep | WizLoops `format/fixtures/invalid/two-triggers.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/unclosed.md` | Keep | WizLoops `format/fixtures/invalid/unclosed.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/undeclared-param-check.md` | Keep | WizLoops `format/fixtures/invalid/undeclared-param-check.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/undeclared-param-check/check.sh` | Keep | WizLoops `format/fixtures/invalid/undeclared-param-check/check.sh` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/undeclared-param-env.md` | Keep | WizLoops `format/fixtures/invalid/undeclared-param-env.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/undeclared-param-env/check.sh` | Keep | WizLoops `format/fixtures/invalid/undeclared-param-env/check.sh` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/undeclared-param.md` | Keep | WizLoops `format/fixtures/invalid/undeclared-param.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/unknown-agent-key.md` | Keep | WizLoops `format/fixtures/invalid/unknown-agent-key.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/unknown-field.md` | Keep | WizLoops `format/fixtures/invalid/unknown-field.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/unquoted-string.md` | Keep | WizLoops `format/fixtures/invalid/unquoted-string.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/unused-param.md` | Keep | WizLoops `format/fixtures/invalid/unused-param.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/invalid/webhook-false.md` | Keep | WizLoops `format/fixtures/invalid/webhook-false.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/valid/all-secrets-new.md` | Keep | WizLoops `format/fixtures/valid/all-secrets-new.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/valid/all-secrets-same.md` | Keep | WizLoops `format/fixtures/valid/all-secrets-same.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/valid/at-same.md` | Keep | WizLoops `format/fixtures/valid/at-same.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/valid/cron-check.md` | Keep | WizLoops `format/fixtures/valid/cron-check.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/valid/cron-check/check.sh` | Keep | WizLoops `format/fixtures/valid/cron-check/check.sh` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/valid/fast-no-check.md` | Keep | WizLoops `format/fixtures/valid/fast-no-check.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/valid/in-same.md` | Keep | WizLoops `format/fixtures/valid/in-same.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/valid/long-check.md` | Keep | WizLoops `format/fixtures/valid/long-check.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/valid/long-check/check.sh` | Keep | WizLoops `format/fixtures/valid/long-check/check.sh` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/valid/params-env.md` | Keep | WizLoops `format/fixtures/valid/params-env.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/valid/params-env/check.sh` | Keep | WizLoops `format/fixtures/valid/params-env/check.sh` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/valid/python-check.md` | Keep | WizLoops `format/fixtures/valid/python-check.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/valid/python-check/check.py` | Keep | WizLoops `format/fixtures/valid/python-check/check.py` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/valid/same-thread-agent.md` | Keep | WizLoops `format/fixtures/valid/same-thread-agent.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/valid/same-thread-agent/check.sh` | Keep | WizLoops `format/fixtures/valid/same-thread-agent/check.sh` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/valid/script-only.md` | Keep | WizLoops `format/fixtures/valid/script-only.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/valid/script-only/check.sh` | Keep | WizLoops `format/fixtures/valid/script-only/check.sh` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/valid/short-check.md` | Keep | WizLoops `format/fixtures/valid/short-check.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/valid/short-check/check.sh` | Keep | WizLoops `format/fixtures/valid/short-check/check.sh` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizloops/valid/webhook-new.md` | Keep | WizLoops `format/fixtures/valid/webhook-new.md` is the pinned source for this case; WizLoops `ci/validate.py` consumes the format via `openwiz loop validate`. | — |
| `contracts/fixtures/wizskills/package.json` | Fold | Synthetic package-tree example loaded by `tools/wizskills/test_contract.py`. | CW14 → `tools/wizskills/fixtures/contract/` |
| `contracts/fixtures/wizskills/proof.md` | Fold | Historical proof plan for `tools/wizskills/test_contract.py`. | CW14 → `tools/wizskills/fixtures/contract/` |
| `contracts/fixtures/wizskills/red.txt` | Fold | Archived failing run for `tools/wizskills/test_contract.py`. | CW14 → `tools/wizskills/fixtures/contract/` |
| `contracts/fixtures/wizskills/references.json` | Fold | Synthetic reference cases read by `tools/wizskills/test_contract.py`. | CW14 → `tools/wizskills/fixtures/contract/` |
| `contracts/fixtures/wizskills/refusals.json` | Fold | Synthetic package-refusal cases read by `tools/wizskills/test_contract.py`. | CW14 → `tools/wizskills/fixtures/contract/` |
| `contracts/github-identity.v1.md` | Keep | WizSkills `skills/launch-fleet/scripts/github-app/app.py` and `loop.sh` use the App token profiles and account fallback. WizSkills carries the contract. | — |
| `contracts/install.v1.md` | Keep | Users depend on the installer's verified bundle and refusal rules. WizSkills `skills/install/SKILL.md` uses the OpenWiz installer and names this contract. | — |
| `contracts/install.v1.schema.json` | Keep | Users of `tools/install/install` consume release bundles whose manifest is produced by `tools/release/package.py` and checked before install. | — |
| `contracts/inventory.v1.schema.json` | Keep | CLI and local HTTP clients consume inventory from `openwiz ls/show --json` and the inventory routes. ClosedWiz's `tools/live-check/new/scripts/new-kit.py` reads inventory as well. | — |
| `contracts/loop-cli.v1.md` | Keep | WizLoops' README documents `openwiz loop validate/plan/apply/export`. Its `ci/validate.py` invokes validation and checks the result. | — |
| `contracts/loop-cli.v1.schema.json` | Keep | WizLoops `ci/validate.py` reads the validation report. The same schema documents the CLI's other loop commands for users. | — |
| `contracts/loops.v1.md` | Keep | Users author definitions documented in `loops/README.md`. WizRoom's review-loops bench also depends on the loop behavior documented by OpenWiz. | — |
| `contracts/loops.v1.schema.json` | Keep | Users author repository-local loop definitions using the shape in `loops/README.md`. `crates/store/src/loops/document.rs` reads it, and ClosedWiz has its own `loops/example.json` in that format. | — |
| `contracts/messaging.v1.schema.json` | Keep | CLI and HTTP clients consume send, preview and lookup envelopes. ClosedWiz `tools/live-check/send/scripts/send-kit.py` reads the send output. | — |
| `contracts/new-thread.v1.schema.json` | Keep | CLI and HTTP clients consume create, preview, options and status envelopes. ClosedWiz `tools/live-check/new/scripts/new-kit.py` reads the new-thread results. | — |
| `contracts/open-development.v1.md` | Keep | WizSkills `skills/build-ticket/SKILL.md` follows these public record rules, and the ClosedWiz private decision records use the pointer protocol. | — |
| `contracts/ops-dispatch.v1.md` | Keep | WizSkills `skills/launch-fleet/scripts/records.py` implements the shared GitHub records. Its build-ticket and plan-graph skills use the same approval and grant protocol. | — |
| `contracts/ops-dispatch.v1.schema.json` | Keep | WizSkills carries the schema and uses it for the record examples checked by `skills/launch-fleet/test/ops-protocol/test_protocol.py`. | — |
| `contracts/plan-links.v1.md` | Keep | WizSkills `skills/plan-graph/check-links.sh` checks the ticket link grammar. WizRoom consumes the resulting graph in its page history. | — |
| `contracts/plan-links.v1.schema.json` | Keep | WizRoom `tools/war-room/test_page_history.py` reads graph observations with the plan-links schema ID. WizSkills carries the schema and emits graph reports with that ID. | — |
| `contracts/plan.v1.md` | Keep | Users of the documented local `GET /api/v1/plan` read plan lanes, links and freshness. `apps/web/src/plan.ts` consumes it. | — |
| `contracts/plan.v1.schema.json` | Keep | Local API users consume the plan response. `apps/web/src/plan.ts` reads its envelope and `tests/checks/plan_decisions_schema_conformance.rs` checks its shape. | — |
| `contracts/prompt.v1.schema.json` | Keep | CLI users supply prompt and attachment inputs for `openwiz send` and `openwiz new`. ClosedWiz's live-check fixtures carry the schema for those command checks. | — |
| `contracts/public-cloudroom-setup.v1.md` | Keep | Users follow the CloudRoom connection flow in `apps/web/src/components/CloudRoomSetup.tsx`. The contract governs the owner-confirmed login and reconnect behavior exposed through setup. | — |
| `contracts/public-offer.v1.md` | Fold | Approved offer and copy constraints. `apps/site/test/approved-copy.mjs` and `apps/web/src/components/Setup.tsx` use those constraints. Preserve the offer in the existing decision and place the implementation note by the site. | CW14 → `apps/site/README.md` |
| `contracts/release-candidate.v1.md` | Keep | ClosedWiz's release records use the candidate and receipt rules from ADR 0020. Its `tools/live-smoke/receipt.py` produces receipts for the release gate. | — |
| `contracts/release-candidate.v1.schema.json` | Keep | ClosedWiz `tools/live-smoke/receipt.py` and `smoke.py` use the release-candidate and receipt shapes that OpenWiz's `tools/release/candidate.py` checks. | — |
| `contracts/review-loops.v1.md` | Keep | WizRoom `tools/war-room/test_review_loops.py` reads the v1 contract for the benchmark, and `review_loops.py` retains that record format. | — |
| `contracts/review-loops.v2.md` | Keep | WizSkills' review-ticket writes the verdict, findings and Next line. WizRoom `tools/war-room/review_loops.py` validates those reports. | — |
| `contracts/service.v1.md` | Keep | Service operators configure `service/config.json`, run `openwiz-service status --json`, and read the service's GitHub records. | — |
| `contracts/service.v1.schema.json` | Keep | Service operators consume the status report and author service config. ClosedWiz's `tests/service/t3_planner.rs` and `t5_execution.rs` also exercise the service shapes. | — |
| `contracts/setup-onboard.v1.md` | Keep | WizSkills `skills/onboard/SKILL.md` uses `openwiz init` and its brain reference in the user's setup-to-first-merge journey. | — |
| `contracts/setup-onboard.v1.schema.json` | Keep | WizSkills onboarding invokes the JSON init preview and confirmation and needs their result shape. OpenWiz `crates/cli/src/init.rs` supplies the init document. | — |
| `contracts/setup.v1.md` | Keep | WizSkills `skills/install/SKILL.md` names the setup contract, and `skills/onboard/scripts/onboard.py` implements its readiness evidence window and verified codes. | — |
| `contracts/setup.v1.schema.json` | Keep | Users of the documented local `GET /api/v1/setup` consume readiness and operation results, including the states WizSkills onboarding reads. | — |
| `contracts/web-api.v1.md` | Keep | Users of the local OpenWiz HTTP API rely on its routes, envelopes, bounds and status meanings. ClosedWiz live send and new-thread kits consume those routes. | — |
| `contracts/wizloops-cloudroom.v1.md` | Keep | WizLoops `adapters/cloudroom.v1.md` owns the adapter rules for its loop catalog. OpenWiz `tests/cli-agent/loop_contract.rs` checks the pinned copy. | — |
| `contracts/wizloops-loop.v1.md` | Keep | WizLoops `format/loop.v1.md` owns the format used by catalog authors and checked by WizLoops CI via the OpenWiz CLI. | — |
| `contracts/wizloops-loop.v1.schema.json` | Keep | WizLoops `format/loop.v1.schema.json` is the upstream shape for its catalog. OpenWiz's loop contract check checks the carried copy at the pin. | — |
| `contracts/wizroom.v1.md` | Keep | WizRoom's README links directly to this contract for the public collector and private renderer split. | — |
| `contracts/wizskills.v1.md` | Keep | WizSkills `check/wizskills.v1.json`, `check/standalone.py` and `install.sh` implement the package and standalone rules. OpenWiz's installer consumes the resulting package. | — |
