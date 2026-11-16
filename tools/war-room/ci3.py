#!/usr/bin/env python3
"""CI3's one measure (contracts/ci3.v1.md): the time to a PR's result.

    ci3.py collect --since T --until T --out FILE   read a window from GitHub (gh api, GET only, through bench_measure.py)
    ci3.py measure FILE [--label TEXT]              print the window's record (openwiz.ci3.v1) on stdout
    ci3.py check-steps [--workflow FILE]           require a row of steps.tsv for every step of ci.yml

T is a UTC time, YYYY-MM-DDTHH:MM:SSZ. A window holds the PR heads whose
clock starts at or after --since and before --until. Python 3 standard
library only, and gh. `measure` is offline: the same FILE always prints the
same record.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path
import re
import sys
import time
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
# The war room's copy of the bench's reader, checks and step table (#822, #826): nothing from tools/ci-bench/.
import bench_measure as bench  # noqa: E402

from bench_measure import Fail, as_int, as_list, as_obj, as_str, as_time, need, secs  # noqa: E402

VERSION = "ci3.v1"
SCHEMA = "openwiz.ci3.v1"
WINDOW_SCHEMA = "openwiz.ci3-window.v1"
# The required checks on main today: workflow file and the job whose name is the check.
REQUIRED = {"ci.yml": "ci", "privacy.yml": "privacy"}
# A head's activity: what moves a branch to a new commit.
PUSHES = {"push", "force_push", "branch_creation"}
ACTIVITY_PAGE = 100
RED = {"failure", "timed_out", "startup_failure", "action_required", "stale"}
RUNNING = {"web", "rust", "build", "skills"}


def utc(seconds):
    return bench.utc_text(seconds)


def rank(values, p):
    """Nearest rank: the ceil(p x n)-th smallest value."""
    return bench.nearest_rank(values, p) if values else None


# ---------------------------------------------------------------- collecting


def read_pr_list(since, until, read):
    """Every PR into main whose life overlaps the window, newest update first."""
    base = "repos/{owner}/{repo}"
    prs, page = {}, 1
    while True:
        where = f"gh api pulls page {page}"
        got = as_list(read(f"{base}/pulls?state=all&base={bench.BASE_BRANCH}&sort=updated&direction=desc"
                           f"&per_page={bench.PAGE}&page={page}"), where)
        older = False
        for pr in got:
            as_obj(pr, where)
            n = as_int(pr, "number", where)
            at = f"{where} PR {n}"
            created, closed = as_time(pr, "created_at", at), as_time(pr, "closed_at", at, null=True)
            if secs(as_time(pr, "updated_at", at)) < secs(since):
                older = True
                continue
            head = as_obj(need(pr, "head", at), at)
            repo = need(head, "repo", at)
            fork = repo is None or as_str(as_obj(repo, at), "full_name", at) != as_str(
                as_obj(need(as_obj(need(pr, "base", at), at), "repo", at), at), "full_name", at)
            if secs(created) < secs(until) and (closed is None or secs(closed) >= secs(since)):
                prs[n] = {"number": n, "ref": as_str(head, "ref", at), "created_at": created, "closed_at": closed,
                          "fork": fork}
        # A push to a PR's branch updates the PR: once one was last updated
        # before the window, no later page holds a head inside it.
        if len(got) < bench.PAGE or older:
            break
        page += 1
    return [prs[n] for n in sorted(prs)]


def read_pushes(ref, read):
    path = (f"repos/{{owner}}/{{repo}}/activity?ref={quote('refs/heads/' + ref, safe='/')}"
            f"&per_page={ACTIVITY_PAGE}")
    where = f"gh api {path}"
    got = as_list(read(path), where)
    if len(got) >= ACTIVITY_PAGE:
        raise Fail(f"{where}: {ACTIVITY_PAGE} or more pushes on one branch; the window can't be read complete")
    out = []
    for a in got:
        as_obj(a, where)
        if as_str(a, "activity_type", where) in PUSHES:
            out.append({"sha": as_str(a, "after", where), "at": as_time(a, "timestamp", where)})
    return sorted(out, key=lambda p: (secs(p["at"]), p["sha"]))


def heads_of(pr, pushes):
    """The PR's heads: the commit it opened at, then each push while it was open.
    A head's clock starts when it became the PR's head: the later of its push
    and the PR's opening."""
    created, closed = secs(pr["created_at"]), secs(pr["closed_at"]) if pr["closed_at"] else math.inf
    before = [p for p in pushes if secs(p["at"]) <= created]
    heads = []
    if before:
        heads.append({"sha": before[-1]["sha"], "pushed_at": before[-1]["at"], "start": pr["created_at"]})
    else:
        heads.append({"sha": None, "pushed_at": None, "start": pr["created_at"]})
    for p in pushes:
        if created < secs(p["at"]) < closed:
            heads.append({"sha": p["sha"], "pushed_at": p["at"], "start": p["at"]})
    seen, out = set(), []
    for h in heads:
        if h["sha"] is not None and h["sha"] in seen:
            continue
        seen.add(h["sha"])
        out.append(h)
    return out


