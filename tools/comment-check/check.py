#!/usr/bin/env python3
import argparse
import ast
from bisect import bisect_right
import fnmatch
import io
import json
import re
import subprocess
import sys
import tokenize

SCHEMA = 'openwiz.comments.v1'
EXTENSIONS = {
    '.rs': 'rust', '.py': 'python', '.pyi': 'python', '.sh': 'shell', '.bash': 'shell',
    '.yml': 'yaml', '.yaml': 'yaml', '.toml': 'toml',
    '.js': 'javascript', '.mjs': 'javascript', '.cjs': 'javascript', '.jsx': 'javascript',
    '.ts': 'typescript', '.mts': 'typescript', '.cts': 'typescript', '.tsx': 'typescript',
    '.css': 'css', '.html': 'html', '.htm': 'html',
}
SHEBANGS = [(re.compile(r'^#!.*\bpython[0-9.]*\b'), 'python'), (re.compile(r'^#!.*\b(sh|bash|dash|zsh)\b'), 'shell'),
            (re.compile(r'^#!.*\bnode\b'), 'javascript')]
VENDORED = {'vendor', 'vendored', 'third_party', 'third-party', 'node_modules'}
LICENCE_FILE = re.compile(r'^(licen[cs]e|copying|notice)([.-].*)?$', re.I)
GENERATED = re.compile(r'@generated|\bDO NOT EDIT\b')
ESCAPE = re.compile(r'^comment-ok:(.*)$', re.S)
WARNING = re.compile(r'^(SECURITY|SAFETY|PRIVACY|DATA LOSS):\s*\S')
EXTERNAL = re.compile(r'^External:')
OUR_LINK = re.compile(r'github\.com/(openwizdev|jparker2006)/', re.I)
LINK = re.compile(r'https?://[^\s)>\]"\']+')
POINTER = re.compile(r'https://github\.com/jparker2006/ClosedWiz/(issues|pull)/[1-9][0-9]*#issuecomment-[1-9][0-9]*')
LICENCE = re.compile(r'SPDX-License-Identifier:|\bCopyright\b|\bLicensed under\b')
DIRECTIVE = re.compile(
    r'^(noqa\b|type:\s*ignore\b|pragma:|pylint:|fmt:\s*(off|on|skip)\b|ruff:|mypy:|pyright:|isort:|'
    r'eslint(-disable|-enable)?\b|prettier-ignore\b|@ts-(ignore|expect-error|nocheck)\b|biome-ignore\b|'
    r'shellcheck\s|yamllint\s|stylelint-(disable|enable)|istanbul\s+ignore\b|c8\s+ignore\b|v8\s+ignore\b)')
REASON = re.compile(r'\s(--|#)\s*\S')
CODING = re.compile(r'^[ \t\f]*#.*?coding[:=]')


class Span:
    def __init__(self, l1, c1, l2, c2, text, doc=False):
        self.l1, self.c1, self.l2, self.c2, self.text, self.doc = l1, c1, l2, c2, text, doc


class Lines:
    def __init__(self, text):
        self.starts = [0] + [m.end() for m in re.finditer('\n', text)]

    def at(self, i):
        line = bisect_right(self.starts, i)
        return line, i - self.starts[line - 1]

    def span(self, start, end, text, doc=False):
        l1, c1 = self.at(start)
        l2, c2 = self.at(end)
        return Span(l1, c1, l2, c2, text, doc)


def skip_quoted(s, i, quote, newline_ends=True):
    n = len(s)
    j = i + 1
    while j < n:
        c = s[j]
        if c == '\\':
            j += 2
            continue
        if c == quote:
            return j + 1
        if c == '\n' and newline_ends:
            return j
        j += 1
    return n


def block_comment(s, i, lines, out, nested=False):
    depth, j, n = 1, i + 2, len(s)
    while j < n and depth:
        if nested and s.startswith('/*', j):
            depth, j = depth + 1, j + 2
        elif s.startswith('*/', j):
            depth, j = depth - 1, j + 2
        else:
            j += 1
    body = s[i + 2:j - 2] if not depth else s[i + 2:]
    doc = (body.startswith('*') and not body.startswith('**') and body != '*') or body.startswith('!')
    out.append(lines.span(i, j, '\n'.join(l.strip().lstrip('*').strip() for l in body.split('\n')).strip(), doc))
    return j


