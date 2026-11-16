# TV5 (#807): the web-api group's ledger

Every test of the `web-api` target (`tests/web-api/`, run as `cargo test -p
openwiz-tests --test web-api`) at this pull request's base, `20a5100`: 354
tests, one row each, in the form of `tools/test-value/README.md`. The names
are libtest's (`cargo test -- --list` at the base); five rows are tests of
shared support files the target compiles in (`tests/support/`,
`tests/new-thread/pattern.rs`), which this group leaves unchanged.

- **Rows:** kept 328, deleted 23, merged 1, moved 2. 330 tests stay in
  `web-api`, 2 move to `crates/server/tests/host_names.rs`, 24 go.
- **Catches** for a kept test is the behaviour it asserts, read from its
  body: a change that breaks it fails the test.
- **Keepers checked:** [keepers.txt](keepers.txt) breaks the code each cut
  test guarded and runs only the keeper.

## Where the kept tests live

Two kept tests exercise only `openwiz-server`'s public API and run no
program, so they moved next to it: `only_dns_names_can_be_configured` (A3)
and `a_send_host_can_never_be_loopback_or_an_ip_address` (W3), now
`crates/server/tests/host_names.rs`. They pass both allowlist guards.

Every other kept test stays in `tests/web-api/`, for one of these reasons:

- **It drives the server against a fake source** (every route test: A3 to
  A8, W, U, AW, C3, C10, E11, LP6, ready stock): the fake `room-cli` and fake
  `gh` are `openwiz-tests` binaries, and the tests share `tests/web-api/`'s
  and `tests/messaging/`'s support modules.
- **It compares the server with the CLI** (A6, W5, U5, AW4, C3 semantics):
  it runs `openwiz` from `openwiz-cli` beside the server, two crates.
- **It needs this folder's shared support** (the decisions and plan
  allowlist checks, the web-root checks, the loops read): helpers from
  `e11_*_support.rs`, `a8_web_page.rs`'s tree and `tests/support/dirs.rs`.
  Moving them means moving those helpers too, which the route tests also
  use.
- **It tests shared support** (`tests/support/`, `tests/new-thread/`): those
  files belong to every target that compiles them, not to this group.

