#!/usr/bin/env python3
"""Turn what a traced test touched into repository files (#432, K15).

Used by trace.py, in the job that ran the test (it needs that job's
target/). What a test touched becomes:

- a file in the repository: itself, whether or not it was there (a test
  that looked for a missing file is that file's reader, should it appear);
- a Rust build product under target/ (a test binary, a program it ran, a
  library a compiler read): the sources in its dep-info (a library's
  `lib<crate>-<hash>.rlib` has `<crate>-<hash>.d`; an uplifted program
  without one is the unit it is hard-linked to). A test binary of a
  workspace crate adds every crate that crate depends on, with their
  Cargo.toml; an openwiz-tests binary adds the workspace crates its sources
  name (`openwiz_core`, ...) and theirs. When two packages have a target of
  one name, the one whose folder holds the unit's own sources owns it. A
  registry crate (no workspace owner, no repository source) is Cargo.lock,
  which pins it. Cargo's bookkeeping (fingerprints, build-script folders,
  scratch) is not an input. Any other build product that exists is one the
  selector can't account for: the test is left out of the map (the
  selector always runs it);
- a node_modules folder: its package's package.json and package-lock.json;
- git's own index or objects: the test can see every file through git, so
  it is left out of the map;
- a path reached through a repository link (a tracked symlink, such as
  `skills` or `.claude/skills/<name>`) also needs each link on its way, and
  one inside the installed skills (`.wizskills/`, never tracked) needs
  wizskills.lock, which pins them: only those two can change it in a diff.

Listed folders are kept the same way (a listing inside a build product
counts for nothing: what it holds comes from sources already kept).
"""
import glob
import json
import os
import re
import subprocess

CRATE = re.compile(r'\bopenwiz_[a-z0-9_]+\b')
BOOKKEEPING = re.compile(r'target(/[^/]+)?/(\.rustc_info\.json|CACHEDIR\.TAG|\.cargo-lock|\.fingerprint(/.*)?|'
                         r'build(/.*)?|incremental(/.*)?|tmp(/.*)?|.+\.d|\.package-cache)$|target/tmp(/.*)?$|target$')
GIT_HARMLESS = re.compile(r'\.git(/(HEAD|config|commondir|description|info(/.*)?|hooks(/.*)?|refs(/.*)?|packed-refs'
                          r'|logs(/.*)?|shallow|FETCH_HEAD|ORIG_HEAD))?$')
NODE = re.compile(r'((?:.+/)?)node_modules(/.*)?$')


TESTS_PACKAGE = 'openwiz-tests'
INSTALLED, PIN = '.wizskills', 'wizskills.lock'
LIB_KINDS = {'lib', 'rlib', 'dylib', 'cdylib', 'staticlib', 'proc-macro'}


class Ambiguous(Exception):
    pass


def index(metadata, real_root):
    """(packages, owners) from `cargo metadata --no-deps`: each package's
    folder and path dependencies, and, for each place a build product can
    have, the packages owning a target of each name:
    ('lib', crate name), ('deps', crate name: a library, binary or test, as
    target/<profile>/deps names them), ('bin', name), ('example', name)."""
    pkgs, owners = {}, {}
    for p in metadata['packages']:
        d = os.path.relpath(os.path.dirname(p['manifest_path']), real_root)
        deps = sorted({x['name'] for x in p['dependencies'] if x.get('path')})
        pkgs[p['name']] = {'dir': d, 'deps': deps}
        for t in p['targets']:
            kinds, crate = set(t['kind']), t['name'].replace('-', '_')
            places = []
            if kinds & LIB_KINDS:
                places += [('lib', crate), ('deps', crate)]
            if kinds & {'bin'}:
                places += [('deps', crate), ('bin', t['name'])]
            if kinds & {'test', 'bench'}:
                places += [('deps', crate)]
            if kinds & {'example'}:
                places += [('example', t['name']), ('example', crate)]
            for key in places:
                owners.setdefault(key, set()).add(p['name'])
    return pkgs, owners


