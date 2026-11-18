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
# Loads by path: each call's path argument, by position and by keyword.
LOAD_CALLS = {'spec_from_file_location': (1, 'location'), 'SourceFileLoader': (1, 'path'),
              'run_path': (0, 'path_name')}
MODULE_CALLS = {'import_module', '__import__'}  # the module name: first argument, or name=
PATH_TYPES = ('Path', 'PurePath', 'PosixPath', 'PurePosixPath')
JOINS = ('os.path.join', 'posixpath.join')
PATH_METHODS = ('joinpath', 'with_name', 'resolve', 'absolute')
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


def norm_prefix(v):
    """A partly computed path with its leading known segments normalised (tools/a/../b/ -> tools/b/)."""
    if known(v):
        return norm(v)
    if not v or not isinstance(v[0], str) or '/' not in v[0]:
        return v
    head, _, tail = v[0].rpartition('/')
    head = posixpath.normpath(head) if head else ''
    head = '' if head == '.' else head
    return ((head + '/' if head else '') + tail,) + v[1:] if (head or tail) else v[1:]


def climb(v):
    """What a partly computed file path can reach: an unknown piece may itself hold
    `..` segments, so everything before the first unknown piece says nothing."""
    first = next((i for i, t in enumerate(v) if t is UNKNOWN), 0)
    return v[first:]


def parent(v):
    if not known(v):
        return (UNKNOWN,)
    s = text_of(norm(v))
    if s in ('', '..') or s.startswith('../') or s.startswith('/'):
        return (UNKNOWN,)  # outside the tree
    return (posixpath.dirname(s),)


def could_load(tree, pattern, suffixes=('',)):
    """A load by a partly or wholly computed file path could reach a folder file or
    directory, unless the known text after its first unknown piece rules every one out.
    Whether the file names the folder is no evidence either way."""
    tail = climb(pattern)
    return any(tree.matches(concat(tail, (s,)) if s else tail) for s in suffixes)


def names_folder(tree, pattern):
    """A partly computed path says where it points only when its known part names the folder."""
    segment = posixpath.basename(tree.folder) + '/'
    return any(isinstance(t, str) and (t.startswith(segment) or '/' + segment in t) for t in pattern)


def could_search(tree, pattern):
    """A computed import search path could make imports resolve in the folder: it could
    be the folder, a directory in it, or a directory above it (the repository root too)."""
    tail = climb(pattern)
    if tail == (UNKNOWN,):
        return True
    rx = regex_of(tail)
    return any(rx.fullmatch(d) for d in tree.dirs | tree.above)


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
            raise ValueError(f'no files under {self.folder}')
        self.inside_set = set(self.inside)
        self.all_set = set(self.all)
        self.dirs = {posixpath.dirname(p) for p in self.inside}
        for d in list(self.dirs):
            while d and d != self.folder:
                d = posixpath.dirname(d)
                self.dirs.add(d)
        self.above = set()
        d = self.folder
        while d:
            d = posixpath.dirname(d)
            if d:
                self.above.add(d)
        self.all_dirs = {''}
        for p in self.all:
            d = posixpath.dirname(p)
            while d not in self.all_dirs:
                self.all_dirs.add(d)
                d = posixpath.dirname(d)
        self.own = set(own)

    def text(self, path):
        try:
            data = (self.root / path).read_bytes()
        except OSError as err:  # an unreadable file could hold a reference: fail closed
            raise Refused(f'{path}:1 path: unreadable ({err.strerror})')
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
JS_CALL = re.compile(r'(?<![\w$.])(?:require|import)\s*\(')
JS_STATIC = re.compile(r'''^[ \t]*(?:import|export)\b[^'";]*?\bfrom\s*(['"])([^'"]+)\1|^[ \t]*import\s*(['"])([^'"]+)\3''', re.M)
JS_SUFFIXES = ('', '.js', '.mjs', '.cjs', '/index.js')


