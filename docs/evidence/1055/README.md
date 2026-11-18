# C7 map-age gate and main-push cancellation

Authority: spec #780 revision 5, fingerprint
`35dd6c64d9787548536d4f5fa8b9145adf365294cbf0f34a8b37e43e3ad64aa1`,
[approval](https://github.com/openwizdev/OpenWiz/issues/780#issuecomment-6975578355)
and [option B ruling](https://github.com/openwizdev/OpenWiz/issues/1055#issuecomment-6975999484).
The latter replaces the immediate-trace and ten-minute admission wording.
No environment setting, timer, runner sleep, dispatch trigger, service,
dependency, runner change, budget change or selection-contract change.

## Failing first

Before the fix, the trusted-map read is scaffolded in the owned workflow with
an unconditional trace decision, preserving the old tracer's decision while
main pushes still skip `changes`. It verifies the real synthetic RSA signature,
map shape and commit ancestry; only the clock and issuer key response are
fixture inputs. It is not a live GitHub run or an implemented age gate.

- `python3 -I .github/actions/docs-only/test_workflow.py MainMapAge Workflow.test_main_push_plan_requires_an_old_signed_map_but_other_events_do_not`
  exits 1: [red-age.log](red-age.log) retains four assertion failures.
  A 119-minute map incorrectly produces `trace=true`; exactly 120 minutes does
  too. The 121-minute signed-map case is the passing old-map control. Fresh
  main pushes also lack the conditions to skip plan writing and upload.
- `node --test .github/workflows/ci.test.mjs` exits 1:
  [red-graph.log](red-graph.log) retains three assertion failures. The running
  main push is retained instead of cancelled; `changes` is absent on a fresh
  push; and the independent 121-minute/old-map graph case runs only `main-light`
  instead of the traced full plan and signer.

The existing `python3 -I tools/collector/ci3.py check-steps` also exits 1
before adding the new push-step registry row: [red-step-registry.log](red-step-registry.log).
The error names `Check the signed main map age` as an unclassified CI step.

The tests execute the workflow's actual age script and operative conditions,
and the existing scheduler model, not an invented timer or a fixture timestamp
used in place of signature verification. All cases use synthetic inputs.

## Claims and readiness

| Claim | Evidence boundary | Owner / readiness |
| --- | --- | --- |
| 119 minutes and exactly 120 stay light; 121 minutes and 120 minutes plus one second trace | Actual workflow script with synthetic signed maps and fixed clock | Builder; red first above, green pending |
| Unknown or untrusted age cannot certify light execution | Missing map/token, tampered bytes, wrong repo/ref/event, foreign commit, invalid shape/time | Builder; actual verifier and ancestry check, green pending |
| Fresh pushes skip the full plan; old pushes execute and sign after passing CI; PR/nightly/merge-group keep behavior | Existing executable job graph, step conditions, plan/final-gate proofs | Builder; green pending |
| A newer main push cancels only its main-push group; PR cancellation and schedule/queue isolation stay | Existing concurrency scheduler model over committed expressions | Builder; red first above, green pending; live proof pending |
| Normal hooks and required CI pass at the pushed head | Exact-commit pre-push hook and new PR's CI | Builder and GitHub; pending |
| Two ordinary authorized main pushes show older cancellation and newer signing | Native post-merge run/job links on #1055 | Fleet coordinates ordinary merges, builder records; pending after merge when signed map age exceeds 120 minutes |
| First week's actual signing count is posted on #780 | Exact seven-day post-merge window of native CI run/job signing receipts, with failures/cancellations and unknown reads retained | Fleet owns the week observation; builder requests/records its evidence; due merge time plus seven days; pending |
| Distinct isolated selector proof | Selected plan, failing assertion and every catcher, with no always-run/folder-rule catcher | Builder with fleet's scoped proof authority; pending after fresh push-signed maps, no old proof rerun |

Missing/untrusted cache age is unsupported as a timestamp decision and fails
`changes` explicitly; it is never guessed fresh or silently admitted as old.
The unconditional nightly can restore a trusted signed cache. This keeps the
existing OIDC provenance and ancestry requirements; it does not grant cache
repair, changed trust policy or new proof-edit paths.

## Before and after

[Observed BEFORE and its complete 16-run cohort](https://github.com/openwizdev/OpenWiz/issues/1055#issuecomment-6975768324):
`[2026-11-17T10:21:32Z, 2026-11-18T10:21:32Z)` has **0/16** main-push runs
reaching traced setup and **16/16** reaching `main-light` setup. This is the
light-main baseline, not an immediate-tracing baseline; no savings rate follows
from it. The roughly 12 signings/day and 36,000 monthly runner-minutes are
projections, not measured results. AFTER is the first real week after merge,
not a simulated week, and remains pending with the owner/time above.

## Historical selector-proof limitation

C5 remains **PARTIAL**, per [#780 ruling](https://github.com/openwizdev/OpenWiz/issues/780#issuecomment-6975310131),
[#1123](https://github.com/openwizdev/OpenWiz/issues/1123), and
[the selected review](https://github.com/openwizdev/OpenWiz/pull/1094#issuecomment-6975135149).
Original run [43973090712](https://github.com/openwizdev/OpenWiz/actions/runs/43973090712)
selected and failed `install-connections`, but always-run `InstallJourney` and
selected browser tests `cloudroom-setup` and `setup-github-login` also caught
the edit. Aggregate red is not isolated selector proof. The original #1050,
its branch and run are untouched. No #1123 polish is included here.

## Supporting paths

J110 kind 3 covers this ticket's `docs/evidence/1055/` proof and logs, supporting
its owned workflow/test paths and acceptance gates. Kind 1 covers only the
new `docs/evidence/1055/**` source row in `tools/open-import/paths.json`, needed
so the carriage guard accepts that evidence; all other rows are preserved.
No changelog line: infra CI behavior and evidence only. No helpers used.
