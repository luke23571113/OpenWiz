#!/usr/bin/env python3
"""WM1 (#1056): the war room's split checker (contracts/wizroom.v1.md, "The split rule").

    python3 -I ci/wizroom/split.py --root <tree> [--folder tools/war-room] [--own <path>]...

Reads a repository tree and prints the stay set, each file with the reference
that keeps it public, and the move set. A file in the folder stays public if a
public file outside it reaches it by import, native load, or a path in a
script, workflow, loop or contract; files reached from staying files stay too.
A reference that could name a file in the folder but cannot be resolved is
refused with its location. Exit 0 with a report, 1 refused, 2 usage error.
It writes nothing and makes no network call.
"""
import argparse
import ast
import itertools
from collections import deque
import os
from pathlib import Path
import posixpath
import re
import subprocess
import sys

sys.dont_write_bytecode = True

FOLDER = 'tools/war-room'
# The war room's own files outside its folder: they leave with it, so they are
# not public consumers (contract: "The split rule").
OWN = ('.github/workflows/war-room.yml', '.github/workflows/war-room-proof.yml')
# This checker's synthetic trees are test data, not consumers of the real folder.
FIXTURES = 'ci/wizroom/fixtures/'
SCRIPT_SUFFIXES = {'.py', '.sh', '.bash', '.zsh', '.mjs', '.cjs', '.js', '.ts', '.rs'}
SKIP_DIRS = {'.git', 'node_modules', '__pycache__', 'target'}
UNKNOWN = None  # one unknown piece of a path pattern
LOAD_CALLS = {'spec_from_file_location': 1, 'SourceFileLoader': 1, 'run_path': 0}
MODULE_CALLS = {'import_module', '__import__'}
PRIORITY = {'import': 0, 'native load': 0}


class Refused(Exception):
    pass


def files_of(root):
    if (root / '.git').exists():
        out = subprocess.run(['git', '-C', str(root), 'ls-files', '-z'], capture_output=True, check=True).stdout
        return sorted(p for p in out.decode('utf-8', 'surrogateescape').split('\0') if p and (root / p).is_file())
    found = []
    for base, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        rel = Path(base).relative_to(root).as_posix()
        found += [n if rel == '.' else f'{rel}/{n}' for n in names]
    return sorted(found)


def kind_of(path, text):
    """The class a file outside the folder counts as, or None (not counted)."""
    name = posixpath.basename(path)
    if path.startswith('.github/workflows/') and name.endswith(('.yml', '.yaml')):
        return 'workflow'
    if path.startswith('.github/actions/') and name in ('action.yml', 'action.yaml'):
        return 'workflow'
    if path.startswith('loops/') and name.endswith('.json'):
        return 'loop'
    if path.startswith('contracts/'):
        return 'contract'
    if posixpath.splitext(name)[1] in SCRIPT_SUFFIXES or text.startswith('#!'):
        return 'script'
    return None


PATH_KIND = {'workflow': 'workflow path', 'loop': 'loop path', 'contract': 'contract link',
             'script': 'script path', None: 'path'}


# Path patterns: a tuple of known strings and UNKNOWN pieces, read left to right.

def known(v):
    return v is not None and all(t is not UNKNOWN for t in v)


def text_of(v):
    return ''.join(v)


def concat(a, b):
    if a is None or b is None:
        return (UNKNOWN,)
    out = list(a)
    for t in b:
        if out and isinstance(out[-1], str) and isinstance(t, str):
            out[-1] += t
        else:
            out.append(t)
    return tuple(out)


def join(a, b):
    if a is None or b is None:
        return (UNKNOWN,)
    if known(b) and text_of(b).startswith('/'):
        return b
    if known(a) and text_of(a) in ('', '.'):
        return b
    return concat(concat(a, ('/',)), b)


def norm(v):
    if not known(v):
        return v
    s = posixpath.normpath(text_of(v))
    return ('',) if s == '.' else (s,)


