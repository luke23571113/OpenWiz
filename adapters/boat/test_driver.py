#!/usr/bin/env python3
"""D1, D2 for the boat.dev driver, on a synthetic `boat` CLI (fixtures/bin/boat) and a local tracker.

Run: python3 -I adapters/boat/test_driver.py   (Linux: the kit watches /proc)
These are fixture tests; the live run on boat.dev is recorded on the pull request.
"""
import json
import os
import re
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
# A synthetic value in a GitHub token's shape, built here so no file holds one.
TOKEN = 'gh' + 'p_' + 'Synthetic0Boat0Value' * 2 + '00'
# A driver whose next save fails once a turn's `boat prompt` has begun, as a full disk would make it.
BREAKS_AFTER_SPAWN = '''import importlib.machinery, importlib.util, os, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_loader('boat', importlib.machinery.SourceFileLoader('boat', %r))
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
prompt = t.prompt
def broken(state, run, *rest):
    out = prompt(state, run, *rest)
    os.mkdir(os.path.join(t.STATE, run + '.json.new'))
    return out
t.prompt = broken
t.main()
'''
# A driver whose wake pauses once it reads the sandbox's state, until the file named by RELEASE exists.
PAUSES_IN_WAKE = '''import importlib.machinery, importlib.util, os, sys, time
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_loader('boat', importlib.machinery.SourceFileLoader('boat', %r))
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
sandbox_state = t.sandbox_state
def paused(*args):
    answer = sandbox_state(*args)
    open(os.environ['PAUSED'], 'w').close()
    while not os.path.exists(os.environ['RELEASE']):
        time.sleep(0.01)
    return answer
t.sandbox_state = paused
t.main()
'''
REQUEST = {'repository': 'example/site', 'ticket': 7, 'skill': 'build-ticket', 'harness': 'claude',
           'model': 'claude-opus-5-5'}


def alive(pid):
    try:
        with open('/proc/%d/stat' % pid) as f:
            return f.read().rpartition(')')[2].split()[0] != 'Z'
    except OSError:
        return False