def line_comment(s, i, lines, out, marker, doc=False):
    j = s.find('\n', i)
    j = len(s) if j < 0 else j
    out.append(lines.span(i, j, s[i + len(marker):j].lstrip('/!').strip() if marker == '//' else s[i:j].lstrip('#').strip(), doc))
    return j


RUST_RAW = re.compile(r'[bc]?r(#*)"')
RUST_CHAR = re.compile(r"'(\\(x[0-9a-fA-F]{2}|u\{[0-9a-fA-F]{1,6}\}|.)|[^\\'\n])'")
WORD = re.compile(r'[A-Za-z_$][A-Za-z0-9_$]*')


def scan_rust(s):
    lines, out, i, n = Lines(s), [], 0, len(s)
    while i < n:
        c = s[i]
        if s.startswith('//', i):
            body = s[i + 2:]
            i = line_comment(s, i, lines, out, '//', (body.startswith('/') and not body.startswith('//')) or body.startswith('!'))
        elif s.startswith('/*', i):
            i = block_comment(s, i, lines, out, nested=True)
        elif c == '"':
            i = skip_quoted(s, i, '"', newline_ends=False)
        elif c == "'":
            m = RUST_CHAR.match(s, i)
            i = m.end() if m else i + 1
        elif c.isalpha() or c == '_':
            m = RUST_RAW.match(s, i)
            if m:
                end = s.find('"' + m.group(1), m.end())
                i = n if end < 0 else end + 1 + len(m.group(1))
            else:
                i = WORD.match(s, i).end()
        else:
            i += 1
    return out


def scan_hash(s, triple=True):
    lines, out, i, n = Lines(s), [], 0, len(s)
    while i < n:
        c = s[i]
        if c == '#':
            i = line_comment(s, i, lines, out, '#')
        elif triple and (s.startswith('"""', i) or s.startswith("'''", i)):
            end = s.find(s[i:i + 3], i + 3)
            while end > 0 and s[end - 1] == '\\' and s[i] == '"':
                end = s.find(s[i:i + 3], end + 1)
            i = n if end < 0 else end + 3
        elif c == '"':
            i = skip_quoted(s, i, '"')
        elif c == "'":
            end = s.find("'", i + 1)
            nl = s.find('\n', i + 1)
            i = n if end < 0 else (nl if 0 <= nl < end else end + 1)
        else:
            i += 1
    return out


def scan_python(s):
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(s).readline))
        tree = ast.parse(s)
    except (SyntaxError, tokenize.TokenError, ValueError):
        return scan_hash(s)
    out = [Span(t.start[0], t.start[1], t.end[0], t.end[1], t.string.lstrip('#').strip())
           for t in tokens if t.type == tokenize.COMMENT]
    src = s.split('\n')
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            out.append(Span(node.lineno, 0, node.end_lineno, len(src[node.end_lineno - 1]), node.value.value.strip(), True))
    return out


HEREDOC = re.compile(r'<<(-?)[ \t]*(["\']?)([A-Za-z0-9_.-]+)\2')
SHELL_BREAK = ' \t\n;&|()<>'


def scan_shell(s):
    lines, out, i, n, pending = Lines(s), [], 0, len(s), []
    while i < n:
        c = s[i]
        if c == '\n' and pending:
            i += 1
            for strip, word in pending:
                while i < n:
                    end = s.find('\n', i)
                    end = n if end < 0 else end
                    line = s[i:end]
                    i = end + 1
                    if (line.lstrip('\t') if strip else line) == word:
                        break
            pending = []
        elif c == '#' and (i == 0 or s[i - 1] in SHELL_BREAK):
            i = line_comment(s, i, lines, out, '#')
        elif c == "'":
            end = s.find("'", i + 1)
            i = n if end < 0 else end + 1
        elif c == '$' and s.startswith("$'", i):
            i = skip_quoted(s, i + 1, "'", newline_ends=False)
        elif c in '"`':
            i = skip_quoted(s, i, c, newline_ends=False)
        elif c == '\\':
            i += 2
        elif s.startswith('<<', i) and not s.startswith('<<<', i):
            m = HEREDOC.match(s, i)
            if m:
                pending.append((m.group(1) == '-', m.group(3)))
                i = m.end()
            else:
                i += 2
        else:
            i += 1
    return out


