#!/usr/bin/env python3
"""TV2 (#804) proofs for unread_fixtures.py, on synthetic Git trees.

Run: python3 -I tools/test-value/test_unread_fixtures.py. Each case builds a
small temporary repository, runs the script as a user would, and compares its
exact output with a literal list. The script decides which fixtures are
deleted, so the two ways it can be wrong are both checked: listing a fixture a
test still reads (its deletion breaks that test) and keeping one nothing reads
(the prune misses it). A failure to scan must never print the empty result.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
SCRIPT = Path(__file__).resolve().parent / 'unread_fixtures.py'


class Tree:
    def __init__(self, files):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True, env=env)
        for name, text in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        subprocess.run(['git', '-C', str(self.root), 'add', '-A'], check=True, env=env)

    def run(self, *roots):
        return subprocess.run([sys.executable, '-I', str(SCRIPT), '--repo', str(self.root), *roots],
                              capture_output=True, text=True)

    def close(self):
        self.tmp.cleanup()


class UnreadFixtures(unittest.TestCase):
    def check(self, files, expected, roots=()):
        tree = Tree(files)
        self.addCleanup(tree.close)
        result = tree.run(*roots)
        self.assertEqual(result.stdout.splitlines(), expected, result.stderr)
        self.assertEqual(result.returncode, 1 if expected else 0, result.stderr)

    def test_a_path_in_test_code_is_read_and_a_mention_in_prose_or_data_is_not(self):
        # catches: a fixture named only in docs or a data inventory (such as
        # CI's selection map) kept as if a test read it; and one a test opens
        # by path listed for deletion.
        self.check({
            'tests/fixtures/used.json': '{}',
            'tests/fixtures/deep/used.json': '{}',
            'tests/fixtures/only-in-docs.json': '{}',
            'tests/fixtures/only-in-map.json': '{}',
            'tests/proof/a.rs': 'include_str!("../fixtures/used.json"); let p = dir.join("deep/used.json");',
            'docs/notes.md': 'See tests/fixtures/only-in-docs.json.',
            'ci/map.json': '{"files": ["tests/fixtures/only-in-map.json"]}',
        }, ['tests/fixtures/only-in-docs.json', 'tests/fixtures/only-in-map.json'])

    def test_a_scenario_is_read_through_its_name_and_names_its_own_files(self):
        # catches: a scenario's response files deleted although its
        # scenario.json names them; a response file no scenario names kept
        # because its folder is in use; a scenario folder nothing names kept.
        self.check({
            'tests/fixtures/cli/used/scenario.json':
                '{"extends": "base", "responses": [{"stdout_file": "list.json"}]}',
            'tests/fixtures/cli/used/list.json': '[]',
            'tests/fixtures/cli/used/orphan.json': '[]',
            'tests/fixtures/cli/base/scenario.json': '{"responses": [{"stdout_file": "show.json"}]}',
            'tests/fixtures/cli/base/show.json': '{}',
            'tests/fixtures/cli/unused/scenario.json': '{"responses": [{"stdout_file": "list.json"}]}',
            'tests/fixtures/cli/unused/list.json': '[]',
            'tests/support.rs': 'const FIXTURES: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/fixtures/cli");',
            'tests/send.rs': 'let s = Scenario::new("used");',
        }, ['tests/fixtures/cli/unused/list.json',
            'tests/fixtures/cli/unused/scenario.json',
            'tests/fixtures/cli/used/orphan.json'])

    def test_a_folder_named_by_its_path_is_read_whole_and_a_longer_name_is_not_it(self):
        # catches: a folder a test walks (named by path, no scenario.json)
        # pruned file by file; a folder kept because a longer path such as
        # tests/notes/send.rs or notes/send-extra merely starts with its name.
        self.check({
            'tests/fixtures/walked/a.md': 'a',
            'tests/fixtures/walked/b.md': 'b',
            'tests/fixtures/notes/send/README.md': 'docs only',
            'tests/walk.py': "for p in (ROOT / 'tests/fixtures/walked').iterdir(): p.read_text()",
            'tests/Cargo.toml': 'path = "tests/notes/send.rs"\nname = "notes/send-extra"',
        }, ['tests/fixtures/notes/send/README.md'])

    def test_only_tracked_files_count_and_other_roots_can_be_named(self):
        # catches: an untracked local file reported, or read as a reader; a
        # second fixture root ignored when a later group names it.
        tree = Tree({
            'tests/fixtures/a.json': '{}',
            'tools/x/fixtures/b.json': '{}',
            'tools/x/fixtures/c.json': '{}',
            'tools/x/test.py': "open('fixtures/c.json')",
        })
        self.addCleanup(tree.close)
        (tree.root / 'tests/fixtures/untracked.json').write_text('{}')
        (tree.root / 'tests/untracked.rs').write_text('"fixtures/a.json"')
        result = tree.run('tests/fixtures', 'tools/x/fixtures')
        self.assertEqual(result.stdout.splitlines(),
                         ['tests/fixtures/a.json', 'tools/x/fixtures/b.json'], result.stderr)
        self.assertEqual(result.returncode, 1)

    def test_a_scan_that_cannot_run_never_prints_the_empty_result(self):
        # catches: a missing or misspelt root, a root outside the repository,
        # or a folder that is not a Git checkout reported as "nothing unread",
        # which would pass the prune's proof without scanning anything.
        tree = Tree({'tests/fixtures/a.json': '{}', 'tests/a.rs': '"fixtures/a.json"'})
        self.addCleanup(tree.close)
        for roots in (('tests/fixturez',), ('../outside',), ('tests/a.rs',)):
            with self.subTest(roots=roots):
                result = tree.run(*roots)
                self.assertEqual((result.returncode, result.stdout), (2, ''))
                self.assertTrue(result.stderr.strip())
        with tempfile.TemporaryDirectory() as bare:
            result = subprocess.run([sys.executable, '-I', str(SCRIPT), '--repo', bare],
                                    capture_output=True, text=True)
            self.assertEqual((result.returncode, result.stdout), (2, ''))


if __name__ == '__main__':
    unittest.main()
