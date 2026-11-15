#!/usr/bin/env python3
"""CI3 C1 (#782): time budgets that fail. Offline proofs on synthetic records.

Each test names the bug it catches (the test rule, #687). Every expected
value is a worked literal, never computed the way budgets.py computes it.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TRACED = "${{ (needs.changes.outputs.trace == 'true' || needs.changes.outputs.planted == 'true') && %d || %d }}"
MARK = "        if: needs.changes.outputs.trace == 'true' || needs.changes.outputs.planted == 'true'\n"
HEAD = "workflow\tjob\tmode\ttimeout\tp95_seconds\tsamples\truns\tfirst\tlast\n"
T0 = "2030-01-01T00:00:00Z"


def run(*args, env=None, cwd=None):
    return subprocess.run([sys.executable, "-I", str(HERE / "budgets.py"), *map(str, args)],
                          capture_output=True, text=True, timeout=60, env=env, cwd=cwd)


def workflow(jobs):
    """A workflow file: jobs is [(key, timeout line value or None, traced step?)]."""
    text = "name: Synthetic\non: push\njobs:\n"
    for key, timeout, marked in jobs:
        text += f"  {key}:\n    runs-on: ubuntu-24.04\n"
        if timeout is not None:
            text += f"    timeout-minutes: {timeout}\n"
        text += "    steps:\n      - name: Run npm test\n        run: npm test\n"
        if marked:
            text += "      - uses: actions/upload-artifact@0000000000000000000000000000000000000000 # v0\n" + MARK
    return text


def row(wf, job, mode, timeout, p95, samples=20, runs=150):
    return f"{wf}\t{job}\t{mode}\t{timeout}\t{p95}\t{samples}\t{runs}\t{T0}\t2030-01-02T00:00:00Z\n"


def stamp(seconds):
    day, rest = divmod(seconds, 86400)
    h, rest = divmod(rest, 3600)
    m, s = divmod(rest, 60)
    return f"2030-01-{1 + day:02d}T{h:02d}:{m:02d}:{s:02d}Z"


def job(run_id, name, seconds, conclusion="success", traced=False, event="pull_request", start=0):
    """One record in the CI bench's jobs.jsonl shape."""
    a, b = start + run_id * 3600, start + run_id * 3600 + seconds
    steps = [{"name": "Set up job", "conclusion": "success", "started_at": stamp(a), "completed_at": stamp(a)}]
    if name.startswith(("rust", "web")):
        steps += [{"name": "Run npm test", "conclusion": conclusion, "started_at": stamp(a), "completed_at": stamp(b)},
                  {"name": "Run actions/upload-artifact@0000000000000000000000000000000000000000",
                   "conclusion": "success" if traced else "skipped", "started_at": stamp(b), "completed_at": stamp(b)}]
    return {"completed_at": stamp(b), "conclusion": conclusion, "created_at": stamp(a), "event": event,
            "name": name, "run": run_id, "run_concl": conclusion, "runner_name": "GitHub Actions 1",
            "started_at": stamp(a), "steps": steps, "id": run_id * 100 + len(name), "run_attempt": 1,
            "collected_attempt": 1, "run_created_at": stamp(run_id * 3600)}


