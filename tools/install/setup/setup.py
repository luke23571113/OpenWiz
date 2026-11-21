#!/usr/bin/env python3
import argparse
import base64
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store

DESCRIPTION = "OpenWiz setup: prepare one project and check each connection independently (#1105).\n\n  setup.py prepare --repository OWNER/NAME --project PRJ --operator NAME \\\n      --service-issue N --answer-thread THR --harness H --model M --effort E\n      Without --yes: records the proposed settings and prints their effects,\n      operation id and fingerprint; nothing else is saved. With\n      --yes --operation ID: saves exactly that preview's settings.\n  setup.py check\n      Reads CloudRoom through the installed openwiz CLI, the agents' own\n      GitHub login through gh, and OpenWiz's App through GitHub's App API, and\n      records one result code per component. Reads only: the App's\n      installation token is minted to prove access, then discarded.\n\nResults go to owner-only `<state>/setup/state.json` (store.py), which the\nsetup page reads. Output is JSON with fixed public codes: never a token, key,\nprovider body or URL with credentials. No personal-token fallback for the App.\nPython 3.9+, standard library and /usr/bin/openssl only.\n"

HERE = Path(__file__).resolve().parent
PROFILE = {'metadata': 'read', 'contents': 'write', 'issues': 'write',
           'pull_requests': 'write', 'checks': 'read', 'actions': 'read'}
WRITES = ('contents', 'issues', 'pull_requests')
SKILLS = ('setup', 'grill', 'to-tickets', 'launch-fleet')
API = 'https://api.github.com'
TIMEOUT = 30


def run(argv, limit=4 * 1024 * 1024, env=None):
    try:
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=TIMEOUT, env=env)
    except (OSError, subprocess.TimeoutExpired):
        return None, None
    if len(result.stdout) > limit:
        return result.returncode, None
    try:
        return result.returncode, json.loads(result.stdout, object_pairs_hook=store.unique)
    except ValueError:
        return result.returncode, None


def check_cloudroom(openwiz, state=None):
    tool = HERE.parent / 'cloudroom/cloudroom.py'
    if state is not None and tool.is_file():
        spec = importlib.util.spec_from_file_location('openwiz_cloudroom', tool)
        cloudroom = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cloudroom)
        return cloudroom.status(cloudroom.Host(), state)['code']
    if openwiz is None:
        return 'cloudroom_missing'
    code, value = run([str(openwiz), 'ls', '--json', '--limit', '1'])
    if code != 0 or type(value) is not dict or value.get('schema') != 'openwiz.inventory.v1':
        return 'cloudroom_unreadable'
    if (value.get('coverage') or {}).get('state') != 'complete' or value.get('gaps') != []:
        return 'cloudroom_partial'
    return 'cloudroom_reachable'


def check_harness(openwiz, project):
    if project is None:
        return 'harness_unselected'
    if openwiz is None:
        return 'harness_unreadable'
    code, value = run([str(openwiz), 'models', '--json'])
    if code not in (0, 13) or type(value) is not dict or value.get('schema') != 'openwiz.cloud-options.v1':
        return 'harness_unreadable'
    if value.get('state', {}).get('kind') != 'offered':
        return 'harness_unreadable'
    for harness in value.get('harnesses', []):
        if type(harness) is dict and harness.get('harness') == project['harness']:
            for model in harness.get('models', []):
                if (type(model) is dict and model.get('model') == project['model']
                        and project['effort'] in model.get('efforts', [])):
                    return 'harness_listed'
    return 'harness_unavailable'


def gh(path):
    program = shutil.which('gh')
    if program is None:
        return None, None
    return run([program, 'api', path])


def github_com(path):
    return github_com_read(path)[:2]


UNAUTHENTICATED = re.compile(rb'gh: [^\n]* \(HTTP 401\)\n?')


def github_com_read(path):
    program = shutil.which('gh')
    if program is None:
        return None, None, False
    try:
        result = subprocess.run([program, 'api', path], stdin=subprocess.DEVNULL, capture_output=True,
                                timeout=TIMEOUT, env={**os.environ, 'GH_HOST': 'github.com'})
    except (OSError, subprocess.TimeoutExpired):
        return None, None, False
    try:
        value = json.loads(result.stdout, object_pairs_hook=store.unique) if len(result.stdout) <= 4 * 1024 * 1024 else None
    except (ValueError, store.Refused):
        value = None
    return result.returncode, value, result.returncode == 1 and UNAUTHENTICATED.fullmatch(result.stderr) is not None


