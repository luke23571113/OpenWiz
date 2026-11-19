#!/usr/bin/env python3
"""Exercise the test-line counter on a synthetic Git history."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('count.py').resolve()


class CountTests(unittest.TestCase):
    def test_committed_line_totals_and_areas(self):
        """catches: wrong area totals or non-test and checkout lines counted as tests."""
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)

            def git(*args):
                return subprocess.check_output(['git', *args], cwd=repo, text=True).strip()

            def write(name, content):
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)

            git('init', '-q')
            git('config', 'user.name', 'Synthetic')
            git('config', 'user.email', 'synthetic@example.invalid')
            git('config', 'core.hooksPath', '/dev/null')
            for name, lines in {
                'tests/fleet/check.rs': 2,
                'tests/loops/fixtures/input.json': 3,
                'tests/Cargo.toml': 1,
                'apps/web/src/card.test.tsx': 4,
                'apps/web/src/card.tsx': 11,
                'apps/site/src/home.ts': 7,
                'crates/core/Cargo.toml': 1,
                'crates/core/tests/check.rs': 5,
                'crates/adapters/cloudroom/Cargo.toml': 1,
                'crates/adapters/cloudroom/tests/test_reader.py': 6,
                'tools/test_report.py': 7,
                'ci/plan_test.py': 8,
                '.github/workflows/ci.test.mjs': 9,
                'contracts/fixtures/__tests__/input.json': 10,
                'contracts/fixtures/untested.json': 12,
                'test_root.py': 2,
            }.items():
                # A final line without a newline still counts.
                write(name, b'\n'.join([b'line'] * lines))
            write('assets/opaque.bin', b'\0\none\ntwo\n')
            git('add', '.')
            git('commit', '-qm', 'synthetic baseline')
            baseline = git('rev-parse', 'HEAD')

            write('tests/fleet/check.rs', b'one line\n')
            git('add', '.')
            git('commit', '-qm', 'synthetic change')
            write('tests/loops/fixtures/input.json', b'dirty checkout\n')
            write('.gitattributes', b'*.py -diff\n')

            output = subprocess.check_output(
                [sys.executable, '-I', str(SCRIPT), baseline], cwd=repo, text=True)
            report = json.loads(output)
            self.assertEqual(report['by_area'], {
                '.github/': 9, 'apps/site': 0, 'apps/web': 4, 'ci/': 8,
                'contracts/fixtures/': 10, 'crates/adapters/cloudroom': 6,
                'crates/core': 5, 'other': 2, 'tests/': 1, 'tests/fleet': 2,
                'tests/loops': 3, 'tools/': 7,
            })
            self.assertEqual(report['revision'], baseline)
            self.assertEqual(report['test_lines'], 57)
            self.assertEqual(report['total_lines'], 89)
            self.assertEqual(report['test_share_percent'], 64.04)


if __name__ == '__main__':
    unittest.main()
