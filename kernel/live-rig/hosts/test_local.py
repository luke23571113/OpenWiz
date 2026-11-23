#!/usr/bin/env python3
import ast
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.realpath(os.path.join(HERE, '..', '..', '..'))
CONFIG = os.path.join(HERE, 'local.json')
REPO, TICKET, LOGIN = 'example/local-throwaway', 7, 'example-local-login'
SECRET = 'gh' + 'p_' + 'Synthetic0Local0Value' * 2 + '00'
KEYS = ['host', 'harness', 'model', 'date', 'driver_commit', 'kit_commit', 'outcome', 'skipped', 'kit_exit',
        'stdout', 'seconds']
STATUS = {'claude': ['claude', 'auth', 'status'],
          'codex': ['codex', 'login', 'status'],
          'gh': ['gh', 'auth', 'status', '--hostname', 'github.com', '--active', '--no-refresh']}
RUNS = [{'harness': 'claude', 'model': 'claude-opus-5-5'}]
PASS = ['pass version: openwiz:records v1, and the schema is driver v1',
        'pass start: the run posted builder status note 2',
        'pass wake: the run edited builder status note 2',
        'pass stop: the run ended, and a wake after it is refused',
        'pass token: no login or token passed through the driver']
# SAFETY: refusing stubs first on PATH for every agent CLI the fleet's drivers can start, so no test reaches a real one.
AGENT_CLIS = ['claude', 'codex', 'cursor-agent', 'agent', 'cursor', 'pi', 'opencode', 'copilot', 'goose', 'gemini',
              'kimi', 'qwen', 'cline', 'kilo', 'kilocode', 'crush', 'vibe', 'auggie', 'kiro-cli', 'junie', 'amp', 'agy',
              'oz', 'sculpt', 'hermes', 'acpx', 'droid', 'boat', 'room-cli', 'runpane', 'pane', 'openhands', 'devin',
              'warp', 'grok', 'codespaces', 'conductor']
REFUSE = '#!/bin/sh\necho "%s: refused, the local host tests never start a real program" >&2\nexit 1\n'
FAKE = '''#!/bin/sh
printf '%%s\\n' "%(name)s $*" >> "$LOCAL_FAKE_LOG"
if [ "$*" = "%(status)s" ]; then
  echo "%(name)s: fake status output the rig discards"
  case " $LOCAL_SIGNED_OUT " in *" %(name)s "*) exit 1;; esac
  exit 0
fi
%(extra)secho "%(name)s: refused, the fake answers only its status command" >&2
exit 1
'''
GH_LOGIN = '''if [ "$*" = "api user --jq .login" ]; then
  echo "$LOCAL_GH_LOGIN"
  exit 0
fi
'''
KIT = '''import json, os, sys
%s
with open(os.environ['LOCAL_KIT_LOG'], 'a') as f:
    f.write(json.dumps(sys.argv[1:]) + '\\n')
print(%r)
'''


def git(cwd, *args):
    return subprocess.run(['git', '-c', 'user.name=Example', '-c', 'user.email=example@example.invalid',
                           '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null'] + list(args),
                          cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def kit_shapes_source():
    with open(os.path.join(ROOT, 'kernel', 'driver-kit', 'kit.py')) as f:
        text = f.read()
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign) and [getattr(t, 'id', None) for t in node.targets] == ['SHAPES']:
            return 'import re\n' + ast.get_source_segment(text, node)
    raise AssertionError('kit.py has no SHAPES')


