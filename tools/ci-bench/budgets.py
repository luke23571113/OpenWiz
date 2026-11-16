#!/usr/bin/env python3
"""CI3 C1 (#782): time budgets that fail, read from real runs.

    budgets.py collect --workflow W [--runs 150] [--since T] --out DIR   read W's last completed runs (gh api, GET only)
    budgets.py table DIR [--fallback DIR] [--after DIR --after-jobs JOB...] [--out budgets.tsv]
                                                                         each job's p95 and budget, from DIR's runs
    budgets.py apply [--table budgets.tsv] [WORKFLOW...]                 set each job's timeout-minutes from the table
    budgets.py check [--table budgets.tsv] [WORKFLOW...]                 fail on a job with no row or another timeout

A budget is 1.5x the job's p95 running time (started to completed), rounded
up to a whole minute, at least 5 minutes. WORKFLOW defaults to the CI and
Privacy workflows. Python 3 standard library only, and gh. See README.md.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TABLE = HERE / "budgets.tsv"
WORKFLOWS = [ROOT / ".github/workflows/ci.yml", ROOT / ".github/workflows/privacy.yml"]
RUNS, FLOOR, MIN_SAMPLES = 150, 5, 5
COLUMNS = ["workflow", "job", "mode", "timeout", "p95_seconds", "samples", "runs", "first", "last"]
# A job that runs trace.py or planted.py's records in traced and planted runs
# carries this step; its timeout then has a traced budget and a normal one.
MARK = "if: needs.changes.outputs.trace == 'true' || needs.changes.outputs.planted == 'true'"
TRACED = ("${{ (needs.changes.outputs.trace == 'true' || needs.changes.outputs.planted == 'true')"
          " && %d || %d }}")
TRACED_RE = re.compile(r"\$\{\{ \(needs\.changes\.outputs\.trace == 'true' \|\| needs\.changes\.outputs\.planted"
                       r" == 'true'\) && (\d+) \|\| (\d+) \}\}")
# In a traced or planted run, the step right after a lane's tests uploads
# the trace records; in any other run it is skipped (ci.yml, `MARK`).
LANE_TESTS = {"Run cargo test --workspace", "Run npm test"}
UPLOAD = "Run actions/upload-artifact@"
COUNTED = {"success", "failure"}


sys.dont_write_bytecode = True


def bench():
    spec = importlib.util.spec_from_file_location("ci_bench", HERE / "bench.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


B = bench()
Fail = B.Fail


def budget(p95_seconds):
    """1.5 x p95, rounded up to a whole minute, at least FLOOR: ceil(3s / 120)."""
    return max(FLOOR, -(-3 * p95_seconds // 120))


# ---------------------------------------------------------------- workflows

def read_workflow(path):
    """Each job's key, its timeout-minutes line (index, value) and whether it carries MARK."""
    lines = B.read_file(path).splitlines(keepends=True)
    jobs, key, inside = {}, None, False
    for i, line in enumerate(lines):
        if re.match(r"^jobs:\s*$", line):
            inside = True
            continue
        if not inside:
            continue
        if re.match(r"^\S", line):
            inside = False
            continue
        m = re.match(r"^  ([A-Za-z0-9_-]+):\s*(#.*)?$", line)
        if m:
            key = m[1]
            jobs[key] = {"timeout": None, "marked": False}
            continue
        if key is None:
            continue
        m = re.match(r"^    timeout-minutes:\s*(.*?)\s*(#.*)?$", line)
        if m:
            if jobs[key]["timeout"] is not None:
                raise Fail(f"{Path(path).name} job {key} has two timeout-minutes lines")
            jobs[key]["timeout"] = (i, m[1])
        elif line.strip() == MARK:
            jobs[key]["marked"] = True
    if not jobs:
        raise Fail(f"{path}: no jobs found")
    return lines, jobs


def parse_timeout(value):
    """('all', n) for a plain number, ('traced', traced, normal) for the traced form, None otherwise."""
    if re.fullmatch(r"\d+", value):
        return ("all", int(value))
    m = TRACED_RE.fullmatch(value)
    if m:
        return ("traced", int(m[1]), int(m[2]))
    return None


# ---------------------------------------------------------------- the table

