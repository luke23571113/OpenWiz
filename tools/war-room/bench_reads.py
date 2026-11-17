#!/usr/bin/env python3
"""The ci-bench code the war room reads with, moved here (#822, spec #819 revision 4).

Copied unchanged from ci-bench's bench.py at its retirement's start: its
`gh` reader and page walk, its value checks, the current-activity
observation (WR8), runner kinds, the price table and its list-rate costs, and
the reader of a saved CI bench `point.json`. The war room's modules
import these from here; MT8 (#827) retired the bench itself. Since #1027,
current_activity reads up to WORKERS runs at once, with every check unchanged.
Python 3 standard library only, and gh.
"""
import csv
from functools import lru_cache
import json
import importlib.util
import math
import re
import subprocess
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone, timedelta
from itertools import islice
from pathlib import Path
from threading import Event, Lock

HERE = Path(__file__).resolve().parent

SCHEMA = "closedwiz.ci-bench.v1"
WORKFLOW = "ci.yml"

PAGE = 100
API_LIMIT = 1000
WORKERS = 4  # current_activity reads at most this many CI runs at once (#1027); fixed, no setting

CATEGORIES = ["web", "setup", "rust", "build", "skills"]

TIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ")


class Fail(Exception):
    pass


# ---------------------------------------------------------------- reading

