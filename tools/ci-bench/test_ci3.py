#!/usr/bin/env python3
"""CI3's measure (contracts/ci3.v1.md) on synthetic windows and a fake GitHub.

Every expected number is worked out by hand from fixtures/ci3/README.md,
never by ci3.py. Each test names the bug it catches.
"""
import copy
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import ci3  # noqa: E402

WINDOW = HERE / "fixtures" / "ci3" / "window.json"


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


def fake(activity_extra=()):
    repo = {"full_name": "example/repo"}
    pr = {"number": 9, "created_at": "2026-01-05T10:05:00Z", "updated_at": "2026-01-05T12:00:00Z",
          "closed_at": None, "head": {"ref": "topic/x", "repo": repo}, "base": {"repo": repo}}
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
        f"{B}/actions/runs/4/attempts/2/jobs": jobs(gh_job(42, "ci", "2026-01-05T11:40:00Z", "2026-01-05T11:40:01Z",
                                                            "2026-01-05T11:42:00Z")),
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


if __name__ == "__main__":
    unittest.main()
