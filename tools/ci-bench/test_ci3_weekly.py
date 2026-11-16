#!/usr/bin/env python3
"""CI3's loop every 3 days (#784): its check on synthetic weeks, its gate and its definition.

Every expected value is worked out by hand in fixtures/ci3-weekly/README.md or
written here as a literal, never by ci3_weekly.py. Each test names the bug it
catches.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import ci3_weekly  # noqa: E402

FIX = HERE / "fixtures" / "ci3-weekly"
RECORD = FIX / "record.md"
NOW = "2026-01-06T02:30:00Z"
AUTHORS = frozenset({"synthetic-owner"})
DEFINITION = ROOT / "loops" / "ci3-weekly.json"
SCHEMA = ROOT / "contracts" / "loops.v1.schema.json"
B = "repos/{owner}/{repo}"
BILLING = "organizations/{owner}/settings/billing/usage?year=2026&month=1"
FAIL = {"$fail": "gh api failed (exit 1): HTTP 403"}

NORMAL = [
    "CI3 note due: 2025-12-30 00:00 to 2026-01-06 00:00 UTC, measured as ci3.v1.",
    "Time to a PR's result: p50 15.5 min, p95 42.0 min (2 timed of 2 PR heads in 1 PR; 0 missing).",
    "By outcome: success 15.5 / 42.0 min, failure none, cancelled none; 1 with reruns.",
    "Against BEFORE (20.0 / 45.0 min): p50 -4.5 min, p95 -3.0 min.",
    "Against the last note (until 2026-01-03 00:00 UTC, 14.0 / 44.0 min): p50 +1.5 min, p95 -2.0 min.",
    "Critical path: waiting 95.7%, setup 4.3%, running 0.0%, unclassified 0.0%; biggest: waiting.",
    "Merge queue: p50 none, p95 none (0 groups, 0 missing).",
    "Runner minutes in the window (ci and privacy, PR heads and merge queue): 8.5.",
    "Actions minutes in 2026-01 so far: 35,001 (GitHub billing usage, the organisation).",
    '<!-- openwiz.ci3-note.v1 {"actions_minutes": 35001, "alert": false, "measure": "ci3.v1",'
    ' "minutes_source": "billing", "month": "2026-01", "p50_minutes": 15.5, "p95_minutes": 42.0,'
    ' "until": "2026-01-06T00:00:00Z"} -->',
]


class FakeGitHub:
    """Answers by the longest matching path prefix; `$fail` is a failed read; any other path fails the test."""

    def __init__(self, answers):
        self.answers, self.asked = answers, []

    def __call__(self, path):
        self.asked.append(path)
        for prefix in sorted(self.answers, key=len, reverse=True):
            if path.startswith(prefix):
                answer = self.answers[prefix]
                if isinstance(answer, dict) and "$fail" in answer:
                    raise ci3_weekly.Fail(answer["$fail"])
                return copy.deepcopy(answer)
        raise AssertionError(f"unexpected read: {path}")


def github(**changes):
    answers = json.loads((FIX / "github.json").read_text())
    answers.update(changes)
    return FakeGitHub(answers)


TMP = tempfile.TemporaryDirectory(prefix="test-ci3-weekly-")  # removed at exit


def record(p50, p95):
    """A copy of the synthetic record with another BEFORE, in this run's own folder."""
    fd, path = tempfile.mkstemp(suffix=".md", dir=TMP.name)
    with os.fdopen(fd, "w") as f:
        f.write(RECORD.read_text().replace('"p50_minutes": 20.0', f'"p50_minutes": {p50}')
                .replace('"p95_minutes": 45.0', f'"p95_minutes": {p95}'))
    return path


def check(gh=None, rec=RECORD):
    return ci3_weekly.check(NOW, read=gh or github(), record=rec, authors=AUTHORS).splitlines()


def billing(*quantities):
    return {"usageItems": [{"date": "2026-01-02T00:00:00Z", "product": "actions", "sku": "Actions Linux",
                            "quantity": q, "unitType": "Minutes"} for q in quantities]}


