#!/usr/bin/env python3
"""C12 switch-gate proofs. All archives, identities and runs are synthetic.

Claim CS3: main per-push full work is replaced only after the whole C11 chain
verifies at this candidate, no overload pause applies and a supported admission
mechanism exists. Anything unproven, stale, changed or unknown keeps per-push
full work. The archive is built here from C6's synthetic superseded-pending
fixtures; the private C11 bytes never reach CI.
"""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIXTURES = HERE / 'fixtures/contract'
REPOSITORY = 'synthetic/ci-example'
NIGHTLY_HEAD = '9' * 40
NIGHTLY_RUN = 9000300


def load_admit():
    spec = importlib.util.spec_from_file_location('admit', HERE / 'admit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_blob(data):
    # Git's own blob identity, computed independently of the code under test.
    return hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()


def zipped(name, text):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr(name, text)
    return buffer.getvalue()


def nightly_plan(document):
    plan = json.loads(document['plan'])
    plan['run'].update(id=NIGHTLY_RUN, attempt=1, event='schedule', base=None, head=NIGHTLY_HEAD)
    plan['selection']['reasons'] = [{'code': 'nightly'}]
    return json.dumps(plan, indent=2)


def lane_receipts(plan_text):
    """Expected nightly receipts, written from C6's documented receipt list."""
    plan = json.loads(plan_text)
    lanes, digest = plan['lanes'], hashlib.sha256(plan_text.encode()).hexdigest()
    wanted = {'always': lanes['always']['tests'], 'web': lanes['web']['tests'],
              'build:web_export': []}
    for kind in ('site', 'release'):
        tests = [t for t in lanes['site']['tests'] if t.startswith(kind + ':')]
        if tests:
            wanted[kind] = tests
    wanted.update({'skill:' + s['skill']: s['tests'] for s in lanes['skills']})
    return {lane: dict(lane=lane, tests=tests, plan_sha256=digest, run=plan['run'])
            for lane, tests in wanted.items()}


class Archive:
    """A synthetic C11-shaped private archive with its manifest and pin."""

    def __init__(self, root):
        self.root = Path(root)
        self.document = json.loads((FIXTURES / 'superseded-pending.json').read_text())
        self.context = json.loads((FIXTURES / 'superseded-pending-expected.json').read_text())
        batch = self.context['batch']
        self.files = {}
        obs = 'observation/'
        self.put(obs + 'context.json', json.dumps(self.context))
        self.put(obs + 'inventory.json', json.dumps(self.context['inventory']))
        self.put(obs + 'state.json', json.dumps(dict(
            repository=REPOSITORY, covered=batch['head'], pending=[], last=self.document)))
        self.put(obs + 'reconcile-report.json', json.dumps(dict(
            complete=True, switch_authorized=False, outcome='success', refusals=[],
            measurement=None, batch=batch, execution=self.context['execution'])))
        self.put(obs + 'reconcile-rc', 'rc=0\n')
        plan = nightly_plan(self.document)
        lanes = json.loads(plan)['lanes']
        self.nightly_inventory = [t for k in ('always', 'rust', 'web', 'site')
                                  for t in lanes[k]['tests']] + [t for s in lanes['skills'] for t in s['tests']]
        self.put(obs + 'nightly-inventory.json', json.dumps(self.nightly_inventory))
        self.put(obs + 'nightly-zips/ci-selection-1.zip', zipped('ci-selection.json', plan))
        for lane, receipt in lane_receipts(plan).items():
            name = lane.replace(':', '-')
            self.put(obs + f'nightly-zips/lane-{name}-1.zip', zipped(name + '.json', json.dumps(receipt)))
        self.put(obs + 'nightly-zips/rust-ran-1-1.zip',
                 zipped('ran-1.txt', '\n'.join(lanes['rust']['tests']) + '\n'))
        self.put(obs + 'raw/14-runN.json', json.dumps(dict(
            id=NIGHTLY_RUN, run_attempt=1, event='schedule', head_sha=NIGHTLY_HEAD, head_branch='main',
            path='.github/workflows/ci.yml', status='completed', conclusion='success')))
        self.put(obs + 'raw/15-jobsN.json', json.dumps(dict(total_count=3, jobs=[
            dict(name='changes', status='completed', conclusion='success'),
            dict(name='rust', status='completed', conclusion='skipped'),
            dict(name='ci', status='completed', conclusion='success')])))
        self.put('README.md', 'synthetic archive\n')
        self.blobs_root = self.root / 'tree'
        self.blobs = {}
        for path in ('ci/main-batch/shadow.py', 'contracts/ci-main-batch.v1.md'):
            target = self.blobs_root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            data = (ROOT / path).read_bytes()
            target.write_bytes(data)
            self.blobs[path] = git_blob(data)
        self.seal()

    def put(self, path, data):
        data = data.encode() if isinstance(data, str) else data
        target = self.root / 'archive' / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        self.files[path] = data

    def seal(self):
        lines = ''.join(f'{hashlib.sha256(data).hexdigest()}  ./{path}\n'
                        for path, data in sorted(self.files.items()))
        (self.root / 'archive/MANIFEST.sha256').write_text(lines)
        batch = self.context['batch']
        self.pin = dict(
            repository=REPOSITORY,
            manifest_sha256=hashlib.sha256(lines.encode()).hexdigest(),
            base=batch['base'], head=batch['head'],
            pull_requests=[m['pull_request'] for m in batch['members']],
            run=dict(id=self.context['execution']['id'], attempt=self.context['execution']['attempt']),
            nightly=dict(id=NIGHTLY_RUN, attempt=1, head=NIGHTLY_HEAD),
            blobs=dict(self.blobs))

    def edit(self, path, change):
        value = json.loads(self.files[path])
        change(value)
        self.put(path, json.dumps(value))
        self.seal()

    @property
    def path(self):
        return self.root / 'archive'


class Gate(unittest.TestCase):
    def setUp(self):
        self.admit = load_admit()
        self.temp = tempfile.TemporaryDirectory()
        self.archive = Archive(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def chain(self, pin=None):
        return self.admit.chain_refusals(self.archive.path, self.archive.pin if pin is None else pin,
                                         self.archive.blobs_root)

    def refuses(self, clue):
        refusals = self.chain()
        self.assertTrue(refusals, clue)
        return refusals

    # The complete synthetic chain verifies; the gate itself still stays shut.
    def test_complete_chain_verifies_but_no_mechanism_keeps_per_push_full(self):
        self.assertEqual(self.chain(), [])
        decision = self.admit.decide([], dict(allowed=True, paused=False))
        self.assertEqual(decision['admission'], 'per-push-full')
        self.assertEqual(len(decision['refusals']), 1)
        self.assertIn('no supported admission mechanism', decision['refusals'][0])


if __name__ == '__main__':
    unittest.main()
