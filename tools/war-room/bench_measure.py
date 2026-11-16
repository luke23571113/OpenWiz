#!/usr/bin/env python3
"""ci-bench's collect and measure, moved here (#826, orchestrator ruling on #826).

The code tools/war-room/collect_ci.py and ci3.py load from tools/ci-bench/bench.py:
its window `collect` and its point `measure`, with every definition they reach
that bench_reads.py (#822) doesn't already carry. Each definition below is
copied byte-identical from tools/ci-bench/bench.py; the shared ones come from
bench_reads.py, where they are already identical. HERE is the war room, so the
step table and the prices are tools/war-room/steps.tsv and prices.tsv,
byte-identical to ci-bench's. MT8 (#827) retires the rest of ci-bench.
Python 3 standard library only, and gh.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
# Identical in bench.py and bench_reads.py. TIME, activity_pool and current_activity are
# not used here: collect_ci.py and ci3.py read them through this module, as they read bench.py.
from bench_reads import (  # noqa: E402
    BUCKET_SIZES,
    CATEGORIES,
    CAUSES,
    Fail,
    HERE,
    PAGE,
    SCHEMA,
    TIME,
    WORKFLOW,
    activity_pool,
    as_int,
    as_list,
    as_obj,
    as_str,
    as_time,
    costs,
    current_activity,
    exact,
    gh,
    need,
    never_ran,
    pages,
    read_file,
    read_prices,
    secs,
    strict_json,
    trends_module,
)

STEPS = HERE / "steps.tsv"


BASE_BRANCH = "main"


CODE_STEPS = {"Run npm test", "Run cargo test --workspace", "Run npm run build"}


LEGACY_SETUP = {"The docs-only classifier"}


CODE_RULE = ("successful code runs: push and pull_request runs that succeeded and in which"
             " `Run npm test`, `Run cargo test --workspace` or `Run npm run build` succeeded;"
             " robot time is each job's whole time on its runner")


LEGACY_RULE = ("reconstructed: runs in which `Run npm test` lasted more than 10 s, any event or"
               " conclusion; robot time is the sum of step durations only, with"
               " `The docs-only classifier` counted as setup")


JOB_KEYS = {"completed_at", "conclusion", "created_at", "event", "name", "run", "run_concl", "runner_name",
            "started_at", "steps"}


STEP_KEYS = {"completed_at", "conclusion", "name", "started_at"}


def read_window(d):
    where = f"{d}/window.json"
    w = as_obj(strict_json(read_file(Path(d) / "window.json"), where), where)
    exact(w, {"since", "until"}, where)
    since, until = as_time(w, "since", where), as_time(w, "until", where)
    if secs(until) <= secs(since):
        raise Fail(f"{where}: the window ends before it starts")
    return since, until


def read_merged(d, since, until):
    where = f"{d}/merged.json"
    prs = as_list(strict_json(read_file(Path(d) / "merged.json"), where), where)
    seen, times = set(), {}
    for i, pr in enumerate(prs):
        at = f"{where} item {i + 1}"
        as_obj(pr, at)
        exact(pr, {"merged_at", "number"}, at)
        n, merged = as_int(pr, "number", at), as_time(pr, "merged_at", at)
        if n in seen:
            raise Fail(f"{where}: PR {n} is listed twice")
        seen.add(n)
        if not secs(since) <= secs(merged) < secs(until):
            raise Fail(f"{where}: PR {n} merged outside the window")
        times[n] = merged
    return times


def read_jobs(d, allow_timing_gaps=False):
    where = f"{d}/jobs.jsonl"
    jobs = []
    for i, line in enumerate(read_file(Path(d) / "jobs.jsonl").splitlines()):
        at = f"{where} line {i + 1}"
        job = as_obj(strict_json(line, at), at)
        exact(job, JOB_KEYS | (set(job) & {"runner_labels", "run_created_at", "id", "run_attempt", "collected_attempt"}), at)
        for k in set(job) & {"id", "run_attempt", "collected_attempt"}:
            as_int(job, k, at)
        if "run_created_at" in job:
            as_time(job, "run_created_at", at)
        if "runner_labels" in job:
            labels = as_list(job["runner_labels"], at)
            if any(type(x) is not str for x in labels):
                raise Fail(f"{at}: runner labels must be strings")
        as_int(job, "run", at)
        for k in ("event", "name"):
            as_str(job, k, at)
        for k in ("run_concl", "conclusion", "runner_name"):
            as_str(job, k, at, null=True)
        for k in ("created_at", "started_at", "completed_at"):
            as_time(job, k, at)
        # GitHub shows a job that never got a runner (none, and no steps)
        # ending up to a second before it started: it ran for no time.
        if secs(job["completed_at"]) < secs(job["started_at"]) and not never_ran(job):
            if allow_timing_gaps and job.get("run_concl") in ("failure", "cancelled", "timed_out", "action_required", "startup_failure", "stale", "neutral", "skipped"):
                job["timing_unknown"] = True
            else:
                raise Fail(f"{at}: job {job['name']} ends before it starts")
        for j, step in enumerate(as_list(job["steps"], at)):
            st = f"{at} step {j + 1}"
            as_obj(step, st)
            exact(step, STEP_KEYS, st)
            as_str(step, "name", st)
            as_str(step, "conclusion", st, null=True)
            a, b = as_time(step, "started_at", st, null=True), as_time(step, "completed_at", st, null=True)
            if a is not None and b is not None and secs(b) < secs(a):
                raise Fail(f"{st}: step '{step['name']}' ends before it starts")
        jobs.append(job)
    return jobs


def read_table(path):
    rows = []
    for i, line in enumerate(read_file(path).splitlines()):
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 2 or parts[0] not in CATEGORIES or not parts[1]:
            raise Fail(f"{path} line {i + 1}: not '<category><TAB><step name>'")
        pattern = "".join(".*" if c == "*" else re.escape(c) for c in parts[1])
        rows.append((parts[0], re.compile(pattern)))
    if not rows:
        raise Fail(f"{path}: no rows")
    return rows


def category(table, step, job):
    name = re.sub(r"@\S+", "", step)
    hits = [cat for cat, pat in table if pat.fullmatch(name)]
    if len(hits) != 1:
        how = "matches no row" if not hits else f"matches {len(hits)} rows"
        raise Fail(f"step '{step}' (job {job}) {how} of {STEPS}")
    return hits[0]


def duration(step):
    if step["started_at"] is None or step["completed_at"] is None:
        return 0
    return secs(step["completed_at"]) - secs(step["started_at"])


def nearest_rank(values, p):
    ordered = sorted(values)
    return ordered[math.ceil(p * len(ordered)) - 1]


def cohort(runs, table, legacy, robots, rule):
    """Robot time per run in one cohort. The reconstructed rule counts step
    durations only; successful code runs count each job's whole time, the
    time no step covers going to setup."""
    if not runs:
        return None
    cats = dict.fromkeys(CATEGORIES, 0)
    waiting = robot = 0
    walls = []
    for jobs in runs:
        for job in jobs:
            # A job that never got a runner (none, and no steps) used no
            # robot and waited for none, however long GitHub shows it.
            if never_ran(job):
                continue
            started, done = secs(job["started_at"]), secs(job["completed_at"])
            # A job carried over from an earlier attempt started before it
            # was created: it waited for nothing in this one.
            waiting += max(0, started - secs(job["created_at"]))
            covered = 0
            for step in job["steps"]:
                d = duration(step)
                covered += d
                cat = "setup" if legacy and step["name"] in LEGACY_SETUP else category(table, step["name"], job["name"])
                cats[cat] += d
            if legacy:
                robot += covered
            else:
                if covered > done - started:
                    raise Fail(f"run {job['run']} job {job['name']}: its steps last longer than the job")
                cats["setup"] += done - started - covered
                robot += done - started
        walls.append((max(secs(j["completed_at"]) for j in jobs) - min(secs(j.get("run_created_at", j["created_at"])) for j in jobs)) / 60)
    n = len(runs)
    per_run = robot / n / 60

    def m(x):
        return round(x / n / 60, 4)

    return {
        "rule": rule,
        "runs": n,
        "robot_seconds": robot,
        "robot_minutes_per_run": round(per_run, 4),
        "prs_per_hour": round(robots * 60 / per_run, 4),
        "categories": {k: m(cats[k]) for k in CATEGORIES},
        "split": {"waiting": m(waiting), "setup": m(cats["setup"]), "running": m(robot - cats["setup"])},
        "queued_to_done": {"median": round(statistics.median(walls), 4), "p90": round(nearest_rank(walls, 0.9), 4),
                           "max": round(max(walls), 4)},
    }


def measure(d, robots, label, prices=None, allow_empty=False, allow_timing_gaps=False):
    since, until = read_window(d)
    jobs = read_jobs(d, allow_timing_gaps)
    merged_times = read_merged(d, since, until)
    numbers = sorted(merged_times)
    merged = len(numbers)
    facts = read_factory(d, since, until) if (Path(d) / "factory.json").exists() else None
    found = read_escapes(d, since, until) if (Path(d) / "escapes.json").exists() else None
    table = read_table(STEPS)
    for job in jobs:
        for step in job["steps"]:
            category(table, step["name"], job["name"])
    runs = {}
    for job in jobs:
        runs.setdefault(job["run"], []).append(job)
    for rid, js in runs.items():
        if len({j["event"] for j in js}) != 1:
            raise Fail(f"run {rid} has jobs of two events")
        origins = {j.get("run_created_at") for j in js}
        if len(origins) != 1:
            raise Fail(f"run {rid} has inconsistent run creation times")
        if (None not in origins and js[0]["run_concl"] == "success"
                and secs(next(iter(origins))) > max(secs(j["completed_at"]) for j in js)):
            raise Fail(f"run {rid} was created after its last job completed")
        if len({j["run_concl"] for j in js}) != 1:
            raise Fail(f"run {rid} has jobs of two run conclusions")
    order = sorted(runs)
    code = [runs[r] for r in order
            if runs[r][0]["event"] in ("push", "pull_request") and runs[r][0]["run_concl"] == "success"
            and any(s["name"] in CODE_STEPS and s["conclusion"] == "success" for j in runs[r] for s in j["steps"])]
    legacy = [runs[r] for r in order
              if any(s["name"] == "Run npm test" and duration(s) > 10 for j in runs[r] for s in j["steps"])
              and not any(j.get("timing_unknown") for j in runs[r])]
    if not code and not allow_empty:
        raise Fail("no successful code runs in the window")
    hours = (secs(until) - secs(since)) / 3600
    point = {
        "schema": SCHEMA,
        "label": label,
        "since": since,
        "until": until,
        "hours": round(hours, 4),
        "robots": robots,
        "runs": len(runs),
        "jobs": len(jobs),
        "merged_prs": merged,
        "merged_per_hour": round(merged / hours, 4),
        "code_runs": cohort(code, table, False, robots, CODE_RULE),
        "legacy": cohort(legacy, table, True, robots, LEGACY_RULE),
        "cost": costs(jobs, code, read_prices(prices or HERE / "prices.tsv")),
    }
    if all("run_created_at" in j for j in jobs):
        point["latency_basis"] = "workflow created to last job completed"
    if facts is not None:
        if sorted(p["number"] for p in facts["prs"]) != numbers:
            raise Fail("factory.json and merged.json: merged PRs differ; collect the window again")
        point["factory"] = factory_point(facts, since, until)
    if (Path(d) / "journey-report.json").exists():
        T = trends_module()
        try:
            result = strict_json(read_file(Path(d) / "journey-report.json"), "journey report")
            T.validate(result)
            if (result["since"], result["until"]) != (since, until):
                raise Fail("journey report differs from the measured window")
            point["journey"] = result
        except T.J.ReadError as error:
            raise Fail(str(error))
    if found is not None:
        point["escapes"] = escapes_point(found)
    point["buckets"] = buckets(since, until, robots, table, runs, code, merged_times, facts, jobs)
    write(Path(d) / "point.json", json.dumps(point, indent=2) + "\n")
    c, lg = point["code_runs"], point["legacy"]
    if facts is not None:
        f = point["factory"]
        print(f"{label}: factory: {f['merged_prs']} merged, {f['first_review']['reviewed_prs']} reviewed,"
              f" {f['reruns']['total']} reruns, main red {show(f['main_red']['red_minutes'], '{:.0f}')} min")
    if "escapes" in point:
        print(f"{label}: selector escapes {escapes_cell(point)}")
    if c is None:
        print(f"{label}: no successful code runs; daily cost recorded")
        return
    print(f"{label}: {c['prs_per_hour']:.1f} PRs an hour of capacity on {robots} robots"
          f" ({c['robot_minutes_per_run']:.2f} robot-minutes per code run, {c['runs']} successful code runs);"
          f" {point['merged_per_hour']:.1f} merged an hour")
    if lg:
        print(f"  reconstructed rule: {lg['prs_per_hour']:.1f} PRs an hour"
              f" ({lg['robot_minutes_per_run']:.2f} robot-minutes per code run, {lg['runs']} runs)")


def write(path, text):
    fd, tmp = tempfile.mkstemp(dir=Path(path).parent, prefix=".bench-")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def collect(since, until, out, workers=1):
    if shutil.which("gh") is None:
        raise Fail("gh is not on PATH")
    base = "repos/{owner}/{repo}"
    runs = {}
    for run, where in pages(f"{base}/actions/workflows/{WORKFLOW}/runs?created={since}..{until}"
                            f"&status=completed&per_page={PAGE}", "workflow_runs", "runs"):
        as_obj(run, where)
        rid = as_int(run, "id", where)
        at = f"{where} run {rid}"
        if rid in runs:
            raise Fail(f"{at}: listed twice")
        if as_str(run, "status", at) != "completed":
            raise Fail(f"{at}: not completed")
        runs[rid] = (as_str(run, "event", at), as_str(run, "conclusion", at, null=True), as_time(run, "created_at", at),
                     as_int(run, "run_attempt", at))
    # The API's range includes its end; the window doesn't.
    keep = sorted(r for r, (_, _, created, _) in runs.items() if secs(since) <= secs(created) < secs(until))
    def collect_run(rid):
        lines = []
        event, concl, _, attempt = runs[rid]
        for job, where in pages(f"{base}/actions/runs/{rid}/jobs?per_page={PAGE}", "jobs", "jobs"):
            at = f"{where} run {rid} job"
            as_obj(job, at)
            steps = []
            for step in as_list(need(job, "steps", at), at):
                as_obj(step, at)
                steps.append({"completed_at": as_time(step, "completed_at", at, null=True),
                              "conclusion": as_str(step, "conclusion", at, null=True),
                              "name": as_str(step, "name", at),
                              "started_at": as_time(step, "started_at", at, null=True)})
            record = {"completed_at": as_time(job, "completed_at", at),
                      "conclusion": as_str(job, "conclusion", at, null=True),
                      "created_at": as_time(job, "created_at", at), "event": event, "name": as_str(job, "name", at),
                      "run": rid, "run_concl": concl, "runner_name": as_str(job, "runner_name", at, null=True),
                      "started_at": as_time(job, "started_at", at), "steps": steps,
                      # Identity, so the factory benches reuse exactly this
                      # attempt's jobs and nothing else (#1359).
                      "id": as_int(job, "id", at), "run_attempt": as_int(job, "run_attempt", at),
                      "collected_attempt": attempt}
            record["run_created_at"] = runs[rid][2]
            if "labels" in job:
                labels = as_list(job["labels"], at)
                if any(type(x) is not str for x in labels):
                    raise Fail(f"{at}: runner labels must be strings")
                record["runner_labels"] = labels
            lines.append(json.dumps(record, sort_keys=True))
        # The jobs are the latest attempt's when they were read: if a rerun
        # came between the list and them, they belong to another attempt
        # than the conclusion above. Read the run again; it must not have
        # changed (#383 R2).
        where = f"gh api {base}/actions/runs/{rid}"
        again = as_obj(gh(f"{base}/actions/runs/{rid}"), where)
        if as_int(again, "id", where) != rid:
            raise Fail(f"{where}: run {rid} read again is run {again['id']}")
        before = (attempt, "completed", concl)
        after = (as_int(again, "run_attempt", where), as_str(again, "status", where),
                 as_str(again, "conclusion", where, null=True))
        if after != before:
            raise Fail(f"{where}: run {rid} changed while it was read (attempt, status, conclusion: {before} then"
                       f" {after}); read the window again once its reruns have finished")
        return lines

    if workers == 1:
        lines = [line for group in map(collect_run, keep) for line in group]
    else:
        # Two independent run reads at most; results retain run order.
        with ThreadPoolExecutor(max_workers=workers) as pool:
            lines = [line for group in pool.map(collect_run, keep) for line in group]
    merged, page = {}, 1
    while True:
        where = f"gh api pulls page {page}"
        got = as_list(gh(f"{base}/pulls?state=closed&base={BASE_BRANCH}&sort=updated&direction=desc"
                         f"&per_page={PAGE}&page={page}"), where)
        older = False
        for pr in got:
            as_obj(pr, where)
            n = as_int(pr, "number", where)
            at = f"{where} PR {n}"
            at_merge = as_time(pr, "merged_at", at, null=True)
            if secs(as_time(pr, "updated_at", at)) < secs(since):
                older = True
            if at_merge is not None and secs(since) <= secs(at_merge) < secs(until):
                merged[n] = at_merge
        # Newest first by update, and a merge updates a PR: once one was last
        # updated before the window, no later page holds a merge inside it.
        if len(got) < PAGE or older:
            break
        page += 1
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    write(out / "window.json", json.dumps({"since": since, "until": until}, indent=2, sort_keys=True) + "\n")
    write(out / "jobs.jsonl", "".join(line + "\n" for line in lines))
    write(out / "merged.json", json.dumps([{"merged_at": merged[n], "number": n} for n in sorted(merged)],
                                          indent=2, sort_keys=True) + "\n")
    print(f"collected {len(keep)} runs, {len(lines)} jobs and {len(merged)} merged PRs into {out}")


def utc_text(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_factory(d, since, until):
    where = f"{d}/factory.json"
    f = as_obj(strict_json(read_file(Path(d) / "factory.json"), where), where)
    exact(f, {"since", "until", "prs", "main", "reruns", "attempts", "jobs"}, where)
    if (as_time(f, "since", where), as_time(f, "until", where)) != (since, until):
        raise Fail(f"{where}: not this window's")
    for i, pr in enumerate(as_list(f["prs"], where)):
        at = f"{where} PR {i + 1}"
        exact(as_obj(pr, at), {"number", "merged_at", "verdicts", "verdicts_complete", "tickets", "tickets_complete"}, at)
        as_int(pr, "number", at)
        if not secs(since) <= secs(as_time(pr, "merged_at", at)) < secs(until):
            raise Fail(f"{at}: merged outside the window")
        if any(v not in ("APPROVE", "CHANGES") for v in as_list(pr["verdicts"], at)):
            raise Fail(f"{at}: unknown verdict")
        for t in as_list(pr["tickets"], at):
            exact(as_obj(t, at), {"number", "ready_at", "ready"}, at)
            as_int(t, "number", at)
            if (t["ready"] in ("label", "approval")) != (as_time(t, "ready_at", at, null=True) is not None) or \
                    t["ready"] not in ("label", "approval", "none", "incomplete"):
                raise Fail(f"{at}: bad ready record")
        for k in ("verdicts_complete", "tickets_complete"):
            if type(need(pr, k, at)) is not bool:
                raise Fail(f"{at}: '{k}' is not a boolean")
    main = as_obj(f["main"], f"{where} main")
    exact(main, {"observations", "carry_in", "untimed"}, f"{where} main")
    if type(main["carry_in"]) is not bool:
        raise Fail(f"{where} main: 'carry_in' is not a boolean")
    as_int(main, "untimed", f"{where} main")
    for o in as_list(main["observations"], f"{where} main"):
        at = f"{where} main observation"
        exact(as_obj(o, at), {"run", "attempt", "created_at", "finished_at", "verdict"}, at)
        as_int(o, "run", at), as_int(o, "attempt", at), as_time(o, "created_at", at), as_time(o, "finished_at", at)
        if o["verdict"] not in ("green", "red"):
            raise Fail(f"{at}: unknown verdict")
    for r in as_list(f["reruns"], where):
        at = f"{where} rerun"
        exact(as_obj(r, at), {"run", "attempt", "started_at", "cause"}, at)
        as_int(r, "run", at), as_time(r, "started_at", at)
        if as_int(r, "attempt", at) < 2 or r["cause"] not in CAUSES:
            raise Fail(f"{at}: bad rerun")
    for a in as_list(f["attempts"], where):
        at = f"{where} attempt"
        exact(as_obj(a, at), {"run", "attempt", "started_at"}, at)
        as_int(a, "run", at), as_int(a, "attempt", at), as_time(a, "started_at", at)
    for j in as_list(f["jobs"], where):
        at = f"{where} job"
        exact(as_obj(j, at), {"created_at", "started_at"}, at)
        as_time(j, "created_at", at), as_time(j, "started_at", at)
    return f


def spread(values, digits=4):
    if not values:
        return None, None
    return round(statistics.median(values), digits), round(nearest_rank(values, 0.9), digits)


def main_red(main, since, until):
    """Minutes main's newest-pushed finished run was red. Its state is the
    green or red attempt with the newest push (run creation, then run, then
    attempt) among those finished by then; unknown until one has."""
    def key(o):
        return secs(o["created_at"]), o["run"], o["attempt"]

    s, u = secs(since), secs(until)
    best = None
    for o in main["observations"]:
        if secs(o["finished_at"]) < s and (best is None or key(o) > key(best)):
            best = o
    t, red, unknown = s, 0, 0
    inside = sorted((o for o in main["observations"] if s <= secs(o["finished_at"]) < u),
                    key=lambda o: (secs(o["finished_at"]),) + key(o))
    for at, o in [(secs(o["finished_at"]), o) for o in inside] + [(u, None)]:
        if best is None:
            unknown += at - t
        elif best["verdict"] == "red":
            red += at - t
        if o is not None and (best is None or key(o) > key(best)):
            best = o
        t = at
    untimed = main["untimed"]
    return {"red_minutes": None if unknown or untimed else round(red / 60, 2),
            "unknown_minutes": round(unknown / 60, 2), "untimed_verdicts": untimed, "verdicts": len(inside)}


def first_closers(prs):
    """Each ticket's first merged closing PR (a PR whose closing tickets are
    all known), so a ticket counts once however its PRs are split."""
    first = {}
    for p in sorted(prs, key=lambda p: (secs(p["merged_at"]), p["number"])):
        if p["tickets_complete"]:
            for t in p["tickets"]:
                first.setdefault(t["number"], p["number"])
    return first


def factory_point(facts, since, until, first=None):
    """The factory record of [since, until): PRs by merge, reruns and
    attempts by start, waits by the job's creation, main red within it.
    `first` is the whole day's ticket owners, for a bucket of it."""
    s, u = secs(since), secs(until)

    def inside(t):
        return s <= secs(t) < u

    prs = [p for p in facts["prs"] if inside(p["merged_at"])]
    first = first_closers(prs) if first is None else first
    hours, unknown, unlinked = [], 0, 0
    for p in prs:
        if not p["tickets_complete"]:
            unknown += max(1, len(p["tickets"]))
            continue
        if not p["tickets"]:
            unlinked += 1
        for t in p["tickets"]:
            if first.get(t["number"]) != p["number"]:
                continue
            if t["ready_at"] is None or secs(t["ready_at"]) > secs(p["merged_at"]):
                unknown += 1
            else:
                hours.append((secs(p["merged_at"]) - secs(t["ready_at"])) / 3600)
    median, p90 = spread(hours)
    reviewed = [p for p in prs if p["verdicts"]]
    complete = [p for p in reviewed if p["verdicts_complete"]]
    first_approve = sum(p["verdicts"][0] == "APPROVE" for p in reviewed)
    waits = [(secs(j["started_at"]) - secs(j["created_at"])) / 60 for j in facts["jobs"]
             if inside(j["created_at"]) and secs(j["started_at"]) >= secs(j["created_at"])]
    wait_median, wait_p90 = spread(waits)
    causes = [r["cause"] for r in facts["reruns"] if inside(r["started_at"])]
    return {
        "merged_prs": len(prs),
        "ready_to_merged_hours": {"tickets": len(hours), "median": median, "p90": p90, "unknown_tickets": unknown,
                                  "unlinked_prs": unlinked},
        "first_review": {"reviewed_prs": len(reviewed), "first_approve": first_approve,
                         "share": round(first_approve / len(reviewed), 4) if reviewed else None,
                         "rounds_per_pr": round(sum(len(p["verdicts"]) for p in complete) / len(complete), 4)
                         if complete else None,
                         "rounds_prs": len(complete),
                         "unreviewed_prs": sum(not p["verdicts"] and p["verdicts_complete"] for p in prs),
                         "unknown_prs": sum(not p["verdicts"] and not p["verdicts_complete"] for p in prs)},
        "main_red": main_red(facts["main"], since, until),
        "reruns": {"total": len(causes), **{c: causes.count(c) for c in CAUSES},
                   "attempts": sum(inside(a["started_at"]) for a in facts["attempts"])},
        "runner_wait_minutes": {"jobs": len(waits), "median": wait_median, "p90": wait_p90},
    }


