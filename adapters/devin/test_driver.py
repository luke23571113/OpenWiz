#!/usr/bin/env python3
"""The Devin driver on a synthetic Devin (fixtures/fake-devin), reached only through the kit's key helper.

Run: python3 -I adapters/devin/test_driver.py   (Linux: the kit watches /proc)
"""
import json
import os
import secrets
import shutil
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

ORG = 'org-syn0001'
START = {'repository': 'example/site', 'ticket': 7, 'skill': 'build-ticket', 'harness': 'devin', 'model': 'default'}
SESSIONS = '/v3/organizations/%s/sessions' % ORG


class Driver(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.tracker, self.log = os.path.join(self.folder, 'tracker.json'), os.path.join(self.folder, 'devin.log')
        self.faults = os.path.join(self.folder, 'faults.json')
        with open(self.tracker, 'w') as f:
            json.dump({'record_authors': ['example-bot[bot]'], 'comments': []}, f)
        self.fault({})
        open(self.log, 'w').close()
        self.devin = subprocess.Popen([sys.executable, '-I', os.path.join(HERE, 'fixtures', 'fake-devin'),
                                       self.tracker, self.log, self.faults], stdout=subprocess.PIPE, text=True)
        self.addCleanup(self.devin.stdout.close)
        self.addCleanup(self.devin.wait)
        self.addCleanup(self.devin.kill)
        # A synthetic key: under the loopback override the helper reads only this variable, never the real one.
        self.key = 'syn-test-key-' + secrets.token_hex(12)
        self.env = dict(os.environ, DEVIN_ORG_ID=ORG, KIT_TRACKER=self.tracker,
                        OPENWIZ_DEVIN_STATE=os.path.join(self.folder, 'state'),
                        OPENWIZ_HOSTKEY_TEST_ORIGIN=self.devin.stdout.readline().strip(),
                        OPENWIZ_HOSTKEY_TEST_KEY=self.key)

    def fault(self, faults):
        with open(self.faults, 'w') as f:
            json.dump(faults, f)

    def calls(self):
        with open(self.log) as f:
            return [json.loads(line) for line in f]

    def call(self, cmd, request, **env):
        p = subprocess.run([sys.executable, DRIVER, cmd], input=json.dumps(request), capture_output=True, text=True,
                           env=dict(self.env, **env), timeout=60)
        out = json.loads(p.stdout)
        schema = kit.load_schema()
        self.assertIsNone(kit.invalid(out, schema['commands'][cmd]['output'] if p.returncode == 0 else schema['error']))
        self.assertNotIn(self.key, p.stdout + p.stderr)
        return p.returncode, out

    def test_kit_passes_all_five_with_its_key_check(self):
        # catches: a start, wake or stop that doesn't reach Devin's session through the key helper, or a key that
        # reaches the host, an output, an argument or a variable any other way.
        p = subprocess.run([sys.executable, '-I', os.path.join(KIT, 'kit.py'), '--driver', DRIVER, '--repo',
                            'example/site', '--ticket', '7', '--harness', 'devin', '--model', 'default',
                            '--tracker', self.tracker, '--wait', '8'],
                           env=self.env, capture_output=True, text=True, timeout=300)
        self.assertEqual((p.returncode, p.stdout.splitlines()), (0, [
            'pass version: openwiz:records v1, and the schema is driver v1',
            'pass start: the run posted builder status note 1',
            'pass wake: the run edited builder status note 1',
            'pass stop: the run ended, and a wake after it is refused',
            'pass token: no login or token passed through the driver, and on start, wake and stop the devin key '
            'reached its host only from the key helper, in its header']), p.stderr)

    def test_start_wake_and_stop_are_devins_documented_calls(self):
        # catches: the wrong method, path or body, a key outside the helper's header, a run id that is not
        # Devin's session id, a wake or second stop that reaches Devin after stop, or an unknown run taken.
        code, out = self.call('start', dict(START, model='fast'))
        self.assertEqual(code, 0, out)
        run = out['run']
        self.assertRegex(run, r'^devin-[0-9a-f]{32}$')
        self.assertEqual(self.call('wake', {'run': run}), (0, {'run': run, 'woke': True}))
        self.assertEqual(self.call('stop', {'run': run}), (0, {'run': run, 'stopped': True}))
        create, message, end = self.calls()
        self.assertEqual((create['method'], create['path'], sorted(create['body'])),
                         ('POST', SESSIONS, ['devin_mode', 'prompt']))
        self.assertEqual(create['body']['devin_mode'], 'fast')
        self.assertEqual(create['body']['prompt'], 'Build the ticket: example/site#7, with the build-ticket skill.')
        self.assertEqual((message['method'], message['path'], message['body']), (
            'POST', '%s/%s/messages' % (SESSIONS, run),
            {'message': 'You were woken: read the ticket again and carry on: example/site#7, with the '
                        'build-ticket skill.'}))
        self.assertEqual((end['method'], end['path'], end['body']), ('DELETE', '%s/%s' % (SESSIONS, run), None))
        self.assertEqual({c['authorization'] for c in self.calls()}, {'Bearer ' + self.key})
        self.assertEqual(self.call('wake', {'run': run})[0], 1, 'a stopped run took a wake')
        self.assertEqual(self.call('stop', {'run': run}), (0, {'run': run, 'stopped': True}))
        self.assertEqual(self.call('wake', {'run': 'devin-' + '0' * 32})[0], 1, 'an unknown run took a wake')
        self.assertEqual(len(self.calls()), 3, 'a stopped or unknown run reached Devin')

    def test_model_harness_and_organization_are_checked_before_any_call(self):
        # catches: a model that isn't a Devin mode sent on, the default mode named, another harness taken, or a
        # start without (or with a malformed) DEVIN_ORG_ID reaching the network.
        self.assertEqual(self.call('start', START)[0], 0)
        self.assertNotIn('devin_mode', self.calls()[0]['body'])
        for request, env in ((dict(START, model='Opus 5.5'), {}), (dict(START, harness='claude'), {}),
                             (START, {'DEVIN_ORG_ID': ''}), (START, {'DEVIN_ORG_ID': 'org-x/../y'})):
            with self.subTest(request=request, env=env):
                self.assertEqual(self.call('start', request, **env)[0], 1)
        self.assertEqual(len(self.calls()), 1)

    def test_a_host_refusal_is_an_error_and_a_failed_stop_is_tried_again(self):
        # catches: a refused create saved as a run, a session id that isn't Devin's saved or shown, a failed
        # message answered as woke, or a failed terminate answered as stopped and never sent again.
        for answer in ({'status': 401, 'body': {'detail': 'synthetic refusal'}},
                       {'status': 200, 'body': {'session_id': 'ghp_' + 'Synthetic0' * 3, 'status': 'new'}},
                       {'status': 200, 'body': {'status': 'new'}}):
            with self.subTest(answer=answer):
                self.fault({'POST create': answer})
                code, out = self.call('start', START)
                self.assertEqual(code, 1, out)
                self.assertNotIn('Synthetic', json.dumps(out))
        state = self.env['OPENWIZ_DEVIN_STATE']
        self.assertEqual(os.listdir(state) if os.path.isdir(state) else [], [], 'a refused start left a run')
        self.fault({})
        run = self.call('start', START)[1]['run']
        self.fault({'POST message': {'status': 500, 'body': {}}, 'DELETE end': {'status': 500, 'body': {}}})
        self.assertEqual(self.call('wake', {'run': run})[0], 1)
        self.assertEqual(self.call('stop', {'run': run})[0], 1)
        self.fault({})
        self.assertEqual(self.call('wake', {'run': run})[0], 1, 'a run being stopped took a wake')
        self.assertEqual(self.call('stop', {'run': run}), (0, {'run': run, 'stopped': True}))
        self.assertEqual([c['method'] for c in self.calls()][-3:], ['POST', 'DELETE', 'DELETE'])


if __name__ == '__main__':
    unittest.main()