def read_jobs(rid, attempt, read):
    jobs = []
    for job, where in bench.pages(f"repos/{{owner}}/{{repo}}/actions/runs/{rid}/attempts/{attempt}/jobs"
                                  f"?per_page={bench.PAGE}", "jobs", "jobs", read):
        as_obj(job, where)
        at = f"{where} job"
        steps = [{"name": as_str(as_obj(s, at), "name", at),
                  "started_at": as_time(s, "started_at", at, null=True),
                  "completed_at": as_time(s, "completed_at", at, null=True)}
                 for s in as_list(need(job, "steps", at), at)]
        jobs.append({"id": as_int(job, "id", at), "name": as_str(job, "name", at),
                     "conclusion": as_str(job, "conclusion", at, null=True),
                     "created_at": as_time(job, "created_at", at),
                     "started_at": as_time(job, "started_at", at, null=True),
                     "completed_at": as_time(job, "completed_at", at, null=True),
                     "runner_name": as_str(job, "runner_name", at, null=True), "steps": steps,
                     # The attempt that ran it: a rerun of failed jobs lists the earlier attempt's jobs again.
                     "run_attempt": as_int(job, "run_attempt", at)})
        if not 1 <= jobs[-1]["run_attempt"] <= attempt:
            raise Fail(f"{at}: job {jobs[-1]['id']} of attempt {jobs[-1]['run_attempt']} listed in attempt {attempt}")
    return sorted(jobs, key=lambda j: j["id"])


def read_run(run, where, read):
    """One run with every attempt's jobs: reruns stay in."""
    rid = as_int(run, "id", where)
    attempts = as_int(run, "run_attempt", where)
    return {"id": rid, "event": as_str(run, "event", where), "created_at": as_time(run, "created_at", where),
            "updated_at": as_time(run, "updated_at", where), "status": as_str(run, "status", where),
            "conclusion": as_str(run, "conclusion", where, null=True),
            "attempts": [{"attempt": k, "jobs": read_jobs(rid, k, read)} for k in range(1, attempts + 1)]}


def first_run(sha, workflow, event, start, read):
    """The first run of a workflow on a head, at or after its clock starts."""
    runs = []
    for run, where in bench.pages(f"repos/{{owner}}/{{repo}}/actions/workflows/{workflow}/runs?head_sha={sha}"
                                  f"&event={event}&per_page={bench.PAGE}", "workflow_runs", "runs", read):
        as_obj(run, where)
        if as_str(run, "head_sha", where) != sha:
            raise Fail(f"{where}: a run of another head")
        created = as_time(run, "created_at", where)
        if start is None or secs(created) >= secs(start):
            runs.append((secs(created), as_int(run, "id", where), run, where))
    if not runs:
        return None
    _, _, run, where = min(runs, key=lambda r: r[:2])
    return read_run(run, where, read)


