#!/usr/bin/env python3
"""CI3 in the war room (#826): its measure (contracts/ci3.v1.md) on synthetic
windows and a fake GitHub, and its loop's check (#784) on synthetic weeks, its
gate and its definition.

Every expected number is worked out by hand from fixtures/ci3/README.md and
fixtures/ci3-weekly/README.md, or written here as a literal, never by ci3.py
or ci3_check.py. Each test names the bug it catches.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import random
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import ci3  # noqa: E402
import ci3_check  # noqa: E402

FIXTURES = HERE / "fixtures"
WINDOW = FIXTURES / "ci3" / "window.json"


def window():
    return json.loads(WINDOW.read_text())


def cli(*args):
    return subprocess.run([sys.executable, "-I", str(HERE / "ci3.py"), *args], capture_output=True, text=True,
                          timeout=30)


class Measure(unittest.TestCase):
    def test_red_cancelled_and_rerun_results_stay_in(self):
        # Bug: the bench's own cohort rule (successful runs, latest attempt only)
        # reused here would give 15.0 / 19.3: a faster number from dropped reds
        # and a rerun timed from its last attempt.
        r = ci3.measure(window())["result"]
        self.assertEqual((r["p50_minutes"], r["p95_minutes"]), (20.0, 45.0))
        self.assertEqual(r["timed"], 5)
        self.assertEqual(r["outcomes"], {"success": 3, "failure": 1, "cancelled": 1, "other": 0})
        self.assertEqual(r["with_reruns"], 1)

    def test_fast_reds_show_beside_the_number(self):
        # Bug: quick red heads (a draft fails at once) pull the number down
        # unseen; each outcome's own times sit beside it.
        by = ci3.measure(window())["result"]["by_outcome"]
        self.assertEqual(by, {"success": {"p50_minutes": 20.0, "p95_minutes": 45.0},
                              "failure": {"p50_minutes": 40.0, "p95_minutes": 40.0},
                              "cancelled": {"p50_minutes": 3.0, "p95_minutes": 3.0}})

    def test_missing_results_are_listed_never_dropped(self):
        # Bug: a head with no final result silently leaves the cohort.
        rec = ci3.measure(window())
        self.assertEqual(rec["heads"], 7)
        self.assertEqual(rec["missing"], [
            {"pr": 106, "head": "f" * 40, "reason": "ci: unfinished"},
            {"pr": 107, "head": None, "reason": "push time unknown"},
        ])

    def test_same_runs_give_the_same_record_every_time(self):
        # Bug: the record depends on input order, the clock or the run.
        first, second = cli("measure", str(WINDOW), "--label", "x"), cli("measure", str(WINDOW), "--label", "x")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        w = window()
        random.Random(7).shuffle(w["heads"])
        self.assertEqual(ci3.measure(w, "x"), json.loads(first.stdout))

    def test_a_check_that_never_reported_counts_with_its_run(self):
        # Bug: a run cancelled before its `ci` job existed drops the head, or
        # counts it as missing, so cancelled work leaves the number.
        w = window()
        h4 = next(h for h in w["heads"] if h["pr"] == 104)
        attempt = h4["runs"]["ci.yml"]["attempts"][0]
        attempt["jobs"] = [j for j in attempt["jobs"] if j["name"] != "ci"]
        rec = ci3.measure(w)
        # It ends with its last job, the rust lane, at 13:02:40: 160 s.
        self.assertEqual(rec["result"]["timed"], 5)
        self.assertEqual(rec["result"]["outcomes"]["cancelled"], 1)
        self.assertEqual(rec["result"]["p50_minutes"], 20.0)
        self.assertNotIn(104, [m["pr"] for m in rec["missing"]])
        # Its critical path still counts (R4): anchored at its last job, the
        # rust lane: changes 28 s + rust 107 s on a runner, so waiting 25,
        # setup 10 + 45, running 18 + 62, together its 160 s.
        self.assertEqual(rec["critical_path"]["results"], 5)
        w["heads"] = [h4]
        b = ci3.measure(w)["critical_path"]
        self.assertEqual([b[k]["p50_seconds"] for k in ("waiting", "setup", "running", "unclassified")],
                         [25, 55, 80, 0])
        # With no job at all, the run's own end stands (13:50:20, 3,020 s), all of it waiting.
        attempt["jobs"] = []
        b = ci3.measure(w)["critical_path"]
        self.assertEqual(b["results"], 1)
        self.assertEqual([b[k]["p50_seconds"] for k in ("waiting", "setup", "running", "unclassified")],
                         [3020, 0, 0, 0])

    def test_a_job_that_never_got_a_runner_holds_none(self):
        # Bug (R2): a cancelled job with no runner and no steps is charged as
        # runner minutes and setup; its time was waiting.
        w = window()
        h3 = next(h for h in w["heads"] if h["pr"] == 103)
        h3["runs"]["ci.yml"]["attempts"][-1]["jobs"].append(
            {"id": 999999, "name": "queued", "conclusion": "cancelled", "created_at": "2026-01-05T12:25:00Z",
             "started_at": "2026-01-05T12:25:00Z", "completed_at": "2026-01-05T12:30:00Z", "runner_name": None,
             "steps": [], "run_attempt": 2})
        rec = ci3.measure(w)
        self.assertEqual(rec["runner_minutes"]["total"], 153.8)
        self.assertEqual(rec["critical_path"]["setup"]["p95_seconds"], 58)

    def test_critical_path_splits_the_whole_time(self):
        # Bug: a rerun's earlier attempt and the push-to-run gap vanish from
        # the buckets, so waiting looks smaller than it was.
        b = ci3.measure(window())["critical_path"]
        self.assertEqual(b["results"], 5)
        self.assertEqual((b["waiting"]["p50_seconds"], b["waiting"]["p95_seconds"]), (38, 1808))
        self.assertEqual((b["setup"]["p50_seconds"], b["setup"]["p95_seconds"]), (58, 58))
        self.assertEqual((b["running"]["p50_seconds"], b["running"]["p95_seconds"]), (820, 2300))
        self.assertEqual((b["unclassified"]["p50_seconds"], b["unclassified"]["p95_seconds"]), (14, 14))

    def test_side_numbers(self):
        # Bug: runner minutes lose a rerun's first attempt or the privacy runs.
        rec = ci3.measure(window())
        self.assertEqual(rec["runner_minutes"], {"pr_heads": 122.3, "merge_queue": 31.4, "total": 153.8,
                                                 "per_day": 153.8})
        q = rec["merge_queue"]
        self.assertEqual((q["p50_minutes"], q["p95_minutes"], q["groups"], q["missing"]), (25.0, 25.0, 1, 0))

    def test_a_head_outside_the_window_is_refused(self):
        # Bug: a window file edited by hand quietly mixes in another window's heads.
        w = window()
        w["heads"][0]["start"] = "2026-01-06T00:00:00Z"
        with self.assertRaises(ci3.Fail):
            ci3.measure(w)

    def test_a_window_file_of_another_shape_is_refused(self):
        # Bug: a hand-edited or truncated window file (a run without its
        # attempts, an unknown field) is measured as if complete.
        for edit in (lambda w: w["heads"][0]["runs"]["ci.yml"].pop("attempts"),
                     lambda w: w["heads"][0].update(extra=1),
                     lambda w: next(h for h in w["heads"] if h["pr"] == 103)["runs"]["ci.yml"]["attempts"].reverse(),
                     lambda w: w["groups"][0]["runs"].pop("privacy.yml")):
            w = window()
            edit(w)
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "w.json"
                path.write_text(json.dumps(w))
                run = cli("measure", str(path))
            self.assertEqual((run.returncode, run.stdout), (1, ""))
            self.assertTrue(run.stderr.startswith("ci3: "), run.stderr)
        self.assertEqual(ci3.read_window(WINDOW), window())


SHA1, SHA2 = "1" * 40, "2" * 40


def gh_job(i, name, created, started, completed, conclusion="success"):
    return {"id": i, "name": name, "conclusion": conclusion, "created_at": created, "started_at": started,
            "completed_at": completed, "runner_name": "r", "run_attempt": 1, "steps": []}


def gh_run(i, sha, created, event="pull_request", attempts=1):
    return {"id": i, "head_sha": sha, "event": event, "created_at": created, "updated_at": created,
            "status": "completed", "conclusion": "success", "run_attempt": attempts}


class FakeGitHub:
    """Answers the paths ci3.collect asks for; any other path fails the test."""

    def __init__(self, answers):
        self.answers, self.asked = answers, []

    def __call__(self, path):
        self.asked.append(path)
        for prefix, answer in self.answers.items():
            if path.startswith(prefix):
                return copy.deepcopy(answer)
        raise AssertionError(f"unexpected read: {path}")


def runs(*items):
    return {"total_count": len(items), "workflow_runs": list(items)}


def jobs(*items):
    return {"total_count": len(items), "jobs": list(items)}


B = "repos/{owner}/{repo}"


def fake(activity_extra=(), head_repo="example/repo", created="2026-01-05T10:05:00Z"):
    repo = {"full_name": "example/repo"}
    pr = {"number": 9, "created_at": created, "updated_at": "2026-01-05T12:00:00Z",
          "closed_at": None, "head": {"ref": "topic/x", "repo": {"full_name": head_repo}}, "base": {"repo": repo}}
    activity = [
        {"activity_type": "branch_creation", "after": SHA1, "timestamp": "2026-01-05T10:00:00Z"},
        {"activity_type": "push", "after": SHA2, "timestamp": "2026-01-05T11:00:00Z"},
        {"activity_type": "branch_deletion", "after": "0" * 40, "timestamp": "2026-01-05T11:30:00Z"},
        *activity_extra,
    ]
    return FakeGitHub({
        f"{B}/pulls?": [pr],
        f"{B}/activity?ref=refs/heads/topic/x&": activity,
        f"{B}/actions/workflows/ci.yml/runs?head_sha={SHA1}": runs(gh_run(1, SHA1, "2026-01-05T10:05:10Z")),
        # Privacy also runs when the PR's text is edited: the later run is not the head's result.
        f"{B}/actions/workflows/privacy.yml/runs?head_sha={SHA1}": runs(
            gh_run(3, SHA1, "2026-01-05T10:50:00Z"), gh_run(2, SHA1, "2026-01-05T10:05:05Z")),
        f"{B}/actions/workflows/ci.yml/runs?head_sha={SHA2}": runs(gh_run(4, SHA2, "2026-01-05T11:00:20Z", attempts=2)),
        f"{B}/actions/workflows/privacy.yml/runs?head_sha={SHA2}": runs(gh_run(5, SHA2, "2026-01-05T11:00:20Z")),
        f"{B}/actions/runs/1/attempts/1/jobs": jobs(gh_job(11, "ci", "2026-01-05T10:20:00Z", "2026-01-05T10:20:01Z",
                                                            "2026-01-05T10:20:30Z")),
        f"{B}/actions/runs/2/attempts/1/jobs": jobs(gh_job(21, "privacy", "2026-01-05T10:05:05Z",
                                                            "2026-01-05T10:05:06Z", "2026-01-05T10:08:00Z")),
        f"{B}/actions/runs/3/attempts/1/jobs": jobs(gh_job(31, "privacy", "2026-01-05T10:50:00Z",
                                                            "2026-01-05T10:50:01Z", "2026-01-05T10:59:00Z")),
        f"{B}/actions/runs/4/attempts/1/jobs": jobs(gh_job(41, "ci", "2026-01-05T11:10:00Z", "2026-01-05T11:10:01Z",
                                                            "2026-01-05T11:10:30Z", "failure")),
        f"{B}/actions/runs/4/attempts/2/jobs": jobs(dict(gh_job(42, "ci", "2026-01-05T11:40:00Z", "2026-01-05T11:40:01Z",
                                                                 "2026-01-05T11:42:00Z"), run_attempt=2)),
        f"{B}/actions/runs/5/attempts/1/jobs": jobs(gh_job(51, "privacy", "2026-01-05T11:00:20Z",
                                                            "2026-01-05T11:00:21Z", "2026-01-05T11:03:00Z")),
        f"{B}/actions/workflows/ci.yml/runs?event=merge_group": runs(),
        f"{B}/actions/workflows/privacy.yml/runs?event=merge_group": runs(),
    })


class Collect(unittest.TestCase):
    def collect(self, gh):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "w.json"
            ci3.collect("2026-01-05T00:00:00Z", "2026-01-06T00:00:00Z", out, read=gh, now="2026-01-06T01:00:00Z")
            return ci3.read_window(out)

    def test_clock_starts_at_the_push_or_the_pr_opening(self):
        # Bug: the clock starts at the run's creation (hiding the push-to-run
        # wait), a later `edited` privacy run stands for the head's result, or
        # a rerun's last attempt is timed alone.
        rec = ci3.measure(self.collect(fake()))
        # Head 1: opened 10:05:00 at the 10:00 push; done 10:20:30: 930 s.
        # Head 2: pushed 11:00:00; ci red, then rerun green at 11:42:00: 2520 s.
        self.assertEqual((rec["heads"], rec["result"]["timed"]), (2, 2))
        self.assertEqual((rec["result"]["p50_minutes"], rec["result"]["p95_minutes"]), (15.5, 42.0))
        self.assertEqual(rec["result"]["with_reruns"], 1)

    def test_only_get_reads(self):
        # Bug: collection writes to GitHub or reads outside the bench's GET paths.
        gh = fake()
        self.collect(gh)
        self.assertTrue(all(p.startswith(B + "/") for p in gh.asked))

    def test_a_branch_too_busy_to_read_whole_is_refused(self):
        # Bug: a truncated activity page silently drops heads.
        extra = [{"activity_type": "push", "after": f"{i:040x}", "timestamp": "2026-01-05T09:00:00Z"}
                 for i in range(100)]
        with self.assertRaises(ci3.Fail):
            self.collect(fake(extra))

    def test_a_fork_pr_in_the_window_is_refused(self):
        # Bug (R1): a fork's pushes aren't in this repository's activity, so
        # its heads vanish (heads 0, missing none) and the cohort looks whole.
        for created in ("2026-01-04T10:05:00Z", "2026-01-05T10:05:00Z"):
            with self.assertRaisesRegex(ci3.Fail, "PR #9 is from a fork"):
                self.collect(fake(head_repo="contributor/fork", created=created))

    def test_a_partial_rerun_counts_each_execution_once(self):
        # Bug (R3): a rerun of failed jobs lists the earlier attempt's
        # successful job again; it is charged twice and enters the rerun's
        # critical path as setup.
        gh = fake()
        setup = gh_job(43, "setup", "2026-01-05T11:00:20Z", "2026-01-05T11:00:21Z", "2026-01-05T11:05:21Z")
        for k in (1, 2):
            gh.answers[f"{B}/actions/runs/4/attempts/{k}/jobs"]["jobs"].append(copy.deepcopy(setup))
            gh.answers[f"{B}/actions/runs/4/attempts/{k}/jobs"]["total_count"] += 1
        rec = ci3.measure(self.collect(gh))
        # 29 + 174 + 29 + 119 + 159 s, plus the 300 s setup job once: 810 s.
        self.assertEqual(rec["runner_minutes"]["total"], 13.5)
        # Head 2's path is the rerun's ci job alone (119 s, no steps: setup).
        self.assertEqual(rec["critical_path"]["setup"]["p95_seconds"], 119)


class Steps(unittest.TestCase):
    def test_check_steps_covers_ci_and_refuses_a_step_with_no_row(self):
        # catches: a CI step with no row in the war room's step table, whose
        # time CI3's critical path then counts as unclassified unseen; or a
        # check that passes anything. Moved with the table from ci-bench (#826).
        workflow = ROOT / ".github" / "workflows" / "ci.yml"
        ok = cli("check-steps")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertRegex(ok.stdout, r"^covered [1-9][0-9]* CI steps\n$")
        with tempfile.TemporaryDirectory() as tmp:
            planted = Path(tmp) / "ci.yml"
            planted.write_text(workflow.read_text() + "\n      - name: A newly planted unknown CI step\n        run: true\n")
            bad = cli("check-steps", "--workflow", str(planted))
        self.assertEqual((bad.returncode, bad.stdout), (1, ""))
        self.assertEqual(bad.stderr, f"ci3: step 'A newly planted unknown CI step' (job {planted}) matches no row"
                                     f" of {HERE / 'steps.tsv'}\n")


# ---------------------------------------------------------------- the loop's check (#784)

FIX = FIXTURES / "ci3-weekly"
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


class FakeWeek:
    """Answers by the longest matching path prefix; `$fail` is a failed read; any other path fails the test."""

    def __init__(self, answers):
        self.answers, self.asked = answers, []

    def __call__(self, path):
        self.asked.append(path)
        for prefix in sorted(self.answers, key=len, reverse=True):
            if path.startswith(prefix):
                answer = self.answers[prefix]
                if isinstance(answer, dict) and "$fail" in answer:
                    raise ci3_check.Fail(answer["$fail"])
                return copy.deepcopy(answer)
        raise AssertionError(f"unexpected read: {path}")


def github(**changes):
    answers = json.loads((FIX / "github.json").read_text())
    answers.update(changes)
    return FakeWeek(answers)


TMP = tempfile.TemporaryDirectory(prefix="test-ci3-check-")  # removed at exit


def record(p50, p95):
    """A copy of the synthetic record with another BEFORE, in this run's own folder."""
    fd, path = tempfile.mkstemp(suffix=".md", dir=TMP.name)
    with os.fdopen(fd, "w") as f:
        f.write(RECORD.read_text().replace('"p50_minutes": 20.0', f'"p50_minutes": {p50}')
                .replace('"p95_minutes": 45.0', f'"p95_minutes": {p95}'))
    return path