def parent(v):
    if not known(v):
        return (UNKNOWN,)
    s = text_of(norm(v))
    if s in ('', '..') or s.startswith('../') or s.startswith('/'):
        return (UNKNOWN,)  # outside the tree
    return (posixpath.dirname(s),)


def could_name(tree, pattern, text):
    """A computed load could name a folder file: its known parts match one, or it is
    wholly computed in a file that names the folder."""
    if specific(pattern):
        return bool(tree.matches(pattern))
    return tree.folder in text or posixpath.basename(tree.folder) in text


def names_folder(tree, pattern):
    """A partly computed path says where it points only when its known part names the folder."""
    segment = posixpath.basename(tree.folder) + '/'
    return any(isinstance(t, str) and (t.startswith(segment) or '/' + segment in t) for t in pattern)


def could_name_dir(tree, pattern):
    return specific(pattern) and any(m in tree.dirs for m in tree.matches(pattern))


def regex_of(v):
    return re.compile(''.join(re.escape(t) if isinstance(t, str) else '.+' for t in v))


def specific(v):
    """A partly known pattern says something only if it names more than separators."""
    return any(isinstance(t, str) and t.strip('/.') for t in v)


class Tree:
    def __init__(self, root, folder, own):
        self.root = root
        self.folder = folder.strip('/')
        self.all = files_of(root)
        self.inside = [p for p in self.all if p.startswith(self.folder + '/')]
        if not self.inside:
            raise SystemExit(f'split: no files under {self.folder} in {root}')
        self.inside_set = set(self.inside)
        self.all_set = set(self.all)
        self.dirs = {posixpath.dirname(p) for p in self.inside}
        for d in list(self.dirs):
            while d and d != self.folder:
                d = posixpath.dirname(d)
                self.dirs.add(d)
        self.own = set(own)

    def text(self, path):
        data = (self.root / path).read_bytes()
        return '' if b'\0' in data[:8192] else data.decode('utf-8', 'replace')

    def targets(self, path):
        """The folder's files a known path names: a file, or every file under a directory."""
        path = posixpath.normpath(path)
        if path in self.inside_set:
            return [path]
        if path in self.dirs and path != self.folder:
            return [p for p in self.inside if p.startswith(path + '/')]
        return []

    def matches(self, pattern):
        rx = regex_of(pattern)
        return [p for p in self.inside if rx.fullmatch(p)] + [d for d in sorted(self.dirs) if rx.fullmatch(d)]


# References: (line, kind, target) for each folder file a file reaches; refusals raise.

LITERAL = None


def literal_refs(tree, path, text, kind):
    global LITERAL
    if LITERAL is None or LITERAL[0] != tree.folder:
        LITERAL = (tree.folder, re.compile(r'(?<![\w.-])' + re.escape(tree.folder) + r'/([^\s\'"`()\[\]<>{},;:*?|$\\#]+)'))
    refs = []
    for no, line in enumerate(text.splitlines(), 1):
        for m in LITERAL[1].finditer(line):
            for t in tree.targets(tree.folder + '/' + m.group(1).rstrip('.')):
                refs.append((no, PATH_KIND[kind], t))
    return refs


MD_LINK = re.compile(r'\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)|^\s*\[[^\]]+\]:\s*<?(\S+?)>?(?:\s|$)')


def markdown_refs(tree, path, text, kind):
    refs = []
    for no, line in enumerate(text.splitlines(), 1):
        for m in MD_LINK.finditer(line):
            target = (m.group(1) or m.group(2)).split('#', 1)[0]
            if not target or re.match(r'^[a-z][a-z0-9+.-]*:', target, re.I) or target.startswith('/'):
                continue
            for t in tree.targets(posixpath.join(posixpath.dirname(path), target)):
                refs.append((no, PATH_KIND[kind], t))
    return refs


SHELL_SOURCE = re.compile(r'(?:^|[;&|(]\s*|\bthen\s+|\bdo\s+)(?:\.|source)\s+(\S+)')
JS_LOAD = re.compile(r'\b(?:require|import)\s*\(\s*([^)]*?)\s*\)')
JS_STATIC = re.compile(r'''^\s*(?:import|export)\b[^'"]*\bfrom\s*['"]([^'"]+)['"]|^\s*import\s*['"]([^'"]+)['"]''')


