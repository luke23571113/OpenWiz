#!/usr/bin/env python3
"""#2882: supply.py imports from a clean checkout and writes the guard's observation from a fixture.

Every test puts only a fake `gh` on PATH, so no real gh, agent or host CLI can run."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REPO = 'synthetic-owner/synthetic-repo'
BASE = f'repos/{REPO}/actions'
STATUSES = ('requested', 'waiting', 'pending', 'queued', 'in_progress')
FAKE_GH = '''import json, sys
answers = json.load(open(sys.argv[0] + '.json'))
if sys.argv[1:2] != ['api'] or len(sys.argv) != 3 or sys.argv[2] not in answers:
    print('gh: HTTP 404: Not Found (synthetic)', file=sys.stderr)
    sys.exit(1)
print(json.dumps(answers[sys.argv[2]]))
'''


def job(jid, run, status, created, started=None, attempt=1):
    return {'id': jid, 'run_id': run, 'run_attempt': attempt, 'status': status, 'created_at': created,
            'started_at': started, 'labels': ['ubuntu-24.04']}


def answers():
    """Three active runs: a pull_request ci.yml run, a merge_group privacy.yml run and a push ci.yml run."""
    got = {}
    for workflow in ('ci.yml', 'privacy.yml'):
        for status in STATUSES:
            got[f'{BASE}/workflows/{workflow}/runs?status={status}&per_page=100&page=1'] = {
                'total_count': 0, 'workflow_runs': []}
    runs = {('ci.yml', 'in_progress'): [{'id': 7101, 'run_attempt': 1, 'event': 'pull_request'},
                                        {'id': 7103, 'run_attempt': 1, 'event': 'push'}],
            ('privacy.yml', 'in_progress'): [{'id': 7102, 'run_attempt': 2, 'event': 'merge_group'}]}
    for (workflow, status), listed in runs.items():
        got[f'{BASE}/workflows/{workflow}/runs?status={status}&per_page=100&page=1'] = {
            'total_count': len(listed), 'workflow_runs': listed}
    jobs = {7101: [job(8101, 7101, 'in_progress', '2026-01-05T12:00:00Z', '2026-01-05T12:00:10Z'),
                   job(8102, 7101, 'completed', '2026-01-05T12:00:00Z', '2026-01-05T12:00:05Z')],
            7102: [job(8201, 7102, 'in_progress', '2026-01-05T12:01:00Z', '2026-01-05T12:01:30Z', attempt=2)],
            7103: [job(8301, 7103, 'queued', '2026-01-05T11:00:00Z')]}
    for rid, listed in jobs.items():
        got[f'{BASE}/runs/{rid}/jobs?per_page=100&page=1'] = {'total_count': len(listed), 'jobs': listed}
    got['rate_limit'] = {'resources': {pool: {'limit': 5000, 'remaining': 4000, 'reset': 1767618000, 'used': 1000}
                                       for pool in ('core', 'graphql', 'search')}}
    return got


class Supply(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        fake = self.bin / 'gh'
        fake.write_text(f'#!{sys.executable} -I\n' + FAKE_GH)
        fake.chmod(0o755)
        self.output = self.root / 'private' / 'observation.json'
        self.output.parent.mkdir()
        self.tool = self.clean_copy()

    def clean_copy(self):
        """The tracked files of tools/ci-overload alone, as a clean checkout has them, with no other tool beside."""
        listed = subprocess.run(['git', 'ls-files', '-z', '--', 'tools/ci-overload'], cwd=ROOT,
                                capture_output=True, check=True).stdout.decode().split('\0')
        for name in filter(None, listed):
            target = self.root / 'checkout' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        return self.root / 'checkout/tools/ci-overload'

    def supply(self, answered, supplier=None):
        (self.bin / 'gh.json').write_text(json.dumps(answered))
        env = {'PATH': str(self.bin), 'HOME': str(self.root), 'LANG': 'C.UTF-8'}
        return subprocess.run([sys.executable, '-I', str(supplier or self.tool / 'supply.py'), '--repository', REPO,
                               '--output', str(self.output)], env=env, capture_output=True, text=True, timeout=60)

    def guard(self, observed):
        state = self.root / 'private' / 'pause.json'
        result = subprocess.run([sys.executable, '-I', str(self.tool / 'alarm.py'), '--repository', REPO,
                                 '--input', str(self.output), '--state', str(state), '--now', str(observed),
                                 '--action', 'merge-batch'], capture_output=True, text=True, timeout=60)
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return json.loads(result.stdout)

    def written(self, answered):
        before = int(time.time())
        result = self.supply(answered)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '', ''))
        observation = json.loads(self.output.read_text())
        self.assertTrue(before <= observation['observed_at'] <= int(time.time()))
        return observation

    def test_a_clean_checkout_supplies_a_complete_observation_the_guard_admits(self):
        # catches: supply.py importing a reader outside tools/ci-overload (the deleted tools/collector), so every
        # fleet's guard pauses on a missing input; or a reader that marks a push run's queued job required.
        observation = self.written(answers())
        self.assertEqual(sorted(observation), ['budgets', 'complete', 'observed_at', 'queue', 'repository'])
        self.assertEqual((observation['repository'], observation['complete'], observation['queue']['complete']),
                         (REPO, True, True))
        jobs = {j['id']: j for j in observation['queue']['jobs']}
        self.assertEqual(sorted(jobs), ['job-8101', 'job-8102', 'job-8201', 'job-8301'])
        self.assertEqual([jobs[j]['required'] for j in sorted(jobs)], [True, True, True, False])
        self.assertEqual(jobs['job-8301']['status'], 'queued')
        self.assertIsNone(jobs['job-8301']['started_at'])
        self.assertEqual(observation['budgets']['rest'],
                         {'remaining': 4000, 'limit': 5000, 'reset_at': 1767618000, 'retry_after': 0})
        answer = self.guard(observation['observed_at'])
        self.assertEqual((answer['level'], answer['allowed'], answer['paused']), ('healthy', True, False))

    def test_an_unestablished_page_run_or_attempt_writes_complete_false(self):
        # catches: a reader that keeps the first page, skips a run it couldn't read or counts an older attempt's
        # job, and so hands the guard a complete observation that admits new work.
        def missing_page(answered):
            answered[f'{BASE}/runs/7102/jobs?per_page=100&page=1']['total_count'] = 101

        def older_attempt(answered):
            answered[f'{BASE}/runs/7102/jobs?per_page=100&page=1']['jobs'][0]['run_attempt'] = 1

        def unknown_status(answered):
            answered[f'{BASE}/runs/7101/jobs?per_page=100&page=1']['jobs'][1]['status'] = 'synthetic_state'

        for case in (missing_page, older_attempt, unknown_status):
            with self.subTest(case=case.__name__):
                answered = answers()
                case(answered)
                observation = self.written(answered)
                self.assertEqual((observation['complete'], observation['queue']['complete']), (False, False))
                (self.root / 'private' / 'pause.json').unlink(missing_ok=True)
                answer = self.guard(observation['observed_at'])
                self.assertEqual((answer['level'], answer['allowed']), ('unknown', False))

    def test_a_partial_read_keeps_its_known_exhaustion(self):
        # catches: a supplier that drops an incomplete observation, losing an exhausted pool it did read.
        answered = answers()
        del answered[f'{BASE}/runs/7103/jobs?per_page=100&page=1']
        answered['rate_limit']['resources']['core']['remaining'] = 0
        answer = self.guard(self.written(answered)['observed_at'])
        self.assertEqual((answer['level'], answer['allowed'], answer['escalation']), ('escalate', False, 'due_not_sent'))
        self.assertEqual(sorted(answer['causes']), ['observation_unknown', 'rest_exhausted'])

    def test_a_failing_reader_exits_1_and_writes_nothing(self):
        # catches: a supplier that writes an empty or healthy observation, or leaves the previous one in place,
        # when it can't read the budgets or a run listing, or can't import its reader at all.
        lone = self.root / 'lone'
        lone.mkdir()
        shutil.copyfile(self.tool / 'supply.py', lone / 'supply.py')
        no_budgets = answers()
        del no_budgets['rate_limit']
        no_runs = answers()
        del no_runs[f'{BASE}/workflows/privacy.yml/runs?status=queued&per_page=100&page=1']
        cases = (('no budgets', no_budgets, None, 'supply: the queue read failed\n'),
                 ('no run listing', no_runs, None, 'supply: the queue read failed\n'),
                 ('no reader', answers(), lone / 'supply.py', 'supply: the queue reader could not be imported\n'))
        for case, answered, supplier, line in cases:
            with self.subTest(case=case):
                shutil.copyfile(self.tool / 'fixtures/healthy.json', self.output)
                result = self.supply(answered, supplier)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (1, '', line))
                self.assertFalse(self.output.exists())
                self.assertEqual(sorted(os.listdir(self.output.parent)), [])


if __name__ == '__main__':
    unittest.main()