def trends_module():
    spec = importlib.util.spec_from_file_location("bench_trends", HERE / "trends_reads.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module




def strict_json(text, where):
    """JSON with no repeated key and no NaN or Infinity."""
    def pairs(items):
        out = {}
        for k, v in items:
            if k in out:
                raise Fail(f"{where}: repeated key '{k}'")
            out[k] = v
        return out

    def constant(name):
        raise ValueError(name)

    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except ValueError:
        raise Fail(f"{where}: not JSON")


def read_file(path):
    try:
        return Path(path).read_text()
    except OSError as e:
        raise Fail(f"cannot read {path}: {e.strerror}")


def need(obj, key, where):
    if key not in obj:
        raise Fail(f"{where}: missing '{key}'")
    return obj[key]


def as_int(obj, key, where):
    v = need(obj, key, where)
    if type(v) is not int:
        raise Fail(f"{where}: '{key}' is not an integer")
    return v


def as_str(obj, key, where, null=False):
    v = need(obj, key, where)
    if v is None and null:
        return v
    if type(v) is not str:
        raise Fail(f"{where}: '{key}' is not a string")
    return v


def as_time(obj, key, where, null=False):
    v = need(obj, key, where)
    if v is None and null:
        return v
    if type(v) is not str or not TIME.fullmatch(v):
        raise Fail(f"{where}: '{key}' is not a UTC time")
    try:
        datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise Fail(f"{where}: '{key}' is not a UTC time")
    return v


def as_obj(v, where):
    if type(v) is not dict:
        raise Fail(f"{where}: not an object")
    return v


def as_list(v, where):
    if type(v) is not list:
        raise Fail(f"{where}: not a list")
    return v


def exact(obj, keys, where):
    if set(obj) != keys:
        raise Fail(f"{where}: keys are {sorted(obj)}, expected {sorted(keys)}")


def secs(t):
    return parsed_secs(t)


@lru_cache(maxsize=8192)
def parsed_secs(t):
    # Only successful, context-free conversions are retained. A bounded LRU
    # also caps memory for high-cardinality windows and direct module callers.
    return int(datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp())


def never_ran(job):
    return not job["steps"] and not job["runner_name"]


def gh(path):
    """One read: `gh api <path>`, a GET with no other flag."""
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if r.returncode != 0:
        first = (r.stderr.strip().splitlines() or [""])[0]
        raise Fail(f"gh api {path} failed (exit {r.returncode}): {first}")
    return strict_json(r.stdout, f"gh api {path}")


def pages(path, key, what, read=None):
    """Every item of a paged list whose answers say their total_count."""
    items, total, page = [], None, 1
    while total is None or len(items) < total:
        where = f"gh api {path}&page={page}"
        ans = as_obj((read or gh)(f"{path}&page={page}"), where)
        count, got = as_int(ans, "total_count", where), as_list(need(ans, key, where), where)
        if total is None:
            total = count
            if total > API_LIMIT:
                raise Fail(f"the window holds more than {API_LIMIT} {what}, the API's limit: split it")
        elif count != total:
            raise Fail(f"{where}: total_count changed between pages")
        if not got and len(items) < total:
            raise Fail(f"{where}: fewer {what} than total_count ({len(items)} of {total})")
        items += [(item, where) for item in got]
        page += 1
    if len(items) > total:
        raise Fail(f"gh api {path}: more {what} than total_count ({len(items)} of {total})")
    return items



# WR8 exact pool selectors, separate from historical pricing precedence.
ACTIVITY_POOLS = {"closedwiz-pc", "self-hosted", "ubuntu-24.04", "ubuntu-22.04",
                  "ubuntu-latest", "ubuntu-slim", "blacksmith-2vcpu-ubuntu-2404"}


def activity_pool(labels):
    if not labels or set(labels) - ACTIVITY_POOLS - {"Linux", "linux", "X64", "x64"}:
        return None
    selected = set(labels) & ACTIVITY_POOLS
    if "closedwiz-pc" in selected:
        selected.discard("self-hosted")
    if len(selected) != 1 or runner_kind({"runner_labels": labels}) == "unknown":
        return None
    return next(iter(selected))


def current_activity(since, until, *, repo, read):
    """WR8's injected current observation; never changes completed collect.

    All ci.yml runs (including old active ones), bounded by the existing API
    limit. Two equal enumerations bracket jobs; two equal job reads and a run
    reread reject changing attempts/membership/status rather than infer a pool.
    Up to WORKERS runs are read at once, so `read` must be safe to call from
    several threads; results merge in run order, as a serial read gives them.
    No runner inventory endpoint, clock, output file or implicit live reader.
    """
    base = f"repos/{repo}"
    path = f"{base}/actions/workflows/{WORKFLOW}/runs?per_page={PAGE}"

    def runs():
        result = {}
        for value, where in pages(path, "workflow_runs", "runs", read):
            as_obj(value, where)
            rid = as_int(value, "id", where)
            attempt = as_int(value, "run_attempt", where)
            if rid <= 0 or attempt <= 0 or rid in result:
                raise Fail("current runs: duplicate or invalid identity")
            result[rid] = {"id": rid, "run_attempt": attempt,
                           "status": as_str(value, "status", where),
                           "conclusion": as_str(value, "conclusion", where, null=True),
                           "created_at": as_time(value, "created_at", where)}
            if secs(result[rid]["created_at"]) > secs(until):
                raise Fail("current run created after observation")
        return result

    def facts(rid, run):
        """One run's two jobs reads and its reread, in their existing order and checks."""
        job_path = f"{base}/actions/runs/{rid}/jobs?per_page={PAGE}"
        rows = pages(job_path, "jobs", "jobs", read)
        if [v for v, _ in rows] != [v for v, _ in pages(job_path, "jobs", "jobs", read)]:
            raise Fail("current jobs changed during observation")
        seen, jobs, priced = set(), [], []
        for value, where in rows:
            as_obj(value, where)
            jid = as_int(value, "id", where)
            if jid <= 0 or jid in seen or as_int(value, "run_id", where) != rid:
                raise Fail("current jobs: duplicate or invalid identity")
            seen.add(jid)
            if as_int(value, "run_attempt", where) != run["run_attempt"]:
                raise Fail("current job attempt changed or carried over")
            status = as_str(value, "status", where)
            if status not in ("completed", "in_progress", "queued"):
                raise Fail("current job status unavailable")
            labels = value.get("labels")
            if labels is not None and (type(labels) is not list or any(type(x) is not str for x in labels)):
                raise Fail("current job labels unavailable")
            jobs.append({"id": jid, "run": rid, "attempt": run["run_attempt"],
                         "status": status, "pool": activity_pool(labels)})
            if run["status"] == "completed":
                if status != "completed":
                    raise Fail("completed current run contains an unfinished job")
                item = {"runner_labels": labels if activity_pool(labels) else [],
                        "runner_name": as_str(value, "runner_name", where, null=True),
                        "steps": as_list(need(value, "steps", where), where),
                        "started_at": as_time(value, "started_at", where, null=True),
                        "completed_at": as_time(value, "completed_at", where, null=True)}
                if not never_ran(item):
                    if (item["started_at"] is None or item["completed_at"] is None
                            or item["completed_at"] < item["started_at"] or item["completed_at"] > until):
                        raise Fail("completed current job timing unavailable")
                priced.append((jid, item))
        again = as_obj(read(f"{base}/actions/runs/{rid}"), "current run reread")
        if any(again.get(k) != v for k, v in run.items()):
            raise Fail("current run changed during observation")
        return jobs, priced

    before = runs()
    todo = []
    for rid, run in sorted(before.items()):
        if run["status"] == "completed" and not since <= run["created_at"] < until:
            continue
        if run["status"] not in ("completed", "in_progress", "queued", "waiting", "pending", "requested"):
            raise Fail("current run status unavailable")
        todo.append((rid, run))
    # #1027: at most WORKERS runs are read at once, only after the first enumeration and all
    # finished before the second. A failing worker sets `failed` itself, under the lock each
    # admission and each worker's start take, so once any worker has failed no further run is
    # admitted, whatever wait() last returned, and no queued run sends a request. The first
    # failure the scheduler sees cancels every queued run; the runs already reading finish
    # (nothing is left running), their results are dropped and that first failure is raised.
    lock, failed = Lock(), Event()

    def worker(rid, run):
        with lock:
            if failed.is_set():
                return None  # queued when another run failed: read nothing
        try:
            return facts(rid, run)
        except BaseException:
            with lock:
                failed.set()
            raise

    done, flying, error = {}, {}, None
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        queue = iter(todo)
        while True:
            with lock:
                if not failed.is_set():
                    for rid, run in islice(queue, WORKERS - len(flying)):
                        flying[pool.submit(worker, rid, run)] = rid
            if not flying:
                break
            finished, _ = wait(flying, return_when=FIRST_COMPLETED)
            for future in sorted(finished, key=flying.get):
                rid = flying.pop(future)
                if future.cancelled():
                    continue
                if future.exception() is not None:
                    if error is None:
                        error = future.exception()
                        for queued in flying:
                            queued.cancel()  # only a run not yet started can be cancelled
                    continue
                done[rid] = future.result()
    if error is not None:
        raise error
    # Merged in run order, as the serial read produced it; job ids stay unique across runs.
    seen, jobs, priced, cost_ids = set(), [], [], []
    for rid in sorted(done):
        run_jobs, run_priced = done[rid]
        for j in run_jobs:
            if j["id"] in seen:
                raise Fail("current jobs: duplicate or invalid identity")
            seen.add(j["id"])
        jobs += run_jobs
        priced += [item for _, item in run_priced]
        cost_ids += [jid for jid, _ in run_priced]
    if runs() != before:
        raise Fail("current run enumeration changed during observation")
    prices = read_prices(HERE / "prices.tsv")
    return {"runs": sorted(before), "jobs": jobs, "cost_jobs": cost_ids,
            "cost": costs(priced, [], prices)}

POINT_KEYS = {"schema", "label", "since", "until", "hours", "robots", "runs", "jobs", "merged_prs", "merged_per_hour",
              "code_runs", "legacy"}
COHORT_KEYS = {"rule", "runs", "robot_seconds", "robot_minutes_per_run", "prs_per_hour", "categories", "split",
               "queued_to_done"}
NUMBERS = {"categories": set(CATEGORIES), "split": {"waiting", "setup", "running"},
           "queued_to_done": {"median", "p90", "max"}}


def as_num(obj, key, where):
    v = need(obj, key, where)
    if type(v) not in (int, float):
        raise Fail(f"{where}: '{key}' is not a number")
    if not math.isfinite(v) or v < 0:
        raise Fail(f"{where}: '{key}' must be finite and nonnegative")
    return v


def read_cohort(c, where):
    as_obj(c, where)
    exact(c, COHORT_KEYS, where)
    as_str(c, "rule", where)
    for k in ("runs", "robot_seconds"):
        as_int(c, k, where)
    for k in ("robot_minutes_per_run", "prs_per_hour"):
        as_num(c, k, where)
    for k, keys in NUMBERS.items():
        part = as_obj(c[k], f"{where} {k}")
        exact(part, keys, f"{where} {k}")
        for n in keys:
            as_num(part, n, f"{where} {k}")


def read_point(d):
    """A point.json, every field `chart` reads, each of its own type."""
    where = f"{d}/point.json"
    p = as_obj(strict_json(read_file(Path(d) / "point.json"), where), where)
    if p.get("schema") != SCHEMA:
        raise Fail(f"{where}: schema is not {SCHEMA}")
    exact(p, POINT_KEYS | (set(p) & {"cost", "latency_basis", "factory", "buckets", "escapes", "journey"}), where)
    if "journey" in p:
        T = trends_module()
        try:
            T.validate(p["journey"])
            if (p["journey"]["since"], p["journey"]["until"]) != (p["since"], p["until"]):
                raise Fail("journey report differs from point window")
        except T.J.ReadError as error:
            raise Fail(str(error))
    if "escapes" in p:
        validate_escapes(p["escapes"], f"{where} escapes")
    if "factory" in p:
        validate_factory(p["factory"], f"{where} factory")
    if "buckets" in p:
        validate_buckets(p["buckets"], f"{where} buckets")
    if "latency_basis" in p and p["latency_basis"] != "workflow created to last job completed":
        raise Fail(f"{where}: unknown latency basis")
    as_str(p, "label", where)
    for k in ("since", "until"):
        as_time(p, k, where)
    for k in ("robots", "runs", "jobs", "merged_prs"):
        as_int(p, k, where)
    for k in ("hours", "merged_per_hour"):
        as_num(p, k, where)
    if p["code_runs"] is not None:
        read_cohort(p["code_runs"], f"{where} code_runs")
    if "cost" in p:
        validate_cost(p["cost"], where)
    if p["legacy"] is not None:
        if type(p["legacy"]) is not dict:
            raise Fail(f"{where}: 'legacy' is not an object or null")
        read_cohort(p["legacy"], f"{where} legacy")
    return p


def runner_kind(job):
    labels = set(job.get("runner_labels", []))
    # Only observed PC and published standard SKU labels are recognised.
    # Never guess a price from an arbitrary runner name or a generic Linux tag.
    jog = [x for x in labels if x == "jog" or x.startswith("jog-")]
    if jog:
        return jog[0] if len(jog) == 1 and jog[0] in {"jog-4vcpu", "jog-8vcpu", "jog-16vcpu"} else "unknown"
    blacksmith = [x for x in labels if x.startswith("blacksmith-")]
    if blacksmith:
        return blacksmith[0] if len(blacksmith) == 1 else "unknown"
    if labels & {"closedwiz-pc", "self-hosted"}:
        return "self-hosted"
    if "ubuntu-slim" in labels:
        return "github-hosted-slim"
    if labels & {"ubuntu-24.04", "ubuntu-22.04", "ubuntu-latest"} and not labels & {"ARM64", "arm64"}:
        return "github-hosted"
    return "unknown"


def read_prices(path):
    columns = ["runner_kind", "compute_usd_per_minute", "platform_usd_per_minute", "source_url", "verified_on"]
    reader = csv.DictReader(read_file(path).splitlines(), delimiter="\t")
    if reader.fieldnames != columns:
        raise Fail(f"{path}: invalid price table columns")
    prices = {}
    for row in reader:
        kind = row["runner_kind"]
        if not kind or kind in prices or set(row) != set(columns) or any(v is None for v in row.values()):
            raise Fail(f"{path}: invalid or repeated price row")
        if not re.fullmatch(r"https://\S+", row["source_url"]):
            raise Fail(f"{path}: price needs a source URL")
        try:
            datetime.strptime(row["verified_on"], "%Y-%m-%d")
            for key in columns[1:3]:
                row[key] = None if row[key] == "unknown" else float(row[key])
                if row[key] is not None and (not math.isfinite(row[key]) or row[key] < 0):
                    raise ValueError()
        except ValueError:
            raise Fail(f"{path}: invalid price or date")
        prices[kind] = row
    return prices


def costs(jobs, code, prices):
    def subtotal(selected):
        minutes, billed, total, unknown = {}, {}, 0, 0
        for job in selected:
            if job.get("timing_unknown"):
                unknown = math.inf
                continue
            if never_ran(job):
                continue
            kind = runner_kind(job)
            seconds = secs(job["completed_at"]) - secs(job["started_at"])
            elapsed = seconds / 60
            # GitHub bills each hosted job rounded up to a whole minute.
            # Jog publishes per-second billing; other third-party estimates
            # retain the existing conservative whole-minute unit.
            charged = elapsed if kind in {"jog-4vcpu", "jog-8vcpu", "jog-16vcpu"} else math.ceil(elapsed)
            minutes[kind] = minutes.get(kind, 0) + elapsed
            billed[kind] = billed.get(kind, 0) + charged
            row = prices.get(kind)
            rate = None if row is None or any(row[k] is None for k in
                       ("compute_usd_per_minute", "platform_usd_per_minute")) else (
                       row["compute_usd_per_minute"] + row["platform_usd_per_minute"])
            if rate is None and elapsed:
                unknown += elapsed
            elif rate is not None:
                total += charged * rate
        return ({k: round(v, 4) for k, v in sorted(minutes.items())}, billed,
                None if unknown else round(total, 6), None if math.isinf(unknown) else round(unknown, 4))
    minutes, billed, total, unknown = subtotal(jobs)
    code_total = subtotal([j for run in code for j in run])[2]
    result = {"runner_minutes": minutes, "billed_minutes": billed, "window_usd": total,
            "per_code_run_usd": None if code_total is None or not code else round(code_total / len(code), 6),
            "unknown_minutes": unknown, "prices": list(prices.values())}
    unknown_jobs = sum(bool(j.get("timing_unknown")) for j in jobs)
    if unknown_jobs:
        result["unknown_jobs"] = unknown_jobs
    return result


def validate_cost(cost, where):
    as_obj(cost, where)
    exact(cost, {"runner_minutes", "billed_minutes", "window_usd", "per_code_run_usd", "unknown_minutes", "prices"} | (set(cost) & {"unknown_jobs"}), where)
    if "unknown_jobs" in cost:
        as_int(cost, "unknown_jobs", where)
    for key in ("window_usd", "per_code_run_usd", "unknown_minutes"):
        if cost[key] is not None:
            as_num(cost, key, where)
    for key in ("runner_minutes", "billed_minutes"):
        for kind in as_obj(cost[key], where):
            as_num(cost[key], kind, where)
    for row in as_list(cost["prices"], where):
        as_obj(row, where)
        exact(row, {"runner_kind", "compute_usd_per_minute", "platform_usd_per_minute", "source_url", "verified_on"}, where)
        for key in ("runner_kind", "source_url", "verified_on"):
            as_str(row, key, where)
        for key in ("compute_usd_per_minute", "platform_usd_per_minute"):
            if row[key] is not None:
                as_num(row, key, where)

CAUSES = ("flaky", "runner_network", "after_pass", "after_cancel", "unknown")

FACTORY_SHAPE = {
    "ready_to_merged_hours": ({"tickets", "unknown_tickets", "unlinked_prs"}, {"median", "p90"}),
    "first_review": ({"reviewed_prs", "first_approve", "rounds_prs", "unreviewed_prs", "unknown_prs"},
                     {"share", "rounds_per_pr"}),
    "main_red": ({"untimed_verdicts", "verdicts"}, {"red_minutes", "unknown_minutes"}),
    "reruns": ({"total", "attempts", *CAUSES}, set()),
    "runner_wait_minutes": ({"jobs"}, {"median", "p90"}),
}


def validate_factory(f, where):
    as_obj(f, where)
    exact(f, {"merged_prs"} | set(FACTORY_SHAPE), where)
    as_int(f, "merged_prs", where)
    for part, (counts, numbers) in FACTORY_SHAPE.items():
        at = f"{where} {part}"
        exact(as_obj(f[part], at), counts | numbers, at)
        for k in counts:
            as_int(f[part], k, at)
        for k in numbers:
            if f[part][k] is not None:
                as_num(f[part], k, at)
    if f["main_red"]["unknown_minutes"] is None:
        raise Fail(f"{where} main_red: 'unknown_minutes' is not a number")

BUCKET_SIZES = (("1h", 1), ("6h", 6))
BUCKET_CI = {"code_runs", "minutes_per_pr", "prs_per_hour", "merged_prs"}


def validate_buckets(b, where):
    as_obj(b, where)
    exact(b, {name for name, _ in BUCKET_SIZES}, where)
    for name, _ in BUCKET_SIZES:
        for i, row in enumerate(as_list(b[name], where)):
            at = f"{where} {name} {i + 1}"
            as_obj(row, at)
            exact(row, {"start", "end", "ci"} | (set(row) & {"factory"}), at)
            if secs(as_time(row, "end", at)) <= secs(as_time(row, "start", at)):
                raise Fail(f"{at}: ends before it starts")
            ci = as_obj(row["ci"], at)
            exact(ci, BUCKET_CI, at)
            as_int(ci, "code_runs", at), as_int(ci, "merged_prs", at)
            for k in ("minutes_per_pr", "prs_per_hour"):
                if ci[k] is not None:
                    as_num(ci, k, at)
            if "factory" in row:
                validate_factory(row["factory"], f"{at} factory")

ESCAPE_POINT_KEYS = {"count", "attempts", "failed_attempts", "unknown"}


def validate_escapes(e, where):
    as_obj(e, where)
    exact(e, ESCAPE_POINT_KEYS, where)
    for k in ("attempts", "failed_attempts", "unknown"):
        if as_int(e, k, where) < 0:
            raise Fail(f"{where}: '{k}' is negative")
    if (e["count"] is None) != (e["unknown"] > 0) or (e["count"] is not None and (type(e["count"]) is not int or e["count"] < 0)):
        raise Fail(f"{where}: 'count' is a whole number exactly when nothing is unknown")
    if e["failed_attempts"] > e["attempts"]:
        raise Fail(f"{where}: more failed attempts than attempts")
