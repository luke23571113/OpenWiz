#!/usr/bin/env python3
"""The kit's key helper (driver v1 N4): the one place a host API key is ever read.

A driver runs `python3 -I kernel/driver-kit/hostkey.py` with one JSON request on stdin: exactly `host`, `method`
(GET, POST or DELETE), `path` and an optional `body` (an object). The helper reads the host's key from the
environment variable registered for it in hosts.json, or else from the system keychain, sends the request only to
the host's registered HTTPS origin with the key in its Authorization header, and prints exactly `status` and `body`.
On a refusal or failure it exits 1 with driver v1's D3 error. Standard library only.

SECURITY: the key is never printed, logged, echoed, cached or put on a command line, and no error text, answer or
child process's arguments or environment carries it. Every error below is a fixed text that names only registry
names, never a value the driver sent or the host answered.
"""
import json
import os
import re
import subprocess
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(HERE, 'hosts.json')
OVERRIDE = 'OPENWIZ_HOSTKEY_TEST_ORIGIN'
METHODS = ('GET', 'POST', 'DELETE')
FIELDS = ('origin', 'variable', 'keychain', 'header')
NAME = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')
ENTRY = {'origin': re.compile(r'https://[a-z0-9]+(?:-[a-z0-9]+)*(?:\.[a-z0-9]+(?:-[a-z0-9]+)*)+'),
         'variable': re.compile(r'[A-Z][A-Z0-9_]{0,63}'),
         'keychain': re.compile(r'[a-z0-9]+(?:[.-][a-z0-9]+)*'),
         'header': re.compile(r'authorization-bearer')}
TEST_ORIGIN = re.compile(r'http://127\.0\.0\.1:([1-9][0-9]{0,4})')
PATH = re.compile(r"/[A-Za-z0-9._~!$&'()*+,;=/?%-]*")
KEY = re.compile(r'[\x21-\x7e]{1,4096}')
LIMIT = 1 << 20
SCHEMA = 'send exactly host, method, path and an optional body, as kernel/driver-kit/README.md shows'
_key = []


class Refused(Exception):
    pass


def _unique(pairs):
    if len({k for k, _ in pairs}) != len(pairs):
        raise Refused('a key is repeated in the input', 'send each key once')
    return dict(pairs)


def _no_constant(name):
    raise ValueError(name)


def registry(path=REGISTRY):
    """The registry, read whole and exactly: a host name maps to exactly origin, variable, keychain and header."""
    bad = Refused('kernel/driver-kit/hosts.json is not a valid registry', 'restore it from OpenWiz')
    try:
        with open(path, 'rb') as f:
            hosts = json.loads(f.read().decode('utf-8'), object_pairs_hook=_unique, parse_constant=_no_constant)
    except (OSError, ValueError, Refused):
        raise bad
    if not isinstance(hosts, dict) or not hosts:
        raise bad
    for name, entry in hosts.items():
        if not (len(name) <= 40 and NAME.fullmatch(name)) or not isinstance(entry, dict) or set(entry) != set(FIELDS):
            raise bad
        if not all(isinstance(entry[k], str) and ENTRY[k].fullmatch(entry[k]) for k in FIELDS):
            raise bad
    return hosts


def path_fault(path):
    """Why a request path could leave the registered origin, or None. It fails closed: one fixed character set."""
    if not isinstance(path, str):
        return 'path is not a string'
    if not path.startswith('/'):
        return 'path is not absolute'
    if len(path) > 2048:
        return 'path is longer than 2048 characters'
    decoded = urllib.parse.unquote(path, errors='strict') if '%' in path and _escapes_ok(path) else path
    for text in (path, decoded):
        if any(ord(c) < 0x20 or ord(c) == 0x7f for c in text):
            return 'path has a control character'
        for part, what in (('//', '// (a host)'), ('..', '..'), ('\\', 'a backslash'), ('@', '@ (user info)'),
                           ('#', '#'), (':', 'a scheme or a port')):
            if part in text:
                return 'path has ' + what
    if not PATH.fullmatch(path):
        return 'path has a character outside letters, digits and -._~!$&\'()*+,;=/?%'
    if not _escapes_ok(path):
        return 'path has a percent sign that is not a %XX escape'
    if '%' in decoded:
        return 'path is percent-encoded twice'
    return None


def _escapes_ok(path):
    try:
        urllib.parse.unquote(path, errors='strict')
    except UnicodeDecodeError:
        return False
    return not re.search(r'%(?![0-9A-Fa-f]{2})', path)


def read_request(text, hosts):
    try:
        req = json.loads(text, object_pairs_hook=_unique, parse_constant=_no_constant)
    except ValueError:
        raise Refused('the input is not one JSON object', SCHEMA)
    if not isinstance(req, dict) or not {'host', 'method', 'path'} <= set(req) <= {'host', 'method', 'path', 'body'}:
        raise Refused('the input needs exactly host, method, path and an optional body', SCHEMA)
    if not isinstance(req['host'], str):
        raise Refused('host is not a string', SCHEMA)
    if req['host'] not in hosts:
        raise Refused('host is not in kernel/driver-kit/hosts.json',
                      'use a registered host name; adding a host is a reviewed change to hosts.json')
    if req['method'] not in METHODS or not isinstance(req['method'], str):
        raise Refused('method is not GET, POST or DELETE', SCHEMA)
    why = path_fault(req['path'])
    if why:
        raise Refused(why, 'send only the path below the host, such as /v1/things, never an address')
    if 'body' in req and not isinstance(req['body'], dict):
        raise Refused('body is not an object', SCHEMA)
    return req


