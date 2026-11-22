#!/usr/bin/env bash
set -eu
py="$(command -v python3 || true)"
if [ -z "$py" ] || ! "$py" -I -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
    echo "bootstrap: needs python3 3.9 or later on PATH; install it with your system package manager" \
         "(this bootstrap never runs sudo)" >&2
    exit 2
fi
here="$(cd "$(dirname "$0")" && pwd)"
exec "$py" -I - "$here" "$@" <<'PY'
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

USAGE = '''usage: bootstrap.sh [--dry-run] [--prefix DIR] [--tools FILE]

Installs the free CLIs the waiting live-check hosts need, pinned in tools.json, into --prefix
(default ~/.local; commands go in <prefix>/bin). Every download is checked against its pinned
sha256 before anything is run or installed from it. It never signs in, never installs a paid tool,
never runs sudo, and runs nothing it installed except `<tool> --version`. A second run installs
nothing. --dry-run prints each step and changes nothing.

Exit 0 when every tool is installed, already there or left out by design; 1 when a download,
checksum or install failed; 2 on a usage error or a missing python3 3.9+.'''
NO_SUDO = 'this bootstrap never runs sudo'


class Refused(Exception):
    pass


def usage(message):
    print('bootstrap: %s\n%s' % (message, USAGE), file=sys.stderr)
    sys.exit(2)


def options(here, argv):
    opts = {'dry': False, 'prefix': '~/.local', 'tools': os.path.join(here, 'tools.json')}
    while argv:
        arg = argv.pop(0)
        if arg == '--dry-run':
            opts['dry'] = True
        elif arg in ('--prefix', '--tools') and argv:
            opts[arg[2:]] = argv.pop(0)
        elif arg in ('-h', '--help'):
            print(USAGE)
            sys.exit(0)
        else:
            usage('unknown argument: %s' % arg)
    opts['prefix'] = os.path.abspath(os.path.expanduser(opts['prefix']))
    return opts


def platform_key():
    system, machine = platform.system().lower(), platform.machine().lower()
    if machine in ('amd64', 'x86_64'):
        machine = 'x86_64'
    elif machine in ('arm64', 'aarch64'):
        machine = 'arm64' if system == 'darwin' else 'aarch64'
    return '%s-%s' % (system, machine)


def env():
    return dict(os.environ, DO_NOT_TRACK='1')


def run_version(command):
    try:
        r = subprocess.run([command, '--version'], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           timeout=60, env=env())
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (r.stdout + r.stderr).strip() if r.returncode == 0 else None


def numbers(text):
    match = re.search(r'(\d+)\.(\d+)(?:\.(\d+))?', text or '')
    return match and tuple(int(x or 0) for x in match.groups())


def system_tool(name, minimum):
    path = shutil.which(name)
    have = numbers(run_version(path)) if path else None
    fix = 'install %s %s or later with your system package manager (%s)' % (name, minimum, NO_SUDO)
    if not path:
        return None, 'not on PATH; ' + fix
    if not have:
        return None, '`%s --version` names no version; %s' % (name, fix)
    if have < numbers(minimum):
        return None, '%s %s is older than %s; %s' % (name, '.'.join(map(str, have)), minimum, fix)
    return '.'.join(map(str, have)), None


def fetch(file, work):
    path = os.path.join(work, 'download')
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(file['url'], timeout=120) as src, open(path, 'wb') as dst:
            for block in iter(lambda: src.read(1 << 20), b''):
                digest.update(block)
                dst.write(block)
    except (OSError, ValueError) as e:
        raise Refused('download failed: %s' % (getattr(e, 'reason', None) or type(e).__name__))
    if digest.hexdigest() != file['sha256']:
        os.remove(path)
        raise Refused('checksum mismatch: expected %s, got %s' % (file['sha256'], digest.hexdigest()))
    return path


