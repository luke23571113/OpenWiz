#!/usr/bin/env python3
"""The first-fleet bench on fixture runs: python3 -I tools/bench/first-fleet/test_bench.py"""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
BENCH = HERE / 'bench.py'
FIXTURES = HERE / 'fixtures'


def bench(*args):
    return subprocess.run([sys.executable, '-I', str(BENCH), *map(str, args)],
                          capture_output=True, text=True, timeout=30)


class Report(unittest.TestCase):
    # catches: a wrong start offset, step length, waits column, GitHub row or total.
    def test_merged_run_prints_the_exact_table_and_total(self):
        r = bench('report', FIXTURES / 'merged')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, (FIXTURES / 'merged' / 'expected.txt').read_text())

    # catches: --json drifting from the table (another total, offsets or rows).
    def test_merged_run_json_is_the_same_table(self):
        r = bench('report', FIXTURES / 'merged', '--json')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout),
                         json.loads((FIXTURES / 'merged' / 'expected.json').read_text()))

    # catches: a timer wait that goes unflagged.
    def test_timer_waits_are_flagged(self):
        r = bench('report', FIXTURES / 'timer')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, (FIXTURES / 'timer' / 'expected.txt').read_text())
        j = json.loads(bench('report', FIXTURES / 'timer', '--json').stdout)
        self.assertEqual(j['timer_waits'], ['build', 'review', 'merge'])
        self.assertEqual(j['total_seconds'], 1570)

    # catches: a total invented from an open pull request or a missing merge time.
    def test_unmerged_run_reports_no_total_and_why(self):
        r = bench('report', FIXTURES / 'unmerged')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, (FIXTURES / 'unmerged' / 'expected.txt').read_text())
        j = json.loads(bench('report', FIXTURES / 'unmerged', '--json').stdout)
        self.assertIsNone(j['total_seconds'])
        self.assertIsNone(j['stop'])
        self.assertEqual(j['no_total_reason'], 'no fleet pull request has merged')
        self.assertIsNone(j['steps'][-1]['length_seconds'])


class Broken(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.run_dir = self.tmp / 'run'
        shutil.copytree(FIXTURES / 'merged', self.run_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def refused(self, name, text, where):
        (self.run_dir / name).write_text(text)
        for args in ((), ('--json',)):
            r = bench('report', self.run_dir, *args)
            self.assertNotEqual(r.returncode, 0, r.stdout)
            self.assertEqual(r.stdout, '')
            self.assertIn(f'{name} line {where}:', r.stderr)

    # catches: a bad step log line skipped or reported without its line.
    def test_a_malformed_step_log_names_the_bad_line(self):
        good = '{"at": "2026-11-22T10:01:00Z", "step": "install", "waits_on": "agent"}\n'
        for bad in ('not json',
                    '{"at": "2026-11-22T10:02:00Z", "step": "deploy", "waits_on": "agent"}',
                    '{"at": "2026-11-22T10:02:00Z", "step": "grill", "waits_on": "nobody"}',
                    '{"at": "yesterday", "step": "grill", "waits_on": "user"}',
                    '{"at": "2026-11-22T10:02:00", "step": "grill", "waits_on": "user"}',
                    '{"at": "2026-11-22T10:00:00Z", "step": "grill", "waits_on": "user"}',
                    '{"at": "2026-11-22T10:02:00Z", "step": "grill", "waits_on": "user", "failure": 3}',
                    '{"at": "2026-11-22T10:02:00Z", "step": "grill", "waits_on": "user", "failure": ""}',
                    '{"at": "2026-11-22T10:02:00Z", "step": "grill", "waits_on": "user", "note": "x"}',
                    '{"at": "2026-11-22T10:02:00Z", "step": "grill", "step": "plan", "waits_on": "user"}',
                    '{"at": "2026-11-22T10:02:00Z", "waits_on": "user"}',
                    '["grill"]'):
            with self.subTest(bad=bad):
                self.refused('steps.jsonl', good + bad + '\n', 2)

    # catches: bad GitHub JSON read as missing data, or reported without its line.
    def test_malformed_github_json_names_the_bad_line(self):
        prs = (FIXTURES / 'merged' / 'prs.json').read_text()
        cases = (
            ('prs.json', prs.replace('"2026-11-22T10:18:00Z"', '"yesterday"'), 8),
            ('prs.json', prs.replace('"number": 11', '"number": "11"'), 2),
            ('prs.json', prs.replace('[{"number": 13}]', '"13"'), 8),
            ('prs.json', prs.replace('"number": 22', '"number": 22, "title": "x"'), 8),
            ('prs.json', prs.replace('"number": 22', '"number": 22, "number": 23'), 8),
            ('tickets.json', '{"createdAt":"2026-11-22T10:08:50Z","number":12}\n{"createdAt":\n', 3),
            ('tickets.json', '{"createdAt":"2026-11-22T10:08:50Z","number":12}\n{"number":13}\n', 2),
            ('spec.json', '{"createdAt":"2026-11-22T10:08:30Z"}\n', 1),
            ('spec.json', '[]\n', 1),
        )
        for name, text, where in cases:
            with self.subTest(name=name, where=where):
                shutil.copy(FIXTURES / 'merged' / name, self.run_dir / name)
                self.refused(name, text, where)

    # catches: a missing input taken as an empty run.
    def test_a_missing_input_is_refused(self):
        (self.run_dir / 'prs.json').unlink()
        r = bench('report', self.run_dir)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('prs.json', r.stderr)


class Mark(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    # catches: mark writing a line report cannot read, or overwriting the log.
    def test_mark_appends_one_timed_line_per_step(self):
        run_dir = self.tmp / 'run'
        for args in (('install', 'agent', '--at', '2026-11-22T10:01:00Z'),
                     ('connect', 'user', '--failure', 'gh lacked a scope', '--at', '2026-11-22T10:03:30+00:00'),
                     ('grill', 'user')):
            r = bench('mark', run_dir, *args)
            self.assertEqual(r.returncode, 0, r.stderr)
        lines = [json.loads(l) for l in (run_dir / 'steps.jsonl').read_text().splitlines()]
        self.assertEqual(lines[:2], [
            {'at': '2026-11-22T10:01:00Z', 'step': 'install', 'waits_on': 'agent'},
            {'at': '2026-11-22T10:03:30Z', 'step': 'connect', 'waits_on': 'user', 'failure': 'gh lacked a scope'},
        ])
        self.assertEqual(sorted(lines[2]), ['at', 'step', 'waits_on'])
        self.assertRegex(lines[2]['at'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$')
        for name in ('spec.json', 'tickets.json', 'prs.json'):
            shutil.copy(FIXTURES / 'unmerged' / name, run_dir / name)
        j = json.loads(bench('report', run_dir, '--json').stdout)
        self.assertEqual([s['step'] for s in j['steps']], ['install', 'connect', 'grill'])
        self.assertEqual(j['steps'][0]['length_seconds'], 150)

    # catches: mark accepting a step or wait the report would then refuse.
    def test_mark_refuses_an_unknown_step_or_wait(self):
        run_dir = self.tmp / 'run'
        for args in (('deploy', 'agent'), ('grill', 'nobody'), ('grill', 'user', '--at', 'soon')):
            with self.subTest(args=args):
                r = bench('mark', run_dir, *args)
                self.assertNotEqual(r.returncode, 0)
                self.assertFalse((run_dir / 'steps.jsonl').exists())


if __name__ == '__main__':
    unittest.main()
