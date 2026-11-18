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
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import sys
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TABLE = HERE / "budgets.tsv"
WORKFLOWS = [ROOT / ".github/workflows/ci.yml", ROOT / ".github/workflows/privacy.yml"]
RUNS, FLOOR, MIN_SAMPLES = 150, 5, 5
COLUMNS = ["workflow", "job", "mode", "timeout", "p95_seconds", "samples", "runs", "first", "last", "source"]
# measured[:samples-file]: from the job's own runs; derived:<job>: from a twin with the same steps, for a job that has
# never run; unmeasured[:provenance]: authorized prior limit until enough runs (#782 question 4).
SOURCE = re.compile(r"(?:measured|unmeasured)(?::[^\t\n]+)?|derived:[A-Za-z0-9_-]+")
# Marked jobs execute three distinct modes. Planted takes precedence when both flags are true.
MARK = "if: needs.changes.outputs.trace == 'true' || needs.changes.outputs.planted == 'true'"
THREE = ("${{ needs.changes.outputs.planted == 'true' && %d || "
         "needs.changes.outputs.trace == 'true' && %d || %d }}")
THREE_RE = re.compile(r"\$\{\{ needs\.changes\.outputs\.planted == 'true' && (\d+) \|\| "
                      r"needs\.changes\.outputs\.trace == 'true' && (\d+) \|\| (\d+) \}\}")
MODES = ("planted", "traced", "normal")
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
    """A plain timeout or the planted, traced, normal expression; legacy mixed forms refuse."""
    if re.fullmatch(r"\d+", value):
        return ("all", int(value))
    m = THREE_RE.fullmatch(value)
    return ("modes", *map(int, m.groups())) if m else None


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
        if r["mode"] not in ("all", "normal", "traced", "planted"):
            raise Fail(f"{path} line {n}: mode {r['mode']!r} is not all, normal, traced or planted")
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
    """A marked job needs all three independent mode rows."""
    modes = {m: r for (w, j, m), r in rows.items() if (w, j) == (wf, key)}
    if not modes:
        return None
    if set(modes) == {"all"}:
        return ("all", modes["all"]["timeout"])
    if set(modes) == set(MODES):
        return ("modes", *(modes[m]["timeout"] for m in MODES))
    raise Fail(f"{wf} job {key}: its rows must be one all row, or normal, traced and planted rows")


def timeout_text(want):
    return str(want[1]) if want[0] == "all" else THREE % want[1:]


def is_unmeasured(row, rows):
    """An explicit unknown p95, including a planted row's same-mode export twin."""
    source = row["source"]
    if source == "unmeasured" or source.startswith("unmeasured:"):
        return True
    if row["mode"] == "planted" and source.startswith("derived:"):
        twin = rows.get((row["workflow"], source.split(":", 1)[1], "planted"))
        return twin is not None and (twin["source"] == "unmeasured" or twin["source"].startswith("unmeasured:"))
    return False


