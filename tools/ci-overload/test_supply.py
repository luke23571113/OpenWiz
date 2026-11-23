#!/usr/bin/env python3
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
RESET = int(time.time()) + 3600
STATUSES = ('requested', 'waiting', 'pending', 'queued', 'in_progress')
FAKE_GH = '''import json, sys
answers = json.load(open(sys.argv[0] + '.json'))
args = [a for a in sys.argv[1:] if a != '--include']
if args[:2] == ['api', 'graphql'] and len(args) == 4 and args[2] == '-f' and args[3].startswith('query='):
    key = 'graphql'
else:
    key = args[1] if args[:1] == ['api'] and len(args) == 2 else None
if key not in answers:
    print('gh: Not Found (HTTP 404)', file=sys.stderr)
    sys.exit(1)
got = answers[key]
response = got['gh'] if type(got) is dict and 'gh' in got else {'body': got}
if 'raw' in response:
    sys.stdout.write(response['raw'])
    sys.exit(0)
status = response.get('status', 200)
headers = {'X-Ratelimit-Resource': 'graphql' if key == 'graphql' else 'core', 'X-Ratelimit-Remaining': '4000'}
headers.update(response.get('headers', {}))
if '--include' in sys.argv:
    sys.stdout.write('HTTP/2.0 %d %s\\n' % (status, 'OK' if status < 400 else 'Error'))
    sys.stdout.write(''.join('%s: %s\\r\\n' % item for item in sorted(headers.items())) + '\\r\\n')
sys.stdout.write(json.dumps(response['body']))
if status >= 400:
    print('gh: synthetic error (HTTP %d)' % status, file=sys.stderr)
    sys.exit(1)
'''


def job(jid, run, status, created, started=None, attempt=1):
    return {'id': jid, 'run_id': run, 'run_attempt': attempt, 'status': status, 'created_at': created,
            'started_at': started, 'labels': ['ubuntu-24.04']}


def answers():
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
    got['graphql'] = {'data': {'rateLimit': {'remaining': 4000}}}
    got['rate_limit'] = {'resources': {pool: {'limit': 5000, 'remaining': 4000, 'reset': RESET, 'used': 1000}
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

    def guard(self, observed=None):
        state = self.root / 'private' / 'pause.json'
        now = [] if observed is None else ['--now', str(observed)]
        result = subprocess.run([sys.executable, '-I', str(self.tool / 'alarm.py'), '--repository', REPO,
                                 '--input', str(self.output), '--state', str(state), *now,
                                 '--action', 'merge-batch'], capture_output=True, text=True, timeout=60)
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return json.loads(result.stdout)

    def written(self, answered):
        result = self.supply(answered)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '', ''))
        observation = json.loads(self.output.read_text())
        self.assertIs(type(observation['observed_at']), int)
        return observation

    def test_a_clean_checkout_supplies_a_complete_observation_the_guard_admits(self):
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
                         {'remaining': 4000, 'limit': 5000, 'reset_at': RESET, 'retry_after': 0})
        answer = self.guard()
        self.assertEqual((answer['level'], answer['allowed'], answer['paused']), ('healthy', True, False))

    def test_an_unestablished_page_run_or_attempt_writes_complete_false(self):
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
        answered = answers()
        del answered[f'{BASE}/runs/7103/jobs?per_page=100&page=1']
        answered['rate_limit']['resources']['core']['remaining'] = 0
        answer = self.guard(self.written(answered)['observed_at'])
        self.assertEqual((answer['level'], answer['allowed'], answer['escalation']),
                         ('escalate', False, 'due_not_sent'))
        self.assertEqual(sorted(answer['causes']), ['observation_unknown', 'rest_exhausted'])

    def test_a_failing_reader_exits_1_and_writes_nothing(self):
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

    def test_no_backoff_signal_gives_retry_after_0_and_a_complete_observation(self):
        observation = self.written(answers())
        self.assertEqual((observation['complete'], observation['queue']['complete']), (True, True))
        self.assertEqual([observation['budgets'][pool]['retry_after'] for pool in ('rest', 'graphql')], [0, 0])

    def test_a_backoff_signal_gives_its_real_wait(self):
        secondary = {'message': 'You have exceeded a secondary rate limit. Please wait a few minutes.'}
        page = f'{BASE}/runs/7102/jobs?per_page=100&page=1'
        listing = f'{BASE}/workflows/ci.yml/runs?status=queued&per_page=100&page=1'
        limited = {'errors': [{'type': 'RATE_LIMITED', 'message': 'API rate limit exceeded'}]}
        cases = (('retry-after on a 403', page, {'status': 403, 'headers': {'Retry-After': '120'}, 'body': secondary},
                  'rest', 120),
                 ('a secondary 403 with no retry-after', page, {'status': 403, 'body': secondary}, 'rest', 60),
                 ('a 429 on a run listing', listing,
                  {'status': 429, 'headers': {'Retry-After': '90'}, 'body': {'message': 'Too many requests'}},
                  'rest', 90),
                 ('graphql rate limited', 'graphql', {'headers': {'Retry-After': '45'}, 'body': limited},
                  'graphql', 45))
        for case, path, response, pool, wait in cases:
            with self.subTest(case=case):
                answered = answers()
                answered[path] = {'gh': response}
                observation = self.written(answered)
                budgets = observation['budgets']
                self.assertIn(budgets[pool]['retry_after'] - observation['observed_at'], range(wait - 5, wait + 1))
                self.assertEqual(budgets['graphql' if pool == 'rest' else 'rest']['retry_after'], 0)
                self.assertEqual(observation['complete'], False)
                (self.root / 'private' / 'pause.json').unlink(missing_ok=True)
                answer = self.guard()
                self.assertEqual((answer['level'], answer['allowed']), ('alarm', False))
                self.assertEqual(sorted(answer['causes']), sorted([pool + '_backoff', 'observation_unknown']))

    def test_an_unknown_backoff_writes_complete_false(self):
        page = f'{BASE}/runs/7101/jobs?per_page=100&page=1'
        cases = (('no header block', page, lambda body: {'raw': json.dumps(body)}),
                 ('a retry-after that is not seconds', page,
                  lambda body: {'headers': {'Retry-After': 'Wed, 21 Oct 2026 07:28:00 GMT'}, 'body': body}),
                 ('graphql unreadable', 'graphql', lambda body: {'status': 502, 'body': {'message': 'Server Error'}}),
                 ('graphql errors', 'graphql',
                  lambda body: {'body': {'errors': [{'type': 'INTERNAL', 'message': 'x'}]}}))
        for case, path, response in cases:
            with self.subTest(case=case):
                answered = answers()
                answered[path] = {'gh': response(answered[path])}
                observation = self.written(answered)
                self.assertEqual((observation['complete'], observation['queue']['complete']), (False, False))
                (self.root / 'private' / 'pause.json').unlink(missing_ok=True)
                answer = self.guard()
                self.assertEqual((answer['level'], answer['allowed']), ('unknown', False))


if __name__ == '__main__':
    unittest.main()
