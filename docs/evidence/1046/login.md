# #1043: pending sign-in restart

The existing restart test protects one browser sign-in per living, durably
recorded pending child, including when its record is old. It catches a restart
opening a duplicate sign-in and relying on record age despite a living child.
No new test: strengthen this existing keeper; the other identity assertions
remain unchanged.

The first baseline run failed with the reported 60-second subprocess timeout.
The direct measurement in `measure-login.py` then failed before ageing the
record: its PID was null while the fake child was alive. The fake child's marker
is written independently of the wrapper's atomic durable PID replacement. The
test killed the wrapper between these events, then aged the unprovable record
past its expiry. Starting a new browser flow is correct for that state; the
fixture's second pending flow caused the timeout.

Wait for the record to name the marker's child before interrupting the wrapper.
Keep the original 20-second readiness bound, 60-second subprocess timeout,
age change, one-sign-in counts, and successful fresh sign-in after cleanup.
No production edit, retry, timeout increase, or sleep increase.

Reproduce the direct cause measurement from the repository root:

```sh
python3 -B docs/evidence/1046/measure-login.py
python3 -I tools/install/setup/test_github_login.py -v
```

Evidence: `login-baseline-red.log`, `login-cause-red.log`,
`login-cause-green.log`, and `login-green.log`. The baseline and measurement
were retained in a separate commit before the fix. All provider data is synthetic.

Supporting edits: this ticket's own evidence folder under the standing
supporting-edit rule, for #1043's required red/green evidence. Tests only:
no changelog line. Helpers: none for this independent Python slice.
