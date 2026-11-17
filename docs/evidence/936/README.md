# #936 — deadline slot ownership

Part of #1046 (J130), fixture evidence only.

Before changing the test: this keeper must catch freeing a worker's slot merely
because HTTP timed out, sharing a new request onto an expired flight, or failing
to release the slot when its source finally finishes. It currently also requires
a fresh process-backed plan to complete within the intentionally short two-second
HTTP deadline. That is not guaranteed under load. The unchanged shared-flight
keeper owns healthy 200 responses and exact source-call counts.

Plan: reproduce the final recovery 504 versus 200 by delaying only its fourth
GitHub wrapper launch. Retain that red before any fix. Re-arm the real wrapper's
existing FIFO gate for recovery, observe admission/core-run ownership, hold it
until its HTTP deadline, release it, and observe actual source completion and
exact calls. Keep the original deadline, slot wait and wait-helper bounds.
The healthy 200/shared-flight keeper remains unchanged.

No new test: strengthen the existing deadline keeper. All inputs are local and
synthetic; proof available now at the real server/fake-provider boundary.
Supporting evidence is covered by fleet supporting-edit kind 3. No production
edits, dependencies, retries, timeout increases, skipped or deleted tests.

Supporting registry row: `tools/open-import/paths.json` adds only this ticket's
public evidence folder, under fleet supporting-edit kind 1. This prevents the
carriage guard refusing its new proof artifacts before any test lane starts.

Results: the controlled fourth-launch delay reproduces the exact final 504 versus
200 assertion (`red-delayed-recovery.txt`, committed before the fix at 63ecf6b).
The first diagnostic hooked the unused posix_spawn symbol; its missing-marker
result is excluded, not counted as a red. The retained runner hooks the binary's
actual posix_spawnp symbol and rejects a missing marker or wrong assertion.
The red executable's deadline/support file blobs were verified identical to main.

Reproduce with the web-api executable:
`TMPDIR=/dev/shm python3 docs/evidence/936/run-probe.py <executable> red|green`.
The only injected load is 2.2 seconds at the recovery worker's first launch;
the adapter/server and source calls remain real. The corrected keeper passes
that same probe (`green-delayed-recovery.txt`) with the existing two-second
request deadline, 60ms slot wait, five-second gate wait and ten-second stats wait.
Both initial and recovery flights keep their slots after HTTP expiry, then free
them only after actual completion. Exact provider count remains six.

All six `e11_plan_bounds` tests pass (6.16s), including the unchanged healthy
200/shared-flight keeper; format and scoped Clippy pass. The carriage row is
checked by the existing carriage guard. No new test for that registry wiring.

Diff/checklist: only the owned deadline keeper, its kind-3 evidence folder and
its own kind-1 carriage-list row. No retries, larger bounds, deleted/ignored
tests, new dependencies, production code, policies or contracts. The source gate
is the existing FIFO wrapper, re-armed only after the first source truly finishes.
Fixture proof only; no live observation. No helpers or later-ticket seams.
No changelog: test-only (`no-changelog`). Full suites run in CI.
