#!/usr/bin/env python3
"""WRD1 (#629): the three v2 health providers. Injected readers only.

`main_ci`, `ci_queue` (`read_queue`) and `stage_health` return providers for
`suite.compose`'s `health` section (contract.v2.md). They reuse the existing
checked readers: `bench.pages` and WR8's `bench.current_activity` with its exact
pool classification for Actions, and TL2's `validate_stage_waits`/`stage_bench`
with TL1's `limits.read` for stages. No CLI, default reader, wall clock,
schedule, limit or policy is added. A failed or unstable read is explicit
Unknown, never green or zero.
"""
import copy
import hashlib
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import activity  # noqa: E402
import stage_waits  # noqa: E402
import suite  # noqa: E402

B = activity.B
producer, limits = stage_waits.producer, stage_waits.limits
MAIN_SCHEMA, QUEUE_SCHEMA = 'openwiz.war-room.main-ci.v1', 'openwiz.war-room.ci-queue.v1'
IDENTITY = ('repository', 'branch', 'head_sha', 'workflow', 'run_id', 'run_attempt', 'pool', 'stage',
            'interval', 'ticket', 'pull_request')
HEALTH_STAGES = ('builder_start', 'reviewer_start', 'merge')
ACTIVE = ('queued', 'in_progress', 'waiting', 'pending', 'requested')
RESULTS = {'success': 'success', 'failure': 'failure', 'timed_out': 'failure', 'startup_failure': 'failure',
           'cancelled': 'cancelled'}
MAIN_READ = 'Complete, stable reads of the main head and every page of its ci.yml push runs are required.'
QUEUE_READ = ("WR8's complete, stable ci.yml run/job pages with every job's attempt, status and created time "
              'are required; an incomplete read never shows zero.')
UNCLASSIFIED = 'A job with missing or unsupported runner labels: no exact pool count is complete.'
QUEUED = 'Still queued at the read: a lower bound measured to the read time.'
SETTINGS = ("TL1's limits.conf must be read at or after TL2's read, so its limits are the ones these waits "
            'were judged by.')
STAGE_REFUSED = ("TL2's journeys.json and its bound stage-waits.json, checked by TL2, and TL1's limits.conf read "
                 'by limits.py are required; {what} was unavailable or refused.')


def _iso(value):
    return value.strftime('%Y-%m-%dT%H:%M:%SZ')


def _minutes(since, until):
    return round((suite._time(until) - suite._time(since)).total_seconds() / 60, 2)


def observation(id, label, *, state, statistic, read, source, point=None, window=None, result=None, value=None,
                unit=None, evidence=(), evidence_class='current_read', cohort=None, identity=None, interval=None,
                limit=None, identities=(), expected='same', prerequisites=()):
    ident = dict.fromkeys(IDENTITY)
    ident.update(identity or {})
    return {'id': id, 'label': label, 'state': state, 'result': result, 'value': value, 'unit': unit,
            'statistic': statistic, 'point': point, 'window': window, 'read': dict(read),
            'fresh_until': None, 'freshness': 'unknown',  # None of these sources owns a validity bound.
            'source': source, 'evidence': sorted(set(evidence)), 'evidence_class': evidence_class,
            'cohort': cohort, 'identity': ident, 'interval': interval, 'limit': limit,
            'sample': {'observed': len(identities), 'expected': len(identities) if expected == 'same' else expected,
                       'identities': list(identities)},
            'prerequisites': [] if state == 'known' else list(dict.fromkeys(prerequisites))}


def provider(slot, observations, prerequisites=()):
    if observations and all(o['state'] == 'known' for o in observations) and not prerequisites:
        state = 'known'
    elif any(o['state'] != 'unavailable' for o in observations):
        state = 'partial'
    else:
        state = 'unavailable'
    gaps = list(dict.fromkeys(list(prerequisites) + [p for o in observations for p in o['prerequisites']]))
    return {'slot': slot, 'state': state, 'observations': observations, 'prerequisites': [] if state == 'known' else gaps}


def unavailable(slot, reason):
    return {'slot': slot, 'state': 'unavailable', 'observations': [], 'prerequisites': [reason]}


