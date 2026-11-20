#!/usr/bin/env python3
"""WRD1 (#629): health signals and the v2 history contract. Synthetic only.

P1: the three health signals are saved at five-minute identities, through the
real finite gather and collector, with a synthetic gh and a virtual clock;
retries reuse a boundary, gaps stay absent, failures are explicit, old v1
bytes never change and nothing is backfilled.
P2: health means sourced current observations against existing limits:
current-head/run/attempt cases, complete and partial queue reads, and open,
held and shared stage cases at, below and above the loaded TL1 limits.

Expected values are literals read off the synthetic inputs below, or the TL2
fixture's literal endpoints (fixtures/stage-waits/).
"""
import copy
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PUBLIC_ROOT = Path(__file__).resolve().parents[1] / 'collector'
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
FIX = HERE / 'fixtures'
TL2 = PUBLIC_ROOT / 'fixtures/stage-waits'
sys.path.insert(0, str(HERE))
import history  # noqa: E402
sys.path.insert(0, str(PUBLIC_ROOT))
import sources  # noqa: E402
import suite  # noqa: E402

REPO = 'synthetic-owner/work'
API = 'repos/' + REPO
EVIDENCE = 'https://github.com/synthetic-owner/work/issues/9001'
H1, H2 = 'a1' * 20, 'b2' * 20
POOLS = ('closedwiz-pc', 'ubuntu-24.04')
LIMITS = 'builder_start={}\nreviewer_start={}\nmerge={}\nfix_after_changes=30\nbuilder_question_answer=15\n'
# The canonical bytes history.save writes for fixtures/contract/known.json, pinned once by
# hand: a v1 sample saved before v2 existed must keep exactly these bytes.
V1_SHA256 = '6f6006dda51632d1c1b4726de2a3ef5be19ba2abb0e62bd26f299f0d526a400c'


