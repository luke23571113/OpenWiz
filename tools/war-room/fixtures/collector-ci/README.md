# Collector CI fixtures (MT3, #822)

Synthetic only: the repository, run, job, PR and head numbers, times, labels
and rate-limit values are made up and assert nothing about a real repository.

| File | What it is |
| --- | --- |
| `github.json` | Every `gh api` answer the CI facts read, as `[key, answer]` pairs |
| `fake_gh.py` | The synthetic `gh` the tests put on `PATH`: it answers `gh api PATH` from `github.json`, never the network |
| `red-first.log` | The tests against the red-run stub, before the collector was built |
| `red-mutations.log` | The two proofs added later, each against the collector with its rule broken |
| `red-review-r1.log` | Review round 1's R1 and R2 proofs, before their fix |
| `green.log` | The same tests passing on the built collector, and the contract suite |

A key matches its path exactly, or, when it ends in `?` or `&`, as the path's
prefix; the first match answers. `{owner}/{repo}` resolve from `GH_REPO`, as
gh's own placeholders do, so a reader that forgets to pin the repository fails.
An answer `{"sequence": [A1, A2, ...]}` gives the n-th ask of its path An
(and the last one after that), so a test can move GitHub on between two reads.
The tests point `OPENWIZ_COLLECTOR_STORE` at a private temporary store and read
the kept job records and CI3 window back from it.
The last two keys answer every other `ci.yml` and `privacy.yml` run listing
with a complete read of nothing.

The same answers feed the collector, ci-bench (`bench.py collect` and
`measure`, as `daily.sh` runs them), CI3 (`ci3.py collect` and `measure`) and
the overload guard (`alarm.py`), so the tests compare their numbers on one
source. The worked values below are the tests' independent expectations.

## `runs` and `minutes`: the window [2026-01-04T00:00:00Z, 01:00:00Z)

| Run | Event, result, created | Jobs (runner, started to completed) |
| --- | --- | --- |
| 501 | pull_request, success, 00:00:00 | 5011 `rust` on `ubuntu-24.04`, 00:01:00–00:07:30 (`Run cargo test --workspace` succeeds); 5012 `web` on the PC, 00:00:30–00:04:30 (`Run npm test`) |
| 502 | pull_request, success, 00:10:00 | 5021 `rust` on `ubuntu-24.04`, 00:11:00–00:20:00 |
| 503 | push, failure, 00:30:00 | 5031 `rust` on `ubuntu-24.04`, 00:31:00–00:33:20 (fails) |
| 505 | pull_request, success, 01:00:00 | none read: the API's `created` range includes its end, the window does not |

- **`runs`:** 3 runs, 4 jobs. Code runs (push or pull request, succeeded, a
  code step succeeded): 501 and 502. Queued to done, from the run's creation
  to its last job: 501 is 7.5 minutes, 502 is 10.0. Median 8.75; nearest-rank
  p90 of two is the second, 10.0; max 10.0.
- **`minutes`:** `ubuntu-24.04` is `github-hosted`, the PC `self-hosted`.
  Runner minutes: 6.5 + 9 + 2.3333 = 17.8333 hosted, 4.0 self-hosted. Billed
  (each hosted job rounded up to a whole minute): 7 + 9 + 3 = 19, and 4.
  From `tools/ci-bench/prices.tsv`: 19 × $0.006 = **$0.114**; the PC is $0.
  Per code run: (7 × 0.006 + 9 × 0.006) ÷ 2 = **$0.048**. Nothing unknown.
- **Broken-timing variant** (a test makes job 5031, of the failed run 503,
  end at 00:30:59, before its 00:31:00 start): `unknown_jobs` is 1, its
  minutes are unknown, so `unknown_minutes` and `window_usd` are null and the
  fact is `partial`; the 15.5 hosted and 4.0 PC minutes are kept.
- **Unpriced variant** (a test relabels job 5031 `macos-14`): its 2.3333
  minutes are kept under `unknown`, `unknown_minutes` is 2.3333, `window_usd`
  is null and the fact is `partial`; the code runs are still $0.048 each.

## `ci3`: the window [2026-01-05, 2026-01-06)

`tools/ci-bench/test_ci3.py`'s fake GitHub, unchanged but for the repository:
PR #9 opens at 10:05:00 on head 1 (pushed 10:00:00) and is pushed head 2 at
11:00:00. Head 1's `ci` finishes 10:20:30: 930 seconds. Head 2's `ci` fails,
is rerun and finishes 11:42:00: 2520 seconds. So 2 heads, 2 timed, p50 15.5
and p95 42.0 minutes, 1 with reruns. A test empties head 2's `ci.yml` runs:
the record lists it in `missing` (`ci: no run`) and the fact is `partial`.

## `activity` and `queue`: active runs, 2026-01-05 12:00–12:04

| Run | Workflow, event, status | Jobs (status, created, started, pool) |
| --- | --- | --- |
| 7101 | `ci.yml`, pull_request, in progress | 8101 queued 12:03:20, `ubuntu-24.04`; 8102 in progress 12:02:00, started 12:02:30, the PC; 8103 completed 12:00:00, started 12:00:10 |
| 7102 | `privacy.yml`, merge_group, queued | 8201 queued 12:04:00 |
| 7103 | `privacy.yml`, push, in progress | 8301 in progress 12:01:00, started 12:01:05 |

- **`activity`** is `ci.yml` only: run 7101, its three jobs, no completed run
  to price, and the creation times of its active jobs 8101 and 8102.
- **`queue`** is the guard's cohort: both workflows. Required means a job of
  a pull request or merge group run's current attempt, so every job but 8301
  (a push) is required. Unix seconds: 12:00:00 is 1767614400, 12:00:10 is
  1767614410, 12:01:00 is 1767614460, 12:01:05 is 1767614465, 12:02:00 is
  1767614520, 12:02:30 is 1767614550, 12:03:20 is 1767614600, 12:04:00 is
  1767614640. REST 4000 of 5000 and GraphQL 4800 of 5000, both resetting at
  4102444800 (2100-01-01).
- Job 8101 has waited far past 900 seconds, so the guard escalates. With the
  queued jobs taken out, the guard is `healthy` 60 seconds after the read and
  `unknown` (stale) at 61. With one job page unreadable too, the observation
  is incomplete and the guard says `unknown`. A job of another attempt than
  its run's (8301 as attempt 2 of run 7103's attempt 1) is kept, not
  required, and leaves the observation incomplete. So does a run that appears
  between the two run enumerations that bracket the job reads (run 7104,
  listed in progress only the second time), or a job that appears between a
  page's two reads (job 8104).
| `green-move.log` | Revision 4's move (#822's second pull request): every war-room suite that now reads the moved ci-bench code, passing |
