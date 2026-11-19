# TV7 (#809): the messaging group's ledger

Every test of the `messaging` target (`tests/messaging/`, run as `cargo test
-p openwiz-tests --test messaging`) at this pull request's base, `20a5100`:
189 tests, one row each, in the form of `tools/test-value/README.md`. Two of
them live in shared support (`tests/support/`), which every target compiles
in; they are rowed kept and left alone.

- **Rows:** kept 165, deleted 15, merged 1, moved 8
  (189 rows).
- **Catches** for a kept or moved test is the behaviour it asserts, read from
  its body: a change that breaks it fails the test.
- **Keepers** of the deleted tests were checked by a break where the cut
  test guarded code; see [`keepers.txt`](keepers.txt). The compiler re-check
  and the measurement were checked by reading (README, "Keeper checks").

| Test | Outcome | Keeper | Catches |
| --- | --- | --- | --- |
| `tests/messaging/ad_send_attachments.rs::ad01_a_path_in_the_text_is_sent_as_text_never_attached` | kept | itself | a change that breaks: staged-copy path in text (bare, file://, prefixed) never attached |
| `tests/messaging/ad_send_attachments.rs::ad01_one_tell_carries_every_staged_copy_files_first_then_images` | kept | itself | a change that breaks: one tell, files then images, absolute paths, digest, wording |
| `tests/messaging/ad_send_attachments.rs::ad02_each_unready_attachment_gives_zero_calls_and_is_named` | kept | itself | a change that breaks: each unready attachment alone refused, named, zero calls |
| `tests/messaging/ad_send_attachments.rs::ad03_one_refusal_names_every_problem_and_no_subset_is_ever_sent` | kept | itself | a change that breaks: one refusal names all five problems; no subset sent |
| `tests/messaging/ad_send_attachments.rs::ad04_a_0_0_3_record_without_attachments_still_matches` | kept | itself | a change that breaks: pre-attachment record replays; same op id with attachment conflicts |
| `tests/messaging/ad_send_attachments.rs::ad04_same_op_id_and_payload_is_one_call_any_attachment_difference_is_refused` | kept | itself | a change that breaks: same payload replays; added, removed, reordered, changed bytes conflict |
| `tests/messaging/ad_send_attachments.rs::ad05_steer_with_attachments_is_refused_with_zero_calls_local_and_cloud` | kept | itself | a change that breaks: steer with attachments refused, exit 2, stderr text, no call |
| `tests/messaging/ad_send_attachments.rs::ad05_the_adapter_never_starts_a_steer_with_attachments` | kept | itself | a change that breaks: adapter returns NotStarted for steer with attachments; no call |
| `tests/messaging/ad_send_attachments.rs::ad07_every_row_of_the_outcome_table` | kept | itself | a change that breaks: sent, queued, rejected, timeout and undocumented each map to their status, record and retention; failed and uncertain never say handed to CloudRoom |
| `tests/messaging/ad_send_attachments.rs::ad07_legacy_queued_receipt_keeps_staged_copies_and_prompt` | deleted | `tests/messaging/ad_send_attachments.rs::ad09_retention_follows_the_table` (copies kept while uncertain) and `tests/messaging/m04_outcome_mapping.rs::unobserved_documented_queued_receipts_are_uncertain` (the same receipt is uncertain) |  |
| `tests/messaging/ad_send_attachments.rs::ad09_attachment_ls_and_rm_see_the_claim_through_the_release_binary` | kept | itself | a change that breaks: killed send's attachment listed as kept; rm refused, exit 14 |
| `tests/messaging/ad_send_attachments.rs::ad09_retention_follows_the_table` | kept | itself | a change that breaks: copies deleted after accepted outcome, kept on failed and uncertain |
| `tests/messaging/ad_send_attachments.rs::ad10_a_crash_at_each_step_keeps_the_attachments_and_dispatches_nothing` | kept | itself | a change that breaks: killed send keeps attachment; claim matches outcome; no second call |
| `tests/messaging/ad_send_attachments.rs::ad13_attach_and_attachment_send_one_tell_and_the_json_matches_the_text` | kept | itself | a change that breaks: --attach plus --attachment: one tell, files first; JSON matches text |
| `tests/messaging/ad_send_attachments.rs::ad13_attach_that_fails_on_any_path_sends_nothing_and_prints_every_result` | kept | itself | a change that breaks: bad --attach exits 5, lists every path, reads and sends nothing |
| `tests/messaging/ad_send_attachments.rs::ad13_json_help_describes_attach_path_failures_for_send_and_new` | kept | itself | a change that breaks: --help JSON text documents attach-path report and exit 5 |
| `tests/messaging/ad_send_attachments.rs::ad13_json_help_describes_store_failures_for_send_and_new` | kept | itself | a change that breaks: store-open failure exits 10 with stated output, send and new |
| `tests/messaging/ad_send_attachments.rs::ad13_preview_and_check_take_no_attachment` | kept | itself | a change that breaks: --preview and --check refuse attachment flags, exit 2, no read |
| `tests/messaging/ad_send_attachments.rs::dispatch_write_failure_stops_the_send` | kept | itself | a change that breaks: failed dispatching mark returns store error, no call |
| `tests/messaging/b8_memory.rs::b8_the_fakes_peak_memory_grows_with_the_dispatchs_total_bytes` | deleted | `tests/messaging/ad_send_attachments.rs::ad01_one_tell_carries_every_staged_copy_files_first_then_images` (a send of staged attachments); the cut test measured the fake's model of `room-cli`, not OpenWiz, for B2's recorded evidence |  |
| `tests/messaging/m01_exact_invocation.rs::invalid_op_ids_are_refused_with_no_call` | kept | itself | a change that breaks: bad op ids (".x", "_x", "a.b", 65 chars) refused by parse and CLI, no call |
| `tests/messaging/m01_exact_invocation.rs::invalid_text_is_refused_with_no_call` | kept | itself | a change that breaks: five invalid texts refused before any claim; cap counted in bytes |
| `tests/messaging/m01_exact_invocation.rs::one_send_makes_one_tell_in_the_chosen_shape` | kept | itself | a change that breaks: one accepted send; exact reads, then one queue tell argv; no excluded flag |
| `tests/messaging/m01_exact_invocation.rs::the_cli_passes_dash_leading_and_stdin_text_byte_for_byte` | kept | itself | a change that breaks: dash-leading argument and piped stdin keep exact bytes incl. newline |
| `tests/messaging/m01_exact_invocation.rs::the_cli_refuses_invalid_text_with_no_call` | kept | itself | a change that breaks: CLI exits 2, empty stdout, no tell for invalid text |
| `tests/messaging/m01_exact_invocation.rs::the_text_is_one_argument_byte_for_byte` | kept | itself | a change that breaks: ten texts (dash, Unicode, bidi, 16 KiB) reach one tell unchanged |
| `tests/messaging/m02_one_target.rs::a_target_that_is_not_found_gets_no_tell` | kept | itself | a change that breaks: send NotFound makes zero tells; CLI exits 3 |
| `tests/messaging/m02_one_target.rs::archived_and_hidden_targets_are_refused_with_no_tell` | kept | itself | a change that breaks: archived and hidden targets refused, zero tells |
| `tests/messaging/m02_one_target.rs::missing_visibility_is_refused_without_a_tell` | kept | itself | a change that breaks: missing visibility field fails closed, no tell |
| `tests/messaging/m02_one_target.rs::the_cli_takes_exactly_one_target` | kept | itself | a change that breaks: two ids, comma, space, dash-led id, no id: exit 2, no read |
| `tests/messaging/m02_one_target.rs::the_target_is_resolved_in_the_same_operation` | kept | itself | a change that breaks: show precedes tell on same target; report carries the read title |
| `tests/messaging/m02_one_target.rs::unknown_visibility_is_refused_without_a_tell` | kept | itself | a change that breaks: unrecognised visibility value fails closed, no tell; paused-queue ack does not bypass |
| `tests/messaging/m03_mode_rules.rs::an_unsupported_mode_is_reported_with_no_second_call` | kept | itself | a change that breaks: unsupported steer reported; one steer call; CLI steer no fallback |
| `tests/messaging/m03_mode_rules.rs::the_cli_has_no_other_mode` | kept | itself | a change that breaks: --mode, --mode=, --auto, --steer=no refused, exit 2, no call |
| `tests/messaging/m03_mode_rules.rs::the_requested_mode_is_the_one_passed` | kept | itself | a change that breaks: queue and steer argv; JSON requested_mode per send |
| `tests/messaging/m04_outcome_mapping.rs::a_call_that_never_started_is_failed_not_uncertain` | kept | itself | a change that breaks: missing program gives Failed call_not_started and zero tells |
| `tests/messaging/m04_outcome_mapping.rs::a_started_tell_with_a_wait_error_is_not_reported_as_not_started` | kept | itself | a change that breaks: started tell with failed wait stays uncertain (CallNotConfirmed), not NotStarted |
| `tests/messaging/m04_outcome_mapping.rs::documented_rejections_are_failed_with_the_reason` | kept | itself | a change that breaks: documented 404/400 rejections map to Failed with their reason, one call each |
| `tests/messaging/m04_outcome_mapping.rs::everything_else_is_uncertain` | kept | itself | a change that breaks: eight undocumented outcomes map to Uncertain with exact reason, no retry |
| `tests/messaging/m04_outcome_mapping.rs::no_raw_room_cli_text_reaches_any_output` | kept | itself | a change that breaks: planted room-cli markers absent from stdout, stderr and record |
| `tests/messaging/m04_outcome_mapping.rs::observed_receipt_guards_fail_closed` | kept | itself | a change that breaks: sent receipts with missing, bad, duplicate or extra fields are Uncertain, never retried |
| `tests/messaging/m04_outcome_mapping.rs::observed_sent_receipt_is_accepted_once` | deleted | `tests/messaging/m04_outcome_mapping.rs::pc_probe_sent_queue` |  |
| `tests/messaging/m04_outcome_mapping.rs::pc_probe_busy_queue` | kept | itself | a change that breaks: observed Local busy queued receipt gives queued, thread_busy, replays |
| `tests/messaging/m04_outcome_mapping.rs::pc_probe_busy_queue_allows_the_owner_noted_user_sender` | kept | itself | a change that breaks: user-initiated queued row with null sender is accepted as queued thread_busy |
| `tests/messaging/m04_outcome_mapping.rs::pc_probe_claude_queued_steer` | kept | itself | a change that breaks: observed Steer queued receipt gives queued, waiting_on not_reported, replays from record |
| `tests/messaging/m04_outcome_mapping.rs::pc_probe_cloud_queued_queue` | kept | itself | a change that breaks: observed Cloud Queue-requested queued receipt gives queued, not_reported, replays |
| `tests/messaging/m04_outcome_mapping.rs::pc_probe_missing_wait_reason_round_trips_without_inventing_one` | deleted | `tests/messaging/m04_outcome_mapping.rs::pc_probe_claude_queued_steer` |  |
| `tests/messaging/m04_outcome_mapping.rs::pc_probe_sent_queue` | kept | itself | a change that breaks: observed sent Queue accepted, replays from record, schema-valid, one write |
| `tests/messaging/m04_outcome_mapping.rs::pc_probe_sent_steer` | kept | itself | a change that breaks: observed sent Steer accepted, replays, schema-valid, accepted prompt text erased |
| `tests/messaging/m04_outcome_mapping.rs::pc_probe_shapes_reject_drift_at_every_depth` | kept | itself | a change that breaks: each queued-receipt drift at every depth is UnexpectedReceipt, one call |
| `tests/messaging/m04_outcome_mapping.rs::sent_is_accepted_and_never_completion` | kept | itself | a change that breaks: sent is Accepted for Queue and Steer; wording never says complete |
| `tests/messaging/m04_outcome_mapping.rs::the_requested_mode_and_the_reported_delivery_are_kept_apart` | kept | itself | a change that breaks: Steer uncertain gives "Steer requested · uncertain" and null waiting_on |
| `tests/messaging/m04_outcome_mapping.rs::the_target_reads_not_found_is_an_exact_line` | kept | itself | a change that breaks: a read line merely mentioning 404 is TargetNotRead, not NotFound |
| `tests/messaging/m04_outcome_mapping.rs::unobserved_documented_queued_receipts_are_uncertain` | kept | itself | a change that breaks: seven documented-but-unobserved queued receipts give Uncertain, "unobserved" gap, one call |
| `tests/messaging/m04_outcome_mapping.rs::unobserved_receipts_stay_uncertain_and_say_so` | kept | itself | a change that breaks: queued-without-message, Steer-vs-queue mismatch, unsupported receipts give Uncertain, "unobserved" gap |
| `tests/messaging/m05_effects.rs::a_paused_queue_is_shown_and_not_sent_without_acknowledgement` | kept | itself | a change that breaks: CLI shows paused-queue text, exits 5, sends nothing until --resume-paused-queue |
| `tests/messaging/m05_effects.rs::duplicate_host_rows_keep_preview_effects_unknown` | kept | itself | a change that breaks: duplicate machine rows for one host give unknown effect and one gap |
| `tests/messaging/m05_effects.rs::duplicate_queue_rows_require_acknowledgement` | kept | itself | a change that breaks: duplicate thread-list rows refuse send unless acknowledged; one tell after ack |
| `tests/messaging/m05_effects.rs::effects_are_worked_out_and_recorded_before_the_call` | kept | itself | a change that breaks: dispatching record on disk holds the same effects that were shown |
| `tests/messaging/m05_effects.rs::effects_for_every_state_read_through_the_adapter` | kept | itself | a change that breaks: each read state yields expected effect, ack flag and paused-queue text |
| `tests/messaging/m05_effects.rs::preview_refuses_repeated_machine_list_keys_and_keeps_single_key_facts` | kept | itself | a change that breaks: repeated machine-list status keys give unknown host effect; single key kept |
| `tests/messaging/m05_effects.rs::preview_refuses_repeated_show_keys_and_keeps_single_key_effects` | kept | itself | a change that breaks: repeated thread-show keys give refused target_not_read; single-key shows keep effects |
| `tests/messaging/m05_effects.rs::preview_refuses_repeated_thread_list_keys_and_keeps_single_key_facts` | kept | itself | a change that breaks: repeated or non-JSON thread-list keys give unknown and needs-ack; single keys kept |
| `tests/messaging/m05_effects.rs::send_effects_contracts_preserve_original_cases` | moved | `crates/core/tests/send_effects.rs::send_effects_contracts_preserve_original_cases` | a change that breaks: runs two named core-rule proofs, which have no #[test] of their own |
| `tests/messaging/m05_effects.rs::the_reads_age_counts_from_the_start_of_the_target_read` | kept | itself | a change that breaks: read age ≥400 ms when the thread-list read takes 500 ms (real clock) |
| `tests/messaging/m05_effects.rs::unique_host_rows_preserve_preview_effects` | kept | itself | a change that breaks: other-id duplicates ignored; connected host keeps its effect |
| `tests/messaging/m05_effects.rs::unique_queue_rows_keep_their_effects` | kept | itself | a change that breaks: duplicates of other ids leave this target's effects known |
| `tests/messaging/m05_effects.rs::unknowns_stay_unknown_in_json_and_text` | kept | itself | a change that breaks: unrecognised status shows "unknown (why)" in send JSON and text |
| `tests/messaging/m06_lost_acknowledgement.rs::accepted_then_timed_out_is_uncertain_keeps_the_text_and_never_resends` | kept | itself | a change that breaks: hang gives uncertain TimedOut; text kept; replay and duplicate blocked; no resend |
| `tests/messaging/m06_lost_acknowledgement.rs::cli_duplicate_refusal_retains_stored_reconciliation_metadata` | kept | itself | a change that breaks: refusal shows stored reconciliation metadata; no read, no call |
| `tests/messaging/m06_lost_acknowledgement.rs::one_message_matching_on_text_and_time_is_still_uncertain` | kept | itself | a change that breaks: reconcile() counts and Attributed branch on fixture observations |
| `tests/messaging/m06_lost_acknowledgement.rs::the_cli_refuses_a_blind_resend_and_shows_the_earlier_send` | kept | itself | a change that breaks: CLI exit 9 names earlier op; --accept-possible-duplicate sends again, exit 6 |
| `tests/messaging/m07_op_id_binding.rs::a_recorded_failure_is_returned_not_retried` | kept | itself | a change that breaks: replayed failed op returns failure with no read or call |
| `tests/messaging/m07_op_id_binding.rs::reuse_with_a_different_target_mode_or_text_is_refused_with_no_call` | kept | itself | a change that breaks: target, mode or text change refused with exact differs list; no call |
| `tests/messaging/m07_op_id_binding.rs::the_binding_is_the_target_the_mode_and_a_sha256_of_the_text` | kept | itself | a change that breaks: SHA-256 vectors incl. 1 MB; binding fields in report and record |
| `tests/messaging/m07_op_id_binding.rs::the_same_op_id_and_binding_makes_one_call` | kept | itself | a change that breaks: same op id replays recorded outcome; one tell; no read on replay |
| `tests/messaging/m08_cross_process_claim.rs::many_processes_racing_on_one_op_id_make_exactly_one_tell` | kept | itself | a change that breaks: 12 racing processes make one tell and one fresh owner |
| `tests/messaging/m08_cross_process_claim.rs::racing_on_one_op_id_with_different_texts_still_sends_once` | kept | itself | a change that breaks: two texts racing: still one tell, one fresh owner |
| `tests/messaging/m09_crash_recovery.rs::an_abandoned_record_is_recovered_by_the_duplicate_check_too` | kept | itself | a change that breaks: abandoned dispatching record: same-text send exits 9, no call |
| `tests/messaging/m09_crash_recovery.rs::stopped_after_the_call_before_the_outcome_recovers_as_uncertain` | kept | itself | a change that breaks: crash after call, before outcome: uncertain, never accepted |
| `tests/messaging/m09_crash_recovery.rs::stopped_after_the_claim_recovers_as_failed_before_dispatch` | kept | itself | a change that breaks: kill after claim recovers failed, no call, no redispatch |
| `tests/messaging/m09_crash_recovery.rs::stopped_after_the_dispatching_mark_recovers_as_uncertain` | kept | itself | a change that breaks: abort after mark recovers uncertain on disk; no call |
| `tests/messaging/m09_crash_recovery.rs::stopped_during_the_call_recovers_as_uncertain` | kept | itself | a change that breaks: kill inside the call recovers uncertain; no redispatch |
| `tests/messaging/m10_record.rs::a_claimer_takes_a_lock_released_while_it_waits` | kept | itself | a change that breaks: claim waits on a lock its holder drops, then is Owned |
| `tests/messaging/m10_record.rs::a_relative_state_directory_override_is_refused` | merged | `crates/store/tests/state_dir.rs::the_default_state_directory_is_the_owners_and_outside_the_repository` | (as its keeper) |
| `tests/messaging/m10_record.rs::a_state_directory_inside_a_repository_is_refused` | moved | `crates/store/tests/state_dir.rs::a_state_directory_inside_a_repository_is_refused` | a change that breaks: state inside repo refused, also via symlink from outside; nothing created |
| `tests/messaging/m10_record.rs::a_state_directory_others_can_read_is_refused` | kept | itself | a change that breaks: 0755 state refused by store and send; nothing sent |
| `tests/messaging/m10_record.rs::an_invalid_op_id_never_becomes_a_path` | kept | itself | a change that breaks: bad op ids fail to deserialize; planted escaping record never used as path |
| `tests/messaging/m10_record.rs::concurrent_writers_keep_every_record_whole` | kept | itself | a change that breaks: 12 parallel sends give whole records and no temp files |
| `tests/messaging/m10_record.rs::every_created_directory_is_synced_in_its_parent` | moved | `crates/store/tests/state_dir.rs::every_created_directory_is_synced_in_its_parent` | a change that breaks: create_dir_synced syncs parent, in store source |
| `tests/messaging/m10_record.rs::every_opener_syncs_the_whole_directory_chain` | moved | `crates/store/tests/state_dir.rs::every_opener_syncs_the_whole_directory_chain` | a change that breaks: each opener syncs every ancestor of sends, incl. dirs another opener made |
| `tests/messaging/m10_record.rs::every_write_syncs_the_file_and_its_directory` | moved | `crates/store/tests/state_dir.rs::every_write_syncs_the_file_and_its_directory` | a change that breaks: write_record orders sync_all, rename, sync_all in source |
| `tests/messaging/m10_record.rs::no_path_trick_puts_the_record_inside_a_repository` | moved | `crates/store/tests/state_dir.rs::no_path_trick_puts_the_record_inside_a_repository` | a change that breaks: sends symlink into repo and `..` path refused; repo stays empty |
| `tests/messaging/m10_record.rs::the_default_state_directory_is_the_owners_and_outside_the_repository` | moved | `crates/store/tests/state_dir.rs::the_default_state_directory_is_the_owners_and_outside_the_repository` | a change that breaks: default dir from HOME/XDG/env; no HOME refused; not in repo |
| `tests/messaging/m10_record.rs::the_dispatching_mark_is_on_disk_before_the_call` | kept | itself | a change that breaks: dispatching state, dispatching_at, text kept, delivery null at call |
| `tests/messaging/m10_record.rs::the_record_is_readable_by_the_owner_only` | kept | itself | a change that breaks: state, sends/, record and lock modes 0700/0600 |
| `tests/messaging/m10_record.rs::the_text_is_kept_only_while_uncertain_or_failed` | kept | itself | a change that breaks: text kept on failed/not-found/uncertain, cleared on accepted/queued |
| `tests/messaging/m10_record.rs::unknown_send_record_schemas_are_unavailable_without_side_effects` | kept | itself | a change that breaks: unknown record schemas exit 10, no tell, store unchanged |
| `tests/messaging/m10_record.rs::v1_send_records_still_load_and_replay` | kept | itself | a change that breaks: v1 records replay with no provider call |
| `tests/messaging/m11_inventory_unchanged.rs::no_inventory_command_reaches_the_write` | kept | itself | a change that breaks: ls/show/--help never tell; `send` refused by run with code 2 |
| `tests/messaging/m11_inventory_unchanged.rs::the_inventory_api_keeps_its_signatures` | deleted | `crates/core/tests/inventory.rs::a_session_listed_twice_appears_once_with_a_gap` (a compiler re-check: a changed `ops::list` or `show` signature fails the build of the CLI, the server and every caller) |  |
| `tests/messaging/m11_inventory_unchanged.rs::the_inventory_code_cannot_name_the_write` | kept | itself | a change that breaks: inventory sources never name tell/messaging; SessionSource has no send/tell |
| `tests/messaging/m12_allowlist.rs::m12_the_terminal_send_exception_refuses_any_widening` | kept | itself | a change that breaks: terminal spells "send" once in the action seam, no other write word; stays: M12 is the protected allowlist guard |
| `tests/messaging/m12_allowlist.rs::no_product_source_spells_an_excluded_flag_or_another_write` | kept | itself | a change that breaks: no crate spells excluded flags or write words outside allowlisted spots; stays: M12 is the protected allowlist guard |
| `tests/messaging/m12_allowlist.rs::service_update_exception_never_allows_a_command_or_another_file` | kept | itself | a change that breaks: "update" exemption matches only the JSON field or updater const; stays: M12 is the protected allowlist guard |
| `tests/messaging/m12_allowlist.rs::t5_loop_pause_exception_rejects_other_paths_and_command_like_occurrences` | kept | itself | a change that breaks: loop-pause exemption accepts only its one allowlist arm; stays: M12 is the protected allowlist guard |
| `tests/messaging/m12_allowlist.rs::t5_loop_resume_exception_rejects_other_paths_and_command_like_occurrences` | kept | itself | a change that breaks: loop-resume exemption accepts only its one allowlist arm; stays: M12 is the protected allowlist guard |
| `tests/messaging/m12_allowlist.rs::the_fake_refuses_every_other_write_and_every_other_tell_shape` | kept | itself | a change that breaks: fake exits 97 on 12 non-allowlisted shapes, counts none; stays: M12 is the protected allowlist guard |
| `tests/messaging/m12_allowlist.rs::the_fake_takes_attachment_flags_only_with_staged_paths_in_queue` | kept | itself | a change that breaks: fake takes --file/--image only in queue, with staged absolute paths; stays: M12 is the protected allowlist guard |
| `tests/messaging/m12_allowlist.rs::thread_tell_is_sends_only_write_in_exactly_its_shape` | kept | itself | a change that breaks: read argv have no mutating word; tell argv exact for varied text; stays: M12 is the protected allowlist guard |
| `tests/messaging/m13_drift.rs::a_failed_version_read_never_echoes_its_error_text_in_send` | kept | itself | a change that breaks: failed version read shows "(detail withheld)" in report, text, JSON, record |
| `tests/messaging/m13_drift.rs::a_record_from_before_250_never_replays_or_looks_up_as_tested` | kept | itself | a change that breaks: pre-#250 record judged by this build in replay, lookup; nothing resent |
| `tests/messaging/m13_drift.rs::a_record_with_an_empty_version_never_replays_as_tested` | kept | itself | a change that breaks: record with empty known version never replays as tested |
| `tests/messaging/m13_drift.rs::a_record_with_no_tested_version_never_replays_as_tested` | deleted | `tests/messaging/m13_drift.rs::a_record_from_before_250_never_replays_or_looks_up_as_tested` |  |
| `tests/messaging/m13_drift.rs::a_send_at_the_reads_tested_version_is_not_live_tested_for_sending` | kept | itself | a change that breaks: v127 send is not live-tested in report, record, text, JSON; release regression 0.0.3-R1-fresh runs it by name |
| `tests/messaging/m13_drift.rs::an_earlier_untested_version_record_replays_as_failed` | kept | itself | a change that breaks: pre-#37 record without source loads, replays failed with exit 5 |
| `tests/messaging/m13_drift.rs::an_unexpected_receipt_is_uncertain_with_a_gap` | kept | itself | a change that breaks: eight drift receipts uncertain, name a gap, never accepted, recorded |
| `tests/messaging/m13_drift.rs::an_unrecognised_or_unreadable_version_never_stops_a_send` | kept | itself | a change that breaks: unknown version gives controlled gap; provider text never shown; send goes on |
| `tests/messaging/m13_drift.rs::an_untested_version_never_stops_a_send` | kept | itself | a change that breaks: versions 0.44.0 and 0.43.1 send as v127 and report not-live-tested |
| `tests/messaging/m13_drift.rs::help_names_each_kind_of_runs_own_tested_version` | deleted | `tests/proof/p04_partial_failures.rs::help_documents_the_commands_the_order_and_the_exit_codes` (the same four lines) |  |
| `tests/messaging/m13_drift.rs::help_names_provider_reads_without_a_version_read` | kept | itself | a change that breaks: preview and models read no --version; help names the exceptions |
| `tests/messaging/m13_drift.rs::help_version_wording_agrees_with_offline_check` | kept | itself | a change that breaks: --check runs offline; help wording has no "Every run reads" |
| `tests/messaging/m13_drift.rs::send_has_its_own_tested_version_never_the_reads` | deleted | `tests/messaging/m13_drift.rs::a_send_at_the_reads_tested_version_is_not_live_tested_for_sending` (send's) and `tests/proof/p12_drift.rs::an_untested_version_is_reported_and_never_stops` (the reads') |  |
| `tests/messaging/m13_drift.rs::the_schema_says_send_has_its_own_tested_version` | kept | itself | a change that breaks: schema source description text and tested_version/version_tested types |
| `tests/messaging/m14_cli.rs::errors_go_to_stderr_with_stdout_empty` | kept | itself | a change that breaks: send usage errors exit 2, stdout empty, one stderr line |
| `tests/messaging/m14_cli.rs::generated_id_guidance_checks_the_record_without_sending_again` | kept | itself | a change that breaks: generated-id guidance; recheck reads the record, makes no call |
| `tests/messaging/m14_cli.rs::help_documents_send_its_flags_and_its_limits` | kept | itself | a change that breaks: send --help names each flag and limit; equals help(); reads nothing |
| `tests/messaging/m14_cli.rs::m14_cli_parser_contracts_preserve_original_cases` | kept | itself | a change that breaks: four sub-proofs: exit codes documented, inline and ./ attach paths, preview/check help, op-id operands |
| `tests/messaging/m14_cli.rs::missing_attachment_value_must_not_swallow_read_only_switches_and_dispatch` | kept | itself | a change that breaks: "--attach/--attachment --check, --preview, --" refused; no call, no staging |
| `tests/messaging/m14_cli.rs::missing_op_id_value_must_not_swallow_check_and_dispatch` | kept | itself | a change that breaks: "--op-id --check" is a usage error: no call, no state |
| `tests/messaging/m14_cli.rs::queued_receipt_id_matches_json_and_text` | kept | itself | a change that breaks: queued receipt id in JSON and as a text line |
| `tests/messaging/m14_cli.rs::repeated_op_id_options_are_refused_without_reads_or_state` | kept | itself | a change that breaks: repeated --op-id forms refused, exit 2, no call or state |
| `tests/messaging/m14_cli.rs::send_text_preserves_each_reported_gap_subject_and_detail` | kept | itself | a change that breaks: each text gap line equals "gap: subject · detail" |
| `tests/messaging/m14_cli.rs::send_text_reports_the_effects_read_age` | kept | itself | a change that breaks: text shows "effects (read 4s before sending)"; JSON read_age 4500 |
| `tests/messaging/m14_cli.rs::terminal_stdin_is_refused_before_reading_text_or_opening_state` | kept | itself | a change that breaks: terminal stdin never read; exit 2; no state, no call |
| `tests/messaging/m14_cli.rs::the_json_matches_the_text_and_the_schema` | kept | itself | a change that breaks: eleven send outcomes: JSON schema-valid, text carries each value, exit codes |
| `tests/messaging/m14_cli.rs::the_release_build_sends_through_the_fake` | kept | itself | a change that breaks: release openwiz sends piped stdin once; generated op id shown |
| `tests/messaging/m14_cli.rs::valid_op_id_forms_preserve_check_and_literal_message_text` | kept | itself | a change that breaks: valid op ids work inline and separate; --check text stays literal |
| `tests/messaging/m15_text_only.rs::a_file_path_in_the_text_is_sent_as_text` | kept | itself | a change that breaks: path text sent verbatim, never as --file/--image; CLI passes path as text |
| `tests/messaging/m15_text_only.rs::there_is_no_file_or_image_option` | kept | itself | a change that breaks: send refuses --file, --image, --attach without value, --attachment path; exit 2, no tell |
| `tests/messaging/m16_preview.rs::a_preview_after_the_budget_ran_out_is_refused_like_the_send` | kept | itself | a change that breaks: preview refused budget_exhausted, keeps effects, CLI exit 5 |
| `tests/messaging/m16_preview.rs::a_preview_costs_two_or_three_reads` | deleted | `tests/messaging/m05_effects.rs::preview_refuses_repeated_thread_list_keys_and_keeps_single_key_facts` (Cloud: exactly two reads) and `tests/messaging/m05_effects.rs::preview_refuses_repeated_machine_list_keys_and_keeps_single_key_facts` (Local: exactly three) |  |
| `tests/messaging/m16_preview.rs::a_preview_makes_no_claim_and_no_tell` | kept | itself | a change that breaks: preview never tells, claims or writes; only target reads, all targets |
| `tests/messaging/m16_preview.rs::a_preview_names_each_refusal` | kept | itself | a change that breaks: not-found, hidden, archived refusals named; "would be refused" wording |
| `tests/messaging/m16_preview.rs::a_preview_takes_no_text_and_no_send_option` | kept | itself | a change that breaks: --preview refuses text, attachments, --op-id, resume and duplicate flags |
| `tests/messaging/m16_preview.rs::a_previews_effects_equal_sends_for_every_send_fixture` | kept | itself | a change that breaks: preview effects, title, status, refusal equal send's on every fixture |
| `tests/messaging/m16_preview.rs::an_invalid_target_id_is_refused_with_no_read` | kept | itself | a change that breaks: invalid target id errors, CLI exits 2, zero room-cli calls |
| `tests/messaging/m16_preview.rs::only_the_preview_works_out_effects` | deleted | `tests/messaging/m16_preview.rs::a_previews_effects_equal_sends_for_every_send_fixture` (the cut test was a source grep; the behaviour, the preview's effects equal send's, is the keeper's) |  |
| `tests/messaging/m16_preview.rs::the_cli_preview_matches_the_schema_and_the_text` | kept | itself | a change that breaks: CLI JSON is schema-valid, exit code per status, text carries fields |
| `tests/messaging/m16_preview.rs::the_cli_preview_summary_describes_a_pending_interaction` | kept | itself | a change that breaks: pending-interaction preview exits 0, says "waits for the pending interaction" |
| `tests/messaging/m16_preview.rs::the_cli_preview_summary_names_the_requested_mode` | kept | itself | a change that breaks: summary starts "Queue requested" or "Steer requested" per mode |
| `tests/messaging/m16_preview.rs::the_release_build_previews_through_the_fake` | kept | itself | a change that breaks: release binary preview is schema-valid, stderr empty, claims nothing |
| `tests/messaging/m17_lookup.rs::a_check_needs_an_op_id_and_takes_no_text_or_send_option` | kept | itself | a change that breaks: --check needs --op-id; refuses text, attachments, send flags, bad op id |
| `tests/messaging/m17_lookup.rs::a_check_with_no_send_record_creates_nothing` | kept | itself | a change that breaks: no record creates no state dir or sends/ dir; exit 11 |
| `tests/messaging/m17_lookup.rs::a_known_op_id_gives_its_recorded_report_with_no_call` | kept | itself | a change that breaks: recorded report returned whole, marked replayed, no call, record unchanged |
| `tests/messaging/m17_lookup.rs::a_read_only_store_refuses_every_write` | kept | itself | a change that breaks: read-only store refuses claim, update, withdraw and matching writes |
| `tests/messaging/m17_lookup.rs::a_stopped_senders_record_is_recovered_never_resent` | kept | itself | a change that breaks: stopped records show failed or uncertain, recovered, with reasons, no call |
| `tests/messaging/m17_lookup.rs::an_in_progress_op_id_says_so_and_stays_its_owners` | kept | itself | a change that breaks: claimed and dispatching records report in_progress; owner still finishes |
| `tests/messaging/m17_lookup.rs::an_op_id_bound_to_another_target_is_not_this_targets` | deleted | `tests/messaging/m17_lookup.rs::the_cli_check_matches_the_schema_and_the_text_and_reads_nothing` |  |
| `tests/messaging/m17_lookup.rs::an_unknown_op_id_has_no_record_and_nothing_is_made` | deleted | `tests/messaging/m17_lookup.rs::a_check_with_no_send_record_creates_nothing` |  |
| `tests/messaging/m17_lookup.rs::check_refuses_a_send_record_whose_attachments_disagree_with_its_binding` | kept | itself | a change that breaks: record with mismatched attachment digest refused, exit 10, file untouched |
| `tests/messaging/m17_lookup.rs::no_lookup_path_changes_the_send_record` | kept | itself | a change that breaks: every lookup form leaves record listing byte-identical, no call |
| `tests/messaging/m17_lookup.rs::the_cli_check_matches_the_schema_and_the_text_and_reads_nothing` | kept | itself | a change that breaks: six check cases give pinned exit codes, schema-valid JSON, matching text, no call |
| `tests/messaging/m17_lookup.rs::the_release_build_checks_with_no_call` | kept | itself | a change that breaks: release binary check replays the send, makes no call |
| `tests/messaging/m18_in_flight.rs::a_finished_or_stopped_send_is_not_in_flight` | kept | itself | a change that breaks: finished and stopped-before-mark sends don't block; stopped-after-mark does |
| `tests/messaging/m18_in_flight.rs::a_new_op_id_is_refused_while_the_same_send_is_claimed_or_dispatching` | kept | itself | a change that breaks: claimed and dispatching refused; no record, no read, schema-valid |
| `tests/messaging/m18_in_flight.rs::a_record_reread_under_the_lock_is_matched_again` | kept | itself | a change that breaks: uncertain scan drops a record rebound to other text under lock |
| `tests/messaging/m18_in_flight.rs::a_scan_never_resurrects_a_withdrawn_claim` | kept | itself | a change that breaks: withdrawn record never recreated by any scan |
| `tests/messaging/m18_in_flight.rs::a_sender_that_slips_in_before_the_claim_is_still_caught` | kept | itself | a change that breaks: racer claiming after pre-check is caught; claim withdrawn |
| `tests/messaging/m18_in_flight.rs::accepting_a_possible_duplicate_sends_anyway` | deleted | `tests/messaging/m18_in_flight.rs::across_processes_a_second_op_id_waits_for_nothing_and_sends_nothing` (its acknowledged third send) |  |
| `tests/messaging/m18_in_flight.rs::across_processes_a_second_op_id_waits_for_nothing_and_sends_nothing` | kept | itself | a change that breaks: second op id refused while first in call; acknowledged third sends |
| `tests/messaging/m18_in_flight.rs::duplicate_refusal_keeps_distinct_prior_ids_once_in_claimed_time_order` | kept | itself | a change that breaks: earlier sends listed once each, in claim-time order |
| `tests/messaging/m18_in_flight.rs::duplicate_refusal_summary_distinguishes_uncertain_in_flight_and_mixed` | kept | itself | a change that breaks: summary wording and earlier rows for uncertain, in-flight, mixed |
| `tests/messaging/m18_in_flight.rs::many_new_op_ids_racing_on_one_send_make_at_most_one_tell` | kept | itself | a change that breaks: 8 racers make at most one call; exits only 0 or 9 |
| `tests/messaging/m18_in_flight.rs::only_the_same_target_mode_and_text_is_in_flight` | kept | itself | a change that breaks: other text, mode or target never refused as in-flight |
| `tests/messaging/m18_in_flight.rs::scan_failure_after_claim_never_dispatches` | kept | itself | a change that breaks: failed post-claim scan returns store error, no call |
| `tests/messaging/m18_in_flight.rs::the_cli_refuses_with_exit_9_and_names_the_send_in_flight` | kept | itself | a change that breaks: exit 9; JSON in_flight true; text says "still in progress" |
| `tests/messaging/m18_in_flight.rs::the_same_op_id_again_is_a_replay_not_a_duplicate` | kept | itself | a change that breaks: same op id while claimed returns in_progress, no call |
| `tests/messaging/structure.rs::every_serialized_label_is_in_the_schema` | kept | itself | a change that breaks: every serialized core label is in the schema enums; stays: it reads the schema with the shared checker (`tests/support/schema.rs`) or `cargo metadata` across crates |
| `tests/messaging/structure.rs::no_temp_path_is_shared_between_test_runs` | kept | itself | a change that breaks: test files use the temp dir only in run_root, with pid+nanos naming; stays: it reads the schema with the shared checker (`tests/support/schema.rs`) or `cargo metadata` across crates |
| `tests/messaging/structure.rs::the_core_does_no_io` | moved | `crates/core/tests/send_effects.rs::the_core_does_no_io` | a change that breaks: core/src spells no fs, io, net, process, env, clock or print |
| `tests/messaging/structure.rs::the_guard_methods_have_no_default` | deleted | `tests/messaging/m18_in_flight.rs::a_new_op_id_is_refused_while_the_same_send_is_claimed_or_dispatching` (the cut test was a source grep; a store that falls back to nothing in flight fails the keeper) |  |
| `tests/messaging/structure.rs::the_messaging_schema_uses_only_checked_keywords` | kept | itself | a change that breaks: messaging schema lints clean; request accepts valid, refuses mode auto; stays: it reads the schema with the shared checker (`tests/support/schema.rs`) or `cargo metadata` across crates |
| `tests/messaging/structure.rs::the_preview_and_lookup_shapes_are_in_the_schema` | kept | itself | a change that breaks: preview/lookup defs, consts, all preview statuses in enum; recorded/dispatched lookups refused; stays: it reads the schema with the shared checker (`tests/support/schema.rs`) or `cargo metadata` across crates |
| `tests/messaging/structure.rs::the_request_no_longer_says_the_route_body_carries_the_target` | deleted | `tests/web-api/w4_bounds.rs::a_body_that_breaks_the_rules_is_refused_with_no_call` (the behaviour: a body with a `target` key is refused; the cut test pinned the schema's wording) |  |
| `tests/messaging/structure.rs::the_schema_checker_enforces_unique_items` | kept | itself | a change that breaks: shared schema checker rejects duplicate array items; stays: it reads the schema with the shared checker (`tests/support/schema.rs`) or `cargo metadata` across crates |
| `tests/messaging/structure.rs::the_store_depends_only_inward` | kept | itself | a change that breaks: store reaches core only; core/adapter never reach store; cli reaches store; deps recorded; stays: it reads the schema with the shared checker (`tests/support/schema.rs`) or `cargo metadata` across crates |
| `tests/support/forks.rs::a_lock_stays_listed_while_a_childs_copy_holds_it` | kept | itself | a fork-wait helper that reports a lock gone while a child's copy still holds it; shared support, outside `tests/messaging/` |
| `tests/support/schema.rs::tests::shared_text_keywords_are_linted_and_enforced` | kept | itself | a schema checker that ignores `pattern` or `maxUtf8Bytes` on a shared text definition; shared support, outside `tests/messaging/` |

## Where the kept tests live

- **Moved (8):** the six store-only cases of M10 to
  `crates/store/tests/state_dir.rs` (target `openwiz-store:state_dir`), and
  M5's core effects rule and the core's no-I/O rule to
  `crates/core/tests/send_effects.rs` (target `openwiz-core:send_effects`).
  Both files pass the P8(a) and M12 allowlist guards. They need no new
  dependency.
- **Stay in `tests/messaging/` (163; with the two shared-support tests,
  the target runs 165):** every other kept
  test crosses crates. It sends or reads through the core, the CloudRoom
  adapter and the store, runs the fake `room-cli`, the CLI or the release
  `openwiz`, or reads a contract with the shared schema checker. The
  single-crate ones that stay, each for one reason:
  - `m12_allowlist.rs` (8): M12 is the protected allowlist guard, edited by
    no group.
  - `structure.rs`: the schema tests use `tests/support/schema.rs` and
    `serde_json`, which the core lacks (a new dev-dependency is ask-first);
    `the_store_depends_only_inward` reads `cargo metadata` across crates;
    `no_temp_path_is_shared_between_test_runs` checks this folder's own
    files.
  - `m01::invalid_text_is_refused_with_no_call`, `m03::the_cli_has_no_other_mode`,
    `m14`'s help and parser tests: they run through `SendFake` and
    `support.rs`, the folder's shared fake and fixtures.