def collect_head(pr, head, read):
    runs = {}
    if head["sha"] is not None:
        for wf in sorted(REQUIRED):
            runs[wf] = first_run(head["sha"], wf, "pull_request", head["start"], read)
    return {"pr": pr["number"], "sha": head["sha"], "pushed_at": head["pushed_at"], "start": head["start"],
            "fork": pr["fork"], "runs": runs}


def collect_groups(since, until, read):
    """The merge queue's groups: the first run of each required workflow per group head."""
    shas = {}
    for wf in sorted(REQUIRED):
        for run, where in bench.pages(f"repos/{{owner}}/{{repo}}/actions/workflows/{wf}/runs?event=merge_group"
                                      f"&created={since}..{until}&per_page={bench.PAGE}", "workflow_runs", "runs", read):
            as_obj(run, where)
            created = as_time(run, "created_at", where)
            if secs(since) <= secs(created) < secs(until):
                shas.setdefault(as_str(run, "head_sha", where), {}).setdefault(wf, []).append(
                    (secs(created), as_int(run, "id", where), run, where))
    groups = []
    for sha in sorted(shas):
        runs = {}
        for wf in sorted(REQUIRED):
            found = shas[sha].get(wf)
            runs[wf] = read_run(*min(found, key=lambda r: r[:2])[2:], read) if found else None
        groups.append({"sha": sha, "runs": runs})
    return groups


def collect(since, until, out, workers=1, read=None, now=None):
    read = read or bench.gh
    if secs(until) <= secs(since):
        raise Fail("--until must be after --since")
    prs = read_pr_list(since, until, read)
    work = []
    for pr in prs:
        if pr["fork"]:
            raise Fail(f"PR #{pr['number']} is from a fork: its pushes aren't in this repository's activity,"
                       " so the window's heads can't be read complete")
        pushes = read_pushes(pr["ref"], read)
        for head in heads_of(pr, pushes):
            if secs(since) <= secs(head["start"]) < secs(until):
                work.append((pr, head))
    if workers == 1:
        heads = [collect_head(pr, h, read) for pr, h in work]
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            heads = list(pool.map(lambda w: collect_head(w[0], w[1], read), work))
    window = {"schema": WINDOW_SCHEMA, "since": since, "until": until,
              "collected_at": now or utc(time.time()),
              "heads": heads, "groups": collect_groups(since, until, read)}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    bench.write(out, json.dumps(window, indent=1, sort_keys=True) + "\n")
    print(f"collected {len(heads)} PR heads of {len(prs)} PRs and {len(window['groups'])} merge groups into {out}",
          file=sys.stderr)


# ---------------------------------------------------------------- measuring


def check_result(run, job_name):
    """A required check's final result on one run: (outcome, end, attempt) or a missing reason."""
    if run is None:
        return None, "no run"
    if run["status"] != "completed":
        return None, "unfinished"
    final = run["attempts"][-1]
    jobs = [j for j in final["jobs"] if j["name"] == job_name]
    if len(jobs) > 1:
        raise Fail(f"run {run['id']}: {len(jobs)} jobs named {job_name}")
    if jobs and jobs[0]["completed_at"] is not None and jobs[0]["conclusion"] is not None:
        return {"outcome": jobs[0]["conclusion"], "end": jobs[0]["completed_at"], "attempt": final, "job": jobs[0]}, None
    # The check never reported (a run cancelled before it): the run's own end and
    # conclusion stand for it, anchored at its last job, or its update with none.
    done = [j for j in owned(final) if j["completed_at"] is not None]
    anchor = max(done, key=lambda j: (secs(j["completed_at"]), j["id"])) if done else None
    end = anchor["completed_at"] if anchor else run["updated_at"]
    return {"outcome": run["conclusion"] or "cancelled", "end": end, "attempt": final, "job": anchor}, None


def owned(attempt):
    """The jobs this attempt ran itself, not those carried from an earlier one."""
    return [j for j in attempt["jobs"] if j["run_attempt"] == attempt["attempt"]]


