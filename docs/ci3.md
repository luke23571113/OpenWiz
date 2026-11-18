# CI3: the time to a PR's result

The record for CI improvement 3 (spec #780), measured as
[`ci3.v1`](../contracts/ci3.v1.md) defines it: from a PR head's push to the
final result of every required check on it (`ci` and `privacy`), green or red,
at p50 and p95. Aggregates only. BEFORE first; each later point is added below
it, dated, with the same fields. There is no target: the record says whether
the number moved, and why.

## BEFORE: the 2026-11-15 audit window

| | |
| --- | --- |
| Window | 2026-11-14 03:17 to 2026-11-15 17:16 UTC (38 hours), the CI-speed audit's window on #693 |
| Cohort | 65 PR heads of 36 pull requests; 65 with a result, **0 missing** |
| Outcomes | 50 success, 14 failure, 1 cancelled; no reruns |
| Read | 2026-11-15 23:52 UTC, after every head's result had settled (first read 22:46 UTC; read again after the review's fixes to unallocated and carried jobs and fallback buckets: every number unchanged) |

| Number | p50 | p95 | n |
| --- | ---: | ---: | ---: |
| **Time to a PR's result (CI3)** | **22.4 min** | **50.9 min** | 65 |
| Green results only | 23.5 min | 27.8 min | 50 |
| Red results only | 18.7 min | 63.6 min | 14 |
| Merge-queue result (first run to last required check) | 23.9 min | 26.9 min | 43 groups |

The p95 is red: the slowest results are the window's first PRs, each running
as one single-shard job until it failed (the audit's cause 5, the 60 to 90
minute timeouts). Green results alone sit at 27.8 minutes; they match the
audit's own first-full-result count (22.6 and 27.5 minutes), which used run
creation, not the push, as its start and left reds out.

**Critical path** (the jobs each result waited on):

| Bucket | Share | p50 | p95 |
| --- | ---: | ---: | ---: |
| waiting | 1.3% | 12 s | 51 s |
| setup | 4.4% | 57 s | 105 s |
| **running** | **94.2%** | 1,281 s | 2,918 s |
| unclassified | 0.1% | 0 s | 1 s |

Running is the biggest bucket: the tests themselves, not queues or setup.

**Runner minutes:** 8,878 in the window (5,008 on PR heads, 3,871 in the merge
queue), 5,610 a day. That counts only the `ci` and `privacy` runs above;
pushes to `main`, nightly runs and other workflows are outside the measure.

**Reproduce it:**

```sh
python3 tools/collector/ci3.py collect --since 2026-11-14T03:17:00Z --until 2026-11-15T17:16:00Z --out WINDOW.json --workers 4
python3 tools/collector/ci3.py measure WINDOW.json --label BEFORE
```

The window file holds run ids and job records: it stays private. A later read
of the same window can differ only if GitHub's records changed (a rerun, a
deleted run), and the record then says so in its counts.

<details><summary>The BEFORE record (<code>openwiz.ci3.v1</code>)</summary>

```json
{
  "collected_at": "2026-11-15T23:52:51Z",
  "critical_path": {
    "results": 65,
    "running": {
      "p50_seconds": 1281,
      "p95_seconds": 2918,
      "share": 0.942
    },
    "setup": {
      "p50_seconds": 57,
      "p95_seconds": 105,
      "share": 0.044
    },
    "unclassified": {
      "p50_seconds": 0,
      "p95_seconds": 1,
      "share": 0.001
    },
    "waiting": {
      "p50_seconds": 12,
      "p95_seconds": 51,
      "share": 0.013
    }
  },
  "heads": 65,
  "label": "BEFORE",
  "measure": "ci3.v1",
  "merge_queue": {
    "by_outcome": {
      "cancelled": {
        "p50_minutes": 6.4,
        "p95_minutes": 6.4
      },
      "failure": {
        "p50_minutes": 19.9,
        "p95_minutes": 26.1
      },
      "success": {
        "p50_minutes": 23.9,
        "p95_minutes": 26.9
      }
    },
    "groups": 43,
    "missing": 0,
    "outcomes": {
      "cancelled": 1,
      "failure": 2,
      "other": 0,
      "success": 40
    },
    "p50_minutes": 23.9,
    "p95_minutes": 26.9,
    "timed": 43,
    "with_reruns": 0
  },
  "missing": [],
  "prs": 36,
  "required_checks": [
    "ci",
    "privacy"
  ],
  "result": {
    "by_outcome": {
      "cancelled": {
        "p50_minutes": 25.1,
        "p95_minutes": 25.1
      },
      "failure": {
        "p50_minutes": 18.7,
        "p95_minutes": 63.6
      },
      "success": {
        "p50_minutes": 23.5,
        "p95_minutes": 27.8
      }
    },
    "outcomes": {
      "cancelled": 1,
      "failure": 14,
      "other": 0,
      "success": 50
    },
    "p50_minutes": 22.4,
    "p95_minutes": 50.9,
    "timed": 65,
    "with_reruns": 0
  },
  "runner_minutes": {
    "merge_queue": 3870.7,
    "per_day": 5609.7,
    "pr_heads": 5007.5,
    "total": 8878.2
  },
  "schema": "openwiz.ci3.v1",
  "since": "2026-11-14T03:17:00Z",
  "until": "2026-11-15T17:16:00Z"
}
```

</details>

## C13: speed, spend, overload and waiting (#463)

C13 (#463, formerly ClosedWiz #2320) asked Jake to review actual speed, spend,
overload and shared-read evidence together. Spec #780 folds it into this
record (Jake, 2026-11-15, CI3-A;
[private record](https://github.com/jparker2006/ClosedWiz/issues/325#issuecomment-6902453888)).
Under the move to OpenWiz's free hosted runners, it reads:

- **Speed:** the time to a PR's result is 22.4 minutes at p50 and 50.9 at
  p95 (green only: 23.5 and 27.8), and the merge queue's 23.9 and 26.9, all
  above. C13's old bar (median under 10 minutes, p90 under 20) is not met,
  and CI3 sets no target in its place (spec #780, out of scope).
- **Runner minutes and their cost:** 8,878 runner minutes in the window,
  5,610 a day, on GitHub's standard hosted runners (OpenWiz is public).
  GitHub's billing usage for the organisation, read on 2026-11-15 at 22:48
  UTC for November so far: 19,796 OpenWiz minutes (19,631 Linux, 126 Linux
  slim, 39 macOS), $120.46 at list price, **all discounted: $0.00 billed**;
  the organisation's other repositories add 82 Linux minutes, also $0.00.
  Billing comes a day at a time, so its minutes include runs the measure
  doesn't count (main pushes, nightly, other workflows) and GitHub's
  per-job rounding up to a minute. At list price the window's measured
  minutes would be about $34 a day; they cost nothing while public minutes
  stay free.
- **Overload and waiting:** waiting is 1.3% of the critical path, 12 s at
  p50 and 51 s at p95, so the hosted runners were not overloaded for PRs.
  The only real waiting the audit found was main pushes queued behind each
  other, which #749 removed (main pushes now run only the light check).

**Out of scope under C3** (spec #780: no paid runners, no new dependency):
C13's whole-bill spending guard and the single $60 ceiling, the free-first
paid fallback and its alarms, the App installation and its shared
installation-read observation, and any paid or third-party runner. They
stay unbuilt; the cost line above is the billing read, not a guard. The
monthly 50,000-minute alert is the weekly loop's (#784).
