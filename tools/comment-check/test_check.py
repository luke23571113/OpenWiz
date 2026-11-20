#!/usr/bin/env python3
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
CHECK = HERE / 'check.py'
CONTRACTS = HERE.parent.parent / 'contracts'
FIXTURES = CONTRACTS / 'fixtures' / 'comments'
SCHEMA = json.loads((CONTRACTS / 'comments.v1.schema.json').read_text())
EXPECTED = json.loads((FIXTURES / 'expected.json').read_text())
LANGUAGES = {'rust.rs', 'python.py', 'shell.sh', 'yaml.yml', 'toml.toml', 'javascript.js', 'css.css', 'html.html'}


class Repo:
    def __init__(self, test):
        self.tmp = tempfile.TemporaryDirectory()
        test.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'Synthetic')
        self.git('config', 'user.email', 'synthetic@example.com')
        self.write('README.md', 'synthetic\n')
        self.commit()

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def copy(self, source, dest):
        shutil.copytree(source, self.root / dest, dirs_exist_ok=True)

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '-q', '-m', 'synthetic')
        return self.git('rev-parse', 'HEAD')

    def check(self, *args):
        run = subprocess.run([sys.executable, '-I', str(CHECK), *args], cwd=self.root,
                             capture_output=True, text=True)
        return run.returncode, run.stdout, run.stderr


def failures(stdout):
    found = set()
    for line in stdout.splitlines():
        m = re.match(r'^(.+?):(\d+): ([a-z-]+): ', line)
        if m:
            found.add((m.group(1), int(m.group(2)), m.group(3)))
    return found


def validate(value, schema, root=SCHEMA, where='report'):
    if '$ref' in schema:
        return validate(value, root['$defs'][schema['$ref'].split('/')[-1]], root, where)
    if 'oneOf' in schema:
        errors = [validate(value, s, root, where) for s in schema['oneOf']]
        return [] if any(not e for e in errors) else [f'{where}: matches no option']
    kinds = {'object': dict, 'array': list, 'string': str, 'integer': int, 'null': type(None)}
    kind = schema.get('type')
    if kind and not (isinstance(value, kinds[kind]) and not (kind == 'integer' and isinstance(value, bool))):
        return [f'{where}: not {kind}']
    errors = []
    if 'const' in schema and value != schema['const']:
        errors.append(f'{where}: not {schema["const"]}')
    if 'pattern' in schema and not re.search(schema['pattern'], value):
        errors.append(f'{where}: does not match {schema["pattern"]}')
    if 'minimum' in schema and value < schema['minimum']:
        errors.append(f'{where}: below {schema["minimum"]}')
    if kind == 'array':
        for i, item in enumerate(value):
            errors += validate(item, schema.get('items', {}), root, f'{where}[{i}]')
    if kind == 'object':
        props = schema.get('properties', {})
        errors += [f'{where}: missing {k}' for k in schema.get('required', []) if k not in value]
        for key, item in value.items():
            if key in props:
                errors += validate(item, props[key], root, f'{where}.{key}')
            elif isinstance(schema.get('additionalProperties'), dict):
                errors += validate(item, schema['additionalProperties'], root, f'{where}.{key}')
            elif schema.get('additionalProperties') is False:
                errors.append(f'{where}: unexpected {key}')
    return errors


