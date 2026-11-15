#!/usr/bin/env python3
"""The scratch install's App token route for the smoke's App steps (#772).

Mints one installation token of the existing OpenWiz App on the PC, from the
scratch install's own App state (`<state>/service/app`: app.json and
private-key.pem, owner-only), downscoped to the one scratch repository and to
exactly the kit's recorded `release.scope.app_permissions`. A permission the
App is not already registered with (tools/github-app/manifest.json) refuses
before any request, and so does a grant other than the one asked for. The token
then reaches only `smoke.py` on this same kit, through its environment as
OPENWIZ_SMOKE_APP_TOKEN: never argv, a file, the kit or any output. It expires
within the hour; a later resume runs this route again.

    python3 -I app_token.py --kit KIT --state-dir STATE --installation-id N \\
        --repository OWNER/NAME -- python3 -I smoke.py --kit KIT ...
"""
from datetime import datetime, timezone
import importlib.util
import os
from pathlib import Path
import re
import runpy
import sys

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('openwiz_github_app', HERE.parent / 'github-app' / 'app.py')
app = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(app)
prepare = runpy.run_path(str(HERE / 'prepare.py'))
LEVEL = {'read': 1, 'write': 2}


def requested(kit):
    """The kit's App scope as GitHub permissions, within the App's own profile."""
    entries = kit['release']['scope']['app_permissions']
    app.require(type(entries) is list and entries)
    wanted = {}
    for entry in entries:
        match = re.fullmatch('([a-z][a-z_]*):(read|write)', entry) if type(entry) is str else None
        app.require(match is not None and match.group(1) not in wanted)
        name, level = match.groups()
        # No new App permission: only what the App is registered with, never more.
        app.require(name in app.SERVICE and LEVEL[level] <= LEVEL[app.SERVICE[name]])
        wanted[name] = level
    return wanted


def main():
    parser = app.arguments(__doc__)
    parser.add_argument('--kit', required=True, type=Path)
    parser.add_argument('--installation-id', required=True)
    parser.add_argument('--repository', required=True, help='OWNER/NAME: the scratch repository')
    parser.add_argument('command', nargs='+', help='-- python3 -I smoke.py --kit KIT ...')
    args = parser.parse_args()
    command = args.command
    # The token goes to this folder's runner on this same kit, nothing else.
    app.require(len(command) >= 5 and Path(command[0]).is_absolute() and command[1] == '-I'
                and Path(command[2]) == HERE / 'smoke.py' and command[3:5] == ['--kit', str(args.kit)])
    kit = prepare['read_private'](args.kit, 'kit_not_owner_only')
    permissions = requested(kit)
    repository = app.repository(args.repository).lower()
    app.api_base(args.api_base)
    app.manifest()
    installation = app.positive_id(args.installation_id)
    directory = app.app_directory(app.state_path(args.state_dir))
    try:
        config = app.parse_json(app.read_file(directory, 'app.json', 1024))
        app.require(set(config) == {'app_id'})
        jwt = app.jwt(directory, config['app_id'])
        result = app.post(args.api_base, f'/app/installations/{installation}/access_tokens',
                          {'permissions': permissions, 'repositories': [repository.split('/')[1]]}, jwt)
    finally:
        os.close(directory)
    # Exactly the grant asked for: nothing wider, nothing foreign.
    app.require(result.get('permissions') == permissions)
    listed = result.get('repositories')
    app.require(result.get('repository_selection') == 'selected' and type(listed) is list
                and [r.get('full_name', '').lower() if type(r) is dict else None for r in listed] == [repository])
    token = result.get('token')
    app.require(type(token) is str and re.fullmatch(r'[A-Za-z0-9._~+/-]+=*', token) is not None)
    expiry = datetime.fromisoformat(result['expires_at'].replace('Z', '+00:00'))
    app.require(0 < (expiry - datetime.now(timezone.utc)).total_seconds() <= 3600 + 300)
    os.execve(command[0], command, dict(os.environ, OPENWIZ_SMOKE_APP_TOKEN=token))


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # Never echo a response, path, JWT or exception: it may carry a secret.
        print('App token refused: check the kit scope, the scratch App state and its installation.',
              file=sys.stderr)
        sys.exit(2)
