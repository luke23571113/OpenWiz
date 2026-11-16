# TV8 (#810): the attachments group's ledger

Every test of the `attachments` target (`tests/attachments/`, run as `cargo
test -p openwiz-tests --test attachments`) at this pull request's base,
`20a5100`: 67 tests, one row each, in the form of
`tools/test-value/README.md`. Two more rows are sub-proofs a wrapper test
ran (`…_preserve_…_cases`, one `#[test]` that runs several named proofs,
#1259) that this group cut or merged; the wrapper's own row covers the
rest. One more row is a script in the folder that no test or CI job runs.

- **Rows, `#[test]`s only:** 67 at the base: kept 52 (in `tests/attachments/`),
  moved 14 (7 to `openwiz-core`, 7 to `openwiz-store`), deleted 1. After:
  66 tests in three targets (52 + 7 + 7).
- **Sub-proof and file rows:** 1 deleted, 1 merged, and the script
  deleted.
- **Not this group's code:** `forks::…` and `schema::tests::…` are the
  shared `tests/support/` modules' own tests, compiled into this target by
  `#[path]`. Their files are outside this ticket's owned paths, so they stay
  unchanged.
- **Catches** for a kept or moved test is the behaviour it asserts, read
  from its body: a change that breaks it fails the test.
- **Where the kept tests live:** a test moved when it needs one crate alone
  and passes the P8(a) and M12 guards there. The reason a kept test stays in
  `tests/attachments/` is in brackets at the end of its Catches cell: *[CLI]*, it runs `openwiz
  attachment` (`openwiz-cli` over the store and the core); *[child]*, it runs
  this test binary again as a process; *[program]*, it starts another program
  (`mkfifo`, `/bin/df` or the release `openwiz`), which P8(a) refuses under
  `crates/` outside its named sources; *[sources]*, it reads other crates'
  sources; *[schema]*, it needs the shared schema checker in `tests/support/`
  and `serde_json`, which `openwiz-core` doesn't have as a dependency.

| Test | Outcome | Keeper | Catches |
| --- | --- | --- | --- |
| `tests/attachments/ad_static.rs::ad08_the_wording_table_and_no_stronger_claim_anywhere` | kept | itself | an outcome that says more than "handed to CloudRoom", or a failed or uncertain one that claims a hand-over; any source wording a stronger delivery claim [sources] |
| `tests/attachments/ad_static.rs::ad11_one_attachment_args_and_no_other_place_builds_file_or_image` | kept | itself | a second `attachment_args`, or `--file`/`--image` spelled outside its one builder, or a write that doesn't take its tail from it [sources] |
| `tests/attachments/ad_static.rs::ad11_send_and_new_thread_share_the_one_gate` | kept | itself | a second gate, a `ReadyPrompt` built outside the gate, or send/new reaching the claim without passing the gate [sources] |
| `tests/attachments/ad_static.rs::ad_static_affected_contracts_preserve_original_cases` | kept | itself | a wrong attachments digest or empty digest, files not before images in the owner's order, a wrong allowance, an attachment listed twice, a claim rule off retention, a gate that passes some and not all, a messaging schema that takes another attachment shape [schema] |
| `tests/attachments/ap01_kind.rs::ap1_kind_contracts_preserve_all_original_cases` | moved | `crates/core/tests/attachment/ap01_kind.rs::ap1_kind_contracts_preserve_all_original_cases` | a kind taken from the extension, a HEIC/HEIF (any brand position, either box header) not refused, an unclear `ftyp` let through as a file, a mismatched name and type not refused |
| `tests/attachments/ap02_limits.rs::ap02_limits_affected_contracts_preserve_original_cases` | moved | `crates/core/tests/attachment/ap02_limits.rs::ap02_limits_affected_contracts_preserve_original_cases` | a limit other than 10 MiB per image and 25 MiB per file, an image-typed file not given the image limit, a count cap in the model |
| `tests/attachments/ap02_limits.rs::the_extension_table_is_pinned` | moved | `crates/core/tests/attachment/ap02_limits.rs::the_extension_table_is_pinned` | the image-typed extension table drifting from `contracts/attachment-mime-types.v1.md` |
| `tests/attachments/ap02_limits.rs::no_other_size_or_count_constant` | moved | `crates/core/tests/attachment/ap02_limits.rs::no_other_size_or_count_constant` | a new size or count constant in the attachment model, or an attachment cap anywhere else in the core (AP2's static half) |
| `tests/attachments/ap02_limits.rs::two_hundred_small_files_all_become_ready_in_the_store` | kept | itself | a count cap in one `add` [CLI] |
| `tests/attachments/ap02_limits.rs::the_store_and_the_cli_add_no_cap` | kept | itself | a size or count cap declared in the store's or the CLI's attachment module [sources] |
| `tests/attachments/ap03_safe_names.rs::ap3_name_contracts_preserve_all_original_cases` | moved | `crates/core/tests/attachment/ap03_safe_names.rs::ap3_name_contracts_preserve_all_original_cases` | a staged name outside `[A-Za-z0-9._-]`, starting with `-` or `.`, over 179 bytes, not a fixed point of CloudRoom's reduction, or whose stored name overflows the Cloud core's 200 bytes; an invalid name parsed back |
| `tests/attachments/ap03_safe_names.rs::the_display_name_keeps_the_original_as_text` (sub-proof) | deleted | `tests/attachments/ap11_schema.rs::ap11_schema_contracts_preserve_all_original_cases` |  |
| `tests/attachments/ap04_ready.rs::each_step_is_durable_before_the_next_and_ready_comes_last` | moved | `crates/store/tests/attachments/ap04_ready.rs::each_step_is_durable_before_the_next_and_ready_comes_last` | a staging step out of order or not synced before the next, `ready` before the metadata is durable, a sweep during staging deleting the copy being written |
| `tests/attachments/ap04_ready.rs::a_copy_changed_after_ready_is_never_verified` | moved | `crates/store/tests/attachments/ap04_ready.rs::a_copy_changed_after_ready_is_never_verified` | a staged copy with other bytes, another size or a link in its place verified as ready |
| `tests/attachments/ap04_ready.rs::metadata_that_is_not_exactly_the_record_is_never_ready` | moved | `crates/store/tests/attachments/ap04_ready.rs::metadata_that_is_not_exactly_the_record_is_never_ready` | metadata with another id, an extra key, a key twice or another shape read as ready |
| `tests/attachments/ap04_ready.rs::a_source_rewritten_while_it_is_copied_is_never_ready` | moved | `crates/store/tests/attachments/ap04_ready.rs::a_source_rewritten_while_it_is_copied_is_never_ready` | a copy that is part old and part new staged as ready |
| `tests/attachments/ap04_ready.rs::stopped_after_any_step_nothing_usable_is_left_or_a_verified_attachment` | kept | itself | a process stopped after a staging step leaving a usable unverified copy, or an unfinished one the next open doesn't remove [child] |
| `tests/attachments/ap05_originals.rs::every_source_is_unchanged_and_only_read` | kept | itself | `add` changing a source's bytes, size, mtime or mode, writing beside it, or failing on a read-only source [CLI] |
| `tests/attachments/ap05_originals.rs::folders_links_to_folders_and_other_non_files_are_refused` | kept | itself | a folder, a link to one, a dangling link, a FIFO or a missing path staged or misreported [CLI, program: `mkfifo`] |
| `tests/attachments/ap05_originals.rs::a_fifo_swapped_in_after_the_look_is_refused_without_hanging` | kept | itself | staging that blocks on, or stages, a FIFO swapped in after the look [program: `mkfifo`] |
| `tests/attachments/ap05_originals.rs::a_file_swapped_in_after_the_look_is_refused` | moved | `crates/store/tests/attachments/ap05_originals.rs::a_file_swapped_in_after_the_look_is_refused` | a file or link swapped in between the look and the open staged in place of the one looked at |
| `tests/attachments/ap06_streaming.rs::a_file_at_its_limit_is_staged_with_bounded_memory` | kept | itself | staging that holds a whole file in memory [child] |
| `tests/attachments/ap06_streaming.rs::memory_comparison_handles_decreases_and_keeps_the_strict_bound` | kept | itself | AP6's memory comparison failing on a lower later peak, or loosening its strict bound, so AP6 is flaky or vacuous; it tests AP6's own helper, so it stays beside it [child] |
| `tests/attachments/ap07_low_disk.rs::below_the_floor_nothing_is_written` | moved | `crates/store/tests/attachments/ap07_low_disk.rs::below_the_floor_nothing_is_written` | staging that leaves under 1 GiB free, measures the wrong volume, or leaves a partial or a directory when refused |
| `tests/attachments/ap07_low_disk.rs::dfs_output_is_read_only_in_its_posix_form` | moved | `crates/store/tests/attachments/ap07_low_disk.rs::dfs_output_is_read_only_in_its_posix_form` | `df` output read from anything but its exact POSIX form (localized, ambiguous, overflowing, extra fields) |
| `tests/attachments/ap07_low_disk.rs::free_space_that_cant_be_measured_stages_nothing` | kept | itself | a failed free-space measure staging anyway, or the CLI not exiting 10 [CLI] |
| `tests/attachments/ap07_low_disk.rs::the_cli_says_low_disk_and_exits_5` | kept | itself | the CLI not saying low disk or not exiting 5 [CLI] |
| `tests/attachments/ap07_low_disk.rs::the_real_measure_is_bin_df_and_fails_closed` | kept | itself | the real measure not `/bin/df -P -k`, disagreeing with it, or not failing closed [program: `/bin/df`] |
| `tests/attachments/ap08_removal_expiry.rs::a_claim_read_failure_after_an_expired_copy_keeps_it` | kept | itself | a sweep deleting a copy before every claim is read [CLI] |
| `tests/attachments/ap08_removal_expiry.rs::a_claimed_attachment_is_kept_while_its_operation_may_use_it` | kept | itself | removal or expiry of a dispatching or uncertain attachment, or an accepted one kept [CLI] |
| `tests/attachments/ap08_removal_expiry.rs::a_damaged_unclaimed_copy_expires_at_its_time_to_live` | kept | itself | a damaged unclaimed copy expired early, never, or reported twice [CLI] |
| `tests/attachments/ap08_removal_expiry.rs::an_attachment_that_expires_as_rm_runs_is_reported_expired` | kept | itself | `rm` reporting an attachment that expired as it ran as removed [CLI] |
| `tests/attachments/ap08_removal_expiry.rs::an_unclaimed_attachment_expires_at_its_time_to_live` | kept | itself | an unclaimed attachment kept past 24 hours, expired before, or reported twice; a wrong `expires_at` or `age_ms` [CLI] |
| `tests/attachments/ap08_removal_expiry.rs::damaged_accepted_copies_are_released_and_failed_copies_expire` | kept | itself | a damaged accepted copy kept, or a damaged failed one never expired (#762) [CLI] |
| `tests/attachments/ap08_removal_expiry.rs::damaged_copies_are_kept_while_their_operations_may_use_them` | kept | itself | a damaged copy deleted while its operation is dispatching or uncertain [CLI] |
| `tests/attachments/ap08_removal_expiry.rs::damaged_copies_with_unknown_claims_are_kept_under_the_claims_lock` | kept | itself | a copy whose claim can't be read deleted, or a claim read outside the claims lock [CLI] |
| `tests/attachments/ap08_removal_expiry.rs::damaged_copies_with_unreadable_metadata_are_kept` | kept | itself | a copy with malformed, mismatched or unreadable metadata deleted by a sweep [CLI] |
| `tests/attachments/ap08_removal_expiry.rs::dangling_metadata_removal_preserves_claim_guards` | kept | itself | `rm` of a copy with dangling metadata ignoring its claim, or a claim lookup failure [CLI] |
| `tests/attachments/ap08_removal_expiry.rs::every_open_expires_and_add_reports_it` | kept | itself | `add` not expiring, or not reporting, an attachment past its time-to-live [CLI] |
| `tests/attachments/ap08_removal_expiry.rs::list_text_reports_actual_elapsed_age` | kept | itself | `ls` text showing another age than the elapsed one [CLI] |
| `tests/attachments/ap08_removal_expiry.rs::ls_lists_ready_attachments_oldest_first` | kept | itself | `ls` not listing oldest first, by id or directory order (#933) [CLI] |
| `tests/attachments/ap08_removal_expiry.rs::present_unreadable_metadata_is_broken_and_removable` | kept | itself | metadata that is a link or a FIFO read through, waited on, or making the copy unremovable [CLI, program: `mkfifo`] |
| `tests/attachments/ap08_removal_expiry.rs::rm_deletes_the_bytes_and_the_metadata` | kept | itself | `rm` leaving bytes or metadata, touching another attachment, or misreporting a missing id [CLI] |
| `tests/attachments/ap08_removal_expiry.rs::unfinished_copies_go_when_the_store_opens` | kept | itself | an unfinished copy kept or listed after the store opens [CLI] |
| `tests/attachments/ap09_owner_only.rs::ap9_owner_only_contracts_preserve_original_cases` | kept | itself | a directory or file not the owner's only, a state directory open to others or inside a repository accepted, a link in place of `attachments/` written through [CLI] |
| `tests/attachments/ap10_no_dispatch.rs::the_model_has_no_dispatch_path_and_no_io` | kept | itself | the attachment model naming an invocation, a process, a flag or I/O (AP10's static proof; it reads the core's source only, but is AP10's one file with the next row, which reads the store's and the CLI's) [sources] |
| `tests/attachments/ap10_no_dispatch.rs::the_allowlist_names_each_attachment_flag_once_inside_its_one_builder` | deleted | `tests/attachments/ad_static.rs::ad11_one_attachment_args_and_no_other_place_builds_file_or_image` |  |
| `tests/attachments/ap10_no_dispatch.rs::only_the_store_and_the_cli_use_the_model_and_neither_dispatches` | kept | itself | the adapter (outside the allowlist) using the model, or the store or the CLI naming `room-cli`, the adapter, a write or a process [sources] |
| `tests/attachments/ap11_cli.rs::a_usage_error_opens_nothing` | kept | itself | a usage error that opens the store, prints to stdout, or exits other than 2 [CLI] |
| `tests/attachments/ap11_cli.rs::ap11_cli_output_contracts_preserve_original_cases` | kept | itself | an undocumented exit code or usage line, or a failed write or flush of `ls` reported as success [CLI] |
| `tests/attachments/ap11_cli.rs::every_path_is_reported_after_a_store_error` | kept | itself | a store error that hides the paths after it [CLI] |
| `tests/attachments/ap11_cli.rs::every_path_is_reported_in_order_and_one_failure_hides_no_other` | kept | itself | `add` reporting paths out of order, or one failure hiding another [CLI] |
| `tests/attachments/ap11_cli.rs::every_report_matches_the_schema` | kept | itself | an `add`, `ls` or `rm` report off its schema [CLI, schema] |
| `tests/attachments/ap11_cli.rs::list_claim_read_error_after_sweep_is_not_unclaimed` | kept | itself | `ls` showing an attachment as unclaimed when its claim read failed [CLI] |
| `tests/attachments/ap11_cli.rs::options_paths_and_names` | kept | itself | help opening the store, `--` not ending options, a non-UTF-8 name not staged or shown wrong [CLI] |
| `tests/attachments/ap11_cli.rs::removal_json_indexes_match_id_argument_positions` | kept | itself | `rm --json` indexes not matching the ids' positions [CLI] |
| `tests/attachments/ap11_cli.rs::removal_reports_every_id_after_a_store_error` | kept | itself | a store error that hides the ids after it [CLI] |
| `tests/attachments/ap11_cli.rs::the_json_matches_the_text` | kept | itself | the `--json` and text reports saying different things [CLI] |
| `tests/attachments/ap11_schema.rs::ap11_schema_contracts_preserve_all_original_cases` | kept | itself | the schema not describing what the core serializes (references, states, reasons, bounds), unchecked keywords, a loose pattern check, ids or hashes not checked however they arrive [schema] |
| `tests/attachments/ap11_schema.rs::the_checker_rejects_what_the_core_never_writes` (sub-proof) | merged | `tests/attachments/parity.rs::parity_contracts_preserve_all_original_cases` | (as its keeper: its three values parity lacked, an empty name, a short hash and `ready` with a reason, are parity rows now) |
| `tests/attachments/ap12_logs.rs::every_error_path_logs_no_name_content_or_hash` | kept | itself | an error path that logs a file name, content or a hash [CLI] |
| `tests/attachments/ap12_logs.rs::the_scan_finds_names_content_and_hashes` | kept | itself | AP12's log scan missing a name, content or a hash, so every clean-log check in the group is vacuous; it tests the bench's own scan, so it stays beside it [CLI] |
| `tests/attachments/child.rs::child_process` | kept | itself | not a check on its own: the child entry AP4 and AP6 run (it returns at once without its variable) [child] |
| `tests/attachments/parity.rs::parity_contracts_preserve_all_original_cases` | kept | itself | the core reading a shape the schema refuses, or refusing one it allows, a key given twice accepted, the label lists drifting from the schema's enums [schema] |
| `tests/attachments/program.rs::the_release_program_stages_lists_and_removes_and_runs_nothing_else` | kept | itself | the release `openwiz attachment` running another program (a `df` or `room-cli` on `PATH`), a dirty log, or a store not owner-only [program: the release `openwiz`] |
| `tests/attachments/rules.rs::rules_contracts_preserve_all_original_cases` | moved | `crates/core/tests/attachment/rules.rs::rules_contracts_preserve_all_original_cases` | a wrong readiness transition, retention (24 hours, claims, partials), removal while in flight, or a free-disk floor other than 1 GiB |
| `tests/attachments/sha256_stream.rs::sha256_stream_contracts_preserve_original_cases` | moved | `crates/core/tests/attachment/sha256_stream.rs::sha256_stream_contracts_preserve_original_cases` | a streaming SHA-256 that differs from the whole input's, or from FIPS 180-4's examples, at any cut or the padding boundary |
| `tests/support/forks.rs::a_lock_stays_listed_while_a_childs_copy_holds_it` | kept | itself | (the shared `tests/support/forks.rs`'s own test, outside this ticket's paths) |
| `tests/support/schema.rs::tests::shared_text_keywords_are_linted_and_enforced` | kept | itself | (the shared `tests/support/schema.rs`'s own test, outside this ticket's paths) |
| `tests/attachments/check_oldest_first.py` (a script, no test) | deleted | `tests/attachments/ap08_removal_expiry.rs::ls_lists_ready_attachments_oldest_first` |  |

## Notes on the cuts

- **`ap10…the_allowlist_names_each_attachment_flag_once_inside_its_one_builder`:**
  every assertion it makes (each flag once in the allowlist, inside
  `attachment_args`) is one of AD11's, which also checks every other source
  and the one builder. M12's
  `no_product_source_spells_an_excluded_flag_or_another_write` checks the
  same two literals as well.
- **`ap03…the_display_name_keeps_the_original_as_text`:** it needs
  `serde_json`, which `openwiz-core`'s tests can't use. AP11's
  `every_reference_the_core_serializes_matches` serializes hostile display
  names (`../../報告書\u{202e}.txt`, the empty one) and reads them back equal,
  so a serializer that changes the display name fails it.
- **Not cut: `ap03…an_invalid_name_from_a_record_is_refused`'s `serde_json`
  line** (`"../x"` refused as a `SafeName`). Parity doesn't reach
  `SafeName`'s own `Deserialize` (the reference reader parses the name
  itself), so its planted break passed parity. The line moved with ap03,
  now through serde's own string reader, and it fails on that break.
- **`ap11_schema…the_checker_rejects_what_the_core_never_writes`:** its
  mutations are parity's table rows, which check the schema and the core
  together; the three it alone had are parity rows now.
- **`check_oldest_first.py`:** #933's one-off mutation runner for
  `ls_lists_ready_attachments_oldest_first`. No test, CI job or document
  runs it. The test it checked stays, and its two mutants were rerun here
  as keeper checks.

Each cut's keeper was checked by breaking the code it guarded:
[`keepers.txt`](keepers.txt).