def planted_evidence(table, rows, r):
    """Validate a planted row against its offline, mode-bound duration observations."""
    source = r["source"]
    if source == "unmeasured" or source.startswith("unmeasured:"):
        if r["samples"] >= MIN_SAMPLES:
            raise Fail("planted evidence: five eligible samples must be measured")
        if r["p95_seconds"] != 0:
            raise Fail("planted evidence: an unmeasured row cannot claim a p95")
        if ":" in source:
            B.read_file(Path(table).parent / source.split(":", 1)[1])
        return
    if source.startswith("derived:"):
        twin = rows.get((r["workflow"], source.split(":", 1)[1], "planted"))
        if twin is None or twin["source"].startswith("derived:"):
            raise Fail("planted evidence: missing direct planted twin")
        if any(r[k] != twin[k] for k in COLUMNS if k not in ("job", "source")):
            raise Fail("planted evidence: derived row differs from its planted twin")
        return
    if not source.startswith("measured:"):
        raise Fail("planted evidence: a measured planted row needs its own sample provenance")
    path = Path(table).parent / source.split(":", 1)[1]
    data = B.as_list(B.strict_json(B.read_file(path), str(path)), str(path))
    got, seen = [], set()
    for sample in data:
        B.as_obj(sample, str(path))
        if (sample.get("workflow"), sample.get("job")) != (r["workflow"], r["job"]):
            continue
        if execution_mode(sample) != "planted":
            raise Fail("planted evidence: traced, normal or unknown sample attributed to planted")
        if (any(type(sample.get(k)) is not int or sample[k] < 1 for k in ("run", "attempt"))
                or not isinstance(sample.get("leg"), str)
                or not (sample["leg"] == r["job"] or sample["leg"].startswith(r["job"] + " ("))):
            raise Fail("planted evidence: invalid run, attempt or job identity")
        created = B.as_time(sample, "created_at", str(path))
        if not (r["first"] <= created <= r["last"]):
            raise Fail("planted evidence: sample outside the row's window")
        ident = (sample["run"], sample["attempt"], sample["leg"])
        if (ident in seen or sample.get("conclusion") not in COUNTED
                or sample.get("complete") is not True):
            raise Fail("planted evidence: duplicate or incomplete sample")
        seen.add(ident)
        seconds = sample.get("seconds")
        if type(seconds) is not int or seconds < 0:
            raise Fail("planted evidence: invalid duration")
        got.append(sample)
    if len({sample["run"] for sample in got}) > r["runs"]:
        raise Fail("planted evidence: more sample runs than the row records")
    if len(got) < MIN_SAMPLES or len(got) != r["samples"]:
        raise Fail("planted evidence: missing samples or fewer than five")
    legs = {}
    for sample in got:
        legs.setdefault(sample["leg"], []).append(sample["seconds"])
    p95 = max(B.nearest_rank(v, 0.95) for v in legs.values())
    if r["p95_seconds"] != p95:
        raise Fail("planted evidence: row p95 differs from its own samples")


def check(table, workflows):
    rows = read_table(table)
    errors = []
    for (wf, key, mode), r in sorted(rows.items()):
        if not is_unmeasured(r, rows) and r["timeout"] != budget(r["p95_seconds"]):
            errors.append(f"{wf} {key} {mode}: timeout {r['timeout']}, but 1.5x its p95 of {r['p95_seconds']} s"
                          f" is {budget(r['p95_seconds'])}")
        if mode == "planted":
            try:
                planted_evidence(table, rows, r)
            except Fail as e:
                errors.append(f"{wf} {key}: {e}")
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
            if j["marked"] and want[0] == "all":
                errors.append(f"{wf} job {key}: missing normal, traced and planted budgets")
                continue
            if j["timeout"] is None:
                errors.append(f"{wf} job {key} has no timeout-minutes")
                continue
            got = parse_timeout(j["timeout"][1])
            if got is None:
                errors.append(f"{wf} job {key}: timeout-minutes {j['timeout'][1]!r} is neither a number nor the"
                              " planted/traced/normal form")
            elif got[0] != want[0]:
                errors.append(f"{wf} job {key}: timeout-minutes has no matching planted/traced/normal budget")
            elif got[0] == "all" and got[1] != want[1]:
                errors.append(f"{wf} job {key}: timeout-minutes {got[1]}, its budget is {want[1]}")
            elif got[0] == "modes":
                for mode, g, w in zip(MODES, got[1:], want[1:]):
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

