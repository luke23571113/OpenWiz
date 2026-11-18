#!/usr/bin/env python3
"""MT3 (#822): the collector's CI facts (collector.v1.md), read on demand. Reads only.

  python3 -I collect_ci.py read --repo OWNER/NAME --fact NAME [--fact NAME ...] [--since UTC --until UTC]

Prints one `openwiz.war-room.collector.read.v1` envelope holding the named
CI facts (`runs`, `minutes`, `ci3`, `activity`, `queue`) and exits 0. A bad
command line exits 2 before any read; a refused read (a privacy hit, an
envelope that breaks the contract) exits 1 with nothing on stdout.

Every number comes from the tool that produces it today, unchanged: ci-bench's
`collect` and `measure` (`runs`, `minutes`), CI3's `collect` and `measure`
(`ci3`) and WR8's `current_activity` (`activity`). `queue` is the overload
guard's observation, read in the same pass. Every read is a `gh api` GET of
the named repository. A fact that can't be read is `unavailable` with its
prerequisite, never zero.

The exact bytes behind `runs`/`minutes` (ci-bench's job records) and `ci3`
(CI3's private window) are kept, owner-only, in the collector store
(OPENWIZ_COLLECTOR_STORE, by default ~/.openwiz/war-room/collector) at their
`source.path`, named by their SHA-256, before the read returns. A source that
can't be kept leaves its fact unavailable. `activity` and `queue` carry their
observed bytes in their value.
"""
import argparse
import contextlib
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'collector'))
import collector_runtime
import activity  # noqa: E402
import health  # noqa: E402
import sources  # noqa: E402
import suite  # noqa: E402

C3 = sources.native('tools/war-room/ci3.py')
B = C3.bench  # ci-bench's reader, rules and prices: the numbers ci-bench publishes
FAILS = (B.Fail, activity.B.Fail, OSError, ValueError, TypeError, KeyError, ArithmeticError)
SCHEMA = json.loads((HERE / 'collector.v1.schema.json').read_text(encoding='utf-8'))
FACTS = ('runs', 'minutes', 'ci3', 'activity', 'queue')
WINDOWED = ('runs', 'minutes', 'ci3')
QUEUE_BOUND = 60  # seconds: the overload guard's --max-age (collector.v1.md, "Freshness")
QUEUE_WORKFLOWS = ('ci.yml', 'privacy.yml')
REQUIRED_EVENTS = ('pull_request', 'merge_group')  # runs the required checks `ci` and `privacy` wait on
# Earliest first: a run that moves on while the statuses are listed lands in a later list, never in none.
PROGRESSION = ('requested', 'waiting', 'pending', 'queued', 'in_progress')
WAITING = ('queued', 'waiting', 'pending', 'requested')  # a job not yet on a runner
ROBOTS = 5  # ci-bench's daily default (daily.sh); runs and minutes don't depend on it
UNAVAILABLE = {
    'runs': 'CI runs unavailable: the ci.yml run read failed.',
    'minutes': 'CI minutes unavailable: the ci.yml job read failed.',
    'ci3': 'CI3 unavailable: the window\'s PR heads and runs could not be read whole.',
    'activity': 'Current CI activity unavailable: the ci.yml run and job pages were incomplete or changed.',
    'queue': 'Queue and rate limits unavailable: the Actions or rate-limit read failed.',
}
UNSETTLED = 'The window has not ended yet: read it once it has.'
NO_PRICE = 'Some job has no known price or timing: the list-rate totals are unknown.'
INCOMPLETE_QUEUE = ('The queue read is incomplete: a run or job changed during the read, or a job page or a job\'s '
                    'run, attempt or start could not be established.')
NOT_KEPT = 'The read\'s source bytes could not be kept in the collector store, so nothing recoverable stands behind it.'


class Refused(Exception):
    """The whole read is refused: nothing is printed."""


def now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(at):
    return at.strftime('%Y-%m-%dT%H:%M:%SZ')


