# TV12 ledger

Source: `openwizdev/OpenWiz@aa09045873946bf512f7e2ad538ecc17384366d8`,
`tests/checks/skills.rs`: 48 tests. Repositories are explicit in cross-repository
keepers. Pure wording matches and tests of their private, test-only Markdown
parsers are retired under #814: they did not execute a supported operation.
This does not remove the instructions or authorize bypassing any of their rules.
Local release safety contracts, consumer links and suite wrappers stay here.

| Test | Outcome | Keeper | Catches |
| --- | --- | --- | --- |
| `tests/checks/skills.rs::codex_helpers_use_sol_high_default_tier_and_claude_helpers_keep_their_family` | deleted | behaviour gone: exact helper model/service-tier prose enforcement retired by #814 | |
| `tests/checks/skills.rs::fresh_nightly_claim_continues_the_ticks_other_lines` | deleted | behaviour gone: exact unfinished-claim paragraph wording enforcement retired by #814 | |
| `tests/checks/skills.rs::codex_default_tier_setting_discloses_rust_dispatch_limitation` | deleted | behaviour gone: exact Rust-dispatch disclaimer wording enforcement retired by #814 | |
| `tests/checks/skills.rs::reviewer_builder_family_has_a_recorded_source` | deleted | behaviour gone: exact reviewer-family source paragraph wording enforcement retired by #814 | |
| `tests/checks/skills.rs::diagnose_orchestrator_is_routed_from_review_findings` | deleted | behaviour gone: exact diagnosis handoff string enforcement retired by #814 | |
| `tests/checks/skills.rs::launch_fleet_nightly_only_tick_reaches_step_six` | deleted | behaviour gone: exact nightly-routing paragraph spelling enforcement retired by #814 | |
| `tests/checks/skills.rs::builder_checkout_isolation_is_portable` | deleted | behaviour gone: exact builder isolation sentence placement/spelling enforcement retired by #814 | |
| `tests/checks/skills.rs::builder_follows_the_fleet_test_command_rule` | deleted | behaviour gone: exact fleet-test-command sentence enforcement retired by #814 | |
| `tests/checks/skills.rs::reviewer_checkout_isolation_is_portable` | deleted | behaviour gone: exact reviewer isolation sentence placement/spelling enforcement retired by #814 | |
| `tests/checks/skills.rs::checkout_isolation_check_refuses_hidden_or_shared_output_rules` | deleted | behaviour gone: the private Markdown parser used only to pin isolation-rule prose retired by #814 | |
| `tests/checks/skills.rs::checkout_isolation_ignores_unrelated_fenced_examples` | deleted | behaviour gone: the private Markdown parser used only to pin isolation-rule prose retired by #814 | |
| `tests/checks/skills.rs::checkout_isolation_respects_fence_boundaries` | deleted | behaviour gone: the private Markdown parser used only to pin isolation-rule prose retired by #814 | |
| `tests/checks/skills.rs::checkout_isolation_respects_comment_spans` | deleted | behaviour gone: the private Markdown parser used only to pin isolation-rule prose retired by #814 | |
| `tests/checks/skills.rs::setup_checkout_isolation_slot_is_optional` | deleted | behaviour gone: exact optional template-slot spelling enforcement retired by #814 | |
| `tests/checks/skills.rs::the_skills_folder_passes_the_static_check` | kept | itself | Installed skill harness links missing, dangling or pointed at another folder; cross-repository consumer integration stays in OpenWiz. |
| `tests/checks/skills.rs::diagnose_bisect_wrapper_skips_inconclusive_input` | deleted | behaviour gone: exact bisect explanation spelling enforcement (no bisect wrapper is executed) retired by #814 | |
| `tests/checks/skills.rs::research_raw_output_instruction_survives_filling_measurements` | deleted | behaviour gone: exact raw-output sentence/placeholder spelling enforcement retired by #814 | |
| `tests/checks/skills.rs::huntr_checklist_separates_stale_docs_from_product_text` | deleted | behaviour gone: exact huntr checklist question/tier prose enforcement retired by #814 | |
| `tests/checks/skills.rs::huntr_test_audit_keeps_protected_tests_and_the_coverage_and_kill_guard` | deleted | behaviour gone: exact test-audit policy prose enforcement (no test-removal guard is executed) retired by #814 | |
| `tests/checks/skills.rs::overnight_preserves_huntr_risk_tiers_and_open_cap` | deleted | behaviour gone: literal overnight authority/cap prose enforcement retired by #814 | |
| `tests/checks/skills.rs::huntr_kind_approval_has_a_durable_record` | deleted | behaviour gone: exact kind-approval instruction and trace-row wording enforcement retired by #814 | |
| `tests/checks/skills.rs::huntr_kind_record_preserves_standing_tier_approval` | deleted | behaviour gone: exact standing-tier instruction wording enforcement retired by #814 | |
| `tests/checks/skills.rs::huntr_holds_one_controller_by_lease_and_waits_by_waking` | deleted | behaviour gone: literal lease/controller instruction inventory enforcement (no lease/controller is executed) retired by #814 | |
| `tests/checks/skills.rs::overnight_reuses_huntr_thirty_minute_loop` | deleted | behaviour gone: exact night-controller paragraph spelling enforcement retired by #814 | |
| `tests/checks/skills.rs::overnight_day_review_preserves_redacted_technical_facts` | deleted | behaviour gone: exact overnight day-review instruction inventory enforcement retired by #814 | |
| `tests/checks/skills.rs::a_dangling_or_wrong_link_fails` | kept | itself | A harness-link checker accepting dangling, missing, wrong, absolute, copied or extra links; its synthetic cases exercise the OpenWiz integration. |
| `tests/checks/skills.rs::plan_graph_relies_on_form` | moved | `openwizdev/WizSkills:skills/plan-graph/test/test_relies.py::ReliesTest.test_relies_on_form` | Invalid, hidden, unsafe or missing dependency declarations accepted by the public shell checker, including loss of its sh/jq-only runtime. |
| `tests/checks/skills.rs::plan_graph_relies_on_rule_and_template` | deleted | behaviour gone: the private validator of plan-graph rule/template wording (the executable dependency checker is retained pending its port) retired by #814 | |
| `tests/checks/skills.rs::plan_graph_relies_on_rule_is_visible_and_template_is_unique` | deleted | behaviour gone: the private validator of plan-graph rule/template wording (the executable dependency checker is retained pending its port) retired by #814 | |
| `tests/checks/skills.rs::research_worker_github_check` | moved | `openwizdev/WizSkills:skills/research/test/test_workers.py::WorkerTest.test_worker_github_check` | Worker writes, broad/wrong/stale allowances, deletion allowances accepting edits and invalid/incomplete observations reported clean. |
| `tests/checks/skills.rs::research_workflow_checks_github_around_dispatch` | deleted | behaviour gone: exact workflow wording enforcement (the executable guard and commands are retained pending their ports) retired by #814 | |
| `tests/checks/skills.rs::research_snapshot_path_survives_fresh_shells` | moved | `openwizdev/WizSkills:skills/research/test/test_snapshot_commands.py::SnapshotTest.test_snapshot_path_survives_fresh_shells` | Snapshot/check/allowance commands losing the recorded path or breaking argv/redirection across fresh shells with spaces and apostrophes. |
| `tests/checks/skills.rs::ask_wiz_contract` | deleted | behaviour gone: literal ask-wiz routing/install-rule prose validation (the skill and its approval rule remain) retired by #814 | |
| `tests/checks/skills.rs::ask_wiz_phase_boundaries` | deleted | behaviour gone: literal ask-wiz routing/install-rule prose validation (the skill and its approval rule remain) retired by #814 | |
| `tests/checks/skills.rs::ask_wiz_install_rule_refuses_ungated_or_hidden_instructions` | deleted | behaviour gone: literal ask-wiz routing/install-rule prose validation (the skill and its approval rule remain) retired by #814 | |
| `tests/checks/skills.rs::adr0019_live_smoke_and_hands_on_timing` | kept | itself | Local live-check release instructions losing candidate, authority or device-evidence gates; these skills remain local to OpenWiz. |
| `tests/checks/skills.rs::adr0019_combined_release_gate` | kept | itself | Local release instructions or the release-candidate contract accepting incomplete combined smoke; OpenWiz-owned release contract. |
| `tests/checks/skills.rs::adr0019_automatic_export_and_one_final_approval` | kept | itself | Local release instructions losing activation, exact decisions, invalidation, immutable publishing or delivery gates; OpenWiz release integration. |
| `tests/checks/skills.rs::adr0019_release_skills_are_kept_for_rust_checks` | kept | itself | The OpenWiz CI classifier pruning the local release instruction files that its checks read. |
| `tests/checks/skills.rs::onboard_keeps_its_gates` | deleted | behaviour gone: literal onboard heading/order/prose/file inventory enforcement (the actual journey wrapper stays) retired by #814 | |
| `tests/checks/skills.rs::onboard_journey_fixtures_pass` | kept | itself | The onboarding fixture journey suite failing; replacement needed: a WizSkills onboard suite executing tools/install/tests/onboard/test_journey.py. |
| `tests/checks/skills.rs::install_keeps_its_order_and_gates` | deleted | behaviour gone: literal install heading/order/prose/file inventory enforcement (the actual install suites stay) retired by #814 | |
| `tests/checks/skills.rs::setup_onboard_contract_passes` | kept | itself | The setup/onboard consistency suite failing; replacement needed: a WizSkills setup suite executing tools/install/tests/setup-onboard-contract/test_contract.py. |
| `tests/checks/skills.rs::setup_onboard_init_passes` | kept | itself | The installed init runtime suite failing; replacement needed: a WizSkills setup suite executing tools/install/tests/init/test_init.py. |
| `tests/checks/skills.rs::setup_onboard_login_passes` | kept | itself | The browser sign-in/App-skip suite failing; replacement needed: a WizSkills setup suite executing tools/install/setup/test_github_login.py (with -B). |
| `tests/checks/skills.rs::setup_onboard_journey_passes` | kept | itself | The first-merge journey suite failing; replacement needed: a WizSkills onboard suite executing tools/install/tests/first-hour/test_first_merge.py. |
| `tests/checks/skills.rs::one_install_line_everywhere` | kept | itself | OpenWiz consumer documentation and web setup disagreeing with the installed install prompt and upgrade destination. |
| `tests/checks/skills.rs::install_journey_and_live_kit_pass` | kept | itself | Cold-consumer install/live-kit/first-hour suites failing; replacement needed: a WizSkills install suite executing all four existing script paths, listed below. |

