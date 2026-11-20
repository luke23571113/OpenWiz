# Skill A/B: offline controls and analysis

EB8-O (#2235, spec #1383). Offline, synthetic controls only. #2179 owns the real inputs, the frozen protocol, the method review and any live result. Nothing here grants live, paid-eval, spending, activation, release, publishing or merge authority.

## Controls

`tools/war-room/experiments/controls.py` reads validated EB5 bundles and journey v1 snapshots. It collects nothing and starts nothing. Missing or unknown facts refuse; there is no override.

- `launch_check(bundle, journey, at=..., safeguards=...)`: checks injected facts (research, CF4, replay, reviewed preregistration, its live approval) before the fixed horizon.
- `assign(..., ticket, at=..., eligible=True, safeguards=...)`: odd tickets get the candidate, even the old arm, with the frozen arm revision and protocol hash. Refuses earlier builder work, first push, verdict or merge. An exact repeat returns the same assignment; deviations append, never rewrite.
- `advance(before, before_journey, after, journey, at=...)`: takes new event snapshots, checks immutable history and computes harm.
- `handback_check(..., record, current, at=..., safeguards=...)`: joins the precheck to the arm's exact CF4 result keys. `ready` means offline conformance only, never a review.

## Harm stops

- **Doubled rounds:** the mean count of independent verdicts per assigned PR with a verdict in `(event_time - window_hours, event_time]`, against `mean >= 2 * rounds_reference`; exposure counts distinct assigned tickets. Helpers and `duplicate_of` verdicts never count. The window, reference and minimum exposure come from the frozen protocol.
- **Red main:** an attributable `main-red` event stops its arm; timing alone is not attribution.
- A stop is terminal and survives restart. A completed stage (`pass`, `fail`, `stopped`, `inconclusive`) takes no more assignments; there is no resume command.

## Commands

```sh
python3 -I tools/war-room/experiments/run.py init \
  --bundle SYNTHETIC_BUNDLE.json --journey SYNTHETIC_JOURNEY.json \
  --checkpoint SYNTHETIC_CHECKPOINT.json
python3 -I tools/war-room/experiments/run.py assign \
  --checkpoint SYNTHETIC_CHECKPOINT.json --ticket 4301 \
  --facts SYNTHETIC_FACTS.json --at 2030-01-05T00:00:00Z
python3 -I tools/war-room/experiments/run.py advance \
  --checkpoint SYNTHETIC_CHECKPOINT.json --bundle NEXT_SYNTHETIC_BUNDLE.json \
  --journey NEXT_SYNTHETIC_JOURNEY.json --at 2030-01-06T00:00:00Z
python3 -I tools/war-room/experiments/run.py analyze \
  --checkpoint SYNTHETIC_CHECKPOINT.json --at 2030-02-01T00:00:00Z
```

Assignment facts hold exactly `eligible` and `safeguards`; safeguards holds exactly `holds_clear`, `independent_review_required`, `required_ci` and `verified_merge_required`, each true. `check --checkpoint FILE` only reads. The checkpoint is written atomically under an exclusive lock with the expected prior digest; a leftover lock is inspected, never cleared by age.

## Analysis

`analysis.power_plan(power, guards)` uses `ceil(2*(z_alpha+z_power)^2*SD_hours^2/effect_hours^2)`, at least the largest guard minimum (alpha .05, power .8, SD 3 h, effect 2 h gives 36; the EB5 guard example raises it to 72). `analysis.analyze(bundle, journey, at=...)` keeps every assigned ticket in its arm and derives counts from the journey. Supported method names, exact:

| Field | Supported value |
| --- | --- |
| `primary.statistic` | `restricted-mean-hours-v1 tau=24` (positive finite numeric tau, in hours) |
| `primary.test` | `bounded-mean-hoeffding-v1` |
| `primary.unfinished` | `right-censor-at-horizon; closed-unmerged=tau; all-assigned` |
| `primary.missing` | `unknown-effect; censoring-bounds; parity-is-not-random` |
| `guards.rounds.test` | `welch-independent-rounds-v1` |
| `guards.defects.test` | `bonferroni-wilson-risk-difference-v1` |

- **Time:** the mean of `min(first-push-to-merge hours, tau)`. Open or closed-unmerged work is right-censored at the horizon (journey v1 has no closure time), bounded by partial identification and widened by `tau*sqrt(log(2/alpha)*(1/n_old+1/n_candidate)/2)` ([Hoeffding, theorem 2](https://repository.lib.ncsu.edu/bitstreams/d0e6ed15-3e1c-432f-8419-e55ffb6f3171/download)).
- **Rounds:** Welch-Satterthwaite t interval; fewer than two observations per arm or zero variance is unknown ([NIST](https://www.itl.nist.gov/div898/handbook/prc/section3/prc312.htm)).
- **Defects:** Wilson intervals at `z(1-alpha/4)`, combined into a Bonferroni risk difference ([NIST](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm)).

Improvement needs EB5's rule unchanged: enough n, known timing, mature follow-up, time upper bound below zero, both guard upper bounds at most zero, widths within bounds and no material deviation. A positive guard lower bound is harm; anything else is inconclusive.

## Verification

```sh
python3 -I tools/war-room/experiments/test_controls.py
python3 -I tools/war-room/experiments/test_analysis.py
python3 -I tools/war-room/experiments/test_checkpoint.py
```
