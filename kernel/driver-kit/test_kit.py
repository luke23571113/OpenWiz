#!/usr/bin/env python3
import importlib.machinery
import importlib.util
import json
import os
import re
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


KEY = 'synthetic-kit-key-' + 'Kit0Value' * 2
KEY_PASS = PASS[4] + ", and the devin key reached only its host, in the helper's header"
KEY_HOST = os.path.join(FIXTURES, 'key-host', 'driver')
NOT_RUN = ['fail wake: not run: start failed', 'fail stop: not run: start failed']
IN_ARGS = 'a process the driver started holds a credential on its command line'
PLANTED_KEY = {
    'key-reads-itself': PASS[:4] + ["fail token: the driver's file driver names DEVIN_API_KEY, the key's variable"],
    'key-in-args': PASS[:4] + ['fail token: %s; a process holds the devin key on its command line' % IN_ARGS],
    'key-unregistered-host': [PASS[0], 'fail start: the key helper refused: host is not in '
                              'kernel/driver-kit/hosts.json'] + NOT_RUN +
                             ["fail token: the devin key never reached the kit's fake host"],
    'key-host-in-path': [PASS[0], 'fail start: the key helper refused: path has // (a host)'] + NOT_RUN +
                        ["fail token: the devin key never reached the kit's fake host"],
    'key-in-env': PASS[:4] + ['fail token: a process the driver started holds a credential in OPENWIZ_COPY, which '
                              'the kit never gave it; a process the driver started holds the devin key in '
                              'OPENWIZ_COPY, not in DEVIN_API_KEY'],
    'key-echoed': PASS[:4] + ['fail token: the driver printed a credential; the driver printed the devin key'],
    'key-in-body': PASS[:4] + ["fail token: the devin key reached the kit's fake host outside the helper's "
                               "Authorization header"],
    'key-calls-keychain': PASS[:4] + ["fail token: the driver's file driver calls the keychain tool secret-tool"],
    'key-sets-override': PASS[:4] + ["fail token: the driver's file driver names OPENWIZ_HOSTKEY_TEST_ORIGIN, the "
                                     "kit's test override"],
}
HOST_SCHEMA = {'type': 'object', 'required': ['origin', 'variable', 'keychain', 'header'],
               'additionalProperties': False,
               'properties': {'origin': {'type': 'string',
                                         'pattern': r'^https://[a-z0-9]+(-[a-z0-9]+)*(\.[a-z0-9]+(-[a-z0-9]+)*)+$'},
                              'variable': {'type': 'string', 'pattern': '^[A-Z][A-Z0-9_]{0,63}$'},
                              'keychain': {'type': 'string', 'pattern': r'^[a-z0-9]+([.-][a-z0-9]+)*$'},
                              'header': {'const': 'authorization-bearer'}}}
