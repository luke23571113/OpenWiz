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
import tempfile
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

    # catches: a regex backtick hides a following real direct or multiline load
    # (R11), so a successful split moves a collector that Node still requires.
    def test_javascript_regex_does_not_hide_following_loads(self):
        fixture = FIXTURES / 'js-regex/tools'
        cases = [(name, (fixture / 'client' / name).read_text())
                 for name in ('read.cjs', 'multiline.cjs')]
        cases += [(name, prefix + '\nrequire("../war-room/collector.cjs");\n')
                  for name, prefix in (
                      ('quotes.cjs', 'const regex = /[`\'"]/;'),
                      ('escaped.cjs', r'const regex = /\`/;'),
                      ('class-slash.cjs', r'const regex = /[/`]/;'),
                      ('escaped-slash.cjs', r'const regex = /\/`/g;'),
                      ('comment-text.cjs', 'const regex = /[/*`]/;'),
                  )]
        for name, source in cases:
            with self.subTest(consumer=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / 'tools/client').mkdir(parents=True)
                (root / 'tools/war-room').mkdir()
                (root / 'tools/client/read.cjs').write_text(source)
                (root / 'tools/war-room/collector.cjs').write_bytes(
                    (fixture / 'war-room/collector.cjs').read_bytes())
                loaded = subprocess.run(['node', str(root / 'tools/client/read.cjs')],
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(loaded.returncode, 0, loaded.stderr)
                self.assertEqual(loaded.stdout, 'synthetic loaded\n')
                stay, move = report(root)
                self.assertEqual(stay, {
                    'tools/war-room/collector.cjs': 'tools/client/read.cjs:2 import'})
                self.assertEqual(move, [])

    # catches: literal/comment/template text counted as a real load, or an
    # ordinary regex or division suppressing a real following collector load.
    def test_javascript_regex_comment_and_template_controls(self):
        load = 'require("../war-room/collector.cjs");'
        cases = (
            ('ordinary regex', 'const regex = /x/;\n' + load, True),
            ('division', 'const amount = 12 / 3 / 2;\n' + load, True),
            ('division load operand', 'const amount = 12\n/ ' + load, True),
            ('quoted text', 'const text = " /`/ ";\n' + load, True),
            ('line comment', '// ' + load, False),
            ('block comment', '/*\n' + load + '\n*/', False),
            ('template text', 'const text = `\n' + load + '\n`;', False),
            ('regex text', r'const regex = /require\("..\/war-room\/collector.cjs"\)/;', False),
        )
        for name, source, keeps in cases:
            with self.subTest(control=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / 'tools/client').mkdir(parents=True)
                (root / 'tools/war-room').mkdir()
                (root / 'tools/client/read.cjs').write_text(source)
                (root / 'tools/war-room/collector.cjs').write_text('')
                stay, move = report(root)
                self.assertEqual(stay, {
                    'tools/war-room/collector.cjs': 'tools/client/read.cjs:2 import'} if keeps else {})
                self.assertEqual(move, [] if keeps else ['tools/war-room/collector.cjs'])

    # catches: ordinary shebangs, regex starts and division operands refuse the
    # entire split, stopping WM2 even though a following collector load resolves.
    def test_javascript_ordinary_syntax_keeps_following_loads(self):
        cases = (
            ('shebang', '#!/usr/bin/env node', 2),
            ('not regex', 'const okay = !/a/.test("b");', 2),
            ('arrow regex', 'const test = x => /a/.test(x);', 2),
            ('arrow backtick regex', 'const test = (x) => /`/.test(x);', 2),
            ('greater regex', 'const okay = "a" > /`/.source;', 2),
            ('identifier division', 'const total = 8; const half = total / 2;', 2),
            ('bracket division', 'const a = [8]; const half = a[0] / 2;', 2),
            ('call division', 'function f(x) { return x; } const half = f(8) / 2;', 2),
            ('grouped division', 'const half = (8 + 4) / 2;', 2),
            ('string division', 'const half = "8" / 2;', 2),
            ('template division', 'const half = `8` / 2;', 2),
            ('postfix increment', 'let total = 8; const half = total++ / 2;', 2),
            ('postfix decrement', 'let total = 8; const half = total-- / 2;', 2),
            ('if regex', 'if (true) /`/.test("x");', 2),
            ('while regex', 'while (false) /`/.test("x");', 2),
            ('for regex', 'for (; false;) /`/.test("x");', 2),
            ('with regex', 'with ({}) /`/.test("x");', 2),
            ('nested control', 'if ((Math.max(1, 2))) /`/.test("x");', 2),
            ('keyword method', 'const obj = {if() { return 8; }}; const half = obj.if() / 2;', 2),
            ('literal division', 'const half = true / 2;', 2),
            ('regex division', 'const half = /a/ / 2;', 2),
            ('division load operand',
             'const total = 8; const half = total / require("../war-room/collector.cjs");', 1),
        )
        fixture = FIXTURES / 'js-regex/tools/war-room/collector.cjs'
        for name, prefix, line in cases:
            for load in ('require("../war-room/collector.cjs");',
                         'require(\n  "../war-room/collector.cjs"\n);'):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    (root / 'tools/client').mkdir(parents=True)
                    (root / 'tools/war-room').mkdir()
                    (root / 'tools/client/read.cjs').write_text(prefix + '\n' + load + '\n')
                    (root / 'tools/war-room/collector.cjs').write_bytes(fixture.read_bytes())
                    loaded = subprocess.run(['node', str(root / 'tools/client/read.cjs')],
                                            capture_output=True, text=True, timeout=10)
                    self.assertEqual(loaded.returncode, 0, loaded.stderr)
                    self.assertEqual(loaded.stdout, 'synthetic loaded\n')
                    stay, move = report(root)
                    self.assertEqual(stay, {
                        'tools/war-room/collector.cjs': f'tools/client/read.cjs:{line} import'})
                    self.assertEqual(move, [])

    # catches: unresolved loads after a regex, or ambiguous/unterminated regex
    # syntax, yielding a successful unsafe move instead of a located refusal.
    def test_javascript_regex_uncertainty_refuses_without_sets(self):
        cases = (
            ('computed load', 'const regex = /`/;\nrequire(process.env.SYNTHETIC_MODULE);', 2),
            ('ambiguous closing brace', 'if (true) {} /`/.test("x");\nrequire("../war-room/collector.cjs");', 1),
            ('unterminated regex', 'const regex = /`\nrequire("../war-room/collector.cjs");', 1),
        )
        for name, source, line in cases:
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / 'tools/client').mkdir(parents=True)
                (root / 'tools/war-room').mkdir()
                (root / 'tools/client/read.cjs').write_text(source)
                (root / 'tools/war-room/collector.cjs').write_text('')
                result = run(root)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(f'refused tools/client/read.cjs:{line} native load:', result.stderr)
                self.assertNotRegex(result.stdout, r'(?m)^(stay|move) ')

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