YAML_BLOCK = re.compile(r'^(\s*(?:-\s+)?)([^\s#][^#]*?):\s*[|>][0-9+-]*\s*$')
YAML_ITEM_BLOCK = re.compile(r'^(\s*)-\s+[|>][0-9+-]*\s*$')


def yaml_line_comment(line):
    quote = None
    for j, c in enumerate(line):
        if quote:
            if c == '\\' and quote == '"':
                continue
            if c == quote:
                quote = None
        elif c in '"\'' and (j == 0 or line[j - 1] in ' \t[{,'):
            quote = c
        elif c == '#' and (j == 0 or line[j - 1] in ' \t'):
            return j
    return -1


def scan_yaml(s):
    src = s.split('\n')
    out, block, run = [], None, []

    def flush():
        if run:
            first = run[0][0]
            for sp in scan_shell('\n'.join(text for _, text in run)):
                out.append(Span(sp.l1 + first - 1, sp.c1, sp.l2 + first - 1, sp.c2, sp.text))
            run.clear()

    for number, line in enumerate(src, 1):
        if block is not None:
            indent = len(line) - len(line.lstrip(' '))
            if not line.strip() or indent > block[0]:
                if block[1]:
                    run.append((number, line))
                continue
            flush()
            block = None
        j = yaml_line_comment(line)
        code = line if j < 0 else line[:j]
        if j >= 0:
            out.append(Span(number, j, number, len(line), line[j:].lstrip('#').strip()))
        m = YAML_BLOCK.match(code)
        if m:
            block = (len(m.group(1)), m.group(2).strip() == 'run')
        elif YAML_ITEM_BLOCK.match(code):
            block = (len(YAML_ITEM_BLOCK.match(code).group(1)), False)
    flush()
    return out


REGEX_AFTER = set('(,=:[!&|?{};+-*%<>~^}') | {'', 'return', 'typeof', 'case', 'do', 'else', 'in', 'of', 'new',
                                             'delete', 'void', 'throw', 'yield', 'await', 'instanceof'}


def skip_regex(s, i):
    j, n, cls = i + 1, len(s), False
    while j < n and s[j] != '\n':
        c = s[j]
        if c == '\\':
            j += 2
            continue
        if c == '[':
            cls = True
        elif c == ']':
            cls = False
        elif c == '/' and not cls:
            j += 1
            while j < n and (s[j].isalnum()):
                j += 1
            return j
        j += 1
    return j


def scan_js(s, base=0, lines=None, out=None):
    lines = lines or Lines(s)
    out = [] if out is None else out
    i, n, stack, prev = base, len(s), [], ''
    if base == 0 and s.startswith('#!'):
        i = n if s.find('\n') < 0 else s.find('\n')

    def template(j):
        while j < n:
            if s[j] == '\\':
                j += 2
            elif s[j] == '`':
                return j + 1, 'a'
            elif s.startswith('${', j):
                stack.append(0)
                return j + 2, '('
            else:
                j += 1
        return n, 'a'

    while i < n:
        c = s[i]
        if c in ' \t\r\n':
            i += 1
        elif s.startswith('//', i):
            i = line_comment(s, i, lines, out, '//')
        elif s.startswith('/*', i):
            i = block_comment(s, i, lines, out)
        elif c in '"\'':
            i, prev = skip_quoted(s, i, c), 'a'
        elif c == '`':
            i, prev = template(i + 1)
        elif c == '{':
            if stack:
                stack[-1] += 1
            i, prev = i + 1, '{'
        elif c == '}':
            if stack and stack[-1] == 0:
                stack.pop()
                i, prev = template(i + 1)
            else:
                if stack:
                    stack[-1] -= 1
                i, prev = i + 1, '}'
        elif c == '/':
            if prev in REGEX_AFTER:
                i, prev = skip_regex(s, i), 'a'
            else:
                i, prev = i + 1, '/'
        elif c.isalnum() or c in '_$':
            m = WORD.match(s, i)
            word = m.group(0) if m else c
            i, prev = i + len(word), (word if word in REGEX_AFTER else 'a')
        else:
            i, prev = i + 1, c
    return out