def outcome_of(outcomes):
    if all(o == "success" for o in outcomes):
        return "success"
    if any(o in RED for o in outcomes):
        return "failure"
    if any(o == "cancelled" for o in outcomes):
        return "cancelled"
    return "other"


def job_secs(job):
    # A job that never got a runner (none, and no steps) held one for no time, as the bench counts it.
    if job["started_at"] is None or bench.never_ran(job) or job["completed_at"] is None:
        return 0
    return max(0, secs(job["completed_at"]) - secs(job["started_at"]))


def critical_path(attempt, last):
    """The jobs the last job waited on, newest first: each one's predecessor is the
    job of the same attempt that finished last before it was created."""
    path, cur = [], last
    while cur is not None:
        path.append(cur)
        done = [j for j in owned(attempt) if j["id"] not in {p["id"] for p in path}
                and j["completed_at"] is not None and secs(j["completed_at"]) <= secs(cur["created_at"])]
        cur = max(done, key=lambda j: (secs(j["completed_at"]), j["id"])) if done else None
    return path


def split(path, total, table):
    """waiting + setup + running (+ unclassified) == total, in seconds."""
    setup = running = unclassified = 0
    for job in path:
        whole = job_secs(job)
        covered = 0
        for step in job["steps"]:
            d = bench.duration(step)
            covered += d
            try:
                cat = bench.category(table, step["name"], job["name"])
            except Fail:
                unclassified += d
                continue
            if cat in RUNNING:
                running += d
            else:
                setup += d
        # A job's time no step covers is setup, as the bench counts it.
        setup += max(0, whole - covered)
    on_runner = setup + running + unclassified
    return {"waiting": max(0, total - on_runner), "setup": setup, "running": running, "unclassified": unclassified}


def result(item, start, table):
    """One head's (or group's) time to its result, or the reason it is missing."""
    checks, missing = {}, []
    for wf, name in sorted(REQUIRED.items()):
        got, why = check_result(item["runs"].get(wf), name)
        if got is None:
            missing.append(f"{name}: {why}")
        else:
            checks[name] = got
    if missing:
        return None, "; ".join(missing)
    last = max(checks.values(), key=lambda c: secs(c["end"]))
    total = secs(last["end"]) - secs(start)
    if total < 0:
        raise Fail(f"{item.get('sha')}: its result ends before its clock starts")
    attempts = sum(len(item["runs"][wf]["attempts"]) for wf in REQUIRED)
    out = {"seconds": total, "outcome": outcome_of([c["outcome"] for c in checks.values()]),
           "reruns": attempts - len(REQUIRED)}
    path = critical_path(last["attempt"], last["job"]) if last["job"] is not None else []
    out["buckets"] = split(path, total, table)
    if sum(out["buckets"].values()) != total:
        raise Fail(f"{item.get('sha')}: its buckets don't add up to its time")
    return out, None


def runner_seconds(items):
    return sum(job_secs(j) for it in items for run in it["runs"].values() if run
               for a in run["attempts"] for j in owned(a))


def minutes(s):
    return None if s is None else round(s / 60, 1)


def summary(results):
    times = [r["seconds"] for r in results]
    counts = {k: sum(1 for r in results if r["outcome"] == k) for k in ("success", "failure", "cancelled", "other")}
    by = {}
    for k in ("success", "failure", "cancelled"):
        t = [r["seconds"] for r in results if r["outcome"] == k]
        by[k] = {"p50_minutes": minutes(rank(t, 0.5)), "p95_minutes": minutes(rank(t, 0.95))}
    return {"p50_minutes": minutes(rank(times, 0.5)), "p95_minutes": minutes(rank(times, 0.95)), "timed": len(times),
            "outcomes": counts, "by_outcome": by, "with_reruns": sum(1 for r in results if r["reruns"])}


