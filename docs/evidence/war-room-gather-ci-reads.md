# War-room gather: bounded parallel CI activity reads (#1027)

`bench_reads.current_activity` now reads up to four `ci.yml` runs at once
(`WORKERS = 4`, fixed). Every per-run read and check is kept: both jobs
enumerations and their equality check, the run reread, and the outer run-list
enumerations before and after. Results merge in run order. Request volume is
unchanged.

## Controlled replay (synthetic, no live read)

[`tools/war-room/fixtures/activity/replay.py`](../../tools/war-room/fixtures/activity/replay.py)
builds one synthetic day of 259 runs (the count in the gather profile behind
the ticket): 207 completed today with six jobs each, 52 active with three. Each
request sleeps a latency fixed by its path and read number alone, spread over
0.35–1.15 s (the observed live range) times `--scale`. Parent and head
therefore wait for exactly the same requests. Same sandbox, Python 3.11.2; within each
pair parent and head ran one after the other. Scaled runs 1–3 ran while the
full-latency parent run was sleeping in another process; their times match
run 0's.

- Parent: `origin/main` at `83ecddd`, `tools/war-room/bench_reads.py` written out with `git show`.
- Head: this pull request's `tools/war-room/bench_reads.py`.

| Latency | Version | Activity seconds | Requests | Runs | Jobs | Priced jobs | Most in flight | Result sha256 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ×0.02 (7–23 ms), run 0 | parent | 11.93 | 783 | 259 | 1398 | 1242 | 1 | `66e4eb9d…` |
| ×0.02, run 0 | head | 3.08 | 783 | 259 | 1398 | 1242 | 4 | `66e4eb9d…` |
| ×0.02, runs 1–3 | parent | 11.94, 11.94, 11.93 | 783 | 259 | 1398 | 1242 | 1 | `66e4eb9d…` |
| ×0.02, runs 1–3 | head | 3.08, 3.08, 3.08 | 783 | 259 | 1398 | 1242 | 4 | `66e4eb9d…` |
| ×1 (0.35–1.15 s), one run | parent | 588.29 | 783 | 259 | 1398 | 1242 | 1 | `66e4eb9d…` |
| ×1, one run | head | 151.38 | 783 | 259 | 1398 | 1242 | 4 | `66e4eb9d…` |

Every run is listed; none was dropped or retried. Activity-phase wall time is
3.9× lower with four workers at both latencies (588 s to 151 s at the
observed one), against the ticket's 2× target, with identical results (same sha256 over the whole observation: runs, jobs, cost job ids and
cost) and the same 783 requests (2 outer enumerations × 3 pages + 259 × 3).

UTC bounds: scaled pairs 2026-11-16T13:56:36Z–13:58Z; full-latency parent 2026-11-16T13:56:57Z–14:06:46Z, head 14:06:46Z–14:09:17Z.

## Limits

- **No live gather pair.** This build ran no live read, so the ticket's
  budget-checked live baseline/head pair on a GitHub runner (P3) is not
  measured. The end-to-end gain on a live gather is unknown until it is.
- The replay measures the activity phase only. The rest of a gather is
  unchanged; total gather time falls by at most the activity phase's saving.
- **The hourly API-budget risk is not solved.** Requests per gather are the
  same; four workers spend them up to four times faster. Rate-limit and read
  failures still refuse the observation as before (no retry was added).