def show(v, fmt="{:.2f}"):
    return "unknown" if v is None else fmt.format(v)


def buckets(since, until, robots, table, runs, code, merged_times, facts, jobs):
    created = {rid: min(secs(j.get("run_created_at", j["created_at"])) for j in js) for rid, js in runs.items()}
    owners = first_closers(facts["prs"]) if facts is not None else None
    out = {}
    for name, hours in BUCKET_SIZES:
        rows, start = [], secs(since)
        while start < secs(until):
            end = min(start + 3600 * hours, secs(until))

            def inside(t):
                return start <= t < end

            selected = [r for r in code if inside(created[r[0]["run"]])]
            c = cohort(selected, table, False, robots, CODE_RULE)
            row = {"start": utc_text(start), "end": utc_text(end),
                   "ci": {"code_runs": len(selected), "minutes_per_pr": c["queued_to_done"]["median"] if c else None,
                          "prs_per_hour": c["prs_per_hour"] if c else None,
                          "merged_prs": sum(inside(secs(t)) for t in merged_times.values())}}
            if facts is not None:
                row["factory"] = factory_point(facts, row["start"], row["end"], owners)
            rows.append(row)
            start = end
        out[name] = rows
    return out


ESCAPES_KEYS = {"since", "until", "attempts", "failed_attempts", "escapes", "unknown"}