def scan_css(s, base=0, lines=None, out=None):
    lines = lines or Lines(s)
    out = [] if out is None else out
    i, n = base, len(s)
    while i < n:
        if s.startswith('/*', i):
            i = block_comment(s, i, lines, out)
        elif s[i] in '"\'':
            i = skip_quoted(s, i, s[i])
        else:
            i += 1
    return out


HTML_OPEN = re.compile(r'<!--|<(script|style)\b([^>]*)>', re.I)
JS_TYPE = re.compile(r'\btype\s*=\s*["\']?([^"\'\s>]+)', re.I)


def scan_html(s):
    lines, out, i = Lines(s), [], 0
    while True:
        m = HTML_OPEN.search(s, i)
        if not m:
            return out
        if m.group(0) == '<!--':
            end = s.find('-->', m.end())
            end = len(s) if end < 0 else end + 3
            out.append(lines.span(m.start(), end, s[m.end():max(m.end(), end - 3)].strip()))
            i = end
            continue
        tag = m.group(1).lower()
        close = re.compile(r'</' + tag + r'\s*>', re.I).search(s, m.end())
        stop = len(s) if not close else close.start()
        kind = JS_TYPE.search(m.group(2))
        if tag == 'style':
            scan_css(s[:stop], m.end(), lines, out)
        elif not kind or re.search(r'javascript|module|ecmascript', kind.group(1), re.I):
            scan_js(s[:stop], m.end(), lines, out)
        i = stop if not close else close.end()


SCANNERS = {'rust': scan_rust, 'python': scan_python, 'shell': scan_shell, 'yaml': scan_yaml, 'toml': scan_hash,
            'javascript': scan_js, 'typescript': scan_js, 'css': scan_css, 'html': scan_html}


def language(path, text):
    for ext, name in EXTENSIONS.items():
        if path.endswith(ext):
            return name
    if '.' not in path.rsplit('/', 1)[-1]:
        first = text.split('\n', 1)[0]
        for pattern, name in SHEBANGS:
            if pattern.match(first):
                return name
    return None


def matches(path, globs):
    for g in globs:
        g = g[2:] if g.startswith('./') else g
        if g.endswith('/') and path.startswith(g):
            return True
        if fnmatch.fnmatchcase(path, g) or fnmatch.fnmatchcase(path, g.rstrip('/') + '/*'):
            return True
    return False


def excluded(path, text, attributes, extra):
    parts = path.split('/')
    if VENDORED & set(parts[:-1]) or LICENCE_FILE.match(parts[-1]) or path in attributes:
        return True
    if parts[-1].endswith(('.min.js', '.min.css')) or any(a == 'fixtures' and b == 'comments' for a, b in zip(parts, parts[1:-1])):
        return True
    return bool(GENERATED.search('\n'.join(text.split('\n', 5)[:5]))) or matches(path, extra)