COMPUTED = r'(\$\{[^}]*\}|\$\([^)]*\)|\$\w+|`[^`]*`)'


def shell_pattern(arg):
    pieces = re.split(COMPUTED, arg.replace('"', '').replace("'", ''))
    return tuple(UNKNOWN if i % 2 else piece for i, piece in enumerate(pieces) if piece)


def js_pattern(arg):
    out = ()
    for part in arg.split('+'):
        part = part.strip()
        literal = re.fullmatch(r'''(['"])([^'"]*)\1''', part)
        if literal:
            out = concat(out, (literal.group(2),))
        elif part.startswith('`') and part.endswith('`') and len(part) > 1:
            out = concat(out, shell_pattern(part[1:-1]))
        else:
            out = concat(out, (UNKNOWN,))
    return out


def other_script_refs(tree, path, text):
    """Shell sources and JavaScript loads: resolved when literal, refused when computed into the folder."""
    refs = []
    here = posixpath.dirname(path)
    suffix = posixpath.splitext(path)[1]
    for no, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith(('#', '//')):
            continue
        args = []
        if suffix in ('.sh', '.bash', '.zsh') or (not suffix and text.startswith('#!') and 'sh' in text.split('\n', 1)[0]):
            args += [(m.group(1), False) for m in SHELL_SOURCE.finditer(line)]
        if suffix in ('.mjs', '.cjs', '.js', '.ts'):
            args += [(m.group(1), True) for m in JS_LOAD.finditer(line)]
            args += [(f"'{m.group(1) or m.group(2)}'", True) for m in JS_STATIC.finditer(line)]
        for arg, relative in args:
            url = re.search(r'''new\s+URL\(\s*(['"])([^'"]*)\1\s*,\s*import\.meta\.url''', arg) if relative else None
            if url:
                arg = f"'{url.group(2) if url.group(2).startswith('.') else './' + url.group(2)}'"
            literal = re.fullmatch(r'''(['"])([^'"$`]*)\1''', arg) if relative else re.fullmatch(r'''['"]?([^'"$`]*)['"]?''', arg)
            if literal:
                target = literal.group(literal.lastindex)
                base = here if relative and target.startswith('.') else ''
                full = posixpath.normpath(posixpath.join(base, target))
                for cand in (full, full + '.js', full + '.mjs', full + '/index.js'):
                    refs += [(no, 'import' if relative else 'native load', t) for t in tree.targets(cand)]
                continue
            pattern = js_pattern(arg) if relative else shell_pattern(arg)
            if relative and pattern and isinstance(pattern[0], str) and pattern[0].startswith('.'):
                pattern = join((here,), pattern)
            if could_name(tree, pattern, text):
                raise Refused(f'{path}:{no} native load: computed path ({arg}) could name a file in {tree.folder}')
    return refs


def dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return '.'.join(reversed(parts))
    return ''


