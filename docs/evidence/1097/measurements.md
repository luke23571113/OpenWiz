# C8 measurement checkpoint

Approval: spec #780 revision 4, [comment 6966973244](https://github.com/openwizdev/OpenWiz/issues/780#issuecomment-6966973244),
fingerprint `09364d968dd0c2532f8297841e1f77f7ff691d6427d3abe8722f24c65294b704`.
This is an implementation checkpoint with a mandatory measurement gap. It does
not establish an adequate planted Rust budget or unblock #783.

## Original failure

[Run 44190068127 attempt 1](https://github.com/openwizdev/OpenWiz/actions/runs/44190068127/attempts/1),
head `7d599a5fc3b0b85ef23a31686010bd4773b0af3d`, Rust-export job
[134417717261](https://github.com/openwizdev/OpenWiz/actions/runs/44190068127/job/134417717261),
ran from 2026-11-17T22:28:08Z to 23:24:24Z. Its check-run annotation reports
exceeding the 56m0s maximum execution time; its conclusion is cancelled. The
observed 3,376 seconds includes shutdown time. It is excluded from completed
budget samples.

Attempt 2's Rust-export job ran from 2026-11-18T00:08:26Z to 00:16:33Z and failed
in the new-thread target before planted proof. Its 487 seconds are excluded
from completed planted samples. The separate failure is tracked in #1107. No
Rust test was changed, and neither #1094 nor closed proof #1050 was rerun.

## Collection and provenance

Native read-only `gh api` calls listed all 615 completed `ci.yml` runs available
at collection, created 2026-11-14T03:17:38Z through 2026-11-18T01:54:55Z.
Each available latest-attempt `ci-selection-<attempt>` artifact was read and its
`ci-dispatch.json` checked against the SHA-256 of the accompanying
`ci-selection.json` and that selection's run/attempt identity. The run was read
again to reject changed attempts. Counts: 468 normal, 25 trace-only, 5 planted,
117 unknown (no matching dispatch artifact). These are execution-mode counts,
not a claim that every requested workload completed. Unknown modes were not
guessed from branch names or successful combined trace/planted uploads.

Only the 30 identified traced/planted runs needed duration reads for this
repair. All their latest-attempt jobs were read, then run identity/status was
rechecked. A broad duration collection was stopped after narrowing this read;
it produced no table and contributes no samples. No raw job logs, runner names,
product session data or credentials are published here.

[observations.json](observations.json) records the five actual planted dispatches
and each relevant job's eligibility. Four runs had both flags true: planted
execution takes precedence. Source URLs identify dispatch artifacts; run links
identify the Actions records used for duration reads (`started_at` through
`completed_at`). Cancellation and early workload failure never establish a
completed planted duration. Failure after a workload reaches its record upload
can still count, preserving C1's completed failure rule.

## Planted measurements and gaps

The window contains five planted runs, created 2026-11-14T03:17:38Z through
2026-11-17T22:26:26Z; only each latest attempt counts, as C1 requires.

| Job | Eligible samples | p95 seconds | Timeout minutes | Source / readiness |
| --- | ---: | ---: | ---: | --- |
| always | 4 | unknown | 13 | existing limit retained, unmeasured; one more completed sample needed |
| web-build | 5 | 81 | 5 | own planted samples; measured |
| rust-export | 1 | unknown | 56 | existing limit retained, unmeasured; four more completed samples needed |
| web-export | 4 | unknown | 75 | existing limit retained, unmeasured; one more completed sample needed |
| rust | 0 own | unknown | 56 | existing limit retained, unmeasured; own evidence or an approved same-mode twin is missing |
| web | 0 own | unknown | 75 | existing limit retained, unmeasured; own evidence or an approved same-mode twin is missing |

The five web-build durations are 68, 72, 81, 69 and 50 seconds. Nearest-rank p95
of five is 81 seconds. `ceil(1.5 * 81 / 60) = 3`, so the floor sets 5 minutes.
[planted.samples.json](planted.samples.json) holds those observations and the
other completed planted observations, including their mode and provenance.
Only the sufficiently sampled web-build row claims measured p95. TSV p95 `0`
with source `unmeasured` means unknown, not a measured zero-second workload.

The sole completed planted Rust-export workload is
[43586844977 attempt 1](https://github.com/openwizdev/OpenWiz/actions/runs/43586844977/attempts/1):
4,233 seconds (70m33s). It exceeds 56 minutes, but **one observation is not a
five-sample p95**. No wider timeout is inferred from it. The other latest
attempts are early failures or cancellation; counting them as complete would
understate the workload. The remaining planted runs are
[43550871140](https://github.com/openwizdev/OpenWiz/actions/runs/43550871140),
[43556797470](https://github.com/openwizdev/OpenWiz/actions/runs/43556797470),
[43568492229](https://github.com/openwizdev/OpenWiz/actions/runs/43568492229), and
[44190068127 attempt 2](https://github.com/openwizdev/OpenWiz/actions/runs/44190068127/attempts/2).

[Builder question](https://github.com/openwizdev/OpenWiz/issues/1097#issuecomment-6967279066):
measurement owner/path needed for sufficient completed observations, without
rerunning #1094/#1050, reducing the sample minimum or applying an exception.
`needs-info` is set beside `ready-for-agent`. A passing ordinary CI run cannot
replace this missing measurement or prove an adequate planted Rust timeout.

## Corrected trace-only provenance

The original C1 fallback rows combined traced and planted samples. Removing the
four planted runs from that original window leaves 23 trace-only runs, created
2026-11-14T20:40:28Z through 2026-11-15T20:01:10Z. No newer duration is substituted
for this correction. [traced-samples.json](traced-samples.json) records the
23 own observations for each affected measured job and their dispatch sources.

| Job | p95 seconds | Samples / runs | Formula budget minutes |
| --- | ---: | ---: | ---: |
| always | 520 | 23 / 23 | 13 |
| web-build | 81 | 23 / 23 | 5 |
| rust-export | 2,126 | 23 / 23 | 54 |
| web-export | 812 | 23 / 23 | 21 |

Rust and web retain C1's already approved trace-only export-twin derivations.
Normal rows and all unrelated job/Privacy rows stay byte-identical. The six
workflow edits are timeout lines only. Test selection, upload conditions,
sharding, signing, jobs/events/concurrency, runners, required checks, contracts
and dependencies are unchanged.

## Proof readiness

- Fixture test: independent 600/1,800/3,600-second normal/traced/planted durations
  give 15/45/90-minute budgets. The original collector pooled the last two,
  reporting traced p95 3,600 seconds with ten samples and no planted row.
  Committed red: [red.txt](red.txt), commit `9b75eef`.
- Fixture test: the old budget CLI accepted a legacy combined timeout with no
  planted row. The fixed CLI refuses it, mode-misattributed provenance, incomplete
  samples and each mode's mismatched timeout. It also accepts a fully valid
  independent table. Source counts, formula, rounding, floor, matrix maximum,
  fallback/shape filters and Privacy inventory retain their owning C1 proofs.
- Fixture test: actual workflow expressions select planted, traced and ordinary
  branches independently, including both flags true and equal real limits.
  Committed red: [timeout-red.txt](timeout-red.txt), commit `66b33a8`.
- Fixture test: missing dispatch artifacts, hash/attempt mismatch, failed lanes,
  ambiguous combined uploads, early failures and attempt mismatch do not supply
  fabricated planted samples. Existing trace-step inference coverage is replaced
  by actual-dispatch and ambiguity coverage: a combined upload no longer claims
  to distinguish traced from planted.
- Live observation: saved public Actions records establish the counts and gaps
  above; they do not supply the missing completed workloads.
- Independent review: pending the selected reviewer and an eligible hand-back.
- Required CI at the checkpoint head: pending PR execution; no corrected-budget
  planted success is claimed. The final measured budget and corresponding proof
  remain missing. This checkpoint is not a completed C8 hand-back.

The first PR CI run [44226086889](https://github.com/openwizdev/OpenWiz/actions/runs/44226086889)
failed in the carriage guard before planning: its seven new evidence paths were
unclassified. The owning registry row `docs/evidence/1097/**` is added to
`tools/open-import/paths.json` under the standing own-row allowance in
`docs/agents/fleet.md` (Supporting edits, item 1). This covered supporting edit
serves CI3-B's evidence and validation criterion; it supports the owned
`docs/evidence/1097/` folder and adds no broader class or protected-rule change.
The actual guard is rerun at the amended head. No Actions rerun is requested;
a normal branch push starts its next CI run.

No helpers were used. No new dependency or file under `tools/ci-bench` was added.
This is infrastructure work; `no-changelog` applies.
