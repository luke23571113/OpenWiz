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

### The `secret_capability` producer

`AgentSetupTests.test_agent_capability_reports_only_what_this_host_shows` was
written after the producer. Run against the red commit's `setup.py`, it fails
because the producer does not exist yet. That red shows the seam was missing,
not a wrong answer:

```text
FAIL: test_agent_capability_reports_only_what_this_host_shows (registered=True, store=False, delivered=None)
AssertionError: 2 != 0 (setup.py: error: unrecognized arguments: --capability)
FAIL: test_agent_capability_reports_only_what_this_host_shows (registered=True, store=False, delivered='1001')
AssertionError: 2 != 0 (setup.py: error: unrecognized arguments: --capability)
FAIL: test_agent_capability_reports_only_what_this_host_shows (registered=True, store=False, delivered=None)
AssertionError: 2 != 0 (setup.py: error: unrecognized arguments: --capability)
FAIL: test_agent_capability_reports_only_what_this_host_shows (registered=True, store=False, delivered='1002')
AssertionError: 2 != 0 (setup.py: error: unrecognized arguments: --capability)
```

## What changed

- **Private by default (AC1).** `tools/github-app/manifest.json` is
  `"public": false`. A user's own App is registered as `OpenWiz <login>`, cut to
  GitHub's 34-character limit with a short hash, because the factory already has
  the name `OpenWiz` and Create must need no edit. Only `setup.py --factory`, the
  explicit separate setting, registers or reconciles the factory's public App.
- **Owner-bound token paths (AC1, C-G1).** `openwiz github token`
  (`crates/adapters/github/src/app.rs`, `crates/cli/src/github_token.rs`) and
  `mint-token.py` read the App's owner (`GET /app`) and the installation's
  account before any token exists. A user App mints only when the installation's
  account is both the repository's owner and the App's owner. Factory mode
  (`OPENWIZ_GITHUB_APP_MODE=factory`) accepts only the identity contract's
  named installations; Python reads them from the contract's pin and refuses
  when the contract is absent. Any other mode value is refused (exit 1). The
  permission profile, read downscoping, lifetime guards, exits and "never falls
  back" are unchanged.
- **Setup refuses another owner (AC1, AC4).** Agent mode refuses a conversion
  owned by another account: the key goes nowhere, nothing is offered for
  install, and the recorded id blocks another registration. It also refuses a
  delivered key whose App is another account's, unless `--factory` is set and
  the account is named. Host mode captures an installation only on the App
  owner's account.
- **Key routes (AC3).** No supported CloudRoom save exists, so the
  `--secret-store` seam stays a seam. `--capability` prints the setup-onboard.v1
  `secret_capability` document from local facts. The protected-paste route
  lists its six counted owner steps. Delivery is `verified` only when the
  delivered id agrees with the saved one. A store seam reports the upstream as
  `unknown`, which the contract's checker reports as `agent_save_unavailable`.
- **Guide (AC2, AC3, AC4).** `docs/agents/github-app.md` covers both modes, the
  counted fallback, rotation, revocation and the wrong-owner recovery.

## Which route was proved

Only the **protected-paste** route and the seam, on synthetic fixtures. The
no-paste route (CloudRoom agent-side save-secret) is **not shipped and not
observed**. Nothing here establishes it, and a fake store proves only the
seam. No live App, installation, key, secret prompt or token was used.

## Claims and evidence

| Claim | Evidence (class) |
| --- | --- |
| User manifest private; factory public only with `--factory` | `ManifestTests.test_manifest_is_exactly_the_service_profile`, `AgentSetupTests.test_agent_page_carries_exactly_the_contract_profile` (fixture) |
| Python mint refuses another owner's installation; factory mode only for named installations | `ReadProfileTests.test_read_token_is_bound_to_the_app_owner_or_the_named_factory_installations` (fixture) |
| Rust mint refuses another owner's installation; factory only when explicit and named; unknown mode, revoked or foreign App key mint nothing | `j48_a_user_app_mints_only_on_its_owners_account_and_the_factory_only_when_explicit`, `j48_an_unreadable_mode_or_a_revoked_or_foreign_app_key_mints_nothing` (fixture) |
| Agent conversion or reconcile under another owner is refused, keeps no key and never re-registers | `AgentSetupTests.test_agent_app_created_by_another_account_is_refused_and_never_installed`, `..._reconcile_is_bound_to_the_owner_unless_the_factory_setting_is_explicit` (fixture) |
| Host installation captured only on the App owner's account | `SetupTests.test_installation_on_the_repository_owner_must_also_be_the_app_owner` (fixture) |
| `secret_capability` claims no success without verified delivery, and no no-paste route without an observed upstream | `AgentSetupTests.test_agent_capability_reports_only_what_this_host_shows`, judged by the contract's `check.py` (fixture) |
| Existing store-failure, lost-reply, ID-without-key, replay, partial-delivery and leak guards still hold | The existing `tools/github-app/test.py` and `github_token` cases, unchanged in intent (fixture) |
| Credential boundary | Independent review (pending) |

## Gaps

- The no-paste route stays unverified until the real CloudRoom interface ships
  and is observed (T4, then a plan change).
- A factory host that mints for a cross-account installation must set
  `OPENWIZ_GITHUB_APP_MODE=factory`. `docs/agents/fleet.md`'s identity table
  and `contracts/cli.v1.md` are outside this ticket's paths and do not name the
  setting yet.
- A user App name can still collide with someone else's App on GitHub; the
  owner would then have to edit the name on GitHub's page.