def collect_mode(base, run):
    """Read the persisted dispatcher flags, paired by plan hash and run/attempt identity."""
    rid, attempt = run["id"], run["attempt"]
    unknown = {"attempt": attempt, "source": "unknown", "reason": "no matching dispatch artifact"}
    listed = [a for a, _ in B.pages(f"{base}/runs/{rid}/artifacts?per_page=100", "artifacts", "artifacts")]
    artifacts = [a for a in listed if a.get("name") == f"ci-selection-{attempt}" and a.get("expired") is False]
    if len(artifacts) != 1:
        return unknown
    artifact = artifacts[0]
    result = subprocess.run(["gh", "api", f"{base}/artifacts/{artifact['id']}/zip"], capture_output=True)
    if result.returncode:
        return dict(unknown, reason="dispatch artifact download failed")
    try:
        with zipfile.ZipFile(io.BytesIO(result.stdout)) as archive:
            if any(archive.namelist().count(name) != 1 for name in ("ci-selection.json", "ci-dispatch.json")):
                return dict(unknown, reason="missing or duplicate dispatch artifact files")
            plan_bytes = archive.read("ci-selection.json")
            plan = B.as_obj(B.strict_json(plan_bytes.decode(), "selection artifact"), "selection artifact")
            dispatch = B.as_obj(B.strict_json(archive.read("ci-dispatch.json").decode(), "dispatch artifact"), "dispatch artifact")
            B.as_obj(plan.get("run"), "selection run")
        if (plan.get("schema") != "openwiz.ci-selection.v1" or plan.get("run", {}).get("id") != rid
                or plan["run"].get("attempt") != attempt
                or dispatch.get("plan_sha256") != hashlib.sha256(plan_bytes).hexdigest()
                or type(dispatch.get("trace")) is not bool or type(dispatch.get("planted")) is not bool):
            return dict(unknown, reason="dispatch artifact identity, hash or flags mismatch")
    except (Fail, KeyError, ValueError, UnicodeError, zipfile.BadZipFile):
        return dict(unknown, reason="unreadable dispatch artifact")
    return {"attempt": attempt, "trace": dispatch["trace"], "planted": dispatch["planted"],
            "source": artifact["archive_download_url"], "plan_sha256": dispatch["plan_sha256"]}


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
    lines, modes = [], {}
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
        if workflow == "ci.yml":
            modes[str(rid)] = collect_mode(base, run)
        # A rerun between the list and the jobs would mix attempts (bench.py, #383 R2).
        where = f"gh api {base}/runs/{rid}"
        again = B.as_obj(B.gh(f"{base}/runs/{rid}"), where)
        after = (B.as_int(again, "run_attempt", where), B.as_str(again, "status", where),
                 B.as_str(again, "conclusion", where, null=True))
        if after != (run["attempt"], "completed", run["conclusion"]):
            raise Fail(f"{where}: run {rid} changed while it was read; read again once its reruns have finished")
    d = Path(out) / workflow.removesuffix(".yml")
    d.mkdir(parents=True, exist_ok=True)
    if workflow == "ci.yml":
        B.write(d / "modes.json", json.dumps(modes, indent=2, sort_keys=True) + "\n")
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
    mode_file = d / "modes.json"
    modes = B.as_obj(B.strict_json(B.read_file(mode_file), str(mode_file)), str(mode_file)) if mode_file.exists() else {}
    for job in jobs:
        job["execution"] = B.as_obj(modes.get(str(job["run"]), {}), str(mode_file))
    return w, jobs


def execution_mode(evidence):
    if (type(evidence.get("trace")) is not bool or type(evidence.get("planted")) is not bool
            or not isinstance(evidence.get("source"), str) or not evidence["source"]):
        return None
    return "planted" if evidence["planted"] else "traced" if evidence["trace"] else "normal"


def run_modes(jobs, wjobs):
    """Actual dispatch flags, bound to the collected attempt; legacy ambiguous uploads stay unknown."""
    answers, runs = {}, set()
    for j in jobs:
        rid = j["run"]
        runs.add(rid)
        e = j.get("execution", {})
        mode = execution_mode(e) if type(e.get("attempt")) is int and e["attempt"] == j.get("run_attempt") else None
        j["mode_complete"] = j["conclusion"] == "success"
        for at, name in wjobs.get(j["name"].split(" (")[0], {}).get("marks", []):
            if at < len(j["steps"]) and j["steps"][at]["name"] == name and j["steps"][at]["conclusion"] in COUNTED:
                j["mode_complete"] = True
        if mode is None:
            # Both flags false is observable in a skipped combined step after clean steps.
            # A combined step that ran cannot tell traced from planted, even on a schedule.
            for at, name in wjobs.get(j["name"].split(" (")[0], {}).get("marks", []):
                if (at < len(j["steps"]) and j["steps"][at]["name"] == name
                        and j["steps"][at]["conclusion"] == "skipped"
                        and all(s["conclusion"] in ("success", "skipped") for s in j["steps"][:at])):
                    mode = "normal"
        if mode:
            answers.setdefault(rid, set()).add(mode)
    known = {r: next(iter(a)) for r, a in answers.items() if len(a) == 1}
    return known, runs - set(known)