def read_table(path):
    lines = B.read_file(path).splitlines()
    if not lines or lines[0].split("\t") != COLUMNS:
        raise Fail(f"{path}: the first line must be the columns {' '.join(COLUMNS)}")
    rows = {}
    for n, line in enumerate(lines[1:], 2):
        f = line.split("\t")
        if len(f) != len(COLUMNS):
            raise Fail(f"{path} line {n}: {len(f)} fields, not {len(COLUMNS)}")
        r = dict(zip(COLUMNS, f))
        if r["mode"] not in ("all", "normal", "traced"):
            raise Fail(f"{path} line {n}: mode {r['mode']!r} is not all, normal or traced")
        for k in ("timeout", "p95_seconds", "samples", "runs"):
            if not re.fullmatch(r"\d+", r[k]):
                raise Fail(f"{path} line {n}: {k} {r[k]!r} is not a whole number")
            r[k] = int(r[k])
        ident = (r["workflow"], r["job"], r["mode"])
        if ident in rows:
            raise Fail(f"{path} line {n}: {' '.join(ident)} is listed twice")
        rows[ident] = r
    return rows


def write_table(path, rows):
    text = "\t".join(COLUMNS) + "\n"
    for r in rows:
        text += "\t".join(str(r[k]) for k in COLUMNS) + "\n"
    B.write(Path(path), text)


def expected(rows, wf, key):
    """The timeout a job's rows give it: ('all', n) or ('traced', traced, normal)."""
    modes = {m: r for (w, j, m), r in rows.items() if (w, j) == (wf, key)}
    if not modes:
        return None
    if set(modes) == {"all"}:
        return ("all", modes["all"]["timeout"])
    if set(modes) == {"normal", "traced"}:
        return ("traced", modes["traced"]["timeout"], modes["normal"]["timeout"])
    raise Fail(f"{wf} job {key}: its rows must be one all row, or one normal and one traced row")


def timeout_text(want):
    return str(want[1]) if want[0] == "all" else TRACED % (want[1], want[2])


def check(table, workflows):
    rows = read_table(table)
    errors = []
    for (wf, key, mode), r in sorted(rows.items()):
        if r["timeout"] != budget(r["p95_seconds"]):
            errors.append(f"{wf} {key} {mode}: timeout {r['timeout']}, but 1.5x its p95 of {r['p95_seconds']} s"
                          f" is {budget(r['p95_seconds'])}")
    seen = set()
    for path in workflows:
        wf = Path(path).name
        _, jobs = read_workflow(path)
        for key, j in jobs.items():
            seen.add((wf, key))
            want = expected(rows, wf, key)
            if want is None:
                errors.append(f"{wf} job {key} has no budget row")
                continue
            if j["timeout"] is None:
                errors.append(f"{wf} job {key} has no timeout-minutes")
                continue
            got = parse_timeout(j["timeout"][1])
            if got is None:
                errors.append(f"{wf} job {key}: timeout-minutes {j['timeout'][1]!r} is neither a number nor the"
                              " traced form")
            elif got[0] == "all" and want[0] == "traced":
                errors.append(f"{wf} job {key}: timeout-minutes {got[1]} has no traced budget")
            elif got[0] == "traced" and want[0] == "all":
                errors.append(f"{wf} job {key}: a traced timeout-minutes, but its budget has no traced row")
            elif got[0] == "all" and got[1] != want[1]:
                errors.append(f"{wf} job {key}: timeout-minutes {got[1]}, its budget is {want[1]}")
            elif got[0] == "traced":
                for mode, g, w in (("traced", got[1], want[1]), ("normal", got[2], want[2])):
                    if g != w:
                        errors.append(f"{wf} job {key}: {mode} timeout-minutes {g}, its budget is {w}")
    for wf, key in sorted({(w, j) for w, j, _ in rows} - seen):
        errors.append(f"{wf} has no job {key} for its budget row")
    for e in errors:
        print(f"budgets: {e}", file=sys.stderr)
    if errors:
        return 1
    print(f"budgets: {len(seen)} jobs in {len(workflows)} workflows match {len(rows)} rows")
    return 0


def apply(table, workflows):
    rows = read_table(table)
    for path in workflows:
        wf = Path(path).name
        lines, jobs = read_workflow(path)
        for key, j in jobs.items():
            want = expected(rows, wf, key)
            if want is None:
                raise Fail(f"{wf} job {key} has no budget row")
            if j["timeout"] is None:
                raise Fail(f"{wf} job {key} has no timeout-minutes line to set")
            i, value = j["timeout"]
            lines[i] = lines[i].replace(f"timeout-minutes: {value}", f"timeout-minutes: {timeout_text(want)}", 1)
        B.write(Path(path), "".join(lines))
    return check(table, workflows)


# ---------------------------------------------------------------- reading runs

