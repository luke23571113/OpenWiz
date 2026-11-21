#!/usr/bin/env python3
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
INSTALL = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('test_install', INSTALL / 'test_install.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

URL = 'https://github.com/openwizdev/WizSkills.git'
NAMES = ('grill', 'handoff', 'launch-fleet', 'research', 'setup', 'to-spec', 'to-tickets', 'triage')
CLASHES = ('handoff', 'research', 'to-spec', 'to-tickets', 'triage')
GIT = {'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1',
       'GIT_AUTHOR_NAME': 'Synthetic', 'GIT_AUTHOR_EMAIL': 'synthetic@example.invalid',
       'GIT_COMMITTER_NAME': 'Synthetic', 'GIT_COMMITTER_EMAIL': 'synthetic@example.invalid'}


def skill(name, text):
    return b'---\nname: %s\n---\n%s\n' % (name.encode(), text.encode())


def bundled():
    files = {f'runtime/skills/{name}/SKILL.md': skill(name, 'Synthetic bundled copy.') for name in NAMES}
    files['runtime/skills/launch-fleet/scripts/fleet.sh'] = b'#!/bin/sh\necho synthetic bundled fleet\n'
    return files


def git(*args, cwd=None):
    return subprocess.run(['git', *args], cwd=cwd, env={**os.environ, **GIT}, check=True,
                          capture_output=True, text=True).stdout.strip()


class Skills(base.Bundles):

    def setUp(self):
        super().setUp()
        self.run_install(self.bundle(override=bundled()))
        self.home = self.base / 'home'
        self.home.mkdir()
        self.checkout = self.base / 'checkout'
        (self.checkout / 'tools').mkdir(parents=True)
        shutil.copytree(INSTALL, self.checkout / 'tools/install',
                        ignore=shutil.ignore_patterns('tests', 'test_*.py', '__pycache__'))
        self.remote = self.base / 'wizskills.git'
        git('init', '-q', '--bare', str(self.remote))
        self.work = self.base / 'wizskills-work'
        git('init', '-q', str(self.work))
        self.tags = {}
        for version in ('0.2.0', '0.2.1', '0.3.0'):
            self.release(version)
        self.lock('0.2.0')

    def release(self, version, record=None):
        skills = self.work / 'skills'
        shutil.rmtree(skills, ignore_errors=True)
        for name in NAMES:
            (skills / name).mkdir(parents=True)
            (skills / name / 'SKILL.md').write_bytes(skill(name, f'Synthetic release {version}.'))
        script = skills / 'launch-fleet/scripts/fleet.sh'
        script.parent.mkdir()
        script.write_bytes(b'#!/bin/sh\necho synthetic release fleet\n')
        script.chmod(0o755)
        (skills / 'README.md').write_bytes(b'Synthetic skills index.\n')
        git('add', '-A', cwd=self.work)
        git('commit', '-q', '-m', 'Synthetic release ' + version, cwd=self.work)
        commit, tree = git('rev-parse', 'HEAD', cwd=self.work), git('rev-parse', 'HEAD^{tree}', cwd=self.work)
        value = {'schema': 'openwiz.wizskills.release.v1', 'version': version, 'commit': commit, 'tree': tree}
        value.update(record or {})
        git('tag', '-a', 'v' + version, '-m', json.dumps(value, separators=(',', ':')), cwd=self.work)
        git('push', '-q', str(self.remote), 'v' + version, cwd=self.work)
        self.tags[version] = {'version': version, 'commit': commit, 'tree': tree}

    def lock(self, version):
        (self.checkout / 'wizskills.lock').write_text(json.dumps(self.tags[version], indent=2) + '\n')

    def skills(self, remote=None, env=None):
        redirect = {'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': f'url.{(remote or self.remote).as_uri()}.insteadOf',
                    'GIT_CONFIG_VALUE_0': URL}
        result = subprocess.run([sys.executable, '-I', str(self.checkout / 'tools/install/install'), 'skills',
                                 '--root', str(self.root)], capture_output=True, text=True,
                                env={'PATH': os.environ['PATH'], 'HOME': str(self.home), **redirect, **(env or {})})
        return result.returncode, json.loads(result.stdout or '{}')

    def text(self, folder, name='grill'):
        return (folder / name / 'SKILL.md').read_bytes()

    def rows(self, result):
        return {row['id']: row for row in result.get('harnesses', [])}


class Report(Skills):
    def test_no_agent_folder_is_absent_and_never_reported_installed(self):
        code, result = self.skills()
        self.assertEqual((code, result.get('outcome')), (5, 'refused'), result)
        for row in result['harnesses']:
            with self.subTest(agent=row['id']):
                self.assertEqual(row['state'], 'absent')
                folder = str(self.home / ('.config/opencode' if row['id'] == 'opencode' else
                                          '.claude' if row['id'] == 'claude-code' else '.' + row['id']))
                self.assertIn(folder, row['next'])
        self.assertEqual(sorted(p.name for p in self.home.iterdir()), [])
        self.assertFalse((self.root / 'skills').exists())

    def test_codex_home_lands_the_skills_there_and_leaves_dot_codex_alone(self):
        elsewhere = self.base / 'codex-elsewhere'
        elsewhere.mkdir()
        code, result = self.skills(env={'CODEX_HOME': str(elsewhere)})
        self.assertEqual((code, result.get('outcome')), (0, 'installed'), result)
        row = self.rows(result)['codex']
        self.assertEqual((row['state'], row['path']), ('installed', str(elsewhere / 'skills')))
        self.assertEqual(sorted(p.name for p in (elsewhere / 'skills').iterdir()), sorted(NAMES))
        self.assertFalse((self.home / '.codex').exists())


class Newest(Skills):
    def test_the_newest_release_of_the_pinned_line_is_installed_over_the_bundled_copy(self):
        (self.home / '.claude').mkdir()
        code, result = self.skills()
        self.assertEqual((code, result.get('outcome')), (0, 'installed'), result)
        self.assertEqual(result.get('skills_from'), {'kind': 'release', 'version': '0.2.1',
                                                 'commit': self.tags['0.2.1']['commit'],
                                                 'tree': self.tags['0.2.1']['tree']})
        for folder in (self.home / '.claude/skills', self.root / 'skills'):
            with self.subTest(folder=folder):
                self.assertEqual(sorted(p.name for p in folder.iterdir()), sorted(NAMES))
                self.assertEqual(self.text(folder), skill('grill', 'Synthetic release 0.2.1.'))
                fleet = folder / 'launch-fleet/scripts/fleet.sh'
                self.assertTrue(os.access(fleet, os.X_OK))

    def test_a_newest_tag_whose_record_does_not_match_installs_the_bundled_copy_and_says_so(self):
        self.release('0.2.2', record={'tree': '0' * 40})
        (self.home / '.claude').mkdir()
        code, result = self.skills()
        self.assertEqual((code, result.get('outcome')), (0, 'installed'), result)
        self.assertEqual((result.get('skills_from') or {}).get('kind'), 'bundled')
        self.assertIn('0.2.2', (result.get('skills_from') or {}).get('reason', ''))
        self.assertEqual(self.text(self.home / '.claude/skills'), skill('grill', 'Synthetic bundled copy.'))

    def test_an_unreadable_release_installs_the_bundled_copy_and_says_so(self):
        (self.home / '.claude').mkdir()
        code, result = self.skills(remote=self.base / 'missing.git')
        self.assertEqual((code, result.get('outcome')), (0, 'installed'), result)
        self.assertEqual((result.get('skills_from') or {}).get('kind'), 'bundled')
        self.assertTrue((result.get('skills_from') or {}).get('reason', ''))
        self.assertEqual(self.text(self.home / '.claude/skills'), skill('grill', 'Synthetic bundled copy.'))


class PerSkill(Skills):
    def test_the_users_own_same_named_skills_in_one_agent_block_nothing_else(self):
        (self.home / '.claude').mkdir()
        own = self.home / '.codex/skills'
        for name in CLASHES:
            (own / name).mkdir(parents=True)
            (own / name / 'SKILL.md').write_bytes(b'The owner ' + name.encode() + b'.\n')
        before = base.snapshot(own)
        code, result = self.skills()
        self.assertEqual((code, result.get('outcome')), (0, 'partial'), result)
        rows = self.rows(result)
        self.assertEqual(rows['claude-code']['state'], 'installed')
        self.assertEqual(sorted(p.name for p in (self.home / '.claude/skills').iterdir()), sorted(NAMES))
        self.assertEqual(rows['codex']['state'], 'partial')
        self.assertEqual([s['skill'] for s in rows['codex']['skipped']], list(CLASHES))
        for skipped in rows['codex']['skipped']:
            with self.subTest(skill=skipped['skill']):
                self.assertIn(str(own / skipped['skill']), skipped['next'])
                self.assertIn('Codex', skipped['next'])
                self.assertIn('run this again', skipped['next'])
        for name in set(NAMES) - set(CLASHES):
            self.assertEqual(self.text(own, name), skill(name, 'Synthetic release 0.2.1.'))
        self.assertEqual({k: v for k, v in base.snapshot(own).items() if k.split('/')[0] in CLASHES}, before)
        self.assertEqual(sorted(p.name for p in (self.root / 'skills').iterdir()), sorted(NAMES))
        again = self.skills()
        self.assertEqual((again[0], again[1].get('outcome')), (0, 'partial'))
        self.assertEqual({k: v for k, v in base.snapshot(own).items() if k.split('/')[0] in CLASHES}, before)


if __name__ == '__main__':
    unittest.main()
