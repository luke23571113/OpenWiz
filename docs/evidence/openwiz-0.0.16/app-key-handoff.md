# 0.0.16 T3 (#606): private personal App and protected key handoff

Sanitized builder evidence for #606 of spec #625. Synthetic fixtures only; no
live App, account, key, secret or CloudRoom save was used or observed.

## Red runs (before the fix)

Base `192f6e4b636895d15b04421c6741f32253459d81`, tests changed first. Every
red reaches its claim's own assertion: today's code makes the user manifest
public, has no explicit factory setting, and mints or installs for an App
owned by another account.

### `python3 -I tools/github-app/test.py`

```text
ERROR: test_agent_reconcile_is_bound_to_the_owner_unless_the_factory_setting_is_explicit (account=('--agent-for', 'synthetic-owner'), owner='synthetic-elsewhere')
ERROR: test_agent_reconcile_is_bound_to_the_owner_unless_the_factory_setting_is_explicit (account=('--agent-for', 'jparker2006'), owner='openwizdev')
FAIL: test_agent_app_created_by_another_account_is_refused_and_never_installed
FAIL: test_agent_page_carries_exactly_the_contract_profile (account=('--agent-for', 'synthetic-owner'))
FAIL: test_agent_page_carries_exactly_the_contract_profile (account=('--agent-for', 'synthetic-org', '--organization'))
FAIL: test_agent_page_carries_exactly_the_contract_profile (account=('--agent-for', 'synthetic-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx'))
FAIL: test_agent_page_carries_exactly_the_contract_profile (account=('--agent-for', 'synthetic-org', '--organization', '--factory'))
FAIL: test_agent_reconcile_is_bound_to_the_owner_unless_the_factory_setting_is_explicit (account=('--agent-for', 'jparker2006', '--factory'), owner='openwizdev')
FAIL: test_agent_reconcile_is_bound_to_the_owner_unless_the_factory_setting_is_explicit (account=('--agent-for', 'synthetic-owner', '--factory'), owner='openwizdev')
FAIL: test_manifest_is_exactly_the_service_profile
FAIL: test_read_token_is_bound_to_the_app_owner_or_the_named_factory_installations (mode=None, app_owner='synthetic-elsewhere', account='synthetic-owner', repository='synthetic-owner/work')
FAIL: test_read_token_is_bound_to_the_app_owner_or_the_named_factory_installations (mode='user', app_owner='synthetic-elsewhere', account='synthetic-owner', repository='synthetic-owner/work')
FAIL: test_read_token_is_bound_to_the_app_owner_or_the_named_factory_installations (mode=None, app_owner='openwizdev', account='jparker2006', repository='jparker2006/ClosedWiz')
FAIL: test_read_token_is_bound_to_the_app_owner_or_the_named_factory_installations (mode='factory', app_owner='openwizdev', account='jparker2006', repository='jparker2006/synthetic-unnamed')
FAIL: test_read_token_is_bound_to_the_app_owner_or_the_named_factory_installations (mode='factory', app_owner='openwizdev', account='synthetic-owner', repository='synthetic-owner/work')
FAIL: test_read_token_is_bound_to_the_app_owner_or_the_named_factory_installations (mode='public', app_owner='synthetic-owner', account='synthetic-owner', repository='synthetic-owner/work')
FAIL: test_read_token_is_bound_to_the_app_owner_or_the_named_factory_installations (mode='', app_owner='synthetic-owner', account='synthetic-owner', repository='synthetic-owner/work')
FAIL: test_read_token_names_exact_selection_and_its_expiry
FAIL: test_read_token_refuses_foreign_unselected_expired_or_mixed_owner
FAIL: test_installation_on_the_repository_owner_must_also_be_the_app_owner
FAIL: test_signs_real_jwt_and_prints_only_read_token
Ran 64 tests in 84.614s
FAILED (failures=19, errors=2)
```

### `cargo test -p openwiz-tests --test cli-agent github_token`

With the compiling seam only (`Call::App`, `Mode`, the setting parsed; no owner check):

```text
thread 'github_token::gi_p6_a_refused_exchange_or_an_answer_outside_the_contract_exits_5'  panicked at tests/cli-agent/github_token.rs:593:9:
  left: 1
 right: 2
thread 'github_token::gi_p6_an_unknown_repository_exits_3_and_never_mints'  panicked at tests/cli-agent/github_token.rs:568:5:
  left: ["installation synthetic-owner/work"]
 right: ["app", "installation synthetic-owner/work"]
thread 'github_token::gi_p6_a_lost_reply_is_a_failure_exit_1_never_a_token'  panicked at tests/cli-agent/github_token.rs:621:9:
  left: 1
 right: 2
thread 'github_token::gi_p6_each_fixture_case_gives_its_exit_stdout_stderr_and_exact_request'  panicked at tests/cli-agent/github_token.rs:314:9:
  left: ["installation synthetic-owner/work", "access_tokens 2002"]
 right: ["app", "installation synthetic-owner/work", "access_tokens 2002"]
thread 'github_token::gi_p6_the_jwt_authenticates_as_the_app_for_an_installation_token'  panicked at tests/cli-agent/github_token.rs:392:5:
  left: 2
 right: 3
thread 'github_token::j48_a_user_app_mints_only_on_its_owners_account_and_the_factory_only_when_explicit'  panicked at tests/cli-agent/github_token.rs:742:9:
  left: ["installation", "access_tokens"]
 right: ["app", "installation", "access_tokens"]
thread 'github_token::j48_an_unreadable_mode_or_a_revoked_or_foreign_app_key_mints_nothing'  panicked at tests/cli-agent/github_token.rs:800:9:
  left: (0, "expires_at 4600\n")
 right: (5, "openwiz: github token: GitHub refused the token (details withheld); no token was printed\n")
test result: FAILED. 7 passed; 7 failed; 0 ignored; 0 measured; 43 filtered out; finished in 2.49s
```
