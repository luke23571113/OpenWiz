#!/usr/bin/env python3
"""The Hermes driver passes the kit's five checks on a synthetic `hermes` CLI (fixtures/bin/hermes) and a local
tracker.

Run: python3 -I adapters/hermes/test_driver.py   (Linux: the kit watches /proc)
PATH is only fixtures/bin, /usr/bin and /bin, so no real `hermes`, `claude` or `codex` is ever reached.
"""
import json
import os
import secrets
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
# Synthetic values in a GitHub token's shape and in Hermes' API key's place, built here so no file holds one.
TOKEN = 'gh' + 'p_' + 'Synthetic0Hermes0Value' * 2
API_KEY = 'synthetic-' + 'hermes-api-server-value'
REQUEST = {'repository': 'example/site', 'ticket': 7, 'skill': 'build-ticket', 'harness': 'claude',
           'model': 'synthetic-model-1'}


def alive(pid):
    try:
        with open('/proc/%d/stat' % pid) as f:
            return f.read().rpartition(')')[2].split()[0] != 'Z'
    except OSError:
        return False


class Hermes(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.mark = secrets.token_hex(8)
        self.tracker = os.path.join(self.folder, 'tracker.json')
        with open(self.tracker, 'w') as f:
            json.dump({'record_authors': ['example-bot[bot]'], 'comments': []}, f)
        self.turns, self.hold = os.path.join(self.folder, 'turns'), os.path.join(self.folder, 'hold')
        self.env = {'HOME': self.folder, 'LANG': 'C.UTF-8', 'KIT_TRACKER': self.tracker, 'KIT_TEST': self.mark,
                    'GH_TOKEN': TOKEN, 'API_SERVER_KEY': API_KEY, 'FAKE_TURNS': self.turns,
                    'FAKE_HOLD': self.hold, 'FAKE_HERMES_HOME': os.path.join(self.folder, 'hermes'),
                    'OPENWIZ_HERMES_STATE': os.path.join(self.folder, 'state'),
                    'PATH': os.pathsep.join([os.path.join(HERE, 'fixtures', 'bin'), '/usr/bin', '/bin'])}

    def tearDown(self):
        for pid in self.marked():
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

    def marked(self):
        """Every live process this test started that still carries its mark."""
        found = []
        for pid in filter(str.isdigit, os.listdir('/proc')):
            try:
                with open('/proc/%s/environ' % pid, 'rb') as f:
                    if ('KIT_TEST=' + self.mark).encode() in f.read().split(b'\0') and alive(int(pid)):
                        found.append(int(pid))
            except OSError:
                pass
        return found

    def until(self, ready):
        deadline = time.monotonic() + 10
        while not ready() and time.monotonic() < deadline:
            time.sleep(0.05)
        return ready()

    def test_kit_passes_all_five(self):
        # catches: a start that answers before Hermes has a session, a wake that opens a new session (a second
        # note), a stop that leaves the turn's processes running, and a key or token passed into a process the
        # driver starts.
        p = subprocess.run([sys.executable, '-I', KIT, '--driver', DRIVER, '--repo', 'example/site',
                            '--ticket', '7', '--harness', 'claude', '--model', 'synthetic-model-1',
                            '--tracker', self.tracker, '--wait', '8'],
                           env=self.env, capture_output=True, text=True, timeout=300)
        self.assertEqual((p.returncode, p.stdout.splitlines()), (0, [
            'pass version: openwiz:records v1, and the schema is driver v1',
            'pass start: the run posted builder status note 1',
            'pass wake: the run edited builder status note 1',
            'pass stop: the run ended, and a wake after it is refused',
            'pass token: no login or token passed through the driver']), p.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
