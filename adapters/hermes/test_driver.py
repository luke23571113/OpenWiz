#!/usr/bin/env python3
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

    def driver(self, cmd, request, **env):
        p = subprocess.run([DRIVER, cmd], input=json.dumps(request), env=dict(self.env, **env),
                           capture_output=True, text=True, timeout=120)
        return p.returncode, json.loads(p.stdout)

    def logged(self):
        try:
            with open(self.turns) as f:
                return [(int(a), int(b), c, d, json.loads(e)) for a, b, c, d, e in
                        (line.rstrip('\n').split(' ', 4) for line in f)]
        except FileNotFoundError:
            return []

    def notes(self):
        with open(self.tracker) as f:
            return [(c['id'], c['body'].split('step: ')[1].split('\n')[0]) for c in json.load(f)['comments']]

    def test_wake_resumes_the_session_its_start_reported(self):
        for harness, skill in (('claude', 'claude-code'), ('codex', 'codex')):
            with self.subTest(harness=harness):
                code, out = self.driver('start', dict(REQUEST, harness=harness))
                self.assertEqual(code, 0, out)
                self.assertTrue(self.until(lambda: not alive(self.logged()[-1][0])), 'the first turn never ended')
                self.assertEqual(self.driver('wake', out), (0, dict(out, woke=True)))
                self.assertTrue(self.until(lambda: len(self.logged()) % 2 == 0), 'the wake started no turn')
                first, woken = self.logged()[-2:]
                self.assertEqual((first[3], woken[3], woken[2]), ('first', 'woken', first[2]))
                self.assertEqual(woken[4][woken[4].index('--resume') + 1], first[2])
                for argv in (first[4], woken[4]):
                    self.assertEqual(argv[argv.index('-s') + 1], skill)
                    self.assertNotIn('-m', argv)
                    self.assertIn('the model synthetic-model-1', argv[-1])
                self.assertEqual(self.notes()[-1][1], 'woke and read the ticket again')
        self.assertEqual(len(self.notes()), 2, 'a wake posted a second note')
        code, out = self.driver('start', dict(REQUEST, harness='hermes'))
        self.assertEqual(code, 0, out)
        argv = self.until(lambda: len(self.logged()) == 5) and self.logged()[-1][4]
        self.assertEqual((argv[argv.index('-m') + 1], '-s' in argv), ('synthetic-model-1', False))

    def test_stop_interrupts_the_turn_then_ends_everything(self):
        open(self.hold, 'w').close()
        code, out = self.driver('start', REQUEST)
        self.assertEqual(code, 0, out)
        self.assertTrue(self.until(lambda: self.logged()), 'the turn never began')
        self.assertEqual(self.driver('stop', out), (0, dict(out, stopped=True)))
        self.assertEqual([t[3] for t in self.logged()], ['first', 'interrupted'], 'stop never interrupted Hermes')
        self.assertEqual(self.marked(), [], 'a process the run started still runs after stop')
        self.assertEqual([n for n in os.listdir(self.env['OPENWIZ_HERMES_STATE']) if n.endswith('.log')], [])
        self.assertEqual(self.driver('wake', out)[0], 1, 'a wake after stop was not refused')

    def test_a_start_without_a_session_starts_nothing_wakeable(self):
        code, out = self.driver('start', REQUEST, FAKE_NO_INIT='1')
        self.assertEqual(code, 1, out)
        self.assertIn('did not report a session', out['error'])
        self.assertTrue(self.until(lambda: not self.marked()), 'its turn still runs')
        run = out['error'].split('run ')[1].split(',')[0]
        self.assertEqual(self.driver('wake', {'run': run})[0], 1)
        self.assertEqual(len(self.logged()), 1, 'a wake started the failed run')

    def test_a_start_it_cannot_run_starts_nothing(self):
        code, out = self.driver('start', dict(REQUEST, harness='pi'))
        self.assertEqual((code, out['next']), (1, 'use one of: claude, codex, hermes'))
        code, out = self.driver('start', REQUEST, PATH='/usr/bin:/bin')
        self.assertEqual((code, out['error']), (1, 'hermes is not installed here'))
        self.assertEqual((self.logged(), self.marked()), ([], []))


if __name__ == '__main__':
    unittest.main(verbosity=2)