def test_origin(environ):
    """The kit's loopback override, honoured only as exactly http://127.0.0.1:<port>; any other value refuses."""
    if OVERRIDE not in environ:
        return None
    m = TEST_ORIGIN.fullmatch(environ[OVERRIDE])
    if not m or int(m.group(1)) > 65535:
        raise Refused('OPENWIZ_HOSTKEY_TEST_ORIGIN is not http://127.0.0.1:<port>, so the helper will not run',
                      'unset it: it is only for the kit\'s tests, which point it at a loopback fake host')
    return environ[OVERRIDE]


def find_key(entry, environ):
    """The key: the registered variable when set and non-empty, else the keychain entry, read from a pipe.

    Under the test override the keychain is never read, so no test and no driver can send a stored key to a fake host.
    """
    variable, keychain = entry['variable'], entry['keychain']
    names = '%s or the keychain entry %s' % (variable, keychain)
    key, where = environ.get(variable, ''), variable
    if not key and OVERRIDE not in environ:
        key, where = _keychain(keychain, {k: v for k, v in environ.items() if k not in (variable, OVERRIDE)}), keychain
    if not key:
        extra = '; under OPENWIZ_HOSTKEY_TEST_ORIGIN only the variable is read' if OVERRIDE in environ else ''
        raise Refused('no key in either %s%s' % (names, extra),
                      'set %s, or add the key to your keychain as %s; OpenWiz never stores it' % (variable, keychain))
    if not KEY.fullmatch(key):
        raise Refused('the key in %s is not one line of printable characters' % where,
                      'store the key alone, with no spaces or line breaks, in %s' % names)
    return key


def _keychain(entry, env):
    if sys.platform == 'darwin':
        argv = ['security', 'find-generic-password', '-s', entry, '-w']
    elif sys.platform.startswith('linux'):
        argv = ['secret-tool', 'lookup', 'service', entry]
    else:
        return ''
    try:
        p = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           env=env, timeout=60)
        out = p.stdout.decode('utf-8')
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
        return ''
    if p.returncode:
        return ''
    return out[:-1] if out.endswith('\n') else out


def send(origin, method, path, body, key):
    """One request, with no redirect followed, no proxy and TLS verified against the system defaults."""
    import http.client
    import ssl
    scheme, _, hostport = origin.partition('://')
    host, _, port = hostport.partition(':')
    headers = {'Authorization': 'Bearer ' + key, 'Accept': 'application/json', 'User-Agent': 'openwiz-hostkey/1'}
    data = None
    if body is not None:
        data = json.dumps(body, allow_nan=False).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    try:
        if scheme == 'https':
            for name in ('SSL_CERT_FILE', 'SSL_CERT_DIR'):
                os.environ.pop(name, None)
            conn = http.client.HTTPSConnection(host, int(port or 443), timeout=60,
                                               context=ssl.create_default_context())
        else:
            conn = http.client.HTTPConnection(host, int(port), timeout=60)
        try:
            conn.request(method, path, body=data, headers=headers)
            answer = conn.getresponse()
            status, raw = answer.status, answer.read(LIMIT + 1)
        finally:
            conn.close()
    except ssl.SSLError:
        raise Refused('TLS verification of the host failed', 'check the host\'s address and your system\'s '
                      'certificates; the helper trusts only the system defaults')
    except (OSError, http.client.HTTPException, ValueError):
        raise Refused('the helper could not reach the host, or its answer was unreadable',
                      'check your network and the host\'s status, then retry')
    if len(raw) > LIMIT:
        raise Refused('the host answered more than 1 MiB', 'ask the host for a smaller answer')
    return status, raw


def _strings(value):
    stack = [value]
    while stack:
        v = stack.pop()
        if isinstance(v, str):
            yield v
        elif isinstance(v, dict):
            stack += list(v) + list(v.values())
        elif isinstance(v, list):
            stack += v


def answer(status, raw, key):
    try:
        body = json.loads(raw.decode('utf-8'), parse_constant=_no_constant) if raw else None
    except ValueError:
        body = None
    if key.encode('utf-8') in raw or any(key in s for s in _strings(body)):
        raise Refused('the host\'s answer held the key, so the helper did not pass it on',
                      'check the host: it should never send a key back')
    return {'status': status, 'body': body}


def run(stdin, environ):
    if not sys.flags.isolated:
        raise Refused('the helper runs only in Python\'s isolated mode', 'run it as python3 -I '
                      'kernel/driver-kit/hostkey.py')
    override = test_origin(environ)
    hosts = registry()
    data = stdin.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise Refused('the input is larger than 1 MiB', SCHEMA)
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        raise Refused('the input is not one JSON object', SCHEMA)
    req = read_request(text, hosts)
    entry = hosts[req['host']]
    origin = override or entry['origin']
    target = urllib.parse.urlsplit(origin + req['path'])
    if (target.scheme, target.netloc) != tuple(urllib.parse.urlsplit(origin)[:2]):
        raise Refused('path would leave the registered address', 'send only the path below the host')
    key = find_key(entry, environ)
    _key.append(key)
    status, raw = send(origin, req['method'], req['path'], req.get('body'), key)
    return answer(status, raw, key)


def main():
    os.dup2(os.open(os.devnull, os.O_WRONLY), 2)
    try:
        out, code = run(sys.stdin.buffer, os.environ), 0
    except Refused as e:
        out, code = {'error': e.args[0], 'next': e.args[1]}, 1
    except BaseException as e:
        out, code = {'error': 'the key helper failed: ' + type(e).__name__, 'next': 'report it to OpenWiz'}, 1
    text = json.dumps(out)
    if any(k in text for k in _key):
        text, code = json.dumps({'error': 'the answer held the key, so the helper did not print it',
                                 'next': 'report it to OpenWiz'}), 1
    sys.stdout.write(text + '\n')
    sys.stdout.flush()
    sys.exit(code)


if __name__ == '__main__':
    main()