## Wrappers retained, pending named replacements

All six suite wrappers remain byte-for-byte in their test bodies. The scripts
remain in OpenWiz, so no WizSkills green result can stand in for them today.
`install_journey_and_live_kit_pass` still runs all four:

- `tools/install/tests/journey/test_journey.py`
- `tools/install/live-kit-test.py`
- `tools/install/tests/first-hour/test_journey.py`
- `tools/install/tests/first-hour/test_kit.py`

The three executable portable proofs moved only after WizSkills run
[44390693366](https://github.com/openwizdev/WizSkills/actions/runs/44390693366)
passed at `0564f5e3cb3c0e8a2461279ee1dcfbe7e69051b1`. Each suite printed its
pass receipt; [wizskills-ci.json](wizskills-ci.json) binds them to that head.
Their keeper paths are:

- `openwizdev/WizSkills:skills/plan-graph/test/test_relies.py::ReliesTest.test_relies_on_form`
- `openwizdev/WizSkills:skills/research/test/test_workers.py::WorkerTest.test_worker_github_check`
- `openwizdev/WizSkills:skills/research/test/test_snapshot_commands.py::SnapshotTest.test_snapshot_path_survives_fresh_shells`

The snapshot port keeps cross-shell-variable validation and executes each
extracted command. It retires exact prose/command spelling assertions; the
literal expected argv and redirection outcomes stay checked.

## Per ported test

- `ReliesTest.test_relies_on_form` catches: dependency declarations that hide a
  dependency, escape the repository, refer to missing/symlink paths, or require
  Python in the public shell checker. All 45 original table rows remain.
- `WorkerTest.test_worker_github_check` catches: writes on each checked GitHub
  surface, broad/wrong/stale allowances, deletion allowances accepting edits,
  invalid snapshots and missing/partial/malformed/duplicate reads reported clean.
- `SnapshotTest.test_snapshot_path_survives_fresh_shells` catches: fresh-shell
  variables and unquoted spaces/apostrophes losing the recorded snapshot or argv.
- No new product test: these are ports of three existing executable proofs.
  The production scripts are unchanged; no product bug fix is claimed.
