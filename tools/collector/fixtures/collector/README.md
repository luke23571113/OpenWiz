# Collector fixtures (MT1, #820)

Synthetic only: the repository, PR, ticket, run, job and comment numbers,
times, heads, hashes and prices are made up and assert nothing about a real
repository. `aaaa…` source hashes are synthetic placeholders. Three carried
values are other fixtures' JSON, unchanged, and their `source.sha256` is
those files' real hash, so a reader can check the binding:

| Carried value | From |
| --- | --- |
| `stage_waits.value.journey`, `sidecar`, `bench` | `tools/collector/fixtures/stage-waits/journeys.json`, `stage-waits.json` and `bench.json` (TL2's demonstration). `source` hashes the sidecar; `limits` hashes `tools/collector/limits.conf` (byte-identical to the retired factory-metrics copy). `journey.validate_stage_waits(sidecar, journey)` accepts them, and `journey.stage_bench(sidecar, limits.read(limits.conf))` equals the carried bench |
| `activity.value.current.cost`, `read-minutes-partial.json`'s `minutes` | `bench.costs` on synthetic jobs, priced from the real `tools/collector/prices.tsv` as `bench.read_prices` reads it (its `unknown` row has null rates) |
| `journeys.value.document` | `tools/war-room/fixtures/rework/journeys.json` (WR6's three-PR cohort plus one) |
| `ci3.value` | `python3 tools/collector/ci3.py measure tools/collector/fixtures/ci3/window.json` (no label), worked by hand in [its README](../ci3/README.md) |

## Files

| File | Form | What it is for |
| --- | --- | --- |
| `snapshot.json` | `openwiz.war-room.collector.v1` | One full collection at 2030-03-01T12:05:00Z: every fact, known or partial. The page's input (MT2, MT3, MT4) |
| `snapshot-unavailable.json` | `openwiz.war-room.collector.v1` | Every fact unavailable, each with its own prerequisite: a page with nothing read stays grey, never zero |
| `read-stall.json` | `openwiz.war-room.collector.read.v1` | The stall alarm's on-demand read at a 12:04:00Z tick (MT5) |
| `read-queue.json` | `openwiz.war-room.collector.read.v1` | The overload guard's on-demand read (MT6) |
| `read-ci3.json` | `openwiz.war-room.collector.read.v1` | The CI3 loop's on-demand read of a settled window (MT7) |
| `read-minutes-partial.json` | `openwiz.war-room.collector.read.v1` | A `minutes` fact with one job's timing unavailable: known minutes kept, totals unknown (MT3) |
| `red-review-r1.log` | log | Review round 1's fixtures against the schema before its fix: each of R2–R5 refused at its own rule |

## Worked values in `snapshot.json`

The windowed facts cover the UTC day 2030-02-28.

- **`merges`:** 3 PRs over all bases: #4201 (01:15, `main`, no ticket,
  direction unknown), #4202 (02:20, `main`, ticket 14, forward), #4203 (04:30,
  `release-0.0.9`, ticket 15, backwards). Into `main`: 2.
- **`prs_per_hour`:** 4 successful code runs at 12.0 robot-minutes each on 3
  robots: 3 × 60 ÷ 12.0 = **15.0** PRs an hour of capacity. Merged into
  `main`: 2 ÷ 24 = 0.083333 an hour. Baseline: 3 × 60 ÷ 10.0 = 18.0.
- **`stalls`:** ticket 14's `findings sent` gap 02:30–04:00 (90 minutes: 30 in
  hour 02, 60 in hour 03) and ticket 15's `review started` gap 05:00–05:45
  (45 minutes, hour 05): 90 + 45 = **135** idle minutes. #4201 closes no
  ticket, so it is unlinked. Partial: history is unknown.
