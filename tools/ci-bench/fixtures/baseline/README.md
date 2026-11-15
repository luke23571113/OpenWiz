# Synthetic baseline (#677)

A **synthetic** stand-in for the historical baseline, so `test.py`'s `Baseline`
case and every test that needs a baseline point run from the public checkout
alone. Every value here is invented: no run, job, PR number, runner or time
came from a real CI account. The historical baseline and its results stay
private and are not reproduced or claimed here.

`jobs.jsonl`, `merged.json` and `window.json` are the inputs `bench.py measure`
reads. `point.json` is the expected result without `cost` and `buckets`,
typed in by hand from the arithmetic below, never written by `bench.py`.

## Assumptions

- Window 2030-02-01 00:00:00Z to 03:00:00Z (3 hours), 3 robots, label
  `2030-02-01 baseline` (date-shaped, so charts show `Baseline Feb 1`).
- Step names are rows of `../../steps.tsv` as it stands; the rules are
  `bench.py`'s own (code runs and the reconstructed rule), unchanged.
- Runner names are `synthetic-runner-N`; jobs carry no `run_created_at`, so
  queued-to-done starts at the run's first job created.
- Values are rounded to 4 places; none of the values below lands on a
  rounding tie.

## The runs (seconds unless said)

| Run | Event, result | Code run? | Reconstructed? | Why |
| --- | --- | --- | --- | --- |
| 201 | pull_request, success | yes | yes | `Run npm test` succeeded, 360 s |
| 202 | push, failure | no: failed | yes | `Run npm test` lasted 120 s (any result) |
| 203 | pull_request, success | yes | no | `Run npm run build` succeeded; no `npm test` |
| 204 | schedule, success | no: not push/PR | no | only `cargo test` |
| 205 | pull_request, success | yes | no: exactly 10 s | `Run npm test` 10 s, not more than 10 |
| 206 | pull_request, cancelled | no | no | one job that never got a runner |

6 runs, 8 jobs (201 has 3). 4 PRs merged in 3 hours: 4 / 3 = 1.3333 an hour.

- **201** web-test: created 00:00:00, runner 00:01:00 to 00:08:00: waits 60,
  runs 420. Steps: Set up job 20 (setup), Run npm test 360 (web), Complete job
  10 (setup); 390 covered, 30 uncovered. rust: waits 30, runs 300 (00:00:30
  to 00:05:30). Steps: Rust 1.99.1 30 (setup), cargo test 240 (rust), The
  docs-only classifier 20 (skills; setup under the reconstructed rule); 290
  covered, 10 uncovered. web-test-shard (1): skipped, no runner, no steps,
  shown 30 s long: no robot time and no waiting. Queued to done 00:00:00 to
  00:08:00 = 8 min.
- **202** web-test: no wait, 180 on the runner. Steps 30 setup, 120 npm test
  (failed), 17 setup = 167 covered. Queued to done 3 min.
- **203** web-build: waits 120, runs 180. Steps 15 setup, 120 + 30 build,
  15 setup; all covered. Queued to done 5 min.
- **205** web-test: no wait, runs 70. Steps 20 setup, 10 npm test, 20 setup;
  20 uncovered. Queued to done 70 s = 1.1667 min.

## Successful code runs (201, 203, 205): whole runner time, denominator 3

- Robot time 720 + 180 + 70 = 970 s; 970 / 3 / 60 = 5.38889 = **5.3889** min a run.
- PRs an hour: 3 x 60 / (970 / 180) = 32400 / 970 = 33.40206 = **33.4021**.
- Categories (sum / 180): setup 100 + 30 + 60 = 190 = 1.05556 = **1.0556**;
  build 150 = **0.8333**; rust 240 = **1.3333**; skills 20 = **0.1111**;
  web 360 + 10 = 370 = 2.05556 = **2.0556**. 190 + 150 + 240 + 20 + 370 = 970.
- Split: waiting 60 + 30 + 120 = 210 = **1.1667**; setup **1.0556**;
  running 970 - 190 = 780 = **4.3333**.
- Queued to done 8, 5, 1.1667: median **5.0**; p90 by nearest rank,
  ceil(0.9 x 3) = the 3rd of 3, **8.0**; max **8.0**.

## Reconstructed rule (201, 202): step time only, denominator 2

- Robot time 680 + 167 = 847 s (uncovered time not counted); 847 / 120 =
  7.05833 = **7.0583** min a run.
- PRs an hour: 3 x 60 / (847 / 120) = 21600 / 847 = 25.50177 = **25.5018**.
- Categories (sum / 120): setup 20 + 10 + 30 + 20 (classifier) + 30 + 17 =
  127 = 1.05833 = **1.0583**; web 360 + 120 = 480 = **4.0**; rust 240 =
  **2.0**; build **0.0**; skills **0.0**. 127 + 480 + 240 = 847.
- Split: waiting 60 + 30 + 0 = 90 = **0.75**; setup **1.0583**; running
  847 - 127 = 720 = **6.0**.
- Queued to done 8 and 3: median **5.5**, p90 (2nd of 2) **8.0**, max **8.0**.

## Run 202 with its npm test passing (#701)

`test.py`'s second `Baseline` case changes one value in a copy of
`jobs.jsonl`: run 202's `Run npm test` step succeeds. The run itself still
failed, so it is still not a code run: **3** code runs, 720 + 180 + 70 =
**970** s, as above. Counting the failed run would give 4 runs and
970 + 180 = 1150 s. The reconstructed rule takes any result: still 201 and
202, **847** s.
