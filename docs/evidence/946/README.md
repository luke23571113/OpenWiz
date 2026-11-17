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

Results: all four original AW5 tests passed one 150ms/170ms process-pause run
(`baseline-pause.txt`). The focused real scan/cleanup probe reproduces CI's
500 `store_unavailable` at `attach_support.rs:260`, with an explicit marker
confirming reservation removal between the scan's read and directory listing.
`red-reservation-race.txt` was committed before changing the keeper.

Reproduce: compile the web-api test executable, then run
`TMPDIR=/dev/shm python3 docs/evidence/946/run-probe.py <executable> red|green`.
The probe holds only this synthetic upload's cleanup before reservation removal.
An unfixed keeper starts the next upload during that hold; the probe releases
cleanup after its scanner reads the reservation, then lets the scan continue
after real directory removal. With the fix the next case cannot start until
cleanup finishes. The same probe passes (`green-reservation-race.txt`), without
changing a refusal or zero-call assertion. The three-second hold is diagnostic
load only, not part of the fixed keeper. Its runner rejects wrong-target,
missing-marker and unexpected exit/assertion outcomes.

Limits: this establishes a real concurrent-client storage edge in
`crates/store/src/attachments.rs::outstanding`, where abort cleanup can remove
a scanned directory. No production edit was made and this PR does not fix or
claim to fix that concurrent-client behavior. Its purpose is to restore the
independent gate cases' intended precondition. A production follow-up requires
separate approval through #1046.

Diff/checklist: one explicit state wait in the owned flaky test plus its own
kind-3 supporting evidence folder. Every readiness refusal, zero-call/no-record
check and final valid send stays. No new test, dependencies, guards, policies,
timeout increases, retries or production changes. No helpers or seams.

Validation: all four AW5 proofs pass under the same process pauses (5.96s),
the controlled cleanup probe passes (3.49s), `cargo fmt --check` passes and
`cargo clippy -p openwiz-tests --all-targets -- -D warnings` passes.
No changelog: tests only (`no-changelog`). Normal hook and full CI remain gates.