class Judged:
    def __init__(self, text, lang, docs):
        self.src = text.split('\n')
        self.failures, kept, masked = [], [], []
        for sp in SCANNERS[lang](text):
            (masked if self.is_code(sp, lang) else kept).append(sp)
        self.lines = set()
        for sp in kept:
            self.lines.update(range(sp.l1, sp.l2 + 1))
        covered = {}
        for sp in kept + masked:
            for ln in range(sp.l1, sp.l2 + 1):
                covered.setdefault(ln, []).append(sp)
        self.code = {ln for ln, line in enumerate(self.src, 1) if self.has_code(ln, line, covered.get(ln, []))}
        self.bad_lines = set()
        for block in self.blocks(kept):
            reason = self.judge(block, docs)
            if reason:
                lines = set()
                for sp in block:
                    lines.update(range(sp.l1, sp.l2 + 1))
                self.failures.append((lines, reason))
                self.bad_lines |= lines

    def is_code(self, sp, lang):
        if sp.l1 == 1 and sp.c1 == 0 and self.src[0].startswith('#!'):
            return True
        if lang == 'python' and sp.l1 <= 2 and CODING.match(self.src[sp.l1 - 1]):
            return True
        if DIRECTIVE.match(sp.text):
            if REASON.search(sp.text):
                return True
            sp.directive = True
        return False

    def has_code(self, ln, line, spans):
        chars = list(line)
        for sp in spans:
            start = sp.c1 if sp.l1 == ln else 0
            stop = sp.c2 if sp.l2 == ln else len(chars)
            chars[start:stop] = [' '] * (stop - start)
        return bool(''.join(chars).strip())

    def full(self, sp):
        return not self.src[sp.l1 - 1][:sp.c1].strip() and not self.src[sp.l2 - 1][sp.c2:].strip()

    def blocks(self, spans):
        spans = sorted(spans, key=lambda sp: (sp.l1, sp.c1))
        block = []
        for sp in spans:
            last = block[-1] if block else None
            if (last and self.full(sp) and self.full(last) and sp.l1 == last.l2 + 1 and sp.doc == last.doc
                    and not getattr(sp, 'directive', False) and not getattr(last, 'directive', False)):
                block.append(sp)
                continue
            if block:
                yield block
            block = [sp]
        if block:
            yield block

    def judge(self, block, docs):
        text = '\n'.join(sp.text for sp in block).strip()
        first = text.split('\n', 1)[0].strip()
        if getattr(block[0], 'directive', False):
            return 'directive-reason'
        m = ESCAPE.match(first)
        if m:
            return None if m.group(1).strip() else 'escape-tag-reason'
        if WARNING.match(first) or POINTER.search(text):
            return None
        if EXTERNAL.match(first):
            return None if any(not OUR_LINK.search(u) for u in LINK.findall(text)) else 'external-link'
        if LICENCE.search(text) and not any(ln in self.code for ln in range(1, block[0].l1)):
            return None
        if docs and all(sp.doc for sp in block):
            return None
        return 'comment'


MESSAGES = {
    'comment': 'a comment outside the allowed kinds: delete it, or turn what it meant into a name, a test or a check',
    'escape-tag-reason': 'the escape tag needs a reason after "comment-ok:"',
    'external-link': 'an "External:" constraint needs a link to the outside source',
    'directive-reason': 'a lint or formatter switch needs its reason after " -- "',
}


def git(*args, binary=False):
    run = subprocess.run(['git', *args], capture_output=True)
    if run.returncode:
        raise SystemExit(f'comment-check: git {" ".join(args)}: {run.stderr.decode(errors="replace").strip()}')
    return run.stdout if binary else run.stdout.decode()


def read_blobs(rev, paths):
    if not paths:
        return {}
    run = subprocess.run(['git', 'cat-file', '--batch'], input=''.join(f'{rev}:{p}\n' for p in paths).encode(),
                         capture_output=True)
    data, out, i = run.stdout, {}, 0
    for path in paths:
        end = data.index(b'\n', i)
        header = data[i:end].split()
        i = end + 1
        if len(header) < 3 or header[1] != b'blob':
            continue
        size = int(header[2])
        blob, i = data[i:i + size], i + size + 1
        if b'\0' in blob:
            continue
        try:
            out[path] = blob.decode('utf-8')
        except UnicodeDecodeError:
            continue
    return out


def attributes(rev, paths):
    if not paths:
        return set()
    run = subprocess.run(['git', 'check-attr', f'--source={rev}', '-z', '--stdin', 'linguist-generated', 'linguist-vendored'],
                         input='\0'.join(paths).encode() + b'\0', capture_output=True)
    fields = run.stdout.decode(errors='replace').split('\0')
    return {fields[k] for k in range(0, len(fields) - 2, 3) if fields[k + 2] not in ('unspecified', 'unset', 'false')}