REPO = "synthetic-owner/synthetic-repo"
# A synthetic `gh` for the collector's own reads: it answers `gh api PATH` as FakeWeek does, from the
# same answers, and logs each path it is asked. It never reaches the network.
FAKE_GH = """import json, os, sys
path = sys.argv[2] if sys.argv[1:2] == ["api"] and len(sys.argv) == 3 else None
with open(os.environ["CI3_TEST_LOG"], "a") as log:
    log.write(json.dumps(path) + "\\n")
answers = json.load(open(os.environ["CI3_TEST_ANSWERS"]))
for prefix in sorted(answers, key=len, reverse=True):
    if path is not None and path.startswith(prefix):
        answer = answers[prefix]
        if isinstance(answer, dict) and "$fail" in answer:
            sys.exit(answer["$fail"])
        print(json.dumps(answer))
        sys.exit(0)
sys.exit("synthetic gh: unexpected read")
"""


class Collector:
    """FakeWeek's answers behind a synthetic `gh` on PATH, for the war room's collector, with its own
    private store; on exit every path the collector asked joins the fake's `asked`."""

    def __init__(self, gh):
        self.gh = gh

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="test-ci3-collector-")
        root = Path(self.tmp.name)
        (root / "bin").mkdir()
        fake = root / "bin" / "gh"
        fake.write_text(f"#!{sys.executable} -I\n" + FAKE_GH)
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        (root / "answers.json").write_text(json.dumps(self.gh.answers))
        self.store, self.log = root / "store", root / "gh.log"
        self.env = dict(os.environ)
        os.environ.update(PATH=f"{root / 'bin'}{os.pathsep}{os.environ['PATH']}", GH_REPO=REPO,
                          CI3_TEST_ANSWERS=str(root / "answers.json"), CI3_TEST_LOG=str(self.log),
                          OPENWIZ_COLLECTOR_STORE=str(self.store))
        return self

    def __exit__(self, *exc):
        os.environ.clear()
        os.environ.update(self.env)
        asked = [json.loads(p) for p in self.log.read_text().splitlines()] if self.log.exists() else []
        self.gh.asked += asked
        self.kept = sorted(p.relative_to(self.store).as_posix() for p in self.store.rglob("*.json")) \
            if self.store.exists() else []
        self.windows = [json.loads((self.store / p).read_text()) for p in self.kept]
        self.tmp.cleanup()