def _wire(observed):
    # Only identities, times and fixed words: no titles, branch names, labels or raw errors.
    return (json.dumps(observed, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


# --- main_ci ----------------------------------------------------------------

def _head(repo, read):
    answer = B.as_obj(read(f'repos/{repo}/branches/main'), 'main branch')
    sha = B.as_str(B.as_obj(B.need(answer, 'commit', 'main branch'), 'main commit'), 'sha', 'main commit')
    if B.as_str(answer, 'name', 'main branch') != 'main' or not re.fullmatch('[0-9a-f]{40}', sha):
        raise B.Fail('main head unavailable')
    return sha


def main_ci(repo, read, clock, *, source_path='health/main-ci.json'):
    """(provider, observation bytes): the current main head's latest ci.yml push run."""
    started = clock()
    seen = {'schema': MAIN_SCHEMA, 'repo': repo, 'read_started_at': started, 'head': None,
            'head_after': None, 'runs': None, 'chosen': None, 'gaps': []}
    gaps, chosen, result = seen['gaps'], None, 'unknown'
    try:
        head = seen['head'] = _head(repo, read)
        path = (f'repos/{repo}/actions/workflows/{B.WORKFLOW}/runs?branch=main&event=push'
                f'&head_sha={head}&per_page={B.PAGE}')
        runs = []
        for value, where in B.pages(path, 'workflow_runs', 'runs', read):
            B.as_obj(value, where)
            row = {'id': B.as_int(value, 'id', where), 'run_attempt': B.as_int(value, 'run_attempt', where),
                   'status': B.as_str(value, 'status', where),
                   'conclusion': B.as_str(value, 'conclusion', where, null=True),
                   'head_sha': B.as_str(value, 'head_sha', where), 'head_branch': B.as_str(value, 'head_branch', where),
                   'event': B.as_str(value, 'event', where), 'created_at': B.as_time(value, 'created_at', where)}
            if row['id'] <= 0 or row['run_attempt'] <= 0 or any(r['id'] == row['id'] for r in runs):
                raise B.Fail('main runs: duplicate or invalid identity')
            runs.append(row)
        seen['runs'] = runs
        latest = max((r['created_at'] for r in runs), default=None)
        tied = [r for r in runs if r['created_at'] == latest]
        if any((r['head_sha'], r['head_branch'], r['event']) != (head, 'main', 'push') for r in runs):
            gaps.append('A listed run is not a main push run for the current head: no result is admitted.')
        elif not runs:
            gaps.append('No ci.yml push run is observed for the current main head yet.')
        elif len(tied) > 1:
            gaps.append('ci order unknown: the latest runs on the head were created in the same second.')
        else:
            chosen = seen['chosen'] = tied[0]
            again = B.as_obj(read(f'repos/{repo}/actions/runs/{chosen["id"]}'), 'main run reread')
            if any(again.get(k) != v for k, v in chosen.items()):
                gaps.append('The chosen run changed during the read.')
            elif chosen['status'] != 'completed':
                result = 'pending'
            elif chosen['conclusion'] in RESULTS:
                result = RESULTS[chosen['conclusion']]
            else:
                gaps.append('The run completed without a CI result (conclusion %s).' % chosen['conclusion'])
        after = seen['head_after'] = _head(repo, read)
        if after != head:
            gaps.append('The main head changed during the read.')
    except (B.Fail, OSError, ValueError, TypeError, KeyError):
        gaps.append(MAIN_READ)
    if gaps:
        result = 'unknown'
    ended = clock()
    seen['observed_at'] = ended
    wire = _wire(seen)
    source = {'path': source_path, 'schema': MAIN_SCHEMA, 'sha256': hashlib.sha256(wire).hexdigest()}
    identity = {'repository': repo, 'branch': 'main', 'head_sha': seen['head'], 'workflow': B.WORKFLOW}
    if chosen is not None:
        identity.update(run_id=chosen['id'], run_attempt=chosen['run_attempt'])
    item = observation('main', 'Main CI result at the current main head (latest ci.yml push run)',
                       state='unavailable' if result == 'unknown' else 'known', statistic='result', result=result,
                       read={'started_at': started, 'ended_at': ended}, point=ended, source=source,
                       evidence=[f'https://github.com/{repo}/actions/runs/{chosen["id"]}'] if chosen else [],
                       cohort='main-head', identity=identity, prerequisites=gaps,
                       identities=[f'run-{chosen["id"]}-attempt-{chosen["run_attempt"]}'] if chosen else [])
    return provider('main_ci', [item]), wire


# --- ci_queue ---------------------------------------------------------------

JOBS = re.compile(r'repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/runs/[1-9][0-9]*/jobs\?.*')


def capture(read):
    """WR8's reader, unchanged, with each job's raw page entry kept for its created time."""
    raw = {}

    def wrapped(path):
        answer = read(path)
        if JOBS.fullmatch(path) and type(answer) is dict and type(answer.get('jobs')) is list:
            for item in answer['jobs']:
                if type(item) is dict and type(item.get('id')) is int:
                    raw[item['id']] = copy.deepcopy(item)
        return answer
    return wrapped, raw


def read_queue(repo, pools, read, started, ended, *, source_path='health/ci-queue.json'):
    """One WR8 current read, then its queue projection. `read` lists every ci.yml run."""
    wrapped, raw = capture(read)
    day = _iso(suite._time(ended).replace(hour=0, minute=0, second=0))
    try:
        ci = B.current_activity(day, ended, repo=repo, read=wrapped)
    except (B.Fail, OSError, ValueError, TypeError, KeyError):
        ci = None
    return ci_queue(repo, pools, ci, raw, started, ended, source_path=source_path)


def ci_queue(repo, pools, ci, raw, started, ended, *, source_path='health/ci-queue.json'):
    """(provider, observation bytes) from WR8's checked current observation `ci` (None: failed)."""
    if len(set(pools)) != len(pools) or any(p not in B.ACTIVITY_POOLS for p in pools):
        raise ValueError('select unique exact supported pool labels')
    seen = {'schema': QUEUE_SCHEMA, 'repo': repo, 'read_started_at': started, 'observed_at': ended,
            'pools': list(pools), 'jobs': None}
    if ci is not None:
        try:
            jobs = []
            for j in ci['jobs']:
                if j['status'] == 'completed':
                    continue
                created = B.as_time(B.as_obj(raw.get(j['id']), 'queued job'), 'created_at', 'queued job')
                if created > ended:  # `ended` is the queue read's actual end (gather closes it after WR8's reads)
                    raise B.Fail('job created after the read')
                jobs.append({'id': j['id'], 'run': j['run'], 'attempt': j['attempt'], 'status': j['status'],
                             'pool': j['pool'], 'created_at': created})
            seen['jobs'] = jobs
        except (B.Fail, TypeError, KeyError):
            seen['jobs'] = None
    wire = _wire(seen)
    source = {'path': source_path, 'schema': QUEUE_SCHEMA, 'sha256': hashlib.sha256(wire).hexdigest()}
    read_bounds = {'started_at': started, 'ended_at': ended}
    jobs, items = seen['jobs'], []

    def link(j):
        return f'https://github.com/{repo}/actions/runs/{j["run"]}'
    for pool in pools:
        for status, name in (('queued', 'queued'), ('in_progress', 'running')):
            if jobs is None:
                items.append(observation(f'{name}:{pool}', f'CI {name} in exact pool {pool}', state='unavailable',
                                         statistic='count', unit='count', read=read_bounds, source=source,
                                         point=ended, identity={'pool': pool, 'workflow': B.WORKFLOW},
                                         expected=None, prerequisites=[QUEUE_READ]))
                continue
            complete = all(j['pool'] is not None for j in jobs)
            mine = [j for j in jobs if j['status'] == status and j['pool'] == pool]
            items.append(observation(f'{name}:{pool}', f'CI {name} in exact pool {pool}',
                                     state='known' if complete else 'partial', statistic='count', unit='count',
                                     value=len(mine) if complete else None, read=read_bounds, source=source,
                                     point=ended, evidence=[link(j) for j in mine], cohort='ci-yml-active',
                                     identity={'pool': pool, 'workflow': B.WORKFLOW},
                                     identities=[f'job-{j["id"]}' for j in mine],
                                     expected='same' if complete else None, prerequisites=[UNCLASSIFIED]))
        if jobs is None:
            continue
        queued = sorted((j for j in jobs if j['status'] == 'queued' and j['pool'] == pool), key=lambda j: j['id'])
        if queued and all(j['pool'] is not None for j in jobs):
            items.append(observation(f'oldest-queued:{pool}', f'Oldest queued job age in exact pool {pool} (at the read)',
                                     state='known', statistic='max', unit='minutes', read=read_bounds, source=source,
                                     value=max(_minutes(j['created_at'], ended) for j in queued), point=ended,
                                     evidence=[link(j) for j in queued], cohort='ci-yml-active',
                                     identity={'pool': pool, 'workflow': B.WORKFLOW},
                                     identities=[f'job-{j["id"]}' for j in queued]))
        for j in queued:
            items.append(observation(f'queued-wait:{pool}:job-{j["id"]}', f'Queued job wait in exact pool {pool}',
                                     state='partial', statistic='observation', unit='minutes', read=read_bounds,
                                     source=source, value=_minutes(j['created_at'], ended), point=ended,
                                     evidence=[link(j)], cohort='ci-yml-active',
                                     identity={'pool': pool, 'workflow': B.WORKFLOW, 'run_id': j['run'],
                                               'run_attempt': j['attempt']},
                                     interval={'id': f'job-{j["id"]}', 'started_at': j['created_at'], 'ended_at': None},
                                     identities=[f'job-{j["id"]}'], prerequisites=[QUEUED]))
    return provider('ci_queue', items, [] if jobs is not None else [QUEUE_READ]), wire


# --- stage_health -------------------------------------------------------------

def stage_health(root, *, journey, sidecar, settings, settings_read_at, read, evidence):
    """The health stages from TL2's validated evidence against TL1's loaded limits.

    The same pinned inputs `stage_waits.project` reads; refusal is the explicit
    unavailable slot. `read` is the caller's collection bounds."""
    try:
        pinned = {what: stage_waits._pinned(root, rel)
                  for what, rel in (('journey', journey), ('sidecar', sidecar), ('settings', settings))}
    except (OSError, ValueError):
        return unavailable('stage_health', STAGE_REFUSED.format(what='an input file'))
    try:
        doc = producer.M.load(pinned['journey'][0].decode('utf-8'))
        side = producer.M.load(pinned['sidecar'][0].decode('utf-8'))
        producer.validate_stage_waits(side, doc)
    except (ValueError, UnicodeError, KeyError, TypeError, StopIteration, producer.ReadError):
        return unavailable('stage_health', STAGE_REFUSED.format(what='the TL2 journey/sidecar pair'))
    try:
        loaded = stage_waits._settings(root, settings, pinned['settings'][0])
    except (OSError, ValueError, UnicodeError):
        return unavailable('stage_health', STAGE_REFUSED.format(what='the TL1 settings file'))
    read_at = side['read_at']
    if settings_read_at is None or suite._time(settings_read_at) < suite._time(read_at):
        return unavailable('stage_health', SETTINGS)
    bench = producer.stage_bench(side, loaded)
    suite.require(bench['authority'] == 'none', 'stage facts carry no authority')
    repo, links = side['repo'], side['sources']
    intervals = {i['key']: i for i in side['intervals']}
    tl2 = {'path': pinned['sidecar'][1]['path'], 'schema': side['schema'], 'sha256': pinned['sidecar'][1]['sha256']}
    tl1 = {'path': pinned['settings'][1]['path'], 'schema': loaded['schema'], 'sha256': pinned['settings'][1]['sha256']}

    def limit(minutes):
        return {'minutes': minutes, 'owner': 'tools/factory-metrics/limits.conf', 'schema': loaded['schema'],
                'sha256': tl1['sha256'], 'read_at': settings_read_at}
    items = []
    for row in bench['stages']:
        stage = row['stage']
        if stage not in HEALTH_STAGES:
            continue  # Fix and answer stay in stage_waits' detailed figures.
        name = stage_waits.NAMES[stage]
        items.append(observation(f'limit:{stage}', f'{name} limit (TL1 setting)', state='known', statistic='limit',
                                 unit='minutes', value=row['limit_minutes'], read=read, source=tl1,
                                 point=settings_read_at, evidence=evidence, evidence_class='settings_read',
                                 cohort='tl1-limits', identity={'stage': stage}, limit=limit(row['limit_minutes'])))
        for w in (w for w in bench['waits'] if w['stage'] == stage):
            i, key = intervals[w['key']], w['key'].lower()
            ticket = w['tickets'][0] if len(w['tickets']) == 1 else None
            links_ = [f'https://github.com/{repo}/issues/{t}' for t in w['tickets']]
            if w['pull_request'] is not None:
                links_.append(f'https://github.com/{repo}/pull/{w["pull_request"]}')
            links_ += [links[s] for s in [w['start'], w['end'], *w['support']] if s]
            start = i['start']['at'] if i['start'] else None
            exact_end = i['end'] and i['end']['at'] == i['end']['latest']
            interval = {'id': key, 'started_at': start, 'ended_at': i['end']['at'] if start and exact_end else None}
            result = w['result'].replace(' ', '_')
            gaps = [f'TL2 {w["result"]}: {g}' for g in w['gaps']]
            if result in ('gated', 'stale'):
                state, value = 'partial', None
            elif w['wait_range_minutes'] is None:  # TL2 measured nothing: wholly unobserved
                state, value = 'unavailable', None
            elif i['end'] is None:
                state, value = 'partial', w['wait_range_minutes'][0]
                gaps.append('Open at the TL2 read: the wait is a lower bound measured to its read time.')
            elif w['wait_minutes'] is None:
                state, value = 'partial', w['wait_range_minutes'][0]
                gaps.append('Edited end record: the wait lies between {} and {} minutes.'.format(*w['wait_range_minutes']))
            else:
                state, value = 'known', w['wait_minutes']
            items.append(observation(f'wait:{key}', f'{name} wait: {w["result"]}', state=state, statistic='observation',
                                     unit='minutes', result=result, value=value, read=read, source=tl2, point=read_at,
                                     evidence=links_, evidence_class='producer_fact', cohort='tl2-stage-health',
                                     identity={'stage': stage, 'interval': key, 'ticket': ticket,
                                               'pull_request': w['pull_request']},
                                     interval=interval, limit=limit(w['limit_minutes']), identities=[key],
                                     prerequisites=gaps))
    return provider('stage_health', items, [stage_waits.HISTORY])