- **`cost`:** Actions 12 minutes, $0.60; Claude $3, GPT $6, sandbox $3. A
  reader's factory total is $0.60 + $3 + $6 + $3 = $12.60, and over the 3
  merges $4.20 each (factory-metrics' own worked example).
- **`runs` and `minutes`:** 6 completed `ci.yml` runs, 14 jobs, 4 code runs;
  queued-to-done median 9.5, p90 14.0 minutes. 60 runner minutes (40 GitHub,
  20 PC); 41 billed GitHub minutes × $0.006 = **$0.246**; the PC is $0.
- **`open_prs`:** see `read-stall.json` below (the same four PRs).
- **`activity`:** today so far, `ci.yml` only: run 7100's job 8000 completed
  (10 minutes on GitHub's Ubuntu: 10 billed × $0.006 = **$0.06**,
  `cost_jobs` [8000]); run 7101's job 8001 queued since 12:03:20 and job 8002
  running on the PC since its creation at 12:02:00.
- **`queue`:** job-8001 queued at 12:03:20 and job-8002 running (both
  `ci.yml` run 7101), and job-8004 queued at 12:04:00 (`privacy.yml` run
  7102, which `activity` does not cover), read to 12:04:50, so `fresh_until`
  is 12:05:50. REST 4000/5000, GraphQL 4800/5000.

## `read-stall.json`: two alarms

The tick is 12:04:00Z. `merges` for `[11:04, 12:04)` is a complete read of
nothing.

- **No merges:** #4210 has `VERDICT: APPROVE` at its head, `ci` succeeded at
  that head, the rollup is green and it is `MERGEABLE`, and nothing merged in
  the hour: the alarm fires.
- **Idle agent:** #4211's latest fleet record is `findings sent` at its
  current head, at 10:50: 74 minutes old, at least 60: the alarm fires.
- #4212 is a draft: neither alarm counts it.
- #4213's rollup is null (no check has reported): it is not eligible for the
  no-merge alarm, but its `findings sent` record at its head is 66 minutes
  old, so the idle-agent alarm fires for it too.

## `read-minutes-partial.json`: unknowns kept

One job ran 10.5 minutes on GitHub's Ubuntu (billed 11); another job's timing
is unavailable. `runner_minutes` keeps the 10.5 and `billed_minutes` the 11.
`unknown_minutes` is null, because the unknown job's minutes are themselves
unknown. `window_usd` and `per_code_run_usd` are null, and the fact is
`partial`. `prices` keeps the table's `unknown` row with null rates.

## `read-queue.json`: the 60-second bound

The read ends at 12:10:02Z, so `observed_at` is 1898597402 and `fresh_until`
12:11:02Z. One required job has queued since 12:08:00 (1898597280); one
running job is not required. Write `ci.queue.value.observation` to a file and
give it to the guard unchanged:

| Guard `--now` | Age | Result |
| --- | --- | --- |
| 1898597462 | 60 s | `healthy`, exit 0: allowed; the required job has waited 182 s |
| 1898597463 | 61 s | `unknown`, exit 1: refused and paused, the observation is stale |

Both rows were run against `tools/ci-overload/alarm.py --action merge-batch`
with a fresh temporary state each.

## Checking a fixture

Each fixture conforms to `collector.v1.schema.json` under the war room's own
stdlib checker:

```sh
python3 -I -c 'import importlib.util as u, json, sys
s = u.spec_from_file_location("suite", "tools/collector/suite.py"); m = u.module_from_spec(s); s.loader.exec_module(m)
schema = json.load(open("tools/collector/collector.v1.schema.json"))
for path in sys.argv[1:]:
    doc = json.load(open(path))
    m._shape(doc, schema if doc["schema"].endswith("collector.v1") else schema["$defs"]["read_envelope"], schema)
    print("conforms", path)' tools/war-room/fixtures/collector/*.json
```

Conformance is shape only. The contract's cross-field rules (read bounds,
the 60-second `fresh_until`, sums and ratios) are each collector module's to
check (MT2, MT3).
