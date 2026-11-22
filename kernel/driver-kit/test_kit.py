#!/usr/bin/env python3
import importlib.machinery
import importlib.util
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, 'fixtures')
TEMPLATE = os.path.join(HERE, '..', '..', 'adapters', 'template', 'driver')
NO_PROC = os.path.join(HERE, '..', '..', 'kernel', 'driver-kit', 'fixtures', 'no-proc')
REPO = os.path.realpath(os.path.join(HERE, '..', '..'))
HARNESSES = ('claude', 'claude-code', 'codex', 'gemini', 'opencode', 'openclaw', 'cursor-agent', 'amp', 'aider', 'goose')
TOOLS = ('sh', 'ps', 'lsof', 'awk', 'sleep', 'dirname', 'true')
TOKEN = 'gh' + 'p_' + 'Synthetic0Kit0Value' * 2 + '00'
PASS = ['pass version: openwiz:records v1, and the schema is driver v1',
        'pass start: the run posted builder status note 2',
        'pass wake: the run edited builder status note 2',
        'pass stop: the run ended, and a wake after it is refused',
        'pass token: no login or token passed through the driver']
PLANTED = {
    'token-in-args': PASS[:4] + ['fail token: a process the driver started holds a credential on its command line'],
    'token-in-env': PASS[:4] + ['fail token: a process the driver started holds a credential in OPENWIZ_GITHUB, '
                                'which the kit never gave it'],
    'echoes-token': PASS[:4] + ['fail token: the driver printed a credential'],
    'takes-token': PASS[:4] + ['fail token: start took a token field instead of refusing it'],
    'stop-leaves-run': PASS[:3] + ['fail stop: a process the run started still runs after stop', PASS[4]],
    'wake-does-nothing': PASS[:2] + ['fail wake: builder status note 2 did not change after the wake'] + PASS[3:],
    'old-records': ['fail version: it names no openwiz:records v1'] + PASS[1:],
    'error-without-next': PASS[:3] + ['fail stop: next is not a string',
                                      'fail token: its answer to a token field: next is not a string'],
}


CONTRACT_FORMATS = ['token=', 'key=', 'secret=', 'password=', 'sig=', 'password:', 'Bearer', 'gh?_', 'github_pat_',
                    'AKIA', 'xox?-', 'sk-']


def planted(name):
    return module(os.path.join(FIXTURES, 'planted', name))


