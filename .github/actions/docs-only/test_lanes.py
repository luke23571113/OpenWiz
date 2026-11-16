#!/usr/bin/env python3
"""X5's real final-step adapter on synthetic GitHub needs and receipts."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


class Lanes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.receipts = self.path / 'receipts'; self.receipts.mkdir()
        self.plan = json.loads((ROOT / 'ci/selection/valid/full-nightly.json').read_text())
        raw = json.dumps(self.plan)
        self.sha = hashlib.sha256(raw.encode()).hexdigest()
        (self.path / 'ci-selection.json').write_text(raw)
        self.dispatch = {**dict.fromkeys(('build-web','lint-rust','export-rust','export-web','build-site','image-skills'), True),
                         'rust': True, 'web': True, 'site': True, 'release': True, 'toolkit': True,
                         'skills': ['launch-fleet','plan-graph','triage'], 'trace': False, 'planted': False,
                         'plan_sha256': self.sha}
        (self.path / 'ci-dispatch.json').write_text(json.dumps(self.dispatch))
        self.needs = {k: {'result': 'success'} for k in
                      ('changes','always','web-build','rust-export','web-export','site','release','skills','launch-fleet')}
        self.needs.update({k: {'result': 'skipped'} for k in ('rust','web')})
        self.expected = {k: self.plan['lanes'][k]['tests'] for k in ('always','rust','web')}
        self.expected.update(site=['site:build','site:test'], release=['release:package'])
        self.expected.update({'skill:'+s['skill']: s['tests'] for s in self.plan['lanes']['skills']})
        self.expected['prerequisite:toolkit'] = []
        self.expected['build:web_export'] = []
        for name, tests in self.expected.items():
            self.receipt(name, tests)

    def receipt(self, name, tests):
        path = self.receipts / (name.replace(':','-') + '.json')
        path.write_text(json.dumps({'lane': name, 'tests': tests, 'plan_sha256': self.sha, 'run': self.plan['run']}))
        return path

    def run_finish(self):
        (self.path / 'needs.json').write_text(json.dumps(self.needs))
        env = dict(os.environ, GITHUB_RUN_ID=str(self.plan['run']['id']),
                   GITHUB_RUN_ATTEMPT=str(self.plan['run']['attempt']), GITHUB_EVENT_NAME=self.plan['run']['event'])
        return subprocess.run([sys.executable,'-I',str(HERE/'run.py'),'finish',str(self.path),
                               str(self.path/'needs.json'),str(self.receipts)],
                              env=env,capture_output=True,text=True,timeout=10)

    def selected_site_release(self):
        self.plan['selection'] = {'mode': 'selected'}
        self.plan['run'].update(event='pull_request', action='synchronize',
                                base='1' * 40, pull_request=909)
        self.plan['diff'] = {'state': 'read', 'paths': ['apps/site/index.html']}
        raw = json.dumps(self.plan)
        self.sha = hashlib.sha256(raw.encode()).hexdigest()
        (self.path / 'ci-selection.json').write_text(raw)
        self.dispatch['plan_sha256'] = self.sha
        (self.path / 'ci-dispatch.json').write_text(json.dumps(self.dispatch))
        self.needs['site']['result'] = 'skipped'
        for name, tests in self.expected.items():
            self.receipt(name, tests)

    def test_selected_site_and_release_need_both_receipts_in_one_job(self):
        self.selected_site_release()
        result = self.run_finish()
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ('site', 'release'):
            with self.subTest(missing=name):
                path = self.receipts / (name + '.json')
                path.unlink()
                result = self.run_finish()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(name, result.stderr)
                self.receipt(name, self.expected[name])
        for state in ('failure', 'cancelled', 'skipped', None):
            with self.subTest(release=state):
                if state is None:
                    del self.needs['release']
                else:
                    self.needs['release']['result'] = state
                result = self.run_finish()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('release', result.stderr)
        self.needs['release'] = {'result': 'success'}
        self.needs['site']['result'] = 'success'
        result = self.run_finish()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('site', result.stderr)

    def test_combined_receipts_reject_omitted_work_stale_plan_and_foreign_head_attempt(self):
        self.selected_site_release()
        for field, value in [('tests', []), ('plan_sha256', '0' * 64),
                             ('head', 'f' * 40), ('attempt', 2)]:
            with self.subTest(field=field):
                path = self.receipt('site', self.expected['site'])
                entry = json.loads(path.read_text())
                if field in ('head', 'attempt'):
                    entry['run'][field] = value
                else:
                    entry[field] = value
                path.write_text(json.dumps(entry))
                result = self.run_finish()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('site', result.stderr)
        self.receipt('site', self.expected['site'])
        self.receipts.joinpath('duplicate.json').write_bytes(self.receipts.joinpath('site.json').read_bytes())
        result = self.run_finish()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('duplicate', result.stderr)

    def test_selected_release_stamp_keeps_separate_site_and_release_receipts(self):
        self.selected_site_release()
        for path in self.receipts.glob('*.json'):
            path.unlink()
        env = dict(os.environ, GITHUB_RUN_ID=str(self.plan['run']['id']),
                   GITHUB_RUN_ATTEMPT='1', GITHUB_EVENT_NAME='pull_request')
        result = subprocess.run([sys.executable, '-I', str(HERE / 'run.py'), 'stamp',
            str(self.path), 'release', str(self.receipts)], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sorted(p.name for p in self.receipts.glob('*.json')), ['release.json', 'site.json'])
        for name in ('site', 'release'):
            self.assertEqual(json.loads(self.receipts.joinpath(name + '.json').read_text()),
                {'lane': name, 'tests': self.expected[name], 'plan_sha256': self.sha, 'run': self.plan['run']})

    def test_every_planned_job_and_skill_member_passed(self):
        result = self.run_finish()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('every planned lane passed',result.stdout)

    def test_actual_job_failure_cancellation_and_absence_fail(self):
        original = json.loads(json.dumps(self.needs))
        for job in ('changes','always','web-build','rust-export','web-export','site','release','skills','launch-fleet'):
            for state in ('failure','cancelled','skipped',None):
                with self.subTest(job=job,state=state):
                    self.needs = json.loads(json.dumps(original))
                    if state is None: del self.needs[job]
                    else: self.needs[job]['result'] = state
                    result = self.run_finish()
                    self.assertEqual(result.returncode,1,result.stderr)
                    self.assertIn(job,result.stderr)

    def test_successful_matrix_aggregate_cannot_hide_a_missing_member(self):
        self.receipt('skill:plan-graph',self.expected['skill:plan-graph']).unlink()
        result = self.run_finish()
        self.assertEqual(result.returncode,1,result.stderr)
        self.assertIn('skill:plan-graph',result.stderr)

    def test_receipts_bind_the_exact_tests_and_plan(self):
        for change in ('tests','plan_sha256','run'):
            with self.subTest(change=change):
                p = self.receipt('rust',self.expected['rust'])
                entry = json.loads(p.read_text())
                entry[change] = [] if change=='tests' else ('0'*64 if change=='plan_sha256' else {})
                p.write_text(json.dumps(entry))
                result = self.run_finish()
                self.assertEqual(result.returncode,1,result.stderr)
                self.assertIn('rust',result.stderr)
                self.receipt('rust',self.expected['rust'])

    def test_dispatch_cannot_be_reused_for_different_plan_bytes(self):
        with (self.path/'ci-selection.json').open('a') as f: f.write('\n')
        result = self.run_finish()
        self.assertEqual(result.returncode,1,result.stderr)
        self.assertIn('plan',result.stderr)


    def check_shards(self, kind, records):
        paths = []
        for i, entry in enumerate(records):
            path = self.path / f'ran-{i}.json'
            path.write_text(json.dumps(entry))
            paths.append(str(path))
        env = dict(os.environ, GITHUB_RUN_ID=str(self.plan['run']['id']),
                   GITHUB_RUN_ATTEMPT=str(self.plan['run']['attempt']), GITHUB_EVENT_NAME=self.plan['run']['event'])
        return subprocess.run([sys.executable, '-I', str(HERE / 'run.py'), 'check-shards', str(self.path), kind, *paths],
                              cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)

    def test_shard_records_must_run_every_unit_once_and_add_up_to_the_total(self):
        # catches (#743): a shard that silently drops cases or units, a member
        # that never reported, a unit run twice, or a record from another plan.
        script = 'skill:launch-fleet:skills/launch-fleet/scripts/test.sh'
        def member(k, units, cases):
            return {'lane': 'skill:launch-fleet', 'shard': k, 'shards': 3, 'plan_sha256': self.sha,
                    'units': dict.fromkeys(units, 1.0), 'counts': {script: {'cases': cases, 'total': 10, 'groups': 4}}}
        others = ['skill:launch-fleet:' + p for p in ('skills/launch-fleet/test/ops-protocol/test_protocol.py',
            'skills/launch-fleet/scripts/test-effects.py', 'skills/launch-fleet/scripts/test-grants.py',
            'skills/launch-fleet/scripts/test-inbox.py', 'tools/review-relay/test_inbox.py')]
        def fleet():
            return [member(1, [script + ':group:1', script + ':group:2', *others[:2]], 5),
                    member(2, [script + ':group:3', *others[2:4]], 3),
                    member(3, [script + ':group:4', others[4]], 2)]
        result = self.check_shards('skill:launch-fleet', fleet())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('5 + 3 + 2 = 10 of 10 cases', result.stdout)
        def drop_group(r):
            del r[2]['units'][script + ':group:4']; r[2]['counts'][script]['cases'] = 0
        def short(r): r[1]['counts'][script]['cases'] = 2
        def twice(r): r[1]['units'][others[0]] = 1.0
        def missing(r): del r[2]
        def foreign(r): r[0]['plan_sha256'] = '0' * 64
        for name, change, wants in [('dropped group', drop_group, ['group:4: never ran', 'not 10']),
                                    ('short count', short, ['9 cases ran across the shards, not 10']),
                                    ('twice', twice, ['test_protocol.py: ran 2 times']),
                                    ('missing member', missing, ['shard 3 of 3 reported 0 times']),
                                    ('foreign plan', foreign, ['another lane or plan'])]:
            with self.subTest(name):
                records = fleet(); change(records)
                result = self.check_shards('skill:launch-fleet', records)
                self.assertEqual(result.returncode, 1, result.stdout)
                for want in wants:
                    self.assertIn(want, result.stderr)
        # The release lane's open-tickets parts are units too: a dropped part fails.
        self.plan['lanes']['site']['tests'] = ['site:build', 'site:test', 'release:package', 'release:open-tickets']
        raw = json.dumps(self.plan); self.sha = hashlib.sha256(raw.encode()).hexdigest()
        (self.path / 'ci-selection.json').write_text(raw)
        (self.path / 'ci-dispatch.json').write_text(json.dumps(dict(self.dispatch, plan_sha256=self.sha)))
        parts = subprocess.run(['sh', 'tools/open-tickets/test.sh', '--list'], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.split()
        units = ['release:package', *('release:open-tickets:' + p for p in parts)]
        for dropped in ([], ['release:open-tickets:carriage']):
            with self.subTest(dropped=dropped):
                ran = [u for u in units if u not in dropped]
                result = self.check_shards('release', [
                    {'lane': 'release', 'shard': k, 'shards': 2, 'plan_sha256': self.sha,
                     'units': dict.fromkeys(ran[k - 1::2], 1.0), 'counts': {}} for k in (1, 2)])
                self.assertEqual(result.returncode, 1 if dropped else 0, result.stderr)
                if dropped:
                    self.assertIn('release:open-tickets:carriage: never ran', result.stderr)


if __name__=='__main__': unittest.main()
