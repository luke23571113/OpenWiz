#!/usr/bin/env python3
"""CI3's loop every 3 days (#784): the check that finds the note's numbers, and its gate.

    ci3_weekly.py check [--now T] [--record FILE]   the loop's check: the note's finding on stdout, every run
    ci3_weekly.py due [--now T]                     the Cloudroom gate: one line on every third day, else nothing

T is a UTC time, YYYY-MM-DDTHH:MM:SSZ (default: now). `check` reads GitHub
only through the CI bench's reader (`gh api <path>`, GET): the CI3 measure
for the last 7 days (ci3.py), spec #780's comments for the last note, and the
month's Actions minutes (the organisation's billing usage, else this
repository's job times as an estimate, else unknown). A read that fails is
said in the finding, never dropped: every run is due for its note. `due`
reads no network: it counts Pacific days from loops/ci3-weekly.json's anchor.
A command line or a definition it can't read exits 2 with nothing on stdout.
Python 3 standard library only, and gh.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import bench  # noqa: E402
import ci3  # noqa: E402

from bench import Fail, as_int, as_list, as_obj, as_str, as_time, need, secs  # noqa: E402

SPEC = 780
RECORD = ROOT / "docs" / "ci3.md"
FLEET = ROOT / "docs" / "agents" / "fleet.md"
DEFINITION = ROOT / "loops" / "ci3-weekly.json"
ALERT_MINUTES = 50000
DAYS = 7
# The window ends on the hour, two hours before the read: longer than a job's
# timeout, so its heads have their results (ci3.v1, cohort rule 4).
SETTLE = 2 * 3600
MARKER = "openwiz.ci3-note.v1"
MARKED = re.compile(r"<!-- openwiz\.ci3-note\.v1 (\{[^\n]*?\}) -->")
NOTE_KEYS = {"measure", "until", "p50_minutes", "p95_minutes", "month", "actions_minutes", "minutes_source", "alert"}
WORKERS = 4


def utc(seconds):
    return bench.utc_text(seconds)


def shown(t):
    """2026-01-06T00:00:00Z as 2026-01-06 00:00."""
    return t[:10] + " " + t[11:16]


def num(v):
    return "none" if v is None else f"{v:.1f}"


def plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


# ---------------------------------------------------------------- reading


def number(obj, key, where, null=False):
    v = need(obj, key, where)
    if v is None and null:
        return v
    if type(v) not in (int, float) or v < 0:
        raise Fail(f"{where}: '{key}' is not a nonnegative number")
    return v


def read_before(path):
    """The BEFORE record: the JSON block under docs/ci3.md's "The BEFORE record" summary."""
    text = bench.read_file(path)
    at = text.find("<summary>The BEFORE record")
    block = re.compile(r"^```json\n(.*?)\n^```$", re.S | re.M).search(text, at) if at >= 0 else None
    if block is None:
        raise Fail(f"{path}: no BEFORE record block")
    rec = as_obj(bench.strict_json(block.group(1), f"{path} BEFORE"), f"{path} BEFORE")
    where = f"{path} BEFORE"
    if as_str(rec, "schema", where) != ci3.SCHEMA or as_str(rec, "label", where) != "BEFORE":
        raise Fail(f"{where}: not an {ci3.SCHEMA} BEFORE record")
    as_str(rec, "measure", where)
    result = as_obj(need(rec, "result", where), where)
    number(result, "p50_minutes", where, null=True), number(result, "p95_minutes", where, null=True)
    return rec


def record_authors():
    """The factory's record authors, as launch-fleet reads them from docs/agents/fleet.md (#641)."""
    spec = importlib.util.spec_from_file_location("launch_fleet_grants",
                                                  ROOT / "skills" / "launch-fleet" / "scripts" / "grants.py")
    grants = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(grants)
    try:
        return grants.record_authors(bench.read_file(FLEET))
    except ValueError as e:
        raise Fail(str(e))


