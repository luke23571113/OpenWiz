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
only mention files; they never read one. Comments in code do count. A fixture
is read when:

1. a reader holds a path ending in it with at least two parts
   (`../fixtures/a.json`, `send/tell.json`, `FIXTURES/'m1/README.md'`);
2. its folder is in use and it is that folder's `scenario.json`, the file the
   fake `room-cli` and fake `gh` start from, or a fixture already read in the
   same folder quotes its name (`"stdout_file": "a.json"`);
3. its folder, or a folder above it, is named by a path with at least two
   parts that ends there (`fixtures/walked'`, `room-cli-0.43.1/{parent}`), and
   a reader quotes its name (`fixture("drift.json")`) or its folder holds no
   `scenario.json`: a named folder is read whole, subfolders included, since a
   test can build a subfolder's name at run time; a scenario folder inside it
   still needs its own name.

Folders count from a fixed boundary, the outermost `fixtures` folder above the
fixture (or the repository's top), never from the roots given: scanning a
narrower or overlapping root gives the same answer as scanning the wider one.

A folder is in use when it is a root, when rule 3 names it or a folder above it
(scenario folders apart), or when its parent is in use and a reader quotes its
name (`Scenario::new("send")`, `"extends": "complete"`). A quoted file name
alone never keeps a file in a folder only in use by name: `"README.md"` and
`"service"` quoted somewhere do not read `service/README.md`. Name matches are
whole: `terminal/send.rs` and `send-extra` do not name `send`. A match anywhere
keeps the file, so a common name can keep more than it should; a test that
builds a path some other way is caught by the full suite in CI.
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
    if (repo / path).is_dir():
        return False  # a tracked link to a folder
    if name.suffix in CODE:
        return True
    if name.suffix:
        return False
    try:
        with open(repo / path, 'rb') as f:
            return f.read(2) == b'#!'
    except OSError as err:
        raise ScanError(f'cannot read tracked file {path}: {err.strerror}') from err


def read_text(repo, path):
    """A tracked file's text. One that can't be read stops the scan: read as
    empty, it would turn the fixtures it names into deletions."""
    try:
        return (repo / path).read_text('utf-8', 'replace')
    except OSError as err:
        raise ScanError(f'cannot read tracked file {path}: {err.strerror}') from err


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
        quoted = {m.group(2) for m in QUOTED.finditer(text)}
        self.quoted |= quoted
        return quoted

    def file(self, path):
        return any(s in self.inside for s in suffixes(path))

    def folder(self, path):
        return any(s in self.ends for s in suffixes(path))


def boundary(path):
    """The folder a fixture's folders count from: the outermost `fixtures`
    folder above it (`tests/fixtures`, which tests name only to reach what is
    inside), or the repository's top when there is none. Every folder below it,
    a scanned root included, can be named by path and so read whole."""
    parts = PurePosixPath(path).parent.parts
    return '/'.join(parts[:parts.index('fixtures') + 1]) if 'fixtures' in parts else '.'


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
    # Folders count from a fixed boundary, never from the roots given, so a
    # narrower or overlapping root gives the same answer (#853 R1).
    folders = set()
    for p in fixtures:
        stop = boundary(p)
        f = PurePosixPath(p).parent
        while str(f) != stop and str(f) != '.':
            folders.add(str(f))
            f = f.parent
    scenarios = {str(PurePosixPath(p).parent) for p in fixtures if PurePosixPath(p).name == SCENARIO}

    read, in_use, anchored, siblings = set(), set(roots), set(), {}
    while True:
        before = (len(read), len(in_use))
        named = {f for f in folders if refs.folder(f)}
        anchored |= {f for f in folders if any(f == n or f.startswith(n + '/') for n in named)}
        in_use |= named | (anchored - scenarios)
        found = True
        while found:
            found = {f for f in folders - in_use
                     if str(PurePosixPath(f).parent) in in_use and PurePosixPath(f).name in refs.quoted}
            in_use |= found
        for p in fixtures:
            folder, name = str(PurePosixPath(p).parent), PurePosixPath(p).name
            if p not in read and (
                    refs.file(p)
                    or (folder in in_use and (name == SCENARIO or name in siblings.get(folder, ())))
                    or (folder in in_use and folder in anchored
                        and (name in refs.quoted or folder not in scenarios))):
                read.add(p)
                siblings.setdefault(folder, set()).update(refs.add(read_text(repo, p)))
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