class Local(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.checkout = os.path.join(self.folder, 'checkout')
        rig_folder = os.path.join(self.checkout, 'kernel', 'live-rig')
        os.makedirs(os.path.join(rig_folder, 'hosts'))
        os.makedirs(os.path.join(self.checkout, 'kernel', 'driver-kit'))
        shutil.copy2(os.path.join(ROOT, 'kernel', 'live-rig', 'rig.py'), rig_folder)
        if os.path.exists(CONFIG):
            shutil.copy2(CONFIG, os.path.join(rig_folder, 'hosts', 'local.json'))
        with open(os.path.join(self.checkout, 'kernel', 'driver-kit', 'kit.py'), 'w') as f:
            f.write(KIT % (kit_shapes_source(), '\n'.join(PASS)))
        git(self.checkout, 'init', '-q')
        git(self.checkout, 'add', '-A')
        git(self.checkout, 'commit', '-q', '-m', 'fixture checkout')
        self.head = git(self.checkout, 'rev-parse', 'HEAD')
        self.hosts = os.path.join(rig_folder, 'hosts')
        self.settings = os.path.join(self.folder, 'settings.json')
        with open(self.settings, 'w') as f:
            json.dump({'repo': REPO, 'ticket': TICKET}, f)
        self.out = os.path.join(self.folder, 'out')
        self.fake_log = os.path.join(self.folder, 'fakes.log')
        self.kit_log = os.path.join(self.folder, 'kit.log')
        self.stubs = tempfile.mkdtemp(dir=self.folder)
        for name in AGENT_CLIS + ['gh']:
            self.program(name, REFUSE % name)
        tools = tempfile.mkdtemp(dir=self.folder)
        os.symlink(shutil.which('git'), os.path.join(tools, 'git'))
        self.path = os.pathsep.join([self.stubs, tools])
        self.assertEqual({shutil.which(name, path=self.path) for name in AGENT_CLIS},
                         {os.path.join(self.stubs, name) for name in AGENT_CLIS})

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def program(self, name, text):
        with open(os.path.join(self.stubs, name), 'w') as f:
            f.write(text)
        os.chmod(os.path.join(self.stubs, name), 0o700)

    def fakes(self, installed=('claude', 'codex', 'gh')):
        for name, command in STATUS.items():
            if name in installed:
                self.program(name, FAKE % {'name': name, 'status': ' '.join(command[1:]),
                                           'extra': GH_LOGIN if name == 'gh' else ''})
            else:
                os.remove(os.path.join(self.stubs, name))

    def rig(self, signed_out=()):
        env = {'PATH': self.path, 'HOME': self.folder, 'LOCAL_FAKE_LOG': self.fake_log, 'LOCAL_KIT_LOG': self.kit_log,
               'LOCAL_SIGNED_OUT': ' '.join(signed_out), 'LOCAL_GH_LOGIN': LOGIN, 'GH_TOKEN': SECRET}
        p = subprocess.run([sys.executable, '-I', os.path.join(self.hosts, '..', 'rig.py'), '--hosts', self.hosts,
                            '--settings', self.settings, '--out', self.out, '--host', 'local'],
                           env=env, capture_output=True, text=True, timeout=120)
        return p.returncode, p.stdout.splitlines(), p.stderr

    def lines(self, path):
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return f.read().splitlines()

    def record(self):
        days = os.listdir(self.out)
        names = sorted(n for d in days if os.path.isdir(os.path.join(self.out, d))
                       for n in os.listdir(os.path.join(self.out, d)))
        self.assertEqual((len(days) - 1, names), (1, ['local-claude-claude-opus-5-5.json']))
        day = [d for d in days if d != 'rig.lock'][0]
        utc = datetime.datetime.now(datetime.timezone.utc)
        self.assertIn(day, {(utc - datetime.timedelta(days=n)).strftime('%Y-%m-%d') for n in (0, 1)})
        with open(os.path.join(self.out, day, names[0])) as f:
            text = f.read()
        record = json.loads(text)
        self.assertEqual(list(record), KEYS)
        self.assertEqual({k: record[k] for k in KEYS[:6]},
                         {'host': 'local', 'harness': 'claude', 'model': 'claude-opus-5-5', 'date': day,
                          'driver_commit': self.head, 'kit_commit': self.head})
        self.assertIs(type(record['seconds']), int)
        for private in (self.folder, os.path.realpath(self.folder), REPO, LOGIN, SECRET):
            self.assertNotIn(private, text)
        return record

    def commit_config(self, **change):
        self.assertTrue(os.path.exists(CONFIG), 'kernel/live-rig/hosts/local.json is missing')
        with open(CONFIG) as f:
            config = json.load(f)
        with open(os.path.join(self.hosts, 'local.json'), 'w') as f:
            json.dump(dict(config, **change), f)
        git(self.checkout, 'commit', '-qam', 'a changed host config')
        self.head = git(self.checkout, 'rev-parse', 'HEAD')

    def test_the_config_is_the_tickets_local_host_with_its_cited_status_commands(self):
        self.assertTrue(os.path.exists(CONFIG), 'kernel/live-rig/hosts/local.json is missing')
        with open(CONFIG) as f:
            config = json.load(f)
        self.assertEqual(config, {'host': 'local', 'driver': 'adapters/local/driver', 'needs': ['claude', 'codex', 'gh'],
                                  'signed_in': [STATUS['claude'], STATUS['codex'], STATUS['gh']], 'cost': 'none',
                                  'runs': RUNS, 'wait': 900})
        with open(os.path.join(ROOT, 'adapters', 'local', 'README.md')) as f:
            readme = f.read()
        with open(os.path.join(ROOT, 'adapters', 'local', 'driver')) as f:
            harnesses = re.search(r"^HARNESSES = \{(.*?)\}$", f.read(), re.M | re.S).group(1)
        for run in config['runs']:
            self.assertIn('`%s`' % run['harness'], readme)
            self.assertIn("'%s':" % run['harness'], harnesses)
            self.assertIn('"model":"%s"' % run['model'], readme)

    def test_every_program_signed_in_runs_the_kit_once_with_the_configs_exact_command(self):
        self.fakes()
        code, out, err = self.rig()
        self.assertEqual((code, out), (0, ['ran local claude: 5 of 5']), err)
        record = self.record()
        self.assertEqual({k: record[k] for k in KEYS[6:10]},
                         {'outcome': 'ran', 'skipped': None, 'kit_exit': 0, 'stdout': '\n'.join(PASS) + '\n'})
        self.assertEqual([json.loads(line) for line in self.lines(self.kit_log)],
                         [['--driver', 'adapters/local/driver', '--repo', REPO, '--ticket', str(TICKET),
                           '--harness', 'claude', '--model', 'claude-opus-5-5', '--wait', '900']])
        self.assertEqual(self.lines(self.fake_log), [' '.join(c) for c in STATUS.values()] + ['gh api user --jq .login'])

    def test_a_program_not_signed_in_is_skipped_with_its_exact_line_and_starts_no_kit(self):
        for name in STATUS:
            with self.subTest(name):
                self.fakes()
                code, out, err = self.rig(signed_out=[name])
                self.assertEqual((code, out), (0, ['skipped local claude: not signed in: %s' % name]), err)
                self.assertEqual({k: self.record()[k] for k in KEYS[6:10]},
                                 {'outcome': 'skipped', 'skipped': 'not signed in: ' + name, 'kit_exit': None,
                                  'stdout': None})
                self.assertEqual(self.lines(self.kit_log), [])
                ran = [' '.join(c) for c in STATUS.values()]
                self.assertEqual(self.lines(self.fake_log), ran[:list(STATUS).index(name) + 1])
                shutil.rmtree(self.out)
                os.remove(self.fake_log)

    def test_a_missing_program_is_skipped_with_its_exact_line_and_runs_no_status_command_or_kit(self):
        for name in STATUS:
            with self.subTest(name):
                self.fakes(installed=[n for n in STATUS if n != name])
                code, out, err = self.rig()
                self.assertEqual((code, out), (0, ['skipped local claude: not installed: %s' % name]), err)
                self.assertEqual({k: self.record()[k] for k in KEYS[6:10]},
                                 {'outcome': 'skipped', 'skipped': 'not installed: ' + name, 'kit_exit': None,
                                  'stdout': None})
                self.assertEqual((self.lines(self.kit_log), self.lines(self.fake_log)), ([], []))
                shutil.rmtree(self.out)

    def test_a_cost_other_than_none_is_skipped_as_cost_after_every_status_command(self):
        for cost in ('paid', 'unknown'):
            with self.subTest(cost):
                self.fakes()
                self.commit_config(cost=cost)
                code, out, err = self.rig()
                self.assertEqual((code, out), (0, ['skipped local claude: cost']), err)
                self.assertEqual({k: self.record()[k] for k in KEYS[6:10]},
                                 {'outcome': 'skipped', 'skipped': 'cost', 'kit_exit': None, 'stdout': None})
                self.assertEqual(self.lines(self.kit_log), [])
                self.assertEqual(self.lines(self.fake_log), [' '.join(c) for c in STATUS.values()])
                shutil.rmtree(self.out)
                os.remove(self.fake_log)


if __name__ == '__main__':
    unittest.main(verbosity=2)
