# TV3 ledger: the 0.0.1 proofs P1 to P12 (#805)

One row for every test in the `proof` target at the pull request's base
(`f95a553`), in the form of `tools/test-value/README.md`: its 122 test
functions in `tests/proof/`. The target reports 125 at the base and 93 at
the head: the other 3 are compiled in from shared `tests/support/` files
(`real_time.rs`'s two, `schema.rs`'s one), which are the support group's
(TV9, #811) and unchanged here.

| Outcome | Tests |
| --- | ---: |
| kept | 89 |
| moved to `crates/core/tests/inventory.rs` | 12 |
| merged | 4 (into 1) |
| deleted | 17 |

## Keepers are checked

For every deleted test, `keepers.log` plants the bug it guarded in the
product (or `ci/rust-tests.sh`), runs the deleted test at the base and its
keeper at the head, and restores the file: all 18 planted bugs fail both,
each at an assertion, none at a compile error. The four merged tests'
assertions are unchanged inside their keeper.

## Where tests live

The 12 moved tests run `openwiz_core::ops::list` over the scripted source
alone, so they now live in `openwiz-core`'s own `tests/` folder; the
scripted source moved with them to `crates/core/tests/support/scripted.rs`,
which `tests/proof/support.rs` includes, so there is one copy. Every test
kept in `tests/proof` stays because it crosses crates: it runs the tests
package's fake `room-cli` binary through `openwiz-adapter-cloudroom`, or
`openwiz_cli::run`, or both. The exceptions carry their own reason in the
Catches cell: `p07::every_field_is_capped` (core only, but it checks the JSON
and `openwiz-core` has no `serde_json`; adding one asks first), P8(a) (the
protected allowlist guard, reading every crate's sources) and
`ci_rust_tests` (a CI script, no crate).

## The ledger

| Test | Outcome | Keeper | Catches |
| --- | --- | --- | --- |
| `tests/proof/p01_coverage.rs::every_listed_session_appears_exactly_once` | deleted | `tests/proof/p01_coverage.rs::duplicate_session_statuses_are_honest_in_the_fixture_cli` | |
| `tests/proof/p01_coverage.rs::counts_reconcile_for_the_default_list` | deleted | `tests/proof/p01_coverage.rs::duplicate_session_statuses_are_honest_in_the_fixture_cli` | |
| `tests/proof/p01_coverage.rs::counts_reconcile_with_hidden_and_archived_included` | kept | itself | counts that drop or miscount hidden and archived rows once `-a --hidden` asks for them |
| `tests/proof/p01_coverage.rs::unreadable_rows_are_counted_not_dropped` | kept | itself | a row `room-cli` lists without an id that vanishes from the counts, or has no gap |
| `tests/proof/p01_coverage.rs::a_session_listed_twice_appears_once_with_a_gap` | moved | `crates/core/tests/inventory.rs::a_session_listed_twice_appears_once_with_a_gap` | a session listed twice that is shown twice, or once with no gap |
| `tests/proof/p01_coverage.rs::duplicate_session_statuses_are_honest_in_the_fixture_cli` | kept | itself | duplicate `thread list` rows that are shown twice, miscounted, or whose conflicting statuses become one known status, through `ls --json` |
| `tests/proof/p01_coverage.rs::conflicting_unknown_session_statuses_stay_unknown_in_either_order` | moved | `crates/core/tests/inventory.rs::conflicting_unknown_session_statuses_stay_unknown_in_either_order` | a known status chosen from conflicting known and unknown ones, depending on row order |
| `tests/proof/p01_coverage.rs::conflicting_project_names_are_unknown_with_partial_coverage_in_either_order` | moved | `crates/core/tests/inventory.rs::conflicting_project_names_are_unknown_with_partial_coverage_in_either_order` | one of two conflicting project names shown as known, or a result that depends on project row order |
| `tests/proof/p01_coverage.rs::two_conflicting_project_ids_merge_into_one_gap_in_id_order` | moved | `crates/core/tests/inventory.rs::two_conflicting_project_ids_merge_into_one_gap_in_id_order` | one gap per conflicting project, or subjects in row order instead of id order |
| `tests/proof/p01_coverage.rs::identical_project_name_facts_keep_their_single_row_behavior` | moved | `crates/core/tests/inventory.rs::identical_project_name_facts_keep_their_single_row_behavior` | identical repeated project rows treated as a conflict |
| `tests/proof/p02_freshness.rs::snapshot_time_and_source_version_are_reported` | kept | itself | an envelope without the snapshot time, the source name, its version or whether that version is tested |
| `tests/proof/p02_freshness.rs::each_row_has_its_age_from_the_snapshot` | kept | itself | a row whose update time or age is not snapshot minus the reported time |
| `tests/proof/p02_freshness.rs::text_header_shows_the_source_version_and_snapshot_time` | deleted | `tests/proof/p10_json_matches_text.rs::ls_text_matches_the_json_envelope_and_rows`; `tests/proof/p10_json_matches_text.rs::show_text_matches_the_json_envelope` for `show` | |
| `tests/proof/p02_freshness.rs::text_rows_show_their_age` | deleted | `tests/proof/p10_json_matches_text.rs::ls_text_matches_the_json_envelope_and_rows` (printed age); `tests/proof/p02_freshness.rs::each_row_has_its_age_from_the_snapshot` (the age itself) | |
| `tests/proof/p02_freshness.rs::an_out_of_range_update_time_gives_an_unknown_age` | kept | itself | an update time far from the snapshot that panics or wraps instead of giving an unknown age |
| `tests/proof/p02_freshness.rs::visibility_is_known_only_for_hidden_and_visible_at_adapter_reads` | kept | itself | a visibility other than `hidden` or `visible`, or a missing one, read as a known value by `thread list` or `thread show` |
| `tests/proof/p03_unknowns.rs::missing_status_is_unknown_with_a_reason` | deleted | `tests/proof/p03_unknowns.rs::unknowns_print_as_unknown_with_their_reason_in_ls` (same row and scenario; it requires the JSON status unknown) | |
| `tests/proof/p03_unknowns.rs::missing_model_is_unknown_with_a_reason` | kept | itself | a missing model or effort invented as known, or a known effort lost beside a missing model |
| `tests/proof/p03_unknowns.rs::missing_parent_is_unknown_not_top_level` | kept | itself | a missing parent shown as top level, or a null parent shown as unknown |
| `tests/proof/p03_unknowns.rs::missing_freshness_is_unknown_with_a_reason` | deleted | `tests/proof/p03_unknowns.rs::unknowns_print_as_unknown_with_their_reason_in_ls` (same row and scenario; it requires the JSON age unknown) | |
| `tests/proof/p03_unknowns.rs::unknowns_print_as_unknown_with_their_reason_in_ls` | kept | itself | an unknown status, age or model printed in `ls -l` without `unknown (reason)` |
| `tests/proof/p03_unknowns.rs::unknowns_print_as_unknown_with_their_reason_in_show` | kept | itself | an unknown parent or model printed in `show` without `unknown (reason)` |
| `tests/proof/p04_partial_failures.rs::thread_list_error_is_an_explicit_error` | kept | itself | a failed `thread list` that is not an explicit list error with its exit code and safe line |
| `tests/proof/p04_partial_failures.rs::thread_list_timeout_is_explicit_bounded_and_cleaned_up` | kept | itself | a hung `thread list` that is not stopped at the budget, not reported as a timeout, or left running |
| `tests/proof/p04_partial_failures.rs::malformed_thread_list_is_an_explicit_error` | kept | itself | non-JSON or truncated `thread list` output that is not an explicit malformed error |
| `tests/proof/p04_partial_failures.rs::project_list_failure_gives_a_partial_ungrouped_result` | kept | itself | a failed project list that drops sessions or still groups them |
| `tests/proof/p04_partial_failures.rs::conflicting_machine_names_are_unknown_in_the_fixture_cli_in_either_order` | kept | itself | one of two conflicting machine names shown as known, depending on row order |
| `tests/proof/p04_partial_failures.rs::consistent_machine_names_resolve_normally_in_the_fixture_cli` | kept | itself | repeated identical machine rows treated as a conflict, or a long name not cut at 200 characters |
| `tests/proof/p04_partial_failures.rs::detail_read_error_gives_a_partial_result_with_unknown_configuration` | kept | itself | a failed `thread show` that fails the whole `ls -l` or invents a configuration |
| `tests/proof/p04_partial_failures.rs::detail_read_timeout_gives_a_partial_result_within_the_budget` | kept | itself | a hung `thread show` that overruns the budget, gives no gap, or is left running |
| `tests/proof/p04_partial_failures.rs::wrong_types_become_unknowns_not_invented_values` | kept | itself | a mistyped field turned into an invented value instead of an unknown |
| `tests/proof/p04_partial_failures.rs::show_of_a_nonexistent_session_is_not_found` | kept | itself | a missing session not reported as not found (exit 3), printed as if it existed, or read further |
| `tests/proof/p04_partial_failures.rs::show_of_an_unsafe_id_is_refused_without_running_room_cli` | kept | itself | an id like `--work-status` treated as not found, or passed to `room-cli`, at the core |
| `tests/proof/p04_partial_failures.rs::final_output_read_error_gives_a_partial_show` | kept | itself | a failed `thread output` that fails the whole `show` or invents an output |
| `tests/proof/p04_partial_failures.rs::final_output_read_timeout_gives_a_partial_show_within_the_budget` | kept | itself | a hung `thread output` that overruns the budget, gives no gap, or is left running |
| `tests/proof/p04_partial_failures.rs::only_a_first_pull_request_run_to_main_moves_the_15_second_proof` | kept | itself | the 15-second read proof skipped on runs other than a first pull request run to `main` |
| `tests/proof/p04_partial_failures.rs::a_read_that_never_answers_is_stopped_after_15_seconds_and_not_retried` | kept | itself | a read that never answers retried, or not stopped at the 15-second timeout |
| `tests/proof/p04_partial_failures.rs::exit_codes_are_documented_and_errors_go_to_stderr` | kept | itself | a wrong exit code, an error on stdout, or a usage error that reads `room-cli` |
| `tests/proof/p04_partial_failures.rs::help_documents_the_commands_the_order_and_the_exit_codes` | kept | itself | `--help` that drops a command, the sort key or an exit code, or reads `room-cli` |
| `tests/proof/p04_partial_failures.rs::switches_take_no_value` | kept | itself | `--hidden=no` and the like accepted as the switch |
| `tests/proof/p04_partial_failures.rs::an_oversized_response_fails_as_malformed` | kept | itself | a response over 32 MiB read whole, or not failed as malformed |
| `tests/proof/p04_partial_failures.rs::over_cap_send_and_new_receipts_stay_uncertain` | kept | itself | an over-cap `tell` or `spawn` receipt reported as a confirmed refusal instead of uncertain |
| `tests/proof/p04b_source_diagnostics.rs::thread_list_diagnostics_never_reach_the_output` | kept | itself | `room-cli`'s stderr or stray stdout from a failed `thread list` shown in the core result, the CLI text or JSON, or the release binary's output |
| `tests/proof/p04b_source_diagnostics.rs::project_list_diagnostics_never_reach_the_output` | kept | itself | `room-cli`'s stderr or stray stdout from a failed `project list` shown in the core result, the CLI text or JSON, or the release binary's output |
| `tests/proof/p04b_source_diagnostics.rs::machine_list_diagnostics_never_reach_the_output` | kept | itself | `room-cli`'s stderr or stray stdout from a failed `machine list` shown in the core result, the CLI text or JSON, or the release binary's output |
| `tests/proof/p04b_source_diagnostics.rs::thread_show_diagnostics_never_reach_the_output` | kept | itself | `room-cli`'s stderr or stray stdout from a failed `thread show` shown in the core result, the CLI text or JSON, or the release binary's output |
| `tests/proof/p04b_source_diagnostics.rs::thread_output_diagnostics_never_reach_the_output` | kept | itself | `room-cli`'s stderr or stray stdout from a failed `thread output` shown in the core result, the CLI text or JSON, or the release binary's output |
| `tests/proof/p04b_source_diagnostics.rs::version_read_diagnostics_never_reach_the_output` | kept | itself | a failed `--version` read whose text, even a safe-grammar line, is shown |
| `tests/proof/p04b_source_diagnostics.rs::unexpected_stdout_never_reaches_the_output` | kept | itself | text `room-cli` prints where JSON, a version or a recorded value was expected shown in any output |
| `tests/proof/p04b_source_diagnostics.rs::a_not_found_line_with_an_unsafe_suffix_is_still_not_found` | kept | itself | a not-found line with an unsafe suffix no longer exiting 3, or its suffix shown |
| `tests/proof/p04b_source_diagnostics.rs::tell_keeps_its_exact_documented_rejections` | kept | itself | a `thread tell` rejection with an unsafe suffix treated as a definite refusal or shown |
| `tests/proof/p04b_source_diagnostics.rs::the_version_grammar_is_n_n_n_or_v_n` | kept | itself | a version outside `N.N.N` or `v<N>` echoed, or a valid one withheld |
| `tests/proof/p04b_source_diagnostics.rs::ta3_http_word_boundaries_return_typed_private_read_failures` | kept | itself | an HTTP status word matched inside another word, or a private read failure left untyped |
| `tests/proof/p05_paging_and_budget.rs::ordering_is_stable_whatever_order_the_source_returns` | deleted | `tests/proof/p05_paging_and_budget.rs::the_order_is_most_recently_updated_first_then_by_id` (two source orders, one exact order) | |
| `tests/proof/p05_paging_and_budget.rs::limit_and_offset_select_the_page` | moved | `crates/core/tests/inventory.rs::limit_and_offset_select_the_page` | a page past the end that is not empty, or counts that misstate offset, limit or shown |
| `tests/proof/p05_paging_and_budget.rs::pages_cover_every_session_once` | deleted | `tests/proof/p05_paging_and_budget.rs::the_cli_passes_limit_and_offset` (the exact ids of a page) | |
| `tests/proof/p05_paging_and_budget.rs::short_listing_makes_no_detail_reads` | moved | `crates/core/tests/inventory.rs::short_listing_makes_no_detail_reads` | `ls` that reads session details |
| `tests/proof/p05_paging_and_budget.rs::long_listing_enriches_only_the_requested_page` | kept | itself | `ls -l` that reads details, or runs `thread show`, for sessions off the page |
| `tests/proof/p05_paging_and_budget.rs::at_most_four_detail_reads_run_at_once` | moved | `crates/core/tests/inventory.rs::at_most_four_detail_reads_run_at_once` | more than four detail reads at once |
| `tests/proof/p05_paging_and_budget.rs::the_budget_bounds_the_whole_run` | moved | `crates/core/tests/inventory.rs::the_budget_bounds_the_whole_run` | a run that overruns its budget, drops unread rows, or reports no budget gap |
| `tests/proof/p05_paging_and_budget.rs::the_default_budget_is_thirty_seconds` | moved | `crates/core/tests/inventory.rs::the_default_budget_is_thirty_seconds` | reads given a deadline other than the run's 30-second budget |
| `tests/proof/p05_paging_and_budget.rs::the_cli_passes_limit_and_offset` | kept | itself | `--limit` and `--offset` that select the wrong ids, or are not passed to the core |
| `tests/proof/p05_paging_and_budget.rs::the_default_page_is_the_first_100_in_stable_order` | kept | itself | a default page that is not the first 100 sessions in the stable order |
| `tests/proof/p05_paging_and_budget.rs::the_order_is_most_recently_updated_first_then_by_id` | kept | itself | an order other than newest first, ties by id, unknown times last, or one that depends on the source order |
| `tests/proof/p06_verified_grouping.rs::sessions_are_grouped_by_a_project_seen_in_the_same_run` | kept | itself | a session not grouped under its listed project |
| `tests/proof/p06_verified_grouping.rs::an_unseen_project_id_is_ungrouped_with_a_reason` | kept | itself | a session grouped by a project id the project list does not have |
| `tests/proof/p06_verified_grouping.rs::shared_project_names_never_merge_groups` | kept | itself | two projects with one name merged into one group |
| `tests/proof/p06_verified_grouping.rs::a_missing_or_mistyped_project_id_is_ungrouped_with_a_reason` | kept | itself | a missing or mistyped project id grouped anyway, or ungrouped with no reason |
| `tests/proof/p06_verified_grouping.rs::text_shows_ungrouped_sessions_with_their_reason` | deleted | `tests/proof/p10_json_matches_text.rs::ls_text_matches_the_json_envelope_and_rows` (each ungrouped row carries its reason) | |
| `tests/proof/p06_verified_grouping.rs::grouping_uses_only_the_current_runs_project_list` | kept | itself | a grouping, or its absence, kept from an earlier run of the same source |
| `tests/proof/p06_verified_grouping.rs::shared_project_names_are_shown_with_the_last_six_characters_of_the_id` | deleted | `tests/proof/p10_json_matches_text.rs::ls_text_matches_the_json_envelope_and_rows` (each row's header, with `~<last six>` for a shared name, against the JSON name) | |
| `tests/proof/p06_verified_grouping.rs::text_groups_follow_the_project_id_not_the_printed_name` | kept | itself | text groups keyed by the printed name, so `_ungrouped` or look-alike names share a header |
| `tests/proof/p06_verified_grouping.rs::group_headers_stay_distinct_when_a_name_copies_a_widened_header` | kept | itself | a project name equal to another's widened header that prints the same header |
| `tests/proof/p07_bounded_output.rs::purpose_is_cut_to_120_characters` | kept | itself | a purpose not cut at 120 characters, or a short one marked cut |
| `tests/proof/p07_bounded_output.rs::a_session_without_purpose_reads_no_recap_yet` | kept | itself | a session without a purpose not shown as `no recap yet`, or a recap without its label |
| `tests/proof/p07_bounded_output.rs::final_output_is_cut_to_4_kib_on_a_character_boundary` | deleted | `tests/proof/p07_bounded_output.rs::printed_final_output_and_purpose_show_their_cut` (the first 4095 bytes then the cut marker, and the 4095/4096/4097-byte cases) | |
| `tests/proof/p07_bounded_output.rs::a_session_without_final_output_reads_no_final_output_yet` | kept | itself | a session without output not shown as `no final output yet` |
| `tests/proof/p07_bounded_output.rs::show_reads_final_output_never_a_log_tail` | kept | itself | `show` that reads a log instead of `thread output` |
| `tests/proof/p07_bounded_output.rs::rows_are_capped` | moved | `crates/core/tests/inventory.rs::rows_are_capped` | a limit over the row cap that lists more than the cap |
| `tests/proof/p07_bounded_output.rs::printed_final_output_and_purpose_show_their_cut` | kept | itself | a cut final output or purpose printed without the cut marker, past its cap, or an exact 4096 bytes marked cut |
| `tests/proof/p07_bounded_output.rs::every_field_is_capped` | kept | itself | a string field in the result past 200 characters, or a bounded text cut without `truncated`; stays: it checks the JSON, and `openwiz-core` has no `serde_json` |
| `tests/proof/p07_bounded_output.rs::printed_output_shows_every_cut` | kept | itself | a cut value printed without its marker, or text past a cap printed, in `ls -l`, `show`, `--json` or stderr |
| `tests/proof/p07_bounded_output.rs::the_text_never_prints_terminal_control_or_bidi_characters` | kept | itself | escape, bidi or zero-width characters printed to the terminal |
| `tests/proof/p07_bounded_output.rs::the_printed_final_output_stays_within_4_kib` | kept | itself | replacing unsafe characters that makes the printed output longer than 4 KiB |
| `tests/proof/p08a_allowlist_static.rs::allowlist_argv_contracts_preserve_original_cases` | kept | itself | an invocation the allowlist can build that is not on `ALLOWED`, passes a forbidden word, adds hidden or archived flags unasked, or lets an id become a flag; stays: P8(a) is the protected allowlist guard |
| `tests/proof/p08a_allowlist_static.rs::allowlist_source_contracts_preserve_original_cases` | kept | itself | a process started outside the approved runners, or a forbidden `room-cli` word in any product source; stays: it reads every crate's sources |
| `tests/proof/p09_reported_configuration.rs::model_and_effort_come_from_thread_show_as_reported_configuration` | kept | itself | model and effort not read from `thread show` |
| `tests/proof/p09_reported_configuration.rs::json_keeps_model_and_effort_under_reported_configuration` | deleted | `tests/proof/p10_json_matches_text.rs::json_output_matches_the_schema` (the schema allows no other session key and requires `reported_configuration`) | |
| `tests/proof/p09_reported_configuration.rs::text_labels_model_and_effort_as_reported_configuration` | kept | itself | a model or effort printed without the `reported configuration` label, or called the serving model |
| `tests/proof/p10_json_matches_text.rs::inventory_output_write_failure_is_not_success` | merged | `tests/proof/p10_json_matches_text.rs::inventory_output_write_and_flush_failures_are_not_success` | (as its keeper) |
| `tests/proof/p10_json_matches_text.rs::inventory_output_partial_write_failure_is_not_success` | merged | `tests/proof/p10_json_matches_text.rs::inventory_output_write_and_flush_failures_are_not_success` | (as its keeper) |
| `tests/proof/p10_json_matches_text.rs::inventory_output_flush_failure_is_not_success` | merged | `tests/proof/p10_json_matches_text.rs::inventory_output_write_and_flush_failures_are_not_success` | (as its keeper) |
| `tests/proof/p10_json_matches_text.rs::inventory_output_normal_writer_prints_results` | merged | `tests/proof/p10_json_matches_text.rs::inventory_output_write_and_flush_failures_are_not_success` | (as its keeper) |
| `tests/proof/p10_json_matches_text.rs::ls_json_and_text_list_the_same_sessions` | deleted | `tests/proof/p10_json_matches_text.rs::ls_text_matches_the_json_envelope_and_rows` (the same row ids in text and JSON) | |
| `tests/proof/p10_json_matches_text.rs::ls_long_rows_say_the_same_in_json_and_text` | kept | itself | an `ls -l` row whose status, model, effort or recap differs from the JSON |
| `tests/proof/p10_json_matches_text.rs::show_says_the_same_in_json_and_text` | kept | itself | `show` text whose status, title, configuration, final output or reported error differs from the JSON |
| `tests/proof/p10_json_matches_text.rs::json_output_matches_the_schema` | kept | itself | `--json` output outside `openwiz.inventory.v1` |
| `tests/proof/p10_json_matches_text.rs::ls_text_matches_the_json_envelope_and_rows` | kept | itself | `ls` text whose header, counts, gaps, rows, ages, locations, parents, reasons or group headers differ from the JSON |
| `tests/proof/p10_json_matches_text.rs::show_text_matches_the_json_envelope` | kept | itself | `show` text whose header, gaps, age, location, parent, group or configuration differ from the JSON |
| `tests/proof/p10_json_matches_text.rs::the_release_build_prints_schema_valid_json` | kept | itself | a release `openwiz` that prints invalid JSON, uses a fixed clock, or gates an untested version |
| `tests/proof/p11_visibility.rs::hidden_and_archived_sessions_are_excluded_by_default` | kept | itself | plain `ls` that shows hidden or archived sessions, or asks `room-cli` for them |
| `tests/proof/p11_visibility.rs::hidden_sessions_appear_only_with_hidden` | kept | itself | `--hidden` that does not show hidden sessions, also shows archived ones, or passes the wrong flag |
| `tests/proof/p11_visibility.rs::archived_sessions_appear_only_with_a` | kept | itself | `-a` that does not show archived sessions, also shows hidden ones, or passes the wrong flag |
| `tests/proof/p11_visibility.rs::hidden_or_archived_rows_are_excluded_even_if_the_source_returns_them` | moved | `crates/core/tests/inventory.rs::hidden_or_archived_rows_are_excluded_even_if_the_source_returns_them` | hidden or archived rows the source returns anyway shown, or not counted as excluded |
| `tests/proof/p11_visibility.rs::a_row_both_hidden_and_archived_requires_both_flags` | kept | itself | a hidden and archived row shown with only one of `--hidden` and `-a` |
| `tests/proof/p12_drift.rs::an_untested_version_is_reported_and_never_stops` | kept | itself | an untested version that stops a read, or is not marked untested |
| `tests/proof/p12_drift.rs::an_unrecognised_version_is_unknown_and_never_stops` | kept | itself | unrecognised version text echoed, or stopping the run |
| `tests/proof/p12_drift.rs::a_failed_version_read_never_echoes_its_error_text` | kept | itself | a failed version read whose error text is shown in text, JSON or stderr |
| `tests/proof/p12_drift.rs::missing_fields_are_reported_by_session_and_field` | kept | itself | a missing field with no gap naming its session and field |
| `tests/proof/p12_drift.rs::mistyped_fields_are_reported_by_session_and_field` | kept | itself | a mistyped field with no gap naming its session and field |
| `tests/proof/p12_drift.rs::unknown_extra_fields_are_tolerated` | kept | itself | extra fields that change the inventory or make it partial |
| `tests/proof/p12_drift.rs::contradictory_status_keys_never_become_complete_known_facts` | kept | itself | a repeated JSON key in `thread list` read as one value instead of refusing the read |
| `tests/proof/p12_drift.rs::duplicate_keys_in_other_reads_leave_unaffected_inventory_available` | kept | itself | a repeated key in another read that fails the whole inventory or leaks the key |
| `tests/proof/p12_drift.rs::absent_optional_fields_keep_inventory_defaults_and_host_fallback` | kept | itself | an absent purpose or execution target that makes the list partial or loses the host fallback |
| `tests/proof/p12_drift.rs::missing_detail_fields_are_reported_by_session_and_field` | kept | itself | a missing `thread show` field with no gap naming its session and field |
| `tests/proof/p12_drift.rs::unrecognised_values_are_reported_as_drift` | kept | itself | a new `visibility` or `executionTarget` value read as known, with no drift gap |
| `tests/proof/p12_drift.rs::nullable_parent_preserves_primitive_type_drift_at_adapter_reads` | kept | itself | a mistyped parent read as top level instead of unknown with a drift gap |
| `tests/proof/ci_rust_tests.rs::the_release_fixture_is_built_once_before_the_tests` | deleted | `.github/actions/docs-only/test_rust_runner.sh::"one command, 8 test threads"` with its `prebuilt` check (the exact prebuild argv, first and once) | |
| `tests/proof/ci_rust_tests.rs::a_failed_release_build_starts_no_test_on_either_path` | deleted | `.github/actions/docs-only/test_rust_runner.sh::"$mode CPUs, the release fixture fails"` (2 and 8 CPUs: exit 7, no test, no other suite) | |
| `tests/proof/ci_rust_tests.rs::the_one_command_path_runs_eight_test_threads` | deleted | `.github/actions/docs-only/test_rust_runner.sh::"one command, 8 test threads"` | |
| `tests/proof/ci_rust_tests.rs::a_pull_request_to_main_keeps_the_main_only_skips_with_eight_threads` | kept | itself | a pull request to `main` whose one-command run drops a main-only skip; stays: it tests a CI script, no crate |
| `tests/proof/ci_rust_tests.rs::a_failed_test_run_fails_the_step` | deleted | `.github/actions/docs-only/test_rust_runner.sh::"no --alongside, cargo fails"` | |