def collect(workflow, runs, since, out, per_page=100):
    base = "repos/{owner}/{repo}/actions"
    query = "status=completed" + (f"&created=>={since}" if since else "")
    listed, seen, page = [], set(), 1
    while len(listed) < runs:
        where = f"gh api {workflow} runs page {page}"
        ans = B.as_obj(B.gh(f"{base}/workflows/{workflow}/runs?{query}&per_page={per_page}&page={page}"), where)
        got = B.as_list(B.need(ans, "workflow_runs", where), where)
        if not got:
            break
        for run in got:
            B.as_obj(run, where)
            rid = B.as_int(run, "id", where)
            at = f"{where} run {rid}"
            if rid in seen:
                raise Fail(f"{at}: listed twice")
            seen.add(rid)
            if B.as_str(run, "status", at) != "completed":
                raise Fail(f"{at}: not completed")
            listed.append({"id": rid, "event": B.as_str(run, "event", at),
                           "conclusion": B.as_str(run, "conclusion", at, null=True),
                           "created_at": B.as_time(run, "created_at", at), "attempt": B.as_int(run, "run_attempt", at)})
        page += 1
    listed = listed[:runs]
    lines = []
    for run in listed:
        rid = run["id"]
        for job, where in B.pages(f"{base}/runs/{rid}/jobs?filter=latest&per_page=100", "jobs", "jobs"):
            at = f"{where} run {rid} job"
            B.as_obj(job, at)
            steps = []
            for step in B.as_list(B.need(job, "steps", at), at):
                B.as_obj(step, at)
                steps.append({"completed_at": B.as_time(step, "completed_at", at, null=True),
                              "conclusion": B.as_str(step, "conclusion", at, null=True),
                              "name": B.as_str(step, "name", at),
                              "started_at": B.as_time(step, "started_at", at, null=True)})
            record = {"completed_at": B.as_time(job, "completed_at", at),
                      "conclusion": B.as_str(job, "conclusion", at, null=True),
                      "created_at": B.as_time(job, "created_at", at), "event": run["event"],
                      "name": B.as_str(job, "name", at), "run": rid, "run_concl": run["conclusion"],
                      "runner_name": B.as_str(job, "runner_name", at, null=True),
                      "started_at": B.as_time(job, "started_at", at), "steps": steps,
                      "id": B.as_int(job, "id", at), "run_attempt": B.as_int(job, "run_attempt", at),
                      "collected_attempt": run["attempt"], "run_created_at": run["created_at"]}
            lines.append(json.dumps(record, sort_keys=True))
        # A rerun between the list and the jobs would mix attempts (bench.py, #383 R2).
        where = f"gh api {base}/runs/{rid}"
        again = B.as_obj(B.gh(f"{base}/runs/{rid}"), where)
        after = (B.as_int(again, "run_attempt", where), B.as_str(again, "status", where),
                 B.as_str(again, "conclusion", where, null=True))
        if after != (run["attempt"], "completed", run["conclusion"]):
            raise Fail(f"{where}: run {rid} changed while it was read; read again once its reruns have finished")
    d = Path(out) / workflow.removesuffix(".yml")
    d.mkdir(parents=True, exist_ok=True)
    created = sorted(r["created_at"] for r in listed)
    B.write(d / "window.json", json.dumps({"workflow": workflow, "runs": len(listed),
                                           "first": created[0] if created else None,
                                           "last": created[-1] if created else None},
                                          indent=2, sort_keys=True) + "\n")
    B.write(d / "jobs.jsonl", "".join(line + "\n" for line in lines))
    print(f"budgets: collected {len(listed)} {workflow} runs and {len(lines)} jobs into {d}")


def read_window(d, workflow):
    d = Path(d) / workflow.removesuffix(".yml")
    w = B.as_obj(B.strict_json(B.read_file(d / "window.json"), f"{d}/window.json"), f"{d}/window.json")
    jobs = B.read_jobs(d) if B.read_file(d / "jobs.jsonl") else []
    return w, jobs


def traced_runs(jobs):
    """Runs whose lane tests were followed by a trace upload that ran, and scheduled (nightly) runs."""
    traced = {j["run"] for j in jobs if j["event"] == "schedule"}
    for j in jobs:
        steps = j["steps"]
        for a, b in zip(steps, steps[1:]):
            if a["name"] in LANE_TESTS and b["name"].startswith(UPLOAD) and b["conclusion"] not in (None, "skipped"):
                traced.add(j["run"])
    return traced


