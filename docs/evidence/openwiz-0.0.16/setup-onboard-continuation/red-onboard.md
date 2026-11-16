# Red run: onboard journey tests (#636) before the change

Base: 9b67dfb76e1d25c90f8f7a11f85a832b58ca3c2f (main). The new tools/install/tests/onboard/ tests and fakes ran against the unchanged skills/onboard/scripts/onboard.py and SKILL.md.

Command: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tools/install/tests/onboard/test_journey.py

```text
FAIL: test_both_identities_carry_the_same_repository_brain_and_settings [personal_login]
AssertionError: 2 != 0 : usage: onboard.py choose|spec|launch|progress ... (see its header)
FAIL: test_both_identities_carry_the_same_repository_brain_and_settings [app]
AssertionError: 2 != 0 : usage: onboard.py choose|spec|launch|progress ... (see its header)
FAIL: test_only_current_verified_setup_and_a_brain_are_carried [no setup yet]
AssertionError: 2 != 5 : usage: onboard.py choose|spec|launch|progress ... (see its header)
FAIL: test_only_current_verified_setup_and_a_brain_are_carried [no project prepared]
AssertionError: 2 != 5 : usage: onboard.py choose|spec|launch|progress ... (see its header)
FAIL: test_only_current_verified_setup_and_a_brain_are_carried [login not verified]
AssertionError: 2 != 5 : usage: onboard.py choose|spec|launch|progress ... (see its header)
FAIL: test_only_current_verified_setup_and_a_brain_are_carried [login checked for another selection]
AssertionError: 2 != 5 : usage: onboard.py choose|spec|launch|progress ... (see its header)
FAIL: test_only_current_verified_setup_and_a_brain_are_carried [every check out of date]
AssertionError: 2 != 5 : usage: onboard.py choose|spec|launch|progress ... (see its header)
FAIL: test_only_current_verified_setup_and_a_brain_are_carried [App chosen but not verified]
AssertionError: 2 != 5 : usage: onboard.py choose|spec|launch|progress ... (see its header)
FAIL: test_only_current_verified_setup_and_a_brain_are_carried [no identity choice: the App rule]
AssertionError: 2 != 5 : usage: onboard.py choose|spec|launch|progress ... (see its header)
FAIL: test_only_current_verified_setup_and_a_brain_are_carried [no brain]
AssertionError: 2 != 5 : usage: onboard.py choose|spec|launch|progress ... (see its header)
FAIL: test_only_current_verified_setup_and_a_brain_are_carried [a brain for another repository]
AssertionError: 2 != 5 : usage: onboard.py choose|spec|launch|progress ... (see its header)
FAIL: test_only_current_verified_setup_and_a_brain_are_carried [harness refused]
AssertionError: 2 != 5 : usage: onboard.py choose|spec|launch|progress ... (see its header)
FAIL: test_only_current_verified_setup_and_a_brain_are_carried [unreadable store]
AssertionError: 2 != 10 : usage: onboard.py choose|spec|launch|progress ... (see its header)
FAIL: test_the_carried_repository_is_the_only_one
AssertionError: 2 != 0 : usage: onboard.py choose|spec|launch|progress ... (see its header)
FAIL: test_the_prepared_agents_are_reused_only_when_offered
AssertionError: 2 != 5 : nothing carried yet
FAIL: test_a_busy_state_file_is_refused
AssertionError: 2 != 7 : usage: missing --openwiz
FAIL: test_an_uncertain_start_is_never_retried_and_settles_only_on_its_record
AssertionError: 2 != 12
FAIL: test_another_repository_never_runs_this_onboardings_launch
AssertionError: 2 != 5 : (['launch', '--spec', '900'], 'usage: missing --openwiz\n')
FAIL: test_another_specs_frontier_is_not_this_fleets
AssertionError: 2 != 12 : usage: missing --openwiz
FAIL: test_every_builder_profile_the_fleet_can_use_is_the_users_choice [small builder differs]
AssertionError: 2 != 5 : usage: missing --openwiz
FAIL: test_every_builder_profile_the_fleet_can_use_is_the_users_choice [reviewer in the same family]
AssertionError: 2 != 5 : usage: missing --openwiz
FAIL: test_every_builder_profile_the_fleet_can_use_is_the_users_choice [builder tables missing]
AssertionError: 2 != 5 : usage: missing --openwiz
FAIL: test_missing_or_stale_approval_starts_nothing [missing]
AssertionError: 2 != 5 : usage: missing --openwiz
FAIL: test_missing_or_stale_approval_starts_nothing [stale]
AssertionError: 2 != 5 : usage: missing --openwiz
FAIL: test_repeat_and_reload_never_start_again
AssertionError: 2 != 0 : usage: missing --openwiz
FAIL: test_the_whole_journey_starts_one_fleet_thread_through_launch_fleet
AssertionError: 2 != 0 : (['continue'], 'usage: onboard.py choose|spec|launch|progress ... (see its header)\n', '')
FAIL: test_the_yes_binds_the_preview_the_user_saw
AssertionError: 2 != 12 : usage: missing --openwiz
FAIL: test_without_carried_setup_local_agents_or_another_spec_nothing_starts
AssertionError: 2 != 5 : usage: missing --openwiz
FAIL: test_the_conversation_follows_the_packaged_skill
AssertionError: Lists differ: ['explain', 'project', 'grill', 'agents', 'plan', 'launch', 'watch'] != ['explain', 'project', 'connect', 'grill', 'agents', 'plan', 'launch', 'watch']
Ran 20 tests in 17.371s
FAILED (failures=29)
```

Each failure reaches its claim: the unchanged helper has no `continue` (no setup is carried), refuses `choose --from-setup`, and its `launch` still needs `--openwiz` for the engine's tick.
