# ER3 (#797): retire health and takeover — evidence

Fixture evidence only. Nothing here proves live behaviour.

## Red, then green

- **Claim:** a health pass whose only result is the watchdog's is a valid saved state (map section 4, `document.rs` S1).
- **Red** ([red-l5b-watchdog.log](red-l5b-watchdog.log), commit before the fix): with the watchdog-only pass in place and S1 unchanged, `l5b-watchdog` failed 4 of 12 with `service document violates cloudroom first`.
- **Green** ([green-l5b-watchdog.log](green-l5b-watchdog.log)): S1 drops "cloudroom first" and the required `cloudroom`, `tick` and `server` results; `l5b-watchdog` passes 17 of 17 (12 kept, 5 moved in).

## Moved, never deleted (map: "Move, never delete")

The records code they protect (`crates/service/src/health/records.rs`) stays; each now runs on watchdog incidents in `tests/service/l5b_watchdog.rs`.

| Retired test in `t5_execution.rs` | Now | catches |
| --- | --- | --- |
| `only_the_factory_s_comments_confirm_a_health_delivery` (#770) | moved, same name | a stranger's, a user-for-App, a case-mismatched or an authorless copy confirming a delivery, or confirming with no `Record authors` setting. Mutation check: making `authored` accept any login turns it red |
| `uncertain_absent_record_never_gets_a_second_post` | moved, same name | a lost reply whose comment never landed being posted again |
| `legacy_claim_after_healing_gets_its_original_receipt_only_by_unique_readback` | moved, same name (the runtime-repair assertion dropped: repairs are gone) | an old claim settling on an ambiguous read-back, or being posted again |
| `quarantined_frozen_delivery_keeps_other_repairs_and_healing_progressing` | moved as `quarantined_frozen_delivery_keeps_healing_progressing` | an unsafe retained body being rewritten, posted or sent, or blocking a healthy loop's healing; a corrupt one not stopping the pass. The "other repairs" half is gone with the repairs |
| `foreign_project_notification_target_is_never_sent_a_message` | moved, same name | a Needs you sent to a thread outside the configured project |
| `lost_record_reply_is_reconciled_without_another_post_or_resume` | keeper: `changed_problem_notifies_and_uncertain_delivery_survives_healing` (already in `l5b`: a lost reply is reconciled and the comment count stays 3). The "or resume" half is gone with loop resume |

## Deleted tests: keeper or gone

| Deleted | Keeper, or the behaviour that is gone |
| --- | --- |
| `t3_planner.rs`, `t3_checks.rs`, `t3_contract.rs`, `t3_owned.rs` | Gone: the health planner (`crates/core/src/health` `plan`) is deleted. `t3_owned`'s loop-name rule (`is_openwiz_loop`) stays in core, used only by the left-for-later CloudRoom loop inventory |
| `t5_health.rs` (resume of the owned loop, foreign and malformed loop lists) | Gone: the `loop` check and `resume_loop`. Its fake-placement tests have copies in `l5b_watchdog.rs`, `l3_runner.rs` and `install_engine_reads.rs` |
| `t5_server.rs`: `stopped_server_releases_its_listener_before_replacement`, `bounded_shutdown_does_not_claim_drained_while_a_worker_still_runs` | Gone: health's server restart was the only production caller of `openwiz_server::Server::shutdown` (no other caller under `crates/`). No `tests/web-api/` keeper was found |
| `t5_restart.rs`, `t5_runtime.rs` | Gone: the runtime restart channel and the tick and server restarts. `actual_service_registers_health_…` → keeper `l5b` `registered_health_job_runs_the_watchdog` and `l12-registration`'s independent-jobs cases |
| `t5_takeover.rs`, `t5_takeover_execution.rs` | Gone: TK1 takeover, its pause and retirement. Its record-delivery cases are covered by the moved tests above |
| `t5_tick.rs` | Gone: TK1's fleet fence on the controlled tick. ER2 (#796) owns the tick itself |
| `t5_execution.rs`, the rest | Gone: repair fixes, their two tries and their records |
| `t4_reader.rs`: `health_pass_must_include_a_tick_result`, `state_reader_requires_cloudroom_as_the_first_health_result` (Q7) | Gone: S1 no longer requires those results or that order. The opposite case, a watchdog-only pass that saves, runs in every `l5b` pass |

## Helpers

None. This builder did all the work in one session, so there was no swarm and no no-push check.
