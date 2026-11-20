#!/usr/bin/env python3
"""The template driver never leaves an agent running or starts two (#1530, #1549, #1570).

Run: python3 -I adapters/template/test_driver.py   (Linux: it reads /proc)
The kit's five checks against the template are kernel/driver-kit/test_kit.py.
"""
import json
import os
import re
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
START = {'repository': 'example/site', 'ticket': 7, 'skill': 'build-ticket', 'harness': 'fake-harness',
         'model': 'Synthetic 1'}
# A driver whose next save fails once its turn has begun, as a full disk or a removed folder would make it:
# BREAK=folder replaces the state folder with a file; BREAK=write blocks only the run's next write.
BREAKS_AFTER_SPAWN = '''import importlib.machinery, importlib.util, os, shutil, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_loader('template', importlib.machinery.SourceFileLoader('template', %r))
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
launch = t.launch
def broken(req, run, woken):
    pid = launch(req, run, woken)
    if os.environ['BREAK'] == 'folder':
        shutil.rmtree(t.STATE)
        open(t.STATE, 'w').close()
    else:
        os.mkdir(os.path.join(t.STATE, run + '.json.new'))
    return pid
t.launch = broken
t.main()
'''


def alive(pid):
    try:
        with open('/proc/%d/stat' % pid) as f:
            return f.read().rpartition(')')[2].split()[0] != 'Z'
    except OSError:
        return False


class Template(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.mark = secrets.token_hex(8)
        self.turns, self.hold = os.path.join(self.folder, 'turns'), os.path.join(self.folder, 'hold')
        self.env = dict(os.environ, KIT_TEST=self.mark, FAKE_TURNS=self.turns, FAKE_HOLD=self.hold,
                        OPENWIZ_TEMPLATE_STATE=os.path.join(self.folder, 'state'),
                        PATH=os.path.join(HERE, 'fixtures') + os.pathsep + os.environ.get('PATH', ''))

    def tearDown(self):
        for pid in self.marked():
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        shutil.rmtree(self.folder, ignore_errors=True)

    def marked(self):
        """Every live process this test started, through the driver or not."""
        found = []
        for pid in filter(str.isdigit, os.listdir('/proc')):
            try:
                with open('/proc/%s/environ' % pid, 'rb') as f:
                    if ('KIT_TEST=' + self.mark).encode() in f.read().split(b'\0') and alive(int(pid)):
                        found.append(int(pid))
            except OSError:
                pass
        return found

    def call(self, cmd, request, driver=DRIVER, **env):
        p = subprocess.run([driver, cmd], input=json.dumps(request), env=dict(self.env, **env),
                           capture_output=True, text=True, timeout=60)
        return p.returncode, json.loads(p.stdout)

    def logged(self, count=None):
        """The turns the fake harness logged: [(turn pid, child pid, first|woken)], waiting for `count`."""
        deadline = time.monotonic() + 10
        while True:
            try:
                with open(self.turns) as f:
                    turns = [(int(a), int(b), c) for a, b, c in (line.split() for line in f)]
            except FileNotFoundError:
                turns = []
            if count is None or len(turns) >= count or time.monotonic() > deadline:
                return turns
            time.sleep(0.05)

    def until(self, ready):
        deadline = time.monotonic() + 10
        while not ready() and time.monotonic() < deadline:
            time.sleep(0.05)
        return ready()

    def test_stop_ends_what_the_turn_left_behind_after_it_exits(self):
        # catches: a stop that signals only the turn's own process group, after checking only the turn's
        # leader, so a worker the harness started in its own session keeps running once the leader exits
        # while stop still answers stopped (#1530).
        code, out = self.call('start', START)
        self.assertEqual(code, 0, out)
        [(turn, child, _)] = self.logged(1)
        self.assertTrue(self.until(lambda: not alive(turn)), 'the fake turn did not end')
        self.assertTrue(alive(child))
        self.assertEqual(self.call('stop', out), (0, dict(out, stopped=True)))
        self.assertEqual(self.marked(), [], 'a process the run started still runs after stop')
        self.assertEqual(self.call('stop', out), (0, dict(out, stopped=True)), 'stopping again answers again')

    def test_wake_while_a_turn_runs_starts_no_second_turn(self):
        # catches: a wake during a long turn starting a second agent on the same ticket beside the first
        # (#1549), and a wake after that turn ends starting nothing.
        open(self.hold, 'w').close()
        code, out = self.call('start', START)
        self.assertEqual(code, 0, out)
        [(turn, _, _)] = self.logged(1)
        self.assertEqual(self.call('wake', out), (0, dict(out, woke=True)))
        time.sleep(0.5)  # time for a second turn to log itself, if one was started
        self.assertEqual(len(self.logged()), 1, 'a wake during a running turn started a second turn')
        os.remove(self.hold)
        self.assertTrue(self.until(lambda: not alive(turn)), 'the fake turn did not end')
        self.assertEqual(self.call('wake', out), (0, dict(out, woke=True)))
        self.assertEqual([t[2] for t in self.logged(2)], ['first', 'woken'], 'a wake after the turn started none')

    def test_start_with_nowhere_to_save_starts_nothing(self):
        # catches: a start that launches its turn before it saves the run, then fails to save it, leaving
        # an agent running with no run id to stop it, and an error that says to retry (#1570).
        blocker = os.path.join(self.folder, 'a-file')
        open(blocker, 'w').close()
        for state in (blocker, os.path.join(blocker, 'state')):
            with self.subTest(state=state):
                code, out = self.call('start', START, OPENWIZ_TEMPLATE_STATE=state)
                self.assertEqual(code, 1, out)
                time.sleep(0.5)  # time for a turn to log itself, if one was started
                self.assertEqual((self.logged(), self.marked()), ([], []), 'it started a turn with nowhere to save')
                self.assertNotIn('retry', json.dumps(out))

    def test_save_failure_after_spawn_reports_unknown(self):
        # catches: a start whose save fails once its turn has begun answering the generic "retry", which
        # starts a second agent while the first runs on with no run id (#1570).
        driver = os.path.join(self.folder, 'breaks-after-spawn')
        with open(driver, 'w') as f:
            f.write('#!%s\n' % sys.executable + BREAKS_AFTER_SPAWN % DRIVER)
        os.chmod(driver, 0o700)
        for mode in ('folder', 'write'):
            with self.subTest(mode=mode):
                state = os.path.join(self.folder, 'state-' + mode)
                code, out = self.call('start', START, driver=driver, BREAK=mode, OPENWIZ_TEMPLATE_STATE=state)
                self.assertEqual(code, 1, out)
                self.assertIn('unknown', out['error'])
                self.assertNotIn('retry', json.dumps(out))
                self.assertTrue(self.until(lambda: not self.marked()), 'the turn it could not save still runs')
        # catches: the run's first save, still on disk, letting a wake on the run id in the error start it again.
        run = re.search(r'run-[0-9a-f]{12}', out['error']).group()
        turns = len(self.logged())
        code, _ = self.call('wake', {'run': run}, OPENWIZ_TEMPLATE_STATE=state)
        time.sleep(0.5)  # time for a turn to log itself, if one was started
        self.assertEqual((code, len(self.logged()), self.marked()), (1, turns, []), 'a wake restarted the failed run')


if __name__ == '__main__':
    unittest.main(verbosity=2)