def samples(jobs, key, mode, modes):
    """Eligible complete durations from this job and this execution mode only."""
    known, _ = modes
    out = []
    for j in jobs:
        if j["name"] != key and not j["name"].startswith(key + " ("):
            continue
        if j["conclusion"] not in COUNTED or B.never_ran(j):
            continue
        if mode != "all" and known.get(j["run"]) != mode:
            continue
        if mode == "planted" and not j.get("mode_complete"):
            continue
        out.append((j["name"], j["run"], j.get("run_created_at", j["created_at"]),
                    B.secs(j["completed_at"]) - B.secs(j["started_at"])))
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
    """Say how many runs left out of mode-specific jobs had a sample in one."""
    marked = {k for k, j in wjobs.items() if j["marked"]}
    hit = {j["run"] for j in jobs if j["run"] in unclear and j["name"].split(" (")[0] in marked
           and j["conclusion"] in COUNTED and not B.never_ran(j)}
    if hit:
        n = len(hit)
        print(f"budgets: {wf}: {n} run{'' if n == 1 else 's'} with no clear normal, traced or planted mode,"
              " left out of mode-specific jobs")


def table(window, fallback, out, workflows, after=None, after_jobs=(), derive=None, unmeasured=None):
    derive, unmeasured = derive or {}, unmeasured or {}
    rows, errors, evidence = [], [], []
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
            for mode in (("normal", "traced", "planted") if j["marked"] else ("all",)):
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
                    jobs = sjobs
                n = len(got)
                candidates = (f"{key}:{mode}", key)
                if mode == "planted":
                    candidates += (f"{twin}:{mode}", twin)
                unmeasured_key = next((candidate for candidate in candidates if candidate in unmeasured), None)
                if unmeasured_key in unmeasured and (mode != "planted" or n < MIN_SAMPLES):
                    rows.append({"workflow": wf, "job": key, "mode": mode, "timeout": unmeasured[unmeasured_key], "p95_seconds": 0,
                                 "samples": n, "runs": runs, "first": first, "last": last,
                                 "source": f"derived:{twin}" if mode == "planted" and twin != key else "unmeasured"})
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
                if mode == "planted" and twin == key:
                    selected = {(leg, rid) for leg, rid, _, _ in got}
                    for record in jobs:
                        if (record["name"], record["run"]) in selected:
                            evidence.append(dict(record["execution"], workflow=wf, job=key, leg=record["name"],
                                                 run=record["run"], conclusion=record["conclusion"], complete=record["mode_complete"],
                                                 created_at=record.get("run_created_at", record["created_at"]),
                                                 seconds=B.secs(record["completed_at"]) - B.secs(record["started_at"])))
                rows.append({"workflow": wf, "job": key, "mode": mode, "timeout": budget(p95), "p95_seconds": p95,
                             "samples": n, "runs": runs, "first": first, "last": last,
                             "source": ("measured:" + Path(out).with_suffix(".samples.json").name if mode == "planted" else "measured")
                             if twin == key else f"derived:{twin}"})
    for e in errors:
        print(f"budgets: {e}", file=sys.stderr)
    if errors:
        return 1
    if evidence:
        B.write(Path(out).with_suffix(".samples.json"), json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    write_table(out, rows)
    indexed = {(r["workflow"], r["job"], r["mode"]): r for r in rows}
    for r in rows:
        if is_unmeasured(r, indexed):
            print(f"{r['workflow']} {r['job']} {r['mode']}: p95 unknown, {r['samples']} eligible samples;"
                  f" retained unmeasured timeout {r['timeout']} min")
            continue
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
    t.add_argument("--unmeasured", nargs="+", action="extend", default=[], metavar="JOB=MINUTES")
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
