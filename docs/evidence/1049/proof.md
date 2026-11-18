# MT13 proof and scope

The timing gate is replaced by the orchestrator's 2026-11-17 ruling on
OpenWiz #1049 (comment 6963822660): bound this read to 60 seconds, preserve
Unknown on timeout or failure, continue publishing, and log the read's seconds.
The first late-day private publish after its pin moves will measure the landed
read. No runner timing or live published chart is claimed here.

| Claim | Boundary and evidence | Readiness |
| --- | --- | --- |
| A collected value reaches the published chart | `test_charts.py` published-snapshot case; fixture capacity 15.00; inherited red-page.log | Available, synthetic |
| A slow read cannot stall the publish beyond its 60-second read budget | Same gather-to-page path, fake reader completing after 65 seconds; red-timeout.log before the cutoff | Available, synthetic |
| A failed read leaves throughput Unknown and page generation continues | Gather-to-page failure case, unavailable fact and visible Unknown labels | Available, synthetic |
| One line reports the read's seconds | Each gather-to-page case checks the complete timing log | Available, synthetic; not runner evidence |
| Saved snapshot is scanned, allowed, replaced and removed when absent | `test_publish.py` saved-snapshot case and inherited red-publish.log; planted credential, invalid schema and extra filename | Available, local bare origin only |
| The chart is visible | Synthetic page image, drawn through the existing publisher | Available locally; live screenshot remains unverified |
| Required CI passes | Required checks at the pushed head | Produced by CI after PR creation |

No later ticket is blocked by MT13; no new seam is needed. The collector v1
snapshot and its existing chart reader remain the boundary.

## Scope accounting

- `gather.py`: only the published chart's collector read, its bounded execution,
  seconds log and saved snapshot handoff, under comment 6963822660.
- `publish.py`: owned snapshot scan and allowed filename; exactly three
  `chart_builder` lines and four `render` lines under comment 6934512796.
  The inherited three-line `SNAPSHOT` naming block is removed; literal names
  are inside those authorized lines. No other publisher logic changes.
- `test_charts.py`: the published-snapshot page cases only.
- `test_publish.py`: the inherited saved-snapshot case only.
- J110: `docs/evidence/1049/**` contains synthetic failing-first logs and proof.
- #819 comment 6903311310 and J110: one wildcard row for that evidence folder
  in `tools/open-import/paths.json`, beside sibling evidence rows. No existing
  row changes. No dependency, workflow, contract or permission changes.

Every test's catches statement appears in the PR. No tests are deleted.
No helpers were used for this narrow takeover; no reviewer was started.
Both inherited commits remain unchanged, including the original first-push
receipt recorded on the ticket.

## CI integration expectation correction

[Grant 6965460285](https://github.com/openwizdev/OpenWiz/issues/1049#issuecomment-6965460285)
covers exactly one line in `tools/war-room/test_gather.py`,
`Gather.test_the_full_gathered_selection_publishes_with_real_chromium`:
add `snapshot.json` to the expected published filenames. No other line in that
test changes. This supports the owned gather handoff and saved-snapshot
publisher behavior and restores the CI gate while retaining exact equality
and every existing page/image assertion.

The integration check reproduced the CI failure at its file-list assertion
before the correction and passed afterward, including both real-Chromium
layouts and the rest of the existing checks. Both runs are in `green.log`; the
red was committed before the correction. No new or deleted test (#687): the
existing integration test continues to catch missing or unexpected published
files and broken complete-page rendering. No runner timing is inferred.
