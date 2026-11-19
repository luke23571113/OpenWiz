#!/usr/bin/env python3
"""The local driver passes the driver kit's five checks, runs several at once, and refuses a missing harness.

Run: python3 -I adapters/local/test_driver.py   (Linux: the driver and the kit read /proc)
"""
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
DRIVER = os.path.join(HERE, 'driver')
KIT = os.path.join(HERE, '..', '..', 'kernel', 'driver-kit')
sys.path.insert(0, KIT)
import kit  # noqa: E402

# A synthetic value in a GitHub token's shape, built here so no file holds one.
TOKEN = 'gh' + 'p_' + 'Synthetic0Local0Value' * 2 + '00'
PASS = ['pass version: openwiz:records v1, and the schema is driver v1',
        'pass start: the run posted builder status note 1',
        'pass wake: the run edited builder status note 1',
        'pass stop: the run ended, and a wake after it is refused',
        'pass token: no login or token passed through the driver']


class Local(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.bin = os.path.join(self.folder, 'bin')
        os.mkdir(self.bin)
        for name in ('claude', 'codex'):
            os.symlink(os.path.join(HERE, 'fixtures', 'fake-harness'), os.path.join(self.bin, name))
        self.tracker = os.path.join(self.folder, 'tracker.json')
        with open(self.tracker, 'w') as f:
            json.dump({'record_authors': ['Example-Bot[bot]'], 'comments': []}, f)
        self.mark = secrets.token_hex(8)
        self.env = dict(os.environ, KIT_TRACKER=self.tracker, LOCAL_TEST=self.mark, GH_TOKEN=TOKEN,
                        OPENWIZ_LOCAL_STATE=os.path.join(self.folder, 'state'),
                        PATH=self.bin + os.pathsep + os.environ.get('PATH', ''))

    def tearDown(self):
        for pid in self.marked('LOCAL_TEST=' + self.mark):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        shutil.rmtree(self.folder, ignore_errors=True)

    def marked(self, entry):
        """The live processes whose environment holds this entry."""
        found = []
        for pid in filter(str.isdigit, os.listdir('/proc')):
            try:
                with open('/proc/%s/environ' % pid, 'rb') as f:
                    if entry.encode() in f.read().split(b'\0'):
                        found.append(int(pid))
            except OSError:
                pass
        return found

    def driver(self, cmd, request=None, env=None):
        p = subprocess.run([DRIVER, cmd], input='' if request is None else json.dumps(request),
                           env=env or self.env, capture_output=True, text=True, timeout=60)
        return p.returncode, json.loads(p.stdout)

    def start(self, harness='claude', env=None):
        return self.driver('start', {'repository': 'example/site', 'ticket': 7, 'skill': 'build-ticket',
                                     'harness': harness, 'model': 'synthetic-1'}, env)

    def test_kit_passes_all_five_with_each_harness(self):
        # catches: a check the driver fails on its host (a stop that leaves the harness's detached child,
        # a wake that starts nothing, a token taken), or a command line a real harness would not accept.
        for harness in ('claude', 'codex'):
            with self.subTest(harness):
                self.tearDown()
                self.setUp()
                p = subprocess.run([sys.executable, '-I', os.path.join(KIT, 'kit.py'), '--driver', DRIVER,
                                    '--repo', 'example/site', '--ticket', '7', '--harness', harness,
                                    '--model', 'synthetic-1', '--tracker', self.tracker, '--wait', '15'],
                                   env=self.env, capture_output=True, text=True, timeout=180)
                self.assertEqual((p.returncode, p.stdout.splitlines()), (0, PASS), p.stderr)

    def test_several_runs_at_once_stop_only_their_own(self):
        # catches: runs started together sharing an id or state, and a stop that ends another run's agent.
        answers = []
        threads = [threading.Thread(target=lambda: answers.append(self.start())) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual([code for code, _ in answers], [0, 0, 0], answers)
        runs = [a['run'] for _, a in answers]
        self.assertEqual(len(set(runs)), 3)
        end = time.monotonic() + 15
        while not all(self.marked('OPENWIZ_RUN=' + r) for r in runs) and time.monotonic() < end:
            time.sleep(0.1)
        self.assertTrue(all(self.marked('OPENWIZ_RUN=' + r) for r in runs))
        self.assertEqual(self.driver('stop', {'run': runs[0]}), (0, {'run': runs[0], 'stopped': True}))
        self.assertEqual(self.marked('OPENWIZ_RUN=' + runs[0]), [])
        self.assertTrue(all(self.marked('OPENWIZ_RUN=' + r) for r in runs[1:]))
        self.assertEqual(self.driver('wake', {'run': runs[1]}), (0, {'run': runs[1], 'woke': True}))
        self.assertEqual(self.driver('wake', {'run': runs[0]})[0], 1)

    def test_missing_or_unknown_harness_is_an_error_with_next(self):
        # catches: a missing harness crashing, answering a run id that never runs, or an error an agent
        # can't act on; and a harness name outside the allowlist being run from PATH.
        python = os.path.join(self.folder, 'python')  # a PATH with only python3: no harness on it
        os.mkdir(python)
        os.symlink(sys.executable, os.path.join(python, 'python3'))
        bare = dict(self.env, PATH=python)
        schema = kit.load_schema()['error']
        for harness, env, says in (('claude', bare, 'install claude'), ('codex', bare, 'install codex'),
                                   ('fake-harness', self.env, 'claude, codex')):
            with self.subTest(harness):
                code, out = self.start(harness, env)
                self.assertEqual(code, 1)
                self.assertIsNone(kit.invalid(out, schema), out)
                self.assertIn(says, out['next'])
        self.assertFalse(os.path.exists(self.env['OPENWIZ_LOCAL_STATE']) and os.listdir(self.env['OPENWIZ_LOCAL_STATE']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
