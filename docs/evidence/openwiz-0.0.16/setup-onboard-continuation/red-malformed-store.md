# Red run: a malformed setup store is carried (#636)

The continuation case `a project without its CloudRoom project` against the helper at 0514522, before its strict read of the setup store.

```text
FAIL: test_only_current_verified_setup_and_a_brain_are_carried [a project without its CloudRoom project]
AssertionError: 0 != 10 : Carried from setup: repository synthetic-owner/synthetic-sheep, CloudRoom project None.
FAILED (failures=1)
```

The claim: an unreadable or malformed store is refused (exit 10) and nothing is carried; the old reader carried a missing project as `None`.
