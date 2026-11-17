# #1026 — AD7 outcome and attachment lifetime

Part of #1046 (J130). Fixture evidence only; no live calls.

Before changing the test: AD7 must catch a send that records the wrong delivery,
deletes failed/uncertain attachments, retains accepted copies, or dispatches an
op id twice. AD1 owns the actual attachment invocation/upload; M4 owns provider
receipt decoding. Those integration keepers remain unchanged. AD7's one-second
budget currently lets process scheduling choose a different outcome before its
six rows reach their intended seam. Existing happy-path runs miss that fault.

Plan: reproduce the old keeper with #763-style process pauses, retain the red,
then exercise all six outcome inputs through the public Messenger boundary with
real send and attachment stores and controlled time. Assert the real durable
outcome, attachment binding/retention and replay without another dispatch for
every row. Keep the one-second budget. No new test: strengthen AD7's existing
six-row keeper; AD1 and M4 continue to cover the subprocess boundary.

Readiness: all inputs are synthetic, owned by this builder and producible now.
Affected checks: AD7 with the same pauses, the AD attachment group, M4, format,
and Clippy for openwiz-tests. Normal foreground push runs the repository hook.
The full suites belong to CI. No production files or dependencies change.

Reproduction: `TMPDIR=/dev/shm python3 docs/evidence/1026/pause-test.py
<the messaging test executable>` stops only that runner for 2.2 seconds after
the first durable claim. This is a controlled descheduling window, using #763's
SIGSTOP/SIGCONT mechanism, rather than a claim about a specific CI schedule.
`red-pause.txt` anchors the same failure to the first provider read;
`red-durable-pause.txt` anchors it to the durable claim (shared by both versions).
Both reach AD7's accepted-row assertion: Failed versus Accepted. Initial probes
that hit diagnostic setup/cutoff limits were excluded; they are not claim reds.
Disposable state uses tmpfs in this probe to isolate scheduling from journal waits;
real store writes, fsyncs, reopens and retention still execute.

The corrected keeper controls monotonic time because clock expiry is not AD7's
claim. Its Messenger supplies the six semantic inputs; assertions cover the real
core's binding, dispatch mark, durable outcome, copy lifetime and idempotent replay.
It does not claim to test receipt decoding, upload I/O failures or actual provider
timeout handling. The unchanged AD1 and M4 keepers own those integration boundaries.

Validation: AD7 passes normally and with the same durable-claim pause. All 18
`ad_send_attachments` tests pass (53.66s). Format and
`cargo clippy -p openwiz-tests --all-targets -- -D warnings` pass.
An additional M4 run, with AD7 excluded by its filter, had 17 passes and one
failure in unchanged `everything_else_is_uncertain`: the hang row exceeded its
10-second elapsed-time assertion (17.85s suite). Its output is retained in
`m4-unchanged-failure.txt`; no retry or edit to that independent keeper.

Diff/checklist audit: only the owned AD7 test and this standing supporting
`docs/evidence/1026/` folder change. No dependencies, policies, contracts,
production behavior, ignored tests or timeout increases. Synthetic data only.
No helpers or new seams. No changelog: test-only fix (`no-changelog` label).

CI follow-up: the carriage guard refused this new evidence folder before any
Rust tests ran. Add only `docs/evidence/1026/**` to the shared carriage registry
`tools/open-import/paths.json` under standing supporting-edit kind 1; this makes
the already-approved public proof artifacts available to CI. No new test for a
registry row: the existing carriage guard directly verifies its classification.
The first successful push receipt remains the original observation.