class Resolver:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.real = os.path.realpath(self.root)
        self._meta = None
        self._depinfo = None

    # Paths.
    def rel(self, path):
        """The repository-relative path, or None for a path outside it."""
        for base in (self.root, self.real):
            if path == base:
                return '.'
            if path.startswith(base + '/'):
                return path[len(base) + 1:]
        return None

    # Cargo.
    def meta(self):
        if self._meta is None:
            out = subprocess.run(['cargo', 'metadata', '--format-version', '1', '--no-deps', '--locked', '--offline'],
                                 cwd=self.root, capture_output=True, text=True, check=True).stdout
            self._meta = index(json.loads(out), self.real)
        return self._meta

    def owner(self, place, name):
        """The one package whose target this is, or None (none, or ambiguous:
        two packages' targets with one name, #1579 R5)."""
        found = self.meta()[1].get((place, name), set())
        return next(iter(found)) if len(found) == 1 else None

    def closure(self, names):
        pkgs = self.meta()[0]
        seen, todo = set(), list(names)
        while todo:
            n = todo.pop()
            if n in seen or n not in pkgs:
                continue
            seen.add(n)
            todo.extend(pkgs[n]['deps'])
        return seen

    def manifests(self, names):
        """These packages' and their dependencies' Cargo.toml and build.rs."""
        pkgs = self.meta()[0]
        files = set()
        for n in self.closure(names):
            files.add(os.path.join(pkgs[n]['dir'], 'Cargo.toml'))
            if os.path.isfile(os.path.join(self.root, pkgs[n]['dir'], 'build.rs')):
                files.add(os.path.join(pkgs[n]['dir'], 'build.rs'))
        return files

    def package_files(self, names):
        """Every source of these packages and those they depend on, with their
        manifests; Ambiguous if a build product among them has no one owner."""
        wanted = self.closure(names)
        files = self.manifests(names)
        for stem, srcs in self.depinfo().items():
            if self.meta()[1].get(('deps', self.crate_name(stem)), set()) & wanted:
                pkg = self.unit_owner(stem)
                if pkg is None:
                    raise Ambiguous(stem)
                if pkg in wanted:
                    files |= srcs
        return files

    @staticmethod
    def crate_name(stem):
        crate = stem.rsplit('-', 1)[0] if re.search(r'-[0-9a-f]{16}$', stem) else stem
        return re.sub(r'^lib', '', crate).replace('-', '_')

    def unit_owner(self, stem):
        """The one workspace package this unit was built from, or None: by its
        crate name, and when two packages share that name (a `loops` test in
        each), by which one's folder holds the unit's own sources."""
        found = self.meta()[1].get(('deps', self.crate_name(stem)), set())
        if len(found) < 2:
            return next(iter(found), None)
        pkgs = self.meta()[0]

        def home(src):
            here = [n for n in found if pkgs[n]['dir'] == '.' or src.startswith(pkgs[n]['dir'] + '/')]
            return max(here, key=lambda n: len(pkgs[n]['dir']), default=None)
        homes = {home(s) for s in self.depinfo()[stem] if s.endswith('.rs')}
        return homes.pop() if len(homes) == 1 and None not in homes else None

    def unit(self, name):
        """The dep-info stem of a file in deps/, or None: a library
        `lib<crate>-<hash>.rlib` (or .rmeta, ...) has `<crate>-<hash>.d`."""
        stem = re.sub(r'\.(rlib|rmeta|so|dylib|a)$', '', name)
        if stem not in self.depinfo() and stem.startswith('lib'):
            stem = stem[3:]
        return stem if stem in self.depinfo() else None

    def twin(self, full):
        """The deps/ unit an uplifted program is a hard link of, or None."""
        try:
            st = os.stat(full)
            deps = os.path.join(os.path.dirname(full), 'deps')
            found = {self.unit(n) for n in os.listdir(deps) if not n.endswith('.d')
                     and os.path.samestat(st, os.stat(os.path.join(deps, n)))}
        except OSError:
            return None
        return found.pop() if len(found) == 1 and None not in found else None

    def depinfo(self):
        """{dep-info file's stem: the repository sources it lists}."""
        if self._depinfo is None:
            self._depinfo = {}
            for d in glob.glob(os.path.join(self.root, 'target/*/deps/*.d')):
                self._depinfo[os.path.basename(d)[:-2]] = self.read_depinfo(d)
        return self._depinfo

    def read_depinfo(self, path):
        srcs = set()
        with open(path, errors='surrogateescape') as f:
            text = f.read().replace('\\\n', ' ')
        for line in text.splitlines():
            if ':' not in line or line.startswith('#'):
                continue
            target, _, deps = line.partition(': ')
            for tok in re.split(r'(?<!\\) ', deps):
                tok = tok.replace('\\ ', ' ').strip()
                if not tok:
                    continue
                p = os.path.normpath(tok if os.path.isabs(tok) else os.path.join(self.root, tok))
                r = self.rel(p)
                if r and not r.startswith('target/') and r != '.':
                    srcs.add(r)
        return srcs

    def artifact(self, rel):
        """The sources a build product under target/ comes from, or None."""
        full = os.path.join(self.root, rel)
        stem = os.path.basename(rel)
        folder = os.path.dirname(rel)
        if folder.endswith('/deps'):
            return self.unit_files(self.unit(stem))
        # An uplifted program (target/<profile>/<bin> or examples/<example>):
        # its dep-info lists every source, and its package (#1579 R6) adds
        # its own and its dependencies' manifests and build scripts. One
        # `cargo test` uplifted without dep-info is its deps/ unit.
        uplifted = full + '.d'
        if not os.path.isfile(uplifted):
            return self.unit_files(self.twin(full))
        place = 'example' if folder.endswith('/examples') else 'bin'
        if place == 'example' and re.search(r'-[0-9a-f]{16}$', stem):
            stem = self.crate_name(stem)  # the example's own unit, beside its uplifted copy
        pkg = self.owner(place, stem)
        if pkg is None:
            return None
        return self.read_depinfo(uplifted) | self.manifests([pkg])

    def unit_files(self, stem):
        """The sources of one deps/ unit (a dep-info stem), or None."""
        if stem is None:
            return None
        files = set(self.depinfo()[stem])
        pkg = self.unit_owner(stem)
        if pkg is None:
            # A registry crate: no workspace target of its name, and no
            # repository source. Its sources are pinned by the lockfile.
            if not files and not self.meta()[1].get(('deps', self.crate_name(stem))):
                return {'Cargo.lock'}
            return None
        try:
            if pkg == TESTS_PACKAGE:
                used = set()
                for src in files:
                    if src.endswith('.rs'):
                        try:
                            with open(os.path.join(self.root, src), errors='replace') as f:
                                names = set(CRATE.findall(f.read()))
                        except FileNotFoundError:
                            continue
                        for c in names:
                            found = self.meta()[1].get(('lib', c), set())
                            if len(found) > 1:
                                return None  # a library name two packages share: no one owner
                            used |= found
                used.discard(TESTS_PACKAGE)
                own = self.meta()[0][TESTS_PACKAGE]['dir']
                mine = {os.path.join(own, 'Cargo.toml')}
                if os.path.isfile(os.path.join(self.root, own, 'build.rs')):
                    mine.add(os.path.join(own, 'build.rs'))
                return files | self.package_files(used) | mine
            return files | self.package_files([pkg])
        except Ambiguous:
            return None

    # The two answers.
    def resolve(self, touched, listed):
        """(files, folders, None), or ([], [], why) if a test is to be left out."""
        files, dirs = set(), set()
        for path in touched:
            r = self.rel(path)
            if r is None or r == '.':
                continue
            why = self._one(r, files, os.path.join(self.root, r))
            if why:
                return [], [], why
        for path in listed:
            r = self.rel(path)
            if r is None:
                continue
            if r.startswith('target/') or r == 'target' or NODE.match(r) \
                    or r == '.git' or r.startswith('.git/'):
                continue
            else:
                dirs.add(r)
        for p in sorted(files) + sorted(dirs):
            files |= self.via(p)
        return sorted(files), sorted(dirs), None

    def via(self, r, depth=0):
        """What else a repository path depends on: each repository link on
        its way, and wizskills.lock for one inside the installed skills."""
        out = {PIN} if r == INSTALLED or r.startswith(INSTALLED + '/') else set()
        parts = r.split('/')
        for i in range(1, len(parts) + 1):
            link = os.path.join(self.root, *parts[:i])
            if os.path.islink(link):
                out.add('/'.join(parts[:i]))
                target = os.path.normpath(os.path.join(os.path.dirname(link), os.readlink(link), *parts[i:]))
                nxt = self.rel(target)
                if nxt and nxt != '.' and depth < 40:
                    out |= self.via(nxt, depth + 1)
                break
        return out

    def _one(self, r, files, full):
        if r == '.git' or r.startswith('.git/'):
            if GIT_HARMLESS.match(r):
                return None
            return f'reads git\'s own {r}, through which it can see any file'
        n = NODE.match(r)
        if n:
            files.update({n.group(1) + 'package.json', n.group(1) + 'package-lock.json'})
            return None
        if r == 'target' or r.startswith('target/'):
            if BOOKKEEPING.match(r) or not os.path.isfile(full):
                return None
            srcs = self.artifact(r)
            if srcs is None:
                return f'reads {r}, a build product it can\'t trace to its sources'
            files.update(srcs)
            return None
        if os.path.isdir(full):
            return None  # a folder looked at, not listed: its files are what count
        files.add(r)
        return None
