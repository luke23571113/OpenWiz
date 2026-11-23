from datetime import datetime, timezone
import json
import re
import subprocess

PAGE = 100
API_LIMIT = 1000
TIME = re.compile(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ')
WORKFLOWS = ('ci.yml', 'privacy.yml')
REQUIRED_EVENTS = ('pull_request', 'merge_group')
PROGRESSION = ('requested', 'waiting', 'pending', 'queued', 'in_progress')
WAITING = ('queued', 'waiting', 'pending', 'requested')


class Fail(Exception):
    pass


def strict_json(text, where):
    def pairs(items):
        out = {}
        for k, v in items:
            if k in out:
                raise Fail(f'{where}: repeated key')
            out[k] = v
        return out

    def constant(name):
        raise ValueError(name)

    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except ValueError:
        raise Fail(f'{where}: not JSON')


def need(obj, key, where):
    if key not in obj:
        raise Fail(f'{where}: missing {key!r}')
    return obj[key]


def as_obj(v, where):
    if type(v) is not dict:
        raise Fail(f'{where}: not an object')
    return v


def as_list(v, where):
    if type(v) is not list:
        raise Fail(f'{where}: not a list')
    return v


def as_int(obj, key, where):
    v = need(obj, key, where)
    if type(v) is not int:
        raise Fail(f'{where}: {key!r} is not an integer')
    return v


def as_str(obj, key, where):
    v = need(obj, key, where)
    if type(v) is not str:
        raise Fail(f'{where}: {key!r} is not a string')
    return v


def as_seconds(obj, key, where, null=False):
    v = need(obj, key, where)
    if v is None and null:
        return None
    if type(v) is not str or not TIME.fullmatch(v):
        raise Fail(f'{where}: {key!r} is not a UTC time')
    try:
        return int(datetime.strptime(v, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        raise Fail(f'{where}: {key!r} is not a UTC time')


def gh(path):
    try:
        r = subprocess.run(['gh', 'api', path], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    except OSError:
        raise Fail('gh could not start')
    if r.returncode != 0:
        raise Fail(f'gh api {path} failed (exit {r.returncode})')
    return strict_json(r.stdout, f'gh api {path}')


def pages(path, key):
    items, total, page = [], None, 1
    while total is None or len(items) < total:
        where = f'gh api {path}&page={page}'
        ans = as_obj(gh(f'{path}&page={page}'), where)
        count, got = as_int(ans, 'total_count', where), as_list(need(ans, key, where), where)
        if total is None:
            total = count
            if total > API_LIMIT:
                raise Fail(f'{where}: more than {API_LIMIT} items, the API\'s limit')
        elif count != total:
            raise Fail(f'{where}: total_count changed between pages')
        if not got and len(items) < total:
            raise Fail(f'{where}: fewer items than total_count')
        items += [(item, where) for item in got]
        page += 1
    if len(items) > total:
        raise Fail(f'gh api {path}: more items than total_count')
    return items


def active_runs(base):
    runs = {}
    for workflow in WORKFLOWS:
        for status in PROGRESSION:
            for value, where in pages(f'{base}/workflows/{workflow}/runs?status={status}&per_page={PAGE}',
                                      'workflow_runs'):
                rid = as_int(as_obj(value, where), 'id', where)
                run = (workflow, as_int(value, 'run_attempt', where), as_str(value, 'event', where))
                if runs.setdefault(rid, run) != run:
                    raise Fail('a run listed twice, as two different runs')
    return runs


def budget(resources, pool):
    item = as_obj(need(resources, pool, 'rate_limit'), 'rate_limit ' + pool)
    return {'remaining': as_int(item, 'remaining', pool), 'limit': as_int(item, 'limit', pool),
            'reset_at': as_int(item, 'reset', pool), 'retry_after': 0}


def observe(repo, clock=None):
    clock = clock or (lambda: int(datetime.now(timezone.utc).timestamp()))
    base = f'repos/{repo}/actions'
    complete, jobs = True, []
    runs = active_runs(base)
    for rid, (workflow, attempt, event) in sorted(runs.items()):
        job_path = f'{base}/runs/{rid}/jobs?per_page={PAGE}'
        try:
            page = pages(job_path, 'jobs')
            again = pages(job_path, 'jobs')
        except Fail:
            complete = False
            continue
        if [v.get('id') for v, _ in page] != [v.get('id') for v, _ in again]:
            complete = False
        for value, where in page:
            as_obj(value, where)
            jid, status = as_int(value, 'id', where), as_str(value, 'status', where)
            current = value.get('run_attempt') == attempt and value.get('run_id') == rid
            created = as_seconds(value, 'created_at', where)
            begun = as_seconds(value, 'started_at', where, null=True)
            if status in WAITING:
                status, begun = 'queued', None
            elif status not in ('in_progress', 'completed'):
                complete, status, begun = False, 'queued', None
            if not current or (status == 'in_progress' and begun is None) or (begun is not None and begun < created):
                complete = False
            jobs.append({'id': f'job-{jid}', 'required': event in REQUIRED_EVENTS and current,
                         'status': status, 'queued_at': created, 'started_at': begun})
    after = active_runs(base)
    if any(runs.get(rid) != run for rid, run in after.items()):
        complete = False
    limits = as_obj(need(as_obj(gh('rate_limit'), 'rate_limit'), 'resources', 'rate_limit'), 'resources')
    budgets = {'rest': budget(limits, 'core'), 'graphql': budget(limits, 'graphql')}
    stamp = clock()
    if any(j['queued_at'] > stamp or (j['started_at'] or 0) > stamp for j in jobs):
        complete = False
    return {'repository': repo, 'observed_at': stamp, 'complete': complete,
            'queue': {'complete': complete, 'jobs': jobs}, 'budgets': budgets}


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