def read_note(body, where):
    found = MARKED.findall(body)
    if len(found) != 1:
        raise Fail(f"{where}: {len(found)} note markers")
    note = as_obj(bench.strict_json(found[0], where), where)
    bench.exact(note, NOTE_KEYS, where)
    as_str(note, "measure", where), as_time(note, "until", where), as_str(note, "month", where)
    number(note, "p50_minutes", where, null=True), number(note, "p95_minutes", where, null=True)
    if note["actions_minutes"] is not None:
        as_int(note, "actions_minutes", where)
    if note["minutes_source"] not in (None, "billing", "estimate") or type(note["alert"]) is not bool:
        raise Fail(f"{where}: not a note marker")
    return note


def read_last_note(read, authors, spec=SPEC):
    """The newest comment on the spec, by a record author, that carries a note marker; or None."""
    notes, page = [], 1
    while True:
        path = f"repos/{{owner}}/{{repo}}/issues/{spec}/comments?per_page={bench.PAGE}&page={page}"
        got = as_list(read(path), f"gh api {path}")
        for c in got:
            where = f"gh api {path} comment"
            as_obj(c, where)
            user = need(c, "user", where)
            login = as_str(as_obj(user, where), "login", where) if user is not None else None
            body = as_str(c, "body", where, null=True) or ""
            if login is None or login.lower() not in authors or MARKER not in body:
                continue
            notes.append((secs(as_time(c, "created_at", where)), as_int(c, "id", where),
                          as_time(c, "created_at", where), read_note(body, f"{where} {c['id']}")))
        if len(got) < bench.PAGE:
            break
        page += 1
    if not notes:
        return None
    _, _, at, note = max(notes, key=lambda n: n[:2])
    return dict(note, posted_at=at)


def billing_minutes(read, year, month):
    """The organisation's Actions minutes this month, from GitHub's billing usage, rounded up."""
    path = f"organizations/{{owner}}/settings/billing/usage?year={year}&month={month}"
    where = f"gh api {path}"
    total = Decimal(0)
    prefix = f"{year:04d}-{month:02d}-"
    for item in as_list(need(as_obj(read(path), where), "usageItems", where), where):
        as_obj(item, where)
        if not as_time(item, "date", where).startswith(prefix):
            raise Fail(f"{where}: a usage item outside {prefix[:-1]}")
        if as_str(item, "product", where) == "actions" and as_str(item, "unitType", where) == "Minutes":
            total += Decimal(repr(number(item, "quantity", where)))
    return math.ceil(total)


def job_minutes(job, now, where):
    """One job's time on a runner, rounded up to a minute as GitHub bills it; a job still running counts to now."""
    as_obj(job, where)
    started, completed = as_time(job, "started_at", where, null=True), as_time(job, "completed_at", where, null=True)
    as_str(job, "runner_name", where, null=True), as_list(need(job, "steps", where), where)
    if started is None or bench.never_ran(job):
        return 0
    return math.ceil(max(0, secs(completed or now) - secs(started)) / 60)


def estimate_minutes(read, month_start, now, workers=1):
    """This repository's job times this month: every run created since the month began, every attempt's jobs."""
    ids = set()
    for run, where in bench.pages(f"repos/{{owner}}/{{repo}}/actions/runs?created={month_start}..{now}"
                                  f"&per_page={bench.PAGE}", "workflow_runs", "runs", read):
        as_obj(run, where)
        if secs(month_start) <= secs(as_time(run, "created_at", where)) < secs(now):
            ids.add(as_int(run, "id", where))

    def run_minutes(rid):
        jobs = {}
        for job, where in bench.pages(f"repos/{{owner}}/{{repo}}/actions/runs/{rid}/jobs?filter=all"
                                      f"&per_page={bench.PAGE}", "jobs", "jobs", read):
            jobs[as_int(as_obj(job, where), "id", where)] = job_minutes(job, now, f"{where} job")
        return sum(jobs.values())

    if workers == 1:
        return sum(run_minutes(r) for r in sorted(ids))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return sum(pool.map(run_minutes, sorted(ids)))


def read_minutes(read, now, workers=1):
    """(minutes, source, words): billing, else an estimate, else unknown; never a guess below."""
    year, month = int(now[:4]), int(now[5:7])
    try:
        return billing_minutes(read, year, month), "billing", "GitHub billing usage, the organisation"
    except Fail as e:
        no_billing = str(e)
    try:
        n = estimate_minutes(read, f"{now[:7]}-01T00:00:00Z", now, workers)
        return n, "estimate", f"this repository's job times, each rounded up to a minute; billing: {no_billing}"
    except Fail as e:
        return None, None, f"billing: {no_billing}; estimate: {e}"


