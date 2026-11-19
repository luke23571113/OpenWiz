# The installed first hour through a verified merge (#2204)

P5 of #2194: the installed-consumer journey extended from a running first fleet
through independent review, CI and a merge read back from GitHub, with #2222's
fault cases rerun on it, and the bounded live kit's offline checks. Synthetic
throughout; every document is a `recording` or a test fixture, never a pass.

```sh
python3 -I tools/install/tests/first-hour/test_journey.py   # the journey and its fault cases (about 90 s)
python3 -I tools/install/tests/first-hour/test_kit.py       # the live kit's offline proofs
python3 -I tools/install/tests/first-hour/kit.py dry-run [<eligibility.json>]
python3 -I tools/install/tests/first-hour/test_first_merge.py   # #637: the 0.0.16 receipt on the journey and its kit (about 2 min)
python3 -I tools/install/tests/first-hour/first_merge_kit.py dry-run [<eligibility.json> [<binding.json>]]
```

CI runs the first two suites from `tests/checks/skills.rs` (`install_journey_and_live_kit_pass`) and the
0.0.16 suite there too (`setup_onboard_journey_passes`, and `release:setup-onboard-journey`).

| File | What |
| --- | --- |
| `journey.py` | One attempt. It runs #1109's install journey (`../journey/test_journey.py`) unchanged, swapping only its conversation for `first-hour.json`, then the join: the tick's starts land on a recording CloudRoom (a fake `room-cli thread list`) and a recording GitHub (#1108's fake gh world); at each step the **installed** `runtime/skills/launch-fleet/scripts/fleet.sh spec` decides what is due (review, then merge, then the archive and the next ticket), reading those providers. It builds the attempt's first-hour `result` document and one `recovery` document per fault case. |
| `first-hour.json` | The recorded conversation: one fresh small idea on the owner's own selected repository (the one setup prepared, not the demo), separate spec confirmation and plan approval, and the user's explicit harness, model, effort and Cloud choice, with the other-family reviewer's sign-in explained before the plan. |
| `test_journey.py` | The proofs. Every expected code is written by hand from the first-hour rules below; #2200's checks (through #2222's `providers/codes.py`) give the actual ones. `KnownWaysToFail` reruns the attempt with one realistic bug each (a blind merge retry, a restart that starts the reviewer again, red CI, a stale verdict). |
| `kit.py`, `test_kit.py` | The offline dry run, eligibility check and result validator of [first-hour-live-kit.md](../../first-hour-live-kit.md). |
| `providers/` | #2222's recording and fault providers (its own folder). |
| `first_merge_kit.py`, `test_first_merge.py` | #637: the 0.0.16 kit's offline dry run, eligibility check and receipt validator (first-hour-live-kit.md's 0.0.16 extension), and the proofs of it and of the journey's recording receipt. Fixtures: `tests/fixtures/first-hour/setup-onboard/`. |
| `evidence/` | #637's red runs. |

## Evidence and validation

The [schema](../first-hour-contract/first-hour.schema.json) and
[cross-field checks](../first-hour-contract/check.py) read a strict JSON
`openwiz.first-hour.v1` document. A `result` records the whole attempt.
A `recovery` records one fault, including retained work, operation identity,
effect counts and reconciliation. Unknown reads stay unknown. Recovery must
preserve prior work and resolve uncertain effects by read-back before any
retry. Use the [synthetic examples](../../../../tests/fixtures/first-hour/README.md)
for established codes and verdicts.

The first-hour clock starts at opening the public install instruction and
ends at GitHub's read-back of the first verified merge. It includes waits and
help, with a limit of 3,600,000 ms. Recorded stages require their own evidence,
including the user's saved spec and plan approvals, independent review,
required checks and the merged head. A live pass also requires a candidate
binding, private evidence pointer and settled gates. The ten-minute fleet
measure and the 0.0.16 receipt have separate verdicts.

