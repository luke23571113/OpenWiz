#!/usr/bin/env python3
"""OpenWiz setup: GitHub browser sign-in and the explicit App skip (#633).

  github_login.py status [--repository OWNER/NAME]
      Reads the signed-in GitHub account through gh and, for the selected
      repository, its push access. Reads only.
  github_login.py sign-in [--repository OWNER/NAME] [--yes]
      Reuses a positively read existing login. Signed out: without --yes,
      prints the effects; with --yes, opens GitHub's own browser sign-in
      (gh auth login --web) once, then reads the account back. A browser
      launch or its callback alone is never a login. No personal token is
      pasted, read or stored.
  github_login.py skip-app [--yes --operation ID]
      The owner's explicit choice to skip OpenWiz's App and act through the
      verified personal login on the selected repository. Without --yes:
      records the proposal and prints its effects, operation id and
      fingerprint. With --yes --operation ID: saves exactly that choice.

The choice goes to owner-only setup state (store.py). An App failure,
revocation or unknown identity never selects the personal login; only
skip-app does. Output is JSON with fixed public codes and the public login
only: never a token or a provider body. Python 3.9+, standard library only.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store  # noqa: E402
import setup  # noqa: E402  (the same account and repository read-back)

SCHEMA = 'openwiz.github-login.v1'
SIGN_IN_TIMEOUT = 15 * 60  # the owner's browser approval, then gh's own exchange
# GitHub's own browser flow through the GitHub CLI, for github.com over HTTPS.
SIGN_IN = ('auth', 'login', '--hostname', 'github.com', '--web', '--git-protocol', 'https', '--skip-ssh-key')
# gh prefers these over its saved login; a sign-in must never stand on one.
TOKEN_VARIABLES = ('GH_TOKEN', 'GITHUB_TOKEN', 'GH_ENTERPRISE_TOKEN', 'GITHUB_ENTERPRISE_TOKEN')


def selected_repository(saved, explicit):
    if explicit is not None:
        store.require(store.REPOSITORY.fullmatch(explicit) and explicit.split('/')[1] not in ('.', '..'),
                      'invalid repository')
        return explicit
    project = saved.read()['project']
    return project['repository'] if project else None


def result(code, login, repository=None, **extra):
    value = {'schema': SCHEMA, 'code': code, 'login': login, **extra}
    if repository is not None:
        value['repository'] = setup.read_back(repository)[0]
    return value


def sign_in(args):
    saved = store.Store(args.state_dir)
    repository = selected_repository(saved, args.repository)
    program = shutil.which('gh')
    if program is None:
        return result('login_gh_missing', None)
    if any(os.environ.get(name) for name in TOKEN_VARIABLES):
        return result('login_token_environment', None)
    failure, login = setup.account()
    if failure is None:
        return result('login_reused', login, repository)
    if failure != 'identity_signed_out':
        return result(failure, None)  # unknown or refused: never a blind browser sign-in
    if not args.yes:
        return result('login_needed', None, effects=[
            "Open GitHub's own browser sign-in through the GitHub CLI (gh auth login --web).",
            'Approve it in your browser with the one-time code gh shows. You paste no token.',
            'gh saves its own login for github.com on this host. OpenWiz stores no token.',
            'Run sign-in again with --yes to start.'])
    with saved.locked():
        lock = os.open(saved.dir / '.github-login.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return result('login_in_progress', None)
        # A sign-in that finished while this one waited, or before a restart, is reused.
        failure, login = setup.account()
        if failure is None:
            return result('login_reused', login, repository)
        try:
            # gh shows its one-time code and browser prompt to the owner directly.
            finished = subprocess.run([program, *SIGN_IN], stdin=sys.stdin, stdout=sys.stderr,
                                      stderr=sys.stderr, timeout=SIGN_IN_TIMEOUT).returncode
        except (OSError, subprocess.TimeoutExpired):
            finished = None
        failure, login = setup.account()
        if failure is None:
            return result('login_verified', login, repository)
        return result('login_unconfirmed' if finished == 0 else 'login_cancelled', None)
    finally:
        os.close(lock)


def skip_app(args):
    saved = store.Store(args.state_dir)
    project = saved.read()['project']
    store.require(project is not None, 'no repository is selected; save project settings first')
    repository = project['repository']
    code, login = setup.read_back(repository)
    store.require(code == 'identity_verified',
                  f'your personal GitHub login is not verified for {repository} ({code}); sign in, then try again')
    identity = {'selected': 'personal_login', 'app_choice': 'skip', 'acting_login': login,
                'repository': repository}
    request = {'repository': repository, 'acting_login': login, 'app_choice': 'skip'}
    effects = [f"Skip OpenWiz's GitHub App for {repository}: no App is registered, installed or marked verified.",
               f"Act on {repository} as your personal GitHub login {login}; the App stays missing (skipped).",
               "Save this choice in this host's owner-only OpenWiz state. Nothing is sent or created."]

    def current(value):
        return value.get('identity') == identity and (value['project'] or {}).get('repository') == repository
    if not args.yes:
        return saved.propose('connect_app', request, effects, 'Proposed: confirm with --yes --operation.', current)
    store.require(args.operation is not None, '--yes needs --operation from the preview')

    def change(value):
        store.require((value['project'] or {}).get('repository') == repository,
                      'the selected repository changed; preview it again')
        operation = saved.authorized(value, args.operation, 'connect_app', request, current)
        if operation['phase'] == 'applied':
            return dict(operation)  # A retry applies nothing twice.
        store.require(operation['phase'] == 'proposed', 'that operation is not awaiting confirmation')
        if value.get('identity') != identity:
            value['identity'] = identity
            value['revision'] += 1  # a new selection: earlier checks no longer count
        operation['phase'] = 'applied'
        operation['reason'] = 'Saved. The App stays missing (skipped); run the setup check to verify your login.'
        return dict(operation)
    return saved.update(change)


def status(args):
    saved = store.Store(args.state_dir)
    repository = selected_repository(saved, args.repository)
    program = shutil.which('gh')
    if program is None:
        return result('identity_signed_out', None)
    failure, login = setup.account()
    return result(failure or 'login_signed_in', login, repository if failure is None else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('status', 'sign-in', 'skip-app'):
        command = commands.add_parser(name)
        command.add_argument('--state-dir', help='absolute OpenWiz state directory (default: the store\'s)')
    for name in ('status', 'sign-in'):
        commands.choices[name].add_argument('--repository', help='OWNER/NAME (default: the selected project\'s)')
    commands.choices['sign-in'].add_argument('--yes', action='store_true')
    commands.choices['skip-app'].add_argument('--yes', action='store_true')
    commands.choices['skip-app'].add_argument('--operation')
    args = parser.parse_args()
    run = {'status': status, 'sign-in': sign_in, 'skip-app': skip_app}[args.command]
    print(json.dumps(run(args), sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except store.Refused as refusal:
        print(f'openwiz-github-login: refused: {refusal}', file=sys.stderr)
        sys.exit(5)
    except (OSError, ValueError):
        print('openwiz-github-login: refused: setup state or the GitHub read could not be completed safely',
              file=sys.stderr)
        sys.exit(5)
