#!/usr/bin/env python3
"""WM-P1 (#1056): the split checker on synthetic trees, through its command line.

Run from anywhere:  python3 -I ci/wizroom/test_split.py

Each fixture under fixtures/ is a small repository tree with a war-room folder
at tools/war-room. Every case reads the report the checker prints, and checks
the tree is unchanged afterwards: the checker writes nothing.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent
CHECKER = HERE / 'split.py'
FIXTURES = HERE / 'fixtures'


def tree_digest(root):
    digest = hashlib.sha256()
    for path in sorted(root.rglob('*')):
        digest.update(str(path.relative_to(root)).encode())
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def run(fixture):
    root = FIXTURES / fixture
    before = tree_digest(root)
    result = subprocess.run([sys.executable, '-I', str(CHECKER), '--root', str(root)],
                            capture_output=True, text=True, timeout=60)
    assert tree_digest(root) == before, f'the checker changed the {fixture} tree'
    return result


def report(fixture):
    """The stay set as {file: reference} and the move set, from a clean run."""
    result = run(fixture)
    assert result.returncode == 0, f'{fixture}: exit {result.returncode}\n{result.stdout}{result.stderr}'
    stay, move = {}, []
    for line in result.stdout.splitlines():
        if line.startswith('stay '):
            file, _, reference = line[5:].partition(' <- ')
            stay[file] = reference
        elif line.startswith('move '):
            move.append(line[5:])
    return stay, move


class SplitChecker(unittest.TestCase):
    # catches: an imported war-room module moved to WizRoom, so a public tool's
    # import breaks (the stall alarm's collector read).
    def test_an_import_keeps_its_module_public(self):
        stay, move = report('import')
        self.assertEqual(stay, {'tools/war-room/collector.py': 'tools/stall-alarm/alarm.py:5 import'})
        self.assertEqual(move, ['tools/war-room/page.py'])

    # catches: a file loaded by path (importlib), directly or through a small
    # loader helper, treated as unreferenced and moved (skills-eval's contract load).
    def test_a_native_load_keeps_its_file_public(self):
        stay, move = report('native-load')
        self.assertEqual(stay, {
            'tools/war-room/experiment_contract.py': 'tools/skills-eval/replay/score.py:5 native load',
            'tools/war-room/weights.py': 'tools/skills-eval/promotions/promote.py:15 native load',
        })
        self.assertEqual(move, ['tools/war-room/page.py'])

    # catches: a public workflow's runner script moved away; and the war room's
    # own workflow wrongly counted as a public consumer, keeping its code public.
    def test_a_workflow_path_keeps_its_file_public_but_the_war_rooms_own_workflow_does_not(self):
        stay, move = report('workflow')
        self.assertEqual(stay, {'tools/war-room/python.sh': '.github/workflows/board.yml:8 workflow path'})
        self.assertEqual(move, ['tools/war-room/publish.py'])

    # catches: a script a loop names moved away (the CI3 loop's check).
    def test_a_loop_path_keeps_its_file_public(self):
        stay, move = report('loop')
        self.assertEqual(stay, {'tools/war-room/ci3_check.py': 'loops/weekly.json:3 loop path'})
        self.assertEqual(move, ['tools/war-room/page.py'])

    # catches: a file a public contract links to moved away, leaving a dead link;
    # and a staying document's own relative link (the collector contract's schema).
    def test_a_contract_link_keeps_its_file_public(self):
        stay, move = report('contract')
        self.assertEqual(stay, {
            'tools/war-room/review_loops.py': 'contracts/review.v1.md:3 contract link',
            'tools/war-room/collector.v1.md': 'contracts/review.v1.md:4 contract link',
            'tools/war-room/collector.v1.schema.json': 'tools/war-room/collector.v1.md:3 path',
        })
        self.assertEqual(move, ['tools/war-room/page.py'])

    # catches: a staying module's own imports and read files moved away, so the
    # public layer breaks one step behind its consumer.
    def test_files_reached_from_a_staying_file_stay_too(self):
        stay, move = report('transitive')
        self.assertEqual(stay, {
            'tools/war-room/collector_read.py': 'tools/ci-overload/supply.py:5 import',
            'tools/war-room/sources.py': 'tools/war-room/collector_read.py:3 import',
            'tools/war-room/limits.conf': 'tools/war-room/collector_read.py:5 script path',
        })
        self.assertEqual(move, ['tools/war-room/page.py'])

    # catches: a load whose target is computed at run time silently ignored, so a
    # file it may load is moved: a computed module name through the repository
    # root (R3), a computed relative JavaScript path (R4), a wholly computed shell
    # source or import search path in a file that never names the folder (R2,
    # R9); and a computed load whose known parts exclude every folder file
    # refused anyway (plugins.cjs).
    def test_an_unresolvable_dynamic_load_refuses_with_its_location(self):
        result = run('dynamic')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        refused = [line.split(' ')[1] for line in result.stderr.splitlines() if line.startswith('refused ')]
        self.assertEqual(refused, [
            'tools/client/pick.py:6', 'tools/client/read.cjs:1', 'tools/client/run.sh:2',
            'tools/client/search.py:4', 'tools/stall-alarm/alarm.py:6', 'tools/stall-alarm/local.py:6',
            'tools/stall-alarm/plugin.py:6'])
        self.assertNotRegex(result.stdout, r'(?m)^(stay|move) ')

    # catches: ordinary Python forms that load or read a folder file moved away:
    # a plain os.path.join or joinpath read, publicly and from a staying file
    # (R1); a keyword import_module call (R6); a namespace package import (R7);
    # an aliased loader (R8); a with_name sibling load.
    def test_python_path_and_load_forms_keep_their_files_public(self):
        stay, move = report('python-forms')
        self.assertEqual(stay, {
            'tools/war-room/collector.py': 'tools/client/kw.py:6 import',
            'tools/war-room/pkg/reader.py': 'tools/client/ns.py:5 import',
            'tools/war-room/limits.conf': 'tools/client/read.py:3 script path',
            'tools/war-room/runner.py': 'tools/client/run.py:4 native load',
            'tools/war-room/settings.toml': 'tools/client/settings.py:3 script path',
            'tools/war-room/suite.py': 'tools/war-room/runner.py:5 native load',
            'tools/war-room/data/rows.csv': 'tools/war-room/runner.py:6 script path',
        })
        self.assertEqual(move, ['tools/war-room/page.py'])

    # catches: a JavaScript load written across lines ignored (R5), a load in a
    # comment counted, and loads through a URL base or a constant refused or lost.
    def test_javascript_load_forms_keep_their_files_public(self):
        stay, move = report('js-forms')
        self.assertEqual(stay, {
            'tools/war-room/collector.cjs': 'tools/client/multi.cjs:1 import',
            'tools/war-room/reader.mjs': 'tools/client/url.mjs:2 import',
            'tools/war-room/harness.mjs': 'tools/client/url.mjs:4 import',
        })
        self.assertEqual(move, ['tools/war-room/old.cjs'])

    # catches: prose or an unrelated tool counted as a reference, keeping war-room
    # files public that nothing public uses.
    def test_a_tree_with_no_public_reference_moves_everything(self):
        stay, move = report('none')
        self.assertEqual(stay, {})
        self.assertEqual(move, ['tools/war-room/history.py', 'tools/war-room/page.py',
                                'tools/war-room/test_page.py'])


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    unittest.main(verbosity=2)
