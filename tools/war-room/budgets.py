#!/usr/bin/env python3
"""CI3 C1 (#782): time budgets that fail, read from real runs.

    budgets.py collect --workflow W [--runs 150] [--since T] --out DIR   read W's last completed runs (gh api, GET only)
    budgets.py table DIR [--fallback DIR] [--after DIR --after-jobs JOB...] [--derive JOB=TWIN...]
                     [--unmeasured JOB=MINUTES...] [--out budgets.tsv]
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
COLUMNS = ["workflow", "job", "mode", "timeout", "p95_seconds", "samples", "runs", "first", "last", "source"]
# measured: from the job's own runs; derived:<job>: from a twin with the same steps, for a job that has
# never run; unmeasured: today's timeout kept until the job has enough runs (#782 question 4).
SOURCE = re.compile(r"measured|unmeasured|derived:[A-Za-z0-9_-]+")
# A job that runs trace.py or planted.py's records in traced and planted runs
# carries this step; its timeout then has a traced budget and a normal one.
MARK = "if: needs.changes.outputs.trace == 'true' || needs.changes.outputs.planted == 'true'"
TRACED = ("${{ (needs.changes.outputs.trace == 'true' || needs.changes.outputs.planted == 'true')"
          " && %d || %d }}")
TRACED_RE = re.compile(r"\$\{\{ \(needs\.changes\.outputs\.trace == 'true' \|\| needs\.changes\.outputs\.planted"
                       r" == 'true'\) && (\d+) \|\| (\d+) \}\}")
COUNTED = {"success", "failure"}


sys.dont_write_bytecode = True


def bench():
    spec = importlib.util.spec_from_file_location("ci_bench", HERE / "bench_measure.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


B = bench()
Fail = B.Fail


def budget(p95_seconds):
    """1.5 x p95, rounded up to a whole minute, at least FLOOR: ceil(3s / 120)."""
    return max(FLOOR, -(-3 * p95_seconds // 120))


# ---------------------------------------------------------------- workflows

def step_name(entry):
    """A step's name as the jobs API shows it: its name, else Run <uses>, else Run <run>."""
    fields = {}
    for line in entry:
        m = re.match(r"^      (?:- |  )(name|uses|run):\s*(.*?)\s*$", line)
        if m and m[1] not in fields:
            fields[m[1]] = re.sub(r"\s+#.*$", "", m[2]).strip("\"'")
    if "name" in fields:
        return fields["name"]
    if "uses" in fields:
        return "Run " + fields["uses"]
    return "Run " + fields.get("run", "")


def read_workflow(path):
    """Each job's key, its timeout-minutes line (index, value), whether it carries MARK, and
    its MARK steps as (index in the jobs API's step list, API name): "Set up job" comes first."""
    name = Path(path).name
    lines = B.read_file(path).splitlines(keepends=True)
    jobs, key, inside, steps, entries = {}, None, False, False, []

    def close():
        if key is not None:
            jobs[key]["marks"] = [(i + 1, step_name(e)) for i, e in enumerate(entries)
                                  if any(x.strip() == MARK for x in e)]

    for i, line in enumerate(lines):
        if re.match(r"^jobs:\s*$", line):
            inside = True
            continue
        if not inside:
            continue
        if re.match(r"^\S", line):
            inside = False
            continue
        if re.match(r"^  \S", line) and not line.startswith("  #"):
            # A job key, bare or quoted (R2); anything else at this depth is refused.
            m = re.match(r"^  ([\"']?)([A-Za-z0-9_-]+)\1:\s*(#.*)?$", line)
            if not m:
                raise Fail(f"{name} line {i + 1}: a job declaration budgets.py can't read")
            close()
            key, steps, entries = m[2], False, []
            if key in jobs:
                raise Fail(f"{name} line {i + 1}: job {key} is declared twice")
            jobs[key] = {"timeout": None, "marked": False, "marks": []}
            continue
        if key is None:
            continue
        if re.match(r"^    [^\s#]", line):
            steps = bool(re.match(r"^    steps:\s*(#.*)?$", line))
        elif steps and line.startswith("      - "):
            entries.append([line])
        elif steps and entries:
            entries[-1].append(line)
        m = re.match(r"^    timeout-minutes:\s*(.*?)\s*(#.*)?$", line)
        if m:
            if jobs[key]["timeout"] is not None:
                raise Fail(f"{name} job {key} has two timeout-minutes lines")
            jobs[key]["timeout"] = (i, m[1])
        elif line.strip() == MARK:
            jobs[key]["marked"] = True
    close()
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
        if not SOURCE.fullmatch(r["source"]):
            raise Fail(f"{path} line {n}: source {r['source']!r} is not measured, derived:<job> or unmeasured")
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
        if r["source"] != "unmeasured" and r["timeout"] != budget(r["p95_seconds"]):
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


def run_modes(jobs, wjobs):
    """(traced runs, unclear runs), from the workflow's own trace steps (MARK).

    Every MARK step tests the same trace/planted flags. One that ran (success
    or failure) makes its run traced. One skipped after only successful or
    skipped steps makes it normal. One skipped after a failure, or a step list
    that doesn't match the workflow, says nothing. A scheduled (nightly) run
    is traced. A run with no clear answer, or with both, is unclear, and is left
    out of two-mode jobs rather than guessed (R1)."""
    yes, no, runs = set(), set(), set()
    for j in jobs:
        runs.add(j["run"])
        if j["event"] == "schedule":
            yes.add(j["run"])
        steps = j["steps"]
        for at, name in wjobs.get(j["name"].split(" (")[0], {}).get("marks", []):
            if at >= len(steps) or steps[at]["name"] != name:
                continue
            if steps[at]["conclusion"] in COUNTED:
                yes.add(j["run"])
            elif steps[at]["conclusion"] == "skipped" and all(x["conclusion"] in ("success", "skipped")
                                                              for x in steps[:at]):
                no.add(j["run"])
    scheduled = {j["run"] for j in jobs if j["event"] == "schedule"}
    unclear = (runs - yes - no) | ((yes & no) - scheduled)
    return yes - unclear, unclear