class Python:
    """A small evaluator for the path expressions Python files use to find each other."""

    def __init__(self, tree, path, text):
        self.tree, self.path, self.text = tree, path, text
        self.module = ast.parse(text)
        self.scope = {}  # node -> enclosing function
        self.up = {}  # node -> parent node
        self.assigns = {None: {}}
        self.functions = {}
        self.loops = {None: {}}  # function -> {name: the literal strings a for loop binds it to}
        self._index(self.module, None)

    def _index(self, node, fn):
        for child in ast.iter_child_nodes(node):
            self.scope[child] = fn
            self.up[child] = node
            inner = fn
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                inner = child
                self.assigns[child] = {}
                self.loops[child] = {}
                if not isinstance(child, ast.Lambda):
                    self.functions.setdefault(child.name, []).append(child)
            elif (isinstance(child, (ast.For, ast.comprehension)) and isinstance(child.target, ast.Name)
                    and isinstance(child.iter, (ast.Tuple, ast.List)) and child.iter.elts
                    and all(isinstance(x, ast.Constant) and isinstance(x.value, str) for x in child.iter.elts)):
                self.loops[fn].setdefault(child.target.id, []).extend(x.value for x in child.iter.elts)
            if isinstance(child, (ast.Assign, ast.AnnAssign)) and child.value is not None:
                targets = child.targets if isinstance(child, ast.Assign) else [child.target]
                for t in targets:
                    if isinstance(t, ast.Name):
                        self.assigns[fn].setdefault(t.id, []).append(child.value)
            self._index(child, inner)

    def params(self, fn):
        if fn is None:
            return []
        a = fn.args
        return [x.arg for x in a.posonlyargs + a.args + a.kwonlyargs]

    def ev(self, node, fn, bind=None, depth=0):
        if depth > 40:
            return (UNKNOWN,)
        e = lambda n: self.ev(n, fn, bind, depth + 1)
        if isinstance(node, ast.Constant):
            return (node.value,) if isinstance(node.value, str) else (UNKNOWN,)
        if isinstance(node, ast.JoinedStr):
            out = ()
            for v in node.values:
                out = concat(out, e(v.value) if isinstance(v, ast.FormattedValue) else e(v))
            return out
        if isinstance(node, ast.Name):
            if node.id == '__file__':
                return (self.path,)
            if bind is not None and node.id in bind:
                return bind[node.id]
            scope = fn
            while True:
                if scope is not None and node.id in self.params(scope):
                    return (UNKNOWN,)
                values = self.assigns.get(scope, {}).get(node.id)
                if values:
                    results = {e(v) for v in values}
                    return results.pop() if len(results) == 1 else (UNKNOWN,)
                if scope is None:
                    return (UNKNOWN,)
                scope = self.scope.get(scope)
        if isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.Div):
                return join(e(node.left), e(node.right))
            if isinstance(node.op, ast.Add):
                return concat(e(node.left), e(node.right))
            return (UNKNOWN,)
        if isinstance(node, ast.Attribute) and node.attr == 'parent':
            return parent(e(node.value))
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute)
                and node.value.attr == 'parents' and isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, int)):
            v = e(node.value.value)
            for _ in range(node.slice.value + 1):
                v = parent(v)
            return v
        if isinstance(node, ast.Call):
            name = dotted(node.func)
            last = name.rsplit('.', 1)[-1]
            args = node.args
            if last in ('Path', 'PurePath', 'PosixPath', 'PurePosixPath') and args:
                v = e(args[0])
                for a in args[1:]:
                    v = join(v, e(a))
                return v
            if name in ('os.path.join', 'posixpath.join') and args:
                v = e(args[0])
                for a in args[1:]:
                    v = join(v, e(a))
                return v
            if name in ('str', 'os.fspath', 'os.path.abspath', 'os.path.realpath', 'os.path.normpath') and len(args) == 1:
                return e(args[0])
            if name in ('os.path.dirname', 'posixpath.dirname') and len(args) == 1:
                return parent(e(args[0]))
            if isinstance(node.func, ast.Attribute) and node.func.attr in ('resolve', 'absolute'):
                return e(node.func.value)
            if isinstance(node.func, ast.Attribute) and node.func.attr == 'joinpath':
                v = e(node.func.value)
                for a in args:
                    v = join(v, e(a))
                return v
        return (UNKNOWN,)

    def values(self, node):
        """Each value a sink argument can take, with the line that supplies it.

        An argument naming a parameter of the enclosing function is read at each
        call of that function in this file (one level)."""
        fn = self.scope.get(node)
        while fn is not None and not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fn = self.scope.get(fn)
        used = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
        local = self.assigns.get(fn, {})
        pending = list(used)
        while pending:  # a parameter can reach the sink through local assignments
            for value in local.get(pending.pop(), []):
                for n in ast.walk(value):
                    if isinstance(n, ast.Name) and n.id not in used:
                        used.add(n.id)
                        pending.append(n.id)
        # A name a for loop binds to literal strings takes each of them in turn.
        loops = {**self.loops[None], **(self.loops.get(fn) or {})}
        looped = sorted(n for n in used if n in loops)
        choices = [dict(zip(looped, combo)) for combo in itertools.product(*[[(v,) for v in loops[n]] for n in looped])]
        params = [p for p in self.params(fn) if p in used and p not in looped] if fn is not None else []
        calls = [None]
        if params:
            calls = [c for c in ast.walk(self.module)
                     if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == fn.name] or [None]
        out = []
        names = self.params(fn)
        for call in calls:
            bind = {}
            if call is not None:
                for i, p in enumerate(names):
                    arg = call.args[i] if i < len(call.args) else next((k.value for k in call.keywords if k.arg == p), None)
                    bind[p] = self.ev(arg, self.scope.get(call)) if arg is not None else (UNKNOWN,)
            for choice in choices:
                out.append((call.lineno if call is not None else node.lineno,
                            self.ev(node, self.scope.get(node), {**bind, **choice})))
        return out

    def refs(self):
        tree, refs = self.tree, []
        search = []  # (line, pattern, at module level, inserted in front)
        sinks = []  # (line, kind, pattern)
        modules = []  # (line, dotted name)
        dynamic = []  # lines of computed module loads
        for node in ast.walk(self.module):
            if isinstance(node, ast.Import):
                modules += [(node, a.name) for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = posixpath.dirname(self.path)
                    for _ in range(node.level - 1):
                        base = posixpath.dirname(base)
                    mod = (node.module or '').replace('.', '/')
                    for a in node.names:
                        for cand in (posixpath.join(base, mod), posixpath.join(base, mod, a.name)):
                            for c in (cand + '.py', cand + '/__init__.py'):
                                refs += [(node.lineno, 'import', t) for t in tree.targets(c)]
                else:
                    modules.append((node, node.module))
                    modules += [(node, f'{node.module}.{a.name}') for a in node.names]
            elif isinstance(node, ast.Call):
                name = dotted(node.func)
                last = name.rsplit('.', 1)[-1]
                if name in ('sys.path.insert', 'sys.path.append') and node.args:
                    front = (name.endswith('insert') and isinstance(node.args[0], ast.Constant)
                             and node.args[0].value == 0)
                    for line, v in self.values(node.args[-1]):
                        search.append((line, v, self.scope.get(node) is None, front))
                elif last in LOAD_CALLS:
                    pos = LOAD_CALLS[last]
                    arg = node.args[pos] if len(node.args) > pos else next(
                        (k.value for k in node.keywords if k.arg in ('location', 'path', 'path_name')), None)
                    if arg is not None:
                        sinks += [(line, 'native load', v) for line, v in self.values(arg)]
                elif last == 'exec' and node.args:
                    for inner in ast.walk(node.args[0]):
                        if isinstance(inner, ast.Call) and dotted(inner.func) == 'open' and inner.args:
                            sinks += [(line, 'native load', v) for line, v in self.values(inner.args[0])]
                elif last in MODULE_CALLS and node.args:
                    for line, v in self.values(node.args[0]):
                        if known(v):
                            modules.append((node, text_of(v)))
                        else:
                            dynamic.append(line)
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                if not (isinstance(self.up.get(node), ast.BinOp) and isinstance(self.up[node].op, ast.Div)):
                    sinks += [(line, 'script path', v) for line, v in self.values(node)]
        for line, kind, v in sinks:
            v = norm(v)
            if known(v):
                refs += [(line, kind, t) for t in tree.targets(text_of(v))]
            elif kind != 'script path':
                if could_name(tree, v, self.text):
                    raise Refused(f'{self.path}:{line} {kind}: computed path could name a file in {tree.folder}')
            elif names_folder(tree, v):
                refs += [(line, kind, t) for t in tree.matches(v) if t in tree.inside_set]
        entries = []
        for line, v, top, front in search:
            v = norm(v)
            if known(v):
                entries.append((line, text_of(v), top, front))
            elif could_name_dir(tree, v):
                raise Refused(f'{self.path}:{line} import: computed search path could be in {tree.folder}')
        here = posixpath.dirname(self.path)
        inside = lambda d: d == tree.folder or d.startswith(tree.folder + '/')
        if dynamic and any(inside(d) for _, d, _, _ in entries):
            raise Refused(f'{self.path}:{dynamic[0]} import: computed module name could load a file in {tree.folder}')
        for node, mod in modules:
            parts = mod.split('.')
            if self.scope.get(node) is None:
                # At module level Python searches in order and the first folder with the module wins.
                order = [here]
                for line, d, top, front in entries:
                    if top and line < node.lineno:
                        order = [d] + order if front else order + [d]
                order = [next((d for d in order if any(c in tree.all_set for c in (
                    posixpath.join(d, parts[0]) + '.py', posixpath.join(d, parts[0], '__init__.py')))), None)]
            else:
                order = [here] + [d for _, d, _, _ in entries]  # inside a function: any of them
            for d in order:
                if d is None:
                    continue
                for i in range(1, len(parts) + 1):
                    stem = posixpath.join(d, *parts[:i])
                    for c in (stem + '.py', stem + '/__init__.py'):
                        refs += [(node.lineno, 'import', t) for t in tree.targets(c)]
        return refs


def file_refs(tree, path, kind):
    text = tree.text(path)
    if not text:
        return []
    refs = literal_refs(tree, path, text, kind)
    if path.endswith('.md'):
        refs += markdown_refs(tree, path, text, kind)
    if path.endswith('.py') or (text.startswith('#!') and 'python' in text.split('\n', 1)[0]):
        try:
            refs += Python(tree, path, text).refs()
        except SyntaxError as err:
            if posixpath.basename(tree.folder) in text:
                raise Refused(f'{path}:{err.lineno or 1} import: unparsable Python names {tree.folder}')
    elif kind == 'script' or path.startswith(tree.folder + '/'):
        refs += other_script_refs(tree, path, text)
    return sorted(set(refs), key=lambda r: (r[0], PRIORITY.get(r[1], 1), r[2]))


def split(root, folder=FOLDER, own=OWN):
    tree = Tree(root, folder, own)
    stay, queue, refused = {}, deque(), []

    def reach(source, refs):
        for line, kind, target in refs:
            if target not in stay:
                stay[target] = f'{source}:{line} {kind}'
                queue.append(target)

    for path in tree.all:
        if path.startswith(tree.folder + '/') or path in tree.own or path.startswith(FIXTURES):
            continue
        try:
            text = tree.text(path)
        except OSError:
            continue
        kind = kind_of(path, text)
        if kind is None:
            continue
        try:
            reach(path, file_refs(tree, path, kind))
        except Refused as err:
            refused.append(str(err))
    while queue:
        path = queue.popleft()
        try:
            reach(path, file_refs(tree, path, kind_of(path, tree.text(path))))
        except Refused as err:
            refused.append(str(err))
    move = [p for p in tree.inside if p not in stay]
    return stay, move, refused


def main(argv=None):
    parser = argparse.ArgumentParser(description='Print the war room folder\'s stay and move sets.')
    parser.add_argument('--root', required=True, help='the repository tree to read')
    parser.add_argument('--folder', default=FOLDER, help=f'the war room folder (default {FOLDER})')
    parser.add_argument('--own', action='append',
                        help='a war-room file outside the folder that leaves with it (repeatable; '
                             'default: ' + ', '.join(OWN) + ')')
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        parser.error(f'not a directory: {root}')
    stay, move, refused = split(root, args.folder, tuple(args.own) if args.own else OWN)
    if refused:
        for line in refused:
            print('refused ' + line, file=sys.stderr)
        print(f'split: refused {len(refused)} reference(s); no stay or move set', file=sys.stderr)
        return 1
    for path in sorted(stay):
        print(f'stay {path} <- {stay[path]}')
    for path in move:
        print(f'move {path}')
    print(f'total: {len(stay)} stay, {len(move)} move')
    return 0


if __name__ == '__main__':
    sys.exit(main())
