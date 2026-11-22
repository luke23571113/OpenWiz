#!/usr/bin/env python3
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
BOOTSTRAP = os.path.join(HERE, 'bootstrap.sh')
TOOLS = os.path.join(HERE, 'tools.json')
AGENT_CLIS = ('claude codex cursor-agent agent pi opencode copilot goose gemini kimi qwen cline kilo crush vibe '
              'auggie kiro-cli junie amp agy oz sculpt hermes acpx droid').split()
PLATFORMS = ['linux-x86_64', 'linux-aarch64', 'darwin-x86_64', 'darwin-arm64']
SUMMARY = re.compile(r'^bootstrap: (\d+) installed, (\d+) already there, (\d+) left out$')


def script(path, body):
    with open(path, 'w') as f:
        f.write('#!/bin/sh\n' + body)
    os.chmod(path, 0o755)


def logged_logged_fake_tool(version):
    return 'echo "$(basename "$0") $*" >> "$FAKE_CALLS"\necho "fake %s (synthetic)"\n' % version


def sha256(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


class Fixture:

    def __init__(self, root):
        self.root = root
        self.home = os.path.join(root, 'home')
        self.prefix = os.path.join(root, 'prefix')
        self.dl = os.path.join(root, 'downloads')
        self.bin = os.path.join(root, 'bin')
        self.stubs = os.path.join(root, 'stubs')
        self.calls = os.path.join(root, 'calls.log')
        self.installer_log = os.path.join(root, 'installer.log')
        for d in (self.home, self.dl, self.bin, self.stubs):
            os.makedirs(d)
        for name in AGENT_CLIS:
            script(os.path.join(self.stubs, name), 'echo "refused: %s is a stub" >&2\nexit 1\n' % name)
        script(os.path.join(self.bin, 'curl'), 'echo "curl 7.88.1 (synthetic)"\n')
        script(os.path.join(self.bin, 'git'), 'echo "git version 2.43.0 (synthetic)"\n')
        script(os.path.join(self.bin, 'sudo'), 'echo sudo-ran >> "%s"\nexec "$@"\n' % self.installer_log)
        script(os.path.join(self.bin, 'python3'), 'exec %s "$@"\n' % sys.executable)
        self.tools = self.write_tools()

    def raw(self, name, version):
        path = os.path.join(self.dl, name)
        script(path, logged_fake_tool(version))
        return path

    def archive(self, name, member, version, zipped=False):
        body = ('#!/bin/sh\n' + logged_fake_tool(version)).encode()
        path = os.path.join(self.dl, name)
        if zipped:
            with zipfile.ZipFile(path, 'w') as z:
                info = zipfile.ZipInfo(member)
                info.external_attr = 0o755 << 16
                z.writestr(info, body)
        else:
            with tarfile.open(path, 'w:xz') as t:
                info = tarfile.TarInfo(member)
                info.size, info.mode = len(body), 0o755
                t.addfile(info, io.BytesIO(body))
        return path

    def wheel(self, name, version):
        path = os.path.join(self.dl, name)
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('fakewheel/__init__.py', '')
            z.writestr('fakewheel/cli.py', 'import os, sys\n'
                       'def main():\n'
                       '    with open(os.environ["FAKE_CALLS"], "a") as f:\n'
                       '        f.write("runpane " + " ".join(sys.argv[1:]) + "\\n")\n'
                       '    print("fake %s (synthetic)")\n'
                       '    return 0\n' % version)
        return path

    def installer_that_tries_sudo(self, name):
        payload = self.raw('fakeagent.payload', '3.2.1')
        path = os.path.join(self.dl, name)
        with open(path, 'w') as f:
            f.write('#!/usr/bin/env bash\n'
                    'echo "args: $*" >> "{log}"\n'
                    'sudo -n true 2>/dev/null && echo "sudo answered" >> "{log}"\n'
                    'mkdir -p "$HOME/.local/bin" && cp "{payload}" "$HOME/.local/bin/fakeagent"\n'
                    .format(log=self.installer_log, payload=payload))
        return path

    def entry(self, path, **extra):
        files = {p: dict({'url': 'file://' + path, 'sha256': sha256(path)}, **extra) for p in PLATFORMS}
        return files

    def write_tools(self):
        tools = [
            {'name': 'python3', 'kind': 'system', 'min_version': '3.9', 'hosts': ['all'],
             'source': 'the system package manager', 'why': 'synthetic'},
            {'name': 'git', 'kind': 'system', 'min_version': '2.0', 'hosts': ['all'],
             'source': 'the system package manager', 'why': 'synthetic'},
            {'name': 'curl', 'kind': 'archive', 'version': '8.23.0', 'system_min': '8.3', 'hosts': ['all'],
             'source': 'synthetic', 'why': 'synthetic',
             'files': self.entry(self.archive('curl.tar.xz', 'curl', '8.23.0'), member='curl')},
            {'name': 'gh', 'kind': 'archive', 'version': '2.105.0', 'hosts': ['all'], 'source': 'synthetic',
             'why': 'synthetic',
             'files': self.entry(self.archive('gh.zip', 'gh_x/bin/gh', '2.105.0', zipped=True),
                                 member='gh_x/bin/gh')},
            {'name': 'fakedroid', 'kind': 'binary', 'version': '1.17.2', 'hosts': ['factory'],
             'source': 'synthetic', 'why': 'synthetic', 'files': self.entry(self.raw('fakedroid', '1.17.2'))},
            {'name': 'fakeapp', 'kind': 'binary', 'version': '2.4.246', 'run_version': False, 'hosts': ['pane'],
             'source': 'synthetic', 'why': 'synthetic', 'files': self.entry(self.raw('fakeapp', '2.4.246'))},
            {'name': 'runpane', 'kind': 'wheel', 'version': '2.4.246', 'module': 'fakewheel.cli',
             'hosts': ['pane'], 'source': 'synthetic', 'why': 'synthetic',
             'files': {'any': {'url': 'file://' + self.wheel('fake.whl', '2.4.246'),
                               'sha256': sha256(os.path.join(self.dl, 'fake.whl'))}}},
            {'name': 'fakeagent', 'kind': 'installer', 'version': '3.2.1', 'needs': ['git', 'curl'],
             'args': ['--pin', 'abc123', '--dir', '{prefix}/lib/fakeagent'],
             'provides': '{home}/.local/bin/fakeagent', 'hosts': ['hermes'], 'source': 'synthetic',
             'why': 'synthetic', 'files': {'any': {'url': 'file://' + self.installer_that_tries_sudo('install.sh'),
                                                    'sha256': sha256(os.path.join(self.dl, 'install.sh'))}}},
            {'name': 'gatedtool', 'kind': 'binary', 'version': '1.0.0', 'hosts': ['all'], 'source': 'synthetic',
             'why': 'synthetic', 'left_out': 'its only download needs a paid account'},
        ]
        path = os.path.join(self.root, 'tools.json')
        with open(path, 'w') as f:
            json.dump({'tools': tools}, f)
        return path

    def run(self, *args, tools=None):
        env = {'HOME': self.home, 'FAKE_CALLS': self.calls, 'LANG': 'C',
               'PATH': os.pathsep.join([self.stubs, self.bin, '/usr/bin', '/bin'])}
        return subprocess.run(['bash', BOOTSTRAP, '--prefix', self.prefix, '--tools', tools or self.tools] +
                              list(args), env=env, cwd=self.root, capture_output=True, text=True, timeout=120)

    def remove_downloads(self):
        for name in os.listdir(self.dl):
            os.remove(os.path.join(self.dl, name))

    def tree(self):
        found = []
        for top in (self.prefix, self.home):
            for d, _, files in os.walk(top):
                found += [os.path.join(d, f) for f in files]
        return sorted(found)

    def read(self, path):
        if not os.path.exists(path):
            return ''
        with open(path) as f:
            return f.read()


class BootstrapTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        self.fx = Fixture(self.root)

    def summary(self, out):
        lines = out.rstrip('\n').split('\n')
        index = [i for i, line in enumerate(lines) if line.startswith('bootstrap: ')]
        self.assertEqual(len(index), 1, out)
        return lines[index[0]], lines[index[0] + 1:]

    def test_dry_run_prints_every_step_and_changes_nothing(self):
        self.fx.remove_downloads()
        r = self.fx.run('--dry-run')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for name in ('curl 8.23.0', 'gh 2.105.0', 'fakedroid 1.17.2', 'fakeapp 2.4.246', 'runpane 2.4.246',
                     'fakeagent 3.2.1'):
            self.assertIn('would install ' + name, r.stdout)
        self.assertIn('already there python3', r.stdout)
        self.assertIn('already there git', r.stdout)
        line, rest = self.summary(r.stdout)
        self.assertEqual(line, 'bootstrap: dry run, 6 to install, 2 already there, 1 left out')
        self.assertEqual(rest, ['left out gatedtool: its only download needs a paid account'])
        self.assertFalse(os.path.exists(self.fx.prefix))
        self.assertEqual(self.fx.tree(), [])
        self.assertEqual(self.fx.read(self.fx.calls), '')

    def test_real_tools_dry_run_lists_every_tool_and_touches_nothing(self):
        r = self.fx.run('--dry-run', tools=TOOLS)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for name in ('hermes', 'runpane', 'pane', 'droid', 'gh', 'curl', 'git', 'python3'):
            self.assertRegex(r.stdout, r'(?m)^(would install|already there|left out) %s\b' % name)
        self.assertRegex(self.summary(r.stdout)[0], r'^bootstrap: dry run, \d+ to install, \d+ already there, '
                                                   r'\d+ left out$')
        self.assertFalse(os.path.exists(self.fx.prefix))
        self.assertEqual(self.fx.read(self.fx.calls), '')

    def test_fixture_install_into_temp_prefix(self):
        r = self.fx.run()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        line, rest = self.summary(r.stdout)
        self.assertEqual(line, 'bootstrap: 6 installed, 2 already there, 1 left out')
        self.assertEqual(rest, ['left out gatedtool: its only download needs a paid account'])
        for name in ('curl', 'gh', 'fakedroid', 'fakeapp', 'runpane', 'fakeagent'):
            path = os.path.join(self.fx.prefix, 'bin', name)
            self.assertTrue(os.access(path, os.X_OK), name)
        log = self.fx.read(self.fx.installer_log)
        self.assertIn('args: --pin abc123 --dir %s/lib/fakeagent\n' % self.fx.prefix, log)
        self.assertNotIn('sudo', log)
        calls = self.fx.read(self.fx.calls).splitlines()
        self.assertEqual(sorted(calls), sorted('%s --version' % n for n in
                                               ('curl', 'gh', 'fakedroid', 'runpane', 'fakeagent')))
        for name in ('curl 8.23.0', 'gh 2.105.0', 'fakedroid 1.17.2', 'fakeapp 2.4.246', 'runpane 2.4.246',
                     'fakeagent 3.2.1'):
            self.assertRegex(r.stdout, '(?m)^installed %s$' % name)

    def test_checksum_mismatch_is_refused_and_nothing_from_it_runs(self):
        with open(os.path.join(self.fx.dl, 'install.sh'), 'a') as f:
            f.write('echo tampered >> "%s"\n' % self.fx.installer_log)
        with open(os.path.join(self.fx.dl, 'fakedroid'), 'a') as f:
            f.write('# tampered\n')
        r = self.fx.run()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        line, rest = self.summary(r.stdout)
        self.assertEqual(line, 'bootstrap: 4 installed, 2 already there, 3 left out')
        self.assertEqual(len(rest), 3, rest)
        for name in ('fakedroid', 'fakeagent'):
            self.assertTrue(any(re.match(r'left out %s: checksum mismatch: expected [0-9a-f]{64}, got [0-9a-f]{64}$'
                                         % name, x) for x in rest), rest)
            self.assertFalse(os.path.lexists(os.path.join(self.fx.prefix, 'bin', name)), name)
        self.assertEqual(self.fx.read(self.fx.installer_log), '')
        self.assertNotIn('fakedroid', self.fx.read(self.fx.calls))
        self.assertFalse(os.path.exists(os.path.join(self.fx.home, '.local', 'bin', 'fakeagent')))

    def test_second_run_installs_nothing(self):
        first = self.fx.run()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        before = {p: sha256(p) for p in self.fx.tree()}
        installer_log = self.fx.read(self.fx.installer_log)
        self.fx.remove_downloads()
        r = self.fx.run()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        line, rest = self.summary(r.stdout)
        self.assertEqual(line, 'bootstrap: 0 installed, 8 already there, 1 left out')
        self.assertEqual({p: sha256(p) for p in self.fx.tree()}, before)
        self.assertEqual(self.fx.read(self.fx.installer_log), installer_log)

    def test_too_old_system_tool_is_left_out_with_its_reason(self):
        script(os.path.join(self.fx.bin, 'git'), 'echo "git version 1.8.5 (synthetic)"\n')
        r = self.fx.run('--dry-run')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        line, rest = self.summary(r.stdout)
        self.assertEqual(line, 'bootstrap: dry run, 5 to install, 1 already there, 3 left out')
        self.assertIn('left out git: git 1.8.5 is older than 2.0; install git 2.0 or later with your system package manager '
                      '(this bootstrap never runs sudo)', rest)
        self.assertIn('left out fakeagent: needs git', rest)


class ToolsJsonTest(unittest.TestCase):
    def test_every_tool_names_its_source_exact_version_checksum_and_why(self):
        with open(TOOLS) as f:
            tools = json.load(f)['tools']
        names = [t['name'] for t in tools]
        for need in ('hermes', 'runpane', 'pane', 'droid', 'curl', 'git', 'gh', 'python3'):
            self.assertIn(need, names)
        hosts = {h for t in tools for h in t['hosts']}
        self.assertTrue({'hermes', 'pane', 'factory', 'conductor', 'cursor'} <= hosts, hosts)
        for t in tools:
            self.assertTrue(t['source'].startswith('https://') or t['kind'] == 'system', t['name'])
            self.assertGreater(len(t['why']), 20, t['name'])
            if t['kind'] == 'system':
                self.assertRegex(t['min_version'], r'^\d+\.\d+$')
                continue
            self.assertRegex(t['version'], r'^\d+\.\d+\.\d+$', t['name'])
            self.assertTrue(t['files'], t['name'])
            for platform, file in t['files'].items():
                self.assertIn(platform, PLATFORMS + ['any'])
                self.assertTrue(file['url'].startswith('https://'), file)
                self.assertRegex(file['sha256'], r'^[0-9a-f]{64}$', file)
        curl = [t for t in tools if t['name'] == 'curl'][0]
        self.assertEqual(curl['system_min'], '8.3')


if __name__ == '__main__':
    unittest.main(verbosity=2)