def buckets(results):
    parts = ("waiting", "setup", "running", "unclassified")
    split_ = [r["buckets"] for r in results if "buckets" in r]
    total = sum(sum(b[k] for k in parts) for b in split_)
    out = {"results": len(split_)}
    for k in parts:
        vals = [b[k] for b in split_]
        out[k] = {"share": round(sum(vals) / total, 3) if total else None,
                  "p50_seconds": rank(vals, 0.5), "p95_seconds": rank(vals, 0.95)}
    return out


def read_window(path):
    w = as_obj(bench.strict_json(bench.read_file(path), str(path)), str(path))
    if w.get("schema") != WINDOW_SCHEMA:
        raise Fail(f"{path}: not {WINDOW_SCHEMA}")
    bench.exact(w, {"schema", "since", "until", "collected_at", "heads", "groups"}, str(path))
    for k in ("since", "until", "collected_at"):
        as_time(w, k, str(path))
    for i, h in enumerate(as_list(w["heads"], path)):
        at = f"{path} head {i + 1}"
        bench.exact(as_obj(h, at), {"pr", "sha", "pushed_at", "start", "fork", "runs"}, at)
        as_int(h, "pr", at), as_str(h, "sha", at, null=True), as_time(h, "pushed_at", at, null=True)
        as_time(h, "start", at)
        if type(h["fork"]) is not bool:
            raise Fail(f"{at}: fork must be true or false")
        check_runs(h["runs"], at, allowed=set() if h["sha"] is None else set(REQUIRED))
    for i, g in enumerate(as_list(w["groups"], path)):
        at = f"{path} group {i + 1}"
        bench.exact(as_obj(g, at), {"sha", "runs"}, at)
        as_str(g, "sha", at)
        check_runs(g["runs"], at, allowed=set(REQUIRED))
    return w


def check_runs(runs, where, allowed):
    """A head's or group's runs, in exactly the shape collect writes."""
    bench.exact(as_obj(runs, where), allowed, where)
    for wf, run in runs.items():
        at = f"{where} {wf}"
        if run is None:
            continue
        bench.exact(as_obj(run, at), {"id", "event", "created_at", "updated_at", "status", "conclusion", "attempts"}, at)
        as_int(run, "id", at), as_str(run, "event", at), as_str(run, "status", at)
        as_str(run, "conclusion", at, null=True), as_time(run, "created_at", at), as_time(run, "updated_at", at)
        attempts = as_list(run["attempts"], at)
        if not attempts:
            raise Fail(f"{at}: a run with no attempts")
        for k, a in enumerate(attempts, 1):
            aat = f"{at} attempt {k}"
            bench.exact(as_obj(a, aat), {"attempt", "jobs"}, aat)
            if as_int(a, "attempt", aat) != k:
                raise Fail(f"{aat}: attempts out of order")
            for job in as_list(a["jobs"], aat):
                jat = f"{aat} job"
                bench.exact(as_obj(job, jat), {"id", "name", "conclusion", "created_at", "started_at", "completed_at",
                                               "runner_name", "steps", "run_attempt"}, jat)
                if not 1 <= as_int(job, "run_attempt", jat) <= k:
                    raise Fail(f"{jat}: job of attempt {job['run_attempt']} listed in attempt {k}")
                as_int(job, "id", jat), as_str(job, "name", jat), as_time(job, "created_at", jat)
                as_str(job, "conclusion", jat, null=True), as_str(job, "runner_name", jat, null=True)
                as_time(job, "started_at", jat, null=True), as_time(job, "completed_at", jat, null=True)
                for step in as_list(job["steps"], jat):
                    bench.exact(as_obj(step, jat), {"name", "started_at", "completed_at"}, jat)
                    as_str(step, "name", jat)
                    as_time(step, "started_at", jat, null=True), as_time(step, "completed_at", jat, null=True)