def account():
    code, user, unauthenticated = github_com_read('user')
    if code is None or code == 4 or unauthenticated:
        return 'identity_signed_out', None
    if code != 0 or type(user) is not dict:
        return 'identity_unreadable', None
    login = user.get('login')
    if user.get('type') != 'User' or not isinstance(login, str) or login.endswith('[bot]'):
        return 'identity_bot', None
    if store.LOGIN.fullmatch(login) is None:
        return 'identity_unreadable', None
    return None, login


def read_back(repository):
    failure, login = account()
    if failure is not None:
        return failure, None
    code, repo = github_com(f'repos/{repository}')
    if code != 0 or type(repo) is not dict:
        return ('identity_no_push' if code == 1 else 'identity_unreadable'), login
    permissions = repo.get('permissions')
    if type(permissions) is dict and permissions.get('push') is True:
        return 'identity_verified', login
    return 'identity_no_push', login


def check_identity(project, identity=None):
    if project is None:
        return 'identity_unselected'
    code, login = read_back(project['repository'])
    saved = identity or {}
    chosen = saved.get('acting_login') if saved.get('repository') == project['repository'] else None
    if code == 'identity_verified' and chosen is not None and login.lower() != chosen.lower():
        return 'identity_account_mismatch'
    return code


def runtime_pin(runtime):
    if runtime is None:
        return None
    try:
        identity = (Path(runtime) / 'openwiz-build.txt').read_text()
    except OSError:
        return None
    parts = identity.split('\n')
    if (len(parts) != 5 or parts[0] != 'openwiz.package.v1' or parts[4] != ''
            or not re.fullmatch(r'0\.[0-9]{1,10}\.[0-9]{1,10}', parts[1]) or not re.fullmatch('[0-9a-f]{40}', parts[2])):
        return None
    if not all((Path(runtime) / 'skills' / name / 'SKILL.md').is_file() for name in SKILLS):
        return None
    return f'{parts[1]} {parts[2]}'


def sections(text):
    found, name = {}, None
    for line in text.split('\n'):
        if line.startswith('## '):
            name = line[3:].strip()
            found.setdefault(name, [])
        elif name is not None:
            found[name].append(line)
    return found


def table(lines):
    rows = [line.strip() for line in lines if line.strip().startswith('|')]
    if len(rows) < 2 or not re.fullmatch(r'\|(\s*:?-{3,}:?\s*\|)+', rows[1]):
        return []
    split = lambda row: [cell.strip() for cell in row.strip('|').split('|')]
    header = split(rows[0])
    return [dict(zip(header, split(row))) for row in rows[2:] if len(split(row)) == len(header)]


PLACEHOLDER = re.compile(r'<[A-Za-z][^<>\n]*>')
MODELS_HEADER = ['Role', 'Harness', 'Model', 'Effort', '`room-cli thread spawn` flags']
MODEL_ID = r'[A-Za-z0-9._-]+'
MODEL_FLAGS = re.compile(r'`--provider %s --model %s(?:/%s)* --reasoning-level %s`' % ((MODEL_ID,) * 4))


def models_usable(text, body):
    if sum(line.startswith('## ') and line[3:].strip() == 'Models' for line in text.split('\n')) != 1:
        return False
    rows = []
    for line in body:
        if line.startswith('|'):
            rows.append([cell.strip() for cell in line.strip()[1:-1].split('|')] if line.strip().endswith('|') else None)
        elif rows:
            break
    if len(rows) < 2 or rows[0] != MODELS_HEADER or rows[1] != ['---'] * 5 or None in rows:
        return False
    names = [row[0] if len(row) == 5 else None for row in rows[2:]]
    if names[:3] != ['Orchestrator', 'Builder', 'Reviewer'] or names[3:] not in (
            [], ['Small builder'], ['Fixer'], ['Small builder', 'Fixer']):
        return False
    for role, harness, model, effort, flags in rows[2:]:
        if harness == 'follows Builder':
            if role not in ('Small builder', 'Fixer') or model or effort or flags:
                return False
            continue
        if not (harness and model and effort) or not MODEL_FLAGS.fullmatch(flags):
            return False
    return True