The three gates are `cloudroom_setup` (#2201), `paid_offer` (the
[free-only offer decision](../../../../docs/decisions/public-offer.md), settled
by #2293) and `feedback` (#2203, settled by #2292). Settled gates require evidence
from their approved and merged producers. The `paid_offer` field records the
free-only copy and review. Fixtures and recording providers supply synthetic
evidence only.

## The fault cases on this journey

Each compares the owner's work before and after (setup and onboarding records
by the SHA-256 of their canonical JSON, the branch's head, the commit's tree,
each pending intent's id and request fingerprint) and the providers' effect,
call and read-back counts:

| Case | Seam on the installed journey |
| --- | --- |
| `repeat_approval` | The approved launch confirmed again through the installed onboarding helper: no second tick, no second builder |
| `process_restart` | The fleet thread stops after CloudRoom started the reviewer, before its record; on restart it reads the thread back by title first and starts nothing again |
| `revoked_access` | The App's installation removed: GitHub refuses the merge with no effect; the installed setup check says `app_revoked`; reconnecting reads `app_verified` |
| `lost_reply` | The merge's reply lost after its effect: the pull request is read back (merged at the approved head) before anything else; no second merge |
| `update_rejected` | A tampered update through the actual install entry after the merge: refused, the last good build stays, the setup, onboarding record and merged branch unchanged |
| `setup_interrupted` | The installed runtime's access setup (`runtime/access/access.py` and its store) on the journey's own state, with #2222's recording access provider: stopped before any reply, resumed with the same operation id |

**Named gaps (PR4 stays unproven).** `browser_restart` and the same-tab draft
cases need the installed server and page, which #1109's synthetic bundle
replaces with inert programs; their contract-seam proof stays #2222's.
`removal_default` has no owner on main yet (install.v1 leaves removal to later
tickets), as #2222's ruling records. The result names both under its PR4 gap.

**What the result shows.** Every stage is verified on recorded evidence except
`connections`: setup reports the harness only as listed, which is not a usable
login, so it stays `unknown`. The clock is unknown (a recording measures no
time), PR1 and PR2 stay with #2207's live run, and the `cloudroom_setup` gate is
unresolved. The `paid_offer` and `feedback` gates name their verified producers
#2293 and #2292; this journey does not exercise their flows.

**Proof limits.** Fixtures prove the join's gating, effects and recovery, never
a real release, account, login, elapsed time or live behaviour.

## The 0.0.16 receipt on this journey (#637)

The same attempt also yields setup-onboard.v1's `first_merge_receipt`
(`Attempt.first_merge()`), bound to the SHA-256 of its exact `result` text,
its candidate, repository and merge read back at the reviewed, green head.
It never relabels the result: the hour keeps `3600000` and the ten-minute
measure stays `unmeasured`, each with its own verdict.

- **Owner actions, one entry each.** The recorded conversation's own turns
  (typed choices, the grill's confirmation, the spec confirmation, the plan
  approval, the launch's spending approval) and, at Connect, every installed
  tool's `--yes` (prepare, init, the App skip), the App's Create and Install
  stand-in, each owner step of the installed key route (the App tool's
  `--capability`: six for the protected paste) and the owner's merge of the
  brain pull request. A stand-in is `agent_for_owner` and counts like a tap.
  The App path logs 19, the skip path 12: both fail the five-action limit
  (`actions_exceeded`), which this recording reports rather than hides.
- **The fleet start** (`Attempt.fleet_start()`): CloudRoom's fleet-thread
  spawn, launch-fleet's fleet record on the spec with its 10-minute loop, and
  the engine log (absent). A known way to fail, `tick_start`, runs
  `openwiz fleet tick` beside the fleet thread; the kit refuses it.
- **Key faults** (`key_faults()`): the installed App tool's capability on this
  state with no, a full, a foreign-id and a key-only delivery, and with a
  stand-in agent-side store, which stays `agent_save_unavailable` (the no-paste
  route is Unverified until the real CloudRoom contribution is observed). A
  run without the key refuses to register a second App; the owner's work is
  compared before and after (`refused_access`).
- **The public-companion check** (`companion_check()`): installed init on a
  copy of this state for public code, its companion creation's reply lost
  once, then resumed: one private companion, linked (`lost_reply`).
- **The skip-App continuation** is its own attempt (`{'skip_app': True}`).

Its primary attempt still carries #2204's planted fault cases; the live kit's
primary timed run has none (first-hour-live-kit.md, F1 to F13).
