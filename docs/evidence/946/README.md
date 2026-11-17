# #946 — independent AW5 gate cases

Part of #1046 (J130), fixture evidence only.

Before changing the test: AW5 must catch a forged send that bypasses readiness,
claims an operation or calls the provider with an unavailable attachment. Every
existing refusal, record absence and zero-call assertion must remain. The
keeper currently drops an incomplete upload connection then starts the next
independent upload immediately; socket close does not prove server-side cleanup
has finished. The other three AW5 tests do not exercise that cleanup overlap.

Ranked diagnosis: reservation-scan versus aborted-upload removal first; shared
fake/state or port race second. Run all four gate keepers under process pauses,
then force the real reservation scan/cleanup interleaving and retain its exact
store_unavailable assertion red before a fix.

Plan: wait for the aborted upload's real slot to be released before the next
independent case. The server releases it after staging/cleanup returns. Reuse
TestServer::wait_for with its unchanged bound; no sleep, retry or timeout change.
Retain every invalid-send case and the final valid upload/send.

No new test: strengthen the existing owning AW5 keeper. Fixture proof readiness:
all local synthetic inputs, real server/store, builder can produce now.
Supporting evidence is covered by fleet supporting-edit kind 3. No production
files, dependencies, contracts or guards change. Production concurrency behavior
is outside this test-precondition repair and must be disclosed, not claimed fixed.