def at_of(text):
    return datetime.strptime(text, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def runs_link(repo, rid):
    return f'https://github.com/{repo}/actions/runs/{rid}'


def fact(name, state, *, read=None, point=None, window=None, fresh_until=None, freshness='unknown', source=None,
         evidence=(), prerequisites=(), value=None):
    return {'fact': name, 'state': state, 'read': read, 'point': point, 'window': window,
            'fresh_until': fresh_until, 'freshness': freshness, 'source': source,
            'evidence': sorted(set(evidence), key=lambda link: (len(link), link)),
            'prerequisites': list(prerequisites), 'value': value}


def unavailable(name, read, window, why=None):
    return fact(name, 'unavailable', read=read, window=window, prerequisites=[why or UNAVAILABLE[name]])


@contextlib.contextmanager
def pinned(repo):
    """gh resolves `{owner}/{repo}` in ci-bench's and CI3's paths from GH_REPO: pin it to `repo`."""
    before = os.environ.get('GH_REPO')
    os.environ['GH_REPO'] = repo
    try:
        yield
    finally:
        if before is None:
            os.environ.pop('GH_REPO', None)
        else:
            os.environ['GH_REPO'] = before


def store():
    return Path(os.environ.get('OPENWIZ_COLLECTOR_STORE') or Path.home() / '.openwiz' / 'war-room' / 'collector')


def keep(kind, data, suffix):
    """Keep `data` exactly, owner-only, named by its hash; return its source path and hash. OSError if it can't."""
    sha = digest(data)
    rel = f'collector/ci/{kind}/{sha}{suffix}'
    root = store()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = root / rel
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.keep-')  # owner-only
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return rel, sha


# ---------------------------------------------------------------- runs and minutes


def by_kind(minutes):
    return [{'runner_kind': kind, 'minutes': minutes[kind]} for kind in sorted(minutes)]


def bench_window(since, until):
    """ci-bench's own collect and measure of [since, until), as daily.sh runs them: its point."""
    with tempfile.TemporaryDirectory(prefix='collect-ci-') as tmp, contextlib.redirect_stdout(io.StringIO()):
        B.collect(since, until, tmp)
        jobs = (Path(tmp) / 'jobs.jsonl').read_bytes()
        B.measure(tmp, ROBOTS, 'collector', allow_empty=True, allow_timing_gaps=True)
        point = json.loads((Path(tmp) / 'point.json').read_text(encoding='utf-8'))
    run_ids = sorted({json.loads(line)['run'] for line in jobs.decode().splitlines()})
    return point, jobs, run_ids


def runs_and_minutes(repo, names, since, until):
    window = {'since': since, 'until': until, 'timezone': 'UTC'}
    started = now()
    if at_of(until) > started:
        return {n: unavailable(n, None, window, UNSETTLED) for n in names}
    try:
        point, jobs, run_ids = bench_window(since, until)
    except FAILS:
        bounds = {'started_at': iso(started), 'ended_at': iso(now())}
        return {n: unavailable(n, bounds, window) for n in names}
    try:
        path, sha = keep('runs', jobs, '.jsonl')
    except OSError:
        bounds = {'started_at': iso(started), 'ended_at': iso(now())}
        return {n: unavailable(n, bounds, window, NOT_KEPT) for n in names}
    bounds = {'started_at': iso(started), 'ended_at': iso(now())}
    source = {'path': path, 'schema': 'github.rest.actions.runs', 'sha256': sha}
    evidence = [runs_link(repo, rid) for rid in run_ids]
    code, cost = point['code_runs'], point['cost']
    out = {}
    if 'runs' in names:
        out['runs'] = fact('runs', 'known', read=bounds, window=window, source=source, evidence=evidence, value={
            'workflow': B.WORKFLOW, 'runs': point['runs'], 'jobs': point['jobs'],
            'unknown_jobs': cost.get('unknown_jobs', 0), 'code_runs': code['runs'] if code else 0,
            'latency_basis': point['latency_basis'],
            'queued_to_done_minutes': code['queued_to_done'] if code else None})
    if 'minutes' in names:
        value = {'runner_minutes': by_kind(cost['runner_minutes']), 'billed_minutes': by_kind(cost['billed_minutes']),
                 'unknown_minutes': cost['unknown_minutes'], 'window_usd': cost['window_usd'],
                 'per_code_run_usd': cost['per_code_run_usd'], 'prices': cost['prices']}
        unknown = cost['window_usd'] is None or cost['unknown_minutes'] is None
        out['minutes'] = fact('minutes', 'partial' if unknown else 'known', read=bounds, window=window, source=source,
                              evidence=evidence, prerequisites=[NO_PRICE] if unknown else [], value=value)
    return out


# ---------------------------------------------------------------- CI3


def ci3(repo, since, until):
    window = {'since': since, 'until': until, 'timezone': 'UTC'}
    started = now()
    if at_of(until) > started:
        return unavailable('ci3', None, window, UNSETTLED)
    try:
        with tempfile.TemporaryDirectory(prefix='collect-ci3-') as tmp, contextlib.redirect_stderr(io.StringIO()):
            path = Path(tmp) / 'window.json'
            C3.collect(since, until, path, read=B.gh)  # CI3 stamps its own collected_at, as ci3.py does
            raw = path.read_bytes()
            record = C3.measure(C3.read_window(path))
    except FAILS:
        return unavailable('ci3', {'started_at': iso(started), 'ended_at': iso(now())}, window)
    try:
        path, sha = keep('ci3', raw, '.json')
    except OSError:
        return unavailable('ci3', {'started_at': iso(started), 'ended_at': iso(now())}, window, NOT_KEPT)
    heads = json.loads(raw)['heads']
    missing = record['missing']
    return fact('ci3', 'partial' if missing else 'known',
                read={'started_at': iso(started), 'ended_at': record['collected_at']}, window=window,
                source={'path': path, 'schema': C3.WINDOW_SCHEMA, 'sha256': sha},
                evidence=[f'https://github.com/{repo}/pull/{h["pr"]}' for h in heads],
                prerequisites=[f'{len(missing)} PR heads have no result yet; the record lists them in missing.']
                if missing else [], value=record)


# ---------------------------------------------------------------- activity and queue


def current(repo):
    """WR8's current ci.yml observation for today so far, as gather reads it, with each active job's creation."""
    started = now()
    day = started.replace(hour=0, minute=0, second=0)
    window = {'since': iso(day), 'until': iso(started), 'timezone': 'UTC'}
    read, raw = health.capture(collector_runtime.current_runs(repo, iso(day), iso(started), B.gh))
    try:
        observed = activity.B.current_activity(iso(day), iso(started), repo=repo, read=read)
        created = [{'job': j['id'], 'created_at': B.as_time(raw[j['id']], 'created_at', 'active job')}
                   for j in observed['jobs'] if j['status'] != 'completed']
    except FAILS:
        return unavailable('activity', {'started_at': iso(started), 'ended_at': iso(now())}, window)
    value = {'window': window, 'current': observed, 'created_at': created}
    return fact('activity', 'known', read={'started_at': iso(started), 'ended_at': iso(now())}, window=window,
                source={'path': 'collector/ci/activity.json', 'schema': 'openwiz.war-room.activity.v1',
                        'sha256': digest(wire(observed))},
                evidence=[runs_link(repo, rid) for rid in observed['runs']], value=value)


def seconds(text):
    return int(at_of(text).timestamp())


def budget(resources, pool):
    item = B.as_obj(B.need(resources, pool, 'rate_limit'), 'rate_limit ' + pool)
    return {'remaining': B.as_int(item, 'remaining', pool), 'limit': B.as_int(item, 'limit', pool),
            'reset_at': B.as_int(item, 'reset', pool), 'retry_after': 0}


def active_runs(base):
    """Every active ci.yml and privacy.yml run: {id: (workflow, attempt, event)}, statuses listed earliest first."""
    runs = {}
    for workflow in QUEUE_WORKFLOWS:
        for status in PROGRESSION:
            path = f'{base}/workflows/{workflow}/runs?status={status}&per_page={B.PAGE}'
            for value, where in B.pages(path, 'workflow_runs', 'runs', B.gh):
                rid = B.as_int(B.as_obj(value, where), 'id', where)
                run = (workflow, B.as_int(value, 'run_attempt', where), B.as_str(value, 'event', where))
                if runs.setdefault(rid, run) != run:
                    raise B.Fail('a run listed twice, as two different runs')
    return runs


def queue(repo):
    """The overload guard's observation: required ci.yml and privacy.yml jobs and both rate-limit pools.

    Like WR8's reader, two run enumerations bracket the job reads and each job page is read twice: a run or
    job that appears, or a run whose attempt or event changes, in between makes the observation incomplete."""
    started = now()
    base = f'repos/{repo}/actions'
    complete, jobs, names, run_ids = True, [], [], set()
    try:
        runs = active_runs(base)
        for rid, (workflow, attempt, event) in sorted(runs.items()):
            job_path = f'{base}/runs/{rid}/jobs?per_page={B.PAGE}'
            try:
                page = B.pages(job_path, 'jobs', 'jobs', B.gh)
                again = B.pages(job_path, 'jobs', 'jobs', B.gh)
            except FAILS:
                complete = False  # a short page or a changed total: this run's jobs are unknown
                continue
            if [v.get('id') for v, _ in page] != [v.get('id') for v, _ in again]:
                complete = False  # a job came or went between two reads: the run's membership is unknown
            for value, where in page:
                B.as_obj(value, where)
                jid, status = B.as_int(value, 'id', where), B.as_str(value, 'status', where)
                current_attempt = value.get('run_attempt') == attempt and value.get('run_id') == rid
                created = seconds(B.as_time(value, 'created_at', where))
                begun = B.as_time(value, 'started_at', where, null=True)
                begun = None if begun is None else seconds(begun)
                if status in WAITING:
                    status, begun = 'queued', None
                elif status not in ('in_progress', 'completed'):
                    complete, status, begun = False, 'queued', None  # an unknown state: kept, as still waiting
                if (not current_attempt or (status == 'in_progress' and begun is None)
                        or (begun is not None and begun < created)):
                    complete = False  # its run, attempt or start can't be established; the job is kept
                labels = value.get('labels')
                jobs.append({'id': f'job-{jid}', 'required': event in REQUIRED_EVENTS and current_attempt,
                             'status': status, 'queued_at': created, 'started_at': begun})
                names.append({'job': f'job-{jid}', 'workflow': workflow, 'run_id': rid, 'run_attempt': attempt,
                              'pool': activity.B.activity_pool(labels) if type(labels) is list else None})
                run_ids.add(rid)
        after = active_runs(base)
        if any(runs.get(rid) != run for rid, run in after.items()):
            complete = False  # a run appeared, or its attempt changed, while its jobs were read
        limits = B.as_obj(B.need(B.as_obj(B.gh('rate_limit'), 'rate_limit'), 'resources', 'rate_limit'), 'resources')
        budgets = {'rest': budget(limits, 'core'), 'graphql': budget(limits, 'graphql')}
    except FAILS:
        return unavailable('queue', {'started_at': iso(started), 'ended_at': iso(now())}, None)
    ended = now()
    stamp = int(ended.timestamp())
    if any(j['queued_at'] > stamp or (j['started_at'] or 0) > stamp for j in jobs):
        complete = False  # a time after the read's end: the observation can't cover it
    observation = {'repository': repo, 'observed_at': stamp, 'complete': complete,
                   'queue': {'complete': complete, 'jobs': jobs}, 'budgets': budgets}
    return fact('queue', 'known' if complete else 'partial', read={'started_at': iso(started), 'ended_at': iso(ended)},
                point=iso(ended), fresh_until=iso(ended + timedelta(seconds=QUEUE_BOUND)), freshness='fresh',
                source={'path': 'collector/ci/queue.json', 'schema': 'github.rest.actions.jobs+rate_limit',
                        'sha256': digest(wire(observation))},
                evidence=[runs_link(repo, rid) for rid in sorted(run_ids)],
                prerequisites=[] if complete else [INCOMPLETE_QUEUE],
                value={'observation': observation, 'jobs': names})


# ---------------------------------------------------------------- the read and its checks


def empty(name, value):
    """A complete read of nothing, which needs no evidence link."""
    return {'runs': lambda: value['runs'] == 0, 'minutes': lambda: not value['runner_minutes'],
            'ci3': lambda: value['heads'] == 0, 'activity': lambda: not value['current']['runs'],
            'queue': lambda: not value['jobs']}[name]()


def validate(f):
    """collector.v1.md's cross-field rules for one CI fact; ValueError names the first broken rule."""
    need = suite.require
    need(type(f) is dict and f.get('fact') in FACTS, 'not a CI fact')
    name = f['fact']
    suite._shape(f, SCHEMA['$defs']['fact_' + name], SCHEMA)
    state, value, read = f['state'], f['value'], f['read']
    need(f['point'] is None or f['window'] is None, f'{name}: both a point and a window')
    if state == 'known':
        need(value is not None and not f['prerequisites'] and read is not None and f['source'] is not None,
             f'{name}: a known fact needs a value, a read and a source, and no prerequisite')
        need(f['point'] is not None or f['window'] is not None, f'{name}: a known fact needs its time')
        need(f['evidence'] or empty(name, value), f'{name}: a known fact needs evidence')
    elif state == 'partial':
        need(value is not None and f['prerequisites'], f'{name}: a partial fact needs a value and a prerequisite')
    else:
        need(value is None and f['prerequisites'], f'{name}: an unavailable fact has no value and a prerequisite')
    if read is not None:
        need(at_of(read['started_at']) <= at_of(read['ended_at']), f'{name}: its read ends before it starts')
        if f['point'] is not None:
            need(at_of(read['started_at']) <= at_of(f['point']) <= at_of(read['ended_at']),
                 f'{name}: its point lies outside its read')
    if f['window'] is not None:
        need(at_of(f['window']['since']) < at_of(f['window']['until']), f'{name}: an empty window')
        if read is not None and value is not None:
            need(at_of(f['window']['until']) <= at_of(read['ended_at']), f'{name}: its window ends after its read')
    if value is None:
        need(f['freshness'] == 'unknown' and f['fresh_until'] is None, f'{name}: freshness without a value')
        return
    if name == 'queue':
        need(f['window'] is None and f['point'] == read['ended_at'], 'queue: its point is the read\'s end')
        need(f['fresh_until'] == iso(at_of(read['ended_at']) + timedelta(seconds=QUEUE_BOUND)),
             'queue: fresh_until is 60 seconds after the read')
        observation = value['observation']
        need(observation['observed_at'] == seconds(read['ended_at']), 'queue: observed_at is the read\'s end')
        need(observation['complete'] == observation['queue']['complete'] == (state == 'known'),
             'queue: an incomplete observation is partial')
        need([j['id'] for j in observation['queue']['jobs']] == [j['job'] for j in value['jobs']],
             'queue: every observation job is named once')
    else:
        need(f['fresh_until'] is None and f['freshness'] == 'unknown', f'{name}: no validity bound but the guard\'s')
    if name == 'runs':
        need((value['code_runs'] == 0) == (value['queued_to_done_minutes'] is None),
             'runs: latency exists exactly when a code run does')
    if name == 'minutes':
        need((value['window_usd'] is None or value['unknown_minutes'] is None) == (state == 'partial'),
             'minutes: unknown totals are partial')
    if name == 'ci3':
        need(value['schema'] == C3.SCHEMA and (value['since'], value['until']) == (f['window']['since'], f['window']['until']),
             'ci3: the record is its window\'s')
        need(read['ended_at'] == value['collected_at'], 'ci3: its read ends at the record\'s collection')
        need(bool(value['missing']) == (state == 'partial'), 'ci3: a record with missing heads is partial')
    if name == 'activity':
        need(value['window'] == f['window'], 'activity: one window')
        active = {j['id'] for j in value['current']['jobs'] if j['status'] != 'completed'}
        need({c['job'] for c in value['created_at']} == active, 'activity: each active job\'s creation time')


def read(repository, facts, *, since=None, until=None):
    """The named CI facts, read now, as one read envelope (collector.v1.md, "The on-demand read")."""
    facts = list(dict.fromkeys(facts))
    suite.require(facts and all(f in FACTS for f in facts), 'name at least one CI fact')
    suite._shape(repository, SCHEMA['$defs']['read_envelope']['properties']['repository'], SCHEMA)
    windowed = [f for f in facts if f in WINDOWED]
    if windowed or since is not None or until is not None:
        suite.require(since is not None and until is not None and B.TIME.fullmatch(since) and B.TIME.fullmatch(until)
                      and at_of(since) < at_of(until), f'{", ".join(windowed) or "a window"} needs --since before --until')
    requested = now()
    got = {}
    with pinned(repository):
        if 'runs' in facts or 'minutes' in facts:
            got.update(runs_and_minutes(repository, [f for f in facts if f in ('runs', 'minutes')], since, until))
        if 'ci3' in facts:
            got['ci3'] = ci3(repository, since, until)
        if 'activity' in facts:
            got['activity'] = current(repository)
        if 'queue' in facts:
            got['queue'] = queue(repository)
    envelope = {'schema': 'openwiz.war-room.collector.read.v1', 'repository': repository,
                'requested_at': iso(requested), 'factory': {}, 'ci': {f: got[f] for f in facts}}
    check(envelope)
    return envelope


def check(envelope):
    """The envelope's shape, every fact's own rules, and the privacy scan: any failure refuses the read."""
    try:
        suite._shape(envelope, SCHEMA['$defs']['read_envelope'], SCHEMA)
        for f in envelope['ci'].values():
            validate(f)
            if f['read'] is not None and f['fact'] != 'ci3':
                suite.require(at_of(f['read']['started_at']) >= at_of(envelope['requested_at']),
                              f'{f["fact"]}: read before it was requested')
    except ValueError as error:
        raise Refused(f'the read breaks the collector contract: {error}')
    try:
        collector_runtime.scan_bytes(json.dumps(envelope, indent=1).encode())
    except collector_runtime.Fail as error:
        raise Refused(str(error))


def main(argv=None):
    parser = argparse.ArgumentParser(prog='collect_ci.py', description=__doc__.split('\n\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    r = sub.add_parser('read', help='read the named CI facts now')
    r.add_argument('--repo', required=True)
    r.add_argument('--fact', action='append', required=True, choices=FACTS)
    r.add_argument('--since')
    r.add_argument('--until')
    args = parser.parse_args(argv)
    try:
        suite._shape(args.repo, SCHEMA['$defs']['read_envelope']['properties']['repository'], SCHEMA)
        if any(f in WINDOWED for f in args.fact) or args.since is not None or args.until is not None:
            suite.require(args.since is not None and args.until is not None
                          and B.TIME.fullmatch(args.since) and B.TIME.fullmatch(args.until)
                          and at_of(args.since) < at_of(args.until), 'runs, minutes and ci3 need --since before --until')
    except ValueError as error:
        parser.error(str(error))
    try:
        envelope = read(args.repo, args.fact, since=args.since, until=args.until)
    except Refused as error:
        print(f'collect_ci: refused: {error}', file=sys.stderr)
        return 1
    print(json.dumps(envelope, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
