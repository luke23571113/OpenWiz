#!/usr/bin/env python3
"""#633: GitHub browser sign-in and the explicit App skip, on a recording gh.

A synthetic `gh` answers from a scenario file and logs each call, so the
proofs count real provider effects (browser sign-ins) instead of helper calls.
Nothing is signed in, sent or created; every login and repository is synthetic.

  python3 -I tools/install/setup/test_github_login.py
"""
import fcntl
import signal
import time
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
import store  # noqa: E402

TOOL = HERE / 'github_login.py'
REPOSITORY = 'synthetic-owner/synthetic-consumer'
PROJECT = {'repository': REPOSITORY, 'project': 'prj_synthetic', 'operator': 'synthetic-owner',
           'service_issue': 7, 'answer_thread': 'thr_synthetic_answer', 'harness': 'claude-code',
           'model': 'synthetic-model', 'effort': 'high', 'runtime': None}
SKIP = {'selected': 'personal_login', 'app_choice': 'skip', 'acting_login': 'synthetic-owner',
        'repository': REPOSITORY}

# The recording gh: `api user`, `api repos/<r>` and `auth login`, from scenario.json.
# Like gh, a read goes to GH_HOST when set; otherwise to github.com, unless the
# only login on the host is another server's (`enterprise_account`), which gh
# then uses as its default host. `auth login --hostname github.com` signs in
# `account`. The `pending` sign-in waits for the owner until it is killed.
FAKE_GH = r'''
import json, os, sys, time
from pathlib import Path
here = Path(os.environ['SYNTHETIC_GH_DIR'])
scenario = json.loads((here / 'scenario.json').read_text())
with open(here / 'calls.log', 'a') as log:
    log.write(' '.join(sys.argv[1:]) + '\n')
def save():
    (here / 'scenario.json').write_text(json.dumps(scenario))
args = sys.argv[1:]
if args[:2] == ['auth', 'login']:
    mode = scenario['login']
    if mode == 'pending':
        (here / 'auth.pid').write_text(str(os.getpid()))
        time.sleep(120)
        sys.exit(1)
    if mode in ('approve', 'approve_then_interrupt'):
        scenario['account'] = scenario['approve_as']
        save()
    sys.exit({'approve': 0, 'callback_only': 0, 'approve_then_interrupt': 130}.get(mode, 1))
enterprise = scenario.get('enterprise_account')
host = os.environ.get('GH_HOST') or ('github.com' if scenario['account'] is not None or enterprise is None
                                     else 'enterprise.example')
account = scenario['account'] if host == 'github.com' else enterprise
failure = scenario.get('failure')
if failure is not None:  # another failed read: gh's own error line, exit 1
    print(failure, file=sys.stderr)
    sys.exit(1)
if account is None and enterprise is not None:
    # Real gh with a credential only for another server: it asks the selected
    # host anyway, GitHub answers 401, and gh exits 1 (not 4).
    print('{"message":"Requires authentication","status":"401"}')
    print('gh: Requires authentication (HTTP 401)', file=sys.stderr)
    sys.exit(1)
if account is None:
    print('To get started with GitHub CLI, please run:  gh auth login', file=sys.stderr)
    sys.exit(4)
if args == ['api', 'user']:
    print(json.dumps({'login': account, 'type': scenario.get('type', 'User')}))
    sys.exit(0)
if len(args) == 2 and args[0] == 'api' and args[1].startswith('repos/'):
    push = scenario['push'].get(account, {}).get(args[1][len('repos/'):])
    if push is None:
        print('{"message":"Not Found"}')
        sys.exit(1)
    print(json.dumps({'full_name': args[1][len('repos/'):], 'permissions': {'push': push}}))
    sys.exit(0)
sys.exit(2)
'''


def stop_pending(gh_dir):
    """Kill the recording `gh auth login` child this test started, if any."""
    marker = gh_dir / 'auth.pid'
    if marker.exists():
        try:
            os.kill(int(marker.read_text()), signal.SIGKILL)
        except ProcessLookupError:
            pass
        marker.unlink()


