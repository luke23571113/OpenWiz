# War room record contract v2 (health successor)

WRD1 (#629), spec #626. `openwiz.war-room.v2` is the successor of
[`openwiz.war-room.v1`](contract.md). Newly composed snapshots are v2. Saved v1
samples are never rewritten: both versions are read through the same readers.
Fixture proofs are offline. Five-minute operation, live sources and complete
history remain Unverified until the separately authorized live check.

## What changes and what does not

A v2 envelope has exactly `schema`, `sample_id`, `sample_at`, `assembled_at`,
`groups`, `providers` and `health`.

- `schema` is `openwiz.war-room.v2`.
- `sample_id`, `sample_at`, `assembled_at`, `groups` and `providers` keep v1's
  exact meaning, shapes, registry order (the same 17 slots) and every v1 metric
  rule in [contract.md](contract.md). No v1 metric field or semantic is
  relabelled. `stage_waits` keeps its detailed five-stage projection (WR3).
- `health` is new: exactly three health providers, always in this order.

| Slot | Source | Evidence class |
| --- | --- | --- |
| `main_ci` | The configured repository's current `main` head and its `ci.yml` push run/attempt, read through `bench.pages` | `current_read` |
| `ci_queue` | WR8's checked `ci.yml` run/job reader (`bench.current_activity`, bounded by `gather.current_runs`) and its exact pool classification (`bench.activity_pool`) | `current_read` |
| `stage_health` | TL2's validated stage sidecar (`journey.validate_stage_waits`, `journey.stage_bench`) and TL1's one settings file (`limits.read`) | `producer_fact`, and `settings_read` for limits |

`suite.schema_of(record)` names a record's version. `suite.validate`,
`suite.loads` and `suite.load` accept both versions and apply each version's own
rules. `suite.compose` writes v2 only. `suite.health(record)` is the explicit
health reader for both versions: a v1 record yields the three health slots as
`unavailable` with the prerequisite `Not observed: this sample predates the v2
health record.` Nothing is backfilled, and an old sample never reads as green
or as zero.

`record.v2.schema.json` is the structural schema. Its `x-providers` is v1's
registry, unchanged; `x-health` is the health registry and each slot's default
prerequisite. As in v1, schema conformance alone proves no cross-field rule:
always call `validate`.

## Health observations: points, not windows

A health provider is `{slot, state, prerequisites, observations}`. Its state
follows v1's rules: `known` needs a nonempty list of known observations and no
prerequisites; `partial` needs prerequisites and at least one sourced
observation; `unavailable` holds only unavailable observations.

An observation has exactly:

| Field | Meaning |
| --- | --- |
| `id`, `label` | Stable id within the slot; sanitized fixed label |
| `state` | `known`, `partial` or `unavailable` |
| `result` | A named result, or null when the observation is a number only |
| `value`, `unit` | A nonnegative number or null; `count` or `minutes`, or null for a result only |
| `statistic` | `result`, `count`, `max` (oldest age), `observation` (one wait) or `limit` |
| `point` | The source's own point time, or null |
| `window` | A native half-open source window, or null; never both `point` and `window` |
| `read` | `{started_at, ended_at}`: the collector's actual read bounds |
| `fresh_until`, `freshness` | The source-owned validity bound, as in v1. None of the three sources has one, so freshness is `unknown` |
| `source` | Sanitized path, schema and SHA-256 of the retained observation bytes |
| `evidence`, `evidence_class` | GitHub links; `current_read`, `producer_fact`, `settings_read` or `unobserved` |
| `cohort` | The source cohort id, or null |
| `identity` | `repository`, `branch`, `head_sha`, `workflow`, `run_id`, `run_attempt`, `pool`, `stage`, `interval`, `ticket`, `pull_request`; each null when inapplicable |
| `interval` | v1's interval, for one native wait, or null |
| `limit` | The loaded limit that judged it: `{minutes, owner, schema, sha256, read_at}`, or null |
| `sample` | `{observed, expected, identities}`; observed equals the identity count |
| `prerequisites` | What is missing, for every observation that is not `known` |

**A point is not a window.** Current health is observed at a point: `point` is
the read's own time, inside `read`. The five-minute `sample_at` is the sample
identity only. It is never the source's observation time and never a freshness
guarantee. No nonempty window is invented for a point.

General rules, checked by `validate`:

- `read.started_at <= read.ended_at <= assembled_at`; `point` lies at or before
  `read.ended_at`, and `window.until` at or before it.
- `known` needs no prerequisites, complete sample coverage, a source, a `point`
  or `window`, and a value (or, for `result`, a result other than `unknown`).
  `unavailable` has a null value, a null or `unknown` result and prerequisites.
  `partial` has prerequisites. Unknown is never encoded as zero.
- A number or a result needs a source and read bounds. It also needs evidence
  links, unless it is a complete, sourced count of zero: an empty complete read
  has no run to link.
- `count` values are integers equal to `sample.observed`. `result` has a null
  value and unit.

## `main_ci`: the current main head

One observation, `main`, `statistic: result`. Its identity names the
repository, `main`, the head commit, `ci.yml` and the run id and attempt.

The collector reads the branch head, then every page of `ci.yml` push runs for
that head (`branch=main&event=push&head_sha=<head>`), then rereads the chosen
run and the branch head. Results:

| Source state | Result | State |
| --- | --- | --- |
| Latest run on the head is `completed`/`success` | `success` | known |
| `completed`/`failure`, `timed_out` or `startup_failure` | `failure` | known |
| `completed`/`cancelled` | `cancelled` | known |
| Not completed (`queued`, `in_progress`, `waiting`, `pending`, `requested`) | `pending` | known |
| Any other conclusion, no run yet for the head, two latest runs created in the same second, the head or the run changed during the read, a run for another head, or a failed/incomplete read | `unknown` | unavailable |

`validate` admits `success` only as a known observation with a complete
identity. A superseded head cannot be chosen: only runs for the head read at
both ends count. The historical main-red-minutes statistic is not current
status and is not used.

## `ci_queue`: current queue by exact pool

For each selected exact pool: `queued:<pool>` and `running:<pool>` (`count`),
`oldest-queued:<pool>` (`max`, minutes, only when a job is queued there and
every job's pool is known),
and one `queued-wait:<pool>:job-<id>` per queued job (`observation`, minutes,
an open interval from the job's `created_at`, so `partial`: a lower bound at
the read). Sample identities are `job-<id>`; each job's run id and attempt are
in its identity.

Its `read` closes after the last of those Actions reads, and every point and
age is measured to that end. The reader is WR8's: complete stable pages, two equal job reads, a run reread
and an equal run enumeration. A complete read of no active jobs is a known
zero. A failed or partial read (pagination short of `total_count`, a changed
total, a changed attempt or status) makes the whole slot unavailable: it never
produces zero. A job with missing or unsupported labels leaves every pool's
counts `partial` with null values. These are point waits, not completed-run
latency or summed job minutes. **No source owns a queue limit:** `limit` is
null and the display shows Unknown. The overload alarm (CS5) is an alarm, not
a queue limit, and is not used.

## `stage_health`: stage waits against loaded limits

From the same validated TL2/TL1 evidence as `stage_waits`, for at least
`builder_start`, `reviewer_start` and `merge`. The fix and answer stages stay
in `stage_waits`' detailed figures.

- `limit:<stage>`: `statistic: limit`, `evidence_class: settings_read`, with
  `limit` naming `tools/factory-metrics/limits.conf`'s schema, SHA-256 and the
  read time. A settings read before TL2's read, or a refused TL2/TL1 input,
  makes the whole slot `unavailable` with its prerequisite.
- `wait:<TL2 key>`: `statistic: observation`, the TL2 interval, and the limit
  that judged it. Results keep TL2's words (`not missed` becomes `not_missed`):

| TL2 | Result | State and value |
| --- | --- | --- |
| Ended, exact end, `missed` or `not missed` | `missed` / `not_missed` | known, the wait |
| Open at the read, `pending` or `missed` | `pending` / `missed` | partial, the lower bound to TL2's read |
| Edited end range | `missed`, `not_missed` or `unknown` | partial, the range's lower end |
| `gated` (held) or `stale` | `gated` / `stale` | partial, null value, TL2's gaps |
| `unknown` | `unknown` | unavailable |

Held time, censored waits, edited records and shared-PR deduplication are TL2's.
Its `history` is `unknown`, so stage health is never `known` as a provider.
The input covers unfinished work: gather collects TL2 for every open approved
ticket on the board graph as well as the merged cohort's tickets. If either list
cannot be read (no or refused board graph, a graph of another repository or of
one spec only, failed PR pages), no stage evidence
is collected and both stage slots are unavailable with that prerequisite: a
cohort that silently omits unfinished work is never shown. A changed
limit has a different `limit.sha256` and `minutes`. This changes no limit,
hold, recovery or review policy.

## Collection, history and refusal

- **One finite collection.** `publish.py collect --gather OWNER/REPO EVIDENCE`
  runs the gather once (every provider, the three health providers included),
  floors its time to the five-minute boundary, and saves one complete v2
  envelope through `history.collect`. It draws no picture and renders no page.
  The hourly `publish` is unchanged.
- **Independent failures.** Each health source that fails becomes its own
  unavailable provider with its prerequisite. The others are kept.
- **Privacy refuses everything.** A privacy hit in any gathered artifact
  refuses the whole gather, so nothing is selected or saved.
- **Immutable history.** A repeated boundary reuses its sample without a new
  read. A missing boundary stays absent. An out-of-order sample is saved and
  the latest stays the maximum `sample_id`. Saved v1 and v2 bytes never change.
  A failed health source is never filled from the previous sample.
- **Weekly and other consumers** read both versions: `weekly.report` uses
  `stage_waits`, which keeps the same shape in both.

## Synthetic proof

`test_health.py` owns these cases. Its fixtures in `fixtures/health/` are
synthetic and assert no live capability. `test_contract.py` keeps v1's cases
and pins the v1 fixture hashes.
