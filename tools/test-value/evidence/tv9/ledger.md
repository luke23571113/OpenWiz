# TV9 (#811): the checks, cli-agent and support group's ledger

Every test of this group at the pull request's base, `20a5100`, one row
each, in the form of `tools/test-value/README.md`: the `checks` target's
files except `skills.rs` (TV12, #814), the `cli-agent` target, and the
tests in `tests/support/` (one of them, `cloudroom_process_tests.rs`, runs
as the CloudRoom adapter's unit tests). `tests/new-thread/pattern.rs`'s one
test, compiled into both targets, is TV6's (#808).

- **Rows:** 155: kept 142, deleted 7, merged 2, moved 4.
- **Kept** rows' Catches is the bug the test fails on, read from its
  assertions. A keeper for every deleted or merged row was checked by a
  break: [keepers.txt](keepers.txt). Two deletions have no keeper to break:
  a wording pin and an unreachable case (their rows say why).
- **Moved:** the four tests of `tests/support/forks.rs`, `real_time.rs`
  and `schema.rs` moved to `tests/checks/support_proofs.rs`, unchanged.
  Each support file is compiled into several targets, and each copy ran its
  tests again; now they run once, in the `checks` target CI always runs.
- **`tests/cli-agent/ui.rs`** is unchanged in its assertions: #776 removes
  `openwiz ui` and this file with it, so its five rows stay kept until then.
  Two of its fixture lines now use the shared placement helper (below).

| Test | Outcome | Keeper | Catches |
| --- | --- | --- | --- |
| `tests/checks/ci_selection.rs::ci_selection_schema_is_checkable_and_refuses_malformed_roots` | kept | itself | a CI selection schema that uses a keyword the checker ignores, or accepts a null, array or empty root |
| `tests/checks/ci_selection.rs::ci_selection_folder_holds_its_readme_and_fixtures_only` | kept | itself | a selection fixture added or removed without its README row, or a stray file the readers would skip |
| `tests/checks/ci_selection.rs::ci_selection_every_valid_fixture_passes` | kept | itself | a valid selection record refused, or a reason code, event, action or mode no fixture covers |
| `tests/checks/ci_selection.rs::ci_selection_every_invalid_fixture_is_refused_for_its_reason` | kept | itself | an invalid selection record accepted, or refused for another rule than its name says |
| `tests/checks/ci_selection.rs::ci_selection_contract_tables_match_the_schema` | kept | itself | the selection contract's tables and its schema disagreeing on a code, lane, build or diff state |
| `tests/checks/ci_selection.rs::ci_selection_reads_find_each_merged_pull_requests_plan` | kept | itself | a reader that picks the wrong run or attempt's plan for a merged pull request |
| `tests/checks/cockpit_schema_conformance.rs::cockpit_schema_uses_only_checked_keywords` | kept | itself | a cockpit schema rule the checker ignores, or a dangling `$ref` |
| `tests/checks/cockpit_schema_conformance.rs::cockpit_complete_partial_stale_and_empty_responses_validate` | kept | itself | a cockpit schema tightened so a partial, stale or empty response is refused |
| `tests/checks/cockpit_schema_conformance.rs::cockpit_malformed_responses_fail` | kept | itself | a cockpit schema that accepts a wrong field, a missing or extra key, or a positional array |
| `tests/checks/cockpit_schema_conformance.rs::cockpit_preserves_unknown_project_associations` | kept | itself | an unknown project association refused instead of kept with its gap |
| `tests/checks/cockpit_schema_conformance.rs::cockpit_gap_project_cannot_be_empty` | kept | itself | an empty gap project accepted |
| `tests/checks/cockpit_schema_conformance.rs::cockpit_every_schema_field_has_a_source_row` | kept | itself | a cockpit field added to the schema with no source row in its contract, or a stale row |
| `tests/checks/dependencies.rs::the_core_depends_on_neither_the_adapter_nor_the_cli` | deleted | behaviour gone: a compiler re-check; the adapter and the CLI use the core, so a core dependency on either is a cycle Cargo refuses to resolve (`keepers.txt`, first two checks) |  |
| `tests/checks/dependencies.rs::dependencies_point_inward` | deleted | behaviour gone: a compiler re-check; the CLI uses the adapter and both use the core, so an adapter dependency on the CLI is a cycle Cargo refuses, and a missing inward dependency fails the build (`keepers.txt`) |  |
| `tests/checks/dependencies.rs::the_visual_pair_stays_on_the_visual_side` | kept | itself | `ratatui` or `crossterm` reaching a non-visual crate, or the terminal crate depended on outside the tests |
| `tests/checks/dependencies.rs::serde_and_serde_json_are_the_only_direct_dependencies` | kept | itself | an unapproved direct dependency in any workspace crate |
| `tests/checks/dependencies.rs::dependencies_md_records_every_locked_crate_with_its_checksum` | kept | itself | a locked crate or version missing from `contracts/dependencies.v1.md`, or its checksum changed |
| `tests/checks/dir_modes.rs::no_test_leaves_a_directorys_mode_to_the_umask` | kept | itself | a test that creates a directory with the umask's mode (#170) |
| `tests/checks/dir_modes.rs::the_check_catches_every_planted_form` | kept | itself | a directory-mode scan that misses a planted form, so its clean result proves nothing |
| `tests/checks/evidence_outside_crates.rs::no_product_crate_keeps_an_evidence_folder` | deleted | `tests/checks/evidence_outside_crates.rs::no_product_evidence_is_tracked_for_export` |  |
| `tests/checks/evidence_outside_crates.rs::no_product_evidence_is_tracked_for_export` | kept | itself | build evidence tracked under `crates/` at any depth, which would ship in the public tree |
| `tests/checks/fixture_scan.rs::fixtures_contain_only_synthetic_values` | kept | itself | a private value in any fixture or fake, or either fake's source left out of the scan (now also its merged case) |
| `tests/checks/fixture_scan.rs::release_candidate_examples_have_scoped_synthetic_provenance` | kept | itself | a release-candidate provenance pointer accepted outside its exact folder |
| `tests/checks/fixture_scan.rs::release_candidate_privacy_and_unknown_forms_still_refuse` | kept | itself | a private or unknown value accepted in a release-candidate fixture |
| `tests/checks/fixture_scan.rs::release_candidate_duplicate_keys_cannot_hide_private_values` | kept | itself | a repeated JSON key that hides a private value from the scan |
| `tests/checks/fixture_scan.rs::release_candidate_filename_cannot_select_room_cli_scenario_rules` | kept | itself | a candidate file named `scenario.json` getting the looser scenario rules |
| `tests/checks/fixture_scan.rs::every_scenario_records_its_synthetic_assumptions` | kept | itself | a scenario without its `synthetic_assumptions` (AGENTS.md: label every shape not observed) |
| `tests/checks/fixture_scan.rs::the_scan_catches_planted_private_data` | kept | itself | a scan that misses a planted email, home path, id, URL, UUID or truncated JSON |
| `tests/checks/fixture_scan.rs::the_observed_sent_keys_pass_only_in_send_fixtures` | kept | itself | observed send keys accepted outside `send/` |
| `tests/checks/fixture_scan.rs::the_documented_send_shapes_pass_only_in_send_fixtures` | kept | itself | documented `thread tell` shapes accepted outside `send/` |
| `tests/checks/fixture_scan.rs::the_new_thread_shapes_pass_only_in_new_thread_fixtures` | kept | itself | new-thread shapes accepted outside `new-thread/` |
| `tests/checks/fixture_scan.rs::the_github_shapes_pass_only_in_github_fixtures` | kept | itself | `gh` shapes accepted outside `github/`, or a private `gh` value accepted in it |
| `tests/checks/fixture_scan.rs::a_github_scenario_records_its_name_and_synthetic_assumptions` | kept | itself | a GitHub scenario accepted without its name, description or assumptions |
| `tests/checks/fixture_scan.rs::a_github_scenario_answers_only_calls_the_allowlist_allows` | kept | itself | a GitHub scenario answering a call the allowlist refuses, or a path that escapes its folder |
| `tests/checks/fixture_scan.rs::a_github_scenarios_argv_is_only_text` | kept | itself | a non-text, non-list or missing argv silently dropped instead of refused |
| `tests/checks/fixture_scan.rs::the_fake_gh_is_scanned_for_private_data` | merged | `tests/checks/fixture_scan.rs::fixtures_contain_only_synthetic_values` | (as its keeper) |
| `tests/checks/fixture_scan.rs::no_checks_diagnostic_accepts_only_the_existing_synthetic_branch_form` | kept | itself | a real branch name accepted in the no-checks diagnostic |
| `tests/checks/fixture_scan.rs::observed_queued_identifiers_and_keys_are_scoped` | kept | itself | queued ids or send-only keys accepted outside `send/` |
| `tests/checks/limits.rs::the_approved_limits_are_in_the_core` | deleted | `tests/proof/p07_bounded_output.rs::purpose_is_cut_to_120_characters` (120), `tests/proof/p07_bounded_output.rs::printed_final_output_and_purpose_show_their_cut` (4096), `crates/core/tests/inventory.rs::at_most_four_detail_reads_run_at_once` (4), `crates/core/tests/inventory.rs::the_default_budget_is_thirty_seconds` (30 s), `tests/proof/p05_paging_and_budget.rs::the_default_page_is_the_first_100_in_stable_order` (100) |  |
| `tests/checks/loops_schema.rs::loops_schema_definitions_and_records` | kept | itself | the loops schema accepting a bad definition, wake or run result, or refusing a good one |
| `tests/checks/loops_schema.rs::loops_schema_reuses_new_thread_rules` | kept | itself | the loops schema's op id, setting, project or brief rules drifting from new-thread.v1's |
| `tests/checks/loops_schema.rs::loops_schema_example_is_synthetic_and_valid` | kept | itself | `loops/example.json` invalid, enabled, or not in shadow mode |
| `tests/checks/loops_schema.rs::loops_schema_numbers_follow_mathematical_integer_semantics` | kept | itself | the loops schema refusing `5000.0` or `5e3`, or accepting `0.5` or `-1.0`, as an integer |
| `tests/checks/pending.rs::the_pending_list_matches_the_future_behaviour_tests_exactly` | kept | itself | a pending proof missing from `tests/pending-ticket-2.txt`, or a P8(a) test ignored |
| `tests/checks/pending.rs::nothing_else_is_ignored` | kept | itself | an `#[ignore]` anywhere but a listed pending proof case |
| `tests/checks/plan_decisions_schema_conformance.rs::plan_schema_uses_only_checked_keywords` | kept | itself | a plan schema rule the checker ignores, or a malformed root accepted |
| `tests/checks/plan_decisions_schema_conformance.rs::decisions_schema_uses_only_checked_keywords` | kept | itself | a decisions schema rule the checker ignores, or a malformed root accepted |
| `tests/checks/plan_decisions_schema_conformance.rs::plan_every_schema_field_has_a_source_row` | kept | itself | a plan field with no source row in `contracts/plan.v1.md`, or a stale row |
| `tests/checks/plan_decisions_schema_conformance.rs::decisions_every_schema_field_has_a_source_row` | kept | itself | a decisions field with no source row in `contracts/decisions.v1.md`, or a stale row |
| `tests/checks/plan_decisions_schema_conformance.rs::plan_valid_partial_stale_and_empty_fixtures` | kept | itself | a plan schema that refuses a valid, partial, stale, empty or building plan |
| `tests/checks/plan_decisions_schema_conformance.rs::decisions_all_variants_lifecycle_risks_and_empty_responses` | kept | itself | a decisions schema that refuses a valid kind, status or risk |
| `tests/checks/plan_decisions_schema_conformance.rs::plan_and_decisions_malformed_literals_fail` | kept | itself | a plan or decisions schema that accepts a planted bad value |
| `tests/checks/plan_decisions_schema_conformance.rs::decisions_three_questions_and_ten_summary_lines_are_schema_bounds` | kept | itself | a fourth question or an eleventh summary line accepted |
| `tests/checks/plan_decisions_schema_conformance.rs::plan_approval_fingerprint_names_the_existing_revision_script` | kept | itself | the contract naming a revision script that does not exist |
| `tests/checks/plan_decisions_schema_conformance.rs::escaped_decision_markers_validate_and_have_a_discovery_rule` | kept | itself | escaped decision markers refused, or the contract losing its one discovery rule |
| `tests/checks/plan_decisions_schema_conformance.rs::every_fixture_object_refuses_missing_extra_and_positional_keys` | kept | itself | any nested plan or decisions object accepting a missing, extra or positional key |
| `tests/checks/plan_decisions_schema_conformance.rs::plan_and_decisions_have_only_their_two_new_route_rows` | kept | itself | a plan or decisions route missing from, or doubled in, `contracts/web-api.v1.md` |
| `tests/checks/plan_decisions_schema_conformance.rs::plan_approval_summary_names_its_saved_source` | deleted | behaviour gone: none to catch: it pinned five phrases of `skills/plan-graph/SKILL.md`'s prose, which no program reads; the spec deletes wording pins |  |
| `tests/checks/plan_decisions_schema_conformance.rs::plan_approval_command_runs_the_revision_v2_fixture_proof` | kept | itself | the skill's documented revision command producing other bytes or another fingerprint |
| `tests/checks/plan_decisions_schema_conformance.rs::skill_plan_record_rejects_rehashed_revision_drift` | kept | itself | the record check accepting a changed revision rehashed to match (its guard's own planted breaks) |
| `tests/checks/plan_decisions_schema_conformance.rs::skill_plan_record_accepts_matching_rows_and_derives_sorted_graph` | kept | itself | the record check refusing a matching record, or accepting an unsorted or empty graph |
| `tests/checks/plan_decisions_schema_conformance.rs::skills_decision_record_outputs_validate_and_bind_the_proposal` | kept | itself | a skill's example decision record invalid, or its fingerprint not the proposal's hash |
| `tests/checks/plan_links.rs::plan_links_schema_is_checkable_and_refuses_malformed_roots` | kept | itself | a plan-links schema rule the checker ignores, or a malformed root accepted |
| `tests/checks/plan_links.rs::plan_links_every_fixture_has_its_expectations_and_validates` | kept | itself | a plan-links fixture case missing a file, or its graph, report, board or history invalid |
| `tests/checks/plan_links.rs::plan_links_planted_invalid_fixtures_are_refused` | kept | itself | the plan-links schema accepting a planted bad change |
| `tests/checks/plan_links.rs::plan_links_reports_agree_with_their_graph_reads` | kept | itself | a hand-written report that its graph, under the contract's rules, does not give |
| `tests/checks/plan_links.rs::plan_links_board_numbers_follow_the_definitions` | kept | itself | a board number that does not follow from its graph by the definitions |
| `tests/checks/plan_links.rs::plan_links_history_days_and_daily_rows` | kept | itself | a history row on the wrong day, or a daily row that is not the day's last sample |
| `tests/checks/plan_links.rs::plan_links_contract_carries_this_specs_lines_and_the_baseline` | kept | itself | the plan-links contract losing the spec's reason lines or the baseline row |
| `tests/checks/plan_links.rs::plan_links_checker_gives_every_fixtures_reports_exactly` | kept | itself | `check-links.sh` printing other bytes, stderr or exit code for a fixture, or calling `gh` or writing |
| `tests/checks/plan_links.rs::plan_links_checker_reads_each_reason_line_by_the_contract` | kept | itself | `check-links.sh` misreading a reason-line form |
| `tests/checks/plan_links.rs::plan_links_checker_refuses_bad_arguments_and_graph_reads` | kept | itself | `check-links.sh` accepting a bad argument or graph read, or writing on refusal |
| `tests/checks/plan_links.rs::plan_links_checker_reads_a_spec_through_gh` | kept | itself | `check-links.sh` reading a spec through `gh` with other calls or another report |
| `tests/checks/plan_links.rs::plan_links_checker_refuses_a_failed_or_partial_gh_read` | kept | itself | `check-links.sh` reporting from a failed, partial or repeating `gh` read |
| `tests/checks/public_tree.rs::ci_needs_no_private_files` | deleted | `.github/actions/docs-only/test.sh::ci-reads.txt deliberately lists no private input` (the same empty-file check, run by CI and the pre-push hook) |  |
| `tests/checks/public_tree.rs::public_files_use_the_final_openwiz_address` | kept | itself | a public file under contracts, crates, apps or tests with the old OpenWiz address |
| `tests/checks/schema_conformance.rs::the_whole_schema_uses_only_checked_keywords` | kept | itself | an inventory schema rule the checker ignores, or a dangling `$ref` |
| `tests/checks/schema_conformance.rs::the_lint_finds_rules_the_checker_would_ignore` | kept | itself | a lint that misses an unreferenced rule, a dangling `$ref` or an open `additionalProperties` |
| `tests/checks/schema_conformance.rs::the_schema_limits_match_the_core_limits` | kept | itself | the schema's recap `maxLength` and the core's `PURPOSE_MAX_CHARS` disagreeing |
| `tests/checks/schema_conformance.rs::every_envelope_fixture_matches_the_schema` | kept | itself | an envelope fixture the inventory schema refuses |
| `tests/checks/schema_conformance.rs::the_checker_rejects_missing_and_mistyped_fields` | kept | itself | a checker that accepts a missing or mistyped envelope field, so the fixture check proves nothing |
| `tests/checks/schema_conformance.rs::the_core_types_serialize_to_schema_valid_json` | kept | itself | core envelope types that serialize to JSON the schema refuses |
| `tests/cli-agent/github_token.rs::gi_p6_each_fixture_case_gives_its_exit_stdout_stderr_and_exact_request` | kept | itself | the token command giving another exit, output or mint request for a contract case |
| `tests/cli-agent/github_token.rs::gi_p6_read_asks_for_exactly_the_read_profile_and_write_for_the_apps` | kept | itself | `--read` minting write permissions, or a granted write accepted for a read |
| `tests/cli-agent/github_token.rs::gi_p6_the_jwt_authenticates_as_the_app_for_an_installation_token` | kept | itself | a JWT with wrong claims, header or signature |
| `tests/cli-agent/github_token.rs::gi_p6_an_expired_near_expiry_or_overlong_token_is_refused` | kept | itself | an expired, nearly expired or overlong token printed |
| `tests/cli-agent/github_token.rs::gi_p6_a_missing_or_unreadable_secret_or_app_id_exits_1_before_any_call` | kept | itself | a bad key or App id reaching GitHub instead of exit 1 |
| `tests/cli-agent/github_token.rs::gi_p6_an_unknown_repository_exits_3_and_never_mints` | kept | itself | a mint for a repository the App is not installed on |
| `tests/cli-agent/github_token.rs::gi_p6_a_refused_exchange_or_an_answer_outside_the_contract_exits_5` | kept | itself | a refused or out-of-contract exchange printed as a token |
| `tests/cli-agent/github_token.rs::gi_p6_a_lost_reply_is_a_failure_exit_1_never_a_token` | kept | itself | a lost reply treated as a token |
| `tests/cli-agent/github_token.rs::j48_a_user_app_mints_only_on_its_owners_account_and_the_factory_only_when_explicit` | kept | itself | a user App minting on another account, or the factory App without its explicit mode |
| `tests/cli-agent/github_token.rs::j48_an_unreadable_mode_or_a_revoked_or_foreign_app_key_mints_nothing` | kept | itself | an unreadable mode, or a revoked or foreign App key, minting a token |
| `tests/cli-agent/github_token.rs::gi_p6_usage_errors_exit_2_naming_no_value_and_calling_nothing` | kept | itself | a usage error that echoes a pasted value or calls GitHub |
| `tests/cli-agent/github_token.rs::gi_p6_the_parser_takes_the_contracts_form` | kept | itself | the parser refusing the contract's forms, or not lowercasing the repository |
| `tests/cli-agent/github_token.rs::gi_p6_help_prints_usage_and_reads_nothing` | kept | itself | token help that reads a secret or calls GitHub |
| `tests/cli-agent/github_token.rs::gi_p6_the_openwiz_program_routes_github_token_and_refuses_without_the_secret` | kept | itself | the real `openwiz` not routing `github token`, or minting without its secret |
| `tests/cli-agent/github_token.rs::r3_the_service_app_never_exchanges_for_another_owners_or_another_installation` | kept | itself | the service App exchanging its key for another owner's or installation's token |
| `tests/cli-agent/init.rs::installed_init_previews_and_applies_through_the_packaged_runtime` | kept | itself | installed `openwiz init` not reaching its packaged runtime, or a preview that writes (its fixture now placed without a writer: the base's ETXTBSY flake) |
| `tests/cli-agent/init.rs::installed_init_refuses_without_its_runtime_and_on_bad_arguments` | kept | itself | `init` without its runtime or with bad arguments writing state |
| `tests/cli-agent/init.rs::init_help_is_source_free_and_listed_in_agent_discovery` | kept | itself | `init` help reading state, or `init` missing from agent discovery |
| `tests/cli-agent/loop_contract.rs::the_stubs_print_the_schemas_not_built_document_and_read_nothing` | kept | itself | a loop stub printing a document the loop-cli schema refuses, or reading a source |
| `tests/cli-agent/loop_contract.rs::the_pinned_wizloops_files_match_their_record` | kept | itself | a pinned WizLoops file changed without its recorded hash |
| `tests/cli-agent/main.rs::cp1_catalogue_covers_the_public_command_flag_and_schema_matrix` | kept | itself | the agent catalogue advertising other commands or flags than the parsers take, or a result reference that does not resolve |
| `tests/cli-agent/main.rs::cp1_help_aliases_and_invalid_agent_forms_have_no_effects` | kept | itself | a help alias that fails or writes, or a bad `help --agent` form accepted |
| `tests/cli-agent/main.rs::cp1_zero_call_traps_detect_real_fixture_source_invocations` | kept | itself | source-call traps that record nothing, so every zero-call assertion would pass vacuously |
| `tests/cli-agent/main.rs::cp1_schema_refuses_broken_catalogues_and_pins_additive_result_shapes` | kept | itself | the CLI schema accepting a broken catalogue or a result document with a missing or extra field |
| `tests/cli-agent/main.rs::engine_schema_enforces_identity_numeric_and_effect_bounds` | kept | itself | the engine report schema accepting activation, a bad identity, number or effect |
| `tests/cli-agent/main.rs::cp1_advertised_flags_are_accepted_by_the_shipped_public_parsers` | kept | itself | an advertised flag the shipped parser refuses |
| `tests/cli-agent/main.rs::cp1_fleet_forms_separate_execution_from_read_only_candidates_and_plans` | kept | itself | the catalogue giving a read-only fleet form an executing effect, or the reverse |
| `tests/cli-agent/main.rs::cp1_catalogue_is_discoverable_without_sources_or_state` | kept | itself | `help --agent` reading a source, or changing an existing store |
| `tests/cli-agent/process.rs::cp2_due_has_a_json_empty_result_without_room_or_state` | kept | itself | `fleet due --json` on an empty GitHub reading CloudRoom or making state |
| `tests/cli-agent/process.rs::cp2_inventory_success_partial_and_failure_keep_their_meaning` | kept | itself | `ls` and `show` JSON giving another exit or kind for complete, partial, failed or not-found reads |
| `tests/cli-agent/process.rs::cp2_stdin_and_store_errors_emit_documents_before_any_source_call` | kept | itself | bad stdin or an unusable store reaching a source before the error document |
| `tests/cli-agent/process.rs::cp2_send_reports_cover_outcomes_replay_conflict_lookup_and_preview` | kept | itself | a send report, replay, `--check` lookup, conflict or preview with another exit or schema |
| `tests/cli-agent/process.rs::cp2_uncertain_send_is_not_retried_and_duplicate_stays_nonzero` | kept | itself | an uncertain send retried, or a possible duplicate exiting 0 |
| `tests/cli-agent/process.rs::cp2_new_models_preview_create_replay_refusal_and_status` | kept | itself | `new`, `models` or `new --status` JSON with another exit or schema, or a replay that spawns again |
| `tests/cli-agent/process.rs::cp2_new_failed_uncertain_and_unavailable_options_remain_reports` | kept | itself | a failed, uncertain or unavailable `new` spawning again or leaking its stderr |
| `tests/cli-agent/process.rs::cp2_attachment_reports_include_preparation_failures_and_partial_results` | kept | itself | an attachment report that hides a failed path behind a ready one |
| `tests/cli-agent/process.rs::cp2_due_candidates_and_tick_reports_follow_the_recorded_world` | kept | itself | `fleet due` and `tick` reports disagreeing with their recorded world |
| `tests/cli-agent/process.rs::cp2_fleet_source_failures_and_partial_fleets_preserve_reports` | kept | itself | a fleet source failure that writes, or a partial fleet read without its coverage |
| `tests/cli-agent/process.rs::cp2_claimed_operations_report_in_progress_then_failed_without_dispatch` | kept | itself | a claimed send or new dispatched again instead of reported in progress |
| `tests/cli-agent/process.rs::cp2_local_switch_events_keep_their_exact_unwrapped_shape` | kept | itself | `loop on/off` printing an event the CLI schema refuses |
| `tests/cli-agent/process.rs::cp2_attachment_claim_refusal_keeps_copies_and_numeric_exit` | kept | itself | `attachment rm` deleting a claimed copy instead of exit 14 |
| `tests/cli-agent/process.rs::cp2_delimiter_and_stdin_flag_text_reach_the_target_as_data` | kept | itself | message text that looks like a flag parsed as one |
| `tests/cli-agent/process.rs::cp2_non_utf8_attachment_paths_remain_supported_without_lossy_input` | kept | itself | a non-UTF-8 attachment path refused or changed |
| `tests/cli-agent/process.rs::cp2_late_duplicate_attachment_error_does_not_rollback_preparation` | kept | itself | a late duplicate-attachment refusal in JSON mode that loses staged copies or calls a source |
| `tests/cli-agent/process.rs::cp2_broken_stdout_preserves_legacy_outcome_without_retry_or_stderr_document` | kept | itself | a closed stdout making send retry or print an error document |
| `tests/cli-agent/process.rs::cp2_legacy_repeatable_json_switches_remain_idempotent` | kept | itself | a repeated `--json` refused or sending twice |
| `tests/cli-agent/process.rs::cp2_attachment_store_errors_return_one_cli_error` | kept | itself | an unusable attachment store giving other than one exit-10 error document |
| `tests/cli-agent/results.rs::cp2_usage_errors_cover_every_dispatch_family_without_effects` | kept | itself | a usage error in any command family without its one error document, or with an effect |
| `tests/cli-agent/results.rs::cp2_json_help_is_one_document_with_no_reads_or_state` | kept | itself | `--help --json` printing other than one help document, or reading |
| `tests/cli-agent/results.rs::cp2_json_selection_respects_values_delimiters_and_invalid_bytes` | kept | itself | `--json` as an option's value or after `--` switching to JSON, or invalid bytes accepted |
| `tests/cli-agent/results.rs::cp2_no_command_json_is_bounded_usage_without_effects` | kept | itself | bare `openwiz` or `openwiz --json` doing anything but a usage error |
| `tests/cli-agent/results.rs::cp2_all_known_value_options_consume_flag_looking_data` | kept | itself | a value option that takes a flag-looking value as a flag |
| `tests/cli-agent/review.rs::r1_help_precedence_matches_the_shipped_parser_and_catalogue` | kept | itself | `--help` losing or winning precedence against what the parser and catalogue say |
| `tests/cli-agent/review.rs::r2_duplicate_attachment_rejection_retains_staged_bytes_without_source_calls` | kept | itself | a duplicate attachment id that calls a source or loses staged bytes |
| `tests/cli-agent/review.rs::r2_catalogue_qualifies_late_usage_rejection_and_unique_ids` | kept | itself | the catalogue promising unchanged local state on a usage error, or dropping the unique-id rule |
| `tests/cli-agent/review.rs::r3_catalogue_and_schema_cover_conditional_external_programs` | kept | itself | the catalogue hiding an external program a command can run, or the schema accepting an unknown one |
| `tests/cli-agent/ui.rs::ui_json_is_the_capability_document_and_opens_nothing` | kept | itself | `ui --json` printing another capability document, or opening something; #776 removes it with `openwiz ui` |
| `tests/cli-agent/ui.rs::ui_help_errors_and_non_terminal_use_never_wait_or_launch` | kept | itself | `ui` help, errors or non-terminal use waiting or launching; #776 removes it with `openwiz ui` |
| `tests/cli-agent/ui.rs::the_catalogue_registers_ui_with_its_flags_and_capability_schema` | kept | itself | the catalogue's `ui` entry disagreeing with its flags or capability schema; #776 removes it with `openwiz ui` |
| `tests/cli-agent/ui.rs::ui_capability_actions_come_from_the_terminal_registry` | kept | itself | a CLI-side action list that drifts from the terminal registry; #776 removes it with `openwiz ui` |
| `tests/cli-agent/ui.rs::an_action_registered_in_its_module_appears_in_ui_json` | kept | itself | a registered action missing from an installed `ui --json`, or a stub listed; #776 removes it with `openwiz ui` |
| `tests/support/cloudroom_process_tests.rs::ordinary_polling_stays_at_five_milliseconds` | merged | `tests/support/cloudroom_process_tests.rs::fixture_polling_is_fixed_and_process_local` | (as its keeper: it asserts the same 5 ms first) |
| `tests/support/cloudroom_process_tests.rs::fixture_polling_is_fixed_and_process_local` | kept | itself | ordinary polling other than 5 ms, or the fixture's 1 ms leaking out of its own process |
| `tests/support/cloudroom_process_tests.rs::the_read_timeout_is_read_timeout_unless_a_fixture_lowers_it` | kept | itself | a fixture value that raises the read timeout above `READ_TIMEOUT` |
| `tests/support/cloudroom_process_tests.rs::held_process_placement_refuses_a_directory_destination` | deleted | behaviour gone: an unreachable case; this file's fixtures place only fresh paths in their own new folder, so no caller can pass a directory (the guard line in `place` stays) |  |
| `tests/support/cloudroom_process_tests.rs::an_oversized_read_is_refused_without_waiting_for_child_exit` | kept | itself | an oversized read waiting for a live child instead of refusing and reaping it |
| `tests/support/cloudroom_process_tests.rs::over_cap_writes_keep_waiting_and_are_never_early_malformed` | kept | itself | an over-cap write refused early as malformed instead of keeping its timeout outcome |
| `tests/support/cloudroom_process_tests.rs::the_response_collector_reads_exactly_the_cap_plus_one` | kept | itself | a collector that reads more or less than the cap plus one byte |
| `tests/support/cloudroom_process_tests.rs::held_process_fixtures_start_during_concurrent_placement_and_forks` | kept | itself | held-process fixtures that hit ETXTBSY while sibling tests fork (#2896) |
| `tests/support/forks.rs::a_lock_stays_listed_while_a_childs_copy_holds_it` | moved | `tests/checks/support_proofs.rs::a_lock_stays_listed_while_a_childs_copy_holds_it` | `/proc/locks` not listing a lock a child's copy holds, which every lock wait relies on |
| `tests/support/real_time.rs::a_scaled_duration_covers_the_measured_read_within_its_cap` | moved | `tests/checks/support_proofs.rs::a_scaled_duration_covers_the_measured_read_within_its_cap` | a scaled real-time duration below its measured read's slack or above its cap |
| `tests/support/real_time.rs::only_a_first_attempt_pull_request_to_main_gets_the_fast_form` | moved | `tests/checks/support_proofs.rs::only_a_first_attempt_pull_request_to_main_gets_the_fast_form` | a real-time proof running its fast form anywhere but a first-attempt pull request to `main` |
| `tests/support/schema.rs::shared_text_keywords_are_linted_and_enforced` | moved | `tests/checks/support_proofs.rs::shared_text_keywords_are_linted_and_enforced` | a shared checker that lints a text keyword but does not enforce it |

## New test

`tests/checks/support_proofs.rs::placing_a_program_leaves_no_writer_a_concurrent_fork_could_inherit`.
catches: a fixture program written by this process while sibling test
threads fork, so a child keeps the file open for writing and starting it
fails with ETXTBSY. It happened on this group's base:
`tests/cli-agent/init.rs::installed_init_previews_and_applies_through_the_packaged_runtime`
failed with "Text file busy" during the before measure. The proof holds the
copy still on a FIFO and counts this process's writable descriptors; it
failed red with one ([red-place.txt](red-place.txt)) before
`tests/support/place.rs` copied through a separate `cp`.

## Where the kept tests live

No test moved into a crate's own `tests/` folder. Every kept test runs the
`openwiz` fixture program, reads the repository's contracts, fixtures,
skills or Git index, or shares this folder's helpers, so none exercises one
crate alone:

- **`tests/checks/`:** repository-wide guards (dependencies, fixtures,
  schemas, the pending list, the public tree); they read many crates' and
  folders' files, not one crate's code.
- **`tests/cli-agent/`:** each runs the `openwiz-tests` fixture example
  binary, or shares `github_token.rs`'s key and fake helpers
  (`r3_the_service_app_never_exchanges_for_another_owners_or_another_installation`
  is the one test that calls only `openwiz-adapter-github`; it needs those
  helpers and the shared `dirs.rs`).
- **`tests/support/cloudroom_process_tests.rs`:** already the adapter's
  own unit tests, through a `#[path]` in `crates/adapters/cloudroom/src/process.rs`
  (product source this ticket does not own); `tests/service/t6_fixture.rs`
  also copies its bytes.