def window(d, wf, records, runs):
    d = Path(d) / wf.removesuffix(".yml")
    d.mkdir(parents=True)
    (d / "jobs.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records))
    (d / "window.json").write_text(json.dumps({"workflow": wf, "runs": runs, "first": T0,
                                               "last": "2030-01-02T00:00:00Z"}, sort_keys=True))


class Check(unittest.TestCase):
    """CI3-B: the check fails on a job with no budget and on a wrong timeout."""

    def check(self, ci, privacy, table):
        with tempfile.TemporaryDirectory() as temp:
            t = Path(temp)
            (t / "ci.yml").write_text(ci)
            (t / "privacy.yml").write_text(privacy)
            (t / "budgets.tsv").write_text(HEAD + table)
            return run("check", "--table", t / "budgets.tsv", t / "ci.yml", t / "privacy.yml")

    PRIVACY = workflow([("privacy", 5, False)])
    PRIVACY_ROW = row("privacy.yml", "privacy", "all", 5, 120)

    # Bug: a new job arrives with an open-ended timeout and no budget row.
    def test_a_job_with_no_row_fails(self):
        r = self.check(workflow([("always", 12, False), ("site", 30, False)]), self.PRIVACY,
                       row("ci.yml", "always", "all", 12, 450) + self.PRIVACY_ROW)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("ci.yml job site has no budget row", r.stderr)

    # Bug: a timeout is widened (or never set from the table) by hand.
    def test_a_timeout_that_differs_from_its_row_fails(self):
        r = self.check(workflow([("always", 60, False)]), self.PRIVACY,
                       row("ci.yml", "always", "all", 12, 450) + self.PRIVACY_ROW)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("ci.yml job always: timeout-minutes 60, its budget is 12", r.stderr)

    # Bug: a job with no timeout-minutes at all falls back to GitHub's 360.
    def test_a_job_without_a_timeout_fails(self):
        r = self.check(workflow([("always", None, False)]), self.PRIVACY,
                       row("ci.yml", "always", "all", 12, 450) + self.PRIVACY_ROW)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("ci.yml job always has no timeout-minutes", r.stderr)

    # Bug: the Privacy workflow is left out of the check.
    def test_the_privacy_workflow_is_checked_too(self):
        r = self.check(workflow([("always", 12, False)]), workflow([("privacy", 90, False)]),
                       row("ci.yml", "always", "all", 12, 450) + self.PRIVACY_ROW)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("privacy.yml job privacy: timeout-minutes 90, its budget is 5", r.stderr)

    # Bug: a traced or planted run is held to the normal budget, or the other way round.
    def test_traced_and_normal_budgets_are_each_checked(self):
        table = (row("ci.yml", "rust", "normal", 14, 540) + row("ci.yml", "rust", "traced", 47, 1860)
                 + self.PRIVACY_ROW)
        ok = self.check(workflow([("rust", TRACED % (47, 14), True)]), self.PRIVACY, table)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        swapped = self.check(workflow([("rust", TRACED % (14, 47), True)]), self.PRIVACY, table)
        self.assertEqual(swapped.returncode, 1, swapped.stdout + swapped.stderr)
        self.assertIn("ci.yml job rust: traced timeout-minutes 14, its budget is 47", swapped.stderr)
        plain = self.check(workflow([("rust", 14, True)]), self.PRIVACY, table)
        self.assertEqual(plain.returncode, 1, plain.stdout + plain.stderr)
        self.assertIn("ci.yml job rust: timeout-minutes 14 has no traced budget", plain.stderr)

    # Bug: a row's timeout is edited by hand away from 1.5x its p95.
    def test_a_row_whose_timeout_is_not_its_p95_budget_fails(self):
        r = self.check(workflow([("always", 20, False)]), self.PRIVACY,
                       row("ci.yml", "always", "all", 20, 450) + self.PRIVACY_ROW)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("ci.yml always all: timeout 20, but 1.5x its p95 of 450 s is 12", r.stderr)

    # Bug: a row for a job that no longer exists hides a renamed job.
    def test_a_row_for_a_missing_job_fails(self):
        r = self.check(workflow([("always", 12, False)]), self.PRIVACY,
                       row("ci.yml", "always", "all", 12, 450) + row("ci.yml", "gone", "all", 5, 60)
                       + self.PRIVACY_ROW)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("ci.yml has no job gone for its budget row", r.stderr)

    # The real workflows and table: the guard CI runs.
    def test_the_repository_workflows_match_their_table(self):
        r = run("check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class Table(unittest.TestCase):
    """CI3-B: the budgets are 1.5x each job's measured p95, from the collected runs."""

    def table(self, ci_jobs, ci_runs=150, fallback=None, ci=None):
        with tempfile.TemporaryDirectory() as temp:
            t = Path(temp)
            (t / "ci.yml").write_text(ci or workflow([("always", 60, False), ("rust", 60, True)]))
            (t / "privacy.yml").write_text(workflow([("privacy", 90, False)]))
            window(t / "w", "ci.yml", ci_jobs, ci_runs)
            window(t / "w", "privacy.yml", [job(i, "privacy", 100 + i) for i in range(1, 21)], 20)
            args = ["table", t / "w", "--out", t / "budgets.tsv", "--workflows", t / "ci.yml", t / "privacy.yml"]
            if fallback is not None:
                window(t / "f", "ci.yml", fallback, 150)
                window(t / "f", "privacy.yml", [], 0)
                args += ["--fallback", t / "f"]
            r = run(*args)
            rows = {}
            if r.returncode == 0:
                lines = (t / "budgets.tsv").read_text().splitlines()
                self.assertEqual(lines[0] + "\n", HEAD)
                for line in lines[1:]:
                    f = line.split("\t")
                    rows[(f[0], f[1], f[2])] = f[3:]
            return r, rows

    def lanes(self):
        """20 normal runs: always 1..20 min; rust two legs; 3 traced runs."""
        jobs = []
        for i in range(1, 21):
            jobs.append(job(i, "always", 60 * i))
            jobs.append(job(i, "rust (1)", 300 + i))
            jobs.append(job(i, "rust (2)", 400 + i))
        for i in range(21, 24):
            jobs.append(job(i, "always", 120))
            jobs.append(job(i, "rust (1)", 1800 + i, traced=True))
        return jobs

    # Bug: p95, 1.5x, rounding or the 5-minute floor computed wrong; a
    # traced run's long single shard folded into the normal budget; the
    # slower matrix leg's p95 hidden by pooling with the faster one.
    def test_each_job_gets_one_and_a_half_times_its_p95_rounded_up(self):
        r, rows = self.table(self.lanes())
        self.assertEqual(r.returncode, 0, r.stderr)
        # always: 23 samples (20 normal + 3 traced, one mode); nearest-rank
        # p95 is the 22nd of 23 sorted: 60..1200 s and three 120 s, so the
        # sorted list's 22nd is 1140 s; 1.5 x 1140 s = 28.5 min -> 29.
        self.assertEqual(rows[("ci.yml", "always", "all")][:4], ["29", "1140", "23", "150"])
        # rust normal: legs (1) 301..320 and (2) 401..420; leg (2)'s p95 is
        # its 19th, 419 s; 1.5 x 419 s = 10.475 min -> 11.
        self.assertEqual(rows[("ci.yml", "rust", "normal")][:4], ["11", "419", "40", "150"])
        # rust traced: 1821, 1822, 1823 s; p95 of 3 is the 3rd, 1823 s;
        # 1.5 x 1823 s = 45.575 min -> 46.
        self.assertEqual(rows[("ci.yml", "rust", "traced")][:4], ["46", "1823", "3", "150"])
        # privacy: 101..120 s; p95 119 s; 1.5 x 119 s = 2.975 min -> floor 5.
        self.assertEqual(rows[("privacy.yml", "privacy", "all")][:4], ["5", "119", "20", "20"])
        self.assertEqual(rows[("ci.yml", "always", "all")][4:], [T0, "2030-01-02T00:00:00Z"])

    # Bug: a skipped job (no runner, no time) or a cancelled one (cut short)
    # pulls the p95 down; a failed job's real time is dropped.
    def test_only_jobs_that_ran_to_success_or_failure_count(self):
        jobs = [j for j in self.lanes() if j["name"] != "always"]
        jobs += [job(i, "always", 600) for i in range(1, 20)]
        jobs.append(job(20, "always", 900, conclusion="failure"))
        jobs.append(job(21, "always", 3000, conclusion="cancelled"))
        skipped = job(22, "always", 0, conclusion="skipped")
        skipped.update(steps=[], runner_name=None)
        jobs.append(skipped)
        r, rows = self.table(jobs)
        self.assertEqual(r.returncode, 0, r.stderr)
        # 19 x 600 s and one 900 s failure: the 19th of 20 is 600 s -> 15 min.
        self.assertEqual(rows[("ci.yml", "always", "all")][:3], ["15", "600", "20"])

    # Bug: a nightly (schedule) run whose lanes failed before the trace step
    # is counted as a normal run.
    def test_a_scheduled_run_is_traced(self):
        jobs = self.lanes() + [job(30, "rust (1)", 2400, conclusion="failure", event="schedule")]
        r, rows = self.table(jobs)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(rows[("ci.yml", "rust", "traced")][:3], ["60", "2400", "4"])

    # Bug: a job or mode with too few samples gets a budget from noise.
    def test_too_few_samples_read_the_fallback_or_fail(self):
        few = [j for j in self.lanes() if j["run"] < 22]
        r, _ = self.table(few)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("ci.yml job rust traced has 1 sample, fewer than 5", r.stderr)
        older = [job(i, "rust (1)", 1500 + i, traced=True) for i in range(1, 7)]
        r, rows = self.table(few, fallback=older)
        self.assertEqual(r.returncode, 0, r.stderr)
        # From the fallback alone: 1501..1506 s; p95 of 6 is the 6th, 1506 s;
        # 1.5 x 1506 s = 37.65 min -> 38; the row names the fallback's runs.
        self.assertEqual(rows[("ci.yml", "rust", "traced")][:4], ["38", "1506", "6", "150"])

    # Bug: a job in the workflow that never ran in the window is silently
    # left without a row (the check would then fail later, in CI).
    def test_a_job_with_no_samples_fails(self):
        ci = workflow([("always", 60, False), ("rust", 60, True), ("toolkit-nightly", 360, False)])
        r, _ = self.table(self.lanes(), ci=ci)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("ci.yml job toolkit-nightly all has 0 samples, fewer than 5", r.stderr)


class Apply(unittest.TestCase):
    # Bug: setting timeouts by hand edits other lines of a shared workflow.
    def test_apply_changes_only_timeout_lines(self):
        with tempfile.TemporaryDirectory() as temp:
            t = Path(temp)
            before = workflow([("always", 60, False), ("rust", TRACED % (90, 60), True)])
            (t / "ci.yml").write_text(before)
            (t / "privacy.yml").write_text(workflow([("privacy", 5, False)]))
            (t / "budgets.tsv").write_text(HEAD + row("ci.yml", "always", "all", 12, 450)
                                           + row("ci.yml", "rust", "normal", 14, 540)
                                           + row("ci.yml", "rust", "traced", 47, 1860)
                                           + row("privacy.yml", "privacy", "all", 5, 120))
            r = run("apply", "--table", t / "budgets.tsv", t / "ci.yml", t / "privacy.yml")
            self.assertEqual(r.returncode, 0, r.stderr)
            after = (t / "ci.yml").read_text()
            expected = before.replace("timeout-minutes: 60\n", "timeout-minutes: 12\n").replace(
                TRACED % (90, 60), TRACED % (47, 14))
            self.assertEqual(after, expected)
            self.assertEqual(run("check", "--table", t / "budgets.tsv", t / "ci.yml", t / "privacy.yml").returncode, 0)


FAKE_GH = """#!/usr/bin/env python3
import json, os, sys
world = json.load(open(os.environ["FAKE_GH_WORLD"]))
path = sys.argv[2]
with open(os.environ["FAKE_GH_LOG"], "a") as log:
    log.write(" ".join(sys.argv[1:]) + "\\n")
if sys.argv[1] != "api" or len(sys.argv) != 3 or path not in world:
    sys.stderr.write("fake gh: no answer for " + " ".join(sys.argv[1:]) + "\\n")
    sys.exit(1)
print(json.dumps(world[path]))
"""


class Collect(unittest.TestCase):
    # Bug: more runs than asked for are read, an earlier attempt's jobs are
    # used, or a run still in progress is counted.
    def test_collect_reads_the_last_completed_runs_latest_attempt(self):
        base = "repos/{owner}/{repo}/actions"
        def api_run(i, attempt=1):
            return {"id": i, "event": "pull_request", "status": "completed", "conclusion": "success",
                    "created_at": stamp(i * 3600), "run_attempt": attempt}
        def api_job(i, name):
            return {"id": i * 10, "name": name, "conclusion": "success", "created_at": stamp(i * 3600),
                    "started_at": stamp(i * 3600), "completed_at": stamp(i * 3600 + 300), "run_attempt": 2,
                    "runner_name": "GitHub Actions 1", "labels": ["ubuntu-24.04"],
                    "steps": [{"name": "Set up job", "conclusion": "success", "started_at": stamp(i * 3600),
                               "completed_at": stamp(i * 3600)}]}
        runs = [api_run(i, 2) for i in (5, 4, 3)]
        world = {
            f"{base}/workflows/ci.yml/runs?status=completed&created=>=2030-01-01T00:00:00Z&per_page=2&page=1":
                {"total_count": 3, "workflow_runs": runs[:2]},
            f"{base}/workflows/ci.yml/runs?status=completed&created=>=2030-01-01T00:00:00Z&per_page=2&page=2":
                {"total_count": 3, "workflow_runs": runs[2:]},
        }
        for i in (5, 4):
            world[f"{base}/runs/{i}/jobs?filter=latest&per_page=100&page=1"] = {"total_count": 1, "jobs": [api_job(i, "always")]}
            world[f"{base}/runs/{i}"] = api_run(i, 2)
        with tempfile.TemporaryDirectory() as temp:
            t = Path(temp)
            (t / "bin").mkdir()
            (t / "bin" / "gh").write_text(FAKE_GH)
            (t / "bin" / "gh").chmod(0o755)
            (t / "world.json").write_text(json.dumps(world))
            env = {"PATH": f"{t / 'bin'}{os.pathsep}{os.environ['PATH']}", "FAKE_GH_WORLD": str(t / "world.json"),
                   "FAKE_GH_LOG": str(t / "log")}
            r = run("collect", "--workflow", "ci.yml", "--runs", 2, "--per-page", 2, "--since", T0,
                    "--out", t / "w", env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            records = [json.loads(line) for line in (t / "w" / "ci" / "jobs.jsonl").read_text().splitlines()]
            self.assertEqual(sorted(x["run"] for x in records), [4, 5])
            self.assertEqual({x["collected_attempt"] for x in records}, {2})
            self.assertEqual(json.loads((t / "w" / "ci" / "window.json").read_text()),
                             {"workflow": "ci.yml", "runs": 2, "first": stamp(4 * 3600), "last": stamp(5 * 3600)})
            self.assertNotIn("runs/3/", (t / "log").read_text())


if __name__ == "__main__":
    unittest.main()