def check(gh=None, rec=RECORD):
    gh = gh or github()
    with Collector(gh):
        return ci3_check.check(NOW, read=gh, record=rec, authors=AUTHORS).splitlines()


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
        # Runs created up to 32 days before the month can still run in it (R2).
        self.assertIn(f"{B}/actions/runs?created=2025-11-30T00:00:00Z..2026-01-06T02:30:00Z&per_page=100&page=1",
                      gh.asked)

    def test_the_estimate_counts_execution_in_the_month_not_creation(self):
        # Bug (R2): runs are picked by creation date, so a run created on the
        # last day of January that runs in February (queued, or a later
        # attempt) is left out, and February's estimate is low; or a run's
        # January execution is charged to February. A run can be rerun up to
        # 30 days after it started, then queue a day and run 6 hours, so runs
        # created from 32 days before the month are read, and only each job's
        # time inside the month counts.
        now = "2026-02-02T17:00:00Z"
        def job(i, started, completed):
            return {"id": i, "name": "j", "conclusion": "success", "created_at": started, "started_at": started,
                    "completed_at": completed, "runner_name": "r", "run_attempt": 1, "steps": []}
        runs = {"total_count": 3, "workflow_runs": [
            {"id": 700, "created_at": "2026-01-31T23:59:00Z"},
            {"id": 701, "created_at": "2026-01-03T00:00:00Z"},
            {"id": 702, "created_at": "2026-01-31T23:40:00Z"}]}
        gh = FakeWeek({
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
        minutes, source, _ = ci3_check.read_minutes(gh, now)
        self.assertEqual((minutes, source), (99, "estimate"))
        self.assertIn(f"{B}/actions/runs?created=2025-12-31T00:00:00Z..{now}&per_page=100&page=1", gh.asked)

    def test_a_failed_read_still_prints_the_note(self):
        # Bug: one failed read (a fork PR in the window, the comments) silences
        # the run, though every run is due for its note.
        fork = github()
        fork.answers[f"{B}/pulls?"][0]["head"]["repo"]["full_name"] = "contributor/fork"
        fork.answers[f"{B}/issues/780/comments?"] = FAIL
        lines = check(fork)
        self.assertEqual(lines[0], NORMAL[0])
        # The collector's own words for a window it can't read whole (collector.v1, `ci3`).
        self.assertEqual(lines[1], "Time to a PR's result: unknown (CI3 unavailable: the window's PR heads"
                                   " and runs could not be read whole.).")
        self.assertTrue(lines[2].startswith("Against the last note: unknown (gh api failed"), lines[2])
        self.assertEqual(lines[3:], [NORMAL[8], '<!-- openwiz.ci3-note.v1 {"actions_minutes": 35001, "alert": false,'
                                     ' "measure": "ci3.v1", "minutes_source": "billing", "month": "2026-01",'
                                     ' "p50_minutes": null,'
                                     ' "p95_minutes": null, "until": "2026-01-06T00:00:00Z"} -->'])

    def test_the_measure_is_the_collectors_ci3_fact(self):
        # catches: the loop measuring CI3 on its own, beside the war room's
        # collector, so the note's numbers can differ from the page's (spec
        # #819, story 3). The collector keeps the window it measured, privately,
        # named by its hash: one window, the note's seven days.
        gh = github()
        with Collector(gh) as collector:
            lines = ci3_check.check(NOW, read=gh, record=RECORD, authors=AUTHORS).splitlines()
        self.assertEqual(lines, NORMAL)
        self.assertEqual(len(collector.kept), 1, collector.kept)
        self.assertTrue(collector.kept[0].startswith("collector/ci/ci3/"), collector.kept)
        window = collector.windows[0]
        self.assertEqual((window["since"], window["until"], len(window["heads"])),
                         ("2025-12-30T00:00:00Z", "2026-01-06T00:00:00Z", 2))

    def test_the_record_authors_are_the_rules_files_whole_row(self):
        # catches: the note's last-note read trusting a commenter the rules
        # file does not name, or keeping the logins that parsed from a broken
        # row (#641's rule, as contracts/fleet-tick.v1.md words it). Each
        # expected set is written by hand from its row.
        head = "# Fleet\n\n## GitHub identity\n\n| Setting | Value |\n| --- | --- |\n"
        good = [("| Record authors | `Synthetic-App[bot]`, `synthetic-owner` |",
                 {"synthetic-app[bot]", "synthetic-owner"}),
                ("|Record authors|`a`|", {"a"}),
                ("|  Record authors  |  `a` ,`b-c`  |  ", {"a", "b-c"}),
                ("| Record authors | `A1` |\r", {"a1"})]
        bad = ["| Record authors | |", "| Record authors | `` |", "| Record authors | `a--b` |",
               "| Record authors | `-a` |", "| Record authors | `a-` |", "| Record authors | a |",
               "| Record authors | `a`, |", "| Record authors | `a` `b` |", "| Record authors | `a@b` |",
               "| Record authors | `a[bot]x` |", "| Record authors | `a` | extra |",
               "| Record authors | `a` | extra", "| Record authors | `a`",
               "| Record authors | `a` |\n| Record authors | `b` |", "| Record author | `a` |"]
        with tempfile.TemporaryDirectory() as tmp:
            fleet = Path(tmp) / "fleet.md"
            with mock.patch.object(ci3_check, "FLEET", fleet):
                for row, want in good:
                    fleet.write_text(head + row + "\n\n## Next\n")
                    self.assertEqual(ci3_check.record_authors(), frozenset(want), row)
                for row in bad:
                    fleet.write_text(head + row + "\n\n## Next\n")
                    with self.assertRaises(ci3_check.Fail, msg=row):
                        ci3_check.record_authors()
                # The row counts only inside its own section.
                fleet.write_text("# Fleet\n\n## Other\n\n| Record authors | `a` |\n\n## GitHub identity\n")
                with self.assertRaises(ci3_check.Fail):
                    ci3_check.record_authors()

    def test_an_unreadable_author_source_is_said_in_the_finding(self):
        # catches #1208: an author source that is gone, a folder, not UTF-8 or
        # malformed stops the whole check (FileNotFoundError, UnicodeDecodeError)
        # instead of saying the last note is unknown; or the comments are read
        # and trusted with no authors at all.
        with tempfile.TemporaryDirectory() as tmp:
            sources = {"gone": Path(tmp) / "gone.md", "a folder": Path(tmp)}
            (Path(tmp) / "latin1.md").write_bytes(b"## GitHub identity\n| Record authors | `caf\xe9` |\n")
            (Path(tmp) / "broken.md").write_text("## GitHub identity\n| Record authors | `a`, `b c` |\n")
            sources.update({"not UTF-8": Path(tmp) / "latin1.md", "malformed": Path(tmp) / "broken.md"})
            for why, fleet in sources.items():
                gh = github()
                with mock.patch.object(ci3_check, "FLEET", fleet), Collector(gh):
                    lines = ci3_check.check(NOW, read=gh, record=RECORD).splitlines()
                self.assertEqual(lines[:4] + lines[5:], NORMAL[:4] + NORMAL[5:], why)
                self.assertTrue(lines[4].startswith("Against the last note: unknown (cannot read the record authors:"
                                                    " docs/agents/fleet.md: " if why != "malformed" else
                                                    "Against the last note: unknown (docs/agents/fleet.md names no"
                                                    " record authors)."), (why, lines[4]))
                self.assertNotIn(tmp, "\n".join(lines), why)
                self.assertFalse([p for p in gh.asked if "/comments" in p], why)

    def test_the_real_before_record_reads(self):
        # Bug: docs/ci3.md's BEFORE block changes form and every note compares
        # with nothing. Its numbers, 22.4 and 50.9, are the published record's.
        before = ci3_check.read_before(ROOT / "docs" / "ci3.md")
        self.assertEqual((before["result"]["p50_minutes"], before["result"]["p95_minutes"]), (22.4, 50.9))

    def test_only_get_reads(self):
        # Bug: the check writes to GitHub, or reads outside `gh api` GET paths.
        gh = github()
        check(gh)
        self.assertTrue(all(p.startswith((B + "/", "organizations/{owner}/")) for p in gh.asked), gh.asked)


# The smoke run (#1208): the loop's own command on this checkout, offline. Network, any program but
# `gh`, and any read under skills/ (the gitignored WizSkills install) are refused, so the check can
# depend on nothing a fresh clone lacks. argv: the checkout, then the command's own arguments.
SMOKE = r"""
import os, runpy, sys
root = os.path.realpath(sys.argv[1])
banned = [os.path.join(root, "skills"), os.path.join(root, ".wizskills")]
def refuse(event, args):
    if event == "open" and isinstance(args[0], (str, bytes)):
        path = os.fsdecode(args[0])
        for p in {os.path.abspath(path), os.path.realpath(path)}:
            if any(p == b or p.startswith(b + os.sep) for b in banned):
                raise PermissionError(f"smoke: a read under skills/: {path}")
    elif event.startswith("socket.") and event not in ("socket.__new__", "socket.gethostname"):
        raise PermissionError(f"smoke: network: {event}")
    elif event in ("subprocess.Popen", "os.posix_spawn", "os.exec", "os.system") and \
            os.path.basename(os.fsdecode(args[0] if event != "subprocess.Popen" else args[1][0])) != "gh":
        raise PermissionError(f"smoke: a program other than gh: {args[0]}")
sys.addaudithook(refuse)
sys.argv = [os.path.join(root, "tools", "collector", "ci3_check.py"), *sys.argv[2:]]
runpy.run_path(sys.argv[0], run_name="__main__")
"""


class Smoke(unittest.TestCase):
    """CI runs this class on every pull request (ci.yml's always lane): seconds, offline, on the
    real files the loop reads, with no fixture in their place."""

    def test_the_loops_command_prints_its_finding_offline(self):
        # Bug: the loop's command exits nonzero or prints nothing when GitHub
        # can't be read, so no agent wakes and Jake hears nothing. And #1208:
        # it loads a file a fresh clone lacks (launch-fleet's removed helper)
        # or one that moved, and crashes before its finding. Only `gh` is on
        # PATH, and it fails: no read reaches GitHub. The BEFORE record, the
        # record authors and the definition are the checkout's own.
        with tempfile.TemporaryDirectory() as tmp:
            gh = Path(tmp) / "gh"
            gh.write_text("#!/bin/sh\necho 'synthetic: not logged in' >&2\nexit 1\n")
            gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
            env = {"PATH": tmp, "HOME": tmp, "OPENWIZ_COLLECTOR_STORE": str(Path(tmp) / "store")}
            run = subprocess.run([sys.executable, "-I", "-c", SMOKE, str(ROOT), "check", "--now", NOW],
                                 capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        lines = run.stdout.splitlines()
        self.assertEqual(lines[0], NORMAL[0])
        self.assertTrue(lines[1].startswith("Time to a PR's result: unknown ("), lines[1])
        # The real BEFORE record read (no "Against BEFORE: unknown" line), and the real record authors
        # read, so the last note's read reached the comments, which `gh` refused.
        self.assertEqual(lines[2], "Against the last note: unknown (gh api repos/{owner}/{repo}/issues/780/"
                                   "comments?per_page=100&page=1 failed (exit 1): synthetic: not logged in).")
        self.assertTrue(lines[-2].startswith("Actions minutes in 2026-01 so far: unknown ("), lines[-2])
        self.assertLess(len(run.stdout.encode()), 16384)


def due(now):
    return subprocess.run([sys.executable, "-I", str(HERE / "ci3_check.py"), "due", "--now", now],
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
                self.assertEqual(run.stdout, "CI3 note due: run `python3 -I tools/collector/ci3_check.py check`.\n")

    def test_a_gate_that_cannot_read_its_definition_fails_loudly(self):
        # Bug: a broken definition exits 1 with no output, which Cloudroom
        # treats as "nothing due", so the loop stops without a word.
        with tempfile.TemporaryDirectory() as tmp:
            for text in ("{", json.dumps({"wake": {"kind": "interval", "every_ms": 129600000, "anchor_ms": 0}})):
                bad = Path(tmp) / "loop.json"
                bad.write_text(text)
                run = subprocess.run([sys.executable, "-I", str(HERE / "ci3_check.py"), "due", "--now",
                                      "2026-11-16T17:00:00Z", "--definition", str(bad)],
                                     capture_output=True, text=True, timeout=30)
                self.assertEqual((run.returncode, run.stdout), (2, ""), text)
                self.assertTrue(run.stderr.startswith("ci3_check: "), run.stderr)


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
        self.assertEqual(d["check"]["argv"], ["python3", "-I", "tools/collector/ci3_check.py", "check"])
        self.assertTrue((ROOT / d["check"]["argv"][2]).is_file())
        self.assertEqual(d["budget"]["max_agent_starts"], 1)


if __name__ == "__main__":
    unittest.main()
