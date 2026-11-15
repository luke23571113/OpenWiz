#!/usr/bin/env python3
"""Pre-push adapter: guard network destinations except the private repository."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import check


def private_or_local(url):
    # Local fixture/removable-disk remotes cannot publish to a network service.
    if url.startswith(('/', './', '../', 'file://')):
        return True
    if '://' in url:
        value = urlsplit(url)
        host, path = value.hostname, value.path
    else:
        match = re.fullmatch(r'(?:[^/@:]+@)?([^/:]+):(.+)', url)
        if not match:
            # Plain paths without a colon are also Git's local transport.
            return bool(url) and ':' not in url
        host, path = match.groups()
    path = path.strip('/').removesuffix('.git').lower()
    return host and host.lower() == 'github.com' and path == 'jparker2006/closedwiz'


# The only push URLs whose main may narrow a new ref's scan (#727).
PUBLIC_URLS = (
    'https://github.com/openwizdev/OpenWiz',
    'https://github.com/openwizdev/OpenWiz.git',
    'git@github.com:openwizdev/OpenWiz',
    'git@github.com:openwizdev/OpenWiz.git',
)
# GIT_* variables Git itself sets for a hook, none of which picks a
# repository or a transport. Any other one (GIT_DIR, GIT_SSH, GIT_SSH_COMMAND,
# GIT_CONFIG_PARAMETERS from git -c, GIT_CONFIG_COUNT/KEY/VALUE, ...) could
# make the lookup below reach a different repository than the push.
HOOK_GIT_VARIABLES = ('GIT_EXEC_PATH', 'GIT_PREFIX', 'GIT_EDITOR')


def destination_main(repo, url):
    """The commit the push destination itself names as its main, or None.

    A new ref's scan may skip only history already published where the push
    goes. A local tracking ref proves nothing (a separate push URL, or a URL
    retargeted without a fetch), so ask the exact push URL, and only when all
    of these hold: the URL is on PUBLIC_URLS; the push carries no
    command-scoped Git setting or override variable, so the lookup runs with
    the push's own configuration; Git would not rewrite the URL (insteadOf);
    and the destination names exactly one main. Anything else, or any
    failure, returns None: scan from the anchor. That commit must also exist
    locally, or check.py scans from the anchor too.
    """
    if url not in PUBLIC_URLS:
        return None
    if any(k.startswith('GIT_') and k not in HOOK_GIT_VARIABLES for k in os.environ):
        return None
    env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0'}
    def run(*args):
        result = subprocess.run(['git', '-C', str(repo), 'ls-remote', *args], env=env, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=60)
        return result.stdout if result.returncode == 0 else None
    try:
        if run('--get-url', url) != url + '\n':
            return None
        listed = run('--refs', url, 'refs/heads/main')
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return None
    mains = [line.split('\t')[0] for line in (listed or '').splitlines() if line.endswith('\trefs/heads/main')]
    if len(mains) != 1 or not re.fullmatch(r'[0-9a-f]{40}', mains[0]):
        return None
    return mains[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--head', required=True)
    parser.add_argument('--base', required=True)
    parser.add_argument('--literals', type=Path, default=os.environ.get('OPENWIZ_PRIVACY_LITERALS'))
    args = parser.parse_args(argv)
    if private_or_local(args.url):
        return 0
    command = ['--repo', str(args.repo), '--git-tree', args.head, '--head', args.head]
    if args.base.strip('0'):
        command += ['--base', args.base]
    else:
        main = destination_main(args.repo, args.url)
        if main:
            command += ['--upstream', main]
    if args.literals is not None:
        command += ['--literals', str(args.literals), '--require-literals']
    return check.main(command)


if __name__ == '__main__':
    sys.exit(main())
