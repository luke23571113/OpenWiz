#!/usr/bin/env python3
"""The Cloudroom driver on a synthetic room-cli (fixtures/room-cli): the kit's five checks, the wake
route the fleet's GitHub events use, and the refusals that keep a run from being claimed falsely.

Run: python3 -I adapters/cloudroom/test_driver.py   (Linux: the kit watches /proc)
"""
import json
import os
import secrets
import signal
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
DRIVER = os.path.join(HERE, 'driver')
KIT = os.path.join(HERE, '..', '..', 'kernel', 'driver-kit')
sys.path.insert(0, KIT)
import kit  # noqa: E402

TOKEN = 'gh' + 'p_' + 'Synthetic0Kit0Value' * 2 + '00'  # a token's shape, built here so no file holds one
PROJECT = 'prj_syn_0001'
START = {'repository': 'example/site', 'ticket': 7, 'skill': 'build-ticket', 'harness': 'claude', 'model': 'Opus 5.5'}


class Driver(unittest.TestCase):
    def setUp(self):
        self.folder, self.mark = tempfile.mkdtemp(), secrets.token_hex(8)
        self.log = os.path.join(self.folder, 'room.log')
        tracker = os.path.join(self.folder, 'tracker.json')
        with open(tracker, 'w') as f:
            json.dump({'record_authors': ['example-bot[bot]'], 'comments': []}, f)
        self.env = dict(os.environ, KIT_TRACKER=tracker, KIT_TEST=self.mark, GH_TOKEN=TOKEN, ROOM_PROJECT_ID=PROJECT,
                        FAKE_ROOM_LOG=self.log, OPENWIZ_CLOUDROOM_STATE=os.path.join(self.folder, 'state'),
                        PATH=os.pathsep.join([os.path.join(HERE, 'fixtures'), os.path.join(KIT, 'fixtures'),
                                              os.environ.get('PATH', '')]))

    def tearDown(self):
        for pid in filter(str.isdigit, os.listdir('/proc')):
            try:
                with open('/proc/%s/environ' % pid, 'rb') as f:
                    if ('KIT_TEST=' + self.mark).encode() in f.read().split(b'\0'):
                        os.kill(int(pid), signal.SIGKILL)
            except OSError:
                pass

    def call(self, cmd, request, **env):
        p = subprocess.run([sys.executable, DRIVER, cmd], input=json.dumps(request), env=dict(self.env, **env), capture_output=True,
                           text=True, timeout=60)
        out = json.loads(p.stdout)
        schema = kit.load_schema()
        self.assertIsNone(kit.invalid(out, schema['commands'][cmd]['output'] if p.returncode == 0 else schema['error']))
        return p.returncode, out

    def calls(self):
        with open(self.log) as f:
            return [json.loads(line) for line in f]

    def test_kit_passes_all_five(self):
        # catches: a driver whose start, wake or stop doesn't reach the run's thread, or that passes a login through.
        p = subprocess.run([sys.executable, '-I', os.path.join(KIT, 'kit.py'), '--driver', DRIVER, '--repo',
                            'example/site', '--ticket', '7', '--harness', 'fake-harness', '--model', 'Synthetic 1',
                            '--tracker', self.env['KIT_TRACKER'], '--wait', '8'],
                           env=self.env, capture_output=True, text=True, timeout=120)
        self.assertEqual((p.returncode, p.stdout.splitlines()), (0, [
            'pass version: openwiz:records v1, and the schema is driver v1',
            'pass start: the run posted builder status note 1',
            'pass wake: the run edited builder status note 1',
            'pass stop: the run ended, and a wake after it is refused',
            'pass token: no login or token passed through the driver']), p.stderr)

    def test_wake_is_the_fleet_routes_queued_delivery(self):
        # catches: a wake that steers (interrupts) instead of queueing, passes its text as an argument, answers
        # woke when Cloudroom refused the message, or reaches Cloudroom again after stop.
        code, out = self.call('start', START)
        self.assertEqual(code, 0)
        run, spawn = out['run'], self.calls()[0]
        self.assertEqual(spawn[:5] + spawn[5:9], ['thread', 'spawn', '--parent-self', '--project', PROJECT,
                                                  '--provider', 'claude-code', '--model', 'Opus 5.5'])
        thread = 'thr_syn0001'
        self.assertEqual(self.call('wake', {'run': run}), (0, {'run': run, 'woke': True}))
        tell = self.calls()[-1]
        self.assertEqual(tell[:6], ['thread', 'tell', thread, '--mode', 'queue', '--message-file'])
        self.assertEqual(len(tell), 7)
        self.assertFalse(os.path.exists(tell[6]), 'the message file is left behind')
        self.assertEqual(self.call('wake', {'run': run}, FAKE_ROOM_REFUSE='tell')[0], 1)
        self.assertEqual(self.call('stop', {'run': run}, FAKE_ROOM_REFUSE='archive')[0], 1)
        self.assertEqual(self.call('wake', {'run': run})[0], 0, 'a failed stop must leave the run live')
        self.assertEqual(self.call('stop', {'run': run}), (0, {'run': run, 'stopped': True}))
        self.assertEqual(self.calls()[-1], ['thread', 'archive', thread])
        before = len(self.calls())
        self.assertEqual(self.call('wake', {'run': run})[0], 1)
        self.assertEqual(self.call('stop', {'run': run}), (0, {'run': run, 'stopped': True}))
        self.assertEqual(len(self.calls()), before, 'a stopped run reached Cloudroom again')

    def test_start_refuses_a_run_cloudroom_did_not_make(self):
        # catches: a run id answered for a thread that doesn't exist, isn't safe to address, or is in another
        # project; and a missing project or room-cli reported as a crash instead of an error with next.
        receipt = {'id': 'thr_syn0001', 'projectId': PROJECT}
        cases = {'no project': {'ROOM_PROJECT_ID': ''}, 'no room-cli': {'PATH': os.path.join(KIT, 'fixtures')},
                 'refused': {'FAKE_ROOM_REFUSE': 'spawn'}, 'not JSON': {'FAKE_ROOM_RECEIPT': 'Synthetic text'},
                 'no id': {'FAKE_ROOM_RECEIPT': json.dumps({'projectId': PROJECT})},
                 'unsafe id': {'FAKE_ROOM_RECEIPT': json.dumps(dict(receipt, id='thr_syn; rm -rf ~'))},
                 'other project': {'FAKE_ROOM_RECEIPT': json.dumps(dict(receipt, projectId='prj_syn_0002'))}}
        for name, env in cases.items():
            with self.subTest(name):
                self.assertEqual(self.call('start', START, **env)[0], 1)
                self.assertFalse(os.listdir(self.env['OPENWIZ_CLOUDROOM_STATE'])
                                 if os.path.isdir(self.env['OPENWIZ_CLOUDROOM_STATE']) else [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