def module(path):
    name = os.path.basename(path)
    spec = importlib.util.spec_from_loader(name, importlib.machinery.SourceFileLoader(name, path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pinned_path(folder, *fixtures):
    """The tests' PATH: the fixtures, then a folder of only the system tools they run, never the caller's PATH,
    where a real harness may be installed (#2023)."""
    tools = os.path.join(folder, 'tools')
    os.makedirs(tools)
    for name in TOOLS:
        if shutil.which(name):
            os.symlink(shutil.which(name), os.path.join(tools, name))
    os.symlink(sys.executable, os.path.join(tools, 'python3'))
    return no_real_harness(os.pathsep.join(fixtures + (tools,)))


def no_real_harness(path):
    for name in HARNESSES:
        found = shutil.which(name, path=path)
        if found and not os.path.realpath(found).startswith(REPO + os.sep):
            raise AssertionError('%s on the PATH is %s, outside the fixtures: a test could launch a real harness'
                                 % (name, found))
    return path


def tracker(folder):
    path = os.path.join(folder, 'tracker.json')
    old = '<!-- openwiz:status v1 -->\nagent: builder\nstate: stopped\nharness: Fake\nmodel: m\n' \
          'skills: build-ticket@0.1.2\nstep: an earlier run\ntime: 2030-01-02T03:04:05Z\n'
    with open(path, 'w') as f:
        json.dump({'record_authors': ['Example-Bot[bot]'], 'comments': [
            {'id': 1, 'author': 'example-bot[bot]', 'updated_at': '2030-01-02T03:04:05Z', 'body': old}]}, f)
    return path


class Kit(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.mark = secrets.token_hex(8)
        self.env = dict(os.environ, KIT_TRACKER=tracker(self.folder), KIT_TEST=self.mark, GH_TOKEN=TOKEN,
                        OPENWIZ_TEMPLATE_STATE=os.path.join(self.folder, 'state'),
                        PATH=pinned_path(self.folder, FIXTURES))

    def left(self):
        found = []
        for pid in filter(str.isdigit, os.listdir('/proc')):
            try:
                with open('/proc/%s/environ' % pid, 'rb') as f:
                    if ('KIT_TEST=' + self.mark).encode() in f.read().split(b'\0'):
                        found.append(int(pid))
            except OSError:
                pass
        return found

    def tearDown(self):
        for pid in self.left():
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

    def kit(self, driver, python=sys.executable, wait='8', **env):
        env = dict(self.env, **env)
        no_real_harness(env['PATH'])
        p = subprocess.run([python, '-I', os.path.join(HERE, 'kit.py'), '--driver', driver,
                            '--repo', 'example/site', '--ticket', '7', '--harness', 'fake-harness',
                            '--model', 'Synthetic 1', '--tracker', self.env['KIT_TRACKER'], '--wait', wait],
                           env=env, capture_output=True, text=True, timeout=120)
        return p.returncode, p.stdout.splitlines(), p.stderr

    def test_template_passes_all_five(self):
        self.assertEqual(self.kit(TEMPLATE)[:2], (0, PASS))

    def test_without_proc_as_on_macos_the_template_passes_all_five(self):
        macos = {'PATH': NO_PROC + os.pathsep + self.env['PATH'], 'NO_PROC_PYTHON': sys.executable}
        self.assertEqual(self.kit(TEMPLATE, os.path.join(NO_PROC, 'python3'), **macos)[:2], (0, PASS))
        for name in ('stop-leaves-run', 'token-in-env'):
            with self.subTest(name):
                self.tearDown()
                self.setUp()
                macos['PATH'] = NO_PROC + os.pathsep + self.env['PATH']
                code, out, err = self.kit(os.path.join(FIXTURES, 'planted', name), os.path.join(NO_PROC, 'python3'),
                                          **macos)
                self.assertEqual((code, out), (1, PLANTED[name]), err)
        self.tearDown()
        self.setUp()
        spaced = dict(macos, PATH=NO_PROC + os.pathsep + self.env['PATH'], GH_TOKEN='Bearer ' + TOKEN[4:])
        code, out, err = self.kit(os.path.join(FIXTURES, 'planted', 'token-in-env'), os.path.join(NO_PROC, 'python3'),
                                  **spaced)
        self.assertEqual((code, out), (1, PLANTED['token-in-env']), err)

    def test_without_proc_as_on_macos_a_driver_whose_run_stays_in_the_kits_group_passes_all_five(self):
        macos = {'PATH': NO_PROC + os.pathsep + self.env['PATH'], 'NO_PROC_PYTHON': sys.executable,
                 'FAKE_SAME_GROUP': '1'}
        code, out, err = self.kit(os.path.join(FIXTURES, 'same-group-driver'), os.path.join(NO_PROC, 'python3'),
                                  **macos)
        self.assertEqual((code, out), (0, PASS), err)

    def test_the_kits_visibility_probe_signals_ready_through_the_macos_shim_and_runs_until_its_stdin_closes(self):
        p = subprocess.run([os.path.join(NO_PROC, 'python3')] + module(os.path.join(HERE, 'kit.py')).PROBE,
                           input='', env=dict(self.env, NO_PROC_PYTHON=sys.executable), capture_output=True,
                           text=True, timeout=60)
        self.assertEqual((p.returncode, p.stdout, p.stderr), (0, '.', ''))

    def test_without_proc_or_the_runs_visible_environment_stop_and_token_fail_unverified(self):
        cases = {'NO_PROC_HIDE_ENV': "ps shows no process's environment here, so the kit cannot tell which "
                                     "processes the driver started",
                 'NO_PROC_PROBE_ONLY': "ps -E never showed a process of this run, so the kit cannot tell which "
                                       "processes the driver started"}
        for hide, why in cases.items():
            for name in ('template', 'stop-leaves-run', 'token-in-env'):
                with self.subTest(hide=hide, driver=name):
                    self.tearDown()
                    self.setUp()
                    driver = TEMPLATE if name == 'template' else os.path.join(FIXTURES, 'planted', name)
                    code, out, err = self.kit(driver, os.path.join(NO_PROC, 'python3'), **{hide: '1'},
                                              PATH=NO_PROC + os.pathsep + self.env['PATH'],
                                              NO_PROC_PYTHON=sys.executable)
                    self.assertEqual((code, out), (1, PASS[:3] + ['fail stop: ' + why, 'fail token: ' + why]), err)
                    self.assertEqual(bool(self.left()), name == 'stop-leaves-run',
                                     "the driver's own stop lost its baseline under the kit's hidden view")

    def test_probe_only_hides_environments_from_the_kits_own_listing_only(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], env=self.env)
        try:
            for caller, shown in (({}, False), ({'OPENWIZ_KIT_RUN': self.mark}, True)):
                with self.subTest(caller=caller):
                    p = subprocess.run([os.path.join(NO_PROC, 'ps'), '-A', '-ww', '-o', 'pid=', '-o', 'command=', '-E'],
                                       env=dict(self.env, NO_PROC_PROBE_ONLY='1', **caller), capture_output=True,
                                       text=True, timeout=30)
                    rows = [r for r in p.stdout.splitlines() if r.split()[:1] == [str(child.pid)]]
                    self.assertEqual((bool(rows), any('KIT_TEST=' + self.mark in r for r in rows)), (True, shown))
        finally:
            child.kill()
            child.wait()

    def test_a_failed_start_check_still_stops_its_run(self):
        sleepy = os.path.join(self.folder, 'sleepy')
        os.mkdir(sleepy)
        with open(os.path.join(sleepy, 'fake-harness'), 'w') as f:
            f.write('#!%s\nimport time\ntime.sleep(120)\n' % sys.executable)
        os.chmod(os.path.join(sleepy, 'fake-harness'), 0o700)
        code, out, err = self.kit(TEMPLATE, wait='2', PATH=sleepy + os.pathsep + self.env['PATH'])
        self.assertEqual((code, out), (1, [PASS[0], 'fail start: no builder status note appeared within 2 seconds',
                                           'fail wake: not run: start failed', 'fail stop: not run: start failed',
                                           PASS[4]]), err)
        self.assertEqual(self.left(), [], 'the run whose start check failed still runs after the kit')

    def test_no_harness_outside_the_fixtures_is_on_the_tests_path(self):
        outside = os.path.join(self.folder, 'outside')
        os.mkdir(outside)
        with open(os.path.join(outside, 'claude'), 'w') as f:
            f.write('#!/bin/sh\nexit 0\n')
        os.chmod(os.path.join(outside, 'claude'), 0o700)
        old = os.environ['PATH']
        os.environ['PATH'] = outside + os.pathsep + old
        try:
            self.tearDown()
            self.setUp()
        finally:
            os.environ['PATH'] = old
        self.assertIsNone(shutil.which('claude', path=self.env['PATH']), 'the PATH reaches a real claude')
        self.assertEqual(shutil.which('fake-harness', path=self.env['PATH']), os.path.join(FIXTURES, 'fake-harness'))
        with self.assertRaisesRegex(AssertionError, 'could launch a real harness'):
            self.kit(TEMPLATE, PATH=outside + os.pathsep + self.env['PATH'])

    def test_each_planted_driver_fails_its_check(self):
        for name, lines in PLANTED.items():
            with self.subTest(name):
                self.tearDown()
                self.setUp()
                self.assertEqual(self.kit(os.path.join(FIXTURES, 'planted', name))[:2], (1, lines))

    def test_a_refusal_holding_a_credential_never_reaches_the_output(self):
        sample = planted('refuses-with-credential').SAMPLE
        for escape in ('', '1'):
            with self.subTest(escape=escape):
                self.tearDown()
                self.setUp()
                self.env['KIT_ESCAPE'] = escape
                self.assertFalse(any(sample in v for v in self.env.values()))
                code, out, err = self.kit(os.path.join(FIXTURES, 'planted', 'refuses-with-credential'))
                self.assertNotIn(sample, '\n'.join(out) + err)
                self.assertEqual((code, out), (1, PASS[:3] + [
                    'fail stop: its stop output held a credential, which the kit does not show',
                    'fail token: the driver printed a credential; its answer to a token field: its start output '
                    'held a credential, which the kit does not show']))

    def test_each_status_contract_credential_format_is_caught(self):
        formats = planted('leaks-format').FORMATS
        self.assertLessEqual(set(CONTRACT_FORMATS), set(formats))
        for name, sample in formats.items():
            with self.subTest(name):
                self.tearDown()
                self.setUp()
                self.env['KIT_LEAK'] = name
                self.assertFalse(any(sample in v for v in self.env.values()))
                code, out, err = self.kit(os.path.join(FIXTURES, 'planted', 'leaks-format'))
                self.assertEqual((code, out), (1, PASS[:4] + ['fail token: the driver printed a credential']))
                self.assertNotIn(sample, '\n'.join(out) + err)

    def test_template_and_schema_refuse_the_same_starts(self):
        sys.path.insert(0, HERE)
        import kit
        good = {'repository': 'example/site', 'ticket': 7, 'skill': 'build-ticket', 'harness': 'true',
                'model': 'Opus 5.5 Medium'}
        cases = [json.dumps(good), json.dumps(dict(good, token='x')), json.dumps({'repository': 'example/site'}),
                 json.dumps(dict(good, ticket=0)), json.dumps(dict(good, ticket='7')),
                 json.dumps(dict(good, ticket=True)), json.dumps(dict(good, repository='a/b/c')),
                 json.dumps(dict(good, skill='Build')), json.dumps(dict(good, skill='b' * 61)),
                 json.dumps(dict(good, harness='/usr/bin/true')), json.dumps(dict(good, model='m' * 61)),
                 json.dumps(dict(good, model='m\n')), json.dumps([good]), 'not json',
                 json.dumps(good)[:-1] + ', "ticket": 8}']
        schema = kit.load_schema()['commands']['start']['input']
        for case in cases:
            with self.subTest(case):
                try:
                    valid = kit.invalid(kit.parse(case), schema) is None
                except ValueError:
                    valid = False
                p = subprocess.run([TEMPLATE, 'start'], input=case, env=self.env, capture_output=True, text=True,
                                   timeout=60)
                self.assertEqual((p.returncode == 0), valid, p.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
