#!/usr/bin/env python3
"""Seam 1 of spec #2437 (#2441): the rehearsal runner on a synthetic release, on fixtures only.

Green on a good package; red, naming the step, on each planted break the spec lists. The
release is assembled by the real packager from this checkout's runtime and the pinned skills
(fixtures/release.py); GitHub and the harness are the recording fakes in fakes/. It proves the
runner and its checks, never a real release, account, harness or machine.
"""
import hashlib
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'fixtures'))
sys.dont_write_bytecode = True
import release  # noqa: E402

RUNNER = HERE / 'rehearse.py'
SKILLS = ROOT / '.wizskills/skills'
SOURCE = '1' * 40
# This machine's own target, as the installer's preflight reads it; elsewhere the suite skips.
TARGET = {('Linux', 'x86_64'): 'x86_64-unknown-linux-gnu', ('Darwin', 'arm64'): 'aarch64-apple-darwin',
          ('Darwin', 'x86_64'): 'x86_64-apple-darwin'}.get((platform.system(), platform.machine()))
STEPS = ['preflight', 'install', 'build_identity', 'setup', 'skills', 'first_fleet_dry_run']
# Each planted break, the one step it must fail, and words its log must name.
BREAKS = {
    'flipped-archive-byte': ('install', 'refused'),
    'other-version-manifest': ('install', "it installed version '0.0.98'"),
    'other-commit-identity': ('build_identity', "the build identity reads source '%s'" % ('2' * 40)),
    'setup-needs-cloudroom': ('setup', "the setup check reads cloudroom 'cloudroom_missing'"),
    'dry-run-writes': ('first_fleet_dry_run', 'it wrote to GitHub'),
    'calls-cargo': ('build_identity', 'it called a build tool or the harness: cargo build --release'),
}
sys.path.insert(0, str(HERE))
import rehearse  # noqa: E402


def caller_env():
    """The test's own environment without any token, App or CloudRoom variable (the runner refuses them)."""
    return {k: v for k, v in os.environ.items() if not rehearse.SECRET.fullmatch(k)}


@unittest.skipUnless(TARGET, 'only on a machine the installer supports')
class Rehearse(unittest.TestCase):
    def setUp(self):
        self.assertTrue((SKILLS / 'install/SKILL.md').is_file(), 'run tools/wizskills/install.py first')
        self.work = Path(tempfile.mkdtemp(prefix='rehearse-test-')).resolve()
        self.addCleanup(shutil.rmtree, self.work, True)

    def rehearse(self, planted=None, env=None):
        skills = self.work / 'skills'
        shutil.copytree(SKILLS, skills, symlinks=False)
        if planted == 'dry-run-writes':
            release.plant_skill(skills)
        archive = release.build(self.work / 'run', skills, source=SOURCE, target=TARGET, planted=planted)
        output = self.work / 'rehearsal.json'
        done = subprocess.run([sys.executable, '-I', str(RUNNER), '--assets', str(archive.parent),
                               '--target', TARGET, '--version', '0.0.99', '--source', SOURCE,
                               '--checkout', str(ROOT), '--skills', str(skills), '--output', str(output)],
                              capture_output=True, text=True, env=caller_env() if env is None else env, timeout=600)
        receipt = json.loads(output.read_text()) if output.exists() else None
        return done, receipt, archive

    def test_good_package_passes_every_step(self):
        done, receipt, archive = self.rehearse()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(receipt, {
            'schema': 'openwiz.rehearsal.v1', 'version': '0.0.99', 'source': SOURCE, 'target': TARGET,
            'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
            'manifest_sha256': hashlib.sha256(
                (archive.parent / ('openwiz-%s.manifest.json' % TARGET)).read_bytes()).hexdigest(),
            'status': 'pass', 'steps': [{'name': name, 'status': 'pass'} for name in STEPS]})
        self.assertEqual(done.stdout.splitlines(), ['step %s: pass' % name for name in STEPS] + ['rehearsal: pass'])

    def test_each_planted_break_fails_its_named_step(self):
        for planted, (step, words) in BREAKS.items():
            with self.subTest(planted=planted):
                self.setUp()
                done, receipt, _ = self.rehearse(planted)
                self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
                at = STEPS.index(step)
                self.assertEqual(receipt['status'], 'fail')
                self.assertEqual(receipt['steps'], [{'name': n, 'status': 'pass'} for n in STEPS[:at]]
                                 + [{'name': step, 'status': 'fail'}])
                self.assertIn('step %s: fail: ' % step, done.stdout)
                self.assertIn(words, done.stdout)
                self.assertTrue(done.stdout.endswith('rehearsal: fail\n'), done.stdout)

    def test_a_token_in_the_environment_is_refused(self):
        done, receipt, _ = self.rehearse(env=dict(caller_env(), GH_TOKEN='synthetic-not-a-token'))
        self.assertEqual(done.returncode, 2)
        self.assertIsNone(receipt)
        self.assertIn('GH_TOKEN', done.stderr)


if __name__ == '__main__':
    unittest.main()