| Test | Outcome | Keeper | Catches |
| --- | --- | --- | --- |
| `tests/web-api/main.rs::lp6_get_loops_is_busy_while_a_pass_holds_the_state` | kept | itself | would assert 503 loops_busy + Retry-After: 5 |
| `tests/web-api/a3_loopback.rs::a_foreign_host_gets_no_inventory` | kept | itself | foreign Host on inventory and sessions: 421, no read |
| `tests/web-api/a3_loopback.rs::foreign_host_headers_are_refused` | kept | itself | foreign Host gets 421, malformed Host gets 400, no read |
| `tests/web-api/a3_loopback.rs::only_dns_names_can_be_configured` | moved | `crates/server/tests/host_names.rs::only_dns_names_can_be_configured` | valid_host_name accepts and rejects a list of names |
| `tests/web-api/a3_loopback.rs::the_binary_has_no_way_to_choose_the_bind_address` | kept | itself | bind/host/port/allowed-host misuse exits 2; help text lines 102-110 are wording pins (trim) |
| `tests/web-api/a3_loopback.rs::the_binary_listens_on_loopback_only_and_reads_nothing_at_start` | kept | itself | binary's first line is 127.0.0.1 and no room-cli read at start |
| `tests/web-api/a3_loopback.rs::the_configured_host_name_is_served` | kept | itself | configured name served case-insensitively; `:443` and lookalike names refused |
| `tests/web-api/a3_loopback.rs::the_help_says_health_is_the_servers_own_metadata` | deleted | `tests/web-api/a4_no_mutation.rs::health_reads_nothing` (the behaviour the help sentence describes) |  |
| `tests/web-api/a3_loopback.rs::the_listener_is_bound_to_loopback_only` | kept | itself | bind(0) yields 127.0.0.1 and a non-loopback connect is refused |
| `tests/web-api/a3_loopback.rs::the_source_binds_only_one_loopback_address` | kept | itself | source grep for `TcpListener::bind(` count and wildcard strings |
| `tests/web-api/a4_no_mutation.rs::a_head_request_is_refused_without_a_body` | kept | itself | HEAD on read routes: 405 with no body |
| `tests/web-api/a4_no_mutation.rs::a_head_request_refused_before_its_head_parses_has_no_body` | kept | itself | wrapper: 505, 414, 431, 400, 408, 503, split-method and "HEA" cases, no HEAD body |
| `tests/web-api/a4_no_mutation.rs::an_upgrade_request_is_never_upgraded` | kept | itself | Upgrade headers ignored, 200, close |
| `tests/web-api/a4_no_mutation.rs::every_other_method_is_405_and_reads_nothing` | kept | itself | 15 methods on read routes: 405, Allow GET, no read |
| `tests/web-api/a4_no_mutation.rs::every_other_path_is_404_and_reads_nothing` | kept | itself | 40+ unknown paths: 404 no_route, no read |
| `tests/web-api/a4_no_mutation.rs::health_reads_nothing` | kept | itself | health shape, v127 literal, no room-cli read |
| `tests/web-api/a4_no_mutation.rs::server_dependency_gate_rejects_indirect_normal_clients` | kept | itself | meta: tests the test gate on synthetic metadata |
| `tests/web-api/a4_no_mutation.rs::the_route_table_is_the_read_routes_the_send_and_the_create` | kept | itself | exact GET and POST route lists |
| `tests/web-api/a4_no_mutation.rs::the_server_calls_only_the_cores_list_and_show` | kept | itself | source grep: forbidden tokens, `ops::` scan, web.rs and main.rs text checks; plus a closure test of its own (453-490) |
| `tests/web-api/a4_no_mutation.rs::the_server_dependencies_point_inward_and_only_the_service_embeds_it` | kept | itself | exact normal deps; no edge into service/cli |
| `tests/web-api/a4_no_mutation.rs::the_server_makes_exactly_the_reads_the_cli_makes` | kept | itself | server reads equal the CLI's for 5 routes |
| `tests/web-api/a5_bounds.rs::a_request_past_its_deadline_gets_504_and_the_run_keeps_its_slot` | kept | itself | 504 deadline, run still holds slot |
| `tests/web-api/a5_bounds.rs::a_slow_client_times_out_and_does_not_block_others` | kept | itself | half head and drip: 408 within deadline; others served |
| `tests/web-api/a5_bounds.rs::a_waiting_request_runs_when_a_slot_frees` | kept | itself | queued request runs when slot frees |
| `tests/web-api/a5_bounds.rs::connections_are_capped` | kept | itself | 503 busy at cap, recovery after close |
| `tests/web-api/a5_bounds.rs::core_runs_are_capped_and_the_overflow_gets_503_after_a_bounded_wait` | kept | itself | 3rd run gets 503 after bounded wait |
| `tests/web-api/a5_bounds.rs::health_and_show_take_no_query` | kept | itself | query on health or show: 400 |
| `tests/web-api/a5_bounds.rs::identical_concurrent_requests_share_one_core_run` | kept | itself | 8 identical inventory calls: 1 run, same body, no cache |
| `tests/web-api/a5_bounds.rs::identical_show_requests_share_one_core_run` | kept | itself | 4 identical show calls: 1 run |
| `tests/web-api/a5_bounds.rs::ids_the_adapter_refuses_are_rejected_by_the_core` | kept | itself | 5 bad ids: 400, message, only --version read |
| `tests/web-api/a5_bounds.rs::malformed_and_out_of_range_queries_are_rejected_without_a_read` | kept | itself | 36 malformed query strings: 400, no read |
| `tests/web-api/a5_bounds.rs::malformed_requests_are_rejected` | kept | itself | 20 malformed request lines and heads |
| `tests/web-api/a5_bounds.rs::past_both_connection_caps_a_client_still_gets_a_503` | kept | itself | accept-loop 503 for GET and HEAD, bodyless |
| `tests/web-api/a5_bounds.rs::request_bodies_are_rejected` | kept | itself | 4 framings on inventory: 400; empty body OK |
| `tests/web-api/a5_bounds.rs::targets_and_heads_are_capped` | kept | itself | target, header count and header bytes caps: 414, 431 |
| `tests/web-api/a5_bounds.rs::the_cores_limit_cap_is_applied_without_a_read` | kept | itself | over-cap message from core, boundary queries 200 |
| `tests/web-api/a5_bounds.rs::the_limits_are_the_documented_values` | kept | itself | constants and the deadline > run budget + slot wait invariant |
| `tests/web-api/a6_semantics.rs::a_timeout_one_ms_apart_still_matches` | kept | itself | a 1 ms gap between CLI and server timeouts still matches |
| `tests/web-api/a6_semantics.rs::every_error_drift_and_version_case_matches_the_cli` | kept | itself | error, drift and version scenarios match CLI status and message |
| `tests/web-api/a6_semantics.rs::every_normal_case_matches_the_cli` | kept | itself | every normal inventory and show body equals `openwiz --json` |
| `tests/web-api/a6_semantics.rs::every_timeout_case_matches_the_cli` | kept | itself | real server vs CLI on three timeout scenarios |
| `tests/web-api/a6_semantics.rs::only_the_millisecond_count_is_ignored` | kept | itself | the timeout comparator ignores only the ms count |
| `tests/web-api/a6_semantics.rs::x2_a_fixture_read_cap_reaps_the_hang_and_keeps_later_reads_available` | kept | itself | per-read cap; later reads keep budget; zero cap |
| `tests/web-api/a7_headers_and_logs.rs::errors_from_the_core_have_the_same_headers` | kept | itself | core error bodies carry headers and no paths |
| `tests/web-api/a7_headers_and_logs.rs::every_response_has_the_security_headers_and_no_cors` | kept | itself | security headers and no CORS on 15 routes, incl. 421 |
| `tests/web-api/a7_headers_and_logs.rs::the_binary_logs_no_content_and_its_errors_name_no_path` | kept | itself | built binary with empty PATH: no path in errors, no content in log |
| `tests/web-api/a7_headers_and_logs.rs::the_log_holds_method_route_status_and_time_only` | kept | itself | log lines hold method, route template, status, ms only |
| `tests/web-api/a7_headers_and_logs.rs::the_overload_answers_have_the_same_headers` | kept | itself | 503 and 408 carry headers |
| `tests/web-api/a7_source_diagnostics.rs::a_failed_version_read_never_reaches_a_200_envelope` | kept | itself | failed --version text never in a 200 body or log |
| `tests/web-api/a7_source_diagnostics.rs::every_read_the_server_makes_is_planted` | kept | itself | a new server read without a planted row fails |
| `tests/web-api/a7_source_diagnostics.rs::machine_list_diagnostics_reach_no_response_or_log` | kept | itself | planted `machine list` stderr never reaches a response or the log |
| `tests/web-api/a7_source_diagnostics.rs::project_list_diagnostics_reach_no_response_or_log` | kept | itself | planted `project list` stderr never reaches a response or the log |
| `tests/web-api/a7_source_diagnostics.rs::the_binary_shows_no_diagnostics_in_responses_or_its_log_part_1` | kept | itself | the built binary shows no planted diagnostic in a response or its log (part 1 of 4) |
| `tests/web-api/a7_source_diagnostics.rs::the_binary_shows_no_diagnostics_in_responses_or_its_log_part_2` | kept | itself | the built binary shows no planted diagnostic in a response or its log (part 2 of 4) |
| `tests/web-api/a7_source_diagnostics.rs::the_binary_shows_no_diagnostics_in_responses_or_its_log_part_3` | kept | itself | the built binary shows no planted diagnostic in a response or its log (part 3 of 4) |
| `tests/web-api/a7_source_diagnostics.rs::the_binary_shows_no_diagnostics_in_responses_or_its_log_part_4` | kept | itself | the built binary shows no planted diagnostic in a response or its log (part 4 of 4) |
| `tests/web-api/a7_source_diagnostics.rs::the_binarys_parts_together_are_every_case_once` | kept | itself | the four binary parts partition the cases |
| `tests/web-api/a7_source_diagnostics.rs::thread_list_diagnostics_reach_no_response_or_log` | kept | itself | planted `thread list` stderr never reaches a response or the log |
| `tests/web-api/a7_source_diagnostics.rs::thread_output_diagnostics_reach_no_response_or_log` | kept | itself | planted `thread output` stderr never reaches a response or the log |
| `tests/web-api/a7_source_diagnostics.rs::thread_show_diagnostics_reach_no_response_or_log` | kept | itself | planted `thread show` stderr never reaches a response or the log |
| `tests/web-api/a7_source_diagnostics.rs::unexpected_stdout_reaches_no_response_or_log` | kept | itself | unexpected stdout never shown; CLI parity on those bodies |
| `tests/web-api/a7_source_diagnostics.rs::version_read_diagnostics_reach_no_response_or_log` | kept | itself | planted --version stderr never shown in responses or log |
| `tests/web-api/a8_web_page.rs::w10_the_api_is_unaffected_and_web_paths_obey_host` | kept | itself | API identical with and without web root; API 405 `Allow: GET`; Host 421 on web paths; `allowed_host`; log holds route templates only; `WEB_ROUTES` literal |
| `tests/web-api/a8_web_page.rs::w11_a_file_replaced_by_a_fifo_after_start_is_answered_at_once` | kept | itself | File swapped for a FIFO after start still answers in 5 s with the bytes loaded at start |
| `tests/web-api/a8_web_page.rs::w11_the_root_replaced_changed_or_deleted_after_start_changes_nothing` | kept | itself | Root renamed to symlink, files changed, root deleted: served bytes unchanged |
| `tests/web-api/a8_web_page.rs::w1_without_a_web_root_web_paths_stay_404_and_head_405` | kept | itself | No web root: web paths GET 404 `no_route`, HEAD 405 `Allow: GET` |
| `tests/web-api/a8_web_page.rs::w2_every_trap_in_the_root_stops_the_start` | kept | itself | 30 planted traps each make `WebRoot::open` fail |
| `tests/web-api/a8_web_page.rs::w2_the_binary_checks_the_web_root_before_it_starts` | kept | itself | Binary: bad root exits 1 without echoing path; duplicate/missing value exits 2; `--help`; good root serves `/` |
| `tests/web-api/a8_web_page.rs::w2_the_web_root_is_a_directory_with_a_regular_index` | kept | itself | `WebRoot::open` accepts a dir with index (also via symlink); rejects missing, file, no index, dir or linked index |
| `tests/web-api/a8_web_page.rs::w3_serves_exactly_the_allowlist` | kept | itself | Every served file 200 with exact bytes; ~40 non-allowlisted URLs 404 |
| `tests/web-api/a8_web_page.rs::w4_traversal_and_encodings_are_refused` | kept | itself | ~30 traversal/encoded URLs × 3 suffixes refused; `/fonts/OFL.txt` 200 |
| `tests/web-api/a8_web_page.rs::w5_only_get_and_head_and_no_query_or_body` | kept | itself | Non-GET/HEAD 405 `Allow: GET, HEAD`; HEAD bodiless with page headers; query 400; body 400 |
| `tests/web-api/a8_web_page.rs::w5_unloaded_web_paths_check_route_before_query` | kept | itself | Order Host 421 > method 405 > body 400 on web paths; query 400 and 404 on unloaded paths, GET and HEAD (#800) |
| `tests/web-api/a8_web_page.rs::w6_w7_content_types_and_page_headers` | merged | `tests/web-api/a8_web_page.rs::w5_only_get_and_head_and_no_query_or_body` (the same `assert_page_headers` on every GET of the same tree) | (as its keeper) |
| `tests/web-api/a8_web_page.rs::w7_the_page_csp_is_6s_and_runs_no_inline_script` | kept | itself | CSP directives present, banned tokens absent, only `img-src` has `blob:`, `STATIC_CACHE` literal |
| `tests/web-api/a8_web_page.rs::w8_the_real_export_is_served_byte_for_byte` | kept | itself | Every real-export file served with exact bytes and page headers; `/setup` aliases; `404.html` not served |
| `tests/web-api/a8_web_page.rs::w9_the_checker_finds_inline_script` | kept | itself | Self-test of `inline_problems`: 10 bad snippets flagged, 1 good passes |
| `tests/web-api/a8_web_page.rs::w9_the_real_export_has_no_inline_script` | kept | itself | Every real-export `.html` has no inline script, style, handler or `javascript:` URL |
| `tests/web-api/aw01_routes.rs::every_other_method_on_the_attachment_routes_is_405_and_stages_nothing` | kept | itself | 405 and Allow header per method, nothing staged |
| `tests/web-api/aw01_routes.rs::no_route_returns_an_attachments_bytes` | kept | itself | no answer carries an uploaded file's bytes |
| `tests/web-api/aw01_routes.rs::the_list_and_the_removal_take_no_query_and_the_removal_no_body` | kept | itself | query and body refusals; nothing removed |
| `tests/web-api/aw01_routes.rs::the_route_table_adds_exactly_the_attachment_routes` | deleted | `tests/web-api/a4_no_mutation.rs::the_route_table_is_the_read_routes_the_send_and_the_create` |  |
| `tests/web-api/aw01_routes.rs::without_an_attachment_configuration_the_routes_are_absent_for_every_method` | kept | itself | 404 for every method when disabled |
| `tests/web-api/aw02_owner_and_cross_site.rs::every_cross_site_or_misdirected_removal_is_refused_and_removes_nothing` | kept | itself | same matrix on DELETE; removes nothing |
| `tests/web-api/aw02_owner_and_cross_site.rs::every_cross_site_or_misdirected_upload_is_refused_and_stages_nothing` | kept | itself | Host, Origin, Sec-Fetch-Site, custom header and type refusals on upload; the same matrix on /send is in w3_cross_site, a different route |
| `tests/web-api/aw02_owner_and_cross_site.rs::the_list_follows_the_usual_get_rules_and_never_needs_an_origin` | kept | itself | list 200 on loopback and public host, 421 otherwise |
| `tests/web-api/aw02_owner_and_cross_site.rs::the_server_reads_no_access_header_or_cookie` | kept | itself | source grep, not behaviour |
| `tests/web-api/aw02_owner_and_cross_site.rs::without_an_allowed_host_there_is_no_upload_or_removal` | kept | itself | 421 with no configured host |
| `tests/web-api/aw03_bounds.rs::a_body_at_the_cap_is_staged` | kept | itself | the cap is inclusive: exactly 25 MiB stages |
| `tests/web-api/aw03_bounds.rs::a_body_longer_than_its_length_is_read_only_to_its_length` | kept | itself | bytes past Content-Length are not taken (size 100) |
| `tests/web-api/aw03_bounds.rs::a_body_over_the_cap_is_refused_before_it_is_read` | kept | itself | 413 from the head alone, incl. u64::MAX |
| `tests/web-api/aw03_bounds.rs::a_body_shorter_than_its_length_stages_nothing` | kept | itself | short body refused, never ready |
| `tests/web-api/aw03_bounds.rs::a_body_slower_than_the_deadline_is_refused_and_stages_nothing` | kept | itself | 408 at a 1 s deadline; nothing staged |
| `tests/web-api/aw03_bounds.rs::a_refusal_mid_body_can_still_be_read` | kept | itself | a 3 MiB upload refused for low disk is drained, so the client can still read the refusal |
| `tests/web-api/aw03_bounds.rs::a_third_upload_while_two_run_is_busy_and_stages_nothing` | kept | itself | 503 busy with Retry-After; third leaves no .partial |
| `tests/web-api/aw03_bounds.rs::an_unmeasurable_disk_is_a_store_failure_and_stages_nothing` | kept | itself | 500 store_unavailable, no path in message |
| `tests/web-api/aw03_bounds.rs::huntr_percent_escape_requires_two_hex_digits` | kept | itself | signed, short and invalid percent escapes in the name header are refused |
| `tests/web-api/aw03_bounds.rs::low_disk_fails_with_the_cores_reason_and_stages_nothing` | kept | itself | route maps low disk to failed/low_disk; store-level only at tests/attachments/ap07_low_disk.rs:15 |
| `tests/web-api/aw03_bounds.rs::nothing_of_an_upload_is_logged` | kept | itself | log holds no name, id, hash or body |
| `tests/web-api/aw03_bounds.rs::the_approved_bounds` | kept | itself | B-9 values: 25 MiB, 2 slots, 110 s, 1024-byte name cap |
| `tests/web-api/aw03_bounds.rs::the_framing_is_refused_without_a_length_or_with_two` | kept | itself | 411 with no length; 400 for chunked, duplicate, signed, spaced, empty |
| `tests/web-api/aw03_bounds.rs::the_name_header_is_one_percent_encoded_utf8_name` | kept | itself | 14 bad name forms refused; bound and UTF-8 names accepted |
| `tests/web-api/aw03_streaming.rs::a_copy_finishing_while_another_measures_never_crosses_the_floor` | kept | itself | re-check race, copy finishes; wrapper moving_copy(true) |
| `tests/web-api/aw03_streaming.rs::a_copy_moving_on_while_another_measures_never_crosses_the_floor` | kept | itself | re-check race, copy advances three quarters; wrapper moving_copy(false) |
| `tests/web-api/aw03_streaming.rs::a_name_up_to_the_cap_is_staged_whole` | deleted | `tests/web-api/aw03_bounds.rs::the_name_header_is_one_percent_encoded_utf8_name` (a name at the cap, whole) and `crates/core/tests/attachment/ap03_safe_names.rs::cloudrooms_stored_name_fits_the_cloud_cores_limit` (179) |  |
| `tests/web-api/aw03_streaming.rs::an_upload_streams_into_the_store_and_writes_nothing_beside_it` | kept | itself | no file beside the store during upload; nothing left after cut |
| `tests/web-api/aw03_streaming.rs::the_reports_have_one_implementation_in_the_store` | deleted | `tests/web-api/aw04_same_operation.rs::every_upload_case_equals_attachment_add` |  |
| `tests/web-api/aw03_streaming.rs::two_stagings_at_once_never_go_below_the_floor` | kept | itself | a second staging, and a file staging, are refused while the first copy is taking the disk |
| `tests/web-api/aw04_same_operation.rs::a_create_with_attachments_equals_openwiz_new` | kept | itself | preview and create answers equal `openwiz new` |
| `tests/web-api/aw04_same_operation.rs::a_gate_refusal_equals_openwiz_sends` | kept | itself | refusal equals CLI words; overlaps aw05 first refusal but adds CLI parity |
| `tests/web-api/aw04_same_operation.rs::a_send_with_attachments_equals_openwiz_send` | kept | itself | send with files equals `openwiz send`; replay once |
| `tests/web-api/aw04_same_operation.rs::an_expired_attachment_is_listed_and_swept_as_attachment_ls_does` | kept | itself | expired list parity; expired copy deleted |
| `tests/web-api/aw04_same_operation.rs::every_removal_equals_attachment_rm` | kept | itself | rm answers equal CLI; bad ids refused with CLI words |
| `tests/web-api/aw04_same_operation.rs::every_upload_case_equals_attachment_add` | kept | itself | 25 cases: route answer equals `attachment add --json` |
| `tests/web-api/aw04_same_operation.rs::no_attachment_rule_is_worked_out_in_the_server_or_the_web` | kept | itself | source grep; also tests its own scanner |
| `tests/web-api/aw04_same_operation.rs::the_list_equals_attachment_ls` | kept | itself | list equals `attachment ls --json`; empty list creates no store |
| `tests/web-api/aw04_same_operation.rs::the_web_checks_bytes_only_for_a_safe_preview` | kept | itself | source grep of web source for byte signatures |
| `tests/web-api/aw05_gate.rs::a_forged_create_with_an_attachment_that_is_not_ready_is_refused_with_zero_calls` | kept | itself | create and preview refusals; ready image goes as --image |
| `tests/web-api/aw05_gate.rs::a_forged_send_with_an_attachment_that_is_not_ready_is_refused_with_zero_calls` | kept | itself | wrapper of 8 refusals (missing, uploading, removed, expired, mixed, repeated, steer, bad id); zero tells, no record |
| `tests/web-api/aw05_gate.rs::an_attachment_in_use_by_another_send_is_refused_with_zero_calls` | kept | itself | uncertain claim blocks second send and removal; store-level only at tests/attachments/rules.rs:154 |
| `tests/web-api/aw05_gate.rs::the_send_bodys_attachments_must_be_a_list_of_strings` | kept | itself | bad shapes refused; absent means none |
| `tests/web-api/c10_cockpit_cases.rs::c10_agents_are_only_active_sessions_and_unplaced_ones_stay` | kept | itself | active-only filter; unknown status and failed-detail gaps |
| `tests/web-api/c10_cockpit_cases.rs::c10_ambiguous_repository_lists_each_item_once_unassigned` | kept | itself | two projects: each item once, project unknown |
| `tests/web-api/c10_cockpit_cases.rs::c10_complete_two_projects_fresh_with_nothing_waiting` | kept | itself | complete coverage, names, placements, target, empty Needs you |
| `tests/web-api/c10_cockpit_cases.rs::c10_needs_you_keeps_unsupported_facts_unknown_in_order` | kept | itself | Needs you order; unsupported wording, age, risk unknown |
| `tests/web-api/c10_cockpit_cases.rs::c10_partial_one_project_unreadable_keeps_every_usable_row` | kept | itself | one unreadable project: partial, rows kept |
| `tests/web-api/c10_cockpit_cases.rs::c10_stale_snapshots_stay_stale_after_a_new_assembly` | kept | itself | 80 s assembly → stale; target fresh |
| `tests/web-api/c10_cockpit_cases.rs::c10_target_checked_known_absent_and_unknown_stay_distinct` | kept | itself | six target states kept distinct |
| `tests/web-api/c10_cockpit_cases.rs::c10_truncated_fleet_read_keeps_its_gap` | kept | itself | truncated issue list → truncated gap |
| `tests/web-api/c10_cockpit_cases.rs::c10_unknown_freshness_when_project_discovery_has_no_snapshot` | kept | itself | discovery failure → unknown freshness |
| `tests/web-api/c10_cockpit_cases.rs::c10_without_fleet_sources_nothing_is_claimed_complete` | kept | itself | no fleet sources → partial and unknown |
| `tests/web-api/c10_cockpit_review.rs::c10_r1_an_unrecognized_status_is_partial_never_absent` | kept | itself | unrecognised status string → unsupported gap (distinct from Unknown in cases.rs:369) |
| `tests/web-api/c10_cockpit_review.rs::c10_r2_a_truncated_fleet_keeps_the_other_fleets_items` | kept | itself | truncated spec keeps the other fleet's items |
| `tests/web-api/c10_cockpit_review.rs::c10_r3_a_target_grouped_in_another_project_is_not_this_projects` | kept | itself | target in another project is not this project's |
| `tests/web-api/c10_cockpit_review.rs::c10_r4_a_placement_whose_project_contradicts_the_inventory_is_unknown` | kept | itself | placement contradicting inventory is unknown |
| `tests/web-api/c10_cockpit_review.rs::c10_r5_an_unverified_project_or_machine_is_a_gap` | kept | itself | unverified project or machine is a gap |
| `tests/web-api/c10_cockpit_review.rs::c10_r6_conflicting_project_names_are_unknown` | kept | itself | conflicting names → unknown name |
| `tests/web-api/c10_cockpit_review.rs::c10_r7_a_project_without_a_source_snapshot_is_unknown_freshness` | kept | itself | unsourced project → unknown freshness |
| `tests/web-api/c10_cockpit_review.rs::c10_r9_the_inventory_keeps_the_runs_one_deadline` | kept | itself | one deadline across project and session reads |
| `tests/web-api/c10_cockpit_review.rs::c10_review1_r1_an_ambiguous_placement_is_a_gap` | kept | itself | two threads on one branch: ambiguous gap |
| `tests/web-api/c10_cockpit_review.rs::c10_review1_r1_another_fleets_ambiguity_is_not_hidden_by_a_placement` | kept | itself | cross-fleet ambiguity is not hidden by a known placement |
| `tests/web-api/c10_cockpit_review.rs::c10_review1_r2_a_placed_agents_unknown_state_is_a_gap` | kept | itself | closed ticket without verified merge: unknown state gap |
| `tests/web-api/c10_cockpit_review.rs::c10_review2_r3_a_reordered_inventory_keeps_its_running_agent` | kept | itself | reordered pages keep the running agent; one session-list read per run |
| `tests/web-api/c10_cockpit_review.rs::c10_self2_h1_hidden_archived_and_later_page_agents_are_listed` | kept | itself | hidden, archived and page-2 running agents listed |
| `tests/web-api/c10_cockpit_review.rs::c10_self2_h2_an_unplaced_agent_is_a_gap` | kept | itself | only test asserting the 'not placed' gap |
| `tests/web-api/c10_cockpit_route.rs::c10_a_full_slot_is_503_and_a_late_read_is_504_keeping_its_slot` | kept | itself | 503 busy and 504-keeps-slot on the cockpit route |
| `tests/web-api/c10_cockpit_route.rs::c10_identical_reads_share_one_run_and_a_later_read_reads_anew` | kept | itself | single flight on the cockpit route |
| `tests/web-api/c10_cockpit_route.rs::c10_route_is_one_exact_get_with_the_standard_checks` | kept | itself | cockpit 405/HEAD, 400 query and body, 404, 421, headers, route-only log; sub-proofs at :62–98 and :100–110 are cut |
| `tests/web-api/c10_cockpit_route.rs::c10_the_cockpit_read_writes_nothing` | kept | itself | cockpit reads only thread show/list and gh read verbs |
| `tests/web-api/c3_binary.rs::c3_decisions_unread_settings_root_never_falls_back_to_cwd` | kept | itself | real binary: unread settings root never reads cwd; in-process tests always pass settings |
| `tests/web-api/c3_binary.rs::c3_server_program_matches_the_cli_agent_chain` | kept | itself | real binary: fleet bodies schema-valid and equal `fleet 901 --json` |
| `tests/web-api/c3_bounds.rs::c3_distinct_specs_use_distinct_runs_and_share_the_inventory_cap` | kept | itself | distinct spec runs; fleet reads share the 2-slot cap with inventory (503) |
| `tests/web-api/c3_bounds.rs::c3_each_route_past_the_deadline_keeps_its_shared_slot_until_done` | kept | itself | 504 keeps slot on fleet routes (a5 covers inventory only) |
| `tests/web-api/c3_bounds.rs::c3_each_route_shares_only_its_in_progress_result_then_starts_a_fresh_run` | kept | itself | single flight for both fleet routes |
| `tests/web-api/c3_routes.rs::c3_adds_exactly_two_gets_after_the_existing_routes` | deleted | `tests/web-api/a4_no_mutation.rs::the_route_table_is_the_read_routes_the_send_and_the_create` |  |
| `tests/web-api/c3_routes.rs::c3_rejects_methods_bodies_queries_and_noncanonical_spec_numbers_before_reads` | kept | itself | fleet routes: 405, 400 query/framing, 421 host, 400 spec grammar, 404, no reads |
| `tests/web-api/c3_routes.rs::huntr_malformed_host_refused_as_bad_request` | kept | itself | malformed Host grammar on fleet routes (only test with `[::1]:abc`, `[v1.a]`) |
| `tests/web-api/c3_semantics.rs::c3_detail_complete_partial_unreadable_and_boundary_specs_equal_the_cli` | kept | itself | detail bytes equal CLI on 200 and 502 cases |
| `tests/web-api/c3_semantics.rs::c3_detail_read_failure_cleans_controls_exactly_like_the_cli` | kept | itself | control characters stripped from detail error; no other control-cleaning test |
| `tests/web-api/c3_semantics.rs::c3_every_list_fixture_is_byte_for_byte_the_cli_json` | kept | itself | fleet list bytes equal CLI on every fixture |
| `tests/web-api/c3_semantics.rs::c3_planted_github_diagnostics_do_not_escape_in_partial_results_or_errors` | kept | itself | gh stderr never escapes fleet reads (a7 covers inventory/session only) |
| `tests/web-api/c3_semantics.rs::c3_r1_refusal_logs_accept_completion_order_and_keep_exact_validation` | kept | itself | self-test of `assert_refusal_logs` on a synthetic log; no product path |
| `tests/web-api/c3_semantics.rs::c3_r2_hang_must_still_contain_an_actual_timeout_measurement` | kept | itself | self-test that the hang guard panics |
| `tests/web-api/c3_semantics.rs::c3_r2_only_hang_elapsed_digits_are_normalized` | kept | itself | self-test of `list_comparison_body` normaliser |
| `tests/web-api/c3_semantics.rs::c3_refusals_read_neither_source_and_logs_expose_only_route_templates` | kept | itself | fleet log shows route templates only; read check overlaps c3_routes |
| `tests/web-api/contract.rs::general_methods_document_both_loop_switches_as_post_only` | deleted | `tests/web-api/contract.rs::the_contract_documents_what_the_tests_check`; the behaviour: `tests/loops/l6_api.rs::api_rejects_unapproved_shapes_identity_claims_and_origins_before_writing` |  |
| `tests/web-api/contract.rs::general_outcomes_documents_the_fleet_detail_cleaning_exception` | deleted | `tests/web-api/c3_semantics.rs::c3_detail_read_failure_cleans_controls_exactly_like_the_cli` |  |
| `tests/web-api/contract.rs::general_protocol_accounts_for_the_two_loop_switch_posts` | deleted | `tests/web-api/contract.rs::the_contract_documents_what_the_tests_check` (both loop switches are `ROUTES` rows it requires in the contract); the POST-only behaviour: `tests/loops/l6_api.rs::api_rejects_unapproved_shapes_identity_claims_and_origins_before_writing` |  |
| `tests/web-api/contract.rs::general_routes_loop_switch_wiring_is_current` | deleted | `tests/web-api/contract.rs::the_contract_documents_what_the_tests_check` |  |
| `tests/web-api/contract.rs::general_routes_table_documents_both_fleet_reads` | deleted | `tests/web-api/contract.rs::the_contract_documents_what_the_tests_check` (both fleet routes); the CLI equality: `tests/web-api/c3_semantics.rs::c3_every_list_fixture_is_byte_for_byte_the_cli_json` |  |
| `tests/web-api/contract.rs::general_write_scope_documents_local_loop_switches` | deleted | `tests/web-api/contract.rs::the_contract_documents_what_the_tests_check`; the routes themselves: `tests/web-api/a4_no_mutation.rs::the_route_table_is_the_read_routes_the_send_and_the_create` |  |
| `tests/web-api/contract.rs::the_contract_documents_what_the_tests_check` | kept | itself | ~150 literal strings (routes, params, statuses, headers, limits, schema ids) must appear in the doc |
| `tests/web-api/contract.rs::the_contract_has_no_untested_version_outcome` | deleted | behaviour gone: the web API's `untested_version` status and exit removed by #37 |  |
| `tests/web-api/e11_decisions_bounds.rs::e11_decisions_freshness_uses_oldest_source_time_and_a_controlled_clock` | kept | itself | 70,000 ms fresh, 70,001 stale, future snapshot unknown |
| `tests/web-api/e11_decisions_bounds.rs::e11_decisions_shares_only_inflight_reads_and_retains_a_timed_out_runs_slot` | kept | itself | 2 callers share one held read; 504; 503 busy; slot kept |
| `tests/web-api/e11_decisions_guards.rs::e11_decisions_allowlist_accepts_only_the_exact_read_forms` | kept | itself | decisions::allows accepts 5 read argv forms, rejects write flags |
| `tests/web-api/e11_decisions_guards.rs::e11_decisions_grill_reads_allow_only_pinned_scoped_sources` | kept | itself | only pinned head/blob reads allowed |
| `tests/web-api/e11_decisions_guards.rs::e11_decisions_refuses_methods_queries_bodies_and_foreign_hosts_before_reads` | kept | itself | 405/400/framing 400/421 on decisions; log has no request content |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_all_variants_and_partial_answer_progress_are_preserved` | kept | itself | 4 kinds returned; partial answers kept |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_candidate_and_record_refusals_are_explicit_gaps` | kept | itself | 20 bad fence/record shapes → one malformed gap |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_changed_or_unread_risk_never_becomes_current` | kept | itself | 13 risk-line variants never known true |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_duplicate_request_ids_never_select_a_winner` | kept | itself | same request id twice → no winner |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_exact_lookup_is_qualified_by_the_bound_repository` | kept | itself | per-repo Current/Unread/Changed |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_exact_lookup_never_substitutes_another_binding` | kept | itself | changed repo/subject/id/fingerprint never substitute |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_exact_lookup_retains_lifecycle_and_verified_repository` | kept | itself | lookup: open→Unread, resolved/superseded→Resolved |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_exact_lookup_reuses_the_saved_grill_verifier` | kept | itself | lookup Current/Changed/Unread |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_failed_saved_source_reads_have_sanitized_gaps` | kept | itself | head/blob exit 7 → command_failed, no stderr leak |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_invalid_proposal_fingerprint_is_omitted_as_malformed` | kept | itself | open record with bad fingerprint omitted, malformed |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_invalid_proposal_fingerprint_is_reported_before_closed_filtering` | kept | itself | resolved/superseded bad fingerprint still reported |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_latest_saved_summary_is_compared_exactly` | kept | itself | 8 summary and reopen cases: only the latest saved summary, compared exactly, is current |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_matching_saved_words_without_risk_remain_unknown` | kept | itself | saved source without Risk line → unknown |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_matching_self_hash_does_not_verify_independent_saved_wording` | deleted | `tests/web-api/e11_decisions_records.rs::e11_decisions_numeric_repository_links_preserve_pending_comments` (the same record and fingerprint: `current` unknown, the same gap) |  |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_non_ascii_timestamp_is_reported_without_panicking` | kept | itself | claims a non-ASCII timestamp can't panic |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_numeric_links_keep_url_query_relation_and_count_guards` | kept | itself | ~30 bad Link headers malformed; good one complete |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_numeric_repository_links_preserve_pending_comments` | kept | itself | numeric repositories/9001 feed still yields the request end to end |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_open_returned_answered_omitted_malformed_reported` | kept | itself | mixed feed: 1 item, exact gh call sequence |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_paginates_the_entire_feed_and_retains_rows_after_a_page_failure` | kept | itself | 101 rows read both pages; page-2 failure keeps page-1 row |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_saved_grill_uses_the_configured_private_repository` | kept | itself | grill verified only from configured private repo |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_saved_risk_matches_all_explicit_classes` | kept | itself | ordinary/live/release/publish → known true |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_saved_wording_changes_are_known_false` | kept | itself | 4 saved-wording edits → known false |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_schema_and_route_agree_on_parsed_shape_cases` | kept | itself | schema validator and route agree on 9 shapes |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_unverified_pr_heads_and_blobs_stay_unknown` | kept | itself | 13 bad head/blob shapes → unknown, malformed, no leak |
| `tests/web-api/e11_decisions_records.rs::e11_decisions_wrong_subject_is_reported_in_every_lifecycle_state` | kept | itself | issue subject → malformed for 3 statuses |
| `tests/web-api/e11_decisions_records.rs::e11_explicit_repository_pair_keeps_both_local_identities_and_partial_failures` | kept | itself | 8 settings, visibility, identity, role modes |
| `tests/web-api/e11_decisions_review.rs::r1_null_subject_descriptions_retain_valid_requests` | kept | itself | null subject body keeps PR and spec requests |
| `tests/web-api/e11_decisions_review.rs::r1_subject_description_types_remain_strict` | kept | itself | false/7/[]/object body → malformed |
| `tests/web-api/e11_decisions_review.rs::r2_quoted_prose_does_not_invalidate_the_fenced_request` | kept | itself | stray quotes/escapes around a fence keep the request |
| `tests/web-api/e11_decisions_review.rs::r3_changed_contents_prevent_confident_empty_discovery` | kept | itself | edited content never gives confident empty |
| `tests/web-api/e11_decisions_review.rs::r3_deadline_exhaustion_retains_verified_first_scan_requests` | kept | itself | deadline in verification keeps verified request, timed_out gap |
| `tests/web-api/e11_decisions_review.rs::r3_duplicate_comment_id_within_one_scan_remains_ambiguous` | kept | itself | same comment id twice → ambiguous |
| `tests/web-api/e11_decisions_review.rs::r3_equal_count_page_shift_retains_pending_records_and_reports_incomplete_discovery` | kept | itself | equal-count page shift keeps pending, partial |
| `tests/web-api/e11_decisions_review.rs::r3_fork_load_child` | kept | itself | child body of the above |
| `tests/web-api/e11_decisions_review.rs::r3_partial_scans_retain_identical_and_newly_observed_requests` | kept | itself | pending and non-pending variants |
| `tests/web-api/e11_decisions_review.rs::r3_scripted_fakes_start_while_other_threads_fork_slow_children` | kept | itself | runs child binary: 200 scripted fake starts under fork load (#1488) |
| `tests/web-api/e11_decisions_review.rs::r3_unfinished_verification_retains_usable_first_scan_records` | kept | itself | verification exit 7 keeps first-scan request |
| `tests/web-api/e11_decisions_review.rs::r4_positively_unrelated_prose_and_fences_never_add_a_gap` | kept | itself | 5 prose/fence variants add no gap |
| `tests/web-api/e11_decisions_review.rs::r5_mid_feed_deadline_retains_the_newest_verified_request` | kept | itself | mid-feed deadline keeps newest; no asc read |
| `tests/web-api/e11_decisions_routes.rs::e11_decisions_appends_exactly_one_get` | deleted | `tests/web-api/a4_no_mutation.rs::the_route_table_is_the_read_routes_the_send_and_the_create` |  |
| `tests/web-api/e11_decisions_routes.rs::e11_decisions_configured_target_is_verified_by_read_only` | kept | itself | known target; one show; no tell/spawn |
| `tests/web-api/e11_decisions_routes.rs::e11_decisions_invalid_configured_target_never_reaches_the_provider` | kept | itself | 5 invalid target ids → zero messenger calls |
| `tests/web-api/e11_decisions_routes.rs::e11_decisions_target_failure_keeps_its_kind_and_never_leaks_diagnostics` | kept | itself | target show exit 1 → unknown, command_failed, no leak |
| `tests/web-api/e11_decisions_routes.rs::e11_decisions_unconfigured_read_is_an_honest_partial_envelope` | kept | itself | no config → 200 partial, no-store, no provider call |
| `tests/web-api/e11_plan_bounds.rs::e11_gated_wrapper_starts_after_an_unrelated_fork` | kept | itself | reruns deadline case in a child under an LD_PRELOAD fd shim |
| `tests/web-api/e11_plan_bounds.rs::e11_plan_deadline_retains_its_slot_until_the_source_really_finishes` | kept | itself | 504 on deadline; slot held until source ends |
| `tests/web-api/e11_plan_bounds.rs::e11_plan_exact_get_has_all_existing_guards_and_private_route_logs` | kept | itself | plan GET: 405/400/framing/421 refusals, no gh call, 404 paths, log without secret |
| `tests/web-api/e11_plan_bounds.rs::e11_plan_log_status_multiset_rejects_noncanonical_fields_and_wrong_counts` | kept | itself | tests helper assert_status_multiset |
| `tests/web-api/e11_plan_bounds.rs::e11_plan_shares_inflight_only_and_competes_with_inventory_for_two_slots` | kept | itself | shared run; inventory+plan share 2 slots; 3rd gets 503 Retry-After 5 |
| `tests/web-api/e11_plan_bounds.rs::e11_the_route_log_check_takes_the_lines_in_any_order` | kept | itself | tests helper assert_route_log only |
| `tests/web-api/e11_plan_graph.rs::e11_plan_chain_counts_distinct_diamond_reach_and_uses_all_numeric_ties` | kept | itself | 4 literal graphs: diamond reach, length tie, root tie, single |
| `tests/web-api/e11_plan_graph.rs::e11_plan_cycles_and_missing_nodes_keep_rows_but_no_global_maximum` | kept | itself | cycle and missing blocker: rows kept, partial, chain unknown |
| `tests/web-api/e11_plan_graph.rs::e11_plan_empty_and_finished_plans_have_a_known_null_chain` | kept | itself | empty version; finished plans: null or known chain |
| `tests/web-api/e11_plan_partial.rs::e11_plan_bad_page_metadata_preserves_usable_nodes` | kept | itself | pageInfo or totalCount removed: partial, row 902 kept |
| `tests/web-api/e11_plan_partial.rs::e11_plan_complete_several_prs_preserves_fleet_held_and_blocker_semantics` | kept | itself | two OPEN PRs: held, needs_you, unknown PR, blocked child |
| `tests/web-api/e11_plan_partial.rs::e11_plan_milestones_with_unread_titles_remain_as_unknown_lanes` | kept | itself | milestone without title: unknown lane title, other lane kept |
| `tests/web-api/e11_plan_partial.rs::e11_plan_partial_graphql_issue_keeps_its_readable_facts` | kept | itself | direct issue error (exit 0) keeps title/labels, no secret |
| `tests/web-api/e11_plan_partial.rs::e11_plan_positive_parent_link_is_known_despite_a_partial_child_listing` | kept | itself | reciprocal present, partial listing: parent 901 known |
| `tests/web-api/e11_plan_partial.rs::e11_plan_state_requires_a_complete_identified_issue_read` | kept | itself | null title, foreign url, bad milestone: state unknown, partial |
| `tests/web-api/e11_plan_reads.rs::e11_plan_allowlist_refuses_mutations_extra_flags_and_noncanonical_parameters` | kept | itself | plan argvs accepted; mutation, owner, method, cursor refused |
| `tests/web-api/e11_plan_reads.rs::e11_plan_failed_later_page_preserves_read_rows_and_unknown_inverse` | kept | itself | unlocated page-2 failure: page-1 rows kept, dependents unknown |
| `tests/web-api/e11_plan_reads.rs::e11_plan_freshness_ages_the_oldest_read_and_does_not_hide_partial_coverage` | kept | itself | 70000 ms boundary, skew, missing clock; partial not hidden |
| `tests/web-api/e11_plan_reads.rs::e11_plan_malformed_pages_totals_links_and_fields_are_never_complete` | kept | itself | 12 malformed inputs: partial, chain unknown |
| `tests/web-api/e11_plan_reads.rs::e11_plan_pages_repository_and_nested_relations_without_skipping_first_pages` | kept | itself | paging of issues, milestones, subIssues, PRs, labels, blockers |
| `tests/web-api/e11_plan_review.rs::e11_plan_review_r1_errored_list_elements_keep_usable_rows_and_unknown_edges` | kept | itself | null blocker node: row 907 kept, edges unknown |
| `tests/web-api/e11_plan_review.rs::e11_plan_review_r1_graphql_error_exits_retain_first_later_and_direct_rows` | kept | itself | located errors on first, later, direct reads keep rows |
| `tests/web-api/e11_plan_review.rs::e11_plan_review_r1_nullable_error_paths_do_not_become_known_absence` | kept | itself | 9 error-path cases: unknown, not known absence |
| `tests/web-api/e11_plan_review.rs::e11_plan_review_r1_overlapping_paths_keep_independent_fields_known` | kept | itself | two errors on one path: labels, parent known; state unknown |
| `tests/web-api/e11_plan_review.rs::e11_plan_review_r1_unlocated_error_exit_preserves_positive_rows_without_guessing_absences` | kept | itself | exit 1, no path: positives kept, fields unknown |
| `tests/web-api/e11_plan_review.rs::e11_plan_review_r1_unusable_error_stdout_never_becomes_a_complete_empty_plan` | kept | itself | 4 unusable stdouts: partial, empty, chain unknown |
| `tests/web-api/e11_plan_review.rs::e11_plan_review_r2_multiple_merged_prs_leave_merge_and_chain_unknown` | kept | itself | two MERGED PRs: pr, state, column unknown |
| `tests/web-api/e11_plan_review.rs::e11_plan_review_r3_partial_reciprocal_absence_preserves_the_native_parent` | kept | itself | 3 partial-listing cases: parent kept or unknown |
| `tests/web-api/e11_plan_review.rs::e11_plan_review_r4_validates_the_entire_path_before_a_bubbled_null` | kept | itself | 9 error-path suffixes x exit 0/1 |
| `tests/web-api/e11_plan_routes.rs::e11_plan_conflicting_parent_reads_are_unknown_not_a_guessed_lane` | kept | itself | native parent 905 vs spec 901: spec and lane unknown |
| `tests/web-api/e11_plan_routes.rs::e11_plan_incomplete_state_reads_cannot_advertise_a_global_chain` | kept | itself | a duplicate label leaves labels and state unknown and the chain unknown |
| `tests/web-api/e11_plan_routes.rs::e11_plan_missing_parent_field_preserves_other_usable_ticket_facts` | kept | itself | missing parent: spec unknown, title and labels kept |
| `tests/web-api/e11_plan_routes.rs::e11_plan_reads_closed_specs_empty_versions_side_specs_and_recursive_prerequisites` | kept | itself | full universe: lanes, tickets, chain, column |
| `tests/web-api/e11_plan_routes.rs::e11_plan_registers_exact_read_route` | deleted | `tests/web-api/a4_no_mutation.rs::the_route_table_is_the_read_routes_the_send_and_the_create` |  |
| `tests/web-api/e11_plan_routes.rs::e11_plan_retains_side_specs_when_no_child_row_is_usable` | kept | itself | child number 0: side_spec lane kept |
| `tests/web-api/e11_plan_states.rs::e11_plan_every_required_pr_read_is_fail_closed_even_for_a_held_ticket` | kept | itself | six PR read failures: unknown state, no secret |
| `tests/web-api/e11_plan_states.rs::e11_plan_preserves_every_fleet_state_and_ordered_column` | kept | itself | 16-row state/column/yours table, chain, 28 GitHub calls |
| `tests/support/forks.rs::a_lock_stays_listed_while_a_childs_copy_holds_it` | kept | itself | the fork-wait helper's own proof: a lock stays listed while a child's copy holds it |
| `tests/web-api/http.rs::a_read_interrupted_after_the_first_bytes_keeps_the_whole_response` | kept | itself | same, after first bytes |
| `tests/web-api/http.rs::a_read_interrupted_before_the_first_byte_is_tried_again` | kept | itself | EINTR retry in the test client's read_response |
| `tests/web-api/lp6_loops_read.rs::lp6_read_is_busy_while_a_pass_holds_the_state` | kept | itself | held state → Busy after simulated 5 s; readable after drop |
| `tests/web-api/lp6_loops_read.rs::lp6_read_lists_the_default_branch_definitions` | kept | itself | checkout definition → name, enabled, cost 0, problem null |
| `tests/web-api/lp6_loops_read.rs::lp6_read_never_creates_state` | kept | itself | no pass → "not run a pass yet"; no service/loops dir created |
| `tests/web-api/lp6_loops_read.rs::lp6_read_refuses_a_checkout_off_its_clean_default_branch` | kept | itself | dirty definition file → unavailable |
| `tests/web-api/lp6_loops_read.rs::lp6_read_refuses_a_run_admitted_before_it_was_due` | kept | itself | scheduled run started before due → unavailable |
| `tests/web-api/lp6_loops_read.rs::lp6_read_refuses_a_run_updated_before_it_started` | kept | itself | run with updated < started → unavailable |
| `tests/web-api/lp6_loops_read.rs::lp6_read_refuses_without_trusted_context_or_identity` | kept | itself | read() refused with no trust, verify=false, wrong project |
| `tests/web-api/lp6_loops_route.rs::lp6_get_loops_is_get_only_and_takes_no_query` | kept | itself | ?all=1 → 400; POST/PUT/DELETE → 405 Allow: GET; trailing slash → 404 |
| `tests/web-api/lp6_loops_route.rs::lp6_get_loops_refuses_without_context_or_state_never_an_empty_list` | kept | itself | no switching → 503 loops_unavailable; no pass → same, no state created |
| `tests/web-api/lp6_loops_route.rs::lp6_get_loops_serves_the_view_from_the_trusted_context` | kept | itself | HTTP 200, JSON, schema, read_at_ms, cost window, one loop id |
| `tests/new-thread/pattern.rs::the_pattern_form_is_checked_and_matched` | kept | itself | the shared schema pattern checker accepts only its supported form and matches it |
| `tests/web-api/ready_stock.rs::installed_facts::ready_stock_installed_source_failure_retains_original_last_good` | kept | itself | partial issue read keeps last_good ready=2 and running=2 |
| `tests/web-api/ready_stock.rs::installed_facts::ready_stock_installed_source_state_matrix_and_standalone_approval_universe` | kept | itself | join-level states; closed-history R2 (:858); "#9020" title boundary |
| `tests/web-api/ready_stock.rs::installed_facts::ready_stock_installed_sources_never_invent_empty_or_fed_from_gaps` | kept | itself | 13 incomplete-source cases never yield complete totals |
| `tests/web-api/ready_stock.rs::installed_facts::ready_stock_installed_sources_use_title_comments_native_merge_and_optional_capacity` | kept | itself | positive installed join: exact totals object, one enumeration, one PR list, one merge check |
| `tests/web-api/ready_stock.rs::installed_facts::ready_stock_review_partial_discovery_cannot_erase_last_good` | kept | itself | partial discovery keeps identities; complete empty discovery retires them; rediscovery has no last_good |
| `tests/web-api/ready_stock.rs::ready_stock_injected_source_to_cockpit_count_matrix` | kept | itself | 5-row state matrix with full totals object, calls==1, log lines |
| `tests/web-api/ready_stock.rs::ready_stock_missing_sources_are_visible_and_totals_are_unknown` | kept | itself | real route, missing stock sources → coverage partial, totals unknown, 2 projects |
| `tests/web-api/ready_stock.rs::ready_stock_partial_stale_future_missing_and_last_good_keep_original_evidence` | kept | itself | per kind: totals unknown, last_good kept, stale/future freshness |
| `tests/web-api/ready_stock.rs::ready_stock_review_assembly_time_follows_the_provider_read` | kept | itself | snapshot_at taken after provider read → project fresh, stock stale |
| `tests/web-api/ready_stock.rs::ready_stock_review_opaque_project_ids_preserve_cockpit_without_partial_extension` | kept | itself | "zz.synthetic" → cockpit keeps it, ready_stock absent |
| `tests/web-api/ready_stock.rs::ready_stock_review_partial_fleet_discovery_prevents_known_totals` | kept | itself | partial fleet discovery → top-level coverage partial, totals unknown |
| `tests/web-api/ready_stock.rs::ready_stock_review_stale_or_future_discovery_cannot_retire_a_project` | kept | itself | missing project stays visible with last_good under stale/future discovery |
| `tests/support/real_time.rs::a_scaled_duration_covers_the_measured_read_within_its_cap` | kept | itself | the real-time helper scales a duration over the measured read, within its cap |
| `tests/support/real_time.rs::only_a_first_attempt_pull_request_to_main_gets_the_fast_form` | kept | itself | the real-time helper gives the fast form only to a first-attempt pull request to main |
| `tests/support/schema.rs::tests::shared_text_keywords_are_linted_and_enforced` | kept | itself | the shared schema checker enforces every text keyword it accepts |
| `tests/web-api/u01_new_routes.rs::every_other_method_on_the_post_routes_is_405_and_creates_nothing` | kept | itself | non-POST methods on create and preview: 405, Allow POST, no call, no record |
| `tests/web-api/u01_new_routes.rs::get_on_the_reads_never_creates` | kept | itself | GET on both reads 200; preview writes nothing; one create after |
| `tests/web-api/u01_new_routes.rs::post_on_the_read_routes_is_405_and_reads_nothing` | kept | itself | POST/PUT/DELETE/PATCH/OPTIONS on cloud-options and status: 405, Allow GET, no read |
| `tests/web-api/u01_new_routes.rs::the_route_table_adds_exactly_the_new_thread_routes` | deleted | `tests/web-api/a4_no_mutation.rs::the_route_table_is_the_read_routes_the_send_and_the_create` |  |
| `tests/web-api/u01_new_routes.rs::there_is_no_retry_route_for_any_method` | kept | itself | retry-shaped paths: POST/PUT 405, GET 404, no second create |
| `tests/web-api/u01_new_routes.rs::without_a_new_thread_configuration_the_routes_are_absent_for_every_method` | kept | itself | creating=None: all four routes 404, no Allow |
| `tests/web-api/u02_u03_owner_and_cross_site.rs::u2_no_answer_depends_on_access_headers_or_cookies` | kept | itself | forged Access JWT, email and cookies change no create/preview answer |
| `tests/web-api/u02_u03_owner_and_cross_site.rs::u3_a_same_origin_create_goes_through_once` | kept | itself | good create is 200 `created`; charset variant replays |
| `tests/web-api/u02_u03_owner_and_cross_site.rs::u3_cross_site_and_misdirected_creates_and_previews_are_refused_with_zero_calls` | kept | itself | 19 cross-site, Origin, Host, media-type and header refusals with kind, no call, no record |
| `tests/web-api/u02_u03_owner_and_cross_site.rs::u3_without_a_public_host_name_nothing_is_created` | kept | itself | no host name: 421 on both routes, no call |
| `tests/web-api/u04_bounds.rs::a_create_at_the_cap_of_the_body_is_read` | kept | itself | escaped 16 KiB text at the cap: 200 |
| `tests/web-api/u04_bounds.rs::malformed_bodies_are_refused_before_any_read` | kept | itself | 19 malformed create/preview shapes: 400 invalid_request, no call |
| `tests/web-api/u04_bounds.rs::nothing_of_a_create_is_logged` | kept | itself | log lines for four new routes; no text, op id, project, model, effort |
| `tests/web-api/u04_bounds.rs::one_create_at_a_time` | kept | itself | second create during a held first: 503 busy, Retry-After 5, no claim |
| `tests/web-api/u04_bounds.rs::the_cores_rules_refuse_a_bad_op_id_text_or_setting_before_any_read` | kept | itself | bad op id, text or setting: 400 on both routes |
| `tests/web-api/u04_bounds.rs::the_create_limits_are_the_documented_values` | deleted | `tests/web-api/u04_bounds.rs::one_create_at_a_time` (default limits) and `tests/web-api/w4_bounds.rs::the_send_bounds_are_the_documented_values` (99 328) |  |
| `tests/web-api/u04_bounds.rs::the_framing_is_bounded` | kept | itself | 411, Transfer-Encoding 400, 413, 408, query 400, extra-segment POST 405 |
| `tests/web-api/u05_same_operation.rs::a_refused_request_carries_the_cores_words` | kept | itself | CLI exit 2 and stderr message equal the route's 400 text |
| `tests/web-api/u05_same_operation.rs::a_status_with_no_record_is_the_clis` | kept | itself | unknown op: CLI exit 11 JSON equals route 200 JSON; no read |
| `tests/web-api/u05_same_operation.rs::every_catalogue_is_the_clis_models` | kept | itself | OPTIONS equals `models --json` for seven fixtures and the failed read |
| `tests/web-api/u05_same_operation.rs::every_create_preview_and_status_is_the_clis_json` | kept | itself | per fixture case: preview, create, replay, status, reuse equal the CLI JSON and exit mapping |
| `tests/web-api/u05_same_operation.rs::the_server_has_no_new_thread_logic_of_its_own` | deleted | `tests/web-api/u05_same_operation.rs::every_create_preview_and_status_is_the_clis_json` |  |
| `tests/web-api/u06_u12_never_coalesced.rs::u12_repeats_and_client_retries_are_one_call` | kept | itself | four sequential repeats replay; five at once: one call |
| `tests/web-api/u06_u12_never_coalesced.rs::u6_a_conflicting_reuse_is_refused_with_no_call` | kept | itself | changed text, model, effort, harness or project: conflicting_reuse, differs, no call |
| `tests/web-api/u06_u12_never_coalesced.rs::u6_identical_creates_at_once_are_never_shared` | kept | itself | two identical bodies at once: two calls, neither replayed |
| `tests/web-api/u06_u12_never_coalesced.rs::u6_identical_creates_with_different_op_ids_are_two_calls` | kept | itself | two sequential identical creates, different op ids: two calls, neither replayed |
| `tests/web-api/u06_u12_never_coalesced.rs::u6_u12_the_same_op_id_from_two_tabs_at_once_is_one_call` | kept | itself | held 800 ms call, same op id twice: one spawn, one thread |
| `tests/web-api/u09_u11_preview_and_status.rs::cloud_options_share_only_an_in_progress_read` | kept | itself | two concurrent GETs share one catalogue read; a later GET reads again |
| `tests/web-api/u09_u11_preview_and_status.rs::u11_an_uncertain_create_stays_uncertain_and_nothing_retries` | kept | itself | uncertain status reads leave record bytes unchanged; repeat replays; no second spawn |
| `tests/web-api/u09_u11_preview_and_status.rs::u11_the_status_of_a_created_thread_reads_its_start_once` | kept | itself | start read once on create and once on status |
| `tests/web-api/u09_u11_preview_and_status.rs::u9_the_preview_carries_the_cores_effects_and_creates_nothing` | kept | itself | effect kinds in order; no-remote is stopped with no effects; preview writes nothing |
| `tests/web-api/w15_no_redispatch.rs::a_server_killed_during_the_call_never_sends_again` | kept | itself | killed mid-call; restart makes no call; replay recovered as uncertain; one tell. kill_parent appears only here |
| `tests/web-api/w15_no_redispatch.rs::the_server_and_the_cli_share_one_send_record` | kept | itself | U9: server and CLI replay each other's op ids, one tell each. No twin found (create side is u06/u09) |
| `tests/web-api/w1_one_mutation.rs::every_other_method_on_the_send_route_is_405_and_sends_nothing` | kept | itself | 11 methods on send route: 405, Allow POST, no tell |
| `tests/web-api/w1_one_mutation.rs::get_never_sends` | deleted | `tests/web-api/w5_same_operation.rs::every_preview_equals_the_cli` (`tell_count` 0 after every preview GET) and `tests/web-api/w5_same_operation.rs::every_lookup_equals_the_cli` (`tell_count` 2 after two sends and their lookups) |  |
| `tests/web-api/w1_one_mutation.rs::post_anywhere_else_is_405_and_sends_nothing` | kept | itself | POST to 10 non-send targets (trailing slash, /message, /api/v1/messages): 405, Allow GET, no tell. a4:151 covers only 4 GET routes |
| `tests/web-api/w1_one_mutation.rs::the_route_table_is_the_read_routes_and_one_post` | deleted | `tests/web-api/a4_no_mutation.rs::the_route_table_is_the_read_routes_the_send_and_the_create` |  |
| `tests/web-api/w1_one_mutation.rs::without_sending_the_send_routes_are_absent_for_every_method` | kept | itself | sending None: 404, no Allow, nothing read, 6 methods × 3 targets. a4 covers GET only |
| `tests/web-api/w2_owner.rs::no_answer_depends_on_access_headers_or_cookies` | kept | itself | forged Access/Cookie headers change no status or body; one send each |
| `tests/web-api/w2_owner.rs::the_server_never_reads_access_headers_or_cookies` | deleted | `tests/web-api/aw02_owner_and_cross_site.rs::the_server_reads_no_access_header_or_cookie` (the same scan of `crates/server/src`) and `tests/web-api/w2_owner.rs::no_answer_depends_on_access_headers_or_cookies` |  |
| `tests/web-api/w3_cross_site.rs::a_json_content_type_with_utf_8_is_accepted` | kept | itself | three JSON spellings accepted once, no CORS (w3:214) |
| `tests/web-api/w3_cross_site.rs::a_preflight_gets_no_cors_grant` | kept | itself | OPTIONS preflight with foreign Origin: 405, no CORS; accepted send: no CORS |
| `tests/web-api/w3_cross_site.rs::a_send_host_can_never_be_loopback_or_an_ip_address` | moved | `crates/server/tests/host_names.rs::a_send_host_can_never_be_loopback_or_an_ip_address` | SendHost::new rejects 21 loopback/IP/empty/port values, accepts 4 DNS names. tests/service/t4_service.rs:485 checks only 3 values |
| `tests/web-api/w3_cross_site.rs::each_cross_site_vector_is_refused_with_no_call` | kept | itself | 24 vectors (origin, Sec-Fetch-Site, custom header, content type, Host): refused, no CORS, no tell, no claim. Twins in u02/aw02 are other routes |
| `tests/web-api/w3_cross_site.rs::the_binary_refuses_a_loopback_or_ip_send_host_before_any_access` | kept | itself | built binary exits 2 for 4 hosts, no "listening", no echo, no state touched. Only test that runs the binary's send-host gate |
| `tests/web-api/w3_cross_site.rs::without_a_configured_host_name_nothing_can_send` | kept | itself | sending.host None gives 421 for any Host. Twins u02:217 and aw02:175 are other routes |
| `tests/web-api/w4_bounds.rs::a_body_over_the_cap_is_refused_unread_and_one_at_the_cap_is_read` | kept | itself | 413 without reading the body; exactly-at-cap accepted. Create-route cap (u04:171) is another route |
| `tests/web-api/w4_bounds.rs::a_body_that_breaks_the_rules_is_refused_with_no_call` | kept | itself | 18 bad bodies: 400, no record; 4 core messages pinned. Sub-cases overlap only_the_allowed_object_shape_is_a_body |
| `tests/web-api/w4_bounds.rs::a_second_target_is_impossible` | kept | itself | `/sessions/a/b/messages`, comma target, `//` refused, no tell. No twin found |
| `tests/web-api/w4_bounds.rs::framing_is_strict` | kept | itself | 8 framing refusals on the send route (no length, chunked, chunked and a length, hex length, short body, query, …) |
| `tests/web-api/w4_bounds.rs::nothing_of_a_send_reaches_the_log` | kept | itself | marker text and target absent from log; exact request lines present. Create twin u04_bounds.rs:289 is another route. Stale comment |
| `tests/web-api/w4_bounds.rs::only_the_allowed_object_shape_is_a_body` | kept | itself | 24 wrong shapes: 400, no record, store never opened; allowed shapes 200 |
| `tests/web-api/w4_bounds.rs::sends_over_the_cap_are_refused_before_any_claim` | kept | itself | second send at cap 1: 503 busy, Retry-After 5, no claim; reads still served |
| `tests/web-api/w4_bounds.rs::the_send_bounds_are_the_documented_values` | kept | itself | MAX_SENDS=2, BODY_TIMEOUT=10s unique here. 99_328 also pinned at u04_bounds.rs:22 |
| `tests/web-api/w5_same_operation.rs::an_uncertain_send_and_a_possible_duplicate_equal_the_cli` | kept | itself | non-JSON CLI stdout gives uncertain; route equals CLI. Literal "not json" not found in tests/messaging or the send fixture |
| `tests/web-api/w5_same_operation.rs::cloud_queue_receipt_survives_send_replay_and_lookup` | kept | itself | pinned queued delivery JSON, replayed flag, lookup "recorded", one tell |
| `tests/web-api/w5_same_operation.rs::every_lookup_equals_the_cli` | kept | itself | lookup bytes equal `--check --json`; no record before any send |
| `tests/web-api/w5_same_operation.rs::every_preview_equals_the_cli` | kept | itself | preview bytes equal `--preview --json`; 5 bad queries 400; no tell |
| `tests/web-api/w5_same_operation.rs::every_send_fixture_case_equals_the_cli` | kept | itself | route body equals `openwiz send --json` for 11 targets × queue/steer × resume, replay, conflict |
| `tests/web-api/w5_same_operation.rs::the_core_refusals_equal_the_cli` | kept | itself | 4 refusals: body and stderr equal CLI (exit 2 format). Inputs overlap w4:110-141, but this checks CLI parity |
| `tests/web-api/w5_same_operation.rs::the_server_has_no_send_logic` | deleted | `tests/web-api/w5_same_operation.rs::every_send_fixture_case_equals_the_cli` |  |
| `tests/web-api/w6_never_coalesced.rs::a_conflicting_reuse_is_no_call` | kept | itself | changed text, changed mode, other target: conflicting_reuse, one tell |
| `tests/web-api/w6_never_coalesced.rs::identical_sends_at_once_are_two_calls_only_when_the_owner_accepts` | kept | itself | accepted: 2 held calls, 2 tells; not accepted: possible_duplicate_refused, 1 tell |
| `tests/web-api/w6_never_coalesced.rs::identical_sends_with_different_op_ids_are_two_calls` | kept | itself | two sequential sends, different op ids: two calls. Catches dedupe-after-completion, which the concurrent test misses |
| `tests/web-api/w6_never_coalesced.rs::the_same_op_id_from_two_tabs_is_one_call` | kept | itself | 3 concurrent same-op requests: one tell; later replay. Create twin u06_u12 is another route |
| `tests/web-api/w6_never_coalesced.rs::the_send_path_has_no_single_flight` | deleted | `tests/web-api/w6_never_coalesced.rs::identical_sends_at_once_are_two_calls_only_when_the_owner_accepts` |  |