def marker(lines):
    line = lines[-1]
    return json.loads(line[len("<!-- openwiz.ci3-note.v1 "):-len(" -->")])


class Check(unittest.TestCase):
    def test_a_normal_run_prints_the_whole_note(self):
        # Bug: a normal run prints nothing (the loop goes quiet), compares with a
        # spoofed note from someone who isn't a record author, or drops a number
        # the note needs (BEFORE, the last note, the bucket, the minutes).
        self.assertEqual(check(), NORMAL)

    def test_slower_than_before_is_flagged(self):
        # Bug: only p50 is compared, or a faster result is flagged.
        both = check(rec=record(10.0, 30.0))
        self.assertEqual(both[1], "REGRESSION: slower than BEFORE: p50 15.5 min against 10.0,"
                                  " p95 42.0 min against 30.0.")
        self.assertEqual(both[0], NORMAL[0])
        p95 = check(rec=record(20.0, 40.0))
        self.assertEqual(p95[1], "REGRESSION: slower than BEFORE: p95 42.0 min against 40.0.")
        self.assertEqual(len(p95), len(NORMAL) + 1)
        self.assertNotIn("REGRESSION", "\n".join(check(rec=record(15.5, 42.0))))

    def test_points_of_another_measure_version_are_never_compared(self):
        # Bug: a note or BEFORE of another ci3 version is compared, so a changed
        # definition passes for a faster result (ci3.v1, Versions).
        gh = github()
        for c in gh.answers[f"{B}/issues/780/comments?"]:
            c["body"] = c["body"].replace('"measure": "ci3.v1"', '"measure": "ci3.v2"')
        rec = record(10.0, 30.0)
        Path(rec).write_text(Path(rec).read_text().replace('"measure": "ci3.v1"', '"measure": "ci3.v2"'))
        lines = check(gh, rec)
        self.assertEqual(lines[3:5], ["Against BEFORE: not compared (BEFORE is ci3.v2, this is ci3.v1).",
                                      "Against the last note: not compared (it is ci3.v2, this is ci3.v1)."])
        self.assertNotIn("REGRESSION", "\n".join(lines))

    def test_over_50000_minutes_leads_with_the_alert(self):
        # Bug: the alert is missing, buried below the numbers, raised at exactly
        # 50,000, or rounds the minutes down.
        lines = check(github(**{BILLING: billing(50000.5)}))
        self.assertEqual(lines[0], "ALERT: GitHub Actions minutes in 2026-01 passed 50,000: 50,001 so far"
                                   " (GitHub billing usage, the organisation).")
        self.assertEqual(lines[1:-2], NORMAL[:-2])
        self.assertEqual((marker(lines)["alert"], marker(lines)["actions_minutes"]), (True, 50001))
        at = check(github(**{BILLING: billing(30000, 20000)}))
        self.assertFalse(at[0].startswith("ALERT"))
        self.assertEqual(at[-2], "Actions minutes in 2026-01 so far: 50,000 (GitHub billing usage, the organisation).")

    def test_unreadable_minutes_say_unknown_never_under(self):
        # Bug: a failed or malformed billing read counts as 0 minutes (no alert,
        # a low number), or stops the note.
        bad = billing(10)
        bad["usageItems"][0]["quantity"] = "10"
        for answer in (FAIL, bad, {"usage": []}):
            lines = check(github(**{BILLING: answer}))
            self.assertTrue(lines[-2].startswith("Actions minutes in 2026-01 so far: unknown (billing: "), lines[-2])
            self.assertIn("; estimate: ", lines[-2])
            self.assertFalse(any(x.startswith("ALERT") for x in lines))
            self.assertEqual((marker(lines)["actions_minutes"], marker(lines)["minutes_source"]), (None, None))
            self.assertEqual(lines[:-2], NORMAL[:-2])

    def test_unreadable_billing_falls_back_to_a_marked_estimate(self):
        # Bug: the estimate passes for billing, counts a job twice, charges a job
        # that never got a runner, rounds down, or leaves out a job still running.
        def job(i, started, completed, runner="r"):
            return {"id": i, "name": "j", "conclusion": None if completed is None else "success",
                    "created_at": "2026-01-05T00:00:00Z", "started_at": started, "completed_at": completed,
                    "runner_name": runner, "run_attempt": 1, "steps": []}
        runs = {"total_count": 2, "workflow_runs": [{"id": 701, "created_at": "2026-01-05T00:00:00Z"},
                                                    {"id": 702, "created_at": "2026-01-06T01:00:00Z"}]}
        a = job(1, "2026-01-05T00:00:00Z", "2026-01-05T00:01:01Z")    # 61 s: 2 minutes
        never = job(2, None, None, runner=None)                         # no runner: 0
        c = job(3, "2026-01-06T01:00:00Z", "2026-01-06T01:00:30Z")      # 30 s: 1 minute
        running = job(4, "2026-01-06T02:00:00Z", None)                  # running at 02:30: 30 minutes
        gh = github(**{BILLING: FAIL, f"{B}/actions/runs?created=": runs,
                       f"{B}/actions/runs/701/jobs": {"total_count": 3, "jobs": [a, never, a]},
                       f"{B}/actions/runs/702/jobs": {"total_count": 2, "jobs": [c, running]}})
        lines = check(gh)
        self.assertEqual(lines[-2], "Actions minutes in 2026-01 so far: 33, an estimate (this repository's job"
                                    " times, each rounded up to a minute; billing: gh api failed (exit 1): HTTP 403).")
        self.assertEqual((marker(lines)["actions_minutes"], marker(lines)["minutes_source"]), (33, "estimate"))
        # Runs created up to 30 days before the month can still run in it (R2).
        self.assertIn(f"{B}/actions/runs?created=2025-12-02T00:00:00Z..2026-01-06T02:30:00Z&per_page=100&page=1",
                      gh.asked)

    def test_the_estimate_counts_execution_in_the_month_not_creation(self):
        # Bug (R2): runs are picked by creation date, so a run created on the
        # last day of January that runs in February (queued, or a later
        # attempt) is left out, and February's estimate is low; or a run's
        # January execution is charged to February. GitHub reruns a run up to
        # 30 days after it started, so runs created from 30 days before the
        # month are read, and only each job's time inside the month counts.
        now = "2026-02-02T17:00:00Z"
        def job(i, started, completed):
            return {"id": i, "name": "j", "conclusion": "success", "created_at": started, "started_at": started,
                    "completed_at": completed, "runner_name": "r", "run_attempt": 1, "steps": []}
        runs = {"total_count": 3, "workflow_runs": [
            {"id": 700, "created_at": "2026-01-31T23:59:00Z"},
            {"id": 701, "created_at": "2026-01-03T00:00:00Z"},
            {"id": 702, "created_at": "2026-01-31T23:40:00Z"}]}
        gh = FakeGitHub({
            "organizations/{owner}/settings/billing/usage?year=2026&month=2": FAIL,
            f"{B}/actions/runs?created=": runs,
            # Queued at 23:59, ran 00:00 to 01:24 in February: 84 minutes.
            f"{B}/actions/runs/700/jobs": {"total_count": 1, "jobs": [
                job(1, "2026-02-01T00:00:00Z", "2026-02-01T01:24:00Z")]},
            # Its first attempt ran in January (none of it counts); its rerun 29 days later, 5 minutes.
            f"{B}/actions/runs/701/jobs": {"total_count": 2, "jobs": [
                job(2, "2026-01-03T00:00:00Z", "2026-01-03T00:30:00Z"),
                dict(job(3, "2026-02-01T12:00:00Z", "2026-02-01T12:05:00Z"), run_attempt=2)]},
            # 23:50 to 00:10: only the 10 minutes after midnight are February's.
            f"{B}/actions/runs/702/jobs": {"total_count": 1, "jobs": [
                job(4, "2026-01-31T23:50:00Z", "2026-02-01T00:10:00Z")]},
        })
        minutes, source, _ = ci3_weekly.read_minutes(gh, now)
        self.assertEqual((minutes, source), (99, "estimate"))
        self.assertIn(f"{B}/actions/runs?created=2026-01-02T00:00:00Z..{now}&per_page=100&page=1", gh.asked)

    def test_a_failed_read_still_prints_the_note(self):
        # Bug: one failed read (a fork PR in the window, the comments) silences
        # the run, though every run is due for its note.
        fork = github()
        fork.answers[f"{B}/pulls?"][0]["head"]["repo"]["full_name"] = "contributor/fork"
        fork.answers[f"{B}/issues/780/comments?"] = FAIL
        lines = check(fork)
        self.assertEqual(lines[0], NORMAL[0])
        self.assertTrue(lines[1].startswith("Time to a PR's result: unknown (PR #9 is from a fork"), lines[1])
        self.assertTrue(lines[2].startswith("Against the last note: unknown (gh api failed"), lines[2])
        self.assertEqual(lines[3:], [NORMAL[8], '<!-- openwiz.ci3-note.v1 {"actions_minutes": 35001, "alert": false,'
                                     ' "measure": "ci3.v1", "minutes_source": "billing", "month": "2026-01",'
                                     ' "p50_minutes": null,'
                                     ' "p95_minutes": null, "until": "2026-01-06T00:00:00Z"} -->'])

    def test_the_real_before_record_reads(self):
        # Bug: docs/ci3.md's BEFORE block changes form and every note compares
        # with nothing. Its numbers, 22.4 and 50.9, are the published record's.
        before = ci3_weekly.read_before(ROOT / "docs" / "ci3.md")
        self.assertEqual((before["result"]["p50_minutes"], before["result"]["p95_minutes"]), (22.4, 50.9))

    def test_only_get_reads(self):
        # Bug: the check writes to GitHub, or reads outside `gh api` GET paths.
        gh = github()
        check(gh)
        self.assertTrue(all(p.startswith((B + "/", "organizations/{owner}/")) for p in gh.asked), gh.asked)

    def test_the_cli_prints_the_note_when_gh_fails(self):
        # Bug: the loop's command exits nonzero or prints nothing when GitHub
        # can't be read, so no agent wakes and Jake hears nothing.
        with tempfile.TemporaryDirectory() as tmp:
            gh = Path(tmp) / "gh"
            gh.write_text("#!/bin/sh\necho 'synthetic: not logged in' >&2\nexit 1\n")
            gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
            env = dict(os.environ, PATH=f"{tmp}{os.pathsep}{os.environ['PATH']}")
            run = subprocess.run([sys.executable, "-I", str(HERE / "ci3_weekly.py"), "check", "--now", NOW,
                                  "--record", str(RECORD)], capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        lines = run.stdout.splitlines()
        self.assertEqual(lines[0], NORMAL[0])
        self.assertTrue(lines[1].startswith("Time to a PR's result: unknown ("), lines[1])
        self.assertTrue(lines[-2].startswith("Actions minutes in 2026-01 so far: unknown ("), lines[-2])
        self.assertLess(len(run.stdout.encode()), 16384)


def due(now):
    return subprocess.run([sys.executable, "-I", str(HERE / "ci3_weekly.py"), "due", "--now", now],
                          capture_output=True, text=True, timeout=30)


class Due(unittest.TestCase):
    def test_every_third_pacific_day_from_the_anchor(self):
        # Bug: the gate counts whole days of milliseconds from the 17:00 UTC
        # anchor, so in summer, when 09:00 Pacific is 16:00 UTC, it fires a day
        # late. 2026-11-16 to 2027-06-17 is 213 days.
        for now, fires in (("2026-11-16T17:00:30Z", True), ("2026-11-17T17:00:00Z", False),
                           ("2026-11-18T17:00:00Z", False), ("2026-11-19T17:00:00Z", True),
                           ("2027-06-16T16:00:00Z", False), ("2027-06-17T16:00:00Z", True)):
            run = due(now)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(bool(run.stdout), fires, now)
            if fires:
                self.assertEqual(run.stdout, "CI3 note due: run `python3 -I tools/ci-bench/ci3_weekly.py check`.\n")

    def test_a_gate_that_cannot_read_its_definition_fails_loudly(self):
        # Bug: a broken definition exits 1 with no output, which Cloudroom
        # treats as "nothing due", so the loop stops without a word.
        with tempfile.TemporaryDirectory() as tmp:
            for text in ("{", json.dumps({"wake": {"kind": "interval", "every_ms": 129600000, "anchor_ms": 0}})):
                bad = Path(tmp) / "loop.json"
                bad.write_text(text)
                run = subprocess.run([sys.executable, "-I", str(HERE / "ci3_weekly.py"), "due", "--now",
                                      "2026-11-16T17:00:00Z", "--definition", str(bad)],
                                     capture_output=True, text=True, timeout=30)
                self.assertEqual((run.returncode, run.stdout), (2, ""), text)
                self.assertTrue(run.stderr.startswith("ci3_weekly: "), run.stderr)


def records_module():
    spec = importlib.util.spec_from_file_location("skills_eval_records", ROOT / "tools" / "skills-eval" / "records.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


KNOWN = {"$schema", "$id", "$defs", "$ref", "title", "description", "type", "const", "enum", "oneOf", "required",
         "additionalProperties", "properties", "items", "minItems", "minLength", "maxLength", "pattern", "minimum",
         "maxUtf8Bytes"}


def schema_errors(value):
    schema = json.loads(SCHEMA.read_text())
    errors = records_module().schema_errors(value, schema, schema)
    brief = value.get("action", {}).get("brief")
    if isinstance(brief, str) and len(brief.encode()) > schema["$defs"]["brief"]["maxUtf8Bytes"]:
        errors.append("$.action.brief: over maxUtf8Bytes")
    return errors


class Definition(unittest.TestCase):
    def test_the_definition_passes_the_loops_schema(self):
        # Bug: a definition WizLoops can't read (a missing limit, a wrong type,
        # an extra key) waits to fail at takeover.
        self.assertEqual(schema_errors(json.loads(DEFINITION.read_text())), [])

    def test_the_schema_check_refuses_a_broken_definition(self):
        # Bug: the check above passes anything (a keyword the validator ignores,
        # a validator that never fails).
        def walk(node, keys):
            if isinstance(node, dict):
                for k, v in node.items():
                    keys.add(k)
                    if k not in {"properties", "$defs"}:
                        walk(v, keys)
                    else:
                        for sub in v.values():
                            walk(sub, keys)
            elif isinstance(node, list):
                for v in node:
                    walk(v, keys)
            return keys
        self.assertEqual(walk(json.loads(SCHEMA.read_text()), set()) - KNOWN, set())
        good = json.loads(DEFINITION.read_text())
        for edit in (lambda d: d.pop("enabled"), lambda d: d.update(extra=1),
                     lambda d: d["check"].update(timeout_ms=0), lambda d: d["wake"].update(kind="cron"),
                     lambda d: d["action"].update(brief=" "), lambda d: d["action"].update(brief="é" * 8193),
                     lambda d: d["check"].update(argv=[]), lambda d: d.update(mode="on")):
            bad = copy.deepcopy(good)
            edit(bad)
            self.assertNotEqual(schema_errors(bad), [], bad)

    def test_disabled_in_shadow_every_3_days_at_9_pacific(self):
        # Bug: the definition starts live, or wakes at another time or interval
        # than the approved cadence; or its check isn't this script's.
        d = json.loads(DEFINITION.read_text())
        self.assertEqual((d["enabled"], d["mode"]), (False, "shadow"))
        # 3 days, and 2026-11-16 09:00 PST (17:00 UTC) in milliseconds.
        self.assertEqual(d["wake"], {"kind": "interval", "every_ms": 259200000, "anchor_ms": 1794848400000})
        self.assertEqual(d["check"]["argv"], ["python3", "-I", "tools/ci-bench/ci3_weekly.py", "check"])
        self.assertTrue((ROOT / d["check"]["argv"][2]).is_file())
        self.assertEqual(d["budget"]["max_agent_starts"], 1)


if __name__ == "__main__":
    unittest.main()