def wait_for(condition, what, limit=20.0):
    deadline = time.monotonic() + limit
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError(f'timed out waiting for {what}')
        time.sleep(0.05)


class Recording(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix='openwiz-github-login-'))
        self.state = self.base / 'state'
        self.gh_dir = self.base / 'gh'
        self.gh_dir.mkdir()
        gh = self.gh_dir / 'gh'
        gh.write_text(f'#!{sys.executable} -I\n' + FAKE_GH)
        gh.chmod(0o700)
        self.env = {'PATH': f'{self.gh_dir}:/usr/bin:/bin', 'HOME': str(self.base),
                    'SYNTHETIC_GH_DIR': str(self.gh_dir), 'OPENWIZ_STATE_DIR': str(self.state)}
        self.scenario(account=None, login='approve', approve_as='synthetic-owner',
                      push={'synthetic-owner': {REPOSITORY: True}})

    def tearDown(self):
        stop_pending(self.gh_dir)  # own synthetic child only, by its recorded pid
        subprocess.run(['rm', '-rf', str(self.base)], check=True)

    def scenario(self, **values):
        (self.gh_dir / 'scenario.json').write_text(json.dumps(values))

    def update_scenario(self, **values):
        current = json.loads((self.gh_dir / 'scenario.json').read_text())
        current.update(values)
        self.scenario(**current)

    def calls(self):
        log = self.gh_dir / 'calls.log'
        return log.read_text().splitlines() if log.exists() else []

    def sign_ins(self):
        return [c for c in self.calls() if c.startswith('auth login')]

    def tool(self, *args, ok=True, env=None):
        result = subprocess.run([sys.executable, '-I', '-B', str(TOOL), *args], capture_output=True, text=True,
                                env={**self.env, **(env or {})}, stdin=subprocess.DEVNULL, timeout=60)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return json.loads(result.stdout) if ok else result.stderr

    def prepare(self):
        setup = store.Store(str(self.state))

        def change(value):
            value['project'] = dict(PROJECT)
            value['revision'] += 1
        setup.update(change)
        return setup


class SavedIdentity(unittest.TestCase):
    """catches: a saved state that selects the personal login without the
    owner's explicit skip, names no acting login, or smuggles a token-shaped
    value in, being accepted by the store the server reads."""

    def state(self, identity, omit=False):
        value = store.empty()
        value['project'] = dict(PROJECT)
        if not omit:
            value['identity'] = identity
        return value

    def test_old_and_new_saved_states(self):
        store.validate(self.state(None, omit=True))  # an old state: no selection
        store.validate(self.state(None))
        store.validate(self.state(dict(SKIP)))
        store.validate(self.state({'selected': 'unselected', 'app_choice': 'undecided', 'acting_login': None,
                                   'repository': REPOSITORY}))
        for wrong in ({**SKIP, 'app_choice': 'create'},          # personal login without the skip
                      {**SKIP, 'selected': 'unselected'},        # a skip that selects nothing
                      {**SKIP, 'selected': 'app'},               # a skip that keeps the App
                      {**SKIP, 'acting_login': None},            # the acting login unnamed
                      {**SKIP, 'acting_login': 'ghp_' + 'A' * 36},
                      {**SKIP, 'acting_login': 'synthetic/owner'},
                      {**SKIP, 'acting_login': 'x' * 40},
                      {'selected': 'app', 'app_choice': 'reuse', 'acting_login': 'synthetic-owner',
                       'repository': REPOSITORY},                # an App selection naming a login
                      {**SKIP, 'repository': 'synthetic-owner/..'},
                      {**SKIP, 'token': 'x'},
                      {k: v for k, v in SKIP.items() if k != 'repository'},
                      ['personal_login', 'skip', 'synthetic-owner', REPOSITORY],
                      {**SKIP, 'selected': 'fallback'}):
            with self.subTest(identity=wrong):
                with self.assertRaises(store.Refused):
                    store.validate(self.state(wrong))


