#!/usr/bin/env python3
"""The War room's private web adapter (WRD4, #877): one published page, served as it is.

  python3 -I serve.py fetch --remote URL --into DIR
  python3 -I serve.py serve --root DIR [--port N]

`fetch` reads the private `war-room` branch, read-only, and keeps its `war-room.html`
only if it is the page; a failed fetch leaves the last good page in place. `serve`
answers `/` with that page on 127.0.0.1 and nothing else. Access is the tunnel's and
Access's, never this program's (contract.md).
"""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
BRANCH, PAGE, IDENTITY = 'war-room', 'war-room.html', 'identity.json'
HOST = '127.0.0.1'
MAX_BYTES = 8 * 1024 * 1024
POLICY = re.compile(r'<meta http-equiv="Content-Security-Policy" content="([^"<>]+)">')


class Fail(Exception):
    pass


def git(work, *args):
    out = subprocess.run(['git', '-C', str(work), *args], capture_output=True)
    if out.returncode:
        raise Fail('git %s failed' % args[0])  # never the remote URL or git's stderr
    return out.stdout


def policy(page):
    """The page's own Content-Security-Policy, or Fail: the served page keeps it."""
    found = POLICY.findall(page)
    if len(found) != 1:
        raise Fail('the page has no single security policy')
    return found[0]


def check(data):
    if len(data) > MAX_BYTES:
        raise Fail('the page is too large')
    try:
        page = data.decode('utf-8')
    except UnicodeDecodeError:
        raise Fail('the page is not UTF-8')
    if not page.startswith('<!doctype html>') or '<script' in page.lower():
        raise Fail('the page is not the static page')
    policy(page)


def write(path, data):
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name + '.')
    with os.fdopen(fd, 'wb') as f:
        f.write(data)
    os.replace(tmp, path)


def fetch(remote, into):
    into = Path(into)
    into.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='war-room-web-') as tmp:
        git(tmp, 'init', '-q', '--bare', 'git')
        work = Path(tmp) / 'git'
        git(work, 'fetch', '-q', '--depth=1', '--no-tags', remote, 'refs/heads/%s:refs/web/%s' % (BRANCH, BRANCH))
        ref = 'refs/web/' + BRANCH
        commit = git(work, 'rev-parse', ref).decode().strip()
        entry = git(work, 'ls-tree', ref, '--', PAGE).decode()
        if not entry.startswith('100644 blob '):
            raise Fail('the branch has no plain page')
        data = git(work, 'cat-file', 'blob', entry.split()[2])
    check(data)
    write(into / PAGE, data)
    write(into / IDENTITY, (json.dumps({'commit': commit, 'sha256': hashlib.sha256(data).hexdigest()}) + '\n').encode())
    return commit


class Handler(BaseHTTPRequestHandler):
    server_version, sys_version = 'war-room', ''
    root = None

    def log_message(self, *args):
        pass

    def plain(self, code, text, extra=()):
        body = (text + '\n').encode()
        self.send_response(code)
        for name, value in (('Content-Type', 'text/plain; charset=utf-8'), ('Content-Length', str(len(body))),
                            ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'), *extra):
            self.send_header(name, value)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def page(self):
        if self.path.split('?', 1)[0] != '/':
            return self.plain(404, 'not found')
        try:
            data = (self.root / PAGE).read_bytes()
            check(data)
        except (OSError, Fail):
            return self.plain(503, 'no page yet')
        digest = hashlib.sha256(data).hexdigest()
        self.send_response(200)
        headers = [('Content-Type', 'text/html; charset=utf-8'), ('Content-Length', str(len(data))),
                   ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'),
                   ('Referrer-Policy', 'no-referrer'), ('X-Frame-Options', 'DENY'),
                   ('Content-Security-Policy', policy(data.decode('utf-8')) + "; frame-ancestors 'none'"),
                   ('ETag', '"%s"' % digest)]
        try:
            identity = json.loads((self.root / IDENTITY).read_text(encoding='utf-8'))
            if identity.get('sha256') == digest and re.fullmatch('[0-9a-f]{40}', str(identity.get('commit'))):
                headers.append(('X-War-Room-Commit', identity['commit']))
        except (OSError, ValueError, AttributeError):
            pass
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(data)

    do_GET = do_HEAD = page

    def refuse(self):
        self.plain(405, 'method not allowed', [('Allow', 'GET, HEAD')])

    do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_TRACE = do_CONNECT = refuse


def serve(root, port):
    handler = type('Bound', (Handler,), {'root': Path(root).resolve()})
    with ThreadingHTTPServer((HOST, port), handler) as httpd:
        print('serving on %s:%d' % httpd.server_address[:2], flush=True)
        httpd.serve_forever()


def cli(argv):
    parser = argparse.ArgumentParser(description='The War room private web adapter (WRD4).')
    sub = parser.add_subparsers(dest='cmd', required=True)
    f = sub.add_parser('fetch', help='read the war-room branch and keep its page, read-only')
    f.add_argument('--remote', required=True)
    f.add_argument('--into', required=True, type=Path)
    s = sub.add_parser('serve', help='serve the kept page on 127.0.0.1')
    s.add_argument('--root', required=True, type=Path)
    s.add_argument('--port', type=int, default=7391)
    a = parser.parse_args(argv)
    if a.cmd == 'serve':
        serve(a.root, a.port)
        return 0
    try:
        print('kept war-room.html from %s' % fetch(a.remote, a.into))
    except (Fail, OSError) as e:
        print('war-room web: %s; the last good page stays' % (e if isinstance(e, Fail) else type(e).__name__),
              file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(cli(sys.argv[1:]))