def module(name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, (PUBLIC_ROOT if name == 'health' else HERE) / f'{name}.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def health():
    return module('health')


class Clock:
    """A virtual clock: each read is one second after the last."""

    def __init__(self, start):
        self.at = datetime.strptime(start, '%Y-%m-%dT%H:%M:%SZ') - timedelta(seconds=1)

    def __call__(self):
        self.at += timedelta(seconds=1)
        return self.at.strftime('%Y-%m-%dT%H:%M:%SZ')


def run(rid, head=H1, status='completed', conclusion='success', created='2030-03-01T11:40:00Z', attempt=1):
    return {'id': rid, 'run_attempt': attempt, 'status': status, 'conclusion': conclusion, 'head_sha': head,
            'head_branch': 'main', 'event': 'push', 'created_at': created}


def runs_for(head):
    return f'{API}/actions/workflows/ci.yml/runs?branch=main&event=push&head_sha={head}&per_page=100&page=1'


def main_world(head=H1, listed=(), after=None, reread=None):
    """Synthetic main reads: the branch head (read twice), its runs, and each run reread."""
    heads = iter([head, after or head])
    answers = {runs_for(head): {'total_count': len(listed), 'workflow_runs': list(listed)}}
    for r in listed:
        answers[f'{API}/actions/runs/{r["id"]}'] = (reread or {}).get(r['id'], r)

    def read(path):
        if path == f'{API}/branches/main':
            return {'name': 'main', 'commit': {'sha': next(heads)}}
        if path not in answers:
            raise health().B.Fail('synthetic source unavailable')
        return copy.deepcopy(answers[path])
    return read


def job(jid, rid, status, labels, created='2030-03-01T11:50:00Z', attempt=1):
    return {'id': jid, 'run_id': rid, 'run_attempt': attempt, 'status': status, 'labels': labels,
            'created_at': created, 'started_at': None if status == 'queued' else '2030-03-01T11:52:00Z'}


def queue_world(active=(), jobs=None, total=None):
    """Synthetic WR8 reads: every ci.yml run (one page), each run's jobs (read twice) and its reread."""
    listed = list(active)
    answers = {f'{API}/actions/workflows/ci.yml/runs?per_page=100&page=1':
               {'total_count': len(listed) if total is None else total, 'workflow_runs': listed},
               f'{API}/actions/workflows/ci.yml/runs?per_page=100&page=2': {'total_count': total or 0, 'workflow_runs': []}}
    for r in listed:
        mine = [j for j in (jobs or []) if j['run_id'] == r['id']]
        answers[f'{API}/actions/runs/{r["id"]}/jobs?per_page=100&page=1'] = {'total_count': len(mine), 'jobs': mine}
        answers[f'{API}/actions/runs/{r["id"]}'] = r

    def read(path):
        if path not in answers:
            raise health().B.Fail('synthetic source unavailable')
        return copy.deepcopy(answers[path])
    return read


def by_id(provider):
    return {o['id']: o for o in provider['observations']}


def checked(slot, provider):
    """The provider as a saved v2 envelope keeps it: composition validates every rule."""
    record = suite.compose('2030-03-01T12:05:00Z', [provider], assembled_at='2030-03-01T12:09:00Z')
    sources.safe_record(record)
    return next(p for p in record['health'] if p['slot'] == slot)


class MainCI(unittest.TestCase):
    def observe(self, read):
        provider, wire = health().main_ci(REPO, read, Clock('2030-03-01T12:05:01Z'))
        self.assertEqual(json.loads(wire)['schema'], 'openwiz.war-room.main-ci.v1')
        return checked('main_ci', provider)['observations'][0]

    def test_a_success_at_the_current_head_is_green_with_its_identity(self):
        o = self.observe(main_world(listed=[run(501)]))
        self.assertEqual((o['result'], o['state']), ('success', 'known'))
        self.assertEqual({k: o['identity'][k] for k in ('repository', 'branch', 'head_sha', 'workflow', 'run_id', 'run_attempt')},
                         {'repository': REPO, 'branch': 'main', 'head_sha': H1, 'workflow': 'ci.yml',
                          'run_id': 501, 'run_attempt': 1})
        self.assertEqual(o['evidence'], ['https://github.com/synthetic-owner/work/actions/runs/501'])
        # A point read, not an invented window: the point is the read's end.
        self.assertIsNone(o['window'])
        self.assertEqual(o['point'], o['read']['ended_at'])
        self.assertEqual(o['read'], {'started_at': '2030-03-01T12:05:01Z', 'ended_at': '2030-03-01T12:05:02Z'})

    def test_failed_pending_and_cancelled_runs_are_named_never_green(self):
        for status, conclusion, result in (('completed', 'failure', 'failure'), ('completed', 'timed_out', 'failure'),
                                           ('in_progress', None, 'pending'), ('queued', None, 'pending'),
                                           ('completed', 'cancelled', 'cancelled')):
            with self.subTest(status=status, conclusion=conclusion):
                o = self.observe(main_world(listed=[run(501, status=status, conclusion=conclusion)]))
                self.assertEqual((o['result'], o['state']), (result, 'known'))

    def test_the_latest_run_on_the_head_decides_and_a_tie_is_unknown(self):
        older, newer = run(501), run(502, status='in_progress', conclusion=None, created='2030-03-01T11:45:00Z')
        self.assertEqual(self.observe(main_world(listed=[older, newer]))['result'], 'pending')
        tied = run(503, created='2030-03-01T11:40:00Z', conclusion='failure')
        o = self.observe(main_world(listed=[older, tied]))
        self.assertEqual((o['result'], o['state']), ('unknown', 'unavailable'))

    def test_a_superseded_head_or_a_changing_read_cannot_be_green(self):
        cases = {
            # A new push: the old head's success is not the current head's result.
            'superseded head': main_world(head=H2, listed=[]),
            'head moved during the read': main_world(listed=[run(501)], after=H2),
            'attempt changed on reread': main_world(listed=[run(501)], reread={501: run(501, attempt=2)}),
            'status changed on reread': main_world(listed=[run(501, status='in_progress', conclusion=None)],
                                                   reread={501: run(501)}),
            'run for another head listed': main_world(listed=[run(501, head=H2)]),
            'another conclusion': main_world(listed=[run(501, conclusion='skipped')]),
        }
        for name, read in cases.items():
            with self.subTest(name):
                o = self.observe(read)
                self.assertEqual((o['result'], o['state'], o['value']), ('unknown', 'unavailable', None))
                self.assertTrue(o['prerequisites'])

    def test_an_incomplete_or_failed_read_is_unknown(self):
        def short(path):
            if path.endswith('page=1') and 'head_sha' in path:
                return {'total_count': 2, 'workflow_runs': [run(501)]}
            if path.endswith('page=2'):
                return {'total_count': 2, 'workflow_runs': []}
            return main_world(listed=[run(501)])(path)

        def broken(path):
            raise OSError('synthetic failure')
        for read in (short, broken):
            o = self.observe(read)
            self.assertEqual((o['result'], o['state']), ('unknown', 'unavailable'))


class Queue(unittest.TestCase):
    STARTED, ENDED = '2030-03-01T12:05:00Z', '2030-03-01T12:05:30Z'

    def observe(self, read):
        provider, wire = health().read_queue(REPO, POOLS, read, self.STARTED, self.ENDED)
        self.assertEqual(json.loads(wire)['schema'], 'openwiz.war-room.ci-queue.v1')
        return checked('ci_queue', provider)

    def test_a_complete_empty_read_is_a_known_zero_per_pool(self):
        p = self.observe(queue_world())
        got = {i: (o['state'], o['value']) for i, o in by_id(p).items()}
        self.assertEqual(got, {'queued:closedwiz-pc': ('known', 0), 'running:closedwiz-pc': ('known', 0),
                               'queued:ubuntu-24.04': ('known', 0), 'running:ubuntu-24.04': ('known', 0)})
        self.assertEqual(p['state'], 'known')
        for o in p['observations']:
            self.assertIsNone(o['limit'])  # No source owns a queue limit.

    def test_queued_jobs_keep_pool_job_run_attempt_and_their_wait(self):
        runs = [run(601, status='queued', conclusion=None), run(602, status='in_progress', conclusion=None)]
        jobs = [job(7001, 601, 'queued', ['ubuntu-24.04'], created='2030-03-01T11:50:00Z'),
                job(7002, 601, 'queued', ['ubuntu-24.04'], created='2030-03-01T12:01:00Z'),
                job(7003, 602, 'in_progress', ['self-hosted', 'closedwiz-pc'])]
        o = by_id(self.observe(queue_world(runs, jobs)))
        self.assertEqual(o['queued:ubuntu-24.04']['value'], 2)
        self.assertEqual(o['queued:ubuntu-24.04']['sample']['identities'], ['job-7001', 'job-7002'])
        self.assertEqual(o['running:closedwiz-pc']['value'], 1)
        self.assertEqual(o['queued:closedwiz-pc']['value'], 0)
        # 11:50:00 to the 12:05:30 read is 15.5 minutes: the oldest queued age.
        oldest = o['oldest-queued:ubuntu-24.04']
        self.assertEqual((oldest['statistic'], oldest['value'], oldest['unit']), ('max', 15.5, 'minutes'))
        self.assertNotIn('oldest-queued:closedwiz-pc', o)  # Nothing queued there: no age, not zero.
        wait = o['queued-wait:ubuntu-24.04:job-7001']
        self.assertEqual((wait['state'], wait['value']), ('partial', 15.5))
        self.assertEqual(wait['interval'], {'id': 'job-7001', 'started_at': '2030-03-01T11:50:00Z', 'ended_at': None})
        self.assertEqual((wait['identity']['run_id'], wait['identity']['run_attempt'], wait['identity']['pool']),
                         (601, 1, 'ubuntu-24.04'))

    def test_partial_pages_or_changed_attempts_never_produce_zero(self):
        runs = [run(601, status='queued', conclusion=None)]
        cases = {'pagination short of total_count': queue_world(runs, [job(7001, 601, 'queued', ['ubuntu-24.04'])], total=2),
                 'attempt changed': queue_world(runs, [job(7001, 601, 'queued', ['ubuntu-24.04'], attempt=2)]),
                 'failed read': lambda path: (_ for _ in ()).throw(OSError('synthetic'))}
        for name, read in cases.items():
            with self.subTest(name):
                p = self.observe(read)
                self.assertEqual(p['state'], 'unavailable')
                self.assertTrue(all(o['value'] is None for o in p['observations']))
                self.assertTrue(p['prerequisites'])

    def test_an_unclassified_job_leaves_every_pool_count_partial(self):
        runs = [run(601, status='queued', conclusion=None)]
        for labels in (None, ['macos-15']):
            with self.subTest(labels=labels):
                p = self.observe(queue_world(runs, [job(7001, 601, 'queued', labels)]))
                counts = [o for o in p['observations'] if o['statistic'] == 'count']
                self.assertEqual({(o['state'], o['value']) for o in counts}, {('partial', None)})
                self.assertEqual(p['state'], 'partial')


class Stage(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='war-room-health-'))
        self.addCleanup(shutil.rmtree, self.root)
        for name in ('journeys.json', 'stage-waits.json'):
            shutil.copy(TL2 / name, self.root / name)

    def observe(self, builder=10, reviewer=5, merge=5, settings_read_at='2030-03-01T12:04:00Z'):
        (self.root / 'limits.conf').write_text(LIMITS.format(builder, reviewer, merge))
        provider = health().stage_health(self.root, journey='journeys.json', sidecar='stage-waits.json',
                                         settings='limits.conf', settings_read_at=settings_read_at,
                                         read={'started_at': '2030-03-01T12:04:00Z', 'ended_at': '2030-03-01T12:04:30Z'},
                                         evidence=[EVIDENCE])
        return checked('stage_health', provider)

    def test_health_stages_judged_at_below_and_above_their_loaded_limits(self):
        builder = 'wait:builder_start:t4301'  # 09:00 -> 09:10, 10 minutes
        reviewer = 'wait:reviewer_start:p4401:' + '1a' * 20 + ':2030-03-01t10:00:00z'  # 10:00 -> 10:06, 6 minutes
        merge = 'wait:merge:p4401:' + '2b' * 20 + ':c6205:2030-03-01t11:31:00z'  # 11:31 -> 11:36, 5 minutes
        for limits, results in (((10, 6, 5), ('not_missed', 'not_missed', 'not_missed')),   # at
                                ((11, 7, 6), ('not_missed', 'not_missed', 'not_missed')),   # below
                                ((9, 5, 4), ('missed', 'missed', 'missed'))):              # above
            with self.subTest(limits=limits):
                o = by_id(self.observe(*limits))
                self.assertEqual(tuple(o[k]['result'] for k in (builder, reviewer, merge)), results)
                self.assertEqual(tuple(o[k]['value'] for k in (builder, reviewer, merge)), (10.0, 6.0, 5.0))
                self.assertEqual({o[k]['state'] for k in (builder, reviewer, merge)}, {'known'})
                self.assertEqual(tuple(o[k]['limit']['minutes'] for k in (builder, reviewer, merge)), limits)
                self.assertEqual(o['limit:merge']['value'], limits[2])

    def test_open_held_stale_and_unknown_keep_producer_semantics(self):
        o = by_id(self.observe())
        open_ = o['wait:builder_start:t4303']  # open from 11:55 to TL2's 12:00 read: 5 minutes so far
        self.assertEqual((open_['result'], open_['state'], open_['value']), ('pending', 'partial', 5.0))
        self.assertEqual(open_['interval']['ended_at'], None)
        late = by_id(self.observe(builder=4))['wait:builder_start:t4303']
        self.assertEqual((late['result'], late['state'], late['value']), ('missed', 'partial', 5.0))
        gated = o['wait:reviewer_start:p4402:' + '4d' * 20 + ':2030-03-01t08:50:00z']
        stale = o['wait:reviewer_start:p4402:' + '5e' * 20 + ':2030-03-01t08:35:00z']
        unknown = o['wait:builder_start:t4302']
        self.assertEqual((gated['result'], gated['state'], gated['value']), ('gated', 'partial', None))
        self.assertEqual((stale['result'], stale['state'], stale['value']), ('stale', 'partial', None))
        self.assertEqual((unknown['result'], unknown['state'], unknown['value']), ('unknown', 'unavailable', None))
        # Only the three health stages; fix and answer stay in stage_waits' detail.
        self.assertEqual({x['identity']['stage'] for x in o.values()}, {'builder_start', 'reviewer_start', 'merge'})

    def test_r3_an_edited_end_straddling_the_limit_keeps_its_measured_lower_bound(self):
        # TL2: start 09:00, end record edited between 09:10 and 09:11, so the wait is 10 to 11
        # minutes; under the 10-minute limit its pass/miss is unknown, but 10 minutes is proven.
        journeys = json.loads((self.root / 'journeys.json').read_text())
        ticket = next(t for t in journeys['tickets'] if t['ticket'] == 4301)
        next(e for e in ticket['events'] if e['id'] == 'e5')['completeness'] = 'edited'
        side = json.loads((self.root / 'stage-waits.json').read_text())
        interval = next(i for i in side['intervals'] if i['key'] == 'builder_start:t4301')
        interval['end']['latest'] = '2030-03-01T09:11:00Z'
        side['journey_hash'] = health().producer.journey_hash(journeys)
        (self.root / 'journeys.json').write_text(json.dumps(journeys))
        (self.root / 'stage-waits.json').write_text(json.dumps(side))
        wait = by_id(self.observe())['wait:builder_start:t4301']
        self.assertEqual((wait['result'], wait['state'], wait['value']), ('unknown', 'partial', 10.0))
        self.assertIn('Edited end record: the wait lies between 10.0 and 11.0 minutes.', wait['prerequisites'])
        # A wholly unmeasured unknown interval still stays unavailable.
        self.assertEqual(by_id(self.observe())['wait:builder_start:t4302']['state'], 'unavailable')

    def test_a_changed_limit_has_its_own_identity(self):
        a = by_id(self.observe())['limit:builder_start']['limit']
        b = by_id(self.observe(builder=12))['limit:builder_start']['limit']
        self.assertNotEqual(a['sha256'], b['sha256'])
        self.assertEqual((a['minutes'], b['minutes']), (10, 12))
        self.assertEqual(a['sha256'], hashlib.sha256(LIMITS.format(10, 5, 5).encode()).hexdigest())

    def test_settings_read_before_the_tl2_read_or_refused_evidence_is_unavailable(self):
        self.assertEqual(self.observe(settings_read_at='2030-03-01T11:00:00Z')['state'], 'unavailable')
        (self.root / 'stage-waits.json').write_text('{}')
        self.assertEqual(self.observe()['state'], 'unavailable')


