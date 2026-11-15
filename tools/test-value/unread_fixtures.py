#!/usr/bin/env python3
"""List the fixture files no test reads (TV2, #804).

Run: python3 -I tools/test-value/unread_fixtures.py [--repo DIR] [ROOT ...]

Each ROOT is a fixture folder, relative to the repository (default:
tests/fixtures). The script prints, one per line and sorted, every tracked file
under a ROOT that nothing reads, and exits 1 when it printed any, 0 when none
(the empty result), and 2 when it could not scan: a missing root, a root with no
tracked files, a root outside the repository, or no Git checkout. A failed scan
never prints the empty result.

The reading is static and leans towards keeping. A reader is a tracked code
file outside the scanned roots (by extension, or a `#!` script) or a fixture
already found read. Prose and data (Markdown, JSON, logs, CI's selection map)
only mention files; they never read one. A fixture is read when:

1. a reader holds a path ending in it with at least two parts
   (`../fixtures/a.json`, `send/tell.json`, `FIXTURES/'m1/README.md'`);
2. its folder is in use and it is that folder's `scenario.json`, the file the
   fake `room-cli` and fake `gh` start from;
3. its folder is in use and a reader quotes its name (`"stdout_file": "a.json"`);
4. its folder is named by a path with at least two parts that ends there
   (`fixtures/walked'`, `room-cli-0.43.1/{parent}`) and holds no
   `scenario.json`: such a folder is read whole.

A folder is in use when it is a root, when rule 4's path names it, or when its
parent is in use and a reader quotes its name (`Scenario::new("send")`,
`"extends": "complete"`). Name matches are whole: `terminal/send.rs` and
`send-extra` do not name `send`. A match anywhere keeps the file, so a common
name keeps more than it should; nothing is listed only because a test builds
its path in an unusual way, the full suite in CI checks that.
"""
import argparse
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

sys.dont_write_bytecode = True
SELF = {'tools/test-value/unread_fixtures.py', 'tools/test-value/test_unread_fixtures.py'}
CODE = {'.rs', '.py', '.sh', '.bash', '.zsh', '.mjs', '.cjs', '.js', '.jsx', '.ts', '.tsx',
        '.mts', '.cts', '.toml', '.yml', '.yaml', '.c', '.h'}
NAME = re.compile(r'[\w.-]+')
TOKEN = re.compile(r'[\w./-]+')
QUOTED = re.compile(r'''(?=(["'])([\w.-]+)\1)''')
SCENARIO = 'scenario.json'


class ScanError(Exception):
    pass


def tracked(repo):
    try:
        out = subprocess.run(['git', '-C', str(repo), 'ls-files', '-z'],
                             capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as err:
        raise ScanError(f'not a Git checkout: {repo}') from err
    return [p for p in out.decode('utf-8', 'surrogateescape').split('\0') if p]


def normal_root(repo, root):
    path = PurePosixPath(root.replace('\\', '/'))
    if path.is_absolute() or '..' in path.parts or not path.parts or path.parts == ('.',):
        raise ScanError(f'root must be a folder inside the repository: {root}')
    if not (repo / path).is_dir():
        raise ScanError(f'root is not a folder: {root}')
    return str(path)


def under(path, roots):
    return any(path.startswith(r + '/') for r in roots)


def is_code(repo, path):
    name = PurePosixPath(path)
    if path in SELF:
        return False
    if name.suffix in CODE:
        return True
    if name.suffix:
        return False
    try:
        with open(repo / path, 'rb') as f:
            return f.read(2) == b'#!'
    except OSError:
        return False


def read_text(repo, path):
    try:
        return (repo / path).read_text('utf-8', 'replace')
    except OSError:
        return ''


def suffixes(path):
    """Every ending of `path` with at least two parts."""
    parts = path.split('/')
    return ['/'.join(parts[i:]) for i in range(len(parts) - 1)]


class References:
    """What the readers name: every run of two or more whole path parts inside
    a path-like word (`fixtures/a.json` in `../fixtures/a.json`), every such
    run that ends a word (a folder named by path, `dir/` included), and every
    quoted name."""

    def __init__(self):
        self.inside, self.ends, self.quoted = set(), set(), set()

    def add(self, text):
        for token in TOKEN.findall(text):
            parts = token.rstrip('/').split('/')
            for i in range(len(parts)):
                for j in range(i + 2, len(parts) + 1):
                    if all(parts[i:j]):
                        self.inside.add('/'.join(parts[i:j]))
                if i < len(parts) - 1 and all(parts[i:]):
                    self.ends.add('/'.join(parts[i:]))
        self.quoted.update(m.group(2) for m in QUOTED.finditer(text))

    def file(self, path):
        return any(s in self.inside for s in suffixes(path))

    def folder(self, path):
        return any(s in self.ends for s in suffixes(path))


def scan(repo, roots):
    repo = Path(repo).resolve()
    files = tracked(repo)
    roots = [normal_root(repo, r) for r in roots]
    fixtures = sorted(p for p in files if under(p, roots))
    for root in roots:
        if not any(p.startswith(root + '/') for p in fixtures):
            raise ScanError(f'root has no tracked files: {root}')
    for p in fixtures:
        if not NAME.fullmatch(PurePosixPath(p).name):
            raise ScanError(f'cannot match this file name in a reader: {p}')
    refs = References()
    for p in files:
        if not under(p, roots) and is_code(repo, p):
            refs.add(read_text(repo, p))
    folders = set()
    for p in fixtures:
        f = PurePosixPath(p).parent
        while str(f) not in roots:
            folders.add(str(f))
            f = f.parent
    scenarios = {str(PurePosixPath(p).parent) for p in fixtures if PurePosixPath(p).name == SCENARIO}

    read, in_use, whole = set(), set(roots), set()
    while True:
        before = (len(read), len(in_use))
        named = {f for f in folders if refs.folder(f)}
        whole |= {f for f in folders - scenarios
                  if any(f == n or f.startswith(n + '/') for n in named)}
        in_use |= named | whole
        found = True
        while found:
            found = {f for f in folders - in_use
                     if str(PurePosixPath(f).parent) in in_use and PurePosixPath(f).name in refs.quoted}
            in_use |= found
        for p in fixtures:
            folder, name = str(PurePosixPath(p).parent), PurePosixPath(p).name
            if p not in read and (
                    refs.file(p)
                    or (folder in in_use and (name == SCENARIO or name in refs.quoted))
                    or folder in whole):
                read.add(p)
                refs.add(read_text(repo, p))
        if (len(read), len(in_use)) == before:
            break
    return [p for p in fixtures if p not in read]


def main(argv=None):
    parser = argparse.ArgumentParser(description='List the fixture files no test reads.')
    parser.add_argument('--repo', default='.', help='the repository (default: the current folder)')
    parser.add_argument('roots', nargs='*', default=['tests/fixtures'],
                        help='fixture folders, relative to the repository (default: tests/fixtures)')
    args = parser.parse_args(argv)
    try:
        unread = scan(args.repo, args.roots)
    except ScanError as err:
        print(f'unread_fixtures: {err}', file=sys.stderr)
        return 2
    for path in unread:
        print(path)
    return 1 if unread else 0


if __name__ == '__main__':
    sys.exit(main())
