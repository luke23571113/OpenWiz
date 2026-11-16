# Red run: review R5 writer (#636, ruling option A) at cb24337

```text
FAIL: test_the_decisions_pair_is_written_once_and_only_on_yes [no settings file]
AssertionError: 2 != 12 : usage: onboard.py continue|create-repo|choose|spec|launch|progress ... (see its header)
FAIL: test_the_decisions_pair_is_written_once_and_only_on_yes [an existing settings file]
AssertionError: 2 != 12 : usage: onboard.py continue|create-repo|choose|spec|launch|progress ... (see its header)
FAIL: test_the_decisions_pair_is_written_once_and_only_on_yes
AssertionError: 2 != 5 : no companion, nothing to connect
Ran 1 test in 0.092s
FAILED (failures=3)
```

The recording case: preview writes nothing, the yes sets only `decision_repositories` (other keys kept, absent file created with just that key, owner-only), a second run changes nothing, and a repository without a companion writes nothing. Before the writer, `decisions` is not a command.