def fleet_settings_usable(text):
    found = sections(text)
    reviewers = [name for name in found if name.startswith('Reviewer')]
    builders = [name for name in found if name.startswith('Builder')]
    needed = ['Test commands', 'CI checks', 'Standing merge rules']
    if 'Models' in found:
        if not models_usable(text, found['Models']):
            return False
        needed.insert(0, 'Models')
        builders = reviewers = []
    elif not reviewers:
        return False
    else:
        needed.insert(0, 'Builder')
    if not all(name in found for name in needed):
        return False
    for name in needed + builders + reviewers:
        body = found[name]
        if any(PLACEHOLDER.search(line) for line in body):
            return False
        if not any(line.startswith('Source: ') and len(line) > len('Source: ') for line in body):
            return False
    for name in builders + reviewers:
        values = {row.get('Setting'): row.get('Value', '') for row in table(found[name])}
        if not all(values.get(key) for key in ('Harness', 'Model', 'Effort')):
            return False
    if not any(row.get('Command', '').strip('`') for row in table(found['Test commands'])):
        return False
    if not any(row.get('Check', '').strip('`') for row in table(found['CI checks'])):
        return False
    merge = found['Standing merge rules']
    rows = [row for row in table(merge) if all(cell.strip() for cell in row.values())]
    waits = any(line.strip() == 'None yet: every merge waits for the user.' for line in merge)
    return bool(rows) or waits


def check_brain(brain, repository):
    if brain is None or brain['code_repository'].lower() != repository.lower():
        return 'project_verified'
    home = brain['brain_repository']
    code, repo = gh(f'repos/{home}')
    if code is None:
        return 'project_unreadable'
    if code != 0 or type(repo) is not dict or not str(repo.get('full_name', '')).lower() == home.lower() \
            or repo.get('private') is not True or repo.get('visibility') != 'private':
        return 'project_settings_missing' if code in (0, 1) else 'project_unreadable'
    code, record = gh(f"repos/{home}/contents/{brain['folder']}/settings.json")
    if code != 0 or type(record) is not dict or record.get('encoding') != 'base64':
        return 'project_settings_missing' if code in (0, 1) else 'project_unreadable'
    try:
        settings = json.loads(base64.b64decode(record.get('content', ''), validate=False),
                              object_pairs_hook=store.unique)
    except ValueError:
        return 'project_settings_missing'
    if (type(settings) is not dict or settings.get('brain_location') != brain['location']
            or str(settings.get('code_repository', '')).lower() != brain['code_repository'].lower()
            or str(settings.get('brain_repository', '')).lower() != home.lower()):
        return 'project_settings_missing'
    return 'project_verified'


def check_project(openwiz, project, runtime, brain=None):
    if project is None:
        return 'project_unprepared'
    if project['runtime'] is None or runtime_pin(runtime) != project['runtime']:
        return 'project_runtime_missing'
    code, issue = gh(f"repos/{project['repository']}/issues/{project['service_issue']}")
    if code is None:
        return 'project_unreadable'
    if (code != 0 or type(issue) is not dict or issue.get('state') != 'open'
            or issue.get('number') != project['service_issue'] or 'pull_request' in issue):
        return 'project_issue_refused' if code in (0, 1) else 'project_unreadable'
    code, settings = gh(f"repos/{project['repository']}/contents/docs/agents/fleet.md")
    if code != 0 or type(settings) is not dict or settings.get('encoding') != 'base64':
        return 'project_settings_missing' if code in (0, 1) else 'project_unreadable'
    try:
        text = base64.b64decode(settings.get('content', ''), validate=False).decode()
    except ValueError:
        return 'project_settings_missing'
    if not fleet_settings_usable(text):
        return 'project_settings_missing'
    if openwiz is None:
        return 'project_unreadable'
    code, thread = run([str(openwiz), 'show', project['answer_thread'], '--json'])
    if code == 3:
        return 'project_answer_refused'
    if code != 0 or type(thread) is not dict:
        return 'project_unreadable'
    group = (thread.get('data') or {}).get('session', {}).get('group', {})
    if group.get('kind') != 'project' or group.get('id') != project['project']:
        return 'project_answer_refused'
    return check_brain(brain, project['repository'])


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def api_base(value):
    if value != API:
        parts = urllib.parse.urlsplit(value)
        store.require(parts.scheme == 'http' and parts.hostname == '127.0.0.1' and parts.port is not None
                      and parts.netloc == f'127.0.0.1:{parts.port}' and not parts.path
                      and not parts.query and not parts.fragment,
                      'only the GitHub API, or loopback HTTP for synthetic tests, is accepted')
    return value


