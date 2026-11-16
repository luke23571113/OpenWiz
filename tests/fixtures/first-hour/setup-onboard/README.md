# 0.0.16 first-merge kit fixtures (#637)

Synthetic documents for the offline proofs of the 0.0.16 extension of the
[first-hour live kit](../../../../tools/install/first-hour-live-kit.md), read by
`tools/install/tests/first-hour/test_first_merge.py`. Every value is invented:
pointers name the synthetic private comment `ClosedWiz/issues/1`, digests are
repeated hex, and the repository, times and ids are made up.

**Shape only.** Their `live` proof class is a label on invented values, so the
validator's positive path can be exercised. It is never an observation, a
measured time, a real account, an approved authority or an upstream capability.
No file here may be offered as a live result: a real receipt comes only from
T9 #639's run under T8 #638's exact authorization.

| File | What |
| --- | --- |
| `result.json` | A first-hour.v1 `result`: #2200's synthetic `recording-complete` example (`../README.md`) with its times scaled so the merge lands at 29 min 59 s, relabelled `live` with a pointer and every gate settled |
| `receipt.json` | A setup-onboard.v1 `first_merge_receipt` bound to the exact bytes of `result.json` (its SHA-256), the same candidate, repository, merge, waits and help, and five owner actions: the App's Create and Install, the spec confirmation, the plan approval and the launch's spending approval, on the `agent_save` route |
| `fleet.json` | An `openwiz.first-merge-kit-fleet.v1` fleet start: one launch-fleet fleet thread, its 10-minute per-spec loop, no engine activation or tick start |
| `binding.json` | An `openwiz.first-merge-kit-binding.v1` binding for that run, with its test-owned cleanup |
| `eligibility.json` | An `openwiz.first-merge-kit-eligibility.v1` record: graph, the seven producers' synthetic verified merges, one pointer per authority scope and an observed upstream save |

The tests change copies of these and rebind the receipt's SHA-256 as a real run
would; expected codes and refusals are written by hand from the contracts and
the kit.