def read_measure(read, since, until, now, workers=1):
    with tempfile.TemporaryDirectory(prefix="ci3-weekly-") as tmp:
        out = Path(tmp) / "window.json"
        ci3.collect(since, until, out, workers, read=read, now=now)
        return ci3.measure(ci3.read_window(out), label=f"AFTER {until[:10]}")


# ---------------------------------------------------------------- the finding


def delta(a, b):
    return f"{round(a - b, 1):+.1f}"


def against(name, before, rec, when=""):
    b50, b95 = before["p50_minutes"], before["p95_minutes"]
    r = rec["result"]
    parts = [f"{k} {delta(r[f'{k}_minutes'], b)} min" for k, b in (("p50", b50), ("p95", b95))
             if r[f"{k}_minutes"] is not None and b is not None]
    return f"Against {name} ({when}{num(b50)} / {num(b95)} min): {', '.join(parts) or 'not compared'}."


def regression(before, rec):
    worse = [f"{k} {num(rec['result'][f'{k}_minutes'])} min against {num(before[f'{k}_minutes'])}"
             for k in ("p50", "p95")
             if None not in (rec["result"][f"{k}_minutes"], before[f"{k}_minutes"])
             and rec["result"][f"{k}_minutes"] > before[f"{k}_minutes"]]
    return f"REGRESSION: slower than BEFORE: {', '.join(worse)}." if worse else None


def biggest(path):
    shares = {k: path[k]["share"] for k in ("waiting", "setup", "running") if path[k]["share"] is not None}
    if not shares:
        return "unknown"
    top = max(shares.values())
    return " and ".join(k for k, v in shares.items() if v == top)


def measure_lines(rec):
    r = rec["result"]
    lines = [f"Time to a PR's result: p50 {num(r['p50_minutes'])} min, p95 {num(r['p95_minutes'])} min"
             f" ({r['timed']} timed of {rec['heads']} PR heads in {plural(rec['prs'], 'PR')};"
             f" {len(rec['missing'])} missing)."]
    if rec["missing"]:
        shown_ = [f"#{m['pr']} {(m['head'] or 'no head')[:7]} ({m['reason']})" for m in rec["missing"][:10]]
        more = f"; and {len(rec['missing']) - 10} more" if len(rec["missing"]) > 10 else ""
        lines.append(f"Missing: {'; '.join(shown_)}{more}.")
    by = r["by_outcome"]
    outcome = ", ".join(f"{k} {num(by[k]['p50_minutes'])} / {num(by[k]['p95_minutes'])} min"
                        if by[k]["p50_minutes"] is not None else f"{k} none"
                        for k in ("success", "failure", "cancelled"))
    lines.append(f"By outcome: {outcome}; {r['with_reruns']} with reruns.")
    return lines


def path_lines(rec):
    path, q = rec["critical_path"], rec["merge_queue"]
    split = ", ".join(f"{k} {'none' if path[k]['share'] is None else format(path[k]['share'] * 100, '.1f') + '%'}"
                      for k in ("waiting", "setup", "running", "unclassified"))
    return [f"Critical path: {split}; biggest: {biggest(path)}.",
            f"Merge queue: p50 {num(q['p50_minutes'])}, p95 {num(q['p95_minutes'])}"
            f" ({q['groups']} groups, {q['missing']} missing).",
            f"Runner minutes in the window (ci and privacy, PR heads and merge queue):"
            f" {rec['runner_minutes']['total']:,.1f}."]