COMPUTED = r'(\$\{[^}]*\}|\$\([^)]*\)|\$\w+|`[^`]*`)'


def shell_pattern(arg):
    pieces = re.split(COMPUTED, arg.replace('"', '').replace("'", ''))
    return tuple(UNKNOWN if i % 2 else piece for i, piece in enumerate(pieces) if piece)


def js_code(text, path):
    """Blank comments and regex literals without shifting offsets or newlines.

    Keep strings for load-argument evaluation, and mark template text so it is
    never scanned for loads. Recognise regexes where an expression must begin;
    a numeric operand makes a slash division. Other slash contexts require more
    grammar than this small lexer models, so refuse instead of hiding code.
    """
    out, i, n, quote, inside = [], 0, len(text), None, set()
    previous = ''
    prefixes = {'', '(', '[', '{', '=', ',', ':', ';', '?', '~', '*', '%',
                '&', '|', '^', '+', '-', '/', '<', 'return', 'throw', 'case',
                'delete', 'void', 'typeof', 'new', 'in', 'instanceof', 'else',
                'do', 'default', 'debugger'}

    def refuse(at, reason):
        no = text.count('\n', 0, at) + 1
        raise Refused(f'{path}:{no} native load: {reason}')

    while i < n:
        c = text[i]
        if quote:
            out.append(c)
            if quote == '`':
                inside.add(i)
            if c == '\\' and i + 1 < n:
                out.append(text[i + 1])
                i += 1
            elif c == quote or (c == '\n' and quote != '`'):
                quote = None
        elif c in '\'"`':
            quote = c
            previous = 'literal'
            out.append(c)
        elif text.startswith('//', i):
            j = text.find('\n', i)
            j = n if j < 0 else j
            out.append(' ' * (j - i))
            i = j
            continue
        elif text.startswith('/*', i):
            j = text.find('*/', i + 2)
            j = n if j < 0 else j + 2
            out.append(re.sub(r'[^\n]', ' ', text[i:j]))
            i = j
            continue
        elif c == '/':
            if previous == 'number':
                previous = '/'  # division: its operand can contain a real load
                out.append(c)
            else:
                if previous not in prefixes:
                    refuse(i, 'ambiguous JavaScript slash (regex or division)')
                j, bracket = i + 1, False
                while j < n and text[j] not in '\r\n\u2028\u2029':
                    ch = text[j]
                    if ch == '\\':
                        if j + 1 == n or text[j + 1] in '\r\n\u2028\u2029':
                            break
                        j += 2
                        continue
                    if ch == '[':
                        if bracket:
                            refuse(i, 'ambiguous JavaScript regex character class')
                        bracket = True
                    elif ch == ']':
                        bracket = False
                    elif ch == '/' and not bracket:
                        break
                    j += 1
                if j == n or text[j] != '/' or bracket:
                    refuse(i, 'unterminated JavaScript regex literal')
                j += 1
                flags_at = j
                while j < n and (text[j].isalnum() or text[j] in '_$'):
                    j += 1
                flags = text[flags_at:j]
                if any(f not in 'dgimsuy' for f in flags) or len(set(flags)) != len(flags):
                    refuse(i, 'unsupported JavaScript regex flags')
                out.append(' ' * (j - i))
                previous = 'literal'
                i = j
                continue
        elif c.isalnum() or c in '_$':
            j = i + 1
            while j < n and (text[j].isalnum() or text[j] in '_$'):
                j += 1
            token = text[i:j]
            previous = ('number' if token.isdecimal() else
                        token if token in prefixes and previous != '.' else 'identifier')
            out.append(token)
            i = j
            continue
        elif text[i:i + 2] in ('++', '--'):
            out.append(text[i:i + 2])
            previous = 'increment'
            i += 2
            continue
        else:
            out.append(c)
            if not c.isspace():
                previous = c
        i += 1
    return ''.join(out), inside