def measure(window, label=None, table=None):
    """The window's record, in the contract's record form. Deterministic: no clock, no network."""
    table = table or bench.read_table(bench.STEPS)
    since, until = window["since"], window["until"]
    timed, missing = [], []
    for h in sorted(window["heads"], key=lambda h: (h["pr"], secs(h["start"]), h["sha"] or "")):
        if not secs(since) <= secs(h["start"]) < secs(until):
            raise Fail(f"PR #{h['pr']} head {h['sha']}: its clock starts outside the window")
        if h["sha"] is None:
            got, why = None, "push time unknown"
        else:
            got, why = result(h, h["start"], table)
        if got is None:
            missing.append({"pr": h["pr"], "head": h["sha"], "reason": why})
        else:
            timed.append(got)
    groups, group_missing = [], 0
    for g in window["groups"]:
        starts = [secs(r["created_at"]) for r in g["runs"].values() if r]
        got, _ = result(g, utc(min(starts)), table) if starts else (None, "no run")
        if got is None:
            group_missing += 1
        else:
            groups.append(got)
    pr_runner = runner_seconds(window["heads"])
    queue_runner = runner_seconds(window["groups"])
    days = (secs(until) - secs(since)) / 86400
    return {
        "schema": SCHEMA, "measure": VERSION, "label": label, "since": since, "until": until,
        "collected_at": window["collected_at"], "required_checks": sorted(REQUIRED.values()),
        "heads": len(window["heads"]), "prs": len({h["pr"] for h in window["heads"]}),
        "result": summary(timed), "missing": missing,
        "critical_path": buckets(timed),
        "merge_queue": dict(summary(groups), groups=len(window["groups"]), missing=group_missing),
        "runner_minutes": {"pr_heads": minutes(pr_runner), "merge_queue": minutes(queue_runner),
                           "total": minutes(pr_runner + queue_runner),
                           "per_day": minutes((pr_runner + queue_runner) / days)},
    }


# ---------------------------------------------------------------- step coverage


def check_steps(workflow):
    """Every step of the workflow has exactly one row in the step table, so CI3's critical path
    classifies it. Moved with the table from ci-bench's `bench.py check-steps` (#826), unchanged:
    explicit names are API names; otherwise GitHub prefixes uses/run with Run. Parse step entries,
    not name/run words inside scripts or comments, and refuse unnamed multiline runs."""
    table = bench.read_table(bench.STEPS)
    entries = re.split(r"(?m)^      - ", bench.read_file(workflow))[1:]
    if not entries:
        raise Fail(f"{workflow}: no steps found")
    for entry in entries:
        fields = {}
        for line in entry.splitlines():
            match = re.match(r"^(?:        )?(name|run|uses):\s*(.*?)\s*$", line)
            if match:
                fields[match[1]] = re.sub(r"\s+#.*$", "", match[2]).strip("\"'")
        if "name" in fields:
            name = re.sub(r"\$\{\{.*?\}\}", "*", fields["name"])
        elif "uses" in fields:
            name = "Run " + fields["uses"]
        elif "run" in fields and fields["run"] not in ("|", ">", "|-", ">-"):
            name = "Run " + fields["run"]
        else:
            raise Fail(f"{workflow}: step needs an explicit name")
        bench.category(table, name, str(workflow))
    print(f"covered {len(entries)} CI steps")


def main(argv=None):
    p = argparse.ArgumentParser(prog="ci3.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--since", required=True)
    c.add_argument("--until", required=True)
    c.add_argument("--out", required=True)
    c.add_argument("--workers", type=int, default=1, choices=range(1, 5))
    m = sub.add_parser("measure")
    m.add_argument("file")
    m.add_argument("--label")
    k = sub.add_parser("check-steps")
    k.add_argument("--workflow", default=str(ROOT / ".github" / "workflows" / "ci.yml"))
    args = p.parse_args(argv)
    try:
        if args.cmd == "collect":
            for t in (args.since, args.until):
                if not bench.TIME.fullmatch(t):
                    p.error(f"not a UTC time: {t}")
            collect(args.since, args.until, args.out, args.workers)
        elif args.cmd == "check-steps":
            check_steps(args.workflow)
        else:
            print(json.dumps(measure(read_window(args.file), args.label), indent=2, sort_keys=True))
    except Fail as e:
        print(f"ci3: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