def request(base, method, path, jwt, body=None):
    return linked_request(base, method, path, jwt, body)[:2]


def linked_request(base, method, path, jwt, body=None):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'OpenWiz-setup',
               'X-GitHub-Api-Version': '2022-11-28', 'Authorization': 'Bearer ' + jwt}
    data = None
    if body is not None:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(body).encode()
    call = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.build_opener(NoRedirect()).open(call, timeout=TIMEOUT) as response:
            status, raw = response.status, response.read(1024 * 1024 + 1)
            link = response.headers.get('Link')
    except urllib.error.HTTPError as error:
        return error.code, None, None
    except (OSError, ValueError):
        return None, None, None
    try:
        return status, json.loads(raw, object_pairs_hook=store.unique) if len(raw) <= 1024 * 1024 else None, link
    except ValueError:
        return status, None, link


NEXT = re.compile(r'<([^<>]*)>\s*;\s*rel="next"')
PAGES = 100


def read_installations(base, jwt):
    found, path = [], '/app/installations'
    origin = urllib.parse.urlsplit(base)[:2]
    for _ in range(PAGES):
        status, page, link = linked_request(base, 'GET', path, jwt)
        if status != 200 or type(page) is not list:
            return status, None
        found.extend(page)
        following = NEXT.search(link or '')
        if following is None:
            if re.search(r'\bnext\b', re.sub(r'<[^<>]*>', '', link or ''), re.IGNORECASE):
                return None, None
            return status, found
        parts = urllib.parse.urlsplit(following.group(1))
        if parts[:3] != (*origin, '/app/installations') or parts.fragment:
            return None, None
        path = f'{parts.path}?{parts.query}'
    return None, None


def private_file(directory, name, limit):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    info = os.fstat(fd)
    if not (stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_mode & 0o077 == 0
            and info.st_nlink == 1 and 0 < info.st_size <= limit):
        os.close(fd)
        raise store.Refused('unsafe App file')
    return fd


