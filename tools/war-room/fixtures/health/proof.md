# WRD1 (#629) proof record

Synthetic fixture evidence only. No live source was read, and no loop or
workflow was activated. The work was built and reviewed on ClosedWiz as #2937
before the cut-over, then ported to OpenWiz as a patch. **The red runs below
ran on ClosedWiz**, at the ClosedWiz commits they name; their logs are kept here.

| Acceptance criterion | Claim | Evidence (fixture test) |
| --- | --- | --- |
| AC1 successor contract | `contract.v2.md` and `record.v2.schema.json` pin the three provider identities, source admission, point/result shape, limit ownership, freshness, mixed-version reading and immutable history | `test_health.py` `Contract`; `test_contract.py` `test_v1_records_keep_their_bytes_and_still_read` |
| AC2 five-minute collection-only saving | The real gather and `history.collect` save main CI, queue and stage health at five-minute identities without rendering; the hourly publish is unchanged | `Collection.test_boundaries_retries_gaps_failures_and_old_bytes`, `test_collection_only_saves_a_sample_without_drawing`, `test_the_scheduler_invocation_collects_one_v2_sample` |
| AC3 coverage, independent Unknown, privacy | Stage reads cover the open approved tickets and the merged cohort; one failed source greys only its own card; a privacy hit refuses the whole input | `test_gather.py` `test_stage_reads_cover_open_approved_work_and_the_merged_cohort`; `Collection` failed-main boundary; `test_a_privacy_hit_in_health_input_refuses_the_whole_collection` |
| AC4 no false green or zero | Superseded, pending, cancelled, changing or tied main runs are never green; partial or changing queue reads never give zero; open, held, stale and unknown waits keep TL2's meaning; a changed limit has its own identity | `MainCI`, `Queue`, `Stage` |
| AC5 both versions | v1 bytes pinned and unchanged across v2 collections; retries, out-of-order samples, failures and `weekly.py` work over mixed history; nothing backfilled | `Collection.test_boundaries_retries_gaps_failures_and_old_bytes`; `test_weekly.py`, `test_publish.py` and `test_page_history.py` unchanged and passing |
| AC3/AC5 on OpenWiz (approved scope fix: [scope ruling](https://github.com/openwizdev/openwiz/issues/629#issuecomment-6890777309)) | The War room's board readers are in `sources.py` with the board's definitions, and no private module is loaded, so gather and page history run on the public repository | `test_gather.py` `PublicBoardReaders`; `test_gather.py` and `test_page_history.py` passing on OpenWiz (`green.log`) |
| AC6 scheduler and verification | The exact loop script and the three-boundary verification procedure are in the README. Live five-minute operation is **Unverified**: no authorized activation was performed | README "Health collection and v2 history (WRD1)" |

Red runs, each committed before its fix:

- `red-first.log`: the contract claim (new records still v1); the provider cases stopped at the missing module.
- `red-providers.log`: the v2 contract slice with an explicit-Unknown stub, so each provider claim fails at its own lookup or assertion.
- `red-collect-only.log`: the collection still rendered the page through `main.tick`.

`green.log` is the passing run at the hand-back commit.

Guard checks: removing the main-head reread, or treating unclassified jobs as
complete, fails `MainCI` and `Queue` (run by hand, not committed).

## Supporting edit (orchestrator grant)

`tools/open-import/paths.json` is outside #629's owned paths. The CI carriage
guard refused this ticket's 10 new `tools/war-room/` files because none was
classified. The orchestrator's owned-path ruling of 2026-11-14 grants exactly
10 append-only rows in its `source` list, immediately after
`tools/war-room/weekly.py`: one for each new file. The file is shared, and #629
owns only those rows. The rows support AC1 to AC5, whose files they classify as
public, so CI can run. OpenWiz's carriage guard refuses the same files without
them. Evidence: `guard.py` reports "all 10 added paths are classified", and
`test_guard.py` and `test_import.py` pass (see `green.log`).
Private record: https://github.com/jparker2006/ClosedWiz/issues/2937#issuecomment-6875184162

## Review round 1 red (R1-R3)

Committed on ClosedWiz before the fixes, in `25f4df746`, as a separate log, and moved here
so the added paths stay the ten classified ones. The new proofs only, at ClosedWiz `0f73f8b`:

```text
$ python3 -I tools/war-room/test_health.py Stage.test_r3_an_edited_end_straddling_the_limit_keeps_its_measured_lower_bound
FAIL: test_r3_an_edited_end_straddling_the_limit_keeps_its_measured_lower_bound (__main__.Stage.test_r3_an_edited_end_straddling_the_limit_keeps_its_measured_lower_bound)
AssertionError: Tuples differ: ('unknown', 'unavailable', None) != ('unknown', 'partial', 10.0)
Ran 1 test in 0.085s
FAILED (failures=1)
$ python3 -I tools/war-room/test_health.py Collection.test_r1_queue_read_bounds_close_after_its_actions_reads
FAIL: test_r1_queue_read_bounds_close_after_its_actions_reads (__main__.Collection.test_r1_queue_read_bounds_close_after_its_actions_reads)
AssertionError: '2030-03-01T12:05:18Z' not greater than or equal to '2030-03-01T12:05:32Z'
Ran 1 test in 0.840s
FAILED (failures=1)
$ python3 -I tools/war-room/test_gather.py Gather.test_r2_without_a_complete_ticket_enumeration_stage_health_is_not_collected
FAIL: test_r2_without_a_complete_ticket_enumeration_stage_health_is_not_collected (__main__.Gather.test_r2_without_a_complete_ticket_enumeration_stage_health_is_not_collected) [no graph]
AssertionError: Lists differ: [{94}] != []
FAIL: test_r2_without_a_complete_ticket_enumeration_stage_health_is_not_collected (__main__.Gather.test_r2_without_a_complete_ticket_enumeration_stage_health_is_not_collected) [refused graph]
AssertionError: Lists differ: [{94}] != []
FAIL: test_r2_without_a_complete_ticket_enumeration_stage_health_is_not_collected (__main__.Gather.test_r2_without_a_complete_ticket_enumeration_stage_health_is_not_collected) [failed PR pages]
AssertionError: Lists differ: [{9001, 9002, 9003, 9004, 9005, 9006}] != []
Ran 1 test in 2.416s
FAILED (failures=3)
```

## Public board readers red (OpenWiz)

Run on OpenWiz before the extraction, committed with the new proofs:

```text
$ python3 -I tools/war-room/test_gather.py PublicBoardReaders
ERROR: test_board_graph_measures_and_states_keep_the_source_definitions (__main__.PublicBoardReaders.test_board_graph_measures_and_states_keep_the_source_definitions)
AttributeError: module 'sources' has no attribute 'board_check_links'
ERROR: test_credit_samples_and_their_sampled_drops (__main__.PublicBoardReaders.test_credit_samples_and_their_sampled_drops)
AttributeError: module 'sources' has no attribute 'read_credits'
ERROR: test_half_up_rounding_and_undefined_ratios (__main__.PublicBoardReaders.test_half_up_rounding_and_undefined_ratios)
AttributeError: module 'sources' has no attribute 'board_measures'
ERROR: test_history_rows_are_strict (__main__.PublicBoardReaders.test_history_rows_are_strict)
AttributeError: module 'sources' has no attribute 'board_strict'
FAIL: test_no_private_module_is_loaded_and_each_board_source_still_reads (__main__.PublicBoardReaders.test_no_private_module_is_loaded_and_each_board_source_still_reads) [board_graph]
AssertionError: a private module was loaded: private/orchestration/board/board.py
FAIL: test_no_private_module_is_loaded_and_each_board_source_still_reads (__main__.PublicBoardReaders.test_no_private_module_is_loaded_and_each_board_source_still_reads) [board_history]
AssertionError: a private module was loaded: private/orchestration/board/board.py
FAIL: test_no_private_module_is_loaded_and_each_board_source_still_reads (__main__.PublicBoardReaders.test_no_private_module_is_loaded_and_each_board_source_still_reads) [credits]
AssertionError: a private module was loaded: private/orchestration/board/board.py
FAIL: test_no_private_module_is_loaded_and_each_board_source_still_reads (__main__.PublicBoardReaders.test_no_private_module_is_loaded_and_each_board_source_still_reads)
AssertionError: a private module was loaded: private/orchestration/board/board.py
Ran 5 tests in 0.104s
FAILED (failures=4, errors=4)
```

## Board-reader extraction (approved scope fix)

The orchestrator's public scope ruling of 2026-11-15
(https://github.com/openwizdev/openwiz/issues/629#issuecomment-6890777309, which
carries its own private-record pointer) folds the bounded board-reader extraction
into #629. It goes into the owned `sources.py`, `gather.py`, tests and README, with
no new file and still only the ten `paths.json` rows. The CI-bench baseline gap is
#677, outside #629.

## Review round 2 red (R9, OpenWiz)

Committed with the new cases before the fix:

```text
$ python3 -I tools/war-room/test_gather.py Gather.test_r2_without_a_complete_ticket_enumeration_stage_health_is_not_collected PublicBoardReaders.test_no_private_module_is_loaded_and_each_board_source_still_reads
ERROR: test_no_private_module_is_loaded_and_each_board_source_still_reads (__main__.PublicBoardReaders.test_no_private_module_is_loaded_and_each_board_source_still_reads)
TypeError: open_approved() takes 1 positional argument but 2 were given
FAIL: test_r2_without_a_complete_ticket_enumeration_stage_health_is_not_collected (__main__.Gather.test_r2_without_a_complete_ticket_enumeration_stage_health_is_not_collected) [spec graph]
AssertionError: Lists differ: [{9001, 9002, 9003, 9004, 9005, 9006, 94}] != []
FAIL: test_r2_without_a_complete_ticket_enumeration_stage_health_is_not_collected (__main__.Gather.test_r2_without_a_complete_ticket_enumeration_stage_health_is_not_collected) [foreign board graph]
AssertionError: Lists differ: [{9001, 9002, 9003, 9004, 9005, 9006, 94}] != []
Ran 2 tests in 4.460s
FAILED (failures=2, errors=1)
```