def samples(jobs, key, mode, modes):
    """(leg, run, run created, running seconds) for each job named KEY or KEY (matrix values) that ran to
    success or failure; for a two-mode job, only the runs whose mode (run_modes) is MODE."""
    traced, unclear = modes
    out = []
    for j in jobs:
        if j["name"] != key and not j["name"].startswith(key + " ("):
            continue
        if j["conclusion"] not in COUNTED or B.never_ran(j):
            continue
        if mode != "all" and (j["run"] in unclear or (j["run"] in traced) != (mode == "traced")):
            continue
        out.append((j["name"], j["run"], j.get("run_created_at", j["created_at"]), B.secs(j["completed_at"]) - B.secs(j["started_at"])))
    return out


def own_runs(got):
    """Only the job's own last RUNS runs, and the runs, first and last that describe them."""
    created = {run: at for _, run, at, _ in got}
    keep = set(sorted(created, key=lambda r: (created[r], r))[-RUNS:])
    times = sorted(created[r] for r in keep)
    return [g for g in got if g[1] in keep], len(keep), times[0] if times else None, times[-1] if times else None


def current_shape(jobs, keys):
    """Jobs of the runs that ran today's workflow: every job key it defines, and no other.

    GitHub lists every job of a run, skipped ones too, so a run created after
    the merges that still ran the old workflow (no launch-fleet job, an
    unsharded release) lacks a key (#782: two such runs)."""
    have = {}
    for j in jobs:
        have.setdefault(j["run"], set()).add(j["name"].split(" (")[0])
    keep = {run for run, k in have.items() if k == set(keys)}
    return [j for j in jobs if j["run"] in keep], keep


def note(wf, jobs, wjobs, unclear):
    """Say how many runs left out of two-mode jobs had a sample in one."""
    marked = {k for k, j in wjobs.items() if j["marked"]}
    hit = {j["run"] for j in jobs if j["run"] in unclear and j["name"].split(" (")[0] in marked
           and j["conclusion"] in COUNTED and not B.never_ran(j)}
    if hit:
        n = len(hit)
        print(f"budgets: {wf}: {n} run{'' if n == 1 else 's'} with no clear traced or normal mode,"
              " left out of two-mode jobs")


def table(window, fallback, out, workflows, after=None, after_jobs=(), derive=None, unmeasured=None):
    derive, unmeasured = derive or {}, unmeasured or {}
    rows, errors = [], []
    for path in workflows:
        wf = Path(path).name
        _, wjobs = read_workflow(path)
        primary = read_window(window, wf)
        primary_traced = run_modes(primary[1], wjobs)
        note(wf, primary[1], wjobs, primary_traced[1])
        read = {}  # a fallback is read only when a job needs it
        for key, j in wjobs.items():
            # A job whose shape changed in #743 never reads runs from before
            # the merges: only its own runs after them (#782 question 3).
            # A job that has never run reads its twin's runs (derive).
            twin = derive.get(key, key)
            second = after if twin in after_jobs else fallback
            for mode in (("normal", "traced") if j["marked"] else ("all",)):
                w, jobs = primary
                runs, first, last = w["runs"], w["first"], w["last"]
                if twin in after_jobs:
                    jobs, kept = current_shape(jobs, wjobs)
                    created = sorted({j["run_created_at"] for j in jobs})
                    runs, first, last = len(kept), created[0] if created else None, created[-1] if created else None
                got = samples(jobs, twin, mode, primary_traced)
                if len(got) < MIN_SAMPLES and second is not None:
                    if second not in read:
                        _, sjobs = read_window(second, wf)
                        read[second] = (sjobs, run_modes(sjobs, wjobs))
                        note(wf, sjobs, wjobs, read[second][1][1])
                    sjobs, straced = read[second]
                    if twin in after_jobs:
                        sjobs = current_shape(sjobs, wjobs)[0]
                    got, runs, first, last = own_runs(samples(sjobs, twin, mode, straced))
                n = len(got)
                if key in unmeasured:
                    rows.append({"workflow": wf, "job": key, "mode": mode, "timeout": unmeasured[key], "p95_seconds": 0,
                                 "samples": n, "runs": runs, "first": first, "last": last, "source": "unmeasured"})
                    continue
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
                             "samples": n, "runs": runs, "first": first, "last": last,
                             "source": "measured" if twin == key else f"derived:{twin}"})
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
    t.add_argument("--derive", nargs="+", default=[], metavar="JOB=TWIN")
    t.add_argument("--unmeasured", nargs="+", default=[], metavar="JOB=MINUTES")
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
            pairs = {}
            for name, given in (("--derive", a.derive), ("--unmeasured", a.unmeasured)):
                pairs[name] = {}
                for item in given:
                    k, sep, v = item.partition("=")
                    if not sep or not k or not v or (name == "--unmeasured" and not re.fullmatch(r"[1-9]\d*", v)):
                        p.error(f"{name} takes JOB={'TWIN' if name == '--derive' else 'MINUTES'}, not {item!r}")
                    pairs[name][k] = int(v) if name == "--unmeasured" else v
            return table(a.window, a.fallback, a.out, a.workflows, a.after, a.after_jobs,
                         pairs["--derive"], pairs["--unmeasured"])
        return (apply if a.cmd == "apply" else check)(a.table, a.workflows)
    except Fail as e:
        print(f"budgets: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