def samples(jobs, key, mode, traced):
    """(leg, run, run created, running seconds) for each job named KEY or KEY (matrix values) that ran to success or failure."""
    out = []
    for j in jobs:
        if j["name"] != key and not j["name"].startswith(key + " ("):
            continue
        if j["conclusion"] not in COUNTED or B.never_ran(j):
            continue
        if mode != "all" and (j["run"] in traced) != (mode == "traced"):
            continue
        out.append((j["name"], j["run"], j.get("run_created_at", j["created_at"]), B.secs(j["completed_at"]) - B.secs(j["started_at"])))
    return out


def own_runs(got):
    """Only the job's own last RUNS runs, and the runs, first and last that describe them."""
    created = {run: at for _, run, at, _ in got}
    keep = set(sorted(created, key=lambda r: (created[r], r))[-RUNS:])
    times = sorted(created[r] for r in keep)
    return [g for g in got if g[1] in keep], len(keep), times[0] if times else None, times[-1] if times else None


def table(window, fallback, out, workflows, after=None, after_jobs=()):
    rows, errors = [], []
    for path in workflows:
        wf = Path(path).name
        _, wjobs = read_workflow(path)
        primary = read_window(window, wf)
        primary_traced = traced_runs(primary[1])
        read = {}  # a fallback is read only when a job needs it
        for key, j in wjobs.items():
            # A job whose shape changed in #743 never reads runs from before
            # the merges: only its own runs after them (#782 question 3).
            second = after if key in after_jobs else fallback
            for mode in (("normal", "traced") if j["marked"] else ("all",)):
                w, jobs = primary
                got = samples(jobs, key, mode, primary_traced)
                runs, first, last = w["runs"], w["first"], w["last"]
                if len(got) < MIN_SAMPLES and second is not None:
                    if second not in read:
                        _, sjobs = read_window(second, wf)
                        read[second] = (sjobs, traced_runs(sjobs))
                    sjobs, straced = read[second]
                    got, runs, first, last = own_runs(samples(sjobs, key, mode, straced))
                n = len(got)
                if n < MIN_SAMPLES:
                    errors.append(f"{wf} job {key} {mode} has {n} sample{'' if n == 1 else 's'},"
                                  f" fewer than {MIN_SAMPLES}")
                    continue
                legs = {}
                for leg, _, _, seconds in got:
                    legs.setdefault(leg, []).append(seconds)
                # The slowest leg's p95: one timeout covers every matrix leg.
                p95 = max(B.nearest_rank(v, 0.95) for v in legs.values())
                rows.append({"workflow": wf, "job": key, "mode": mode, "timeout": budget(p95), "p95_seconds": p95,
                             "samples": n, "runs": runs, "first": first, "last": last})
    for e in errors:
        print(f"budgets: {e}", file=sys.stderr)
    if errors:
        return 1
    write_table(out, rows)
    for r in rows:
        print(f"{r['workflow']} {r['job']} {r['mode']}: p95 {r['p95_seconds'] / 60:.1f} min over {r['samples']}"
              f" jobs in {r['runs']} runs -> {r['timeout']} min")
    return 0


def main(argv):
    p = argparse.ArgumentParser(prog="budgets.py", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--workflow", required=True)
    c.add_argument("--runs", type=int, default=RUNS)
    c.add_argument("--since")
    c.add_argument("--per-page", type=int, default=100)
    c.add_argument("--out", required=True)
    t = sub.add_parser("table")
    t.add_argument("window")
    t.add_argument("--fallback")
    t.add_argument("--after")
    t.add_argument("--after-jobs", nargs="+", default=[])
    t.add_argument("--out", default=str(TABLE))
    t.add_argument("--workflows", nargs="+", default=[str(w) for w in WORKFLOWS])
    for name in ("apply", "check"):
        s = sub.add_parser(name)
        s.add_argument("--table", default=str(TABLE))
        s.add_argument("workflows", nargs="*", default=[str(w) for w in WORKFLOWS])
    a = p.parse_args(argv)
    try:
        if a.cmd == "collect":
            if a.since and not B.TIME.fullmatch(a.since):
                p.error("--since must be YYYY-MM-DDTHH:MM:SSZ")
            if a.runs < 1 or a.per_page < 1:
                p.error("--runs and --per-page must be at least 1")
            collect(a.workflow, a.runs, a.since, a.out, a.per_page)
            return 0
        if a.cmd == "table":
            return table(a.window, a.fallback, a.out, a.workflows, a.after, a.after_jobs)
        return (apply if a.cmd == "apply" else check)(a.table, a.workflows)
    except Fail as e:
        print(f"budgets: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