class Diff(unittest.TestCase):
    def test_each_allowed_kind_passes_and_each_disallowed_kind_fails_at_its_line(self):
        self.assertEqual(set(EXPECTED['cases']), LANGUAGES)
        repo = Repo(self)
        base = repo.git('rev-parse', 'HEAD')
        repo.copy(FIXTURES / 'cases', 'cases')
        repo.commit()
        code, out, err = repo.check('diff', '--base', base)
        self.assertEqual(code, 1, err)
        for name, case in EXPECTED['cases'].items():
            with self.subTest(name):
                got = {(line, kind) for path, line, kind in failures(out) if path == f'cases/{name}'}
                self.assertEqual(got, {tuple(f) for f in case['failures']})

    def test_doc_comments_pass_only_under_a_published_docs_path(self):
        repo = Repo(self)
        base = repo.git('rev-parse', 'HEAD')
        repo.copy(FIXTURES / 'cases', 'cases')
        repo.commit()
        code, out, err = repo.check('diff', '--base', base, '--docs', 'cases/')
        self.assertEqual(code, 1, err)
        for name, case in EXPECTED['cases'].items():
            with self.subTest(name):
                got = {(line, kind) for path, line, kind in failures(out) if path == f'cases/{name}'}
                want = {tuple(f) for f in case['failures'] if f[0] not in case['docs']}
                self.assertEqual(got, want)

    def test_the_escape_tag_passes_only_with_a_reason(self):
        repo = Repo(self)
        base = repo.git('rev-parse', 'HEAD')
        repo.write('a.py', 'X = 1  # comment-ok:   \nY = 2  # comment-ok: the synthetic loader reads this line\n')
        repo.write('b.rs', '// comment-ok:\t\nfn b() {}\n/* comment-ok: the synthetic macro scans this */\nfn c() {}\n')
        repo.commit()
        code, out, _ = repo.check('diff', '--base', base)
        self.assertEqual(code, 1)
        self.assertEqual(failures(out), {('a.py', 1, 'escape-tag-reason'), ('b.rs', 1, 'escape-tag-reason')})

    def test_only_added_lines_fail(self):
        repo = Repo(self)
        repo.write('src/old.rs', '// Old narration stays until its cut.\nfn old() {}\n')
        repo.write('src/old.py', '# Old narration.\nX = 1\n')
        base = repo.commit()
        repo.write('src/old.rs', '// Old narration stays until its cut.\nfn old() {}\nfn new() {}\n')
        repo.write('src/old.py', '# Old narration.\nX = 1\nY = 2\n')
        repo.commit()
        code, out, err = repo.check('diff', '--base', base)
        self.assertEqual((code, failures(out)), (0, set()), out + err)
        repo.write('src/old.rs', '// Old narration stays until its cut.\nfn old() {}\nfn new() {}\n// New narration.\nfn newer() {}\n')
        repo.commit()
        code, out, _ = repo.check('diff', '--base', base)
        self.assertEqual((code, failures(out)), (1, {('src/old.rs', 4, 'comment')}))

    def test_quoted_paths_and_undecodable_files_fail_closed(self):
        repo = Repo(self)
        base = repo.git('rev-parse', 'HEAD')
        repo.write('odd "name".py', '# New narration.\nX = 1\n')
        (repo.root / 'latin.rs').write_bytes(b'// caf\xe9 narration\nfn f() {}\n')
        repo.commit()
        code, out, _ = repo.check('diff', '--base', base)
        self.assertEqual((code, failures(out)), (1, {('odd "name".py', 1, 'comment'), ('latin.rs', 1, 'unreadable')}))

    def test_excluded_files_never_fail(self):
        repo = Repo(self)
        base = repo.git('rev-parse', 'HEAD')
        repo.copy(FIXTURES / 'tree', '.')
        repo.commit()
        code, out, _ = repo.check('diff', '--base', base, '--exclude', 'src/**')
        self.assertEqual((code, failures(out)), (0, set()), out)


class Count(unittest.TestCase):
    def tree(self):
        repo = Repo(self)
        repo.copy(FIXTURES / 'tree', '.')
        return repo, repo.commit()

    def count(self, repo, *args):
        code, out, err = repo.check('count', *args)
        self.assertEqual(code, 0, err)
        report = json.loads(out)
        self.assertEqual(validate(report, SCHEMA), [])
        return report

    def test_count_matches_the_known_tree(self):
        repo, head = self.tree()
        report = self.count(repo)
        self.assertIsNone(report['before'])
        after = report['after']
        self.assertEqual(after['rev'], head)
        want = EXPECTED['tree']
        self.assertEqual({k: after[k] for k in want}, want)

    def test_cases_count_their_comment_lines(self):
        repo = Repo(self)
        repo.copy(FIXTURES / 'cases', 'cases')
        repo.commit()
        by_file = self.count(repo, '--by-file')['after'].get('by_file')
        self.assertEqual(by_file, {f'cases/{n}': c['comment_lines'] for n, c in EXPECTED['cases'].items()})

    def test_before_and_after_are_counted_the_same_way(self):
        repo, before = self.tree()
        repo.write('src/main.rs', (repo.root / 'src/main.rs').read_text().replace(' // add', ''))
        after = repo.commit()
        report = self.count(repo, '--before', before, 'src/')
        self.assertEqual(report['paths'], ['src/'])
        got = [((t or {}).get('rev'), (t or {}).get('comment_lines')) for t in (report['before'], report['after'])]
        self.assertEqual(got, [(before, 7), (after, 6)])
        self.assertEqual(self.count(repo, '--at', before, 'src/main.rs')['after']['comment_lines'], 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
