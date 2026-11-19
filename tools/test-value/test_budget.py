#!/usr/bin/env python3
"""Observable test-budget proofs using synthetic Git commits, no mocks."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('budget.py').resolve()


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Synthetic')
        self.git('config', 'user.email', 'synthetic@example.invalid')
        self.git('config', 'core.hooksPath', '/dev/null')
        self.write('README.md', 1)
        self.write('tests/old.rs', 250)
        self.base = self.commit()
        self.event = self.root / 'event.json'
        self.description('')

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.repo, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()

    def write(self, path, lines):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('synthetic\n' * lines, encoding='utf-8')

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '-qm', 'synthetic change')
        return self.git('rev-parse', 'HEAD')

    def description(self, body):
        self.event.write_text(json.dumps({'pull_request': {'body': body}}), encoding='utf-8')

    def check_budget(self, status, message, base=None, head='HEAD'):
        proc = subprocess.run([sys.executable, '-I', str(SCRIPT),
                               '--base=' + (self.base if base is None else base),
                               '--head=' + head, '--event=' + str(self.event)],
                              cwd=self.repo, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True)
        self.assertEqual(proc.returncode, status, proc.stdout)
        self.assertIn(message, proc.stdout)

    def test_boundary_and_offsets(self):
        """catches: off-by-one and gross counting instead of net growth."""
        for added, deleted, status, message in [
                (401, 0, 1, 'net=401'), (400, 0, 0, 'net=400'),
                (600, 250, 0, 'added=600 deleted=250 net=350')]:
            with self.subTest(added=added, deleted=deleted):
                self.write('tests/new.rs', added)
                self.write('tests/old.rs', 250 - deleted)
                self.commit()
                self.check_budget(status, message)

    def test_allowance(self):
        """catches: allowances covering the total rather than just the overage."""
        self.write('tests/new.rs', 500)
        self.commit()
        for allowance, status in [(99, 1), (100, 0), (150, 0)]:
            with self.subTest(allowance=allowance):
                self.description(f'Test budget allowance: {allowance} lines. Why: synthetic proof coverage')
                self.check_budget(status, f'net=500 ceiling=400 allowance={allowance}')

    def test_test_paths_only(self):
        """catches: omitted test patterns and unrelated files charged as tests."""
        tests = ['tests/data.txt', 'crates/core/tests/nested/data.json',
                 'test_root.py', 'tools/test_guard.py', 'guard_test.py',
                 'tools/guard_test.py', 'x.test.mjs', 'web/x.test.ts',
                 'web/x.test.tsx', '__tests__/data.bin', 'web/__tests__/nested/file.txt']
        for path in tests:
            self.write(path, 40)
        for path in ['src/main.rs', 'docs/evidence/proof.md', 'fixtures/data.json',
                     'tools/contest_guard.py', 'web/x.test.js', 'crates/core/src/tests.rs',
                     'crates/adapters/cloudroom/src/lib.rs']:
            self.write(path, 500)
        self.commit()
        self.check_budget(1, 'added=440 deleted=0 net=440')

    def test_renames_and_unusual_names(self):
        """catches: renamed files and tab/newline paths escaping accounting."""
        self.git('mv', 'tests/old.rs', 'tests/moved.rs')
        self.write('tests/space\tand\nnewline.rs', 401)
        self.commit()
        self.check_budget(1, 'net=401')
        self.git('mv', 'README.md', 'tests/renamed.md')
        self.commit()
        self.check_budget(1, 'net=402')

    def test_unreadable_revisions(self):
        """catches: missing or invalid commits treated as an empty diff."""
        for base, head, message in [('', 'HEAD', 'unreadable base'),
                                     ('missing-base', 'HEAD', 'unreadable base'),
                                     ('--help', 'HEAD', 'unreadable base'),
                                     (self.base, 'missing-head', 'unreadable head')]:
            with self.subTest(base=base, head=head):
                self.check_budget(1, message, base=base, head=head)

    def test_unreadable_description(self):
        """catches: unreadable descriptions passing even with no growth."""
        for data in [b'{', b'{}', b'{"pull_request":{"body":42}}', b'\xff',
                     b'{"pull_request":{"body":"","body":"other"}}']:
            with self.subTest(data=data):
                self.event.write_bytes(data)
                self.check_budget(1, 'unreadable description')
        self.event.unlink()
        self.check_budget(1, 'unreadable description')
        self.description(None)  # GitHub's readable empty body.
        self.check_budget(0, 'net=0')

    def test_malformed_allowance(self):
        """catches: malformed, empty-reason and duplicate allowances granting growth."""
        self.write('tests/new.rs', 500)
        self.commit()
        for line in ['Test budget allowance: -100 lines. Why: synthetic',
                     'Test budget allowance: 100 lines. Why: ',
                     'Test budget allowance: 100 lines. Why: synthetic\n' * 2,
                     '> Test budget allowance: 100 lines. Why: synthetic',
                     'Example Test budget allowance: 100 lines. Why: synthetic']:
            with self.subTest(line=line):
                self.description(line)
                self.check_budget(1, 'test budget:')

    def test_binary_test_file(self):
        """catches: binary test changes silently counted as zero."""
        (self.repo / 'tests/unknown.bin').write_bytes(b'synthetic\0binary')
        self.commit()
        self.check_budget(1, 'uncountable test diff')

    def test_committed_diff(self):
        """catches: working-tree deletions masking committed growth."""
        self.write('tests/new.rs', 401)
        head = self.commit()
        self.write('tests/new.rs', 0)
        with self.subTest(source='dirty tree'):
            self.check_budget(1, 'net=401', head=head)
        self.git('checkout', '-q', '-b', 'advanced-base', self.base)
        self.write('tests/main.rs', 600)
        advanced = self.commit()
        with self.subTest(source='base advanced independently'):
            self.check_budget(1, 'net=401', base=advanced, head=head)


if __name__ == '__main__':
    unittest.main(verbosity=2)
