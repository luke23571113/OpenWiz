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
