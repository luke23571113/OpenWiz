#!/usr/bin/env python3
"""CI3 C1 (#782): time budgets that fail. Offline proofs on synthetic records.

Each test names the bug it catches (the test rule, #687). Every expected
value is a worked literal, never computed the way budgets.py computes it.
"""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LEGACY = "${{ (needs.changes.outputs.trace == 'true' || needs.changes.outputs.planted == 'true') && %d || %d }}"
MARK = "        if: needs.changes.outputs.trace == 'true' || needs.changes.outputs.planted == 'true'\n"
HEAD = "workflow\tjob\tmode\ttimeout\tp95_seconds\tsamples\truns\tfirst\tlast\tsource\n"
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


def row(wf, job, mode, timeout, p95, samples=20, runs=150, source="measured"):
    return f"{wf}\t{job}\t{mode}\t{timeout}\t{p95}\t{samples}\t{runs}\t{T0}\t2030-01-02T00:00:00Z\t{source}\n"


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
            "collected_attempt": 1, "run_created_at": stamp(run_id * 3600),
            "_mode": "traced" if traced or event == "schedule" else "normal"}


def window(d, wf, records, runs):
    d = Path(d) / wf.removesuffix(".yml")
    d.mkdir(parents=True)
    (d / "jobs.jsonl").write_text("".join(json.dumps({k: v for k, v in r.items() if k != "_mode"}, sort_keys=True) + "\n" for r in records))
    records_by_mode = sorted(records, key=lambda r: {None: -1, "normal": 0, "traced": 1, "planted": 2}[r.get("_mode")])
    modes = {str(r["run"]): {"attempt": 1, "trace": r["_mode"] == "traced", "planted": r["_mode"] == "planted",
                             "source": "synthetic-dispatch", "completed_jobs": ["always", "rust", "rust-export"]} for r in records_by_mode if r.get("_mode") is not None}
    (d / "modes.json").write_text(json.dumps(modes))
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
                 + row("ci.yml", "rust", "planted", 60, 0, samples=0, source="unmeasured")
                 + self.PRIVACY_ROW)
        ok = self.check(workflow([("rust", Planted.THREE % (60, 47, 14), True)]), self.PRIVACY, table)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        swapped = self.check(workflow([("rust", Planted.THREE % (60, 14, 47), True)]), self.PRIVACY, table)
        self.assertEqual(swapped.returncode, 1, swapped.stdout + swapped.stderr)
        self.assertIn("ci.yml job rust: traced timeout-minutes 14, its budget is 47", swapped.stderr)
        plain = self.check(workflow([("rust", 14, True)]), self.PRIVACY, table)
        self.assertEqual(plain.returncode, 1, plain.stdout + plain.stderr)
        self.assertIn("ci.yml job rust: timeout-minutes has no matching planted/traced/normal budget", plain.stderr)

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

    # Bug: a job that has never run (#782 question 4) is held to an
    # invented p95, or an unmeasured row hides a measured job's wider timeout.
    def test_an_unmeasured_row_keeps_its_timeout_and_a_derived_row_is_checked(self):
        table = (row("ci.yml", "slow-nightly", "all", 360, 0, samples=1, source="unmeasured")
                 + row("ci.yml", "rust", "all", 14, 540, source="derived:rust-export") + self.PRIVACY_ROW)
        ok = self.check(workflow([("slow-nightly", 360, False), ("rust", 14, False)]), self.PRIVACY, table)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        wide = table.replace("\t14\t540\t", "\t20\t540\t")
        r = self.check(workflow([("slow-nightly", 360, False), ("rust", 20, False)]), self.PRIVACY, wide)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("ci.yml rust all: timeout 20, but 1.5x its p95 of 540 s is 14", r.stderr)
        moved = self.check(workflow([("slow-nightly", 400, False), ("rust", 14, False)]), self.PRIVACY, table)
        self.assertEqual(moved.returncode, 1, moved.stdout + moved.stderr)
        self.assertIn("ci.yml job slow-nightly: timeout-minutes 400, its budget is 360", moved.stderr)
        odd = self.check(workflow([("slow-nightly", 360, False), ("rust", 14, False)]), self.PRIVACY,
                         table.replace("derived:rust-export", "guessed"))
        self.assertEqual(odd.returncode, 1, odd.stdout + odd.stderr)
        self.assertIn("source 'guessed' is not measured, derived:<job> or unmeasured", odd.stderr)

    # Bug: an authorized unmeasured planted twin is treated as a measured
    # zero-second p95, or a derived row silently carries different statistics.
    def test_planted_twin_inherits_unmeasured_fallback_without_claiming_p95(self):
        rows = ""
        for key in ("rust", "rust-export"):
            rows += row("ci.yml", key, "normal", 14, 540)
            rows += row("ci.yml", key, "traced", 47, 1860)
            rows += row("ci.yml", key, "planted", 90, 0, samples=1,
                        source="derived:rust-export" if key == "rust" else "unmeasured")
        ci = workflow([(key, Planted.THREE % (90, 47, 14), True) for key in ("rust", "rust-export")])
        r = self.check(ci, self.PRIVACY, rows + self.PRIVACY_ROW)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        wrong = rows.replace("rust\tplanted\t90\t0\t1", "rust\tplanted\t90\t0\t2")
        r = self.check(ci, self.PRIVACY, wrong + self.PRIVACY_ROW)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("derived row differs from its planted twin", r.stderr)

    # Bug (R2): a job declared with a quoted YAML key is left out of the
    # inventory, so it runs with GitHub's 360-minute default and no budget.
    def test_a_quoted_job_key_is_checked_and_other_declarations_refused(self):
        quoted = workflow([("always", 12, False)]) + '  "extra":\n    runs-on: ubuntu-24.04\n    steps:\n      - run: echo synthetic\n'
        r = self.check(quoted, self.PRIVACY, row("ci.yml", "always", "all", 12, 450) + self.PRIVACY_ROW)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("ci.yml job extra has no budget row", r.stderr)
        single = quoted.replace('"extra":', "'extra':")
        r = self.check(single, self.PRIVACY, row("ci.yml", "always", "all", 12, 450) + self.PRIVACY_ROW)
        self.assertIn("ci.yml job extra has no budget row", r.stderr)
        flow = workflow([("always", 12, False)]) + "  ? extra\n  : {runs-on: ubuntu-24.04}\n"
        r = self.check(flow, self.PRIVACY, row("ci.yml", "always", "all", 12, 450) + self.PRIVACY_ROW)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("ci.yml line 10: a job declaration budgets.py can't read", r.stderr)

    # The real workflows and table: the guard CI runs.
    def test_the_repository_workflows_match_their_table(self):
        r = run("check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class Table(unittest.TestCase):
    """CI3-B: the budgets are 1.5x each job's measured p95, from the collected runs."""

    def table(self, ci_jobs, ci_runs=150, fallback=None, ci=None, after=None, after_jobs=(), extra=()):
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
            if after is not None:
                window(t / "a", "ci.yml", after, 999)
                window(t / "a", "privacy.yml", [], 0)
                args += ["--after", t / "a", "--after-jobs", *after_jobs]
            args += ["--unmeasured", "rust:planted=60", "rust-export:planted=60", "always:planted=60"]
            r = run(*args, *extra)
            rows = {}
            if r.returncode == 0:
                lines = (t / "budgets.tsv").read_text().splitlines()
                self.assertEqual(lines[0] + "\n", HEAD)
                for line in lines[1:]:
                    f = line.split("\t")
                    rows[(f[0], f[1], f[2])] = f[3:]
            return r, rows

    def lanes(self):
        """20 normal runs: always 1..20 min; rust two legs; 5 traced runs."""
        jobs = []
        for i in range(1, 21):
            jobs.append(job(i, "always", 60 * i))
            jobs.append(job(i, "rust (1)", 300 + i))
            jobs.append(job(i, "rust (2)", 400 + i))
        for i in range(21, 26):
            jobs.append(job(i, "always", 120))
            jobs.append(job(i, "rust (1)", 1800 + i, traced=True))
        return jobs

    # Bug: p95, 1.5x, rounding or the 5-minute floor computed wrong; a
    # traced run's long single shard folded into the normal budget; the
    # slower matrix leg's p95 hidden by pooling with the faster one.
    def test_each_job_gets_one_and_a_half_times_its_p95_rounded_up(self):
        r, rows = self.table(self.lanes())
        self.assertEqual(r.returncode, 0, r.stderr)
        # always: 25 samples (20 normal + 5 traced, one mode); nearest-rank
        # p95 is the 24th of 25 sorted: 60, six 120 s, then 180..1200 s at
        # places 8..25, so the 24th is 1140 s; 1.5 x 1140 s = 28.5 min -> 29.
        self.assertEqual(rows[("ci.yml", "always", "all")][:4], ["29", "1140", "25", "150"])
        # rust normal: legs (1) 301..320 and (2) 401..420; leg (2)'s p95 is
        # its 19th, 419 s; 1.5 x 419 s = 10.475 min -> 11.
        self.assertEqual(rows[("ci.yml", "rust", "normal")][:4], ["11", "419", "40", "150"])
        # rust traced: 1821..1825 s; p95 of 5 is the 5th, 1825 s;
        # 1.5 x 1825 s = 45.625 min -> 46.
        self.assertEqual(rows[("ci.yml", "rust", "traced")][:4], ["46", "1825", "5", "150"])
        # privacy: 101..120 s; p95 119 s; 1.5 x 119 s = 2.975 min -> floor 5.
        self.assertEqual(rows[("privacy.yml", "privacy", "all")][:4], ["5", "119", "20", "20"])
        self.assertEqual(rows[("ci.yml", "always", "all")][4:], [T0, "2030-01-02T00:00:00Z", "measured"])

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
        self.assertEqual(rows[("ci.yml", "rust", "traced")][:3], ["60", "2400", "6"])

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
        # 1.5 x 1506 s = 37.65 min -> 38; the row names the 6 runs it came from.
        self.assertEqual(rows[("ci.yml", "rust", "traced")], ["38", "1506", "6", "6", stamp(3600), stamp(6 * 3600), "measured"])

    # Bug: a rare job's fallback reads the whole older window, or more than
    # its own last 150 runs, or counts runs in which it never ran.
    def test_the_fallback_reads_the_jobs_own_last_150_runs(self):
        few = [j for j in self.lanes() if j["run"] < 22]
        older = [job(i, "rust (1)", 1000 + i, traced=True) for i in range(1, 153)]
        older += [job(i, "always", 60) for i in range(200, 211)]
        r, rows = self.table(few, fallback=older)
        self.assertEqual(r.returncode, 0, r.stderr)
        # Its own last 150 runs are 3..152: 1003..1152 s; nearest-rank p95 is
        # the 143rd, 1145 s; 1.5 x 1145 s = 28.625 min -> 29.
        self.assertEqual(rows[("ci.yml", "rust", "traced")],
                         ["29", "1145", "150", "150", stamp(3 * 3600), stamp(152 * 3600), "measured"])

    # Bug: a job whose shape changed in #743 (release, launch-fleet, skills)
    # gets a budget from runs of its old shape, before the merges (#782 Q3).
    def test_a_shape_changed_job_reads_only_runs_after_the_merges(self):
        ci = workflow([("always", 60, False), ("rust", 60, True), ("release", 60, False)])
        jobs = self.lanes() + [job(i, "release (1)", 300) for i in (1, 2)]
        older = [job(i, "release", 3000) for i in range(1, 20)] + [job(i, "rust (1)", 1500, traced=True) for i in range(1, 7)]
        def shaped(i):  # a run of the current workflow lists every job, even skipped ones
            return [job(i, "always", 60), job(i, "rust (1)", 300)]
        after4 = [x for i in range(1, 5) for x in [job(i, "release (2)", 600 + i)] + shaped(i)]
        r, _ = self.table(jobs, ci=ci, fallback=older, after=after4, after_jobs=["release"])
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("ci.yml job release all has 4 samples, fewer than 5", r.stderr)
        # Run 7 was created after the merges but ran the old workflow: it has
        # no rust job, and its unsharded release took 3000 s (#782: two such runs).
        after6 = [x for i in range(1, 7) for x in [job(i, "release (2)", 600 + i)] + shaped(i)]
        after6 += [job(7, "release", 3000), job(7, "always", 60)]
        r, rows = self.table(jobs, ci=ci, fallback=older, after=after6, after_jobs=["release"])
        self.assertEqual(r.returncode, 0, r.stderr)
        # Never the older or old-shape 3000 s runs: 601..606 s, p95 of 6 is 606 s;
        # 1.5 x 606 s = 15.15 min -> 16, from those 6 runs.
        self.assertEqual(rows[("ci.yml", "release", "all")], ["16", "606", "6", "6", stamp(3600), stamp(6 * 3600), "measured"])

    # Bug: a job in the workflow that never ran in the window is silently
    # left without a row (the check would then fail later, in CI).
    def test_a_job_with_no_samples_fails(self):
        ci = workflow([("always", 60, False), ("rust", 60, True), ("slow-nightly", 360, False)])
        r, _ = self.table(self.lanes(), ci=ci)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("ci.yml job slow-nightly all has 0 samples, fewer than 5", r.stderr)


    # Bug: a job that never ran gets no row (the check stays red for good),
    # or its twin's budget is copied without saying so (#782 question 4).
    def test_derived_and_unmeasured_rows(self):
        ci = workflow([("always", 60, False), ("rust", 60, True), ("rust-export", 60, True),
                       ("slow-nightly", 360, False)])
        jobs = [j for j in self.lanes()] + [dict(j, name=j["name"].replace("rust", "rust-export"))
                                            for j in self.lanes() if j["name"].startswith("rust")]
        jobs = [j for j in jobs if not j["name"].startswith("rust (")] + [job(99, "slow-nightly", 7200, event="schedule")]
        r, rows = self.table(jobs, ci=ci, extra=["--derive", "rust=rust-export", "--unmeasured", "slow-nightly=360"])
        self.assertEqual(r.returncode, 0, r.stderr)
        # rust-export's numbers (the lanes' rust legs: 11 and 46, worked above), marked as derived.
        self.assertEqual(rows[("ci.yml", "rust", "normal")][:4] + rows[("ci.yml", "rust", "normal")][6:],
                         ["11", "419", "40", "150", "derived:rust-export"])
        self.assertEqual(rows[("ci.yml", "rust", "traced")][:4] + rows[("ci.yml", "rust", "traced")][6:],
                         ["46", "1825", "5", "150", "derived:rust-export"])
        self.assertEqual(rows[("ci.yml", "rust-export", "normal")][6:], ["measured"])
        # Unmeasured: today's 360, no p95, its one sample counted.
        self.assertEqual(rows[("ci.yml", "slow-nightly", "all")][:3] + rows[("ci.yml", "slow-nightly", "all")][6:],
                         ["360", "0", "1", "unmeasured"])


    # Bug: combined trace/planted uploads are guessed as traced, or a failed
    # lane loses mode evidence that another lane's persisted dispatch supplies.
    def test_actual_dispatch_survives_failed_lanes_and_ambiguous_uploads_stay_unknown(self):
        jobs = self.lanes()
        jobs.append(job(30, "rust (1)", 3000, conclusion="failure", traced=True))
        ambiguous = job(31, "rust (1)", 4000, traced=True)
        ambiguous.pop("_mode")
        jobs.append(ambiguous)
        r, rows = self.table(jobs)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(rows[("ci.yml", "rust", "traced")][:3], ["75", "3000", "6"])
        self.assertEqual(rows[("ci.yml", "rust", "normal")][:3], ["11", "419", "40"])
        self.assertIn("ci.yml: 1 run with no clear normal, traced or planted mode", r.stdout)


class Planted(unittest.TestCase):
    """CI3-B: exercise the public table/check CLI with independent mode evidence."""

    THREE = ("${{ needs.changes.outputs.planted == 'true' && %d || "
             "needs.changes.outputs.trace == 'true' && %d || %d }}")

    def fixtures(self, t):
        (t / "ci.yml").write_text(workflow([("rust", self.THREE % (90, 45, 15), True)]))
        jobs, modes = [], {}
        # Fixed independent durations: normal 600s, traced 1800s, planted 3600s.
        for i in range(1, 16):
            mode = "normal" if i <= 5 else "traced" if i <= 10 else "planted"
            jobs.append(job(i, "rust (1)", {"normal": 600, "traced": 1800, "planted": 3600}[mode],
                            traced=mode != "normal"))
            modes[str(i)] = {"attempt": 1, "trace": mode == "traced", "planted": mode == "planted",
                             "source": f"https://github.com/synthetic/repo/actions/runs/{i}/artifacts/{i}",
                             "completed_jobs": ["rust"]}
        window(t / "w", "ci.yml", jobs, 15)
        (t / "w/ci/modes.json").write_text(json.dumps(modes))
        return ["table", t / "w", "--out", t / "budgets.tsv", "--workflows", t / "ci.yml"]

    def test_three_modes_have_independent_durations(self):
        with tempfile.TemporaryDirectory() as temp:
            t = Path(temp)
            r = run(*self.fixtures(t))
            self.assertEqual(r.returncode, 0, r.stderr)
            rows = [line.split("\t") for line in (t / "budgets.tsv").read_text().splitlines()[1:]]
            self.assertEqual({f[2]: f[3:6] for f in rows},
                             {"normal": ["15", "600", "5"], "traced": ["45", "1800", "5"],
                              "planted": ["90", "3600", "5"]})
            self.assertEqual(run("check", "--table", t / "budgets.tsv", t / "ci.yml").returncode, 0)

    def test_check_refuses_missing_planted_coverage_even_with_legacy_timeout(self):
        with tempfile.TemporaryDirectory() as temp:
            t = Path(temp)
            (t / "ci.yml").write_text(workflow([("rust", LEGACY % (45, 15), True)]))
            (t / "budgets.tsv").write_text(HEAD + row("ci.yml", "rust", "normal", 15, 600)
                                           + row("ci.yml", "rust", "traced", 45, 1800))
            r = run("check", "--table", t / "budgets.tsv", t / "ci.yml")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("planted", r.stderr)

    def test_check_refuses_traced_samples_attributed_to_planted(self):
        with tempfile.TemporaryDirectory() as temp:
            t = Path(temp)
            args = self.fixtures(t)
            self.assertEqual(run(*args).returncode, 0)
            # Relabel the trace-only records as the planted row's provenance.
            evidence = t / "budgets.samples.json"
            samples = json.loads(evidence.read_text())
            for sample in samples:
                sample["planted"] = False
                sample["trace"] = True
            evidence.write_text(json.dumps(samples))
            r = run("check", "--table", t / "budgets.tsv", t / "ci.yml")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("planted evidence", r.stderr)

    def test_check_refuses_each_modes_wrong_timeout(self):
        with tempfile.TemporaryDirectory() as temp:
            t = Path(temp)
            self.assertEqual(run(*self.fixtures(t)).returncode, 0)
            for mode, values in (("planted", (45, 45, 15)), ("traced", (90, 90, 15)),
                                 ("normal", (90, 45, 45))):
                with self.subTest(mode=mode):
                    (t / "ci.yml").write_text(workflow([("rust", self.THREE % values, True)]))
                    r = run("check", "--table", t / "budgets.tsv", t / "ci.yml")
                    self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                    self.assertIn(f"{mode} timeout-minutes", r.stderr)

    # Bug: an incomplete planted attempt supplies a deceptively short p95,
    # or trace-only/unknown runs fill the planted sample minimum.
    def test_incomplete_or_unknown_planted_evidence_never_fills_the_minimum(self):
        with tempfile.TemporaryDirectory() as temp:
            t = Path(temp)
            args = self.fixtures(t)
            path = t / "w/ci/jobs.jsonl"
            records = [json.loads(line) for line in path.read_text().splitlines()]
            for record in records:
                if record["run"] == 15:
                    record["conclusion"] = "failure"
                    record["steps"][1]["conclusion"] = "failure"
                    record["steps"][2]["conclusion"] = "skipped"
            path.write_text("".join(json.dumps(r) + "\n" for r in records))
            r = run(*args)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("rust planted has 4 samples, fewer than 5", r.stderr)
            # Explicit attempt mismatch cannot be used as planted evidence.
            modes_path = t / "w/ci/modes.json"
            modes = json.loads(modes_path.read_text())
            modes["14"]["attempt"] = 2
            modes_path.write_text(json.dumps(modes))
            r = run(*args)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("rust planted has 3 samples, fewer than 5", r.stderr)
            self.assertIn("no clear normal, traced or planted mode", r.stdout)

    def test_planted_with_trace_flag_also_true_stays_planted(self):
        with tempfile.TemporaryDirectory() as temp:
            t = Path(temp)
            args = self.fixtures(t)
            path = t / "w/ci/modes.json"
            modes = json.loads(path.read_text())
            for i in range(11, 16):
                modes[str(i)]["trace"] = True
            path.write_text(json.dumps(modes))
            self.assertEqual(run(*args).returncode, 0)
            rows = (t / "budgets.tsv").read_text()
            self.assertIn("rust\tplanted\t90\t3600\t5", rows)
            self.assertIn("rust\ttraced\t45\t1800\t5", rows)


class Apply(unittest.TestCase):
    # Bug: setting timeouts by hand edits other lines of a shared workflow.
    def test_apply_changes_only_timeout_lines(self):
        with tempfile.TemporaryDirectory() as temp:
            t = Path(temp)
            before = workflow([("always", 60, False), ("rust", Planted.THREE % (60, 90, 60), True)])
            (t / "ci.yml").write_text(before)
            (t / "privacy.yml").write_text(workflow([("privacy", 5, False)]))
            (t / "budgets.tsv").write_text(HEAD + row("ci.yml", "always", "all", 12, 450)
                                           + row("ci.yml", "rust", "normal", 14, 540)
                                           + row("ci.yml", "rust", "traced", 47, 1860)
                                           + row("ci.yml", "rust", "planted", 60, 0, samples=0, source="unmeasured")
                                           + row("privacy.yml", "privacy", "all", 5, 120))
            r = run("apply", "--table", t / "budgets.tsv", t / "ci.yml", t / "privacy.yml")
            self.assertEqual(r.returncode, 0, r.stderr)
            after = (t / "ci.yml").read_text()
            expected = before.replace("timeout-minutes: 60\n", "timeout-minutes: 12\n").replace(
                Planted.THREE % (60, 90, 60), Planted.THREE % (60, 47, 14))
            self.assertEqual(after, expected)
            self.assertEqual(run("check", "--table", t / "budgets.tsv", t / "ci.yml", t / "privacy.yml").returncode, 0)


FAKE_GH = """#!/usr/bin/env python3
import base64, json, os, sys
world = json.load(open(os.environ["FAKE_GH_WORLD"]))
path = sys.argv[2]
with open(os.environ["FAKE_GH_LOG"], "a") as log:
    log.write(" ".join(sys.argv[1:]) + "\\n")
if sys.argv[1] != "api" or len(sys.argv) != 3 or path not in world:
    sys.stderr.write("fake gh: no answer for " + " ".join(sys.argv[1:]) + "\\n")
    sys.exit(1)
if isinstance(world[path], dict) and "zip_base64" in world[path]:
    sys.stdout.buffer.write(base64.b64decode(world[path]["zip_base64"]))
else:
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
            plan = json.dumps({"schema": "openwiz.ci-selection.v1", "run": {"id": i, "attempt": 2}}).encode()
            dispatch = {"trace": i == 4, "planted": i == 5, "plan_sha256": hashlib.sha256(plan).hexdigest()}
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("ci-selection.json", plan)
                z.writestr("ci-dispatch.json", json.dumps(dispatch))
            world[f"{base}/runs/{i}/artifacts?per_page=100&page=1"] = {"total_count": 1, "artifacts": [
                {"id": i, "name": "ci-selection-2", "expired": False, "archive_download_url": f"synthetic-artifact-{i}"}]}
            world[f"{base}/artifacts/{i}/zip"] = {"zip_base64": base64.b64encode(archive.getvalue()).decode()}
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
            modes = json.loads((t / "w/ci/modes.json").read_text())
            self.assertEqual({r: (m["trace"], m["planted"]) for r, m in modes.items()},
                             {"4": (True, False), "5": (False, True)})
            self.assertNotIn("runs/3/", (t / "log").read_text())
            # Missing artifacts and stale/mismatched plan bindings stay unknown.
            for bad in ("missing", "hash", "attempt"):
                with self.subTest(evidence=bad):
                    broken = json.loads(json.dumps(world))
                    if bad == "missing":
                        broken[f"{base}/runs/5/artifacts?per_page=100&page=1"] = {"total_count": 0, "artifacts": []}
                    else:
                        plan = json.dumps({"schema": "openwiz.ci-selection.v1",
                                           "run": {"id": 5, "attempt": 1 if bad == "attempt" else 2}}).encode()
                        dispatch = {"trace": False, "planted": True,
                                    "plan_sha256": "wrong" if bad == "hash" else hashlib.sha256(plan).hexdigest()}
                        archive = io.BytesIO()
                        with zipfile.ZipFile(archive, "w") as z:
                            z.writestr("ci-selection.json", plan)
                            z.writestr("ci-dispatch.json", json.dumps(dispatch))
                        broken[f"{base}/artifacts/5/zip"] = {"zip_base64": base64.b64encode(archive.getvalue()).decode()}
                    (t / "world.json").write_text(json.dumps(broken))
                    r = run("collect", "--workflow", "ci.yml", "--runs", 2, "--per-page", 2, "--since", T0,
                            "--out", t / "w", env=env)
                    self.assertEqual(r.returncode, 0, r.stderr)
                    mode = json.loads((t / "w/ci/modes.json").read_text())["5"]
                    self.assertEqual(mode["source"], "unknown")
                    self.assertNotIn("planted", mode)



if __name__ == "__main__":
    unittest.main()