class Contract(unittest.TestCase):
    def record(self):
        return suite.compose('2030-03-01T12:05:00Z', assembled_at='2030-03-01T12:06:00Z')

    def test_new_records_are_v2_and_old_ones_still_read(self):
        record = self.record()
        self.assertEqual(record['schema'], 'openwiz.war-room.v2')
        self.assertEqual([p['slot'] for p in record['health']], ['main_ci', 'ci_queue', 'stage_health'])
        self.assertEqual([p['slot'] for p in record['providers']], [p['slot'] for p in suite.PROVIDERS])
        for name in ('known.json', 'partial.json', 'unavailable.json'):
            old = suite.load(PUBLIC_ROOT / 'fixtures/contract' / name)
            self.assertEqual(old['schema'], 'openwiz.war-room.v1')
            for p in suite.health(old):
                self.assertEqual((p['state'], p['observations']), ('unavailable', []))
                self.assertIn('Not observed: this sample predates the v2 health record.', p['prerequisites'])

    def test_version_shapes_do_not_mix(self):
        v1 = suite.load(PUBLIC_ROOT / 'fixtures/contract/known.json')
        v2 = self.record()
        for bad in (dict(v1, health=v2['health']),                   # v1 with health
                    {k: v for k, v in v2.items() if k != 'health'},  # v2 without it
                    dict(v2, health=v2['health'][::-1]),             # out of order
                    dict(v2, schema='openwiz.war-room.v3')):
            with self.subTest(keys=sorted(bad)), self.assertRaises(ValueError):
                suite.validate(bad)

    def test_unknown_is_never_green_or_zero(self):
        read = main_world(listed=[run(501)])
        provider, _ = health().main_ci(REPO, read, Clock('2030-03-01T12:05:01Z'))
        good = checked('main_ci', provider)

        def refused(change):
            p = copy.deepcopy(good)
            change(p['observations'][0])
            with self.assertRaises(ValueError):
                suite.compose('2030-03-01T12:05:00Z', [p], assembled_at='2030-03-01T12:09:00Z')
        refused(lambda o: o.update(prerequisites=['gap']))                     # known with a gap
        refused(lambda o: o.update(result='unknown'))                          # unknown cannot be known
        refused(lambda o: o.update(state='unavailable', prerequisites=['gap']))  # unavailable keeps no result
        refused(lambda o: o['identity'].update(run_attempt=None))              # green needs its identity
        refused(lambda o: o.update(point=None, window=None))                   # a known read has a basis
        refused(lambda o: o.update(window={'since': o['read']['started_at'], 'until': o['read']['ended_at'],
                                            'timezone': 'UTC'}))              # never point and window
        refused(lambda o: o.update(point='2030-03-01T12:08:00Z'))              # point after the read
        queue, _ = health().read_queue(REPO, POOLS, queue_world(), '2030-03-01T12:05:00Z', '2030-03-01T12:05:30Z')
        zero = copy.deepcopy(checked('ci_queue', queue))
        zero['observations'][0]['value'] = 1  # a count must equal its identities
        with self.assertRaises(ValueError):
            suite.compose('2030-03-01T12:05:00Z', [zero], assembled_at='2030-03-01T12:09:00Z')