def js_split(expr, sep):
    """Split at each top-level separator, outside brackets and strings."""
    parts, depth, quote, cur = [], 0, None, ''
    for i, c in enumerate(expr):
        if quote:
            quote = None if c == quote and expr[i - 1] != '\\' else quote
        elif c in '\'"`':
            quote = c
        elif c in '([{':
            depth += 1
        elif c in ')]}':
            depth -= 1
        elif c == sep and depth == 0:
            parts.append(cur)
            cur = ''
            continue
        cur += c
    return parts + [cur]


def js_args(code, open_at):
    """The text between a call's opening bracket and its matching close."""
    depth, quote = 0, None
    for i in range(open_at, len(code)):
        c = code[i]
        if quote:
            quote = None if c == quote and code[i - 1] != '\\' else quote
        elif c in '\'"`':
            quote = c
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return code[open_at + 1:i]
    return code[open_at + 1:]


class JavaScript:
    """Resolves a load's argument: string literals, templates, `+`, constants assigned
    once in the file, and `new URL(<path>, import.meta.url or such a URL)`."""

    def __init__(self, path, code):
        self.here = posixpath.dirname(path)
        self.code = code

    def const(self, name):
        n = re.escape(name)
        found = re.findall(r'(?<![\w$.])(?:const|let|var)\s+' + n
                           + r'(?:\s*:\s*[\w$.<>\[\]| ]+)?\s*=\s*([^;\n]+)', self.code)
        writes = re.findall(r'(?<![\w$.])' + n + r'(?:\s*:\s*[\w$.<>\[\]| ]+)?\s*'
                            r'(?:[-+*/%&|^]|\*\*|<<|>>>?|\?\?|&&|\|\|)?=(?![=>])', self.code)
        return found[0].strip() if len(found) == 1 and len(writes) == 1 else None

    def value(self, expr, depth=0):
        """('url', pattern) for a URL already resolved to a tree path, or ('spec', pattern)
        for a module specifier; anything else is one unknown piece."""
        expr = re.sub(r'\.(?:href|pathname)\s*$', '', expr.strip())
        if depth > 8 or not expr:
            return 'spec', (UNKNOWN,)
        wrapped = re.fullmatch(r'(?:String|fileURLToPath)\s*\((.*)\)', expr, re.S)
        if wrapped and len(js_split(wrapped.group(1), ',')) == 1:
            return self.value(wrapped.group(1), depth + 1)
        url = re.fullmatch(r'new\s+URL\s*\((.*)\)', expr, re.S)
        if url:
            args = js_split(url.group(1), ',')
            if len(args) < 2:
                return 'spec', (UNKNOWN,)
            rel = self.value(args[0], depth + 1)[1]
            if rel and isinstance(rel[0], str) and rel[0].startswith('/'):
                return 'spec', (UNKNOWN,)  # absolute on the server: not a tree path we can see
            base = args[1].strip()
            if base == 'import.meta.url':
                base_v = (self.here + '/' if self.here else '',)
            else:
                kind, base_v = self.value(base, depth + 1)
                if kind != 'url':
                    base_v = (UNKNOWN,)
                elif known(base_v) and not text_of(base_v).endswith('/'):
                    d = posixpath.dirname(text_of(base_v))
                    base_v = (d + '/' if d else '',)
            out = concat(base_v, rel)
            if known(out):  # a URL ending in `/` names a directory: keep it, so it resolves as a base
                return 'url', concat(norm(out), ('/',)) if text_of(out).endswith('/') else norm(out)
            return 'url', norm_prefix(out)
        parts = js_split(expr, '+')
        if len(parts) > 1:
            kind, out = self.value(parts[0], depth + 1)
            for part in parts[1:]:
                out = concat(out, self.value(part, depth + 1)[1])
            return kind, out
        literal = re.fullmatch(r'''(['"])(.*)\1''', expr, re.S)
        if literal and '\\' not in literal.group(2) and literal.group(1) not in literal.group(2):
            return 'spec', (literal.group(2),)
        if expr.startswith('`') and expr.endswith('`') and len(expr) > 1:
            return 'spec', shell_pattern(expr[1:-1]) or ('',)
        if re.fullmatch(r'[\w$]+', expr):
            assigned = self.const(expr)
            if assigned is not None:
                return self.value(assigned, depth + 1)
        return 'spec', (UNKNOWN,)

    def target(self, kind, v):
        """The tree path pattern a load reaches, or None for a package name."""
        if kind == 'url' or not v or v[0] is UNKNOWN:
            return v or None
        if v[0].startswith('.'):
            return norm_prefix(join((self.here,), v))
        return None  # a package name or an absolute path: never a file of the tree


