#!/usr/bin/env python3
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
DRIVER = os.path.join(HERE, 'driver')
KIT = os.path.join(HERE, '..', '..', 'kernel', 'driver-kit', 'kit.py')
TOKEN = 'gh' + 'p_' + 'Synthetic0Factory0Value' * 2
API_KEY = 'fk' + '-synthetic0factory0value'
REAL_PROGRAMS = ('droid', 'claude', 'codex', 'gh', 'hermes', 'boat', 'cursor-agent', 'devin', 'room-cli', 'git',
                 'sh', 'sleep')
REQUEST = {'repository': 'example/site', 'ticket': 7, 'skill': 'build-ticket', 'harness': 'droid',
           'model': 'synthetic-model-1'}


def alive(pid):
    try:
        with open('/proc/%d/stat' % pid) as f:
            return f.read().rpartition(')')[2].split()[0] != 'Z'
    except OSError:
        return False


class Factory(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.mark = secrets.token_hex(8)
        self.tracker = os.path.join(self.folder, 'tracker.json')
        with open(self.tracker, 'w') as f:
            json.dump({'record_authors': ['example-bot[bot]'], 'comments': []}, f)
        self.turns = os.path.join(self.folder, 'turns')
        self.env = {'HOME': self.folder, 'LANG': 'C.UTF-8', 'KIT_TRACKER': self.tracker, 'KIT_TEST': self.mark,
                    'GH_TOKEN': TOKEN, 'FACTORY_API_KEY': API_KEY, 'FAKE_TURNS': self.turns,
                    'FAKE_FACTORY_HOME': os.path.join(self.folder, 'factory'),
                    'OPENWIZ_FACTORY_STATE': os.path.join(self.folder, 'state'),
                    'PATH': os.pathsep.join([os.path.join(HERE, 'fixtures', 'bin'), self.python()])}
        for real in REAL_PROGRAMS:
            found = shutil.which(real, path=self.env['PATH'])
            self.assertTrue(found is None or os.path.dirname(found) == os.path.join(HERE, 'fixtures', 'bin'),
                            'a real %s is reachable on the test PATH: %s' % (real, found))

    def python(self):
        only = os.path.join(self.folder, 'python-only')
        os.mkdir(only)
        os.symlink(sys.executable, os.path.join(only, 'python3'))
        return only

    def tearDown(self):
        self.addCleanup(shutil.rmtree, self.folder, True)
        for pid in self.marked():
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

    def marked(self):
        found = []
        for pid in filter(str.isdigit, os.listdir('/proc')):
            try:
                with open('/proc/%s/environ' % pid, 'rb') as f:
                    if ('KIT_TEST=' + self.mark).encode() in f.read().split(b'\0') and alive(int(pid)):
                        found.append(int(pid))
            except OSError:
                pass
        return found

    def call(self, cmd, request, **env):
        p = subprocess.run([DRIVER, cmd], input=json.dumps(request), env=dict(self.env, **env),
                           capture_output=True, text=True, timeout=60)
        return p.returncode, json.loads(p.stdout)

    def logged(self):
        try:
            with open(self.turns) as f:
                return [tuple(line.split()) for line in f]
        except FileNotFoundError:
            return []

    def test_kit_passes_all_five(self):
        p = subprocess.run([sys.executable, '-I', KIT, '--driver', DRIVER, '--repo', 'example/site',
                            '--ticket', '7', '--harness', 'droid', '--model', 'synthetic-model-1',
                            '--tracker', self.tracker, '--wait', '8'],
                           env=self.env, capture_output=True, text=True, timeout=300)
        self.assertEqual((p.returncode, p.stdout.splitlines()), (0, [
            'pass version: openwiz:records v1, and the schema is driver v1',
            'pass start: the run posted builder status note 1',
            'pass wake: the run edited builder status note 1',
            'pass stop: the run ended, and a wake after it is refused',
            'pass token: no login or token passed through the driver']), p.stderr)

    def test_other_harness_is_refused_before_anything_runs(self):
        code, out = self.call('start', dict(REQUEST, harness='claude'))
        self.assertEqual(code, 1, out)
        self.assertIn('droid', out['next'])
        time.sleep(0.5)
        self.assertEqual((self.logged(), self.marked()), ([], []))

    def test_wake_without_a_session_starts_nothing(self):
        code, out = self.call('start', REQUEST, FAKE_SIGNED_OUT='1')
        self.assertEqual(code, 0, out)
        deadline = time.monotonic() + 10
        while self.marked() and time.monotonic() < deadline:
            time.sleep(0.05)
        code, err = self.call('wake', out, FAKE_SIGNED_OUT='')
        self.assertEqual(code, 1, err)
        self.assertIn('no Droid session', err['error'])
        time.sleep(0.5)
        self.assertEqual((self.logged(), self.marked()), ([], []))


if __name__ == '__main__':
    unittest.main(verbosity=2)