def read_escapes(d, since, until):
    where = f"{d}/escapes.json"
    e = as_obj(strict_json(read_file(Path(d) / "escapes.json"), where), where)
    exact(e, ESCAPES_KEYS, where)
    if (as_time(e, "since", where), as_time(e, "until", where)) != (since, until):
        raise Fail(f"{where}: its window is not window.json's")
    started = as_int(e, "attempts", where)
    failed = as_list(e["failed_attempts"], where)
    if any(not (type(f) is list and len(f) == 2 and all(type(n) is int and n > 0 for n in f)) for f in failed) \
            or len({tuple(f) for f in failed}) != len(failed) or len(failed) > started:
        raise Fail(f"{where}: failed_attempts is not a list of distinct [run, attempt]")
    for item in as_list(e["escapes"], where):
        if not (type(item) is list and len(item) == 4 and item[:2] in failed and type(item[2]) is int
                and type(item[3]) is str):
            raise Fail(f"{where}: an escape is not [failed run, attempt, pull request, test]")
    if any(type(u) is not str for u in as_list(e["unknown"], where)):
        raise Fail(f"{where}: unknown is not a list of reasons")
    return e


def escapes_point(e):
    """Counts only: unknown is never 0."""
    return {"count": None if e["unknown"] else len(e["escapes"]), "attempts": e["attempts"],
            "failed_attempts": len(e["failed_attempts"]), "unknown": len(e["unknown"])}


def escapes_cell(p):
    e = p.get("escapes")
    return "unknown" if e is None or e["count"] is None else str(e["count"])