def other_script_refs(tree, path, text):
    """Shell sources and JavaScript loads: resolved when literal, refused when computed
    and able to reach the folder."""
    refs = []
    suffix = posixpath.splitext(path)[1]
    if suffix in ('.sh', '.bash', '.zsh') or (not suffix and text.startswith('#!') and 'sh' in text.split('\n', 1)[0]):
        for no, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith('#'):
                continue
            for m in SHELL_SOURCE.finditer(line):
                arg = m.group(1)
                literal = re.fullmatch(r'''['"]?([^'"$`]*)['"]?''', arg)
                if literal:
                    refs += [(no, 'native load', t) for t in tree.targets(posixpath.normpath(literal.group(1)))]
                elif could_load(tree, shell_pattern(arg)):
                    raise Refused(f'{path}:{no} native load: computed path ({arg}) could name a file in {tree.folder}')
    if suffix in ('.mjs', '.cjs', '.js', '.ts'):
        code, strings = js_code(text, path)
        js = JavaScript(path, code)
        loads = [(m.start(), js.value(js_args(code, m.end() - 1)))
                 for m in JS_CALL.finditer(code) if m.start() not in strings]
        loads += [(m.start(), ('spec', (m.group(2) or m.group(4),)))
                  for m in JS_STATIC.finditer(code) if m.start() not in strings]
        for at, (kind, v) in sorted(loads, key=lambda x: x[0]):
            no = code.count('\n', 0, at) + 1
            target = js.target(kind, v)
            if target is None:
                continue
            if known(target):
                for s in JS_SUFFIXES:
                    refs += [(no, 'import', t) for t in tree.targets(text_of(target) + s)]
            elif could_load(tree, target, JS_SUFFIXES):
                raise Refused(f'{path}:{no} native load: computed path could name a file in {tree.folder}')
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
        self.alias = {}  # a name bound by an import -> the dotted name it stands for
        for node in ast.walk(self.module):
            if isinstance(node, ast.Import):
                self.alias.update({a.asname: a.name for a in node.names if a.asname})
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                self.alias.update({a.asname or a.name: f'{node.module}.{a.name}' for a in node.names})

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
        if isinstance(node, ast.IfExp):
            pick = (bind or {}).get(node)
            if pick is not None:
                return e(node.body if pick == 0 else node.orelse)
            body, orelse = e(node.body), e(node.orelse)
            return body if body == orelse else (UNKNOWN,)
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
            name = self.name(node.func)
            last = name.rsplit('.', 1)[-1]
            args = node.args
            if last in PATH_TYPES and args:
                v = e(args[0])
                for a in args[1:]:
                    v = join(v, e(a))
                return v
            if name in JOINS and args:
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
            if isinstance(node.func, ast.Attribute) and node.func.attr == 'with_name' and len(args) == 1:
                return join(parent(e(node.func.value)), e(args[0]))
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
        ifs = [n for n in ast.walk(node) if isinstance(n, ast.IfExp)]
        pending = list(used)
        while pending:  # a parameter can reach the sink through local assignments
            name = pending.pop()
            for value in local.get(name, []) + (self.assigns[None].get(name, []) if fn is not None else []):
                for n in ast.walk(value):
                    if isinstance(n, ast.Name) and n.id not in used:
                        used.add(n.id)
                        pending.append(n.id)
                    elif isinstance(n, ast.IfExp) and n not in ifs:
                        ifs.append(n)
        # A name a for loop binds to literal strings takes each of them in turn.
        loops = {**self.loops[None], **(self.loops.get(fn) or {})}
        looped = sorted(n for n in used if n in loops)
        choices = [dict(zip(looped, combo)) for combo in itertools.product(*[[(v,) for v in loops[n]] for n in looped])]
        # A conditional expression takes each of its two branches in turn.
        ifs = ifs[:6]
        choices = [{**c, **dict(zip(ifs, picks))} for c in choices for picks in itertools.product((0, 1), repeat=len(ifs))]
        params = [p for p in self.params(fn) if p in used and p not in looped] if fn is not None else []
        calls = [None]
        if params:
            method = bool(self.params(fn)) and self.params(fn)[0] in ('self', 'cls')
            calls = [c for c in ast.walk(self.module) if isinstance(c, ast.Call) and (
                isinstance(c.func, ast.Attribute) and c.func.attr == fn.name if method
                else isinstance(c.func, ast.Name) and c.func.id == fn.name)] or [None]
        out = []
        names = self.params(fn)
        for call in calls:
            bind = {}
            if call is not None:
                # A method called as self.<name>(...) or cls.<name>(...) binds its first parameter itself.
                skip = 1 if isinstance(call.func, ast.Attribute) else 0
                for i, p in enumerate(names):
                    j = i - skip
                    arg = (call.args[j] if 0 <= j < len(call.args) else
                           next((k.value for k in call.keywords if k.arg == p), None) if j >= 0 else None)
                    bind[p] = self.ev(arg, self.scope.get(call)) if arg is not None else (UNKNOWN,)
            for choice in choices:
                out.append((call.lineno if call is not None else node.lineno,
                            self.ev(node, self.scope.get(node), {**bind, **choice})))
        return out

    def name(self, func):
        """A called name with its imported aliases resolved: `load` from
        `from runpy import run_path as load` is `runpy.run_path`."""
        d = dotted(func)
        head, dot, rest = d.partition('.')
        return self.alias[head] + dot + rest if head in self.alias else d

    def path_call(self, node):
        """A call that builds a path from its arguments or its receiver."""
        if not isinstance(node, ast.Call):
            return False
        name = self.name(node.func)
        return (name.rsplit('.', 1)[-1] in PATH_TYPES or name in JOINS
                or isinstance(node.func, ast.Attribute) and node.func.attr in PATH_METHODS)

    def outermost(self, node):
        """A path expression that is not itself part of a larger one."""
        up = self.up.get(node)
        if isinstance(up, ast.BinOp) and isinstance(up.op, ast.Div):
            return False
        if self.path_call(up) and node in up.args:
            return False
        return not (isinstance(up, ast.Attribute) and up.value is node and up.attr in PATH_METHODS)

    @staticmethod
    def argument(call, pos, keyword):
        if len(call.args) > pos and not any(isinstance(a, ast.Starred) for a in call.args[:pos + 1]):
            return call.args[pos]
        return next((k.value for k in call.keywords if k.arg == keyword), None)

    def module_files(self, roots, parts, first):
        """The folder files an import of PARTS loads from ROOTS: each package's
        `__init__.py` and the module, through regular and namespace packages. With
        FIRST, Python's first match wins; otherwise every root counts."""
        tree, found = self.tree, []
        dirs = roots
        for i, part in enumerate(parts):
            portions, nxt = [], []
            for d in dirs:
                stem = posixpath.join(d, part)
                if stem + '/__init__.py' in tree.all_set:
                    found += tree.targets(stem + '/__init__.py')
                    nxt.append(stem)
                elif stem + '.py' in tree.all_set:
                    found += tree.targets(stem + '.py')
                elif stem in tree.all_dirs:
                    portions.append(stem)  # a namespace package portion
                    continue
                else:
                    continue
                if first:
                    break
            dirs = nxt if (first and nxt) else nxt + portions
            if not dirs:
                break
        return found

    def refs(self):
        tree, refs = self.tree, []
        search = []  # (line, pattern, at module level, inserted in front)
        sinks = []  # (line, kind, pattern)
        modules = []  # (node, dotted name)
        dynamic = []  # (line, module-name pattern) of computed module loads
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
                name = self.name(node.func)
                last = name.rsplit('.', 1)[-1]
                if name in ('sys.path.insert', 'sys.path.append') and node.args:
                    front = (name.endswith('insert') and isinstance(node.args[0], ast.Constant)
                             and node.args[0].value == 0)
                    for line, v in self.values(node.args[-1]):
                        search.append((line, v, self.scope.get(node) is None, front))
                elif last in LOAD_CALLS:
                    arg = self.argument(node, *LOAD_CALLS[last])
                    if arg is not None:
                        sinks += [(line, 'native load', v) for line, v in self.values(arg)]
                elif last == 'exec' and node.args:
                    for inner in ast.walk(node.args[0]):
                        if isinstance(inner, ast.Call) and self.name(inner.func) == 'open':
                            arg = self.argument(inner, 0, 'file')
                            if arg is not None:
                                sinks += [(line, 'native load', v) for line, v in self.values(arg)]
                elif last in MODULE_CALLS:
                    arg = self.argument(node, 0, 'name')
                    for line, v in self.values(arg) if arg is not None else []:
                        if known(v):
                            modules.append((node, text_of(v)))
                        else:
                            dynamic.append((line, v))
                if self.path_call(node) and self.outermost(node):
                    sinks += [(line, 'script path', v) for line, v in self.values(node)]
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div) and self.outermost(node):
                sinks += [(line, 'script path', v) for line, v in self.values(node)]
        for line, kind, v in sinks:
            v = norm_prefix(v)
            if known(v):
                refs += [(line, kind, t) for t in tree.targets(text_of(v))]
            elif kind != 'script path':
                if could_load(tree, v):
                    raise Refused(f'{self.path}:{line} {kind}: computed path could name a file in {tree.folder}')
            elif names_folder(tree, v):
                refs += [(line, kind, t) for t in tree.matches(v) if t in tree.inside_set]
        entries = []
        for line, v, top, front in search:
            v = norm_prefix(v)
            if known(v):
                entries.append((line, text_of(v), top, front))
            elif could_search(tree, v):
                raise Refused(f'{self.path}:{line} import: computed search path could reach {tree.folder}')
        here = posixpath.dirname(self.path)
        roots = [here] + [d for _, d, _, _ in entries]
        for line, v in dynamic:
            # A computed module name, through every root the file can import from.
            name = tuple(t.replace('.', '/') if isinstance(t, str) else t for t in v)
            for d in roots:
                full = join((d,), name)
                if not specific(name):
                    reach = d == '' or d in tree.above or d == tree.folder or d.startswith(tree.folder + '/')
                else:
                    reach = any(tree.matches(concat(full, (s,)) if s else full) for s in ('', '.py', '/__init__.py'))
                if reach:
                    raise Refused(f'{self.path}:{line} import: computed module name could load a file in {tree.folder}')
        for node, mod in modules:
            parts = mod.split('.')
            if self.scope.get(node) is None:
                # At module level Python searches in order and the first match wins.
                order = [here]
                for line, d, top, front in entries:
                    if top and line < node.lineno:
                        order = [d] + order if front else order + [d]
                found = self.module_files(order, parts, True)
            else:
                found = self.module_files(roots, parts, False)  # inside a function: any of them
            refs += [(node.lineno, 'import', t) for t in found]
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
            kind = kind_of(path, tree.text(path))
            if kind is None:
                continue
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
    try:
        stay, move, refused = split(root, args.folder, tuple(args.own) if args.own else OWN)
    except ValueError as err:
        parser.error(str(err))
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
