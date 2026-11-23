#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
COPIED = ['kernel/live-rig/rig.py', 'kernel/driver-kit/kit.py', 'kernel/live-rig/hosts/cloudroom.json']
AGENT_CLIS = ['claude', 'codex', 'cursor-agent', 'agent', 'cursor', 'pi', 'opencode', 'copilot', 'goose', 'gemini',
              'kimi', 'qwen', 'cline', 'kilo', 'kilocode', 'crush', 'vibe', 'auggie', 'kiro-cli', 'junie', 'amp', 'agy',
              'oz', 'sculpt', 'hermes', 'acpx', 'droid', 'boat', 'room-cli', 'runpane', 'pane', 'openhands', 'devin',
              'warp', 'grok', 'codespaces', 'conductor']
STATUS = {'room-cli': 'room-cli status', 'gh': 'gh auth status --hostname github.com --active --no-refresh'}
RUNS = [('claude', 'claude-opus-5-5')]
FAKE = '''#!/bin/sh
printf '%%s\\n' "%s $*" >> "$FAKE_LOG"
if [ "%s $*" = "%s" ]; then exit %d; fi
echo "%s: refused, the Cloudroom host tests answer only its status command" >&2
exit 3
'''


def git(cwd, *args):
    return subprocess.run(['git', '-c', 'user.name=Example', '-c', 'user.email=example@example.invalid',
                           '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null'] + list(args),
                          cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class CloudroomHost(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.checkout = os.path.join(self.folder, 'checkout')
        for path in COPIED:
            src, dst = os.path.join(ROOT, path), os.path.join(self.checkout, path)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.exists(src):
                shutil.copy2(src, dst)
        git(self.checkout, 'init', '-q')
        git(self.checkout, 'add', '-A')
        git(self.checkout, 'commit', '-q', '-m', 'fixture checkout')
        self.head = git(self.checkout, 'rev-parse', 'HEAD')
        self.settings = os.path.join(self.folder, 'settings.json')
        with open(self.settings, 'w') as f:
            json.dump({'repo': 'example/cloudroom-throwaway', 'ticket': 7}, f)
        self.out = os.path.join(self.folder, 'out')
        self.log = os.path.join(self.folder, 'fake.log')
        self.stubs, self.fakes, tools = (os.path.join(self.folder, d) for d in ('stubs', 'fakes', 'tools'))
        for d in (self.stubs, self.fakes, tools):
            os.mkdir(d)
        os.symlink(shutil.which('git'), os.path.join(tools, 'git'))
        for name in AGENT_CLIS:
            if name in STATUS:
                continue
            with open(os.path.join(self.stubs, name), 'w') as f:
                f.write('#!/bin/sh\necho "%s: refused, the Cloudroom host tests never start an agent CLI" >&2\n'
                        'exit 1\n' % name)
            os.chmod(os.path.join(self.stubs, name), 0o700)
        self.path = os.pathsep.join([self.stubs, self.fakes, tools])

    def rig(self, signed_in=('room-cli', 'gh'), missing=()):
        for name, command in STATUS.items():
            if name in missing:
                continue
            with open(os.path.join(self.fakes, name), 'w') as f:
                f.write(FAKE % (name, name, command, 0 if name in signed_in else 1, name))
            os.chmod(os.path.join(self.fakes, name), 0o700)
        for name in AGENT_CLIS + ['gh']:
            want = None if name in missing else os.path.join(self.fakes if name in STATUS else self.stubs, name)
            self.assertEqual(shutil.which(name, path=self.path), want, name)
        env = dict(os.environ, PATH=self.path, HOME=self.folder, FAKE_LOG=self.log)
        p = subprocess.run([sys.executable, '-I', os.path.join(self.checkout, 'kernel', 'live-rig', 'rig.py'),
                            '--hosts', os.path.join(self.checkout, 'kernel', 'live-rig', 'hosts'),
                            '--settings', self.settings, '--out', self.out, '--host', 'Cloudroom'],
                           env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
        self.assertEqual((p.returncode, p.stdout.splitlines()),
                         (0, ['skipped Cloudroom %s: %s' % (h, self.why) for h, _ in RUNS]), p.stderr)
        days = os.listdir(self.out)
        days.remove('rig.lock')
        self.assertEqual(len(days), 1)
        self.assertEqual(sorted(os.listdir(os.path.join(self.out, days[0]))),
                         sorted('Cloudroom-%s-%s.json' % run for run in RUNS))
        for harness, model in RUNS:
            with open(os.path.join(self.out, days[0], 'Cloudroom-%s-%s.json' % (harness, model))) as f:
                record = json.load(f)
            seconds = record.pop('seconds')
            self.assertTrue(type(seconds) is int and 0 <= seconds < 60, seconds)
            self.assertEqual(record, {
                'host': 'Cloudroom', 'harness': harness, 'model': model, 'date': days[0], 'driver_commit': self.head,
                'kit_commit': self.head, 'outcome': 'skipped', 'skipped': self.why, 'kit_exit': None,
                'stdout': None})
        if not os.path.exists(self.log):
            return []
        with open(self.log) as f:
            return f.read().splitlines()

    def test_the_config_checks_only_the_cited_read_only_status_commands(self):
        self.assertTrue(os.path.isfile(os.path.join(HERE, 'cloudroom.json')),
                        'kernel/live-rig/hosts/cloudroom.json is missing')
        with open(os.path.join(HERE, 'cloudroom.json')) as f:
            config = json.load(f)
        self.assertEqual((config['host'], config['driver'], config['needs'], config['cost'], config['wait']),
                         ('Cloudroom', 'adapters/cloudroom/driver', ['room-cli', 'gh'], 'unknown', 900))
        self.assertEqual([' '.join(c) for c in config['signed_in']], [STATUS['room-cli'], STATUS['gh']])
        self.assertEqual([(r['harness'], r['model']) for r in config['runs']], RUNS)
        with open(os.path.join(ROOT, 'adapters', 'cloudroom', 'README.md')) as f:
            readme = f.read()
        for harness, model in RUNS:
            self.assertIn('--harness %s --model %s' % (harness, model), readme)

    def test_signed_in_everywhere_is_skipped_as_cost_and_starts_nothing(self):
        self.why = 'cost'
        self.assertEqual(self.rig(), [STATUS['room-cli'], STATUS['gh']])

    def test_room_cli_signed_out_is_skipped_and_reads_nothing_more(self):
        self.why = 'not signed in: room-cli'
        self.assertEqual(self.rig(signed_in=('gh',)), [STATUS['room-cli']])

    def test_gh_signed_out_is_skipped(self):
        self.why = 'not signed in: gh'
        self.assertEqual(self.rig(signed_in=('room-cli',)), [STATUS['room-cli'], STATUS['gh']])

    def test_room_cli_missing_is_skipped_and_runs_no_status_command(self):
        self.why = 'not installed: room-cli'
        self.assertEqual(self.rig(missing=('room-cli',)), [])

    def test_gh_missing_is_skipped_and_runs_no_status_command(self):
        self.why = 'not installed: gh'
        self.assertEqual(self.rig(missing=('gh',)), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