HOST_NAME = {'type': 'string', 'pattern': '^(?=.{1,40}$)[a-z0-9]+(-[a-z0-9]+)*$'}
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
                        PATH=FIXTURES + os.pathsep + os.environ.get('PATH', ''))

    def tearDown(self):
        for pid in filter(str.isdigit, os.listdir('/proc')):
            try:
                with open('/proc/%s/environ' % pid, 'rb') as f:
                    if ('KIT_TEST=' + self.mark).encode() in f.read().split(b'\0'):
                        os.kill(int(pid), signal.SIGKILL)
            except OSError:
                pass

    def kit(self, driver, python=sys.executable, **env):
        p = subprocess.run([python, '-I', os.path.join(HERE, 'kit.py'), '--driver', driver,
                            '--repo', 'example/site', '--ticket', '7', '--harness', 'fake-harness',
                            '--model', 'Synthetic 1', '--tracker', self.env['KIT_TRACKER'], '--wait', '8'],
                           env=dict(self.env, **env), capture_output=True, text=True, timeout=120)
        return p.returncode, p.stdout.splitlines(), p.stderr

    def keyed(self, driver, *answer, python=sys.executable, **env):
        kit = module(os.path.join(HERE, 'kit.py'))
        host = kit.FakeHost(*answer)
        self.addCleanup(host.close)
        code, out, err = self.kit(driver, python, DEVIN_API_KEY=KEY, OPENWIZ_HOSTKEY_TEST_ORIGIN=host.origin, **env)
        for text in ['\n'.join(out) + err] + [open(os.path.join(d, n), errors='replace').read()
                                              for d, _, names in os.walk(self.folder) for n in names]:
            self.assertNotIn('kit-canary-', text)
            self.assertNotIn(KEY, text)
        return code, out, host

    def test_a_key_host_driver_that_uses_only_the_helper_passes_all_five(self):
        macos = {'PATH': NO_PROC + os.pathsep + self.env['PATH'], 'NO_PROC_PYTHON': sys.executable}
        for python, env in ((sys.executable, {}), (os.path.join(NO_PROC, 'python3'), macos)):
            with self.subTest(python):
                self.tearDown()
                self.setUp()
                code, out, host = self.keyed(KEY_HOST, python=python, **dict(env, PATH=env and macos['PATH']
                                                                                 or self.env['PATH']))
                self.assertEqual((code, out), (0, PASS[:4] + [KEY_PASS]))
                lines = [re.sub(r'run-[0-9a-f]{12}', '<run>', r[0].rpartition(' ')[0]) for r in host.requests]
                self.assertEqual(lines, ['POST /v1/runs/<run>/start', 'POST /v1/runs/<run>/wake',
                                         'DELETE /v1/runs/<run>'])
                for _, headers, _ in host.requests:
                    self.assertEqual([v for k, v in headers if k == 'Authorization'], ['Bearer ' + KEY])

    def test_each_planted_key_driver_fails_with_its_own_line(self):
        for name, lines in PLANTED_KEY.items():
            with self.subTest(name):
                self.tearDown()
                self.setUp()
                code, out, _ = self.keyed(os.path.join(FIXTURES, 'planted', name, 'driver'))
                self.assertEqual((code, out), (1, lines))

    def test_on_macos_a_key_in_an_argument_or_another_variable_is_caught(self):
        for name in ('key-in-args', 'key-in-env'):
            with self.subTest(name):
                self.tearDown()
                self.setUp()
                code, out, _ = self.keyed(os.path.join(FIXTURES, 'planted', name, 'driver'),
                                          python=os.path.join(NO_PROC, 'python3'), NO_PROC_PYTHON=sys.executable,
                                          PATH=NO_PROC + os.pathsep + self.env['PATH'])
                self.assertEqual((code, out), (1, PLANTED_KEY[name]))

    def test_without_the_key_helper_the_kit_refuses_a_driver_with_a_readme_and_runs_one_without(self):
        kit = os.path.join(self.folder, 'kernel', 'driver-kit')
        os.makedirs(kit)
        for name in ('kit.py', 'schema.json'):
            shutil.copy(os.path.join(HERE, name), kit)
        shutil.copytree(os.path.join(HERE, '..', 'records-kit'), os.path.join(self.folder, 'kernel', 'records-kit'))
        shutil.copy(os.path.join(HERE, '..', 'records.v1.md'), os.path.join(self.folder, 'kernel'))
        bare = os.path.join(self.folder, 'bare')
        os.makedirs(bare)
        for name in ('driver', 'schema.json'):
            shutil.copy(os.path.join(os.path.dirname(TEMPLATE), name), bare)
        for driver, want in ((KEY_HOST, 2), (TEMPLATE, 2), (os.path.join(bare, 'driver'), 0)):
            with self.subTest(driver):
                p = subprocess.run([sys.executable, '-I', os.path.join(kit, 'kit.py'), '--driver', driver, '--repo',
                                    'example/site', '--ticket', '7', '--harness', 'fake-harness', '--model', 'm',
                                    '--tracker', self.env['KIT_TRACKER'], '--wait', '8'], env=self.env,
                                   capture_output=True, text=True, timeout=120)
                self.assertEqual(p.returncode, want, p.stdout + p.stderr)
                if want:
                    self.assertEqual(p.stderr, 'kit.py: the key helper kernel/driver-kit/hostkey.py is missing, so '
                                               'the kit cannot check host keys\n')

    def test_a_host_that_answers_a_redirect_fails_start_and_the_redirect_is_never_followed(self):
        kit = module(os.path.join(HERE, 'kit.py'))
        target = kit.FakeHost()
        self.addCleanup(target.close)
        code, out, host = self.keyed(KEY_HOST, 302, [('Location', target.origin + '/v1/runs')], b'')
        self.assertEqual((code, out), (1, [PASS[0], 'fail start: the host answered 302'] + NOT_RUN + [KEY_PASS]))
        self.assertEqual((len(host.requests), target.requests), (1, []))

    def test_the_registry_holds_devin_and_the_schema_and_helper_refuse_the_same_registries(self):
        kit, hostkey = module(os.path.join(HERE, 'kit.py')), module(os.path.join(HERE, 'hostkey.py'))
        good = {'devin': {'origin': 'https://api.devin.ai', 'variable': 'DEVIN_API_KEY', 'keychain': 'openwiz-devin',
                          'header': 'authorization-bearer'}}
        self.assertEqual(hostkey.registry(), good)
        entry = good['devin']
        cases = [good, dict(good, other=dict(entry, origin='https://api.example.org')), {}, [entry], {'devin': [1]},
                 {'Devin': entry}, {'d' * 41: entry}, {'devin': dict(entry, extra='x')}, {'devin': {'origin': 'x'}},
                 {'devin': dict(entry, origin='http://api.devin.ai')}, {'devin': dict(entry, origin=entry['origin'] + '/')},
                 {'devin': dict(entry, origin=entry['origin'] + ':443')}, {'devin': dict(entry, origin='https://API.devin.ai')},
                 {'devin': dict(entry, origin='https://localhost')}, {'devin': dict(entry, header='x-api-key')},
                 {'devin': dict(entry, variable='devin_api_key')}, {'devin': dict(entry, keychain='openwiz devin')},
                 {'devin': dict(entry, variable=7)}, 'raw:{"devin": %s, "devin": %s}' % (json.dumps(entry), json.dumps(entry)),
                 'raw:{"devin": {"origin": NaN}}', 'raw:not json']
        for case in cases:
            with self.subTest(case):
                path = os.path.join(self.folder, 'hosts.json')
                with open(path, 'w') as f:
                    f.write(case[4:] if isinstance(case, str) else json.dumps(case))
                try:
                    value = kit.parse(case[4:]) if isinstance(case, str) else case
                    schema = isinstance(value, dict) and bool(value) and all(
                        kit.invalid(n, HOST_NAME) is None and kit.invalid(e, HOST_SCHEMA) is None for n, e in value.items())
                except ValueError:
                    schema, value = False, None
                try:
                    helper = hostkey.registry(path) == value
                except hostkey.Refused:
                    helper = False
                self.assertEqual((schema, helper), (schema, schema))

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
