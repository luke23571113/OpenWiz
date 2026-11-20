#!/usr/bin/env python3
"""The OpenClaw driver, on a synthetic `acpx` (fixtures/bin/acpx) and a local tracker.

Run: python3 -I adapters/openclaw/test_driver.py   (Linux: the kit watches /proc)
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
KIT = os.path.join(HERE, '..', '..', 'kernel', 'driver-kit', 'kit.py')
# A synthetic value in a GitHub token's shape, built here so no file holds one.
TOKEN = 'gh' + 'p_' + 'Synthetic0Claw0Value' * 2 + '00'
REQUEST = {'repository': 'example/site', 'ticket': 7, 'skill': 'build-ticket', 'harness': 'claude',
           'model': 'claude-opus-5-5'}
# A driver whose next save fails once a turn has begun, as a full disk would make it.
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


def alive(pid):
    try:
        with open('/proc/%d/stat' % pid) as f:
            return f.read().rpartition(')')[2].split()[0] != 'Z'
    except OSError:
        return False


class OpenClaw(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.mark = secrets.token_hex(8)
        self.tracker = os.path.join(self.folder, 'tracker.json')
        with open(self.tracker, 'w') as f:
            json.dump({'record_authors': ['example-bot[bot]'], 'comments': []}, f)
        self.turns, self.hold = os.path.join(self.folder, 'turns'), os.path.join(self.folder, 'hold')
        self.calls = os.path.join(self.folder, 'calls')
        self.env = dict(os.environ, KIT_TRACKER=self.tracker, KIT_TEST=self.mark, GH_TOKEN=TOKEN,
                        FAKE_TURNS=self.turns, FAKE_HOLD=self.hold, FAKE_ACPX_CALLS=self.calls,
                        FAKE_ACPX_STATE=os.path.join(self.folder, 'acpx.json'),
                        OPENWIZ_OPENCLAW_STATE=os.path.join(self.folder, 'state'),
                        PATH=os.path.join(HERE, 'fixtures', 'bin') + os.pathsep + self.bare())

    def bare(self):
        """A folder holding only python3 and sleep, so no real harness or acpx on this machine ever runs."""
        bare = os.path.join(self.folder, 'bare')
        os.mkdir(bare)
        for tool in ('python3', 'sleep'):
            os.symlink(shutil.which(tool), os.path.join(bare, tool))
        return bare

    def tearDown(self):
        for pid in self.marked() + [w for _, w, _ in self.logged() if alive(w)]:
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
        """The prompts the fake acpx logged: [(prompt pid, queue owner pid, first|woken)]."""
        try:
            with open(self.turns) as f:
                return [(int(a), int(b), c) for a, b, c in (line.split() for line in f)]
        except FileNotFoundError:
            return []

    def acpx(self):
        """Every acpx call the driver made, as argument lists."""
        try:
            with open(self.calls) as f:
                return [json.loads(line) for line in f]
        except FileNotFoundError:
            return []

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
        # catches: a wake that opens a new acpx session (a second note), a stop that leaves acpx's queue owner
        # running, a token passed into the acpx processes the driver starts.
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
        # catches: a blanket --approve-all (or a policy approving `*`), a policy that prompts or approves what
        # it doesn't list, a queue owner kept alive forever (--ttl 0), a sign-in prompt instead of a failure, a
        # wake or a stop aimed at another session or folder, and any use of OpenClaw's gateway.
        code, out = self.driver('start', REQUEST)
        self.assertEqual(code, 0, out)
        self.assertTrue(self.until(lambda: self.logged() and not alive(self.logged()[0][0])))
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
            if c in calls[:3]:  # every call that can start the agent
                self.assertEqual((g['--auth-policy'], g['--non-interactive-permissions']), ('fail', 'deny'))
                policy = json.loads(g['--permission-policy'])
                self.assertEqual(policy['defaultAction'], 'deny')
                self.assertNotIn('*', policy['autoApprove'])
                self.assertIn('delete', policy['autoDeny'])
        self.assertEqual(calls[0][calls[0].index('--model') + 1], 'claude-opus-5-5')
        for c in calls[1:3]:
            self.assertTrue(0 < int(c[c.index('--ttl') + 1]) <= 300, c)

    def test_a_harness_acpx_would_run_as_a_command_is_refused(self):
        # catches: passing `harness` straight to acpx, which runs an unknown agent name as a raw command, and
        # `openclaw`, whose ACP bridge goes through the gateway.
        for harness in ('./evil', 'sh', 'openclaw'):
            with self.subTest(harness=harness):
                code, out = self.driver('start', dict(REQUEST, harness=harness))
                self.assertEqual(code, 1, out)
                self.assertIn('claude, codex', out['next'])
        self.assertEqual(self.acpx(), [])

    def test_a_start_whose_session_fails_leaves_nothing_and_repeats_no_output(self):
        # catches: a start that sends the prompt after `sessions new` failed (a missing sign-in), answers a
        # run that can be woken, or copies acpx's own output into its answer.
        code, out = self.driver('start', REQUEST, FAKE_ACPX_FAIL='new')
        self.assertEqual(code, 1, out)
        self.assertNotIn('authentication required', json.dumps(out))
        self.assertIn('signed in', out['next'])
        self.assertEqual((self.logged(), self.marked()), ([], []))
        run = re.search(r'run-[0-9a-f]{12}', out['error']).group()
        self.assertEqual(self.driver('wake', {'run': run})[0], 1)
        self.assertEqual(self.logged(), [])

    def test_a_missing_acpx_is_refused_with_how_to_install_it(self):
        # catches: a start that fails with a bare FileNotFoundError when acpx is not installed.
        code, out = self.driver('start', REQUEST, PATH=os.path.join(self.folder, 'bare'))
        self.assertEqual(code, 1, out)
        self.assertIn('npm install -g acpx', out['next'])

    def test_stop_ends_a_queue_owner_with_a_clean_environment(self):
        # catches: a stop that trusts `acpx cancel` and `sessions close` alone, or finds the run's processes
        # by the mark they inherit, so a queue owner in a clean environment keeps running after stop.
        open(self.hold, 'w').close()
        code, out = self.driver('start', REQUEST, FAKE_CLEAN='1')
        self.assertEqual(code, 0, out)
        self.assertTrue(self.until(lambda: self.logged()))
        [(prompt, owner, _)] = self.logged()
        self.assertEqual(self.driver('stop', out), (0, dict(out, stopped=True)))
        self.assertEqual((alive(prompt), alive(owner), self.marked()), (False, False, []))
        self.assertEqual(self.driver('stop', out), (0, dict(out, stopped=True)), 'stopping again answers again')

    def test_wake_while_a_prompt_runs_sends_no_second_one(self):
        # catches: a wake during a long turn queueing a second prompt behind the first, and a wake after the
        # turn ended sending nothing.
        open(self.hold, 'w').close()
        code, out = self.driver('start', REQUEST)
        self.assertEqual(code, 0, out)
        self.assertTrue(self.until(lambda: self.logged()))
        self.assertEqual(self.driver('wake', out), (0, dict(out, woke=True)))
        time.sleep(0.5)  # time for a second prompt to log itself, if one was sent
        self.assertEqual(len(self.logged()), 1, 'a wake during a running prompt sent another')
        os.remove(self.hold)
        self.assertTrue(self.until(lambda: not alive(self.logged()[0][0])))
        self.assertEqual(self.driver('wake', out), (0, dict(out, woke=True)))
        self.assertTrue(self.until(lambda: [t[2] for t in self.logged()] == ['first', 'woken']))

    def test_save_failure_after_the_prompt_reports_unknown(self):
        # catches: a start whose save fails once its prompt has begun answering the generic "retry", which
        # starts a second agent while the first runs on with no run id.
        path = os.path.join(self.folder, 'breaks')
        with open(path, 'w') as f:
            f.write('#!%s\n' % sys.executable + BREAKS_AFTER_SPAWN % DRIVER)
        os.chmod(path, 0o700)
        code, out = self.driver('start', REQUEST, program=path)
        self.assertEqual(code, 1, out)
        self.assertIn('unknown', out['error'])
        self.assertNotIn('retry', json.dumps(out))
        self.assertTrue(self.until(lambda: not self.marked()), 'the turn it could not save still runs')


if __name__ == '__main__':
    unittest.main(verbosity=2)
