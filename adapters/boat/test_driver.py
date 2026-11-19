#!/usr/bin/env python3
"""D1, D2 for the boat.dev driver, on a synthetic `boat` CLI (fixtures/bin/boat) and a local tracker.

Run: python3 -I adapters/boat/test_driver.py   (Linux: the kit watches /proc)
These are fixture tests; the live run on boat.dev is recorded on the pull request.
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
KIT = os.path.join(HERE, '..', '..', 'kernel', 'driver-kit', 'kit.py')
# A synthetic value in a GitHub token's shape, built here so no file holds one.
TOKEN = 'gh' + 'p_' + 'Synthetic0Boat0Value' * 2 + '00'
REQUEST = {'repository': 'example/site', 'ticket': 7, 'skill': 'build-ticket', 'harness': 'claude',
           'model': 'claude-opus-5-5'}


class Boat(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.mark = secrets.token_hex(8)
        self.tracker = os.path.join(self.folder, 'tracker.json')
        with open(self.tracker, 'w') as f:
            json.dump({'record_authors': ['example-bot[bot]'], 'comments': []}, f)
        self.env = dict(os.environ, KIT_TRACKER=self.tracker, KIT_TEST=self.mark, GH_TOKEN=TOKEN,
                        FAKE_BOAT_STATE=os.path.join(self.folder, 'boat.json'),
                        OPENWIZ_BOAT_STATE=os.path.join(self.folder, 'state'),
                        PATH=os.path.join(HERE, 'fixtures', 'bin') + os.pathsep + os.environ.get('PATH', ''))

    def tearDown(self):
        for pid in filter(str.isdigit, os.listdir('/proc')):
            try:
                with open('/proc/%s/environ' % pid, 'rb') as f:
                    if ('KIT_TEST=' + self.mark).encode() in f.read().split(b'\0'):
                        os.kill(int(pid), signal.SIGKILL)
            except OSError:
                pass

    def driver(self, cmd, request):
        p = subprocess.run([DRIVER, cmd], input=json.dumps(request), env=self.env, capture_output=True,
                           text=True, timeout=120)
        return p.returncode, json.loads(p.stdout)

    def sandboxes(self):
        try:
            with open(self.env['FAKE_BOAT_STATE']) as f:
                return {k: v['state'] for k, v in json.load(f)['sandboxes'].items()}
        except FileNotFoundError:
            return {}

    def notes(self):
        with open(self.tracker) as f:
            return [(c['id'], c['body'].split('step: ')[1].split('\n')[0]) for c in json.load(f)['comments']]

    def test_kit_passes_all_five(self):
        # catches: a wake that opens a new boat conversation (a second note), a start that answers before
        # the agent's turn is queued, a token passed into the `boat` processes the driver starts.
        p = subprocess.run([sys.executable, '-I', KIT, '--driver', DRIVER, '--repo', 'example/site',
                            '--ticket', '7', '--harness', 'claude', '--model', 'claude-opus-5-5',
                            '--tracker', self.tracker, '--wait', '8'],
                           env=self.env, capture_output=True, text=True, timeout=300)
        self.assertEqual((p.returncode, p.stdout.splitlines()), (0, [
            'pass version: openwiz:records v1, and the schema is driver v1',
            'pass start: the run posted builder status note 1',
            'pass wake: the run edited builder status note 1',
            'pass stop: the run ended, and a wake after it is refused',
            'pass token: no login or token passed through the driver']), p.stderr)

    def test_wake_resumes_after_auto_stop_and_stop_ends_the_sandbox(self):
        # catches: a wake that fails once boat's one-hour auto-stop has stopped the sandbox, and a stop
        # that ends only the local process and leaves the sandbox running (and billing) on boat.dev.
        code, started = self.driver('start', REQUEST)
        self.assertEqual(code, 0, started)
        boxes = self.sandboxes()
        self.assertEqual(list(boxes.values()), ['running'])
        sid = next(iter(boxes))
        subprocess.run(['boat', 'stop', sid, '--json'], env=self.env, capture_output=True, check=True)
        self.assertEqual(self.driver('wake', started), (0, dict(started, woke=True)))
        self.assertEqual(self.sandboxes(), {sid: 'running'})
        self.assertEqual(self.notes(), [(1, 'woke and read the ticket again')])
        for _ in range(2):  # stopping a stopped run answers again
            self.assertEqual(self.driver('stop', started), (0, dict(started, stopped=True)))
            self.assertEqual(self.sandboxes(), {sid: 'stopped'})

    def test_a_start_that_fails_leaves_no_sandbox_running(self):
        # catches: a sandbox left running (and billing) when the agent can't start, or created for a
        # harness boat doesn't have.
        code, error = self.driver('start', dict(REQUEST, harness='fake-harness'))
        self.assertEqual((code, self.sandboxes()), (1, {}), error)
        self.assertIn('claude, codex', error['next'])
        self.env['FAKE_BOAT_PROVIDERS'] = 'codex'
        code, error = self.driver('start', REQUEST)
        self.assertEqual((code, list(self.sandboxes().values())), (1, ['stopped']), error)
        self.assertIn('provider_not_configured', error['error'])
        self.assertIn('dashboard', error['next'])


if __name__ == '__main__':
    unittest.main()