class Boat(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.mark = secrets.token_hex(8)
        self.tracker = os.path.join(self.folder, 'tracker.json')
        with open(self.tracker, 'w') as f:
            json.dump({'record_authors': ['example-bot[bot]'], 'comments': []}, f)
        self.turns, self.hold = os.path.join(self.folder, 'turns'), os.path.join(self.folder, 'hold')
        self.env = dict(os.environ, KIT_TRACKER=self.tracker, KIT_TEST=self.mark, GH_TOKEN=TOKEN,
                        FAKE_TURNS=self.turns, FAKE_HOLD=self.hold,
                        FAKE_BOAT_STATE=os.path.join(self.folder, 'boat.json'),
                        OPENWIZ_BOAT_STATE=os.path.join(self.folder, 'state'),
                        PATH=os.path.join(HERE, 'fixtures', 'bin') + os.pathsep + os.environ.get('PATH', ''))

    def tearDown(self):
        for pid in self.marked() + [w for _, w, _, _ in self.logged() if alive(w)]:
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

    def logged(self):
        """The turns the fake `boat prompt` logged: [(prompt pid, worker pid, conversation, first|woken)]."""
        try:
            with open(self.turns) as f:
                return [(int(a), int(b), c, d) for a, b, c, d in (line.split() for line in f)]
        except FileNotFoundError:
            return []

    def until(self, ready):
        deadline = time.monotonic() + 10
        while not ready() and time.monotonic() < deadline:
            time.sleep(0.05)
        return ready()

    def wrapper(self, name, source):
        path = os.path.join(self.folder, name)
        with open(path, 'w') as f:
            f.write('#!%s\n' % sys.executable + source % DRIVER)
        os.chmod(path, 0o700)
        return path

    def driver(self, cmd, request, program=DRIVER, **env):
        p = subprocess.run([program, cmd], input=json.dumps(request), env=dict(self.env, **env),
                           capture_output=True, text=True, timeout=120)
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

    def test_stop_ends_a_worker_the_prompt_left_in_a_clean_environment(self):
        # catches: a stop that signals only the `boat prompt` process group, or finds processes only by the
        # mark they inherit, so a worker the CLI left in its own session keeps running after stop (R2).
        code, out = self.driver('start', REQUEST, FAKE_CLEAN='1')
        self.assertEqual(code, 0, out)
        self.assertTrue(self.until(lambda: len(self.logged()) == 1 and not alive(self.logged()[0][0])))
        worker = self.logged()[0][1]
        self.assertTrue(alive(worker))
        self.assertEqual(self.driver('stop', out), (0, dict(out, stopped=True)))
        self.assertFalse(alive(worker), 'a worker the prompt left still runs after stop')

    def test_simultaneous_wakes_start_one_turn(self):
        # catches: two wakes that both pass their checks before either saves its turn, so both run
        # `boat prompt` and two turns work the ticket at once (R1), and a wake during a running turn adding one.
        code, out = self.driver('start', REQUEST)
        self.assertEqual(code, 0, out)
        self.assertTrue(self.until(lambda: len(self.logged()) == 1 and not alive(self.logged()[0][0])))
        open(self.hold, 'w').close()
        paused, release = os.path.join(self.folder, 'paused'), os.path.join(self.folder, 'release')
        first = subprocess.Popen([self.wrapper('pauses', PAUSES_IN_WAKE), 'wake'], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, env=dict(self.env, PAUSED=paused, RELEASE=release))
        first.stdin.write(json.dumps(out).encode())
        first.stdin.close()
        self.assertTrue(self.until(lambda: os.path.exists(paused)), 'the first wake never reached its pause')
        second = subprocess.Popen([DRIVER, 'wake'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=self.env)
        second.stdin.write(json.dumps(out).encode())
        second.stdin.close()
        try:  # without a lock the second wake finishes now; with one it waits for the first
            second.wait(3)
        except subprocess.TimeoutExpired:
            pass
        open(release, 'w').close()
        answers = [json.loads(p.stdout.read()) for p in (first, second)]
        self.assertEqual(([p.wait(60) for p in (first, second)], answers), ([0, 0], [dict(out, woke=True)] * 2))
        time.sleep(0.5)  # time for a second turn to log itself, if one was started
        self.assertEqual([t[3] for t in self.logged()], ['first', 'woken'], 'two wakes ran two turns')

    def test_stop_ends_the_run_when_it_cannot_save(self):
        # catches: a stop whose save fails before it ends anything, answering "retry" while the turn and the
        # sandbox keep running, and a wake that then runs another turn (R3).
        open(self.hold, 'w').close()
        code, out = self.driver('start', REQUEST)
        self.assertEqual(code, 0, out)
        os.mkdir(os.path.join(self.folder, 'state', out['run'] + '.json.new'))
        code, err = self.driver('stop', out)
        self.assertEqual(code, 1, err)
        self.assertNotIn('retry', json.dumps(err))
        self.assertEqual((self.marked(), list(self.sandboxes().values())), ([], ['stopped']), 'stop left it working')
        code, err = self.driver('wake', out)
        self.assertEqual((code, len(self.logged()), self.marked()), (1, 1, []), 'a wake ran it again')

    def test_wake_checks_its_save_before_and_after_spawn(self):
        # catches: a wake that runs `boat prompt` before it knows it can save the turn, and a save failure
        # after it answering "retry" while the unsaved turn keeps working (R4).
        code, out = self.driver('start', REQUEST)
        self.assertEqual(code, 0, out)
        self.assertTrue(self.until(lambda: len(self.logged()) == 1 and not alive(self.logged()[0][0])))
        blocked = os.path.join(self.folder, 'state', out['run'] + '.json.new')
        os.mkdir(blocked)
        code, err = self.driver('wake', out)
        self.assertEqual((code, len(self.logged())), (1, 1), 'a wake ran a turn with nowhere to save it')
        self.assertIn('nothing was started', err['error'])
        self.assertNotIn('retry', json.dumps(err))
        os.rmdir(blocked)
        open(self.hold, 'w').close()
        before = set(self.marked())  # the first turn's worker still runs
        code, err = self.driver('wake', out, program=self.wrapper('breaks', BREAKS_AFTER_SPAWN))
        self.assertEqual(code, 1, err)
        self.assertIn('unknown', err['error'])
        self.assertNotIn('retry', json.dumps(err))
        self.assertTrue(self.until(lambda: set(self.marked()) <= before), 'the unsaved turn still runs')

    def test_a_start_not_fully_saved_is_never_woken(self):
        # catches: a start whose last save fails after its turn began answering "retry", leaving the turn and
        # the sandbox running, and a wake on the surviving record opening a second conversation (R5).
        code, out = self.driver('start', REQUEST, program=self.wrapper('breaks', BREAKS_AFTER_SPAWN))
        self.assertEqual(code, 1, out)
        self.assertIn('unknown', out['error'])
        self.assertNotIn('retry', json.dumps(out))
        self.assertTrue(self.until(lambda: not self.marked()), 'the turn it could not save still runs')
        self.assertEqual(list(self.sandboxes().values()), ['stopped'])
        os.rmdir(os.path.join(self.folder, 'state', re.search(r'run-[0-9a-f]{12}', out['error']).group() + '.json.new'))
        code, _ = self.driver('wake', {'run': re.search(r'run-[0-9a-f]{12}', out['error']).group()})
        self.assertEqual((code, [t[2] for t in self.logged()]), (1, ['c1']), 'a wake reopened the failed run')


if __name__ == '__main__':
    unittest.main()
