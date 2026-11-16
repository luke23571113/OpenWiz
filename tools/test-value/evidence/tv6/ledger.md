# TV6 (#808): the new-thread group's ledger

Every test of the `new-thread` target (`tests/new-thread/`, run as `cargo
test -p openwiz-tests --test new-thread`) at this pull request's base,
`20a5100`: 113 `#[test]`s, one row each, in the form of
`tools/test-value/README.md`, plus one row for each of the 89 named cases
the 19 wrappers (`…_preserve_…_cases`) run (#1259). Two of the 113 are
compiled in from `tests/support/` (`schema.rs`, `forks.rs`); they are
TV9's (#811) and unchanged here.

- **`#[test]` rows (113):** kept 104, deleted 7, moved 2. The new-thread
  target now runs 104; the two moved wrappers became 4 tests in their
  crates (one in `openwiz-core`, three in `openwiz-adapter-cloudroom`), so
  the group runs 108.
- **Case rows (89):** kept 72, deleted 9, merged 2, moved 6.
- **Catches** for a kept test is the behaviour its name and body assert: a
  change that breaks it fails the test. A wrapper's own row says `(as its
  cases)`.
- **Keepers checked:** every deleted case whose keeper is another test was
  broken in a scratch worktree and its keeper run alone
  ([`keepers.txt`](keepers.txt)): 12 breaks, 12 keepers failed.

## Where the kept tests live

Moved, because they call one crate's public functions and run no program:

- `project_names.rs` (core's `resolve_project`) →
  `crates/core/tests/new_thread_project_names.rs`.
- `n03_existing_projects.rs`'s reader cases and `boundary_readers.rs`'s
  receipt table (the adapter's `parse_projects`, `is_github_remote`,
  `spawn_receipt`) → `crates/adapters/cloudroom/tests/new_thread_readers.rs`.

Stay in `tests/new-thread/`, one reason per kind:

- **They run a program or the CLI** (the release `openwiz`, the in-process
  CLI, the self-exec harness or a shell against the fake `room-cli`), so
  they cross the CLI, adapter, core and store: `n01_end_to_end`, `n02`,
  `n03` (CLI cases), `n06`'s process cases, `n09`, `n10`, `n12`, `n13`,
  `n15`, `n17`, `n18_cli`, `record_store`, `record_load`,
  `boundary_readers` (CLI cases), `ad_new_thread_attachments`,
  `inspect_claim_race`, `harness`.
- **They run the core through the test client** (`support.rs`'s
  `FakeClient` answers through the adapter's parsers, with `MemoryStore`),
  so they cross core and adapter: `n04`, `n05`, `n06`'s wrapper, `n07`,
  `n08`, `n11`, `n14`, `n18_report`, `n19`.
- **They check the contracts with this folder's schema checker**
  (`pattern.rs`, and `serde_json`, which `openwiz-core` has no
  dev-dependency on): `contract_tables`, `schema_parity`, `structure`,
  `pattern`.
- **W1-7, a guard refuses them under `crates/`:**
  `n16_allowlist.rs` (P8(a) and M12 refuse the spawn flags it spells, such
  as `--model`) and `boundary_readers.rs`'s catalogue table (M12 refuses
  the word `steer`). Both were moved, failed the guards locally and were
  moved back unchanged.
- **Shared support** (`tests/support/schema.rs`, `forks.rs`): TV9's.

| Test | Outcome | Keeper | Catches |
| --- | --- | --- | --- |
| `tests/new-thread/ad_new_thread_attachments.rs::ad01_one_spawn_carries_every_staged_copy_before_the_prompt` | kept | itself | a change that breaks: ad01 one spawn carries every staged copy before the prompt |
| `tests/new-thread/ad_new_thread_attachments.rs::newthread_attachment_contracts_preserve_original_cases` | kept | itself | (as its cases) |
| `tests/new-thread/ad_new_thread_attachments.rs::newthread_attachment_contracts_preserve_original_cases::ad01_no_relative_token_file_url_or_unplain_path_can_become_a_staged_path` | kept | itself | a change that breaks: ad01 no relative token file url or unplain path can become a staged path |
| `tests/new-thread/ad_new_thread_attachments.rs::newthread_attachment_contracts_preserve_original_cases::ad01_tell_and_spawn_get_the_same_tail_from_attachment_args` | deleted | `tests/new-thread/ad_new_thread_attachments.rs::ad01_one_spawn_carries_every_staged_copy_before_the_prompt` (spawn) and `tests/messaging/ad_send_attachments.rs::ad13_attach_and_attachment_send_one_tell_and_the_json_matches_the_text` (tell) |  |
| `tests/new-thread/ad_new_thread_attachments.rs::newthread_attachment_contracts_preserve_original_cases::ad04_the_record_reader_takes_attachments_only_exactly_and_agreeing` | kept | itself | a change that breaks: ad04 the record reader takes attachments only exactly and agreeing |
| `tests/new-thread/ad_new_thread_attachments.rs::ad04_same_op_id_and_payload_is_one_spawn_any_attachment_difference_is_refused` | kept | itself | a change that breaks: ad04 same op id and payload is one spawn any attachment difference is refused |
| `tests/new-thread/ad_new_thread_attachments.rs::ad04_an_a1_record_without_attachments_still_reads_and_matches` | kept | itself | a change that breaks: ad04 an a1 record without attachments still reads and matches |
| `tests/new-thread/ad_new_thread_attachments.rs::ad06_across_processes_and_restarts_no_request_id_carries_two_payloads` | kept | itself | a change that breaks: ad06 across processes and restarts no request id carries two payloads |
| `tests/new-thread/ad_new_thread_attachments.rs::ad07_every_row_of_the_outcome_table_for_spawn` | kept | itself | a change that breaks: ad07 every row of the outcome table for spawn |
| `tests/new-thread/ad_new_thread_attachments.rs::ad09_retention_follows_the_table_for_a_new_thread` | kept | itself | a change that breaks: ad09 retention follows the table for a new thread |
| `tests/new-thread/ad_new_thread_attachments.rs::ad10_a_crash_at_each_step_keeps_the_attachments_and_creates_nothing_more` | kept | itself | a change that breaks: ad10 a crash at each step keeps the attachments and creates nothing more |
| `tests/new-thread/ad_new_thread_attachments.rs::ad13_new_with_attach_and_attachment_creates_once_and_the_json_matches_the_text` | kept | itself | a change that breaks: ad13 new with attach and attachment creates once and the json matches the text |
| `tests/new-thread/ad_new_thread_attachments.rs::ad13_the_preview_stages_and_prints_the_command_with_each_attachment` | kept | itself | a change that breaks: ad13 the preview stages and prints the command with each attachment |
| `tests/new-thread/ad_new_thread_attachments.rs::ad13_attach_that_fails_on_any_path_creates_nothing` | kept | itself | a change that breaks: ad13 attach that fails on any path creates nothing |
| `tests/new-thread/ad_new_thread_attachments.rs::ad13_the_printed_command_attaches_exactly_the_previewed_copy` | kept | itself | a change that breaks: ad13 the printed command attaches exactly the previewed copy |
| `tests/new-thread/boundary_readers.rs::boundary_readers_affected_contracts_preserve_original_cases` | kept | itself | (as its cases) |
| `tests/new-thread/boundary_readers.rs::boundary_readers_affected_contracts_preserve_original_cases::the_catalogue_table` | kept | itself | a change that breaks: the catalogue table |
| `tests/new-thread/boundary_readers.rs::boundary_readers_affected_contracts_preserve_original_cases::the_receipt_table` | moved | `crates/adapters/cloudroom/tests/new_thread_readers.rs::the_receipt_table` | a spawn receipt reader that takes a key given twice, a missing id or projectId, or refuses an additive key |
| `tests/new-thread/boundary_readers.rs::sols_duplicate_receipt_is_uncertain_and_keeps_the_prompt` | kept | itself | a change that breaks: sols duplicate receipt is uncertain and keeps the prompt |
| `tests/new-thread/boundary_readers.rs::nested_duplicate_receipt_is_uncertain_through_cli` | kept | itself | a change that breaks: nested duplicate receipt is uncertain through cli |
| `tests/new-thread/boundary_readers.rs::sols_duplicate_ready_offers_nothing_and_creates_nothing` | kept | itself | a change that breaks: sols duplicate ready offers nothing and creates nothing |
| `tests/new-thread/boundary_readers.rs::the_other_reads_refuse_a_key_given_twice` | kept | itself | a change that breaks: the other reads refuse a key given twice |
| `tests/new-thread/boundary_readers.rs::thread_show_distinguishes_not_found_from_other_command_failures` | kept | itself | a change that breaks: thread show distinguishes not found from other command failures |
| `tests/new-thread/contract_tables.rs::contract_tables_contracts_preserve_all_original_cases` | kept | itself | (as its cases) |
| `tests/new-thread/contract_tables.rs::contract_tables_contracts_preserve_all_original_cases::erased_created_records_require_both_digest_length_and_lowercase_hex` | kept | itself | a change that breaks: erased created records require both digest length and lowercase hex |
| `tests/new-thread/contract_tables.rs::contract_tables_contracts_preserve_all_original_cases::the_prompt_contract` | kept | itself | a change that breaks: the prompt contract |
| `tests/new-thread/contract_tables.rs::contract_tables_contracts_preserve_all_original_cases::the_record_contract_with_nested_forms` | kept | itself | a change that breaks: the record contract with nested forms |
| `tests/new-thread/contract_tables.rs::contract_tables_contracts_preserve_all_original_cases::the_records_reader_follows_the_table` | kept | itself | a change that breaks: the records reader follows the table |
| `tests/new-thread/contract_tables.rs::contract_tables_contracts_preserve_all_original_cases::the_settings_and_project_reference_contracts` | kept | itself | a change that breaks: the settings and project reference contracts |
| `tests/new-thread/contract_tables.rs::contract_tables_contracts_preserve_all_original_cases::the_string_enum_contracts` | kept | itself | a change that breaks: the string enum contracts |
| `tests/new-thread/harness.rs::harness_process` | kept | itself | not a proof: the self-exec child that `n12`, `n13` and `ad10` start; it returns at once in a normal run, so its row counts but it catches nothing alone |
| `tests/new-thread/inspect_claim_race.rs::a_stopped_owner_recovers_despite_a_child_copy_of_an_inspection_lock` | kept | itself | a change that breaks: a stopped owner recovers despite a child copy of an inspection lock |
| `tests/new-thread/inspect_claim_race.rs::a_stopped_dispatching_owner_stays_uncertain_despite_an_inspection_copy` | kept | itself | a change that breaks: a stopped dispatching owner stays uncertain despite an inspection copy |
| `tests/new-thread/n01_end_to_end.rs::one_create_makes_one_spawn_in_exactly_the_shape` | kept | itself | a change that breaks: one create makes one spawn in exactly the shape |
| `tests/new-thread/n01_end_to_end.rs::the_text_is_one_argument_byte_for_byte` | kept | itself | a text changed, split or read as a flag on its way to `--prompt` (now also shell syntax and a bare `--`, merged from `n01_exact_invocation`) |
| `tests/new-thread/n01_end_to_end.rs::the_text_from_stdin_reaches_the_spawn_unchanged` | kept | itself | a change that breaks: the text from stdin reaches the spawn unchanged |
| `tests/new-thread/n01_end_to_end.rs::every_setting_is_passed_as_chosen_and_none_is_omitted` | kept | itself | a change that breaks: every setting is passed as chosen and none is omitted |
| `tests/new-thread/n01_exact_invocation.rs::n01_exact_invocation_affected_contracts_preserve_original_cases` | deleted | each case's keeper, below |  |
| `tests/new-thread/n01_exact_invocation.rs::n01_exact_invocation_affected_contracts_preserve_original_cases::an_unsafe_value_is_refused_not_passed` | deleted | `tests/new-thread/n16_allowlist.rs::n16_allowlist_affected_contracts_preserve_original_cases::a_spawn_can_only_be_built_with_safe_arguments` |  |
| `tests/new-thread/n01_exact_invocation.rs::n01_exact_invocation_affected_contracts_preserve_original_cases::every_setting_is_explicit_once` | deleted | `tests/new-thread/n01_end_to_end.rs::one_create_makes_one_spawn_in_exactly_the_shape` |  |
| `tests/new-thread/n01_exact_invocation.rs::n01_exact_invocation_affected_contracts_preserve_original_cases::no_excluded_flag_is_ever_passed` | deleted | `tests/new-thread/n01_end_to_end.rs::one_create_makes_one_spawn_in_exactly_the_shape` |  |
| `tests/new-thread/n01_exact_invocation.rs::n01_exact_invocation_affected_contracts_preserve_original_cases::the_arguments_are_exactly_the_verified_shape` | deleted | `tests/new-thread/n01_end_to_end.rs::one_create_makes_one_spawn_in_exactly_the_shape` |  |
| `tests/new-thread/n01_exact_invocation.rs::n01_exact_invocation_affected_contracts_preserve_original_cases::the_core_passes_the_chosen_settings_and_derived_request_id` | deleted | `tests/new-thread/n01_end_to_end.rs::every_setting_is_passed_as_chosen_and_none_is_omitted` (settings) and `tests/new-thread/n11_op_id_binding.rs::synthetic_request_id_matches_contract_at_spawn` (the request id) |  |
| `tests/new-thread/n01_exact_invocation.rs::n01_exact_invocation_affected_contracts_preserve_original_cases::the_text_is_one_last_argument_byte_for_byte` | merged | `tests/new-thread/n01_end_to_end.rs::the_text_is_one_argument_byte_for_byte` | (as its keeper; its two texts not already there, the shell-syntax one and `--`, were added) |
| `tests/new-thread/n02_no_rewrite.rs::n02_no_rewrite_affected_contracts_preserve_original_cases` | kept | itself | (as its cases) |
| `tests/new-thread/n02_no_rewrite.rs::n02_no_rewrite_affected_contracts_preserve_original_cases::the_model_passed_is_the_model_chosen` | kept | itself | a change that breaks: the model passed is the model chosen |
| `tests/new-thread/n02_no_rewrite.rs::n02_no_rewrite_affected_contracts_preserve_original_cases::the_scrub_list_is_the_sheets` | kept | itself | a change that breaks: the scrub list is the sheets |
| `tests/new-thread/n02_no_rewrite.rs::every_call_runs_without_the_thread_context` | kept | itself | a change that breaks: every call runs without the thread context |
| `tests/new-thread/n02_no_rewrite.rs::new_yes_scrubs_thread_context_on_every_call_including_spawn` | kept | itself | a change that breaks: new yes scrubs thread context on every call including spawn |
| `tests/new-thread/n03_existing_projects.rs::only_a_standard_project_with_a_github_remote_is_accepted` | kept | itself | a change that breaks: only a standard project with a github remote is accepted |
| `tests/new-thread/n03_existing_projects.rs::conflicting_duplicate_project_is_refused_through_cli` | kept | itself | a change that breaks: conflicting duplicate project is refused through cli |
| `tests/new-thread/n03_existing_projects.rs::unusable_project_ids_are_refused_with_readable_status` | kept | itself | a change that breaks: unusable project ids are refused with readable status |
| `tests/new-thread/n03_existing_projects.rs::a_shared_name_is_resolved_only_by_its_qualified_form_or_its_id` | kept | itself | a change that breaks: a shared name is resolved only by its qualified form or its id |
| `tests/new-thread/n03_existing_projects.rs::a_project_list_that_cannot_be_read_creates_nothing` | kept | itself | a change that breaks: a project list that cannot be read creates nothing |
| `tests/new-thread/n03_existing_projects.rs::n03_existing_projects_contracts_preserve_all_original_cases` | moved | its two cases, below, each now its own test | (as its cases) |
| `tests/new-thread/n03_existing_projects.rs::n03_existing_projects_contracts_preserve_all_original_cases::projects_are_read_with_their_kind_and_remote` | moved | `crates/adapters/cloudroom/tests/new_thread_readers.rs::projects_are_read_with_their_kind_and_remote` | a project list reader that loses a row's kind or remote, or reads a mistyped one as known; it gained one drift row, an empty id, which catches a reader that names a project with an empty id (red first: `red.txt`) |
| `tests/new-thread/n03_existing_projects.rs::n03_existing_projects_contracts_preserve_all_original_cases::the_github_rule` | moved | `crates/adapters/cloudroom/tests/new_thread_readers.rs::the_github_rule` | a remote rule that takes a lookalike host, another scheme or a user-info URL as GitHub |
| `tests/new-thread/n04_offered_only.rs::n4_offered_choice_contracts_preserve_all_original_cases` | kept | itself | (as its cases) |
| `tests/new-thread/n04_offered_only.rs::n4_offered_choice_contracts_preserve_all_original_cases::a_model_with_no_shared_effort_is_not_offered` | kept | itself | a change that breaks: a model with no shared effort is not offered |
| `tests/new-thread/n04_offered_only.rs::n4_offered_choice_contracts_preserve_all_original_cases::an_off_catalogue_claude_code_model_is_refused` | kept | itself | a change that breaks: an off catalogue claude code model is refused |
| `tests/new-thread/n04_offered_only.rs::n4_offered_choice_contracts_preserve_all_original_cases::an_unoffered_harness_model_or_effort_is_refused_with_zero_calls` | kept | itself | a change that breaks: an unoffered harness model or effort is refused with zero calls |
| `tests/new-thread/n04_offered_only.rs::n4_offered_choice_contracts_preserve_all_original_cases::an_unverified_mapping_is_unavailable_even_with_models` | kept | itself | a change that breaks: an unverified mapping is unavailable even with models |
| `tests/new-thread/n04_offered_only.rs::n4_offered_choice_contracts_preserve_all_original_cases::conflicting_catalogue_rows_are_unavailable_in_both_orders` | kept | itself | a change that breaks: conflicting catalogue rows are unavailable in both orders |
| `tests/new-thread/n04_offered_only.rs::n4_offered_choice_contracts_preserve_all_original_cases::conflicting_provider_mappings_are_unavailable_in_both_orders` | kept | itself | a change that breaks: conflicting provider mappings are unavailable in both orders |
| `tests/new-thread/n04_offered_only.rs::n4_offered_choice_contracts_preserve_all_original_cases::each_model_uses_its_own_effort_levels` | kept | itself | a change that breaks: each model uses its own effort levels |
| `tests/new-thread/n04_offered_only.rs::n4_offered_choice_contracts_preserve_all_original_cases::identical_catalogue_rows_collapse_and_every_shown_choice_is_accepted` | kept | itself | a change that breaks: identical catalogue rows collapse and every shown choice is accepted |
| `tests/new-thread/n04_offered_only.rs::n4_offered_choice_contracts_preserve_all_original_cases::no_options_refuses_everything` | kept | itself | a change that breaks: no options refuses everything |
| `tests/new-thread/n04_offered_only.rs::n4_offered_choice_contracts_preserve_all_original_cases::nothing_is_defaulted` | kept | itself | a change that breaks: nothing is defaulted |
| `tests/new-thread/n04_offered_only.rs::n4_offered_choice_contracts_preserve_all_original_cases::only_codex_and_claude_code_are_offered_with_the_intersection_of_efforts` | kept | itself | a change that breaks: only codex and claude code are offered with the intersection of efforts |
| `tests/new-thread/n04_offered_only.rs::n4_offered_choice_contracts_preserve_all_original_cases::the_refusal_names_what_is_offered_and_substitutes_nothing` | kept | itself | a change that breaks: the refusal names what is offered and substitutes nothing |
| `tests/new-thread/n05_honest_options.rs::n05_honest_options_affected_contracts_preserve_original_cases` | kept | itself | (as its cases) |
| `tests/new-thread/n05_honest_options.rs::n05_honest_options_affected_contracts_preserve_original_cases::account_and_other_fields_never_reach_the_core` | kept | itself | a change that breaks: account and other fields never reach the core |
| `tests/new-thread/n05_honest_options.rs::n05_honest_options_affected_contracts_preserve_original_cases::not_ready_null_harnesses_and_a_failed_read_give_no_options` | kept | itself | a change that breaks: not ready null harnesses and a failed read give no options |
| `tests/new-thread/n05_honest_options.rs::n05_honest_options_affected_contracts_preserve_original_cases::the_options_carry_the_read_time_and_the_saved_copy_label` | kept | itself | a change that breaks: the options carry the read time and the saved copy label |
| `tests/new-thread/n06_outcome_mapping.rs::n06_outcome_mapping_affected_contracts_preserve_original_cases` | kept | itself | (as its cases) |
| `tests/new-thread/n06_outcome_mapping.rs::n06_outcome_mapping_affected_contracts_preserve_original_cases::a_call_that_never_started_failed_and_sent_nothing` | kept | itself | a change that breaks: a call that never started failed and sent nothing |
| `tests/new-thread/n06_outcome_mapping.rs::n06_outcome_mapping_affected_contracts_preserve_original_cases::a_receipt_is_created_and_never_started` | kept | itself | a change that breaks: a receipt is created and never started |
| `tests/new-thread/n06_outcome_mapping.rs::n06_outcome_mapping_affected_contracts_preserve_original_cases::anything_else_is_uncertain` | kept | itself | a change that breaks: anything else is uncertain |
| `tests/new-thread/n06_outcome_mapping.rs::n06_outcome_mapping_affected_contracts_preserve_original_cases::every_documented_refusal_is_refused_and_nothing_is_created` | kept | itself | a change that breaks: every documented refusal is refused and nothing is created |
| `tests/new-thread/n06_outcome_mapping.rs::an_absent_spawn_program_is_not_started` | kept | itself | a change that breaks: an absent spawn program is not started |
| `tests/new-thread/n06_outcome_mapping.rs::a_spawn_wait_failure_stays_uncertain` | kept | itself | a change that breaks: a spawn wait failure stays uncertain |
| `tests/new-thread/n07_requested_and_reported.rs::n07_requested_and_reported_contracts_preserve_all_original_cases` | kept | itself | (as its cases) |
| `tests/new-thread/n07_requested_and_reported.rs::n07_requested_and_reported_contracts_preserve_all_original_cases::a_differing_report_is_shown_as_differing` | kept | itself | a change that breaks: a differing report is shown as differing |
| `tests/new-thread/n07_requested_and_reported.rs::n07_requested_and_reported_contracts_preserve_all_original_cases::a_matching_report_is_shown_as_requested` | kept | itself | a change that breaks: a matching report is shown as requested |
| `tests/new-thread/n07_requested_and_reported.rs::n07_requested_and_reported_contracts_preserve_all_original_cases::an_unread_report_is_never_called_as_requested` | kept | itself | a change that breaks: an unread report is never called as requested |
| `tests/new-thread/n07_requested_and_reported.rs::n07_requested_and_reported_contracts_preserve_all_original_cases::reported_is_never_the_serving_model` | kept | itself | a change that breaks: reported is never the serving model |
| `tests/new-thread/n07_requested_and_reported.rs::n07_requested_and_reported_contracts_preserve_all_original_cases::the_report_keeps_the_request_as_it_was_asked` | kept | itself | a change that breaks: the report keeps the request as it was asked |
| `tests/new-thread/n08_start_stages.rs::n08_start_stages_contracts_preserve_all_original_cases` | kept | itself | (as its cases) |
| `tests/new-thread/n08_start_stages.rs::n08_start_stages_contracts_preserve_all_original_cases::a_failed_read_is_unknown_with_a_gap` | kept | itself | a change that breaks: a failed read is unknown with a gap |
| `tests/new-thread/n08_start_stages.rs::n08_start_stages_contracts_preserve_all_original_cases::a_long_last_error_is_cut_to_the_field_cap` | kept | itself | a change that breaks: a long last error is cut to the field cap |
| `tests/new-thread/n08_start_stages.rs::n08_start_stages_contracts_preserve_all_original_cases::a_thread_show_of_another_thread_is_not_read` | kept | itself | a change that breaks: a thread show of another thread is not read |
| `tests/new-thread/n08_start_stages.rs::n08_start_stages_contracts_preserve_all_original_cases::every_status_row_has_its_stage` | kept | itself | a change that breaks: every status row has its stage |
| `tests/new-thread/n08_start_stages.rs::n08_start_stages_contracts_preserve_all_original_cases::following_stops_within_the_bound` | kept | itself | a change that breaks: following stops within the bound |
| `tests/new-thread/n09_lost_acknowledgement.rs::a_create_that_times_out_is_uncertain_and_is_never_redone` | kept | itself | a change that breaks: a create that times out is uncertain and is never redone |
| `tests/new-thread/n09_lost_acknowledgement.rs::a_create_that_crashes_or_answers_garbage_is_uncertain` | kept | itself | a change that breaks: a create that crashes or answers garbage is uncertain |
| `tests/new-thread/n09_lost_acknowledgement.rs::a_documented_refusal_is_refused_and_creates_nothing` | kept | itself | a change that breaks: a documented refusal is refused and creates nothing |
| `tests/new-thread/n09_lost_acknowledgement.rs::observations_never_settle_an_uncertain_create` | kept | itself | a change that breaks: observations never settle an uncertain create |
| `tests/new-thread/n09_lost_acknowledgement.rs::synthetic_status_observations_use_claim_time` | kept | itself | a change that breaks: synthetic status observations use claim time |
| `tests/new-thread/n09_lost_acknowledgement.rs::synthetic_status_text_labels_observations_as_inconclusive` | kept | itself | a change that breaks: synthetic status text labels observations as inconclusive |
| `tests/new-thread/n09_lost_acknowledgement.rs::synthetic_status_text_preserves_known_observed_creation_time` | kept | itself | a change that breaks: synthetic status text preserves known observed creation time |
| `tests/new-thread/n10_no_retry.rs::there_is_no_retry` | kept | itself | a `--retry` accepted, or one that reads or calls anything (its source-grep tail is cut: the behaviour half above it is the keeper) |
| `tests/new-thread/n10_no_retry.rs::an_uncertain_create_stays_uncertain_and_one_thread_in_all` | kept | itself | a change that breaks: an uncertain create stays uncertain and one thread in all |
| `tests/new-thread/n10_no_retry.rs::the_fakes_request_id_table` | deleted | `tests/new-thread/n10_no_retry.rs::an_uncertain_create_stays_uncertain_and_one_thread_in_all` |  |
| `tests/new-thread/n11_op_id_binding.rs::n11_op_id_binding_contracts_preserve_all_original_cases` | kept | itself | (as its cases) |
| `tests/new-thread/n11_op_id_binding.rs::n11_op_id_binding_contracts_preserve_all_original_cases::an_op_id_held_by_a_live_process_is_in_progress_with_no_call` | kept | itself | a change that breaks: an op id held by a live process is in progress with no call |
| `tests/new-thread/n11_op_id_binding.rs::n11_op_id_binding_contracts_preserve_all_original_cases::any_difference_is_refused_with_zero_calls` | kept | itself | a change that breaks: any difference is refused with zero calls |
| `tests/new-thread/n11_op_id_binding.rs::n11_op_id_binding_contracts_preserve_all_original_cases::the_attachments_digest_is_part_of_the_binding` | deleted | `tests/new-thread/ad_new_thread_attachments.rs::ad04_same_op_id_and_payload_is_one_spawn_any_attachment_difference_is_refused` |  |
| `tests/new-thread/n11_op_id_binding.rs::n11_op_id_binding_contracts_preserve_all_original_cases::the_record_and_the_call_carry_the_derived_request_id` | kept | itself | a change that breaks: the record and the call carry the derived request id |
| `tests/new-thread/n11_op_id_binding.rs::n11_op_id_binding_contracts_preserve_all_original_cases::the_request_id_is_derived_deterministically_and_is_safe` | kept | itself | a change that breaks: the request id is derived deterministically and is safe |
| `tests/new-thread/n11_op_id_binding.rs::n11_op_id_binding_contracts_preserve_all_original_cases::the_same_op_id_and_binding_make_one_call` | kept | itself | a change that breaks: the same op id and binding make one call |
| `tests/new-thread/n11_op_id_binding.rs::synthetic_request_id_matches_contract_at_spawn` | kept | itself | a change that breaks: synthetic request id matches contract at spawn |
| `tests/new-thread/n12_cross_process_claim.rs::many_processes_racing_on_one_op_id_make_exactly_one_spawn` | kept | itself | a change that breaks: many processes racing on one op id make exactly one spawn |
| `tests/new-thread/n12_cross_process_claim.rs::racing_on_one_op_id_with_different_texts_still_creates_once` | kept | itself | a change that breaks: racing on one op id with different texts still creates once |
| `tests/new-thread/n13_crash_recovery.rs::stopped_after_the_claim_recovers_as_failed_before_dispatch` | kept | itself | a change that breaks: stopped after the claim recovers as failed before dispatch |
| `tests/new-thread/n13_crash_recovery.rs::stopped_after_the_dispatching_mark_recovers_as_uncertain` | kept | itself | a change that breaks: stopped after the dispatching mark recovers as uncertain |
| `tests/new-thread/n13_crash_recovery.rs::stopped_during_the_call_recovers_as_uncertain` | kept | itself | a change that breaks: stopped during the call recovers as uncertain |
| `tests/new-thread/n13_crash_recovery.rs::stopped_after_the_call_recovers_as_uncertain` | kept | itself | a change that breaks: stopped after the call recovers as uncertain |
| `tests/new-thread/n13_crash_recovery.rs::the_dispatching_mark_is_on_disk_before_the_call` | kept | itself | a change that breaks: the dispatching mark is on disk before the call |
| `tests/new-thread/n13_crash_recovery.rs::dispatching_write_failure_must_prevent_spawn` | kept | itself | a change that breaks: dispatching write failure must prevent spawn |
| `tests/new-thread/n14_prompt_seam.rs::n14_prompt_seam_contracts_preserve_all_original_cases` | kept | itself | (as its cases) |
| `tests/new-thread/n14_prompt_seam.rs::n14_prompt_seam_contracts_preserve_all_original_cases::a_file_path_in_the_text_is_sent_as_text` | deleted | `tests/new-thread/n01_end_to_end.rs::the_text_is_one_argument_byte_for_byte` |  |
| `tests/new-thread/n14_prompt_seam.rs::n14_prompt_seam_contracts_preserve_all_original_cases::a_text_only_prompt_passes_no_attachment_flag` | kept | itself | a change that breaks: a text only prompt passes no attachment flag |
| `tests/new-thread/n14_prompt_seam.rs::n14_prompt_seam_contracts_preserve_all_original_cases::an_attachment_id_is_one_safe_segment` | kept | itself | a change that breaks: an attachment id is one safe segment |
| `tests/new-thread/n14_prompt_seam.rs::n14_prompt_seam_contracts_preserve_all_original_cases::the_empty_list_has_its_fixed_digest_on_every_record` | kept | itself | a change that breaks: the empty list has its fixed digest on every record |
| `tests/new-thread/n14_prompt_seam.rs::n14_prompt_seam_contracts_preserve_all_original_cases::the_prompt_schema_allows_attachment_ids_each_once` | merged | `tests/new-thread/contract_tables.rs::contract_tables_contracts_preserve_all_original_cases::the_prompt_contract` | (as its keeper; its rows not already there, `["a/b"]`, `[1]`, an empty text and the serialized text-only payload, were added; the lint is `schema_parity.rs::…::both_contracts_lint_clean`) |
| `tests/new-thread/n14_prompt_seam.rs::n14_prompt_seam_contracts_preserve_all_original_cases::without_an_attachment_store_any_attachment_is_refused_with_zero_calls_and_no_claim` | kept | itself | a change that breaks: without an attachment store any attachment is refused with zero calls and no claim |
| `tests/new-thread/n15_nothing_else_changes.rs::no_read_command_reaches_a_write` | kept | itself | a change that breaks: no read command reaches a write |
| `tests/new-thread/n15_nothing_else_changes.rs::the_server_builds_no_new_thread_call` | kept | itself | a change that breaks: the server builds no new thread call |
| `tests/new-thread/n16_allowlist.rs::n16_allowlist_affected_contracts_preserve_original_cases` | kept | itself | (as its cases) |
| `tests/new-thread/n16_allowlist.rs::n16_allowlist_affected_contracts_preserve_original_cases::a_spawn_can_only_be_built_with_safe_arguments` | kept | itself | a change that breaks: a spawn can only be built with safe arguments |
| `tests/new-thread/n16_allowlist.rs::n16_allowlist_affected_contracts_preserve_original_cases::the_two_additions_in_exactly_their_shapes` | kept | itself | a change that breaks: the two additions in exactly their shapes |
| `tests/new-thread/n16_allowlist.rs::the_fake_refuses_every_other_spawn_and_cloud_shape` | deleted | `tests/new-thread/n01_end_to_end.rs::one_create_makes_one_spawn_in_exactly_the_shape` |  |
| `tests/new-thread/n17_drift.rs::n17_drift_affected_contracts_preserve_original_cases` | kept | itself | (as its cases) |
| `tests/new-thread/n17_drift.rs::n17_drift_affected_contracts_preserve_original_cases::an_unexpected_catalogue_gives_no_options_and_no_call` | kept | itself | a change that breaks: an unexpected catalogue gives no options and no call |
| `tests/new-thread/n17_drift.rs::n17_drift_affected_contracts_preserve_original_cases::an_unexpected_receipt_is_uncertain_with_a_gap` | kept | itself | a change that breaks: an unexpected receipt is uncertain with a gap |
| `tests/new-thread/n17_drift.rs::n17_drift_affected_contracts_preserve_original_cases::an_untested_or_unreadable_version_is_reported_never_a_gate` | kept | itself | a change that breaks: an untested or unreadable version is reported never a gate |
| `tests/new-thread/n17_drift.rs::n17_drift_affected_contracts_preserve_original_cases::the_schema_says_new_has_its_own_tested_version` | deleted | `tests/new-thread/n17_drift.rs::a_new_thread_at_the_reads_tested_version_is_not_live_tested_for_new_threads` |  |
| `tests/new-thread/n17_drift.rs::new_has_its_own_tested_version_never_the_reads` | kept | itself | a change that breaks: new has its own tested version never the reads |
| `tests/new-thread/n17_drift.rs::a_new_thread_at_the_reads_tested_version_is_not_live_tested_for_new_threads` | kept | itself | a change that breaks: a new thread at the reads tested version is not live tested for new threads |
| `tests/new-thread/n18_cli.rs::without_yes_the_effects_and_the_exact_command_are_printed_and_nothing_is_created` | kept | itself | a change that breaks: without yes the effects and the exact command are printed and nothing is created |
| `tests/new-thread/n18_cli.rs::the_json_matches_the_text` | kept | itself | a change that breaks: the json matches the text |
| `tests/new-thread/n18_cli.rs::every_exit_code_is_documented` | kept | itself | a change that breaks: every exit code is documented |
| `tests/new-thread/n18_cli.rs::errors_go_to_stderr_with_stdout_empty_and_read_nothing` | kept | itself | a change that breaks: errors go to stderr with stdout empty and read nothing |
| `tests/new-thread/n18_cli.rs::the_text_is_never_read_from_a_terminal` | kept | itself | a change that breaks: the text is never read from a terminal |
| `tests/new-thread/n18_cli.rs::models_shows_the_options_as_reported_and_no_default` | kept | itself | a change that breaks: models shows the options as reported and no default |
| `tests/new-thread/n18_cli.rs::models_json_keeps_unavailable_harness_with_its_reason_and_explanation` | kept | itself | a change that breaks: models json keeps unavailable harness with its reason and explanation |
| `tests/new-thread/n18_cli.rs::models_json_preserves_each_harness_reported_steer_capability` | kept | itself | a change that breaks: models json preserves each harness reported steer capability |
| `tests/new-thread/n18_cli.rs::models_json_preserves_each_harness_reported_attachment_capabilities` | kept | itself | a change that breaks: models json preserves each harness reported attachment capabilities |
| `tests/new-thread/n18_cli.rs::the_account_never_reaches_any_output` | kept | itself | a change that breaks: the account never reaches any output |
| `tests/new-thread/n18_cli.rs::the_start_is_followed_within_its_bound` | kept | itself | a change that breaks: the start is followed within its bound |
| `tests/new-thread/n18_cli.rs::status_is_read_only_and_exits_as_the_record` | kept | itself | a change that breaks: status is read only and exits as the record |
| `tests/new-thread/n18_cli.rs::the_printed_command_creates_exactly_what_was_previewed` | kept | itself | a change that breaks: the printed command creates exactly what was previewed |
| `tests/new-thread/n18_cli.rs::a_text_changed_on_the_way_is_refused` | kept | itself | a change that breaks: a text changed on the way is refused |
| `tests/new-thread/n18_cli.rs::a_project_name_with_shell_syntax_is_quoted_too` | kept | itself | a change that breaks: a project name with shell syntax is quoted too |
| `tests/new-thread/n18_cli.rs::the_round_trips_fail_without_a_working_zsh` | kept | itself | a change that breaks: the round trips fail without a working zsh |
| `tests/new-thread/n18_cli.rs::models_fixture_process_returns_the_offered_catalogue` | kept | itself | a change that breaks: models fixture process returns the offered catalogue |
| `tests/new-thread/n18_cli.rs::the_zsh_probe_finds_a_missing_or_broken_zsh` | kept | itself | a change that breaks: the zsh probe finds a missing or broken zsh |
| `tests/new-thread/n18_report.rs::n18_report_contracts_preserve_all_original_cases` | kept | itself | (as its cases) |
| `tests/new-thread/n18_report.rs::n18_report_contracts_preserve_all_original_cases::a_preview_shows_the_effects_and_claims_and_calls_nothing` | kept | itself | a change that breaks: a preview shows the effects and claims and calls nothing |
| `tests/new-thread/n18_report.rs::n18_report_contracts_preserve_all_original_cases::create_effects_keep_the_project_read_time` | kept | itself | a change that breaks: create effects keep the project read time |
| `tests/new-thread/n18_report.rs::n18_report_contracts_preserve_all_original_cases::every_outcome_matches_the_schema` | kept | itself | a change that breaks: every outcome matches the schema |
| `tests/new-thread/n18_report.rs::n18_report_contracts_preserve_all_original_cases::preview_effects_keep_the_project_read_time` | kept | itself | a change that breaks: preview effects keep the project read time |
| `tests/new-thread/n18_report.rs::n18_report_contracts_preserve_all_original_cases::the_effects_are_recorded_before_the_call` | kept | itself | a change that breaks: the effects are recorded before the call |
| `tests/new-thread/n18_report.rs::n18_report_contracts_preserve_all_original_cases::the_schema_uses_only_checked_keywords` | kept | itself | a change that breaks: the schema uses only checked keywords |
| `tests/new-thread/n19_status_read_only.rs::n19_status_read_only_contracts_preserve_all_original_cases` | kept | itself | (as its cases) |
| `tests/new-thread/n19_status_read_only.rs::n19_status_read_only_contracts_preserve_all_original_cases::a_created_thread_shows_its_start_apart_from_its_creation` | kept | itself | a change that breaks: a created thread shows its start apart from its creation |
| `tests/new-thread/n19_status_read_only.rs::n19_status_read_only_contracts_preserve_all_original_cases::every_record_state_reads_with_no_spawn_and_no_write` | kept | itself | a change that breaks: every record state reads with no spawn and no write |
| `tests/new-thread/n19_status_read_only.rs::n19_status_read_only_contracts_preserve_all_original_cases::failed_observation_read_is_an_explicit_gap` | kept | itself | a change that breaks: failed observation read is an explicit gap |
| `tests/new-thread/n19_status_read_only.rs::n19_status_read_only_contracts_preserve_all_original_cases::observations_never_settle_an_uncertain_create` | kept | itself | a change that breaks: observations never settle an uncertain create |
| `tests/new-thread/pattern.rs::the_pattern_form_is_checked_and_matched` | kept | itself | a change that breaks: the pattern form is checked and matched |
| `tests/new-thread/project_names.rs::project_names_contracts_preserve_all_original_cases` | moved | `crates/core/tests/new_thread_project_names.rs::project_names_contracts_preserve_all_original_cases` | a name that answers to two projects resolving to one of them, so a create lands in another project |
| `tests/new-thread/project_names.rs::project_names_contracts_preserve_all_original_cases::a_literal_name_that_equals_another_projects_qualified_name_is_ambiguous` | moved | `crates/core/tests/new_thread_project_names.rs::project_names_contracts_preserve_all_original_cases::a_literal_name_that_equals_another_projects_qualified_name_is_ambiguous` | a change that breaks: a literal name that equals another projects qualified name is ambiguous |
| `tests/new-thread/project_names.rs::project_names_contracts_preserve_all_original_cases::a_unique_name_resolves_by_either_form` | moved | `crates/core/tests/new_thread_project_names.rs::project_names_contracts_preserve_all_original_cases::a_unique_name_resolves_by_either_form` | a change that breaks: a unique name resolves by either form |
| `tests/new-thread/project_names.rs::project_names_contracts_preserve_all_original_cases::every_project_is_reachable_by_its_id` | moved | `crates/core/tests/new_thread_project_names.rs::project_names_contracts_preserve_all_original_cases::every_project_is_reachable_by_its_id` | a change that breaks: every project is reachable by its id |
| `tests/new-thread/record_load.rs::binding_reads_are_raw_read_only_and_never_inspect_the_claim_lock` | kept | itself | a change that breaks: binding reads are raw read only and never inspect the claim lock |
| `tests/new-thread/record_load.rs::binding_reads_refuse_malformed_and_foreign_op_records_without_writing` | kept | itself | a change that breaks: binding reads refuse malformed and foreign op records without writing |
| `tests/new-thread/record_store.rs::every_record_the_core_writes_reads_back_the_same` | kept | itself | a change that breaks: every record the core writes reads back the same |
| `tests/new-thread/record_store.rs::the_record_is_owner_only_outside_the_repository_and_beside_the_send_record` | kept | itself | a change that breaks: the record is owner only outside the repository and beside the send record |
| `tests/new-thread/record_store.rs::a_record_that_is_not_exactly_its_shape_is_refused_and_nothing_is_created` | kept | itself | a change that breaks: a record that is not exactly its shape is refused and nothing is created |
| `tests/new-thread/record_store.rs::synthetic_status_refuses_kept_text_with_wrong_hash` | kept | itself | a change that breaks: synthetic status refuses kept text with wrong hash |
| `tests/new-thread/record_store.rs::synthetic_status_refuses_claimed_record_with_created_outcome` | deleted | `tests/new-thread/record_store.rs::synthetic_created_records_require_only_a_finished_phase` |  |
| `tests/new-thread/record_store.rs::synthetic_status_preserves_finished_record_with_created_outcome` | kept | itself | a change that breaks: synthetic status preserves finished record with created outcome |
| `tests/new-thread/record_store.rs::synthetic_created_records_require_only_a_finished_phase` | kept | itself | a change that breaks: synthetic created records require only a finished phase |
| `tests/new-thread/record_store.rs::the_store_claims_once_and_recovers_a_stopped_owner` | kept | itself | a change that breaks: the store claims once and recovers a stopped owner |
| `tests/new-thread/record_store.rs::status_refuses_non_regular_records_without_provider_calls` | kept | itself | a change that breaks: status refuses non regular records without provider calls |
| `tests/new-thread/record_store.rs::status_preserves_missing_malformed_and_valid_regular_record_behavior` | kept | itself | a change that breaks: status preserves missing malformed and valid regular record behavior |
| `tests/new-thread/schema_parity.rs::schema_parity_contracts_preserve_all_original_cases` | kept | itself | (as its cases) |
| `tests/new-thread/schema_parity.rs::schema_parity_contracts_preserve_all_original_cases::attachment_ids_match_rust` | kept | itself | a change that breaks: attachment ids match rust |
| `tests/new-thread/schema_parity.rs::schema_parity_contracts_preserve_all_original_cases::both_contracts_lint_clean` | kept | itself | a change that breaks: both contracts lint clean |
| `tests/new-thread/schema_parity.rs::schema_parity_contracts_preserve_all_original_cases::op_ids_match_rust` | kept | itself | a change that breaks: op ids match rust |
| `tests/new-thread/schema_parity.rs::schema_parity_contracts_preserve_all_original_cases::patterns_under_one_of_are_enforced` | kept | itself | a change that breaks: patterns under one of are enforced |
| `tests/new-thread/schema_parity.rs::schema_parity_contracts_preserve_all_original_cases::project_references_match_rust` | kept | itself | a change that breaks: project references match rust |
| `tests/new-thread/schema_parity.rs::schema_parity_contracts_preserve_all_original_cases::settings_match_rust` | kept | itself | a change that breaks: settings match rust |
| `tests/new-thread/schema_parity.rs::schema_parity_contracts_preserve_all_original_cases::the_prompt_text_matches_rust_in_both_contracts` | kept | itself | a change that breaks: the prompt text matches rust in both contracts |
| `tests/new-thread/schema_parity.rs::schema_parity_contracts_preserve_all_original_cases::the_round_1_counterexamples_are_refused` | kept | itself | a change that breaks: the round 1 counterexamples are refused |
| `tests/new-thread/schema_parity.rs::every_single_character_prompt_matches_rust` | kept | itself | a change that breaks: every single character prompt matches rust |
| `tests/new-thread/structure.rs::only_the_cli_and_the_store_reach_new_threads` | deleted | `tests/new-thread/n15_nothing_else_changes.rs::the_server_builds_no_new_thread_call` (the server names no call builder) and `tests/proof/p08a_allowlist_static.rs::allowlist_argv_contracts_preserve_original_cases` (the allowlist's exact forms) |  |
| `tests/new-thread/structure.rs::no_new_thread_or_prompt_type_has_a_reader` | deleted | `crates/core/src/new_thread/mod.rs::no_readers::no_new_thread_or_prompt_type_has_a_reader` |  |
| `tests/new-thread/structure.rs::the_runner_scrubs_every_call` | deleted | `tests/new-thread/n02_no_rewrite.rs::new_yes_scrubs_thread_context_on_every_call_including_spawn` |  |
| `tests/new-thread/structure.rs::every_serialized_label_is_in_the_schema` | kept | itself | a change that breaks: every serialized label is in the schema |
| `tests/support/schema.rs::tests::shared_text_keywords_are_linted_and_enforced` | kept | itself | the shared schema checker's own proof (compiled into this target from `tests/support/`; TV9's, unchanged here) |
| `tests/support/forks.rs::a_lock_stays_listed_while_a_childs_copy_holds_it` | kept | itself | the shared fork-wait helper's own proof (compiled into this target from `tests/support/`; TV9's, unchanged here) |