class Collection(unittest.TestCase):
    """P1 through the real gather.gather and history.collect, with a synthetic gh."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='war-room-collect-'))
        self.addCleanup(shutil.rmtree, self.tmp)
        self.origin = self.tmp / 'origin.git'
        subprocess.run(['git', 'init', '-q', '--bare', str(self.origin)], check=True)
        self.stage = self.tmp / 'stage'
        self.stage.mkdir()
        for name in ('journeys.json', 'stage-waits.json'):
            shutil.copy(TL2 / name, self.stage / name)
        bin_dir = self.tmp / 'bin'
        bin_dir.mkdir()
        (bin_dir / 'gh').symlink_to(FIX / 'health/fake_gh.py')
        self.answers = self.tmp / 'gh.json'
        self.world()
        self.env = {'PATH': str(bin_dir) + os.pathsep + os.environ['PATH'], 'HEALTH_FIXTURE': str(self.answers)}
        self.history = self.tmp / 'history'
        self.count = 0

    def world(self, main=True):
        answers = {}
        if main:
            answers[f'{API}/branches/main'] = {'name': 'main', 'commit': {'sha': H1}}
            answers[runs_for(H1)] = {'total_count': 1, 'workflow_runs': [run(501)]}
            answers[f'{API}/actions/runs/501'] = run(501)
        listed = f'{API}/actions/workflows/ci.yml/runs?'
        for status in ('in_progress', 'waiting', 'pending', 'requested'):
            answers[listed + f'status={status}&per_page=100&page=1'] = {'total_count': 0, 'workflow_runs': []}
        queued = run(601, status='queued', conclusion=None)
        answers[listed + 'status=queued&per_page=100&page=1'] = {'total_count': 1, 'workflow_runs': [queued]}
        answers['re:' + listed.replace('?', r'\?') + r'created=.*&status=completed&per_page=100&page=1'] = \
            {'total_count': 0, 'workflow_runs': []}
        answers[f'{API}/actions/runs/601/jobs?per_page=100&page=1'] = {
            'total_count': 1, 'jobs': [job(7001, 601, 'queued', ['ubuntu-24.04'], created='2030-03-01T11:50:00Z')]}
        answers[f'{API}/actions/runs/601'] = queued
        self.answers.write_text(json.dumps(answers))

    def gather(self, start):
        import gather
        self.count += 1
        out = self.tmp / f'out-{self.count}'
        clock = Clock(start)
        with patch.dict(os.environ, self.env):
            gather.gather(out, remote=str(self.origin), repo=REPO, run_url=EVIDENCE, clock=clock,
                          pools=POOLS, stage=self.stage)
        return out, clock()

    def collect(self, start):
        import publish
        out, at = self.gather(start)
        reader = publish.selection_reader(out / 'root', out / 'selection.json')
        return history.collect(self.history, at, reader)

    def samples(self):
        return sorted(p.name for p in (self.history / 'samples').glob('*.json'))

    def test_boundaries_retries_gaps_failures_and_old_bytes(self):
        # The same v1 record two hours earlier on the collection day (11:00 -> 01:00, 12:00 -> 02:00).
        v1 = json.loads((PUBLIC_ROOT / 'fixtures/contract/known.json').read_text().replace('2030-01-02T1', '2030-03-01T0'))
        history.save(self.history, v1)
        old = (self.history / 'samples' / '2030-03-01T02-00-00Z.json').read_bytes()
        self.assertEqual(hashlib.sha256(old).hexdigest(), V1_SHA256)

        first, created = self.collect('2030-03-01T12:05:10Z')
        self.assertTrue(created)
        self.assertEqual(first['schema'], 'openwiz.war-room.v2')
        h = {p['slot']: p for p in first['health']}
        main = h['main_ci']['observations'][0]
        self.assertEqual((main['result'], main['identity']['head_sha'], main['identity']['run_id']), ('success', H1, 501))
        queue = by_id(h['ci_queue'])
        self.assertEqual(queue['queued:ubuntu-24.04']['value'], 1)
        self.assertEqual(queue['running:closedwiz-pc']['value'], 0)
        stage = by_id(h['stage_health'])
        self.assertEqual(stage['wait:builder_start:t4301']['result'], 'not_missed')
        self.assertEqual(stage['limit:builder_start']['value'], 10)  # the repository's limits.conf
        # The detailed five-stage projection comes from the same validated evidence.
        waits = next(p for p in first['providers'] if p['slot'] == 'stage_waits')
        self.assertIn('wait:builder_question_answer:t4301:c6102', {m['id'] for m in waits['metrics']})

        # A retry inside the same boundary reuses the saved sample and reads nothing.
        def refuse(at, previous):
            raise AssertionError('a saved boundary was read again')
        again, created = history.collect(self.history, '2030-03-01T12:08:59Z', refuse)
        self.assertEqual((again, created), (first, False))

        # A failed main read greys only main CI; nothing is filled from 12:05.
        self.world(main=False)
        second, _ = self.collect('2030-03-01T12:10:20Z')
        h2 = {p['slot']: p for p in second['health']}
        self.assertEqual(h2['main_ci']['state'], 'unavailable')
        failed = h2['main_ci']['observations'][0]
        self.assertEqual((failed['result'], failed['identity']['head_sha'], failed['evidence']), ('unknown', None, []))
        self.assertNotEqual(failed['read'], main['read'])  # its own read, not 12:05's
        self.assertEqual(by_id(h2['ci_queue'])['queued:ubuntu-24.04']['value'], 1)

        # 12:15 is missed; 12:20 is saved; then 12:15 arrives late and is kept, out of order.
        self.world()
        self.collect('2030-03-01T12:20:05Z')
        late, created = self.collect('2030-03-01T12:15:30Z')
        self.assertTrue(created)
        self.assertEqual(history.latest(self.history)['sample_at'], '2030-03-01T12:20:00Z')
        self.assertEqual(self.samples(), ['2030-03-01T02-00-00Z.json', '2030-03-01T12-05-00Z.json',
                                          '2030-03-01T12-10-00Z.json', '2030-03-01T12-15-00Z.json',
                                          '2030-03-01T12-20-00Z.json'])
        self.assertEqual((self.history / 'samples' / '2030-03-01T02-00-00Z.json').read_bytes(), old)

        # A restart reads both versions; the weekly consumer reads them too.
        result = subprocess.run([sys.executable, '-I', str(HERE / 'weekly.py'), '--history', str(self.history),
                                 '--at', '2030-03-09T09:00:00Z'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        weekly = json.loads(result.stdout)
        self.assertEqual(weekly['weeks'][0]['samples']['observed'], 5)  # the 2030-02-23 to 03-02 PST week
        versions = [r['schema'] for r in history.read_all(self.history)]
        self.assertEqual(versions, ['openwiz.war-room.v1'] + ['openwiz.war-room.v2'] * 4)

    def test_r1_queue_read_bounds_close_after_its_actions_reads(self):
        # Each gh read takes a virtual second. The queue's saved read end must not precede
        # the reads it rests on, and its waits run to that end.
        import gather
        clock, reads = Clock('2030-03-01T12:05:10Z'), []
        real = gather.B.gh

        def timed(path):
            reads.append((path, clock()))
            return real(path)
        with patch.dict(os.environ, self.env), patch.object(gather.B, 'gh', timed):
            gather.gather(self.tmp / 'out-timed', remote=str(self.origin), repo=REPO, run_url=EVIDENCE, clock=clock,
                          pools=POOLS, stage=self.stage)
        selection = json.loads((self.tmp / 'out-timed/selection.json').read_text())
        entry = next(e for e in selection if e['slot'] == 'ci_queue')
        queue = by_id(json.loads((self.tmp / 'out-timed/root' / entry['path']).read_text()))
        last = max(t for path, t in reads if '/actions/workflows/ci.yml/runs?status' in path or '/runs/601' in path)
        oldest = queue['oldest-queued:ubuntu-24.04']
        self.assertGreaterEqual(oldest['read']['ended_at'], last)
        self.assertEqual(oldest['point'], oldest['read']['ended_at'])
        self.assertEqual(oldest['value'], health()._minutes('2030-03-01T11:50:00Z', oldest['read']['ended_at']))
        self.assertLessEqual(entry['observed_at'], max(e['observed_at'] for e in selection))

    def test_a_privacy_hit_in_health_input_refuses_the_whole_collection(self):
        journeys = json.loads((self.stage / 'journeys.json').read_text())
        journeys['repo'] = 'ghp_' + 'A' * 36
        (self.stage / 'journeys.json').write_text(json.dumps(journeys))
        import gather
        with self.assertRaises(gather.Fail):
            self.collect('2030-03-01T12:05:10Z')
        self.assertFalse((self.history / 'samples').exists())

    def test_unreadable_stage_inputs_grey_only_the_two_stage_cards(self):
        # catches (#648): a deleted stage sidecar or an unreadable limits file aborting the whole
        # gather, so main CI and the queue already read are lost and no sample is saved.
        import gather
        for name, start, limits, named in (
                ('missing sidecar', '2030-03-01T12:05:10Z', gather.LIMITS, 'stage-waits.json'),
                ('missing limits', '2030-03-01T12:10:10Z', self.tmp / 'no-limits.conf', 'limits.conf')):
            with self.subTest(name):
                if name == 'missing sidecar':
                    (self.stage / 'stage-waits.json').unlink()
                else:
                    shutil.copy(TL2 / 'stage-waits.json', self.stage / 'stage-waits.json')
                with patch.object(gather, 'LIMITS', limits):
                    record, created = self.collect(start)
                self.assertTrue(created)
                h = {p['slot']: p for p in record['health']}
                self.assertEqual(h['main_ci']['observations'][0]['result'], 'success')
                self.assertEqual(by_id(h['ci_queue'])['queued:ubuntu-24.04']['value'], 1)
                waits = next(p for p in record['providers'] if p['slot'] == 'stage_waits')
                for provider in (h['stage_health'], waits):
                    self.assertEqual(provider['state'], 'unavailable')
                    self.assertIn(named, ' '.join(provider['prerequisites']))

    def test_a_cli_retry_in_a_saved_boundary_reuses_it_without_gathering(self):
        # catches (#647): `collect --gather` gathering before it reads the branch, so a retry in a
        # saved boundary reads every source again and a new gather error fails it; or a gather
        # ending past its boundary saved under the time it started instead of its end.
        import contextlib
        import io
        import itertools
        import gather
        import publish
        real, calls, outs = gather.gather, [], []

        def cli(check, end, fail=False, during=None):
            def gathered(out, **kw):
                calls.append(check)
                outs.append(out)
                if fail:
                    raise gather.Fail('synthetic gather failure')
                selection = real(out, **dict(kw, clock=Clock(check), pools=POOLS))
                if during:  # another writer pushes a sample to war-room while this gather reads
                    publish.publish(str(self.origin), during, publish.selection_reader(out / 'root', out / 'selection.json'),
                                    draw_page=False)
                return selection
            times, said = itertools.chain([check], itertools.repeat(end)), io.StringIO()
            with patch.dict(os.environ, self.env), patch.object(gather, 'gather', gathered), \
                    patch.object(gather, 'now', lambda: next(times)), contextlib.redirect_stdout(said):
                code = publish.cli(['collect', '--remote', str(self.origin), '--gather', REPO, EVIDENCE])
            return code, said.getvalue()

        def saved():
            listed = subprocess.run(['git', '-C', str(self.origin), 'ls-tree', '-r', 'refs/heads/war-room'],
                                    check=True, capture_output=True, text=True).stdout
            return sorted(line.split()[:1:-1] for line in listed.splitlines())  # [name, blob]

        code, said = cli('2030-03-01T12:05:10Z', '2030-03-01T12:06:30Z')
        self.assertEqual(code, 0)
        self.assertTrue(said.startswith('collected into war-room at '))
        first = saved()
        self.assertEqual([name for name, _ in first], ['samples/2030-03-01T12-05-00Z.json'])
        # A retry in that boundary reads nothing, so a gather that would now fail never runs.
        self.assertEqual(cli('2030-03-01T12:08:59Z', '2030-03-01T12:09:30Z', fail=True),
                         (0, 'boundary already collected\n'))
        self.assertEqual(calls, ['2030-03-01T12:05:10Z'])
        self.assertEqual(saved(), first)
        # Started in the unsaved 12:10 boundary, ended in 12:15: the new sample is the gather's end.
        self.assertEqual(cli('2030-03-01T12:14:30Z', '2030-03-01T12:15:30Z')[0], 0)
        crossed = saved()
        self.assertEqual([name for name, _ in crossed], ['samples/2030-03-01T12-05-00Z.json',
                                                          'samples/2030-03-01T12-15-00Z.json'])
        # Ended in a boundary saved meanwhile: the final duplicate check keeps the saved bytes.
        self.assertEqual(cli('2030-03-01T12:14:40Z', '2030-03-01T12:15:50Z'), (0, 'boundary already collected\n'))
        self.assertEqual(len(calls), 3)
        self.assertEqual(saved(), crossed)
        # R1: another writer saves 12:20 during a gather that ends at 12:25: both samples are kept,
        # the push lands on the moved branch, and the other writer's bytes stay as written.
        self.assertEqual(cli('2030-03-01T12:20:05Z', '2030-03-01T12:25:30Z', during='2030-03-01T12:24:50Z')[0], 0)
        moved = saved()
        self.assertEqual([name for name, _ in moved], ['samples/2030-03-01T12-%s-00Z.json' % m for m in ('05', '15', '20', '25')])
        self.assertEqual(moved[:2], crossed)
        # Another writer saves the very boundary this gather ends in: reused, never a failure.
        self.assertEqual(cli('2030-03-01T12:30:05Z', '2030-03-01T12:34:30Z', during='2030-03-01T12:34:00Z'),
                         (0, 'boundary already collected\n'))
        self.assertEqual([name for name, _ in saved()][-1], 'samples/2030-03-01T12-30-00Z.json')
        self.assertEqual(saved()[:4], moved)
        self.assertEqual(len(calls), 5)
        # A writer beating every push is retried at most three times, one gather in all; any
        # other push failure is not retried. Either way nothing new is saved.
        kept = saved()
        for refusal, tries, said in ((publish.Rejected, 3, 'git push rejected'), (publish.Fail, 1, 'git push failed')):
            with self.subTest(said):
                pushes, err = [], io.StringIO()

                def beaten(work):
                    pushes.append(work)
                    raise refusal(said)
                with patch.object(publish, 'push', beaten), contextlib.redirect_stderr(err):
                    self.assertEqual(cli('2030-03-01T12:40:05Z', '2030-03-01T12:41:00Z')[0], 1)
                self.assertEqual(len(pushes), tries)
                self.assertIn(said, err.getvalue())
                self.assertEqual(saved(), kept)
        self.assertEqual(len(calls), 7)
        # Another writer pushes between this collection's fresh fetch and its own push: git
        # refuses it as not a fast-forward, and the same gathered sample lands on the new tip.
        real_push, pushes = publish.push, []

        def raced(work):
            pushes.append(work)
            if len(pushes) == 1:
                publish.publish(str(self.origin), '2030-03-01T12:49:00Z',
                                publish.selection_reader(outs[-1] / 'root', outs[-1] / 'selection.json'), draw_page=False)
            real_push(work)
        with patch.object(publish, 'push', raced):
            self.assertEqual(cli('2030-03-01T12:45:05Z', '2030-03-01T12:50:30Z')[0], 0)
        self.assertEqual((len(pushes), len(calls)), (3, 8))  # rejected, the other writer's, the retry
        self.assertEqual([name for name, _ in saved()][-2:], ['samples/2030-03-01T12-45-00Z.json',
                                                               'samples/2030-03-01T12-50-00Z.json'])
        self.assertEqual(saved()[:5], kept)

    def test_collection_only_saves_a_sample_without_drawing(self):
        import publish
        out, at = self.gather('2030-03-01T12:05:10Z')
        reader = publish.selection_reader(out / 'root', out / 'selection.json')
        empty = self.tmp / 'nobin'
        empty.mkdir()
        with patch.dict(os.environ, {'PATH': empty.as_posix() + os.pathsep + '/usr/bin:/bin'}), \
                patch.object(publish, 'chromium', side_effect=AssertionError('collection drew a picture')), \
                patch.object(publish.main, 'tick', side_effect=AssertionError('collection rendered the page')), \
                patch.object(publish.page, 'render', side_effect=AssertionError('collection rendered the page')):
            head = publish.publish(str(self.origin), at, reader, draw_page=False)
        self.assertTrue(head)
        files = subprocess.run(['git', '-C', str(self.origin), 'ls-tree', '-r', '--name-only', 'refs/heads/war-room'],
                               check=True, capture_output=True, text=True).stdout.split()
        self.assertEqual(files, ['samples/2030-03-01T12-05-00Z.json'])
        wire = subprocess.run(['git', '-C', str(self.origin), 'show', 'refs/heads/war-room:' + files[0]],
                              check=True, capture_output=True, text=True).stdout
        self.assertEqual(suite.loads(wire)['schema'], 'openwiz.war-room.v2')

    def test_the_scheduler_invocation_collects_one_v2_sample(self):
        # The exact command the five-minute loop runs (README), on a local origin and the synthetic gh.
        # It reads the real clock, so the synthetic world is moved into the past.
        self.answers.write_text(self.answers.read_text().replace('2030-03-01T', '2020-03-01T'))
        env = dict(os.environ, **self.env)
        command = [sys.executable, '-I', str(HERE / 'publish.py'), 'collect', '--remote', str(self.origin)]
        result = subprocess.run(command + ['--gather', REPO, EVIDENCE], env=env, capture_output=True, text=True,
                                timeout=300)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith('collected into war-room at '))
        files = subprocess.run(['git', '-C', str(self.origin), 'ls-tree', '-r', '--name-only', 'refs/heads/war-room'],
                               check=True, capture_output=True, text=True).stdout.split()
        self.assertEqual(len(files), 1)
        self.assertRegex(files[0], r'^samples/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-5][05]-00Z\.json$')
        wire = subprocess.run(['git', '-C', str(self.origin), 'show', 'refs/heads/war-room:' + files[0]],
                              check=True, capture_output=True, text=True).stdout
        record = suite.loads(wire)
        h = {p['slot']: p for p in record['health']}
        self.assertEqual(h['main_ci']['observations'][0]['result'], 'success')
        self.assertEqual(by_id(h['ci_queue'])['queued:ubuntu-24.04']['value'], 1)
        # No stage directory and no journey answers: stage health names its prerequisite.
        self.assertEqual(h['stage_health']['state'], 'unavailable')
        self.assertTrue(h['stage_health']['prerequisites'])
        for bad in (['--gather', REPO, EVIDENCE, '--at', '2030-03-01T12:05:00Z'],
                    ['--gather', REPO, EVIDENCE, '--source-root', '.', '--selection', 'x.json'], []):
            with self.subTest(bad=bad):
                refused = subprocess.run(command + bad, env=env, capture_output=True, text=True, timeout=300)
                self.assertEqual((refused.returncode, refused.stdout), (1, ''))


if __name__ == '__main__':
    unittest.main()
