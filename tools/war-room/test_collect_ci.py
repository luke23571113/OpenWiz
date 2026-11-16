#!/usr/bin/env python3
"""MT3 (#822): the collector's CI facts, through its CLI, on a synthetic gh.

fixtures/collector-ci/github.json answers every read; its README works each
expected number by hand. The CI facts are compared red first with what
ci-bench and CI3 print for the same answers, and the queue with what the
overload guard decides. Each test names the bug it catches.
"""
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIX = HERE / 'fixtures' / 'collector-ci'
REPO = 'synthetic-owner/synthetic-repo'
R = 'repos/' + REPO
CI3 = ROOT / 'tools/war-room/ci3.py'
# ci-bench's `collect` and `measure` commands, now bench_measure.py's functions (#827), run as the CLI ran them.
BENCH = ['-c', 'import sys; sys.path.insert(0, sys.argv.pop(1)); import bench_measure as B; a = sys.argv[1:]; '
         '(B.collect(a[2], a[4], a[6]) if a[0] == "collect" else '
         'B.measure(a[1], int(a[3]), a[5], allow_empty=True, allow_timing_gaps=True))', str(ROOT / 'tools/war-room')]
GUARD = ROOT / 'tools/ci-overload/alarm.py'
RUNS_WINDOW = ('--since', '2026-01-04T00:00:00Z', '--until', '2026-01-04T01:00:00Z')
CI3_WINDOW = ('--since', '2026-01-05T00:00:00Z', '--until', '2026-01-06T00:00:00Z')
sys.path.insert(0, str(HERE))
import suite  # noqa: E402

SCHEMA = json.loads((HERE / 'collector.v1.schema.json').read_text(encoding='utf-8'))


def unix(text):
    return int(datetime.strptime(text, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).timestamp())


class Fake:
    """A private copy of the synthetic answers, the fake gh on PATH, and the log of every path asked."""

    def __init__(self, tmp):
        self.tmp = Path(tmp)
        self.answers = json.loads((FIX / 'github.json').read_text(encoding='utf-8'))
        (self.tmp / 'bin').mkdir()
        (self.tmp / 'bin' / 'gh').symlink_to(FIX / 'fake_gh.py')
        self.log = self.tmp / 'gh.log'
        self.store = self.tmp / 'store'

    def put(self, key, answer):
        """Answer `key` first, ahead of every other answer."""
        self.drop(key)
        self.answers.insert(0, [key, answer])

    def answer(self, key):
        return next(a for k, a in self.answers if k == key)

    def drop(self, key):
        self.answers = [[k, a] for k, a in self.answers if k != key]

    def env(self, **extra):
        (self.tmp / 'github.json').write_text(json.dumps(self.answers), encoding='utf-8')
        env = dict(os.environ, PATH=str(self.tmp / 'bin') + os.pathsep + os.environ['PATH'],
                   COLLECTOR_CI_FIXTURE=str(self.tmp / 'github.json'), COLLECTOR_CI_LOG=str(self.log),
                   OPENWIZ_COLLECTOR_STORE=str(self.store))
        env.pop('GH_REPO', None)
        env.update(extra)
        return env

    def asked(self):
        return self.log.read_text(encoding='utf-8').splitlines() if self.log.exists() else []

    def run(self, *args, env=None):
        return subprocess.run([sys.executable, '-I', *map(str, args)], capture_output=True, text=True,
                              env=env or self.env(), cwd=self.tmp, timeout=60)

    def collect(self, *facts, window=()):
        """The collector's read envelope; it must exit 0 and conform to the contract's schema."""
        args = [HERE / 'collect_ci.py', 'read', '--repo', REPO, *[a for f in facts for a in ('--fact', f)], *window]
        done = self.run(*args)
        assert done.returncode == 0, done.stderr
        envelope = json.loads(done.stdout)
        suite._shape(envelope, SCHEMA['$defs']['read_envelope'], SCHEMA)
        assert list(envelope['ci']) == list(facts) and envelope['factory'] == {}
        return envelope['ci']

    def bench_point(self):
        """ci-bench's own collect and measure of the same window, as daily.sh runs them."""
        env, out = self.env(GH_REPO=REPO), self.tmp / 'bench'
        for args in (('collect', *RUNS_WINDOW, '--out', out),
                     ('measure', out, '--robots', '5', '--label', 'x', '--allow-empty', '--allow-timing-gaps')):
            done = self.run(*BENCH, *args, env=env)
            assert done.returncode == 0, done.stderr
        return json.loads((out / 'point.json').read_text(encoding='utf-8'))

    def ci3_record(self):
        """CI3's own collect and measure of the same window."""
        env, out = self.env(GH_REPO=REPO), self.tmp / 'ci3.json'
        done = self.run(CI3, 'collect', *CI3_WINDOW, '--out', out, env=env)
        assert done.returncode == 0, done.stderr
        done = self.run(CI3, 'measure', out, env=env)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)

    def guard(self, observation, now):
        """The overload guard's decision on the observation, unchanged, with a fresh private state."""
        path, state = self.tmp / 'observation.json', self.tmp / ('state-%d.json' % now)
        path.write_text(json.dumps(observation), encoding='utf-8')
        done = self.run(GUARD, '--repository', REPO, '--input', path, '--state', state, '--action', 'merge-batch',
                        '--now', now)
        return done.returncode, json.loads(done.stdout)


