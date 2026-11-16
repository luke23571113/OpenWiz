# CI3's measure, version 1 (`ci3.v1`): the time to a PR's result

CI improvement 3 (spec #780) watches one number: how long a pull request
waits for its result. This contract defines it once, with the cohort, the
numbers reported beside it, the record it is reported in, and the ways to game
it that are forbidden. [`tools/war-room/ci3.py`](../tools/war-room/ci3.py)
computes it; [`docs/ci3.md`](../docs/ci3.md) holds the BEFORE record and every
later point.

Authority: spec #780, confirmed and its plan approved by Jake on 2026-11-15
(CI3-A; [private record](https://github.com/jparker2006/ClosedWiz/issues/325#issuecomment-6902453888)),
from question #693's decision ([public answer](https://github.com/openwizdev/openwiz/issues/693#issuecomment-6902302112)).
There is no target number and no done point: a better number is only ever
reported, never required.

## Words

| Word | Meaning here |
| --- | --- |
| **PR head** | One commit that was a pull request's head: the commit it opened at, and each commit pushed to its branch while it was open. A pull request into `main` with three pushes has four heads at most (its opening commit and three pushes; a commit seen twice counts once) |
| **Clock start** | When the commit became the PR's head: its push, as GitHub's repository activity records it (`push`, `force_push` or `branch_creation`), or the PR's opening when the commit was pushed before the PR was opened. Never a run's creation: the wait from push to run is part of the result's time |
| **Required checks** | The checks `main`'s ruleset requires today: `ci` (the `ci` job of `.github/workflows/ci.yml`) and `privacy` (the `privacy` job of `.github/workflows/privacy.yml`). A change to the set is a new version |
| **A check's result** | The first `pull_request` run of the check's workflow on that head created at or after its clock start, and in it, the check's job in the run's **latest attempt**: its conclusion and completion. A later run on the same head (a PR's text edited, marked ready) is not that head's result. A rerun is a later attempt of that run, so the rerun's result is final and all of its time counts. A completed run whose check never reported (cancelled before the job existed) stands for the check with its own conclusion and the end of its last job (its last update when it has none) |
| **The head's result** | Every required check has its result. Its outcome is `success` when all are green, `failure` when any is red (failed, timed out, start-up failure), else `cancelled` |
| **Time to the result** | The last required check's completion minus the clock start, in seconds |
| **Missing** | A head without a result: its push isn't in the activity (`push time unknown`), a required workflow has no run on it (`no run`), or its run hadn't finished when collected (`unfinished`) |

## The measure

**CI3: the time to a PR's result is the p50 and p95, by nearest rank (the
⌈p × n⌉-th smallest), of the time to the result of every PR head whose clock
starts in the window**, in minutes to one decimal, with the window, the
cohort and its counts.

The cohort rules:

1. **Every PR head counts.** A head is in the window when its clock starts at
   or after `since` and before `until`; its result may come later.
2. **Red, cancelled and rerun results stay in.** A red result's time is a
   result's time. A head superseded by a new push before its result keeps its
   cancelled result. A rerun's extra time is part of the result's time.
3. **Missing results are listed, never dropped.** Each one is named with its
   pull request, head and reason, and counted.
4. **Collect after the window has settled.** A head still running is missing
   as `unfinished`; read the window again later rather than leaving it out.

## Beside it

Reported beside the measure, never instead of it:

- **Each outcome's own p50 and p95** (success, failure, cancelled), so a
  crowd of fast reds (a draft head fails at once) can't pass for speed.
- **The merge queue's result:** for every merge group whose first run is in
  the window, from that run's creation to the last required check's result on
  the group's head, at p50 and p95, with its outcomes and missing groups.
- **Runner minutes:** every job's time on a runner, started to completed, in
  every attempt of every run counted above (PR heads and merge groups), in
  total and per day. A job that never got a runner (none, and no steps)
  counts none. Each execution counts once: a rerun of failed jobs lists the
  earlier attempt's jobs again, and only the attempt that ran a job (its
  `run_attempt`) counts it.
- **The critical path's buckets:** for every result, the jobs its last
  required check waited on, among the jobs its latest attempt ran itself
  (not those carried from an earlier attempt): the check's job (for a check
  that never reported, the attempt's last job; with no job, the path is
  empty and the whole time is waiting), then the job that finished last
  before it was created, and so on back. Each job's steps split into **setup** and **running** by the
  war room's step table (`tools/war-room/steps.tsv`: `setup` rows are setup,
  every other category is running; a job's time no step covers is setup), a
  step the table doesn't name is **unclassified**, and **waiting** is the
  rest of the result's time: push to run, job created to started, the gaps
  between jobs, and any earlier attempt and the wait for its rerun. The four
  add up to the result's time exactly. Reported as each bucket's share of
  the total and its p50 and p95 over the results.

## The record

`ci3.py measure` prints one JSON object, `openwiz.ci3.v1`, with sorted keys:

| Field | What |
| --- | --- |
| `schema` | `openwiz.ci3.v1` |
| `measure` | `ci3.v1`, this contract's version |
| `label` | The point's name (`BEFORE`, `AFTER 2026-11-23`), or `null` |
| `since`, `until` | The window, UTC |
| `collected_at` | When the runs were read |
| `required_checks` | `["ci", "privacy"]` |
| `heads`, `prs` | The cohort: PR heads in the window, and their pull requests |
| `result` | The measure: `p50_minutes`, `p95_minutes`, `timed` (heads with a result), `outcomes` (`success`, `failure`, `cancelled`, `other`), `by_outcome` (each outcome's `p50_minutes`, `p95_minutes`), `with_reruns` |
| `missing` | Every head without a result: `pr`, `head` (or `null`), `reason` |
| `critical_path` | `results`, and for `waiting`, `setup`, `running`, `unclassified`: `share`, `p50_seconds`, `p95_seconds` |
| `merge_queue` | The same fields as `result`, plus `groups` and `missing` (a count) |
| `runner_minutes` | `pr_heads`, `merge_queue`, `total`, `per_day` |

A value with no sample is `null`, never 0. The same window file always prints
the same record: `measure` reads no clock and no network.

The public record ([`docs/ci3.md`](../docs/ci3.md)) carries these numbers,
aggregates and counts only. Raw window files, run ids and job records stay
private.

## How it is read

`ci3.py collect` reads GitHub only through the CI bench's reader (`bench.py`'s
`gh` and `pages`: `gh api <path>`, a GET, complete pages checked against
their `total_count`): the pull requests into `main` updated in the window,
each branch's repository activity, each head's runs of the two required
workflows with every attempt's jobs, and the merge-group runs created in the
window. A read it can't trust stops it (`ci3: <what>`, exit 1, nothing
written), including a branch with 100 or more activity entries, which one page
can't hold, and **a pull request from a fork** in the window: its pushes
aren't in this repository's activity, so its heads can't be listed, and a
cohort without them would look complete. Such a window has no CI3 number
until a later version can read fork heads.

## Gaming it

None of these may make the number better. A point whose improvement comes
from one of them is not an improvement, and the record says so:

- **Removing or skipping a test** without a named keeper of what it checked
  (the test rule, #687).
- **Retries,** of a test, a step or a job, or reruns that hide a red result.
- **Wider timeouts.**
- **Narrowing selection** without a planted proof that the selector still
  catches a real change (C5, #783).
- **Moving a check out of the required set,** or out of the workflows this
  measure reads.
- **Changing the cohort:** excluding pull requests, heads, outcomes or
  windows, timing from anything but the clock start above, or adding heads
  made to finish fast (a fast red is still a result, and shows in
  `by_outcome`).
- **Changing this definition** inside version 1.

## Versions

A change to anything that moves the number (the clock start, the required
checks, a check's result, the cohort, the percentile rule) is a new version,
`ci3.v2`, in a new file, and **restarts the BEFORE record**: points of
different versions are never compared. Wording that changes no number keeps
the version.
