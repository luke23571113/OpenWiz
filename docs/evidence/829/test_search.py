#!/usr/bin/env python3
"""M4's exit status distinguishes absence, hits and unreadable Git data."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('search.sh')


class Search(unittest.TestCase):
    def test_real_git_absence_hits_and_unknown_revision(self):
        # catches #1080: an invalid revision reported as successful absence proof.
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(['git', 'init', '-q', tmp], check=True)
            subprocess.run(['git', '-C', tmp, 'config', 'user.name', 'Synthetic'], check=True)
            subprocess.run(['git', '-C', tmp, 'config', 'user.email', 'synthetic@example.invalid'], check=True)
            source = Path(tmp) / 'sample.txt'
            source.write_text('clean\n')
            subprocess.run(['git', '-C', tmp, 'add', '.'], check=True)
            subprocess.run(['git', '-C', tmp, 'commit', '-qm', 'Synthetic fixture'], check=True)
            for content, args, status in [('clean\n', [], 0), ('tools/live-check\n', [], 1),
                                          ('clean\n', ['nonexistent-ref-829-review'], 128)]:
                source.write_text(content)
                with self.subTest(status=status):
                    run = subprocess.run(['sh', str(SCRIPT), *args], cwd=tmp, capture_output=True, text=True)
                    self.assertEqual(run.returncode, status, run.stderr)

    def test_other_git_read_errors_are_preserved(self):
        # catches #1080: Git failures other than 128 also converted to proof success.
        with tempfile.TemporaryDirectory() as tmp:
            git = Path(tmp) / 'git'
            git.write_text('#!/bin/sh\nexit 2\n')
            git.chmod(0o700)
            run = subprocess.run(['/bin/sh', str(SCRIPT)], cwd=tmp, env=dict(os.environ, PATH=tmp),
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 2, run.stderr)


if __name__ == '__main__':
    unittest.main()
