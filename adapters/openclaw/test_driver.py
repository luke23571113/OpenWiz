#!/usr/bin/env python3
import ctypes
import json
import os
import re
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
TOKEN = 'gh' + 'p_' + 'Synthetic0Claw0Value' * 2 + '00'
REAL = ('claude', 'codex', 'acpx', 'openclaw', 'gh', 'npx', 'node', 'bash', 'sh')
DIAGNOSTIC = 'synthetic acpx diagnostic'
REQUEST = {'repository': 'example/site', 'ticket': 7, 'skill': 'build-ticket', 'harness': 'claude',
           'model': 'claude-opus-5-5'}
BREAKS_AFTER_SPAWN = '''import importlib.machinery, importlib.util, os, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_loader('claw', importlib.machinery.SourceFileLoader('claw', %r))
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
launch = t.launch
def broken(req, run, woken):
    turn = launch(req, run, woken)
    os.mkdir(os.path.join(t.STATE, run + '.json.new'))
    return turn
t.launch = broken
t.main()
'''


ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0)


def alive(pid):
    try:
        with open('/proc/%d/stat' % pid) as f:
            return f.read().rpartition(')')[2].split()[0] != 'Z'
    except OSError:
        return False


def owned():
    children = {}
    for p in filter(str.isdigit, os.listdir('/proc')):
        try:
            with open('/proc/%s/stat' % p) as f:
                fields = f.read().rpartition(')')[2].split()
        except OSError:
            continue
        if fields[0] != 'Z':
            children.setdefault(int(fields[1]), []).append(int(p))
    found, todo = set(), [os.getpid()]
    while todo:
        for c in children.get(todo.pop(), []):
            if c not in found:
                found.add(c)
                todo.append(c)
    return sorted(found)


