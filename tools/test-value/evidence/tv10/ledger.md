# TV10 (#812): the loops group's ledger

Every test of the loops group at this pull request's base, `20a5100`, in the
form of `tools/test-value/README.md`: the `loops` target of `openwiz-tests`
(`tests/loops/main.rs`) and the service crate's `l6-switches` target, whose
entrypoint is `tests/loops/l6_executor.rs`. 36 `#[test]`s in all: 32 in
`loops` and 4 of `l6_executor.rs`; `l6-switches` also ran the 6
`l6_switches.rs` tests a second time, as the module it read its fixture from
(42 runs).

- **Wrappers:** a `…_preserve_…_cases` or `…_contracts_preserve_…` test is one
  `#[test]` that runs several named proofs (#1259). Its row says it is a
  wrapper; each proof it runs has its own row below it, named by its
  function.
- **Rows:** 36 `#[test]`s: kept 26, moved 9 (to `crates/core/tests/loops/`),
  deleted 1. The 7 wrappers among them run 35 proofs, each with its own row:
  moved 34, merged 1. After: 35 `#[test]`s, run 35 times (the 6 doubled runs
  go).
- **The fixture split:** no `l6_*` test changed file. Their shared fixture
  (`Fixture`, `git`, `Trusted`) moved out of `l6_switches.rs` into
  `tests/loops/fixture.rs`, so the service target includes only the fixture
  and no longer runs `l6_switches.rs`'s 6 tests a second time.
- **Where they live:** the planner tables exercise `openwiz-core` alone and
  moved to its own `tests/` folder, where they pass the P8(a) and M12
  allowlist guards. The `l6_*` tests each cross crates, so they stay, with
  the reason in the table under the ledger.
- **Catches** for a kept or moved test is the behaviour it asserts, read from
  its body: a change that breaks it fails the test.

| Test | Outcome | Keeper | Catches |
| --- | --- | --- | --- |
| `tests/loops/capacity.rs::lp1_capacity_contracts_preserve_shared_check_limits` | moved | `crates/core/tests/loops/capacity.rs::lp1_capacity_contracts_preserve_shared_check_limits` | (wrapper: runs the 3 proofs below) |
| `tests/loops/capacity.rs::lp1_existing_checks_count_even_for_disabled_or_removed_loops` | moved | `crates/core/tests/loops/capacity.rs::lp1_existing_checks_count_even_for_disabled_or_removed_loops` | a planner that frees check capacity when an in-flight check's loop is removed or disabled |
| `tests/loops/capacity.rs::lp1_once_checks_respect_total_and_urgent_reserve` | moved | `crates/core/tests/loops/capacity.rs::lp1_once_checks_respect_total_and_urgent_reserve` | a check limit or urgent reserve applied wrongly, or a winner chosen by input order |
| `tests/loops/capacity.rs::lp1_urgent_never_bypasses_full_capacity` | moved | `crates/core/tests/loops/capacity.rs::lp1_urgent_never_bypasses_full_capacity` | an urgent check admitted past a full shared check limit |
| `tests/loops/deferred.rs::lp1_deferred_contracts_preserve_pending_admission` | moved | `crates/core/tests/loops/deferred.rs::lp1_deferred_contracts_preserve_pending_admission` | (wrapper: runs the 6 proofs below) |
| `tests/loops/deferred.rs::r1_deferred_ticks_save_one_run_and_dispatch_once_when_capacity_frees` | moved | `crates/core/tests/loops/deferred.rs::r1_deferred_ticks_save_one_run_and_dispatch_once_when_capacity_frees` | ticks that pile up deferred runs, or a freed slot that dispatches twice or loses the held occurrence |
| `tests/loops/deferred.rs::r1_non_deferred_records_do_not_hold_the_next_scheduled_check` | moved | `crates/core/tests/loops/deferred.rs::r1_non_deferred_records_do_not_hold_the_next_scheduled_check` | a settled or in-flight record that holds the next interval check as pending work |
| `tests/loops/deferred.rs::r1_pending_work_preserves_dispatch_gates_and_leaves_check_capacity_for_other_loops` | moved | `crates/core/tests/loops/deferred.rs::r1_pending_work_preserves_dispatch_gates_and_leaves_check_capacity_for_other_loops` | pending work that skips a dispatch gate, or takes check capacity another loop needs |
| `tests/loops/deferred.rs::r3_permanent_dispatch_holds_allow_checks_even_after_many_missed_ticks` | moved | `crates/core/tests/loops/deferred.rs::r3_permanent_dispatch_holds_allow_checks_even_after_many_missed_ticks` | a permanently held dispatch (revision, budget, shadow) that stops the loop's checks, or a planner that mutates the record |
| `tests/loops/deferred.rs::r3_used_positive_budget_coalesces_until_the_saved_charge_expires` | moved | `crates/core/tests/loops/deferred.rs::r3_used_positive_budget_coalesces_until_the_saved_charge_expires` | a used budget that dispatches before its saved charge expires, or never after |
| `tests/loops/deferred.rs::r3_zero_budget_keeps_checking_across_ticks_without_dispatching` | moved | `crates/core/tests/loops/deferred.rs::r3_zero_budget_keeps_checking_across_ticks_without_dispatching` | a zero budget that dispatches, stops checking, or lets checks bypass the shared limit |
| `tests/loops/dispatch.rs::lp1_dispatch_contracts_preserve_capacity_budget_and_refusals` | moved | `crates/core/tests/loops/dispatch.rs::lp1_dispatch_contracts_preserve_capacity_budget_and_refusals` | (wrapper: runs the 9 proofs below, 8 after this pull request) |
| `tests/loops/dispatch.rs::lp1_active_and_unresolved_agents_count_once_and_keep_original_priority` | moved | `crates/core/tests/loops/dispatch.rs::lp1_active_and_unresolved_agents_count_once_and_keep_original_priority` | an active or uncertain agent counted twice, not at all, or at the wrong priority |
| `tests/loops/dispatch.rs::lp1_agent_capacity_and_reserve_table` | moved | `crates/core/tests/loops/dispatch.rs::lp1_agent_capacity_and_reserve_table` | an agent limit or urgent reserve applied wrongly, or a winner chosen by input order |
| `tests/loops/dispatch.rs::lp1_an_expired_budget_charge_does_not_free_an_uncertain_agent_slot` | moved | `crates/core/tests/loops/dispatch.rs::lp1_an_expired_budget_charge_does_not_free_an_uncertain_agent_slot` | an uncertain agent's slot freed when its budget charge expires |
| `tests/loops/dispatch.rs::lp1_budget_charges_saved_attempts_and_expires_by_dispatch_time` | moved | `crates/core/tests/loops/dispatch.rs::lp1_budget_charges_saved_attempts_and_expires_by_dispatch_time` | a budget that charges the wrong results, or expires by update time or at the wrong window edge |
| `tests/loops/dispatch.rs::lp1_off_shadow_and_changed_revision_never_dispatch` | moved | `crates/core/tests/loops/dispatch.rs::lp1_off_shadow_and_changed_revision_never_dispatch` | a disabled, shadow or changed-revision loop that dispatches |
| `tests/loops/dispatch.rs::lp1_one_pass_charges_each_new_dispatch_against_the_same_loop_budget` | moved | `crates/core/tests/loops/dispatch.rs::lp1_one_pass_charges_each_new_dispatch_against_the_same_loop_budget` | two dispatches in one pass that together exceed one loop's budget |
| `tests/loops/dispatch.rs::lp1_settled_outcomes_never_repeat_a_dispatch` | merged | `crates/core/tests/loops/schedules.rs::lp1_once_occurrences_are_not_repeated_across_results_or_revisions` | (as its keeper) |
| `tests/loops/dispatch.rs::lp1_unknown_occupancy_holds_dispatch_but_allows_checks` | moved | `crates/core/tests/loops/dispatch.rs::lp1_unknown_occupancy_holds_dispatch_but_allows_checks` | a dispatch while agent occupancy is unread, or checks held with it |
| `tests/loops/dispatch.rs::lp1_zero_budget_allows_checks_and_never_dispatches` | moved | `crates/core/tests/loops/dispatch.rs::lp1_zero_budget_allows_checks_and_never_dispatches` | a zero budget that dispatches or stops checks |
| `tests/loops/guards.rs::lp1_snapshot_contracts_preserve_closed_admission` | moved | `crates/core/tests/loops/guards.rs::lp1_snapshot_contracts_preserve_closed_admission` | (wrapper: runs the 3 proofs below) |
| `tests/loops/guards.rs::lp1_ambiguous_or_impossible_snapshots_fail_closed` | moved | `crates/core/tests/loops/guards.rs::lp1_ambiguous_or_impossible_snapshots_fail_closed` | a planner that plans from any of 19 duplicate, impossible or contradictory snapshots instead of refusing |
| `tests/loops/guards.rs::lp1_removed_deferred_work_is_reported_and_never_dispatched` | moved | `crates/core/tests/loops/guards.rs::lp1_removed_deferred_work_is_reported_and_never_dispatched` | deferred work of a removed loop that is dispatched or dropped silently |
| `tests/loops/guards.rs::lp1_reserve_cannot_exceed_total_capacity` | moved | `crates/core/tests/loops/guards.rs::lp1_reserve_cannot_exceed_total_capacity` | limits whose reserve exceeds the total, accepted |
| `tests/loops/load.rs::lp2_two_hundred_loops_drain_with_both_shared_limits_and_no_loop_cap` | moved | `crates/core/tests/loops/load.rs::lp2_two_hundred_loops_drain_with_both_shared_limits_and_no_loop_cap` | a hidden loop cap, a limit exceeded under load, a repeated check or dispatch, or work replayed on restart (LP2) |
| `tests/loops/load.rs::lp2_two_hundred_overdue_intervals_coalesce_without_a_replay_burst` | moved | `crates/core/tests/loops/load.rs::lp2_two_hundred_overdue_intervals_coalesce_without_a_replay_burst` | overdue intervals replayed as a burst instead of one coalesced check each (LP2) |
| `tests/loops/missed.rs::lp1_missed_contracts_preserve_occurrence_identity` | moved | `crates/core/tests/loops/missed.rs::lp1_missed_contracts_preserve_occurrence_identity` | (wrapper: runs the 6 proofs below) |
| `tests/loops/missed.rs::lp1_an_old_event_record_does_not_consume_a_scheduled_occurrence` | moved | `crates/core/tests/loops/missed.rs::lp1_an_old_event_record_does_not_consume_a_scheduled_occurrence` | an event run that consumes a scheduled occurrence |
| `tests/loops/missed.rs::lp1_coalescing_survives_restart_revision_and_every_recorded_result` | moved | `crates/core/tests/loops/missed.rs::lp1_coalescing_survives_restart_revision_and_every_recorded_result` | coalesced checks replayed after a restart, a revision change or any recorded result |
| `tests/loops/missed.rs::lp1_held_checks_do_not_consume_missed_occurrences` | moved | `crates/core/tests/loops/missed.rs::lp1_held_checks_do_not_consume_missed_occurrences` | a held check (capacity or disabled) that consumes the missed occurrence |
| `tests/loops/missed.rs::lp1_interval_coalescing_never_wraps_or_walks_the_missed_tick_count` | moved | `crates/core/tests/loops/missed.rs::lp1_interval_coalescing_never_wraps_or_walks_the_missed_tick_count` | interval arithmetic that overflows at `u64::MAX` or walks every missed tick |
| `tests/loops/missed.rs::lp1_missed_intervals_keep_oldest_due_and_coalesce_through_admission` | moved | `crates/core/tests/loops/missed.rs::lp1_missed_intervals_keep_oldest_due_and_coalesce_through_admission` | a missed interval reported at the wrong due time, or an update read as a new admission |
| `tests/loops/missed.rs::lp1_urgent_first_then_oldest_due_then_loop_id` | moved | `crates/core/tests/loops/missed.rs::lp1_urgent_first_then_oldest_due_then_loop_id` | checks admitted out of the urgent, oldest-due, loop-id order |
| `tests/loops/schedules.rs::lp1_schedule_contracts_preserve_wakes_and_consumption` | moved | `crates/core/tests/loops/schedules.rs::lp1_schedule_contracts_preserve_wakes_and_consumption` | (wrapper: runs the 4 proofs below) |
| `tests/loops/schedules.rs::lp1_disabled_holds_checks_and_shadow_still_checks` | moved | `crates/core/tests/loops/schedules.rs::lp1_disabled_holds_checks_and_shadow_still_checks` | a disabled loop that checks, or a shadow loop that doesn't |
| `tests/loops/schedules.rs::lp1_events_need_a_delivered_identity_and_are_not_clock_wakes` | moved | `crates/core/tests/loops/schedules.rs::lp1_events_need_a_delivered_identity_and_are_not_clock_wakes` | an event loop woken by the clock, or a delivered event not admitted and dispatched |
| `tests/loops/schedules.rs::lp1_once_occurrences_are_not_repeated_across_results_or_revisions` | moved | `crates/core/tests/loops/schedules.rs::lp1_once_occurrences_are_not_repeated_across_results_or_revisions` | a once occurrence checked or dispatched again after any result (settled or in flight) or a revision change |
| `tests/loops/schedules.rs::lp1_schedule_boundaries_keep_original_occurrence_times` | moved | `crates/core/tests/loops/schedules.rs::lp1_schedule_boundaries_keep_original_occurrence_times` | a wake checked a millisecond early, or at a shifted time, at the `0` and `u64::MAX` edges |
| `tests/loops/schedules.rs::delivered_event_contracts_preserve_admission_and_identity` | moved | `crates/core/tests/loops/schedules.rs::delivered_event_contracts_preserve_admission_and_identity` | (wrapper: runs the 4 proofs below) |
| `tests/loops/schedules.rs::delivered_events_deduplicate_and_keep_stable_identity_order` | moved | `crates/core/tests/loops/schedules.rs::delivered_events_deduplicate_and_keep_stable_identity_order` | a duplicate delivery admitted twice, an order that depends on input, or a held delivery consumed |
| `tests/loops/schedules.rs::delivered_events_reject_invalid_input_before_admitting_checks` | moved | `crates/core/tests/loops/schedules.rs::delivered_events_reject_invalid_input_before_admitting_checks` | a delivery for an unknown, timer or mismatched loop, or a blank or NUL event id, admitted |
| `tests/loops/schedules.rs::delivered_events_share_check_capacity_and_urgent_ordering_with_schedules` | moved | `crates/core/tests/loops/schedules.rs::delivered_events_share_check_capacity_and_urgent_ordering_with_schedules` | delivered events outside the shared check limit or urgent order |
| `tests/loops/schedules.rs::delivered_events_use_disabled_shadow_and_pending_work_gates` | moved | `crates/core/tests/loops/schedules.rs::delivered_events_use_disabled_shadow_and_pending_work_gates` | a delivery that skips the disabled, shadow or pending-work gate |
| `tests/loops/l6_switches.rs::off_and_on_save_exact_operator_time_and_identity_across_reopen` | kept | itself | a switch that saves the wrong actor, time or order, loses an event on reopen, or a file that isn't owner-only |
| `tests/loops/l6_switches.rs::foreign_unknown_ambiguous_and_untrusted_targets_never_change_switches` | kept | itself | a switch saved for an unknown, foreign, ambiguous or untrusted target or actor |
| `tests/loops/l6_switches.rs::dirty_or_nondefault_checkout_and_clock_reversal_refuse_without_audit` | kept | itself | a switch saved from a dirty or unmerged checkout, or with time running backwards |
| `tests/loops/l6_switches.rs::corrupt_switch_documents_and_linked_files_fail_closed` | kept | itself | a corrupt or symlinked switch file read or overwritten instead of refused |
| `tests/loops/l6_switches.rs::switch_and_scheduler_share_the_lock_and_authority_is_rechecked_under_it` | kept | itself | a switch that saves while the scheduler holds the lock, or skips the authority recheck under it |
| `tests/loops/l6_switches.rs::r1_busy_deadline_changes_no_state_and_retry_saves_once` | kept | itself | a busy deadline that changes state, or a retry that saves twice |
| `tests/loops/l6_cli.rs::cli_off_and_on_call_the_shared_writer_and_print_the_saved_audit` | kept | itself | `loop off`/`on` that doesn't save through the shared writer or prints another audit |
| `tests/loops/l6_cli.rs::malformed_cli_forms_and_missing_trust_save_nothing` | kept | itself | a malformed `loop` command, or one without trusted context, that saves or exits with the wrong code |
| `tests/loops/l6_cli.rs::r1_cli_reports_a_running_pass_and_retry_without_writing` | kept | itself | a busy `loop` command that writes, or doesn't say a pass is running and to retry |
| `tests/loops/l6_config.rs::installed_operator_and_project_are_read_from_private_config_and_rechecked` | kept | itself | an operator not read from install config, or not rechecked on the next switch |
| `tests/loops/l6_config.rs::missing_invalid_duplicate_or_foreign_install_context_never_switches` | kept | itself | an install context with a bad, duplicate or foreign operator, project or repository that switches |
| `tests/loops/l6_config.rs::installed_origin_requires_one_exact_existing_github_remote` | kept | itself | a near-miss, extra or rewritten (`insteadOf`) origin accepted as the GitHub repository |
| `tests/loops/l6_config.rs::real_cli_uses_install_operator_and_refuses_unconfigured_or_caller_identity` | kept | itself | the real `openwiz loop` binary taking a caller's `--operator`, or switching without an installed operator |
| `tests/loops/l6_config.rs::unsupported_or_ambiguous_origin_headers_are_refused` | kept | itself | a case-changed or duplicate origin section read as the origin |
| `tests/loops/l6_api.rs::api_off_and_on_return_the_same_durable_audit_as_cli` | kept | itself | the API's switch saving or answering another audit than the CLI's |
| `tests/loops/l6_api.rs::api_rejects_unapproved_shapes_identity_claims_and_origins_before_writing` | kept | itself | a switch request with a wrong method, query, body, identity claim or origin header that writes |
| `tests/loops/l6_api.rs::api_refuses_unknown_foreign_and_missing_trusted_context` | kept | itself | the API switching an unknown or foreign loop, without context (503) or for a wrong host (421) |
| `tests/loops/l6_api.rs::installed_api_attributes_to_local_operator_and_refuses_missing_invalid_or_foreign_context` | kept | itself | the API attributing a switch to anyone but the installed operator, or switching on a bad install config |
| `tests/loops/l6_api.rs::route_inventory_appends_exactly_the_two_local_switch_writes` | deleted | `tests/web-api/a4_no_mutation.rs::the_route_table_is_the_read_routes_the_send_and_the_create` |  |
| `tests/loops/l6_api.rs::r1_api_busy_is_retryable_and_failed_wait_has_no_audit_event` | kept | itself | a busy switch request that writes, or answers without 503, `Retry-After` and `switch_busy` |
| `tests/loops/l6_api.rs::r5_expired_request_deadline_never_saves_a_switch` | kept | itself | a switch saved after the request deadline passed |
| `tests/loops/l6_api.rs::r5_contended_request_uses_its_shorter_deadline` | kept | itself | a contended switch that waits out the 30-second default instead of the request's deadline |
| `tests/loops/l6_api.rs::r5_expiry_during_locked_authority_read_never_saves` | kept | itself | a switch saved although the deadline passed during the locked authority read |
| `tests/loops/l6_executor.rs::off_survives_restart_and_refresh_and_runner_preserves_every_audit_event` | kept | itself | an off loop checked after a restart or refresh, or a runner pass that loses a switch event |
| `tests/loops/l6_executor.rs::off_prevents_a_deferred_agent_even_after_restart` | kept | itself | a deferred agent started after its loop was switched off |
| `tests/loops/l6_executor.rs::service_and_switch_config_readers_preserve_optional_operator_shape_and_duplicates` | kept | itself | the service's and the store's config readers disagreeing on the operator's shape or a duplicate key |
| `tests/loops/l6_executor.rs::r1_switch_waits_for_running_check_then_saves_once` | kept | itself | a switch that saves during a running check, or saves twice |

## Why the kept tests stay in `tests/loops/`

| File | Crosses | Reason it stays |
| --- | --- | --- |
| `l6_switches.rs` | store, core (`Clock`) | crosses store and core, and runs `git` to build its checkout |
| `fixture.rs` | store | the shared fixture of the four `l6_*` files and the service target; runs `git` |
| `l6_cli.rs` | CLI, store, core | the CLI's command seam over the store's switches |
| `l6_config.rs` | store, the real `openwiz` binary | runs the built CLI and `git` |
| `l6_api.rs` | server, store, adapter, core | the HTTP seam over the store's switches |
| `l6_executor.rs` | service, store, adapter, core | the service's runner against the switches; already its own target in the service crate |
