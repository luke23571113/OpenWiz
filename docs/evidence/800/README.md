# #800 evidence: retiring the start-up switch and the CLI tick

Synthetic fixtures only. Nothing here is a live observation.

## Deleted tests and their keepers

Whole files (the retired code's own tests):

| File | Keeper or behaviour |
| --- | --- |
| `tests/service/t12_handover.rs` | gone: the activation handover the `engine` commands drove; `crates/service/src/bootstrap.rs` stays (D2) |
| `tests/service/install_engine_commands.rs` | gone: `openwiz engine`'s JSON boundary |
| `tests/fleet/pre_effect.rs`, `pre_effect_input.rs` | gone: `--expect-plan` |
| `tests/proof/p08a_allowlist_static.rs` `engine_interpreter_exception_rejects_planted_widening` and `ENGINE_LAUNCHER` | gone: `engine.rs` and its process exception; the same test still refuses a process start in any other non-adapter source |
| `tests/cli-agent/main.rs` `engine_schema_enforces_identity_numeric_and_effect_bounds` | gone: the `openwiz.engine.v1` shape, removed from `contracts/cli.v1.schema.json` |

The map's list of failing `tests/fleet` tests (71, from `cargo test -p openwiz-tests --test fleet` with the executor deleted): 66 are deleted below; five test the kept `fleet due` and are re-seeded instead (next section).

| File | Test | Keeper or behaviour |
| --- | --- | --- |
| `b5_edges.rs` | `b5_approval_time_is_creation_not_edit` | plan part kept by `b5_edges` approval tests on `--dry-run` (`b5_approval_v1_is_stale_and_aligned_table_is_valid`, `b5_r1_*`, `b5_review_r4_*`, `r9_*`) and `b2_planner`; the executing part is gone |
| `b5_edges.rs` | `b5_archive_retains_reviewer_start_order_after_a_recheck` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_edges.rs` | `b5_close_retries_state_but_never_repeats_its_reason_comment` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_edges.rs` | `b5_external_failing_check_never_disappears_from_merge_authority` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_edges.rs` | `b5_noncontiguous_or_repeated_approval_table_separator_grants_no_authority` | plan part kept by `b5_edges` approval tests on `--dry-run` (`b5_approval_v1_is_stale_and_aligned_table_is_valid`, `b5_r1_*`, `b5_review_r4_*`, `r9_*`) and `b2_planner`; the executing part is gone |
| `b5_edges.rs` | `b5_notification_finishes_last_after_a_partial_failure` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_edges.rs` | `b5_ordinary_tick_prints_judgment_only` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_edges.rs` | `b5_pending_recovery_refuses_changed_project_mapping` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_edges.rs` | `b5_r19_foreign_closed_reference_still_blocks_a_replaced_review_head` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_edges.rs` | `b5_r19_unlinked_closed_review_comments_only_block_their_own_ticket_cleanup` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_edges.rs` | `b5_r19_unlinked_closed_review_starts_only_block_their_own_ticket_cleanup` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_edges.rs` | `b5_r19_unlinked_replaced_head_comments_cannot_finish_cleanup` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_edges.rs` | `b5_r19_unlinked_replaced_head_starts_cannot_finish_cleanup` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_edges.rs` | `b5_r19_unlinked_replaced_head_unread_comments_cannot_finish_cleanup` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_edges.rs` | `b5_recovered_starts_are_reported_with_their_outcomes` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_edges.rs` | `b5_release_rechecks_approval_before_removing_held` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_edges.rs` | `b5_review_r12_closed_and_replacement_reviewers_keep_global_start_order` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_edges.rs` | `b5_review_r12_closed_unmerged_pr_reviewer_is_archived_before_completion_record` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_edges.rs` | `b5_review_r12_deleted_closed_pr_head_does_not_erase_reviewer_history` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_edges.rs` | `b5_review_r12_unread_or_foreign_closed_review_association_cannot_finish_cleanup` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_edges.rs` | `b5_review_r18_comment_pages_outlive_one_read_and_keep_execution_budget` | plan reads kept by `b5_review_r3_no_contract_paths_skip_history_reads` and `b5_review_r3b_*` (dry-run and due reads); the executing part is gone |
| `b5_edges.rs` | `b5_review_r2_archive_record_recovers_after_agents_are_already_archived` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_edges.rs` | `b5_review_r3_closed_spec_skips_contract_history_but_keeps_cleanup` | plan reads kept by `b5_review_r3_no_contract_paths_skip_history_reads` and `b5_review_r3b_*` (dry-run and due reads); the executing part is gone |
| `b5_edges.rs` | `b5_review_r3_fifteen_closed_specs_and_two_hundred_merges_keep_cleanup_readable` | plan reads kept by `b5_review_r3_no_contract_paths_skip_history_reads` and `b5_review_r3b_*` (dry-run and due reads); the executing part is gone |
| `b5_edges.rs` | `b5_review_r3_new_contract_merge_and_base_invalidate_cached_authority` | gone: the executor's cached authority refresh between actions |
| `b5_edges.rs` | `b5_review_r3_shared_history_and_targeted_authority_have_bounded_reads` | plan reads kept by `b5_review_r3_no_contract_paths_skip_history_reads` and `b5_review_r3b_*` (dry-run and due reads); the executing part is gone |
| `b5_edges.rs` | `b5_review_r3_targeted_refresh_still_refuses_global_placement_conflicts` | gone: the executor's targeted refresh between actions |
| `b5_edges.rs` | `b5_standalone_follow_up_is_summarized_and_prevents_spec_close` | the planner rule is kept by `tests/fleet/b2_planner.rs` (B2 cases); the executing part is gone |
| `b5_edges.rs` | `b5_start_refuses_changed_project_mapping` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_edges.rs` | `b5_start_refuses_changed_rules` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_edges.rs` | `b5_timed_out_start_is_uncertain_and_never_retried` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_edges.rs` | `b5_unrelated_pr_without_closing_reference_does_not_block_the_fleet` | the planner rule is kept by `tests/fleet/b2_planner.rs` (B2 cases); the executing part is gone |
| `b5_edges.rs` | `x2_a_fixture_read_timeout_stops_a_hung_start_early` | gone: the shared fake's worker handling, exercised only through executing ticks; every kept B5 test still runs on that fake |
| `b5_edges.rs` | `x2_killing_a_client_cancels_its_worker_without_stopping_other_worlds` | gone: the shared fake's worker handling, exercised only through executing ticks; every kept B5 test still runs on that fake |
| `b5_edges.rs` | `x2_shared_fake_keeps_worlds_independent_when_a_world_is_dropped` | gone: the shared fake's worker handling, exercised only through executing ticks; every kept B5 test still runs on that fake |
| `b5_public.rs` | `p4_718_an_outsider_copy_never_stands_in_for_the_tick_s_record` | plan part kept by `b5_public` `p4_718_a_missing_or_malformed_record_authors_row_stops_the_tick`; the executing part is gone |
| `b5_public.rs` | `p4_718_only_the_factory_s_records_count` | plan part kept by `b5_public` `p4_718_a_missing_or_malformed_record_authors_row_stops_the_tick` and the record-author dry-run cases; the executing part is gone |
| `b5_public.rs` | `p4_ambiguous_titles_and_disagreement_never_choose_an_agent` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_public.rs` | `p4_appended_giveup_retires_every_recheck_alias` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_public.rs` | `p4_conflicting_checked_branches_cannot_receive_ci_messages` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_public.rs` | `p4_fallback_record_is_thread_free_and_an_injected_branch_is_refused` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_public.rs` | `p4_helper_and_other_project_titles_do_not_match_the_builder` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_public.rs` | `p4_legacy_giveup_targets_its_explicit_thread_across_new_spans` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_public.rs` | `p4_quiet_giveup_closes_the_whole_span_even_after_an_in_place_edit` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_public.rs` | `p4_recheck_lineage_merge_and_archive_with_public_and_legacy_records` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_public.rs` | `p4_tick_writes_thread_free_records_through_merge_and_finished` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_tick.rs` | `b5_1196_claude_limit_prints_one_restart_and_keeps_the_branch` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_tick.rs` | `b5_1196_near_labels_keep_default_and_unknown_providers_wait` | the planner rule is kept by `tests/fleet/b2_planner.rs` (B2 cases); the executing part is gone |
| `b5_tick.rs` | `b5_1196_only_positive_claude_limit_stops_can_restart` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_tick.rs` | `b5_1196_recorded_fallback_replacement_waits_for_a_reviewer` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_tick.rs` | `b5_1196_restart_needs_its_lock_and_a_saved_record_before_printing` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_tick.rs` | `b5_1196_reviews_follow_the_recorded_builder_family` | the planner rule is kept by `tests/fleet/b2_planner.rs` (B2 cases); the executing part is gone |
| `b5_tick.rs` | `b5_1196_small_ticket_uses_small_builder` | the planner rule is kept by `tests/fleet/b2_planner.rs` (B2 cases); the executing part is gone |
| `b5_tick.rs` | `b5_1196_unknown_builder_family_refuses_a_reviewer` | the planner rule is kept by `tests/fleet/b2_planner.rs` (B2 cases); the executing part is gone |
| `b5_tick.rs` | `b5_1330_claude_fallback_is_refused_without_consuming_the_restart` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_tick.rs` | `b5_concurrent_ticks_share_one_builder_start` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_tick.rs` | `b5_crash_after_dispatch_never_repeats_an_uncertain_start` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_tick.rs` | `b5_merge_requires_every_observed_gate_including_real_success` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_tick.rs` | `b5_missing_orchestrator_leaves_notification_due_and_no_completion_record` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_tick.rs` | `b5_pending_created_start_is_recovered_without_a_second_builder` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_tick.rs` | `b5_plain_tick_names_a_failed_action_and_stays_silent_on_success` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_tick.rs` | `b5_plain_tick_names_a_failed_recovery_outcome_without_repeating_it` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_tick.rs` | `b5_plain_tick_names_a_refused_or_uncertain_action` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_tick.rs` | `b5_pre_merge_authority_recheck_refuses_a_revoked_plan_approval` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_tick.rs` | `b5_pre_merge_base_recheck_refuses_a_move_after_authority_refresh` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |
| `b5_tick.rs` | `b5_synthetic_fleet_reaches_last_merge_without_duplicate_builders` | gone: the executing tick's effects (starts, sends, merges, closes, archives, records, recovery or their outcome lines) |

## Re-seeded `fleet due` keepers

Each set up its world with the executing tick. Each now writes the same GitHub
records, start record and thread directly (`builder_started`, `review_started`
in `b5_tick.rs`; the records are those the tick wrote on `main` at `47c5600`).
Each was checked against a mutation of `crates/cli/src/fleet_tick.rs`:

| Test | Mutation | Result |
| --- | --- | --- |
| `b5_r13_due_ignores_a_superseded_approval_at_the_same_head` | any APPROVE report counts, not only the latest (#852) | fails: "a superseded approval woke the loop" |
| `b5_due_running_builder_is_idle_without_cloudroom_or_state` | open, not closed, tickets become audit candidates | fails: prints candidates #10 and #11 |
| `b5_due_wakes_for_closed_ticket_with_unrecorded_agent_audit_comment` | the closed-ticket audit candidate is dropped | fails |
| `b5_review_r2_github_only_cannot_distinguish_an_unlogged_local_start` | the closed-ticket audit candidate is dropped | fails |
| `p4_github_only_due_defers_thread_free_identity_to_tick` | planned actions are not candidates | fails |

## The retired executing form refuses

`cp1_fleet_forms_separate_execution_from_read_only_candidates_and_plans` now
expects `fleet tick`, `fleet tick --json` and `fleet tick --expect-plan PATH --json`
to be refused by the parser. With the new refusal removed from `parse`, it fails:
[red-parse.log](red-parse.log).
