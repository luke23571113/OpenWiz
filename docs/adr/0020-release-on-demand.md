# Release on demand from public source after cut-over

After verified open-development cut-over, Jake chooses when a release ships and
approves its exact changelog; changelog approval may precede ship. Those are the
only two human release actions. Agents prepare one checked public candidate,
collect required CI, privacy/claims and an agent-run combined live smoke that
exercises every included promise end to end, publish when all gates pass, then
verify the remote bytes and a matching normal user install/update. Sending,
thread creation, App-permission and spending changes also need their bounded
live results before shipping. Unknown risk or missing, stale or uncertain
evidence refuses. A caller's approval flag is not a decision record. Ordinary
development review, plan approval and merge CI remain.

The [candidate contract](../../contracts/release-candidate.v1.md) binds public
source provenance, compiled products, exact notes/artifacts, actual decisions,
receipts and original ship time. Target: strictly under 30 minutes from the
ship instruction through verified install/update, including approval waits,
queueing, checks, builds, publication and download. Record preparation
separately. A blocked run stays incomplete; a slow run records a miss. One light
actual observation suffices; fixtures do not prove live timing.

No private export script, standalone export review, final-diff approval,
export plan, mandatory hands-on/device step, second publish instruction or
per-step publishing approval is a human gate on this path. Private-to-public
release copying stays stopped, except specifically assigned O16 work.
`release/openwiz/RELEASING.md` stays frozen; historical backfill keeps its
separate gate.

Live checks keep their approved kits, throwaway targets, counts, allowlists and
spending bounds, run early, and publish in strict order. Ship infers no broader
App grants, account effects, spending, activation or machine authority. Releases
stay immutable; no force-push; protected-source and merge rules hold; unsafe
retries after uncertain writes refuse. Incomplete evidence returns a block
without a watcher, polling loop or sleep.

Source: Jake, 2026-11-10: confirmed public-source on-demand shipping after
cut-over, with ship and exact changelog approval as the only human release
actions, automatic gates, bounded risk checks and a light under-30-minute
ship-to-install observation ([private record](https://github.com/jparker2006/ClosedWiz/issues/2183#issuecomment-6757029416)).