def place(data, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    part = dst + '.part'
    with open(part, 'wb') as f:
        f.write(data)
    os.chmod(part, 0o755)
    os.replace(part, dst)


def member(path, name):
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            return z.read(name)
    with tarfile.open(path) as t:
        f = t.extractfile(name)
        if f is None:
            raise Refused('%s is not a file in the archive' % name)
        return f.read()


def install(tool, file, prefix, work):
    name, kind = tool['name'], tool['kind']
    dst = os.path.join(prefix, 'bin', name)
    path = fetch(file, work)
    if kind == 'binary':
        place(open(path, 'rb').read(), dst)
    elif kind == 'archive':
        try:
            place(member(path, file['member']), dst)
        except (KeyError, OSError, tarfile.TarError, zipfile.BadZipFile) as e:
            raise Refused('cannot unpack %s: %s' % (file['member'], type(e).__name__))
    elif kind == 'wheel':
        wheel = os.path.join(prefix, 'lib', 'openwiz-vps', '%s-%s.whl' % (name, tool['version']))
        place(open(path, 'rb').read(), wheel)
        code = 'import importlib, sys; sys.path.insert(0, sys.argv.pop(1)); ' \
               'sys.exit(importlib.import_module(%r).main())' % tool['module']
        place(('#!/bin/sh\nexec %s -I -c %s %s "$@"\n' % (shlex.quote(sys.executable), shlex.quote(code),
                                                         shlex.quote(wheel))).encode(), dst)
    elif kind == 'installer':
        # SAFETY: a third-party installer finds a refusing sudo first on its PATH; this bootstrap never runs sudo.
        guard = os.path.join(work, 'guard')
        place(('#!/bin/sh\necho "bootstrap: sudo refused; %s" >&2\nexit 1\n' % NO_SUDO).encode(),
              os.path.join(guard, 'sudo'))
        fill = {'{prefix}': prefix, '{home}': os.path.expanduser('~')}
        args = [re.sub(r'\{prefix\}|\{home\}', lambda m: fill[m.group()], a) for a in tool['args']]
        path_var = os.pathsep.join([guard, os.path.join(prefix, 'bin'), os.environ.get('PATH', '')])
        r = subprocess.run(['bash', path] + args, stdin=subprocess.DEVNULL, stdout=sys.stderr, cwd=work,
                           env=dict(env(), PATH=path_var))
        if r.returncode:
            raise Refused('its installer exited %d' % r.returncode)
        provides = re.sub(r'\{prefix\}|\{home\}', lambda m: fill[m.group()], tool['provides'])
        if not os.path.isfile(provides):
            raise Refused('its installer left no %s' % provides)
        if os.path.abspath(provides) != os.path.abspath(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.lexists(dst):
                os.remove(dst)
            os.symlink(provides, dst)
    else:
        raise Refused('unknown kind %r in tools.json' % kind)
    if tool.get('run_version', True):
        said = run_version(dst)
        if not said or tool['version'] not in said:
            raise Refused('installed, but `%s --version` does not name %s' % (name, tool['version']))


def stamp_path(prefix, name):
    return os.path.join(prefix, 'lib', 'openwiz-vps', name + '.json')


def stamped(tool, file, prefix):
    try:
        with open(stamp_path(prefix, tool['name'])) as f:
            stamp = json.load(f)
    except (OSError, ValueError):
        return False
    return stamp == {'version': tool['version'], 'sha256': file['sha256']} and \
        os.path.exists(os.path.join(prefix, 'bin', tool['name']))


def main():
    opts = options(sys.argv[1], sys.argv[2:])
    prefix, dry, key = opts['prefix'], opts['dry'], platform_key()
    try:
        with open(opts['tools']) as f:
            tools = json.load(f)['tools']
    except (OSError, ValueError, KeyError) as e:
        usage('cannot read %s: %s' % (opts['tools'], type(e).__name__))
    installed, there, left, available, failed = 0, 0, [], set(), False

    def leave(name, why):
        left.append('left out %s: %s' % (name, why))
        print(left[-1], flush=True)

    work = tempfile.mkdtemp(prefix='openwiz-vps-')
    try:
        for tool in tools:
            name = tool['name']
            if tool.get('left_out'):
                leave(name, tool['left_out'])
                continue
            if tool['kind'] == 'system':
                have, why = system_tool(name, tool['min_version'])
                if why:
                    leave(name, why)
                else:
                    there += 1
                    available.add(name)
                    print('already there %s %s' % (name, have), flush=True)
                continue
            file = tool['files'].get(key) or tool['files'].get('any')
            have = None
            if file and stamped(tool, file, prefix):
                have = tool['version']
            elif tool.get('system_min'):
                have = system_tool(name, tool['system_min'])[0]
            if have:
                there += 1
                available.add(name)
                print('already there %s %s' % (name, have), flush=True)
                continue
            if not file:
                leave(name, 'no %s build pinned in tools.json%s' % (key, '; ' + tool['note'] if 'note' in tool else ''))
                continue
            missing = [n for n in tool.get('needs', []) if n not in available]
            if missing:
                leave(name, 'needs ' + ', '.join(missing))
                continue
            if dry:
                print('would install %s %s from %s, sha256 %s' % (name, tool['version'], file['url'], file['sha256']),
                      flush=True)
                installed += 1
                available.add(name)
                continue
            step = tempfile.mkdtemp(dir=work)
            try:
                install(tool, file, prefix, step)
            except Refused as e:
                failed = True
                leave(name, str(e))
                continue
            finally:
                shutil.rmtree(step, ignore_errors=True)
            stamp = stamp_path(prefix, name)
            place(json.dumps({'version': tool['version'], 'sha256': file['sha256']}).encode(), stamp)
            os.chmod(stamp, 0o644)
            installed += 1
            available.add(name)
            print('installed %s %s' % (name, tool['version']), flush=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if dry:
        print('bootstrap: dry run, %d to install, %d already there, %d left out' % (installed, there, len(left)))
    else:
        print('bootstrap: %d installed, %d already there, %d left out' % (installed, there, len(left)))
    for line in left:
        print(line)
    return 1 if failed else 0


sys.exit(main())
PY
