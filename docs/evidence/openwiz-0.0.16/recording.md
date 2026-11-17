# 0.0.16 T7: the installed journey's recording proof and the bounded live kit (#637)

Spec #625, revision 6. Recording providers and synthetic fixtures only:
nothing here signed in, created an App, a key, a companion, a project, a
machine or a thread, spent anything, or ran live. A fixture or recording
result is never a live pass, an elapsed time, a real account or a shipped
upstream capability.

## What was built

- **The receipt validator** (`tools/install/tests/first-hour/first_merge_kit.py`),
  supplementing the first-hour kit (`kit.py`), never replacing it. It reads one
  setup-onboard.v1 `first_merge_receipt`, the same attempt's first-hour.v1
  `result`, a fleet-start record, the kit's binding and its eligibility record.
  The receipt's codes come from setup-onboard.v1's checks and the result's
  from first-hour.v1's, kept apart, so neither verdict decides the other.
- **The recording receipt on the installed journey** (`journey.py`,
  `Attempt.first_merge()`), with the fleet start, the key faults, the
  public-companion check and the skip-App continuation at the installed seams
  (README in that folder).
- **The bounded live kit** (`tools/install/first-hour-live-kit.md`, "The 0.0.16
  extension"): eligibility, binding, steps F1 to F17, timing and actions, fleet
  start, receipt validation, and the authority scopes T8 #638 must sign.

## Claims and evidence

| Claim | Evidence (class) | Ready |
| --- | --- | --- |
| P1 The installed path runs on recording providers, no substitute planner or launcher | `test_first_merge.py` `Recording`: #1109's installed journey unchanged, then the installed launch-fleet frontier, review, CI and merge read-back (fixture test) | Yes |
| P2 App and skip both continue | `test_the_app_path_counts_every_owner_equivalent_step`, `test_the_skip_app_continuation_counts_its_own_steps` (fixture test) | Yes; live App and skip runs are T9's |
| P3 Keys: both routes at the seam; no-paste stays Unverified | `test_both_secret_routes_at_the_installed_seam_and_no_paste_stays_unverified` (fixture test) | Yes; the real save and delivery are upstream and unobserved |
| P4 Init: public companion once | `test_a_lost_companion_reply_is_reconciled_once` (fixture test) | Yes; live visibility read-back is T9's |
| P5 Owner work survives key and brain faults | the `refused_access` and `lost_reply` documents of those two tests, compared by first-hour.v1's checks; #2204's six cases unchanged in `test_journey.py` (fixture test) | Yes |
| P6 Merge rules; engine and tick refused | `Kit` weak-merge, init-only and engine/tick cases; `KnownWaysToFail.test_a_tick_start_beside_the_fleet_thread_is_refused` (fixture test) | Yes |
| P7 Under 30 minutes and at most five actions | `Kit.test_the_version_boundaries_never_pass` and the omitted-entry, labelled-live and owner-step cases (fixture test); one live timeline is T9's | Validator yes; the live result is missing until T9 |

## Red first

- `tools/install/tests/first-hour/evidence/red-kit.log`: the kit proofs at the
  red commit, when `first_merge_kit.py` held only the two existing contract
  cores. The boundaries those cores already decide (30 minutes, six actions,
  seeded state, prepared help, init-only) passed; every new rule (result
  binding, candidate/repository/route, merge read-back, omitted entries,
  labelled-live evidence, engine/tick, owner steps, eligibility, unsafe
  cleanup, dry run) failed at its own assertion.
- `tools/install/tests/first-hour/evidence/red-journey.log`: the installed
  journey ran `openwiz fleet tick` beside the fleet thread, and with the red
  validator nothing refused it.

## Finding: the five-action target and today's journey

The recording counts each owner-equivalent step once, as the spec requires.
The App path logs **19** actions and the skip path **12**. The recording
conversation's own turns alone are eight: the idea, Connect, the grill's
answers and confirmation, the agents' location, the spec confirmation, the
plan approval and the launch's yes. Connect adds the yeses for prepare and
init (and the skip), the App's Create and Install, six owner key steps on the
protected paste, and the owner's merge of the brain pull request. With a
created App, the protected-paste route alone needs at least seven entries (two
manifest steps, four or more key steps, one paste), so it can never meet five.
The kit reports this as `actions_exceeded`; it does not group taps to fit. The
measured live result remains T9's, under T8's authorization.

## Sign-off material for #638

The kit's "What execution needs" names the graph, the seven producers' verified
merges (#632, #633, #606, #634, #635, #636, #637), the eleven authority scopes
(`live`, `machine`, `accounts`, `repository`, `app`, `companion`, `secret`,
`agents`, `merges`, `spending`, `cleanup`), the observed upstream save for the
no-paste route, the binding's candidate, host, scope, route, counts, credit
bound and cleanup, and the steps. The dry run with no record refuses every step
and exits 5. This preparation is not that authorization.

## Gaps

- No live, timed or real-account evidence: P1 to P7's live parts stay with T9
  #639 after T8 #638.
- The no-paste route stays Unverified: the CloudRoom agent-side save-secret
  contribution is not observed; a stand-in store is reported
  `agent_save_unavailable`.
- The recording repository is seeded with fleet settings and has no fresh
  machine or initial record, so its receipt is `unverified`/`fail`, never a pass.
- A fresh machine's GitHub sign-in is not exercised: the recording reuses a
  signed-in `gh`; the kit counts every sign-in screen as an owner action.
- Browser restart and removal keep #2204's named gaps.

## Helpers

None: this ticket's pieces share one journey and one validator, so no helper
was started and no no-push check was needed.