class OpenClaw(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.tracker = os.path.join(self.folder, 'tracker.json')
        with open(self.tracker, 'w') as f:
            json.dump({'record_authors': ['example-bot[bot]'], 'comments': []}, f)
        self.turns, self.hold = os.path.join(self.folder, 'turns'), os.path.join(self.folder, 'hold')
        self.calls, self.state = os.path.join(self.folder, 'calls'), os.path.join(self.folder, 'state')
        self.env = dict(HOME=self.folder, LANG='C.UTF-8', KIT_TRACKER=self.tracker, GH_TOKEN=TOKEN,
                        FAKE_TURNS=self.turns, FAKE_HOLD=self.hold, FAKE_ACPX_CALLS=self.calls,
                        FAKE_ACPX_STATE=os.path.join(self.folder, 'acpx.json'), OPENWIZ_OPENCLAW_STATE=self.state,
                        PATH=os.path.join(HERE, 'fixtures', 'bin') + os.pathsep + self.bare())
        real = [shutil.which(t, path=self.env['PATH']) for t in REAL]
        self.assertEqual([r for r in real if r and not r.startswith(os.path.join(HERE, 'fixtures'))], [],
                         'a real harness or host tool is on the test PATH')

    def bare(self):
        bare = os.path.join(self.folder, 'bare')
        os.mkdir(bare)
        for tool in ('python3', 'sleep'):
            os.symlink(shutil.which(tool), os.path.join(bare, tool))
        return bare

    def tearDown(self):
        for pid in owned():
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        while True:
            try:
                if os.waitpid(-1, os.WNOHANG) == (0, 0):
                    break
            except ChildProcessError:
                break
        shutil.rmtree(self.folder, ignore_errors=True)

    def logged(self):
        try:
            with open(self.turns) as f:
                return [(int(a), b) for a, b in (line.split() for line in f)]
        except FileNotFoundError:
            return []

    def acpx(self):
        try:
            with open(self.calls) as f:
                return [json.loads(line) for line in f]
        except FileNotFoundError:
            return []

    def kept(self, text):
        found = []
        for root, _, files in os.walk(self.state):
            for name in files:
                with open(os.path.join(root, name), 'rb') as f:
                    if text.encode() in f.read():
                        found.append(name)
        return found

    def until(self, ready):
        deadline = time.monotonic() + 10
        while not ready() and time.monotonic() < deadline:
            time.sleep(0.05)
        return ready()

    def driver(self, cmd, request, program=DRIVER, **env):
        p = subprocess.run([program, cmd], input=json.dumps(request), env=dict(self.env, **env),
                           capture_output=True, text=True, timeout=120)
        return p.returncode, json.loads(p.stdout)

    def test_kit_passes_all_five(self):
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

    def test_acpx_runs_with_a_permission_policy_and_a_short_queue_owner(self):
        code, out = self.driver('start', REQUEST)
        self.assertEqual(code, 0, out)
        self.assertTrue(self.until(lambda: len(self.logged()) == 1))
        self.assertEqual(self.driver('wake', out), (0, dict(out, woke=True)))
        self.assertTrue(self.until(lambda: len(self.logged()) == 2))
        self.assertEqual(self.driver('stop', out), (0, dict(out, stopped=True)))
        calls, run = self.acpx(), out['run']
        verbs = [c[c.index('claude') + 1:] for c in calls]
        self.assertEqual([v[:3] for v in verbs], [['sessions', 'new', '--name'], ['-s', run, '--no-wait'],
                                                  ['-s', run, '--no-wait'], ['cancel', '-s', run],
                                                  ['sessions', 'close', run]])
        self.assertEqual(verbs[0][3], run)
        for c in calls:
            g = dict(zip(c[:c.index('claude')][::2], c[:c.index('claude')][1::2]))
            self.assertNotIn('--approve-all', c)
            self.assertFalse(any('gateway' in a for a in c), c)
            self.assertEqual(g['--cwd'], dict(zip(calls[0][::2], calls[0][1::2]))['--cwd'])
            if c in calls[:3]:
                self.assertEqual((g['--auth-policy'], g['--non-interactive-permissions']), ('fail', 'deny'))
                policy = json.loads(g['--permission-policy'])
                self.assertEqual(policy['defaultAction'], 'deny')
                self.assertNotIn('*', policy['autoApprove'])
                self.assertIn('delete', policy['autoDeny'])
        self.assertEqual(calls[0][calls[0].index('--model') + 1], 'claude-opus-5-5')
        for c in calls[1:3]:
            self.assertTrue(0 < int(c[c.index('--ttl') + 1]) <= 300, c)

    def test_a_harness_acpx_would_run_as_a_command_is_refused_without_echoing_it(self):
        for harness in ('sh', 'zz-unknown-agent', 'openclaw'):
            with self.subTest(harness=harness):
                code, out = self.driver('start', dict(REQUEST, harness=harness))
                self.assertEqual(code, 1, out)
                self.assertIn('claude, codex', out['next'])
                self.assertNotIn(harness, out['error'])
        self.assertEqual(self.acpx(), [])

    def test_a_field_shaped_like_a_credential_is_refused_before_anything_keeps_it(self):
        for model in (TOKEN, 'Bear' + 'er Synthetic0Value', 'sk-' + 'Synthetic0Claw0Value00'):
            with self.subTest(model=model[:6]):
                code, out = self.driver('start', dict(REQUEST, model=model))
                self.assertEqual(code, 1, out)
                self.assertNotIn(model, json.dumps(out))
                self.assertEqual(self.kept(model), [])
        self.assertEqual(self.acpx(), [])

    def test_a_refused_prompt_fails_start_and_wake(self):
        code, out = self.driver('start', REQUEST, FAKE_ACPX_FAIL='prompt')
        self.assertEqual(code, 1, out)
        self.assertEqual((self.logged(), owned()), ([], []))
        run = re.search(r'run-[0-9a-f]{12}', out['error']).group()
        self.assertEqual(self.driver('wake', {'run': run})[0], 1)
        code, out = self.driver('start', REQUEST)
        self.assertEqual(code, 0, out)
        self.assertTrue(self.until(lambda: len(self.logged()) == 1))
        code, err = self.driver('wake', out, FAKE_ACPX_FAIL='prompt')
        self.assertEqual(code, 1, err)
        self.assertNotIn('woke', err)

    def test_a_wake_during_a_turn_reaches_the_same_session_after_acpx_acknowledged_the_first(self):
        open(self.hold, 'w').close()
        code, out = self.driver('start', REQUEST)
        self.assertEqual(code, 0, out)
        self.assertTrue(self.until(lambda: len(self.logged()) == 1))
        self.assertEqual(self.driver('wake', out), (0, dict(out, woke=True)))
        time.sleep(0.5)
        self.assertEqual(len(self.logged()), 1, 'a wake started a second turn beside the running one')
        os.remove(self.hold)
        self.assertTrue(self.until(lambda: len(self.logged()) == 2))
        [(first, a), (second, b)] = self.logged()
        self.assertEqual((first, a, b), (second, 'first', 'woken'), 'the follow-up ran in another session')
        with open(self.tracker) as f:
            self.assertEqual(len(json.load(f)['comments']), 1)

    def test_acpx_output_is_never_kept(self):
        code, out = self.driver('start', REQUEST)
        self.assertEqual(code, 0, out)
        self.assertTrue(self.until(lambda: len(self.logged()) == 1))
        self.assertEqual(self.driver('wake', out)[0], 0)
        self.assertEqual(self.driver('stop', out)[0], 0)
        code, err = self.driver('start', REQUEST, FAKE_ACPX_FAIL='new')
        self.assertEqual(code, 1, err)
        self.assertNotIn(DIAGNOSTIC, json.dumps(err))
        self.assertIn('signed in', err['next'])
        self.assertEqual(self.kept(DIAGNOSTIC), [])

    def test_an_acpx_config_that_remaps_the_harness_is_refused(self):
        os.mkdir(os.path.join(self.folder, '.acpx'))
        config = os.path.join(self.folder, '.acpx', 'config.json')
        for harness, name in (('claude', 'Claude'), ('droid', 'factory-droid')):
            with self.subTest(harness=harness):
                with open(config, 'w') as f:
                    json.dump({'agents': {name: {'argv': ['synthetic-gateway-bridge']}}}, f)
                code, out = self.driver('start', dict(REQUEST, harness=harness))
                self.assertEqual(code, 1, out)
                self.assertIn('config', out['error'])
        self.assertEqual(self.acpx(), [])
        with open(config, 'w') as f:
            json.dump({'agents': {'gemini': {'argv': ['synthetic-agent']}}}, f)
        open(self.hold, 'w').close()
        code, out = self.driver('start', REQUEST)
        self.assertEqual(code, 0, out)
        self.assertTrue(self.until(lambda: len(self.logged()) == 1))
        work = os.path.join(self.state, 'work', out['run'])
        with open(os.path.join(work, '.acpxrc.json'), 'w') as f:
            json.dump({'agents': {'claude': {'argv': ['synthetic-gateway-bridge']}}}, f)
        calls = len(self.acpx())
        code, err = self.driver('wake', out)
        self.assertEqual(code, 1, err)
        self.assertEqual(len(self.acpx()), calls, 'acpx ran with a remapped harness')
        self.assertEqual(self.driver('stop', out), (0, dict(out, stopped=True)))
        self.assertEqual(owned(), [])

    def test_a_start_whose_session_fails_leaves_nothing(self):
        code, out = self.driver('start', REQUEST, FAKE_ACPX_FAIL='new')
        self.assertEqual(code, 1, out)
        self.assertEqual((self.logged(), owned()), ([], []))
        run = re.search(r'run-[0-9a-f]{12}', out['error']).group()
        self.assertEqual(self.driver('wake', {'run': run})[0], 1)
        self.assertEqual(self.logged(), [])

    def test_a_missing_acpx_is_refused_with_how_to_install_it(self):
        code, out = self.driver('start', REQUEST, PATH=os.path.join(self.folder, 'bare'))
        self.assertEqual(code, 1, out)
        self.assertIn('npm install -g acpx', out['next'])

    def test_stop_ends_a_queue_owner_with_a_clean_environment(self):
        open(self.hold, 'w').close()
        code, out = self.driver('start', REQUEST, FAKE_CLEAN='1')
        self.assertEqual(code, 0, out)
        self.assertTrue(self.until(lambda: len(self.logged()) == 1))
        [(owner, _)] = self.logged()
        self.assertEqual(self.driver('stop', out), (0, dict(out, stopped=True)))
        self.assertEqual((alive(owner), owned()), (False, []))
        self.assertEqual(self.driver('stop', out), (0, dict(out, stopped=True)), 'stopping again answers again')

    def test_save_failure_after_the_prompt_reports_unknown(self):
        path = os.path.join(self.folder, 'breaks')
        with open(path, 'w') as f:
            f.write('#!%s\n' % sys.executable + BREAKS_AFTER_SPAWN % DRIVER)
        os.chmod(path, 0o700)
        code, out = self.driver('start', REQUEST, program=path)
        self.assertEqual(code, 1, out)
        self.assertIn('unknown', out['error'])
        self.assertNotIn('retry', json.dumps(out))
        self.assertTrue(self.until(lambda: not owned()), 'the turn it could not save still runs')


if __name__ == '__main__':
    unittest.main(verbosity=2)
