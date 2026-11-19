# War room collector contract v1

MT1 (#820), spec #819. `openwiz.war-room.collector.v1` is the one form in
which the war room's collector gathers the factory and CI facts, and
`openwiz.war-room.collector.read.v1` is the on-demand read each reader uses.
The war-room page, the CI3 loop, the stall alarm and the overload guard all
read these facts instead of reading GitHub and CI on their own.

Authority: spec #819, confirmed and its plan approved by Jake on 2026-11-15
([private record](https://github.com/jparker2006/ClosedWiz/issues/325#issuecomment-6902677303)).
This contract **extends** the war room's record contracts,
[`contract.md`](contract.md) (v1) and [`contract.v2.md`](contract.v2.md), and
replaces neither: saved v1 and v2 samples, their 17 slots, their three health
slots and every rule in them are unchanged. The collector is the layer under
them that the page's providers, and the three small readers, are built from.

This ticket writes the contract, its [schema](collector.v1.schema.json), its
synthetic [fixtures](fixtures/collector/README.md) and the inventory below. It
implements no collector: MT2 (#821) gathers the factory facts, MT3 (#822) the
CI facts. Nothing here is a live observation.

## Words

| Word | Meaning here |
| --- | --- |
| **Fact** | One named thing the collector gathers, with its read bounds, its own time (a point or a window), its freshness, its source and its value. The registry below names each one |
| **Snapshot** | One complete collection: every fact once, saved as one `openwiz.war-room.collector.v1` document. The five-minute collection and the hourly publish use it |
| **On-demand read** | A fresh read of named facts, now, for one reader: an `openwiz.war-room.collector.read.v1` document. Never served from a saved snapshot |
| **Carried fact** | A fact whose value is another producer's own validated record, kept unchanged (the same JSON value that producer wrote) (TL2's stage sidecar and bench, the journey document, the CI3 record, WR8's current CI observation). The collector adds the read, time and freshness around it; it never recomputes the record |

## The snapshot

```json
{"schema": "openwiz.war-room.collector.v1", "repository": "OWNER/NAME",
 "collected_at": "UTC", "factory": {"<fact>": FACT, ...}, "ci": {"<fact>": FACT, ...}}
```

- `repository` is the one repository every fact was read from.
- `collected_at` is the collection's end: at or after every fact's
  `read.ended_at`. It is the collection's identity, never a fact's time.
- `factory` holds exactly `merges`, `prs_per_hour`, `stage_waits`, `stalls`,
  `open_prs`, `journeys`, `cost` and `flow`; `ci` holds exactly `runs`, `minutes`,
  `ci3`, `activity` and `queue`. Every fact is present, in a snapshot, even when it could
  not be read: an absent source is an `unavailable` fact with its
  prerequisite, never a missing key and never zero. A snapshot written before
  FM2 may omit `flow`. Readers treat that omission as unavailable.
- A failed fact greys only itself; the others are kept. A privacy hit in any
  read refuses the whole collection, as gather does today (WR10).

## A fact

Every fact has exactly these fields:

| Field | Meaning |
| --- | --- |
| `fact` | Its registry name |
| `state` | `known`, `partial` or `unavailable`, with v1's meaning |
| `read` | `{started_at, ended_at}`: the collector's actual read bounds, or null when nothing was read |
| `point` | The source's own point time, or null |
| `window` | v1's half-open native window `{since, until, timezone}`, or null; never both `point` and `window` |
| `fresh_until`, `freshness` | The validity bound and `fresh`, `stale` or `unknown`, as in v1 |
| `source` | Sanitized path, schema and SHA-256 of the retained observation bytes, as in v1 |
| `evidence` | GitHub links, in v1's allowed forms |
| `prerequisites` | What is missing; empty only when `known` |
| `value` | The fact's own payload (below), or null |

General rules, the same as v1 and v2's and checked by each collector module
for its own facts (the schema checks only the shape):

- `known`: a value, no prerequisites, a read, a source, a point or window,
  and evidence links unless the value is a complete read of nothing (no PR
  merged, no job queued). `partial`: prerequisites and a value. `unavailable`:
  a null value and prerequisites. Unknown is never encoded as zero.
- `read.started_at <= read.ended_at <= collected_at` (or the read envelope's
  completion, below). A `point` lies inside `read`; a `window.until` at or
  before `read.ended_at`.
- No raw comment bodies, logs, transcripts, credentials, thread ids or usage
  keys in any field. Numbers keep the rounding of the tool that produces them
  today, so MT2 and MT3 can compare red first on the same fixtures.
- A carried fact keeps its producer's own `read` and evidence: a snapshot may
  carry the latest CI3 record, read days earlier, and says so by its `read`.

## The facts

| Group | Fact | Time | What | Read today by |
| --- | --- | --- | --- | --- |
| factory | `merges` | window | Every PR merged in the window across **all** base branches: number, time, base, closing tickets and direction | factory-metrics, ci-bench (main only), stall alarm (count in the last hour), war room WR8 |
| factory | `prs_per_hour` | window | ci-bench's headline: PRs an hour of CI capacity (robots × 60 ÷ robot-minutes per successful code run) and merged into `main`, with the baseline | ci-bench, war room `ci_bench` slot |
| factory | `stage_waits` | point | TL2's stage sidecar, the journey it is bound to and its stage bench, carried, with the TL1 limits read that judged it | war room WR3 and `stage_health`, via factory-metrics |
| factory | `stalls` | window | Recorded idle agent-minutes: every fleet-record gap, by hour, with its tickets | factory-metrics |
| factory | `open_prs` | point | Open PRs now: head, draft, base, mergeable, required-check results at the head, the latest verdict and the latest fleet record | stall alarm |
| factory | `journeys` | window | The merged cohort's journey document, carried, with its outcome sidecar | ci-bench trends, war room rework, cost and review loops |
| factory | `cost` | window | One UTC day's Actions billing and CloudRoom usage, by provider and unit | factory-metrics |
| factory | `flow` | point | Ticket and spec cost, time, review rounds, stalls and ticket progress | FM3 stall alarm, FM4 cost line, FM5 war room |
| ci | `runs` | window | `ci.yml`'s completed runs (latest attempt): runs, jobs, successful code runs and their queued-to-done latency | ci-bench, war room `ci_bench` slot |
| ci | `minutes` | window | Runner minutes and billed minutes by runner kind, and the list-rate estimate with its prices | ci-bench, war room cost |
| ci | `ci3` | window | The CI3 measure: [`contracts/ci3.v1.md`](../../contracts/ci3.v1.md)'s record, carried | ci-bench `ci3.py`, `docs/ci3.md` |
| ci | `activity` | window | WR8's current `ci.yml` observation, carried: today's runs, every job with its run, attempt, status and pool, each active job's creation time, and the latest completed jobs' list-rate cost with their job ids | war room `activity` slot and health `ci_queue`, through ci-bench's `current_activity` |
| ci | `queue` | point | The overload guard's observation, exactly: required `ci.yml` and `privacy.yml` jobs and both rate-limit pools, with each job's workflow, run, attempt and pool | overload guard (supplied file) |

### Factory values

- **`merges`:** `pull_requests`, each `{number, merged_at, base, tickets,
  direction}`. Every `merged_at` is in the window; each PR once. All bases,
  as factory-metrics counts; a reader wanting `main` only (ci-bench, the
  stall alarm) filters by `base`. `tickets` are the current same-repository
  closing tickets; `direction` is WR8's current-metadata direction
  (`forward`, `sideways`, `backwards`, or `unknown` when tickets disagree, are
  missing or none link). It is current metadata, never historical evidence.
- **`prs_per_hour`:** `robots` (the stated capacity assumption, as ci-bench's
  `--robots`), `code_runs`, `robot_minutes_per_code_run`,
  `capacity_prs_per_hour` (null with no successful code run), `merged_prs`
  and `merged_per_hour` (into `main`, over the window's hours), and
  `baseline`: the first point every chart is drawn against, with its own
  label, window, robots, numbers and source, or null when no reviewed
  baseline is available (O16: the public baseline needs its own review; the
  private one stays private). Capacity is not merged throughput.
- **`stage_waits`:** `journey` is the `closedwiz.journey.v1` document TL2's
  sidecar is bound to, and `sidecar` is TL2's stage-waits sidecar, both
  unchanged: `journey.validate_stage_waits(sidecar, journey)` checks the
  sidecar and its binding. They keep every native wait endpoint, which
  `stage_waits.py`, `health.stage_health` and the weekly report's
  completion-week assignment read. `bench` is
  `journey.stage_bench(sidecar, settings)` for the settings below, unchanged:
  its endpoints are source ids and durations, so it never stands in for the
  sidecar. `limits` is `{schema, path, sha256, read_at}` of the one TL1
  settings file that judged it, read at or after TL2's `read_at` (v2's rule).
  `point` is TL2's `read_at`; `source` names the sidecar. TL2's history is
  unknown, so the fact is never `known`.
- **`stalls`:** factory-metrics' gap rules, unchanged (its README, "What the
  numbers mean"): `idle_minutes`, `hours` (`{start, idle_minutes}` per whole
  UTC hour of the window), `stalls` (`{tickets, pull_request, kind, from,
  until, minutes, open_at_end}`, longest first), `unlinked_prs`,
  `edited_fleet_comments`, `clock_skew_comments`. Historical completeness is
  unknown, so the fact is never `known`. `open_at_end` is factory-metrics'
  `open_at_midnight`, renamed because the window need not be a day.
- **`open_prs`:** `default_branch`, `base`, `checks` (the required checks
  judged) and `pull_requests`, each `{number, draft, base, head, mergeable,
  rollup, checks, verdict, record}`. `rollup` is the head's status rollup
  (`SUCCESS` is `success`, `FAILURE` and `ERROR` are `failure`, `PENDING` and
  `EXPECTED` are `pending`). An explicit null rollup (no checks have reported
  yet) is `null`, with no `checks`: that PR is never eligible for the
  no-merge alarm, and its verdict and record are kept, so its idle-agent
  alarm still fires. Any other state, or an absent or malformed rollup field,
  fails the read, as the stall alarm does today.
  `checks` are `{name, result}` at the head (`success`, `failure`, `pending`,
  `other`). `verdict` is the latest comment
  starting `VERDICT:` by comment id: `{verdict, head, comment_id, at}`.
  `record` is the latest fleet record by last edit, then comment id, named by
  its record prefix only: `{kind, head, comment_id, at}`. Bodies and thread
  ids are never kept. More than 100 comments or checks on a PR, an unknown
  record prefix, a GraphQL error or a repeated key makes the fact
  `unavailable`, as the stall alarm's read does today.
- **`journeys`:** `cohort` (`window`, `pull_requests`), `document`
  (`closedwiz.journey.v1`, verbatim, checked by `journey.validate`) and
  `outcomes` (EB5's outcome export, verbatim, or null). Journey history is
  unknown, so the fact is never `known`.
- **`cost`:** `date` (the window's UTC day), `actions_billing` (`minutes`,
  `usd`, `reason`: reported hosted minutes and net USD, as factory-metrics
  reads them) and `usage` (`complete`, `claude` and `gpt` as `{tokens,
  credits, usd}`, `sandbox` as `{hours, usd}`, `reason`). Unreported units
  are null. Units are never added to each other or converted. A total or a
  per-merge ratio is a reader's arithmetic over known components, with
  `merges`; any null component leaves it unknown.

### Ticket and spec facts (FM2)

Spec #1165 revision 1 adds the `flow` fact. Its value has `tickets` and
`specs` arrays, ordered by issue number. Each ticket row has its `ticket`
number, its parent `spec` or null, `pull_requests` (same-repository closing
PR numbers), and `state` (`open`, `closed`, `merged` or `unknown`). A failed
link read leaves the PR list empty and state unknown. Each spec row has its
`spec` number, its full `tickets` membership or null, and its `created_at` and
`last_merge_at` times.

Run `collect_factory.py read --repo OWNER/NAME --fact flow` on demand.
`--ticket N` selects just that issue and its linked PRs. `--spec N` selects the
spec and every current same-repository sub-issue, even when some have no
merge. Both options can be repeated and combined. Without either option,
the merge window selects the tickets and the collector expands their parent
specs to full membership. The window selects the default cohort. The
measurements use the full recorded ticket lifetime through the earlier of
its completion or the read's opening point. An unknown or cross-repository
spec membership makes the aggregate unknown. A measured total never silently
drops an unmeasured member.

| Field | Source and unit | Unknown form |
| --- | --- | --- |
| `cost.builder`, `cost.reviewer` | Role-attributed CloudRoom daily export totals in `credits` and `tokens`, from claim day through merge, closure or observation day, inclusive | Null per unit for an absent assignment, date, thread row or reported unit |
| `cost.total` | Builder plus reviewer in each unit. Runner minutes remain a separate unit in the cost record | Null when either same-unit part is null |
| `cost.ci_minutes` | Sum of job start-to-completion seconds divided by 60 for `ci.yml` and `privacy.yml` PR runs, including reruns. A job relisted on a later attempt belongs to its original attempt. Explicit skipped or cancelled jobs with no steps and no runner consumed no runner time. Runs link to the PR by GitHub's association or, when the association is empty, the same repository and branch during the PR lifetime. Recorded queue entries also select merge-group runs with the PR's exact queue ref | Null when a workflow history, job duration or ownership cannot be established. Shared PRs have no ticket-level CI allocation |
| `claimed_at`, `merged_at`, `elapsed_seconds` | Earliest surviving factory builder claim or confirmed-start comment's creation to the last linked GitHub merge | Null for an absent or unusable endpoint or duration |
| `stages_seconds.waiting_to_start` | First GitHub `ready-for-agent` label event to claim | Null without both endpoints |
| `stages_seconds.building`, `stages_seconds.in_review` | One linked PR with a matched review sequence. Building is from claim or the preceding verdict to the next head-matched review request. In review is from recorded start or re-check confirmation to its verdict. Review admission time and time from final approval to queue entry may fall outside those stages | Null when the review sequence cannot be paired through approval of the current head |
| `stages_seconds.in_queue` | Head-matched `merge queued` after approval through GitHub merge | Null without both endpoints |
| `review_rounds` | Surviving independent factory verdicts at their creation time, including re-checks, deduplicated per PR by verdict, reviewed head and body. An edited comment counts when the complete GitHub edit history confirms the verdict line and independent-review marker stayed the same | Null if a PR or recorded review cannot be established. Changed or unreadable verdict history also leaves building, review and queue durations that depend on it null |
| `stall_count` | Number of distinct gaps of at least 30 minutes between successive progress events, bounded by verified claim and merge, with the progress coverage below. Claim and merge are endpoints. FM3 uses the progress fields to supply the active stall list, causes and daily count | Null when the interval or any required progress history is unavailable |
| `span_seconds` (spec) | Spec issue creation to the last member merge | Null without complete membership and a merge for each member |

The spec sums the ticket elapsed and stage seconds, role units and stall
counts. Ticket-seconds can overlap when tickets run in parallel. The spec
counts each associated PR's runners and review rounds once, even when that
PR closes two members. A PR shared outside the spec makes those spec totals
unknown. Missing units remain null independently of other numbers.

Each ticket also has a `progress` object. `commit_at` comes from GitHub
branch-tip activity, or an unedited first-successful-push receipt from a
factory author when that is the only observation. `record_at` comes from
the factory's ticket and PR records and includes observed edits.
`ci_result_at` is the latest observed completion of an associated workflow
attempt. `verdict_at` is the latest observed independent verdict at its
creation time and is null when verdict edit history is uncertain.
`last_observed_at` is the latest verified progress, including observed issue
creation, claim or merge. It remains a lower bound when coverage is incomplete.
Each timestamp is null when unreadable.
`ci_pending` is true when either workflow has an observed pending attempt,
false when both were observed and neither is pending, and null when that
cannot be established. `complete` means the ticket and PR comment pages,
branch-tip chains and associated workflow attempt histories were readable.
Edited factory PR comments also need complete GitHub edit history so an
edited or removed verdict cannot silently shorten that history. If the
history is incomplete, the PR's review evidence and dependent stall count
are unknown. The collector retains no comment revisions.
GitHub's surviving records cannot recover deleted comments. A receipt can
establish an observed push without establishing complete push history.

FM3 (#1171) adds two progress fields for the stall alarm's rule.
`last_record` is the kind of the latest factory record on the ticket and its
linked PRs, by last edit: the lowercase words after `launch-fleet: ` up to the
first head, number, `:` or `,` (such as `asked the orchestrator`, `parked` or
`builder fallback due`). Only the kind is kept. It is null with no record, or
when the ticket or a linked PR could not be read. `gaps` lists each gap of at
least 30 minutes between successive progress events as `{from, until}`, from
the claim to the merge, or to the latest observed event while the ticket is
open, so the current open interval is never one. `stall_count` counts the same
gaps. `gaps` is null without a claim or when `complete` is false, so a ticket
with no linked PR yet has unknown gaps.

To include role usage, pass `--flow-threads FILE` and one or more
`--flow-usage FILE` arguments, or pass `flow_threads` and `flow_usage` to
`collect_factory.read`. Use the existing complete daily usage export format
for each day. The private assignment manifest is an object with a
`repository` and a `tickets` map keyed by decimal issue number. Each entry
contains `builder` and `reviewer` arrays of the usage export's thread keys.
Each key may belong to one ticket and role. Manifest coverage must be
complete for the roles it reports. The collector retains only role totals.
It retains no thread keys, input paths, comment bodies or usage export rows.

### CI values

- **`runs`:** `workflow` (`ci.yml`), `runs`, `jobs`, `unknown_jobs`,
  `code_runs` (ci-bench's successful code-run rule), `latency_basis`, and
  `queued_to_done_minutes` (`median`, nearest-rank `p90`, `max`; null with no
  code run). Only completed runs, latest attempt, as ci-bench reads them.
- **`minutes`:** `bench.costs`' record, with its per-kind maps as lists:
  `runner_minutes` and `billed_minutes` as `[{runner_kind, minutes}]` for
  every job with known timing; `unknown_minutes`, the minutes of jobs with no
  known price (null when a job's timing itself is unavailable, so the unknown
  amount is unknown too); `window_usd` and `per_code_run_usd`, list-rate
  estimates, null when any price or timing is unknown; and `prices`
  (`{runner_kind, compute_usd_per_minute, platform_usd_per_minute,
  source_url, verified_on}`), the table as read, where a rate the table says
  is `unknown` is null. Known runner minutes stay when the totals are
  unknown: such a fact is `partial`. Estimates are not invoices; billing is
  `cost`'s.
- **`ci3`:** the `openwiz.ci3.v1` record, exactly as `ci3.py measure` prints
  it: the measure, its cohort, `missing`, the critical path, the merge queue
  and runner minutes. `window` is the record's `since`/`until`;
  `read.ended_at` is its `collected_at`. The measure, its anti-gaming rules
  and its versions stay CI3's (#780); the collector only carries it. Its raw
  window file stays private: `source` names it by hash. A record with missing
  heads is `partial`, its missing heads listed in the record.
- **`activity`:** `window` is today's UTC day so far (to the read's end);
  `current` is `bench.current_activity`'s output for `ci.yml`, unchanged:
  `runs`, `jobs` (`{id, run, attempt, status, pool}`), `cost_jobs` (the
  completed jobs the estimate covers) and `cost` (`bench.costs`' record for
  them). `created_at` is each active job's `created_at` from the same job
  pages, `{job, created_at}`. This is the cohort the page's `activity` slot
  and health `ci_queue` read: `ci.yml` only, with each job's run and attempt
  for evidence and wait identity, and the cost's sample identities. A failed,
  short or changing page makes the whole fact `unavailable`, never zero.
- **`queue`:** `observation` is the overload guard's input,
  [`tools/ci-overload/README.md`](../ci-overload/README.md)'s shape exactly:
  `repository`, `observed_at` (Unix seconds, the read's end), `complete`,
  `queue` (`complete`, `jobs` of `{id, required, status, queued_at,
  started_at}`) and `budgets` (`rest` and `graphql`, each `{remaining, limit,
  reset_at, retry_after}`). `jobs` names each observation job's `workflow`
  (`ci.yml` or `privacy.yml`), `run_id`, `run_attempt` and exact pool (WR8's
  selectors, or null). `queue` is the guard's cohort, not `activity`'s: it
  adds `privacy.yml` and counts only required jobs. The collector derives it
  separately, in the same read pass, and neither stands in for the other. A job is `required` when it is a job of
  a current attempt of a `ci.yml` or `privacy.yml` pull request or merge
  group run: the required checks `ci` and `privacy` wait on it. A job whose
  run, attempt or requiredness can't be established, a short page or a
  changed total makes `complete` false; it never drops the job. The budgets
  are the shared pools' own `/rate_limit` values and the reader's last
  secondary backoff, never a per-agent allowance.

## Freshness, per fact and per reader

Freshness stays per reader: each reader reads the facts it needs the way its
own bound allows. A snapshot never stands in for a reader's fresh read.

| Reader | Read | Facts | Bound |
| --- | --- | --- | --- |
| Overload guard (MT6) | On demand, before each admission | `queue` | **60 seconds.** `queue.fresh_until` is `read.ended_at` + 60 s, and the guard refuses an observation older than its `--max-age` (default 60) at its own clock. A snapshot's `queue` is for the page only: the guard never reads it |
| Stall alarm (MT5) | On demand, inside its tick and its 40-second read budget | `open_prs`, and `merges` for `[tick − 60 min, tick)` | Read at the tick, never from a snapshot; no source validity bound, so `freshness` is `unknown` and the read's own bounds are its time |
| CI3 loop (MT7) | On demand, for its settled window `[since, until)` | `ci3` | CI3's own rule: collect after the window has settled; an unfinished head is `missing`, never dropped. No age bound beyond that |
| War-room page | The five-minute snapshot, published hourly | every fact | v1's rule: no source validity bound means `unknown`, never fresh. `queue` turns `stale` 60 s after its read, which the page shows honestly |

Only `queue` has a validity bound: the guard's. No other bound is invented.

## The on-demand read

```json
{"schema": "openwiz.war-room.collector.read.v1", "repository": "OWNER/NAME",
 "requested_at": "UTC", "factory": {"<fact>": FACT, ...}, "ci": {"<fact>": FACT, ...}}
```

It holds only the facts asked for (at least one), each exactly as in a
snapshot, read now: every `read.started_at` is at or after `requested_at`,
except a carried fact's. A fact the read could not establish is
`unavailable` with its prerequisite. The schema's `$defs/read_envelope` is its
shape, and `$defs/fact_<name>` each fact's.

**Seams** (signatures fixed here so the readers can be built against them):

- `collect_factory.read(repository, facts, *, since=None, until=None)` (MT2)
  and `collect_ci.read(repository, facts, *, since=None, until=None)` (MT3)
  return a read envelope for the named facts of their group; `since`/`until`
  bound the windowed facts. Each module also exposes `validate(fact)`, the
  cross-field rules above for its own facts.
- `gather.py` (shared by MT2 and MT3) composes one snapshot from both groups.
- CLIs: `python3 -I tools/collector/collect_factory.py read --repo OWNER/NAME
  --fact NAME [--fact NAME ...] [--since UTC --until UTC]`, and the same for
  `collect_ci.py`, print one read envelope and exit 0; a bad command line
  exits 2 before any read; a refused read exits 1 with nothing on stdout.
- The guard's supplier (MT6) writes `ci.queue.value.observation`, unchanged,
  as the guard's `--input`. The guard's thresholds, journal, state and
  refusals stay its own.

## How the page reads it

The page's 17 providers and three health slots keep their v1/v2 shapes. The
collector's facts replace the native artifacts their adapters read today:

| v1/v2 slot | From |
| --- | --- |
| `ci_bench` (merged, capacity, robot-minutes, queued-to-done, list cost) | `merges`, `prs_per_hour`, `runs`, `minutes` |
| `factory_metrics` (merges by hour, idle minutes, stalls, costs) | `merges`, `stalls`, `cost` |
| `stage_waits`, health `stage_health` | `stage_waits` |
| `journey`, `rework`, `cost`, `eb6` | `journeys`, with `cost` and `minutes` for the cost slot |
| `activity` throughput | `merges` (direction) |
| `activity` current CI counts and cost today, health `ci_queue` | `activity` (its cost with `cost_jobs` as the sample; the same day's list-rate estimate, never `minutes`' completed window) |

The slot names `ci_bench` and `factory_metrics` are part of the immutable v1
registry and stay, even after both tools retire: saved samples are never
rewritten. Health `main_ci` and the board, credits, usage, decisions,
answer-time and experiment slots keep their existing sources.

## Fixtures

[`fixtures/collector/`](fixtures/collector/README.md) is synthetic: a full
snapshot, an all-unavailable snapshot, and on-demand reads for the stall
alarm, the guard, the CI3 loop and a partial cost, each with its worked values. Every fixture
conforms to the schema under the war room's own stdlib checker
(`suite._shape`), which is why the schema uses only that checker's
vocabulary (booleans are `true`/`false` constants; objects are closed).

## Inventory A: every fact the four tools read today

Found by reading each tool's sources: every `gh api` path, GraphQL query,
local table and supplied file. Each has its place, or the reason it is
dropped. A drop loses no reader: the last column names who still has it.

### ci-bench

| Read today | Place |
| --- | --- |
| `collect`: `ci.yml` runs created in the window, completed; each run's latest-attempt jobs and steps; the run reread | `runs`, `minutes`, `prs_per_hour` |
| `collect`: closed PRs into `main`, merged in the window | `merges` (base `main`) |
| `current_activity` (read by the war room's WR8 and WRD1): today's `ci.yml` runs, every page of their jobs read twice, each run reread, the completed jobs' timing and labels for the estimate | `activity` (unchanged), and the job pages behind `queue` |
| `measure`: `steps.tsv` (step categories) | A rules table, not a fact. It still classifies CI3's critical path (`contracts/ci3.v1.md`) and `check-steps`; it needs a home before MT8 (see Gaps) |
| `measure`: `prices.tsv` (USD per minute) | `minutes.prices`, the prices each estimate used. The table itself is a rules table, as `steps.tsv` |
| `chart`/`dashboard`: the baseline point (`--baseline`, private by default) | `prs_per_hour.baseline` |
| `factory` (#1359): one GraphQL query (merged PRs into `main`, their comments, closing tickets, label events, ticket comments) for ready-to-merge hours and the first-verdict APPROVE share | **Dropped:** only the CI bench's dashboard read them. `journeys` carries the same cohort's ready-to-merge and independent review rounds (EB1/WR6), which the page already uses |
| `factory`: `main`'s push runs, attempts, jobs and failed-job logs, for main red minutes and reruns by cause | **Dropped:** dashboard only. Current main status is health `main_ci`; reruns are in `ci3.result.with_reruns` and the journeys' CI rework. Log text was never kept |
| `factory`: every attempt's jobs, for runner wait (created to started) | **Dropped:** dashboard only. Current waits are `queue` and health `ci_queue`; the result's waiting is `ci3.critical_path.waiting` |
| `measure`: the waiting/setup/running split per code run, buckets (1 h, 6 h) and the reconstructed rule | **Dropped:** dashboard only. CI3's critical path is the kept split; the reconstructed rule belongs to the baseline point alone |
| `escapes`: `main` push and nightly runs over 31 days, the escape finder's runs, issues since the window | **Dropped:** dashboard only. The finder's issues stay the record (`ci/escapes/`) |
| `trends.py collect`: journeys (`journey.py collect`), the usage export and optional CF4 `score.json` | `journeys` (document, outcomes) and `cost.usage`. CF4 scores stay skills-eval's artifact (the `skills_eval` slot), not a GitHub or CI fact |
| `ci3.py collect`: PRs into `main` updated in the window, each branch's activity, each head's `ci.yml`/`privacy.yml` runs with every attempt's jobs, merge-group runs | `ci3` (the record; the window file stays private) |
| `required.py` (CI2): one private frozen bundle, no GitHub read | Not a collector read: an offline analyzer of a frozen capture. Its home is MT8's call (see Gaps) |

### factory-metrics

| Read today | Place |
| --- | --- |
| `metrics.py`: GraphQL PRs, all bases (`mergedAt`, `closedAt`, closing issues) and every closing-issue page | `merges`, and `stalls`' ticket links |
| `metrics.py`: REST every page of repository issue comments (fleet records) | `stalls` |
| `metrics.py`: `DIRECTION_QUERY` (closing tickets' milestone and labels), used by WR8 | `merges.direction` |
| `metrics.py`: repository owner type, then the daily Actions billing summary | `cost.actions_billing` |
| `metrics.py`: the optional daily CloudRoom usage export | `cost.usage`. Its anonymous per-thread ordinals are **dropped**: only the report's table shows them |
| `journey.py collect`: ticket and PR timelines, labels, comments, each PR branch's `ci.yml` runs and attempts, branch activity | `journeys`, and `stage_waits` with `--stage-waits` |
| `journey.py bench --stage-waits` with `limits.py` reading `limits.conf` | `stage_waits` (`bench`, `limits`) |
| `experiment_contract.py` and `experiments/` (EB5 rules and A/B state) | Not facts: rules modules, imported by skills-eval and run by hand (`docs/agents/skills-ab.md`). Where they live is MT2/MT8's (see Gaps) |

### stall alarm

| Read today | Place |
| --- | --- |
| GraphQL: the default branch; open PRs (draft, base, head, mergeable, last 100 comments, the head's status rollup) | `open_prs`, on demand |
| GraphQL search: PRs merged to the base after the hour's cutoff | `merges`, on demand for `[tick − 60 min, tick)`, filtered to the base |
| `room-cli loop list --json`: the fleet loop's status | Not a GitHub or CI fact: CloudRoom loop status stays the alarm's own read. MT5's "no GitHub read of its own" still holds |

### overload guard

| Read today | Place |
| --- | --- |
| The supplied observation file (`--input`): queue jobs and both pools | `queue.observation`, exactly. Today nothing supplies it (the fleet's guard refuses every run); MT6's supplier reads `collect_ci.read(..., ['queue'])` |
| Its own state and pending journal | Not facts: the guard's durable pause, unchanged |

## Inventory B: every consumer of ci-bench and factory-metrics

Repository-wide search at `main` (`git grep -lI -e ci-bench -e ci_bench -e
factory-metrics -e factory_metrics -e ci-benchmarks`, outside the two tools'
own folders, plus each import of their modules by path): 71 files. Each must
read the war room, or lose its reference, before MT8 (#827) deletes the
tools. "MT8" means the path is in MT8's owned paths; **not owned** means no
ticket of #819 owns it yet.

| Consumer | What it uses | Owner |
| --- | --- | --- |
| `.github/workflows/ci-bench.yml` | Runs both tools' tests, `check-steps`, `daily.sh`; its path filter names both folders | MT8 |
| `.github/workflows/board.yml`, `ci-escapes.yml`, `war-room.yml` | `sh tools/ci-bench/python.sh` (the pinned Python), 8 steps; `ci-escapes.yml`'s header names the bench; `war-room.yml` also fetches `ci-benchmarks` | **not owned** (workflows: need asking) |
| `.github/actions/docs-only/test.sh`, `test_plan.py` | Classifier cases naming `tools/ci-bench/steps.tsv` and `tools/factory-metrics/*` paths | MT8 (their rows) |
| `ci/escapes/README.md`, `escapes.py` | Text: the bench counts escapes | MT8 |
| `ci/main-batch/shadow.py` | Imports `tools/ci-bench` (`bench.py`) | MT8 |
| `ci/main-batch/fixtures/shadow/red-r1-benchmark.log` | A historical red log naming `tools/ci-bench` | **not owned** (an old evidence log) |
| `contracts/ci3.v1.md` | Links `tools/ci-bench/ci3.py` and `tools/ci-bench/steps.tsv` | **not owned** (a contract: wording only, CI3's version unchanged) |
| `docs/ci3.md` | `ci3.py collect`/`measure` commands | **not owned** |
| `docs/evidence/ci2-pr-cuts.md` | `tools/ci-bench/required.py` commands and results | **not owned** (evidence) |
| `docs/agents/skills-ab.md` | `tools/factory-metrics/experiments/*` commands | MT8 |
| `loops/README.md` | Factory metrics' `--repo` row; `tools/ci-bench/` | MT8 |
| `STATUS.md` | WR10's `ci-benchmarks` point; CI numbers | **not owned** |
| `skills/launch-fleet/scripts/test-limit-replacement.py`, `test/limit-recovery/README.md` | Text naming `tools/factory-metrics/limits.conf` and its journey contract | MT8 (test references) |
| `skills/launch-fleet/scripts/carried/limits.py`, `limits.conf` | Byte-identical carried copies of factory-metrics' | Stay carried; their checker changes with the source |
| `tools/fleet-load/test_carried.py` | Checks those carried copies against `tools/factory-metrics/limits.py`, `limits.conf` and `fixtures/stage-waits/bench.json` | **not owned** |
| `tools/github-app/test.py` | Lists `tools/factory-metrics` among `GH_TOKEN` readers | **not owned** |
| `tools/open-import/paths.json` | Rows `tools/ci-bench/**`, `tools/factory-metrics/**` | MT8 (under the #819 grant: its own rows) |
| `tools/skills-eval/` (`precheck/contract.md`, `contract-fixtures/README.md`, `test_contract.py`, `promotions/promote.py`, `test_promotions.py`, `replay-contract.md`, `replay/run.py`, `score.py`, `test_replay.py`, `required-text.json`, `weekly/run.py`) | Imports `factory-metrics/experiment_contract.py` and `journey.py`; reads its journey and bottlenecks fixtures; requires its README text | **not owned** |
| `tools/war-room/activity.py`, `cost.py`, `rework.py`, `stage_waits.py`, `review_loops.py`, `sources.py`, `weekly.py`, and `health.py` through `stage_waits.py` | Import `ci-bench/bench.py` (`gh`, `pages`, `read_point`, `current_activity`, `ACTIVITY_POOLS`, prices and costs), `ci-bench/trends.py` (`distribution`, `outcome_cohort`), `factory-metrics/metrics.py` (`collect_prs`, `graphql`, `read_usage`, `activity_directions`), `journey.py` (`validate`, `collect`, `stage_bench`, `validate_stage_waits`, `rounds_of`) and `limits.py` | **not owned** (MT2/MT3 add collectors beside them, but no ticket moves these imports) |
| `tools/war-room/gather.py` | Fetches `ci-benchmarks`, reads `limits.conf`, names `tools/ci-bench/daily.sh` | MT2, MT3 (shared: their calls only) |
| `tools/war-room/page.py`, `charts/prepare.py` | The `ci_bench` slot's names and figures | MT4 (shared: its section, its chart) |
| `tools/war-room/README.md`, `contract.md`, `contract.v2.md`, `charts/contract.md`, `benchmarks.json`, `record.schema.json`, `record.v2.schema.json` | Name the tools as sources; the immutable slot names `ci_bench`, `factory_metrics`; the cost basis cites `tools/ci-bench/prices.tsv` | **not owned** (the slot names must stay) |
| `tools/war-room/test_*.py` and `fixtures/` (contract, cost, page-history, page-design, charts, rework, stage-waits) | Run the native readers on ci-bench and factory-metrics fixtures; saved slot names | **not owned** (tests follow their modules) |

### Gaps for the plan

The inventory finds work no ticket of #819 owns. MT8's search ("nothing refers
to either tool") cannot pass until each has an owner:

1. **The war room's own imports.** Seven war-room modules import code from
   both tools, and `health.py` through one of them. Deleting the folders breaks them unless that code moves into the war
   room first. MT2 and MT3 own new collector files, not these modules.
2. **The pinned Python.** Three other workflows run `tools/ci-bench/python.sh`.
   It needs a new home, and those workflow edits need asking.
3. **skills-eval** imports `experiment_contract.py` and `journey.py` and reads
   factory-metrics' fixtures. Its move to WizSkills is out of this spec's
   scope, so EB5's rules need a home that skills-eval can still import.
4. **Rules tables** `steps.tsv` (CI3's critical path, `check-steps`) and
   `prices.tsv` (the cost basis), and `required.py` with its CI2 evidence.
5. **Text that names the tools**: `contracts/ci3.v1.md`, `docs/ci3.md`,
   `STATUS.md`, `docs/evidence/ci2-pr-cuts.md`, `tools/github-app/test.py`,
   `tools/fleet-load/test_carried.py` and an old red log.
6. **The search itself.** The v1 slot names `ci_bench` and `factory_metrics`
   are immutable and stay in saved samples, so MT8's search should look for
   the tools' paths, `ci-bench.yml` and `ci-benchmarks`, not the slot names.

## Seams left for later tickets

- `collect_factory.read`, `collect_factory.validate`, its CLI, and the
  factory facts of a snapshot (MT2, #821); `collect_ci.read`,
  `collect_ci.validate`, its CLI and the CI facts (MT3, #822).
- `prs_per_hour` with its `baseline` slot, for the chart (MT4, #823).
- The stall alarm's read: `read-stall.json` (MT5, #824).
- The guard's `queue.observation` and its 60-second bound: `read-queue.json`
  (MT6, #825).
- The `ci3` fact for the loop: `read-ci3.json` (MT7, #826).
- Inventory B and its gaps (MT8, #827).

## Versions

A change that moves a fact's meaning, unit, time basis or a reader's bound is
a new version, `collector.v2`, in a new file. Adding a fact or a field is a
new version too: the schema's objects are closed. Wording that changes no
fact keeps the version. The approved FM2 extension adds an optional v1
snapshot property so saved v1 snapshots remain readable. New collections
always include a `flow` fact, including an unavailable result when needed.