def by_kind(minutes):
    return {row['runner_kind']: row['minutes'] for row in minutes}


class RunsAndMinutes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fake = Fake(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_runs_and_minutes_are_ci_bench_s_numbers(self):
        # catches: the collector's runs or minutes drifting from ci-bench's on the same answers: run 505,
        # created at the window's end, counted; latency timed over every run instead of the code runs;
        # minutes from another rounding or price table.
        point = self.fake.bench_point()
        ci = self.fake.collect('runs', 'minutes', window=RUNS_WINDOW)
        runs, minutes = ci['runs'], ci['minutes']
        self.assertEqual((runs['state'], minutes['state']), ('known', 'known'))
        # The README's worked values, then ci-bench's point for the same window.
        self.assertEqual(runs['value'], {'workflow': 'ci.yml', 'runs': 3, 'jobs': 4, 'unknown_jobs': 0, 'code_runs': 2,
                                         'latency_basis': 'workflow created to last job completed',
                                         'queued_to_done_minutes': {'median': 8.75, 'p90': 10.0, 'max': 10.0}})
        self.assertEqual((runs['value']['runs'], runs['value']['jobs'], runs['value']['code_runs'],
                          runs['value']['queued_to_done_minutes']),
                         (point['runs'], point['jobs'], point['code_runs']['runs'], point['code_runs']['queued_to_done']))
        m = minutes['value']
        self.assertEqual((by_kind(m['runner_minutes']), by_kind(m['billed_minutes'])),
                         ({'github-hosted': 17.8333, 'self-hosted': 4.0}, {'github-hosted': 19, 'self-hosted': 4}))
        self.assertEqual((m['window_usd'], m['per_code_run_usd'], m['unknown_minutes']), (0.114, 0.048, 0))
        cost = point['cost']
        self.assertEqual((by_kind(m['runner_minutes']), by_kind(m['billed_minutes']), m['window_usd'],
                          m['per_code_run_usd'], m['unknown_minutes'], m['prices']),
                         (cost['runner_minutes'], cost['billed_minutes'], cost['window_usd'], cost['per_code_run_usd'],
                          cost['unknown_minutes'], cost['prices']))
        self.assertEqual(runs['evidence'], ['https://github.com/%s/actions/runs/%d' % (REPO, n) for n in (501, 502, 503)])
        self.assertEqual(runs['window'], {'since': '2026-01-04T00:00:00Z', 'until': '2026-01-04T01:00:00Z',
                                          'timezone': 'UTC'})
        # Every read is a GET of the named repository, never of the checkout's own.
        self.assertTrue(self.fake.asked() and all(p.startswith(R + '/') for p in self.fake.asked()))

    def test_an_unpriced_job_keeps_its_minutes_and_leaves_the_totals_unknown(self):
        # catches: a job on a runner with no known price costed as $0 (a known, too-low total), or its
        # minutes dropped, instead of known minutes kept and a partial fact with unknown totals.
        job = self.fake.answer(R + '/actions/runs/503/jobs?per_page=100&page=1')['jobs'][0]
        job['labels'] = ['macos-14']
        cost = self.fake.bench_point()['cost']
        m = self.fake.collect('minutes', window=RUNS_WINDOW)['minutes']
        self.assertEqual(m['state'], 'partial')
        self.assertEqual(len(m['prerequisites']), 1)
        # Run 503's job ran 2 min 20 s on the unknown runner: 2.3333 minutes with no price.
        self.assertEqual(by_kind(m['value']['runner_minutes']),
                         {'github-hosted': 15.5, 'self-hosted': 4.0, 'unknown': 2.3333})
        self.assertEqual((m['value']['window_usd'], m['value']['unknown_minutes']), (None, 2.3333))
        self.assertEqual(m['value']['per_code_run_usd'], 0.048)  # the code runs are all priced
        self.assertEqual((by_kind(m['value']['runner_minutes']), m['value']['window_usd'], m['value']['unknown_minutes']),
                         (cost['runner_minutes'], cost['window_usd'], cost['unknown_minutes']))

    def test_a_failed_job_s_broken_timing_leaves_the_unknown_amount_unknown(self):
        # catches: one failed run's job that GitHub shows ending before it starts refusing the whole window,
        # or counted as no minutes, instead of the known minutes kept and the unknown amount itself null.
        job = self.fake.answer(R + '/actions/runs/503/jobs?per_page=100&page=1')['jobs'][0]
        job['completed_at'] = '2026-01-04T00:30:59Z'  # before its 00:31:00 start
        cost = self.fake.bench_point()['cost']
        ci = self.fake.collect('runs', 'minutes', window=RUNS_WINDOW)
        m = ci['minutes']
        self.assertEqual((ci['runs']['state'], m['state']), ('known', 'partial'))
        self.assertEqual(ci['runs']['value']['unknown_jobs'], 1)
        self.assertEqual(by_kind(m['value']['runner_minutes']), {'github-hosted': 15.5, 'self-hosted': 4.0})
        self.assertEqual((m['value']['unknown_minutes'], m['value']['window_usd']), (None, None))
        self.assertEqual((by_kind(m['value']['runner_minutes']), m['value']['unknown_minutes'], cost['unknown_jobs']),
                         (cost['runner_minutes'], cost['unknown_minutes'], 1))

    def test_a_failed_read_is_unavailable_never_zero(self):
        # catches: a missing job page read as no runs (0 runs, $0) instead of an unavailable fact.
        self.fake.drop(R + '/actions/runs/502/jobs?per_page=100&page=1')
        ci = self.fake.collect('runs', 'minutes', window=RUNS_WINDOW)
        for name in ('runs', 'minutes'):
            self.assertEqual((ci[name]['state'], ci[name]['value']), ('unavailable', None))
            self.assertEqual(len(ci[name]['prerequisites']), 1)

    def test_an_unfinished_window_is_never_read(self):
        # catches: a window still open counted as complete, so its runs and CI3 heads look final.
        until = ('--since', '2026-01-04T00:00:00Z', '--until', '2099-01-01T00:00:00Z')
        ci = self.fake.collect('runs', 'ci3', window=until)
        for name in ('runs', 'ci3'):
            self.assertEqual((ci[name]['state'], ci[name]['value'], ci[name]['read']), ('unavailable', None, None))
        self.assertEqual(self.fake.asked(), [])


class Retained(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fake = Fake(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_each_measured_source_is_kept_where_its_hash_points(self):
        # catches (R2): the exact job records behind runs and minutes, and CI3's private window, deleted once
        # measured, so nothing recoverable stands behind the source hashes.
        ci = self.fake.collect('runs', 'minutes', window=RUNS_WINDOW)
        f3 = self.fake.collect('ci3', window=CI3_WINDOW)['ci3']
        for f in (ci['runs'], ci['minutes'], f3):
            kept = self.fake.store / f['source']['path']
            self.assertTrue(kept.is_file(), f'{f["fact"]}: its source is not kept')
            self.assertEqual(hashlib.sha256(kept.read_bytes()).hexdigest(), f['source']['sha256'], f['fact'])
            self.assertEqual(kept.stat().st_mode & 0o077, 0, 'owner-only')
        self.assertEqual(ci['runs']['source'], ci['minutes']['source'])
        jobs = [json.loads(line) for line in (self.fake.store / ci['runs']['source']['path']).read_text().splitlines()]
        self.assertEqual(sorted(j['id'] for j in jobs), [5011, 5012, 5021, 5031])
        # A fresh reader remeasures CI3's record from the kept window alone, after the read returned.
        done = self.fake.run(CI3, 'measure', self.fake.store / f3['source']['path'])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), f3['value'])

    def test_a_source_that_cannot_be_kept_makes_its_fact_unavailable(self):
        # catches (R2): a measured fact reported known while its source bytes could not be kept.
        self.fake.store.write_text('not a directory', encoding='utf-8')
        ci = self.fake.collect('runs', 'minutes', 'queue', window=RUNS_WINDOW)
        for name in ('runs', 'minutes'):
            self.assertEqual((ci[name]['state'], ci[name]['value']), ('unavailable', None))
            self.assertIn('could not be kept', ci[name]['prerequisites'][0])
        self.assertEqual(ci['queue']['state'], 'known')  # nothing to keep: its value is its own bytes
        f3 = self.fake.collect('ci3', window=CI3_WINDOW)['ci3']
        self.assertEqual((f3['state'], f3['value']), ('unavailable', None))
        self.assertIn('could not be kept', f3['prerequisites'][0])


class Ci3(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fake = Fake(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_ci3_fact_carries_ci3_s_own_record(self):
        # catches: the collector recomputing, reshaping or re-rounding CI3's measure instead of carrying
        # ci3.py's record for the same window unchanged.
        record = self.fake.ci3_record()
        f = self.fake.collect('ci3', window=CI3_WINDOW)['ci3']
        self.assertEqual(f['state'], 'known')
        # tools/ci-bench/test_ci3.py's worked heads: 930 s and 2520 s, one with a rerun.
        result = f['value']['result']
        self.assertEqual((f['value']['heads'], result['timed'], result['p50_minutes'], result['p95_minutes'],
                          result['with_reruns']), (2, 2, 15.5, 42.0, 1))
        mine = {k: v for k, v in f['value'].items() if k != 'collected_at'}
        self.assertEqual(mine, {k: v for k, v in record.items() if k != 'collected_at'})
        self.assertEqual(f['read']['ended_at'], f['value']['collected_at'])
        self.assertEqual(f['evidence'], ['https://github.com/%s/pull/9' % REPO])

    def test_a_head_with_no_result_makes_the_fact_partial(self):
        # catches: an unfinished head dropped, or the record called known while it lists missing heads.
        sha = '2' * 40
        self.fake.answer(R + '/actions/workflows/ci.yml/runs?head_sha=%s&' % sha).update(total_count=0, workflow_runs=[])
        f = self.fake.collect('ci3', window=CI3_WINDOW)['ci3']
        self.assertEqual(f['state'], 'partial')
        self.assertEqual(f['value']['missing'], [{'pr': 9, 'head': sha, 'reason': 'ci: no run'}])
        self.assertEqual(f['prerequisites'], ['1 PR heads have no result yet; the record lists them in missing.'])

    def test_a_secret_in_a_read_refuses_the_whole_read(self):
        # catches: a credential-shaped value GitHub returns (here a branch head) printed in the envelope
        # instead of the whole read refused, as gather refuses a privacy hit.
        planted = 'gh' + 'p_' + 'a' * 36
        for item in self.fake.answer(R + '/activity?ref=refs/heads/topic/x&'):
            if item['after'] == '2' * 40:
                item['after'] = planted
        done = self.fake.run(HERE / 'collect_ci.py', 'read', '--repo', REPO, '--fact', 'ci3', *CI3_WINDOW)
        self.assertEqual((done.returncode, done.stdout), (1, ''))
        self.assertNotIn(planted, done.stderr)


class Activity(unittest.TestCase):
    def test_activity_is_wr8_s_current_observation(self):
        # catches: activity mixing in privacy.yml (the guard's cohort, not the page's), dropping a
        # completed job of an active run, or losing an active job's creation time.
        with tempfile.TemporaryDirectory() as tmp:
            fake = Fake(tmp)
            f = fake.collect('activity')['activity']
        self.assertEqual(f['state'], 'known')
        current = f['value']['current']
        self.assertEqual(current['runs'], [7101])
        self.assertEqual(current['jobs'], [
            {'id': 8101, 'run': 7101, 'attempt': 1, 'status': 'queued', 'pool': 'ubuntu-24.04'},
            {'id': 8102, 'run': 7101, 'attempt': 1, 'status': 'in_progress', 'pool': 'closedwiz-pc'},
            {'id': 8103, 'run': 7101, 'attempt': 1, 'status': 'completed', 'pool': 'ubuntu-24.04'}])
        self.assertEqual(current['cost_jobs'], [])
        self.assertEqual(f['value']['created_at'], [{'job': 8101, 'created_at': '2026-01-05T12:03:20Z'},
                                                    {'job': 8102, 'created_at': '2026-01-05T12:02:00Z'}])
        day = f['read']['started_at'][:10] + 'T00:00:00Z'
        self.assertEqual(f['window'], {'since': day, 'until': f['read']['started_at'], 'timezone': 'UTC'})
        self.assertEqual(f['value']['window'], f['window'])


class Queue(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fake = Fake(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def without_queued_jobs(self):
        jobs = self.fake.answer(R + '/actions/runs/7101/jobs?')
        jobs['jobs'] = [j for j in jobs['jobs'] if j['status'] != 'queued']
        jobs['total_count'] = len(jobs['jobs'])
        self.fake.drop(R + '/actions/workflows/privacy.yml/runs?status=queued&')

    def test_the_queue_is_the_guard_s_input_fresh_for_sixty_seconds(self):
        # catches: a queue read whose bound isn't the guard's 60 seconds from the read's end (an older
        # stamp, or a snapshot's time), so the guard admits on stale data or refuses fresh data.
        self.without_queued_jobs()
        f = self.fake.collect('queue')['queue']
        self.assertEqual((f['state'], f['freshness']), ('known', 'fresh'))
        self.assertEqual(f['point'], f['read']['ended_at'])
        observed = f['value']['observation']['observed_at']
        self.assertEqual(observed, unix(f['read']['ended_at']))
        self.assertEqual(unix(f['fresh_until']), observed + 60)
        code, decision = self.fake.guard(f['value']['observation'], observed + 60)
        self.assertEqual((code, decision['level']), (0, 'healthy'))
        code, decision = self.fake.guard(f['value']['observation'], observed + 61)
        self.assertEqual((code, decision['level']), (1, 'unknown'))

    def test_required_jobs_are_the_guard_s_cohort(self):
        # catches: privacy.yml or merge-group jobs left out of the guard's queue, a push run's job counted
        # as required, or a queued job given a start; the guard would then miss a real wait.
        f = self.fake.collect('queue')['queue']
        self.assertEqual(f['state'], 'known')
        observation = f['value']['observation']
        self.assertEqual(observation['queue']['jobs'], [
            {'id': 'job-8101', 'required': True, 'status': 'queued', 'queued_at': 1767614600, 'started_at': None},
            {'id': 'job-8102', 'required': True, 'status': 'in_progress', 'queued_at': 1767614520,
             'started_at': 1767614550},
            {'id': 'job-8103', 'required': True, 'status': 'completed', 'queued_at': 1767614400,
             'started_at': 1767614410},
            {'id': 'job-8201', 'required': True, 'status': 'queued', 'queued_at': 1767614640, 'started_at': None},
            {'id': 'job-8301', 'required': False, 'status': 'in_progress', 'queued_at': 1767614460,
             'started_at': 1767614465}])
        self.assertEqual([(j['job'], j['workflow'], j['run_id'], j['pool']) for j in f['value']['jobs']], [
            ('job-8101', 'ci.yml', 7101, 'ubuntu-24.04'), ('job-8102', 'ci.yml', 7101, 'closedwiz-pc'),
            ('job-8103', 'ci.yml', 7101, 'ubuntu-24.04'), ('job-8201', 'privacy.yml', 7102, 'ubuntu-24.04'),
            ('job-8301', 'privacy.yml', 7103, 'ubuntu-24.04')])
        self.assertEqual(observation['budgets'], {
            'rest': {'remaining': 4000, 'limit': 5000, 'reset_at': 4102444800, 'retry_after': 0},
            'graphql': {'remaining': 4800, 'limit': 5000, 'reset_at': 4102444800, 'retry_after': 0}})
        # job-8101 has queued since 12:03:20 on 2026-01-05: far past 900 s, so the guard escalates.
        code, decision = self.fake.guard(observation, observation['observed_at'])
        self.assertEqual((code, decision['level']), (1, 'escalate'))
        self.assertEqual(decision['oldest_wait_seconds'], observation['observed_at'] - 1767614600)

    def test_a_run_or_job_that_moves_on_mid_read_leaves_the_queue_incomplete(self):
        # catches (R1): one pass over the status lists missing a required run that started between two of
        # them (or a job added between two reads of a page), and calling the queue complete, so the guard
        # admits work while that run's required job has waited past its escalation threshold.
        runs = R + '/actions/workflows/ci.yml/runs?status=in_progress&'
        moved = {'id': 7104, 'event': 'pull_request', 'status': 'in_progress', 'conclusion': None,
                 'created_at': '2026-01-05T12:00:00Z', 'run_attempt': 1}
        late = {'id': 8104, 'run_id': 7101, 'run_attempt': 1, 'name': 'job-8104', 'status': 'queued',
                'conclusion': None, 'created_at': '2026-01-05T12:00:00Z', 'started_at': None, 'completed_at': None,
                'runner_name': None, 'labels': ['ubuntu-24.04'], 'steps': []}
        for move in ('run', 'job'):
            with self.subTest(move=move), tempfile.TemporaryDirectory() as tmp:
                self.fake = Fake(tmp)
                self.without_queued_jobs()
                if move == 'run':
                    first = self.fake.answer(runs)
                    self.fake.put(runs, {'sequence': [first, {'total_count': 2,
                                                              'workflow_runs': first['workflow_runs'] + [moved]}]})
                    self.fake.put(R + '/actions/runs/7104/jobs?', {'total_count': 1, 'jobs': [dict(late, run_id=7104)]})
                else:
                    key = R + '/actions/runs/7101/jobs?'
                    first = self.fake.answer(key)
                    self.fake.put(key, {'sequence': [first, {'total_count': len(first['jobs']) + 1,
                                                             'jobs': first['jobs'] + [late]}]})
                f = self.fake.collect('queue')['queue']
                self.assertEqual(f['state'], 'partial')
                self.assertEqual(f['value']['observation']['complete'], False)
                code, decision = self.fake.guard(f['value']['observation'], f['value']['observation']['observed_at'])
                self.assertEqual((code, decision['level'], decision['allowed']), (1, 'unknown', False))

    def test_a_queue_that_cannot_be_read_whole_says_unknown(self):
        # catches: a job page that can't be read whole treated as an empty queue (the guard admits), a job
        # of another attempt dropped or counted as required, or a failed rate-limit read encoded as zeros.
        self.without_queued_jobs()
        self.fake.drop(R + '/actions/runs/7103/jobs?')
        f = self.fake.collect('queue')['queue']
        self.assertEqual(f['state'], 'partial')
        self.assertEqual(f['value']['observation']['complete'], False)
        code, decision = self.fake.guard(f['value']['observation'], f['value']['observation']['observed_at'])
        self.assertEqual((code, decision['level']), (1, 'unknown'))
        # A job of another attempt than its run's is kept, never required, and the queue incomplete.
        self.fake.answers.append([R + '/actions/runs/7103/jobs?', {'total_count': 1, 'jobs': [
            {'id': 8301, 'run_id': 7103, 'run_attempt': 2, 'status': 'in_progress', 'created_at': '2026-01-05T12:01:00Z',
             'started_at': '2026-01-05T12:01:05Z', 'labels': ['ubuntu-24.04']}]}])
        self.fake.answers.insert(0, self.fake.answers.pop())
        f = self.fake.collect('queue')['queue']
        self.assertEqual(f['state'], 'partial')
        jobs = f['value']['observation']['queue']['jobs']
        self.assertEqual([j['id'] for j in jobs], ['job-8102', 'job-8103', 'job-8301'])
        self.assertEqual(jobs[-1]['required'], False)
        self.fake.drop('rate_limit')
        f = self.fake.collect('queue')['queue']
        self.assertEqual((f['state'], f['value'], f['fresh_until'], f['freshness']),
                         ('unavailable', None, None, 'unknown'))


class CommandLine(unittest.TestCase):
    def test_a_bad_command_line_exits_2_before_any_read(self):
        # catches: a command the contract refuses still reading GitHub, or printing a partial envelope.
        with tempfile.TemporaryDirectory() as tmp:
            fake = Fake(tmp)
            for args in (('--repo', REPO),
                         ('--repo', REPO, '--fact', 'merges'),
                         ('--repo', REPO, '--fact', 'runs'),
                         ('--repo', REPO, '--fact', 'ci3', '--since', '2026-01-06T00:00:00Z',
                          '--until', '2026-01-05T00:00:00Z'),
                         ('--repo', REPO, '--fact', 'queue', '--since', '2026-01-05'),
                         ('--repo', 'not a repository', '--fact', 'queue')):
                done = fake.run(HERE / 'collect_ci.py', 'read', *args)
                self.assertEqual((done.returncode, done.stdout), (2, ''), args)
            self.assertEqual(fake.asked(), [])


class Gather(unittest.TestCase):
    def test_gather_s_ci_call_reads_every_ci_fact(self):
        # catches: a snapshot's CI group missing a fact (the contract requires all five, even unavailable).
        with tempfile.TemporaryDirectory() as tmp:
            fake = Fake(tmp)
            code = ('import json, sys; sys.path.insert(0, sys.argv[1]); import gather; '
                    'print(json.dumps(gather.ci_facts(sys.argv[2], since=sys.argv[3], until=sys.argv[4])))')
            done = fake.run('-c', code, HERE, REPO, '2026-01-04T00:00:00Z', '2026-01-04T01:00:00Z')
        self.assertEqual(done.returncode, 0, done.stderr)
        ci = json.loads(done.stdout)
        suite._shape(ci, SCHEMA['$defs']['ci_facts'], SCHEMA)
        self.assertEqual(list(ci), ['runs', 'minutes', 'ci3', 'activity', 'queue'])
        self.assertEqual({k: f['state'] for k, f in ci.items()},
                         {'runs': 'known', 'minutes': 'known', 'ci3': 'known', 'activity': 'known', 'queue': 'known'})


if __name__ == '__main__':
    unittest.main()