def app_directory(state):
    fd = None
    try:
        fd = os.open(state, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        for part in ('service', 'app'):
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
            info = os.fstat(fd)
            store.require(info.st_uid == os.getuid() and info.st_mode & 0o077 == 0, 'unsafe App directory')
        return fd
    except FileNotFoundError:
        if fd is not None:
            os.close(fd)
        return None


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=')


def sign_jwt(directory, app_id):
    fd = private_file(directory, 'private-key.pem', 16384)
    try:
        now = int(time.time())
        message = b64(b'{"alg":"RS256","typ":"JWT"}') + b'.' + b64(json.dumps(
            {'iat': now - 60, 'exp': now + 540, 'iss': str(app_id)}, separators=(',', ':')).encode())
        result = subprocess.run(['/usr/bin/openssl' if Path('/usr/bin/openssl').exists() else 'openssl',
                                 'dgst', '-sha256', '-sign', f'/dev/fd/{fd}'], input=message,
                                capture_output=True, timeout=10, pass_fds=(fd,))
        store.require(result.returncode == 0, 'App signing failed')
        return (message + b'.' + b64(result.stdout)).decode('ascii')
    finally:
        os.close(fd)


def check_app(state_path, project, recorded, base):
    try:
        directory = app_directory(state_path)
    except (store.Refused, OSError):
        return 'app_files_unusable', None
    if directory is None:
        return 'app_missing', None
    try:
        try:
            fd = private_file(directory, 'app.json', 1024)
        except FileNotFoundError:
            return 'app_missing', None
        with os.fdopen(fd, 'rb') as handle:
            config = json.loads(handle.read(1025), object_pairs_hook=store.unique)
        store.require(type(config) is dict and set(config) == {'app_id'} and store.positive(config['app_id']),
                      'invalid app.json')
        app_id = config['app_id']
        if project is None:
            return 'app_not_installed', {'app_id': app_id, 'installation_id': None}
        jwt = sign_jwt(directory, app_id)
    except (store.Refused, OSError, ValueError, subprocess.SubprocessError):
        return 'app_files_unusable', None
    finally:
        os.close(directory)
    status, installations = read_installations(base, jwt)
    if status == 401:
        return 'app_key_rejected', None
    if status != 200 or type(installations) is not list:
        return 'app_unreadable', None
    owner, name = project['repository'].split('/')
    mine = [i for i in installations if type(i) is dict and i.get('app_id') == app_id
            and isinstance((i.get('account') or {}).get('login'), str)
            and i['account']['login'].lower() == owner.lower()]
    if len(mine) == 1:
        status, found = request(base, 'GET', '/app', jwt)
        if status == 401:
            return 'app_key_rejected', None
        if status != 200 or type(found) is not dict or found.get('id') != app_id:
            return 'app_unreadable', None
        app_owner = (found.get('owner') or {}).get('login')
        if not isinstance(app_owner, str) or app_owner.lower() != owner.lower():
            mine = []
    if len(mine) != 1 or not store.positive(mine[0].get('id')):
        had = recorded is not None and recorded.get('installation_id') is not None
        return ('app_revoked' if had else 'app_not_installed'), {'app_id': app_id, 'installation_id': None}
    installation = mine[0]
    ids = {'app_id': app_id, 'installation_id': installation['id']}
    if installation.get('suspended_at') is not None:
        return 'app_suspended', ids
    if installation.get('repository_selection') != 'selected':
        return 'app_all_repositories', ids
    granted = installation.get('permissions')
    if granted != PROFILE:
        if type(granted) is dict and any(granted.get(k) != 'write' for k in WRITES):
            return 'app_read_only', ids
        return 'app_permissions_mismatch', ids
    status, token = request(base, 'POST', f"/app/installations/{installation['id']}/access_tokens", jwt,
                            {'repositories': [name], 'permissions': PROFILE})
    if status == 404:
        return 'app_revoked', {'app_id': app_id, 'installation_id': None}
    if status == 401:
        return 'app_key_rejected', ids
    if status == 422:
        return 'app_wrong_repository', ids
    if status != 201 or type(token) is not dict:
        return 'app_unreadable', ids
    repositories = token.get('repositories')
    if token.get('permissions') != PROFILE:
        return 'app_read_only', ids
    if (type(repositories) is not list or len(repositories) != 1 or type(repositories[0]) is not dict
            or str(repositories[0].get('full_name', '')).lower() != project['repository'].lower()):
        return 'app_wrong_repository', ids
    if not usable_token(token, time.time()):
        return 'app_token_unusable', ids
    del token
    return 'app_verified', ids


TOKEN = re.compile(r'[A-Za-z0-9._~+/-]{1,16384}=*')


def usable_token(answer, now):
    token, expiry = answer.get('token'), answer.get('expires_at')
    if not isinstance(token, str) or TOKEN.fullmatch(token) is None or len(token) > 16384:
        return False
    if not isinstance(expiry, str) or re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z', expiry) is None:
        return False
    try:
        at = datetime.strptime(expiry, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return False
    return 0 < at - now <= 3600 + 300


def default_openwiz(explicit):
    if explicit is not None:
        return Path(explicit) if Path(explicit).is_file() else None
    packaged = HERE.parent.parent / 'openwiz'
    return packaged if packaged.is_file() else None


def default_runtime(explicit):
    if explicit is not None:
        return Path(explicit)
    return HERE.parent if (HERE.parent / 'openwiz-build.txt').is_file() else None


def check(args):
    setup = store.Store(args.state_dir)
    base = api_base(args.api_base)
    generation = setup.start_check()
    before = setup.read()
    project, revision = before['project'], before['revision']
    openwiz = default_openwiz(args.openwiz)

    def guarded(check_one, failed):
        try:
            return check_one()
        except Exception:
            return failed
    results = {'cloudroom': guarded(lambda: check_cloudroom(openwiz, setup.state), 'cloudroom_unreadable'),
               'harness': guarded(lambda: check_harness(openwiz, project), 'harness_unreadable'),
               'personal_github': guarded(lambda: check_identity(project, before.get('identity')),
                                          'identity_unreadable'),
               'project': guarded(lambda: check_project(openwiz, project, default_runtime(args.runtime),
                                                        before.get('brain')), 'project_unreadable')}
    results['github_app'], ids = guarded(lambda: check_app(setup.state, project, before['app'], base),
                                         ('app_unreadable', None))

    def change(value):
        if value['checks']['committed'] >= generation:
            raise store.Superseded()
        value['checks']['committed'] = generation
        bound = revision
        if value['revision'] == revision and ids is not None and value['app'] != ids:
            value['app'] = ids
            value['revision'] = bound = revision + 1
        now = int(time.time() * 1000)
        for component, code in results.items():
            value['observations'][component] = {'code': code, 'revision': bound, 'at': now}
    setup.update(change)
    print(json.dumps({'schema': 'openwiz.setup-check.v1', 'results': results}, sort_keys=True))


def prepare(args):
    setup = store.Store(args.state_dir)
    pin = runtime_pin(default_runtime(args.runtime))
    project = {'repository': args.repository, 'project': args.project, 'operator': args.operator,
               'service_issue': args.service_issue, 'answer_thread': args.answer_thread,
               'harness': args.harness, 'model': args.model, 'effort': args.effort, 'runtime': pin}
    store.check_project(project)
    effects = [f"Select {args.repository} and CloudRoom project {args.project} for your first fleet.",
               f"Record {args.operator} as the loop operator and issue #{args.service_issue} for service records.",
               f"Send answers to thread {args.answer_thread}.",
               f"Run agents on {args.harness}, {args.model}, {args.effort} effort.",
               (f"Pin packaged runtime {pin.split()[0]} (source {pin.split()[1][:12]})." if pin
                else "No packaged runtime found; project stays unverified."),
               "Save these settings in this host's owner-only OpenWiz state. Nothing is sent or created."]
    def current(value):
        return value['project'] == project
    if not args.yes:
        operation = setup.propose('prepare_project', project, effects, 'Proposed: confirm with --yes --operation.',
                                  current)
    else:
        store.require(args.operation is not None, '--yes needs --operation from the preview')

        def change(value):
            operation = setup.authorized(value, args.operation, 'prepare_project', project, current)
            if operation['phase'] == 'applied':
                return dict(operation)
            store.require(operation['phase'] == 'proposed', 'that operation is not awaiting confirmation')
            if value['project'] != project:
                value['project'] = project
                value['revision'] += 1
            operation['phase'] = 'applied'
            operation['reason'] = 'Saved. Run the setup check to verify each setting.'
            return dict(operation)
        operation = setup.update(change)
    print(json.dumps(operation, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('prepare', 'check'):
        command = commands.add_parser(name)
        command.add_argument('--state-dir', help='absolute OpenWiz state directory (default: the store\'s)')
        command.add_argument('--runtime', help='installed runtime directory (default: this packaged runtime)')
    p = commands.choices['prepare']
    p.add_argument('--repository', required=True)
    p.add_argument('--project', required=True)
    p.add_argument('--operator', required=True)
    p.add_argument('--service-issue', type=int, required=True)
    p.add_argument('--answer-thread', required=True)
    p.add_argument('--harness', required=True)
    p.add_argument('--model', required=True)
    p.add_argument('--effort', required=True)
    p.add_argument('--yes', action='store_true')
    p.add_argument('--operation')
    c = commands.choices['check']
    c.add_argument('--openwiz', help='installed openwiz CLI (default: this package\'s)')
    c.add_argument('--api-base', default=API, help='GitHub API; loopback HTTP for synthetic tests only')
    args = parser.parse_args()
    (prepare if args.command == 'prepare' else check)(args)


if __name__ == '__main__':
    try:
        main()
    except store.Superseded:
        print('openwiz-setup: superseded: a newer check saved its results first; this check saved nothing',
              file=sys.stderr)
        sys.exit(7)
    except store.Refused as refusal:
        print(f'openwiz-setup: refused: {refusal}', file=sys.stderr)
        sys.exit(5)
    except (OSError, ValueError, StopIteration):
        print('openwiz-setup: refused: setup state or a check could not be completed safely', file=sys.stderr)
        sys.exit(5)
