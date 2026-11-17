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