class SignIn(Recording):
    """catches: a browser launch or callback reported as a usable login; a
    second browser flow for a repeated or resumed request; a sign-in that
    ignores an existing verified login or silently uses an environment token."""

    def test_signed_out_preview_opens_nothing_then_one_browser_sign_in_reads_back(self):
        preview = self.tool('sign-in')
        self.assertEqual(preview['code'], 'login_needed')
        self.assertTrue(any('browser' in effect for effect in preview['effects']))
        self.assertEqual(self.sign_ins(), [])
        done = self.tool('sign-in', '--yes')
        self.assertEqual((done['code'], done['login']), ('login_verified', 'synthetic-owner'))
        self.assertEqual(self.sign_ins(), ['auth login --hostname github.com --web --git-protocol https --skip-ssh-key'])
        self.assertEqual(self.calls()[-1], 'api user', 'the account is read back after the browser returns')

    def test_an_existing_login_is_reused_without_a_browser(self):
        self.update_scenario(account='synthetic-owner')
        for args in (('sign-in',), ('sign-in', '--yes')):
            result = self.tool(*args)
            self.assertEqual((result['code'], result['login']), ('login_reused', 'synthetic-owner'))
        self.assertEqual(self.sign_ins(), [])

    def test_cancellation_and_a_callback_alone_are_never_a_login(self):
        for mode, code in (('cancel', 'login_cancelled'), ('callback_only', 'login_unconfirmed')):
            with self.subTest(mode=mode):
                self.update_scenario(account=None, login=mode)
                result = self.tool('sign-in', '--yes')
                self.assertEqual((result['code'], result['login']), (code, None))

    def test_restart_after_an_interrupted_approval_reuses_it(self):
        # The owner approved in the browser, then the process was interrupted.
        self.update_scenario(login='approve_then_interrupt')
        self.assertEqual(self.tool('sign-in', '--yes')['code'], 'login_verified')
        self.assertEqual(self.tool('sign-in', '--yes')['code'], 'login_reused')
        self.assertEqual(len(self.sign_ins()), 1, 'a restart opens no second browser sign-in')

    def test_a_restart_while_approval_is_pending_starts_no_second_browser(self):
        # R2: the wrapper dies while the owner has not yet approved; its gh
        # sign-in child lives on. A resumed request reports that pending flow
        # until it ends, then a new request may start one.
        self.prepare()
        self.update_scenario(login='pending')
        wrapper = subprocess.Popen([sys.executable, '-I', '-B', str(TOOL), 'sign-in', '--yes'],
                                   env=self.env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
        marker = self.gh_dir / 'auth.pid'
        record = self.state / 'setup/github-login-pending.json'

        def recorded_child():
            if not marker.exists() or not record.exists():
                return False
            return json.loads(record.read_text())['pid'] == int(marker.read_text())

        # The child's marker precedes the wrapper's durable PID write. Killing
        # at the marker alone can leave pid=null; ageing that record would
        # legitimately expire it and start a second, pending browser flow.
        # catches: a restart starting another sign-in despite a durably recorded
        # living child, even when that child's record is older than the limit.
        try:
            wait_for(recorded_child, 'the durably recorded pending gh sign-in')
        finally:
            wrapper.kill()
            wrapper.wait()
        child = int(marker.read_text())
        os.kill(child, 0)  # the browser sign-in is still waiting for the owner
        self.assertEqual(self.tool('sign-in', '--yes')['code'], 'login_in_progress')
        # Final check R2: the record's age never outweighs a positively living
        # sign-in child; only an unprovable record ages out.
        old = record.stat().st_mtime - 3 * 3600
        os.utime(record, (old, old))
        self.assertEqual(self.tool('sign-in', '--yes')['code'], 'login_in_progress')
        self.assertEqual(len(self.sign_ins()), 1, 'no second browser sign-in while the first is pending')
        stop_pending(self.gh_dir)
        self.update_scenario(login='approve')
        self.assertEqual(self.tool('sign-in', '--yes')['code'], 'login_verified')
        self.assertEqual(len(self.sign_ins()), 2, 'once the pending flow ended, one new sign-in')

    def test_a_repeated_request_while_one_is_open_starts_no_second_browser(self):
        self.prepare()  # creates the owner-only setup directory the lock lives in
        lock = os.open(self.state / 'setup/.github-login.lock', os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self.assertEqual(self.tool('sign-in', '--yes')['code'], 'login_in_progress')
        finally:
            os.close(lock)
        self.assertEqual(self.sign_ins(), [])

    def test_an_environment_token_is_refused_not_used_as_the_browser_login(self):
        result = self.tool('sign-in', '--yes', env={'GH_TOKEN': 'synthetic-not-a-token'})
        self.assertEqual(result['code'], 'login_token_environment')
        self.assertEqual(self.calls(), [])

    def test_the_selected_repository_access_is_read_back(self):
        self.prepare()
        self.update_scenario(account='synthetic-owner')
        self.assertEqual(self.tool('sign-in')['repository'], 'identity_verified')
        self.update_scenario(push={'synthetic-owner': {REPOSITORY: False}})
        self.assertEqual(self.tool('sign-in')['repository'], 'identity_no_push')


class Packaged(Recording):
    """catches: the installed helper needing a file the package does not ship
    (the runtime's setup/ holds only setup.py, store.py and github_login.py)."""

    def test_the_helper_runs_from_the_packaged_setup_files_alone(self):
        runtime = self.base / 'runtime/setup'
        runtime.mkdir(parents=True)
        for name in ('setup.py', 'store.py', 'github_login.py'):
            (runtime / name).write_bytes((HERE / name).read_bytes())
        self.update_scenario(account='synthetic-owner')
        result = subprocess.run([sys.executable, '-I', '-B', str(runtime / 'github_login.py'), 'sign-in',
                                 '--repository', REPOSITORY], capture_output=True, text=True, env=self.env,
                                stdin=subprocess.DEVNULL, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        answer = json.loads(result.stdout)
        self.assertEqual((answer['code'], answer['repository']), ('login_reused', 'identity_verified'))


class ForeignHost(Recording):
    """R1, catches: a login on another GitHub server (GH_HOST, or gh's
    default host when it is the only login) reused as the github.com login,
    authorizing the App skip or verifying the acting identity."""

    def test_another_servers_login_never_reuses_selects_or_verifies(self):
        self.prepare()
        for env in ({'GH_HOST': 'enterprise.example'}, {}):
            with self.subTest(env=env):
                self.update_scenario(account=None, enterprise_account='synthetic-enterprise', login='approve',
                                     push={'synthetic-enterprise': {REPOSITORY: True},
                                           'synthetic-owner': {REPOSITORY: True}})
                self.assertEqual(self.tool('sign-in', env=env)['code'], 'login_needed')
                self.assertIn('identity_signed_out', self.tool('skip-app', ok=False, env=env))
                with mock.patch.dict(os.environ, {**self.env, **env}):
                    import setup
                    self.assertEqual(setup.check_identity(PROJECT, None), 'identity_signed_out')
                # The browser sign-in is github.com's; its read-back is too.
                done = self.tool('sign-in', '--yes', env=env)
                self.assertEqual((done['code'], done['login']), ('login_verified', 'synthetic-owner'))
        self.assertNotIn('identity', store.Store(str(self.state)).read())

    def test_only_githubs_own_authentication_answer_opens_the_browser_sign_in(self):
        # Final check R3: other failed reads stay refused and open nothing.
        self.prepare()
        for failure in ('gh: Server Error (HTTP 500)', 'gh: Not Found (HTTP 404)',
                        'error connecting to api.github.com', 'gh: Requires authentication (HTTP 401) via proxy'):
            with self.subTest(failure=failure):
                self.update_scenario(account=None, enterprise_account='synthetic-enterprise', failure=failure)
                self.assertEqual(self.tool('sign-in', '--yes')['code'], 'identity_unreadable')
        self.assertEqual(self.sign_ins(), [])


class SkipApp(Recording):
    """catches: an App skip saved without preview/confirmation, for an
    unverified or changed account, or lost on reload; and a check that keeps
    reporting a different signed-in account as the chosen acting login."""

    def setUp(self):
        super().setUp()
        self.setup = self.prepare()
        self.update_scenario(account='synthetic-owner')

    def test_preview_saves_nothing_then_confirmation_saves_the_choice_once(self):
        preview = self.tool('skip-app')
        self.assertEqual((preview['kind'], preview['phase']), ('connect_app', 'proposed'))
        self.assertTrue(any('synthetic-owner' in e for e in preview['effects']))
        self.assertTrue(any('no App is registered' in e for e in preview['effects']))
        before = self.setup.read()
        self.assertNotIn('identity', before)
        applied = self.tool('skip-app', '--yes', '--operation', preview['operation_id'])
        self.assertEqual(applied['phase'], 'applied')
        after = store.Store(str(self.state)).read()  # a reload reads the same choice
        self.assertEqual(after['identity'], SKIP)
        self.assertEqual(after['revision'], before['revision'] + 1, 'a new selection outdates old checks')
        again = self.tool('skip-app', '--yes', '--operation', preview['operation_id'])
        self.assertEqual(again['phase'], 'applied')
        self.assertEqual(store.Store(str(self.state)).read()['revision'], after['revision'])
        self.assertEqual(self.sign_ins(), [])

    def test_an_unverified_or_changed_account_cannot_be_chosen(self):
        self.update_scenario(push={'synthetic-owner': {REPOSITORY: False}})
        self.assertIn('identity_no_push', self.tool('skip-app', ok=False))
        self.update_scenario(push={'synthetic-owner': {REPOSITORY: True}, 'synthetic-other': {REPOSITORY: True}})
        preview = self.tool('skip-app')
        self.update_scenario(account='synthetic-other')
        self.assertIn('preview it again', self.tool('skip-app', '--yes', '--operation', preview['operation_id'],
                                                     ok=False))
        self.update_scenario(account=None)
        self.assertIn('identity_signed_out', self.tool('skip-app', ok=False))
        self.assertNotIn('identity', self.setup.read())

    def test_the_check_refuses_another_account_and_lost_access(self):
        preview = self.tool('skip-app')
        self.tool('skip-app', '--yes', '--operation', preview['operation_id'])
        patch = mock.patch.dict(os.environ, {'PATH': self.env['PATH'], 'SYNTHETIC_GH_DIR': str(self.gh_dir)})
        patch.start()
        self.addCleanup(patch.stop)
        import setup
        identity = self.setup.read()['identity']
        self.assertEqual(setup.check_identity(PROJECT, identity), 'identity_verified')
        self.assertEqual(setup.check_identity(PROJECT, None), 'identity_verified')
        self.update_scenario(account='synthetic-other', push={'synthetic-other': {REPOSITORY: True}})
        self.assertEqual(setup.check_identity(PROJECT, identity), 'identity_account_mismatch')
        self.assertEqual(setup.check_identity(PROJECT, None), 'identity_verified', 'no choice: no account bound')
        self.update_scenario(account='synthetic-owner', push={'synthetic-owner': {REPOSITORY: False}})
        self.assertEqual(setup.check_identity(PROJECT, identity), 'identity_no_push')
        other = {**PROJECT, 'repository': 'synthetic-owner/another'}
        self.update_scenario(push={'synthetic-owner': {'synthetic-owner/another': True}})
        self.assertEqual(setup.check_identity(other, identity), 'identity_verified',
                         'a choice for another repository binds nothing here')


if __name__ == '__main__':
    unittest.main()