def check(now, read=None, record=RECORD, authors=None, workers=1):
    """The finding: the note's numbers, in the order the note gives them. Every failed read is said."""
    read = read or bench.gh
    until = utc((secs(now) // 3600) * 3600 - SETTLE)
    since = utc(secs(until) - DAYS * 86400)
    month = now[:7]

    def attempt(fn):
        try:
            return fn(), None
        except Fail as e:
            return None, str(e)

    rec, no_rec = attempt(lambda: read_measure(read, since, until, now, workers))
    before, no_before = attempt(lambda: read_before(record))
    note, no_note = attempt(lambda: read_last_note(read, authors if authors is not None else record_authors()))
    minutes, source, words = read_minutes(read, now, workers)
    alert = minutes is not None and minutes > ALERT_MINUTES

    lines = []
    if alert:
        how = "GitHub billing usage, the organisation" if source == "billing" else \
            "an estimate from this repository's job times"
        lines.append(f"ALERT: GitHub Actions minutes in {month} passed {ALERT_MINUTES:,}: {minutes:,} so far ({how}).")
    lines.append(f"CI3 note due: {shown(since)} to {shown(until)} UTC, measured as {ci3.VERSION}.")
    if rec is None:
        # No number to compare: say only which other reads failed.
        lines.append(f"Time to a PR's result: unknown ({no_rec}).")
        lines += [f"Against BEFORE: unknown ({no_before})."] if no_before else []
        lines += [f"Against the last note: unknown ({no_note})."] if no_note else []
    else:
        # Points of different versions are never compared (ci3.v1, Versions).
        comparable = before is not None and before["measure"] == rec["measure"]
        worse = regression(before["result"], rec) if comparable else None
        lines += [worse] if worse else []
        lines += measure_lines(rec)
        if before is None:
            lines.append(f"Against BEFORE: unknown ({no_before}).")
        elif not comparable:
            lines.append(f"Against BEFORE: not compared (BEFORE is {before['measure']}, this is {rec['measure']}).")
        else:
            lines.append(against("BEFORE", before["result"], rec))
        if no_note:
            lines.append(f"Against the last note: unknown ({no_note}).")
        elif note is None:
            lines.append("Against the last note: none yet.")
        elif note["measure"] != rec["measure"]:
            lines.append(f"Against the last note: not compared (it is {note['measure']}, this is {rec['measure']}).")
        else:
            lines.append(against("the last note", note, rec, f"until {shown(note['until'])} UTC, "))
        lines += path_lines(rec)
    if minutes is None:
        lines.append(f"Actions minutes in {month} so far: unknown ({words}).")
    elif source == "billing":
        lines.append(f"Actions minutes in {month} so far: {minutes:,} ({words}).")
    else:
        lines.append(f"Actions minutes in {month} so far: {minutes:,}, an estimate ({words}).")
    marker = {"measure": ci3.VERSION, "until": until, "month": month, "actions_minutes": minutes,
              "minutes_source": source, "alert": alert,
              "p50_minutes": rec["result"]["p50_minutes"] if rec else None,
              "p95_minutes": rec["result"]["p95_minutes"] if rec else None}
    lines.append(f"<!-- {MARKER} {json.dumps(marker, sort_keys=True)} -->")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- the gate


def due(now, definition=DEFINITION):
    """Every third day from the anchor's date. Run at 09:00 Pacific, the UTC date is the Pacific date
    (16:00 or 17:00 UTC), so whole dates, not milliseconds, keep the day through daylight saving."""
    d = as_obj(bench.strict_json(bench.read_file(definition), str(definition)), str(definition))
    wake = as_obj(need(d, "wake", str(definition)), str(definition))
    every, anchor = as_int(wake, "every_ms", str(definition)), as_int(wake, "anchor_ms", str(definition))
    if every % 86400000:
        raise Fail(f"{definition}: its interval is not whole days")
    days = (secs(now) // 86400) - (anchor // 1000 // 86400)
    return days >= 0 and days % (every // 86400000) == 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="ci3_weekly.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--now")
    c.add_argument("--record", default=str(RECORD))
    g = sub.add_parser("due")
    g.add_argument("--now")
    g.add_argument("--definition", default=str(DEFINITION))
    args = p.parse_args(argv)
    now = args.now or utc(time.time())
    if not bench.TIME.fullmatch(now):
        p.error(f"not a UTC time: {now}")
    try:
        if args.cmd == "check":
            sys.stdout.write(check(now, record=args.record, workers=WORKERS))
        elif due(now, args.definition):
            print("CI3 note due: run `python3 -I tools/ci-bench/ci3_weekly.py check`.")
    except Fail as e:
        # 2, not 1: Cloudroom skips a gate that exits 1 with no output silently,
        # and counts 2 as a failure (three in a row pause the loop).
        print(f"ci3_weekly: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
