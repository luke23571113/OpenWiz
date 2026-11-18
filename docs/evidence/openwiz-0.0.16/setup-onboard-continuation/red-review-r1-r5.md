# Red run: review R1, R2, R4 and R5 (#636) at 2794f34

The new onboard regression cases against the helper at the reviewed head `2794f34`.

Command: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tools.install.tests.onboard.test_journey -k cut_short -k could_not_run -k void_once -k failed_refresh -k companion_brain

```text
FAIL: test_a_companion_brain_reaches_decisions_only_through_its_configured_pair [no settings file]
AssertionError: 0 != 5 : Carried from setup: repository synthetic-owner/synthetic-sheep, CloudRoom project prj_synthetic.
FAIL: test_a_companion_brain_reaches_decisions_only_through_its_configured_pair [another pair]
AssertionError: 0 != 5 : Carried from setup: repository synthetic-owner/synthetic-sheep, CloudRoom project prj_synthetic.
FAIL: test_a_failed_refresh_withdraws_the_carried_setup_but_keeps_the_choices
AssertionError: 'setup' unexpectedly found in {'choices': {'agents': 'cloud', 'effort': 'high', 'harness': 'codex', 'model': 'syn-codex-model-01'}, 'repo': 'synthetic-owner/synthetic-sheep', 'setup': {'brain': {'location': 'in_repository', 'repository': 'synth
FAIL: test_a_preview_is_void_once_setup_no_longer_verifies [login lost push access]
AssertionError: 0 != 5 : Ready to start the first fleet for spec #900, through launch-fleet, in the Cloud (CloudRoom project prj_synthetic):
FAIL: test_a_preview_is_void_once_setup_no_longer_verifies [checks expired]
AssertionError: 0 != 5 : Ready to start the first fleet for spec #900, through launch-fleet, in the Cloud (CloudRoom project prj_synthetic):
FAIL: test_a_start_cut_short_before_its_outcome_settles_on_its_record
AssertionError: 6 != 0 : Spec #900 already started once (uncertain: never a retry); not starting again.
FAIL: test_a_start_that_could_not_run_is_refused_and_previewed_again
AssertionError: 6 != 5 : Ready to start the first fleet for spec #900, through launch-fleet, in the Cloud (CloudRoom project prj_synthetic):
Ran 5 tests in 32.735s
FAILED (failures=7)
```

- R1: a start cut short after the spawn stays pending, even with its fleet record (exit 6).
- R2: `room-cli` missing at the confirmed start is recorded uncertain (exit 6), so no later start is possible.
- R4: a refused or expired setup leaves the carried setup in place, and the old preview starts a fleet thread (exit 0).
- R5: a public repository's companion is carried with no Decisions repository pair configured (exit 0).