def files_at(rev, pathspecs, extra):
    listing = git('ls-tree', '-r', '-z', '--full-tree', rev, '--', *pathspecs)
    paths = []
    for entry in listing.split('\0'):
        if not entry:
            continue
        meta, path = entry.split('\t', 1)
        mode, kind = meta.split()[:2]
        if kind == 'blob' and mode in ('100644', '100755'):
            paths.append(path)
    texts = read_blobs(rev, paths)
    marked = attributes(rev, list(texts))
    for path, text in texts.items():
        lang = language(path, text)
        if lang and not excluded(path, text, marked, extra):
            yield path, lang, text


def tally(rev, pathspecs, docs, extra, by_file):
    sha = git('rev-parse', '--verify', f'{rev}^{{commit}}').strip()
    out = {'rev': sha, 'files': 0, 'comment_lines': 0, 'disallowed_lines': 0, 'languages': {}}
    per = {}
    for path, lang, text in files_at(sha, pathspecs, extra):
        judged = Judged(text, lang, matches(path, docs))
        out['files'] += 1
        out['comment_lines'] += len(judged.lines)
        out['disallowed_lines'] += len(judged.bad_lines)
        entry = out['languages'].setdefault(lang, {'files': 0, 'comment_lines': 0})
        entry['files'] += 1
        entry['comment_lines'] += len(judged.lines)
        if judged.lines:
            per[path] = len(judged.lines)
    out['languages'] = dict(sorted(out['languages'].items()))
    if by_file:
        out['by_file'] = dict(sorted(per.items()))
    return out


HUNK = re.compile(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@')


def added_lines(base, head):
    diff = git('-c', 'core.quotePath=false', 'diff', '--no-color', '--no-ext-diff', '-U0', '-M', '--diff-filter=d',
               f'{base}...{head}')
    added, path = {}, None
    for line in diff.split('\n'):
        if line.startswith('+++ '):
            path = line[6:].rstrip('\t') if line.startswith('+++ b/') else None
        elif path and line.startswith('@@'):
            m = HUNK.match(line)
            start, count = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
            added.setdefault(path, set()).update(range(start, start + count))
    return added


def diff_mode(args):
    head = git('rev-parse', '--verify', f'{args.head}^{{commit}}').strip()
    added = added_lines(args.base, head)
    texts = read_blobs(head, sorted(added))
    marked = attributes(head, list(texts))
    found = []
    for path, text in sorted(texts.items()):
        lang = language(path, text)
        if not lang or excluded(path, text, marked, args.exclude):
            continue
        judged = Judged(text, lang, matches(path, args.docs))
        for lines, reason in judged.failures:
            hit = lines & added[path]
            if hit:
                found.append((path, min(hit), reason))
    for path, line, reason in sorted(found):
        print(f'{path}:{line}: {reason}: {MESSAGES[reason]}')
    print(f'comment-check: {len(found)} disallowed comment(s) in added lines' if found else 'comment-check: ok', file=sys.stderr)
    return 1 if found else 0


def count_mode(args):
    report = {'schema': SCHEMA, 'paths': args.paths, 'docs': args.docs, 'exclude': args.exclude,
              'before': tally(args.before, args.paths, args.docs, args.exclude, args.by_file) if args.before else None,
              'after': tally(args.at, args.paths, args.docs, args.exclude, args.by_file)}
    print(json.dumps(report, indent=2))
    return 0


def main(argv):
    parser = argparse.ArgumentParser(prog='check.py', description='The comments contract, openwiz.comments.v1.')
    sub = parser.add_subparsers(dest='mode', required=True)
    for name in ('diff', 'count'):
        p = sub.add_parser(name)
        p.add_argument('--docs', action='append', default=[], metavar='PATH')
        p.add_argument('--exclude', action='append', default=[], metavar='GLOB')
    d = sub.choices['diff']
    d.add_argument('--base', required=True, metavar='REV')
    d.add_argument('--head', default='HEAD', metavar='REV')
    c = sub.choices['count']
    c.add_argument('--before', metavar='REV')
    c.add_argument('--at', default='HEAD', metavar='REV')
    c.add_argument('--by-file', action='store_true')
    c.add_argument('paths', nargs='*')
    args = parser.parse_args(argv)
    return diff_mode(args) if args.mode == 'diff' else count_mode(args)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
