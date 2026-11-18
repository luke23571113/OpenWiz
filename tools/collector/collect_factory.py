#!/usr/bin/env python3
"""MT2 (#821): the war room collector's factory facts (collector.v1.md). Reads only.

  python3 -I tools/collector/collect_factory.py read --repo OWNER/NAME --fact NAME [--fact NAME ...]
      [--since UTC --until UTC] [--usage FILE] [--robots N] [--ticket N ...] [--base NAME] [--check NAME ...]
      [--now UTC]

Prints one `openwiz.war-room.collector.read.v1` envelope holding the named
factory facts, read now: merges, prs_per_hour, stage_waits, stalls, open_prs,
journeys and cost. Without --since/--until the window is the last complete UTC
day. A fact that cannot be read is `unavailable` with its prerequisite and
greys only itself; a privacy hit anywhere refuses the whole read (exit 1,
nothing on stdout). A bad command line exits 2 before any read.

The numbers are factory-metrics', ci-bench's and journey.py's own, on the same
reads: this module calls their readers (metrics.py's PR, comment, direction,
billing and usage reads; journey.py's collect and stage bench; bench.py's
collect and measure) and keeps their rounding. Only factory-metrics' daily gap
arithmetic is generalized here, from one UTC day to any window of whole UTC
hours. `--usage` is factory-metrics' daily CloudRoom usage export; `--ticket`
names the tickets whose stage waits are read (the board's open approved work);
`--now` fixes the clock, for fixture proofs.
"""
import argparse
import contextlib
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import collector_runtime
import suite  # noqa: E402


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


J = _module('collect_factory_journey', HERE / 'journey.py')
M = J.M  # journey.py's own metrics module: one ReadError for every read below
A = _module('collect_factory_stall_alarm', ROOT / 'tools/stall-alarm/alarm.py')
B = _module('collect_factory_bench', HERE / 'bench_measure.py')  # ci-bench's collect and measure (#826)
LIMITS = 'tools/collector/limits.conf'  # TL1's one settings file
SCHEMA = suite._decode((HERE / 'collector.v1.schema.json').read_text(encoding='utf-8'))
FACTS = tuple(SCHEMA['x-facts']['factory'])
READ, SNAPSHOT = 'openwiz.war-room.collector.read.v1', 'openwiz.war-room.collector.v1'
ROBOTS = 5  # ci-bench's daily capacity assumption (daily.sh)
REPO = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+')
UTC = re.compile(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ')
SHA = re.compile(r'[0-9a-f]{40}')

# The collector's PR inventory: factory-metrics' query document plus each PR's base branch.
INVENTORY = '''query($owner:String!,$name:String!,$cursor:String){repository(owner:$owner,name:$name){pullRequests(first:100,after:$cursor){nodes{number baseRefName mergedAt closedAt closingIssuesReferences(first:100){nodes{number repository{nameWithOwner}} pageInfo{hasNextPage endCursor}}} pageInfo{hasNextPage endCursor}}}}'''
# The stall alarm's open-PR read, without its search (merges come from the inventory).
OPEN = '''query($owner:String!,$name:String!,$cursor:String){repository(owner:$owner,name:$name){defaultBranchRef{name} pullRequests(states:OPEN,first:50,after:$cursor){nodes{number isDraft baseRefName headRefOid mergeable comments(last:100){pageInfo{hasPreviousPage} nodes{databaseId createdAt updatedAt body}} commits(last:1){nodes{commit{oid statusCheckRollup{state contexts(first:100){pageInfo{hasNextPage} nodes{__typename ... on CheckRun{name status conclusion} ... on StatusContext{context state}}}}}}}} pageInfo{hasNextPage endCursor}}}}'''
RECORD_KIND = re.compile(r'launch-fleet: (review starting|review withdrawn|review started|review told again|re-check sent'
                         r'|review given up|review refused|review failed|CI failure sent|findings sent|merge queued'
                         r'|merge blocked|look)(?: ([0-9a-f]{40}))?')
ROLLUP = {'SUCCESS': 'success', 'FAILURE': 'failure', 'ERROR': 'failure', 'PENDING': 'pending', 'EXPECTED': 'pending'}
FAILED = ('FAILURE', 'TIMED_OUT', 'STARTUP_FAILURE')
NEVER_KNOWN = ('stage_waits', 'stalls', 'journeys')
HISTORY = {'stalls': 'Historical completeness is unknown: edited or deleted records have no recoverable history.',
           'journeys': 'Journey v1 history is unknown.',
           'stage_waits': "TL2's history is unknown: only records GitHub still shows count."}
NO_LINK = ('Billing and usage have no GitHub source link: the billing summary and the owner-supplied export '
           'are named by hash only.')


class Refused(Exception):
    """A privacy hit: the whole read is refused."""


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def when(text):
    suite.require(type(text) is str and UTC.fullmatch(text) is not None, 'invalid UTC time')
    return datetime.strptime(text, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)


def iso(value):
    return value.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def written(value):
    """The bytes journey.py writes for a document: what a carried fact's source hashes."""
    return (json.dumps(value, indent=2) + '\n').encode()


def source(path, schema, data):
    return {'path': path, 'schema': schema, 'sha256': hashlib.sha256(data).hexdigest()}


def unavailable(name, reason, read=None, window=None):
    return {'fact': name, 'state': 'unavailable', 'read': read, 'point': None, 'window': window, 'fresh_until': None,
            'freshness': 'unknown', 'source': None, 'evidence': [], 'prerequisites': [reason], 'value': None}


class Read:
    """One on-demand read: its window, its clock, and the PR inventory its facts share."""

    def __init__(self, repo, since, until, clock, usage, robots, tickets, base, checks):
        self.repo, self.since, self.until, self.clock = repo, since, until, clock
        self.usage, self.robots, self.tickets, self.base, self.checks = usage, robots, tickets, base, checks
        self.web = 'https://github.com/' + repo
        self._prs = None

    def window(self):
        return {'since': iso(self.since), 'until': iso(self.until), 'timezone': 'UTC'}

    def fact(self, name, state, started, *, point=None, window=None, src=None, evidence=(), prerequisites=(),
             value=None):
        return {'fact': name, 'state': state, 'read': {'started_at': started, 'ended_at': self.clock()},
                'point': point, 'window': window, 'fresh_until': None, 'freshness': 'unknown', 'source': src,
                'evidence': list(dict.fromkeys(evidence)), 'prerequisites': list(prerequisites), 'value': value}

    def prs(self):
        """Every PR: merge, closure, base and same-repository closing tickets (metrics.collect_prs, plus base)."""
        if self._prs is not None:
            return self._prs
        prs, cursor, cursors = {}, None, set()
        while True:
            nodes, following = M.connection(M.graphql(self.repo, INVENTORY, cursor).get('pullRequests'))
            for node in nodes:
                pr = M.obj(node)
                n = M.integer(pr.get('number'))
                M.require(n not in prs, 'duplicate PR')
                M.require('mergedAt' in pr and 'closedAt' in pr, 'missing merge/closure timestamp')
                base = pr.get('baseRefName')
                M.require(type(base) is str and bool(base), 'invalid base branch')
                links, link_cursor = M.connection(pr.get('closingIssuesReferences'))
                seen, link_cursors, tickets = set(), set(), []
                while True:
                    for value in links:
                        issue = M.obj(value)
                        t = M.integer(issue.get('number'))
                        owner = M.obj(issue.get('repository')).get('nameWithOwner')
                        M.require(type(owner) is str and (owner.lower(), t) not in seen, 'invalid or duplicate linked issue')
                        seen.add((owner.lower(), t))
                        if owner.lower() == self.repo.lower():
                            tickets.append(t)
                    if link_cursor is None:
                        break
                    M.require(link_cursor not in link_cursors, 'repeated link cursor')
                    link_cursors.add(link_cursor)
                    links, link_cursor = M.connection(M.obj(M.graph(self.repo, link_cursor, n).get('pullRequest'))
                                                      .get('closingIssuesReferences'))
                prs[n] = {'merged': None if pr['mergedAt'] is None else M.timestamp(pr['mergedAt']),
                          'closed': None if pr['closedAt'] is None else M.timestamp(pr['closedAt']),
                          'tickets': sorted(tickets), 'base': base}
            if following is None:
                break
            M.require(following not in cursors, 'repeated PR cursor')
            cursors.add(following)
            cursor = following
        self._prs = prs
        return prs

    def merged(self):
        return {n: p for n, p in sorted(self.prs().items())
                if p['merged'] is not None and self.since <= p['merged'] < self.until}


# --- The facts ---------------------------------------------------------------

def merges(r, started):
    merged = r.merged()
    directions = {d['number']: d['direction'] for d in M.activity_directions(r.repo, merged, read=M.graphql)}
    value = {'pull_requests': [{'number': n, 'merged_at': M.iso(p['merged']), 'base': p['base'], 'tickets': p['tickets'],
                                'direction': directions[n] or 'unknown'} for n, p in merged.items()]}
    return r.fact('merges', 'known', started, window=r.window(), value=value,
                  src=source('collector/factory/merges.json', 'github.graphql.pullRequests', canonical(value)),
                  evidence=['%s/pull/%d' % (r.web, n) for n in merged])


def whole_hours(r):
    return r.since.minute == r.since.second == r.until.minute == r.until.second == 0


def gaps(since, until, prs, records):
    """factory-metrics' gap rules (its README, "What the numbers mean") over [since, until) in whole UTC hours."""
    hours = [[since + timedelta(hours=h), 0.0] for h in range(int((until - since).total_seconds()) // 3600)]
    ticket_merges = {}
    for pr in prs.values():
        if pr['merged'] is not None:
            for t in pr['tickets']:
                ticket_merges[t] = min(ticket_merges.get(t, pr['merged']), pr['merged'])
    # Backwards, so each start finds the next record on any of its targets; a shared start counts once.
    next_at, stalls, links, total = {}, [], [], 0.0
    for rec in reversed(records):
        ends = [next_at[t] for t in rec['targets'] if t in next_at]
        if rec['pr'] is not None:
            ends.extend(at for at in (prs[rec['pr']]['merged'], prs[rec['pr']]['closed']) if at is not None)
        else:
            ends.extend(ticket_merges[t] for t in rec['tickets'] if t in ticket_merges)
        following = min(ends, default=until)
        if rec['kind'] and rec['at'] < until:
            a, b = max(since, rec['at']), min(until, following)
            if b > a:
                seconds = (b - a).total_seconds()
                total += seconds
                stalls.append({'tickets': rec['tickets'], 'pull_request': rec['pr'], 'kind': rec['kind'],
                               'from': M.iso(a), 'until': M.iso(b), 'minutes': round(seconds / 60, 6),
                               'open_at_end': not ends or following > until})
                where = 'pull/%d' % rec['pr'] if rec['pr'] is not None else 'issues/%d' % rec['tickets'][0]
                links.append((M.iso(a), '%s#issuecomment-%d' % (where, rec['id'])))
                for hour in hours:
                    hour[1] += max(0, (min(b, hour[0] + timedelta(hours=1)) - max(a, hour[0])).total_seconds()) / 60
        for t in rec['targets']:
            next_at[t] = rec['at']
    stalls.sort(key=lambda s: (-s['minutes'], s['from'], s['tickets']))
    return (round(total / 60, 6), [{'start': M.iso(h), 'idle_minutes': round(m, 6)} for h, m in hours], stalls,
            [link for _, link in sorted(links)])


def stalls(r, started):
    if not whole_hours(r):
        return unavailable('stalls', 'Stalls need a window of whole UTC hours: idle minutes are split by hour.',
                           window=r.window())
    prs = r.prs()
    records, edited, skewed = M.collect_records(r.repo, prs)
    idle, hours, found, links = gaps(r.since, r.until, prs, records)
    unlinked = {n for n, p in r.merged().items() if not p['tickets']}
    unlinked |= {s['pull_request'] for s in found if s['pull_request'] is not None and not s['tickets']}
    value = {'idle_minutes': idle, 'hours': hours, 'stalls': found, 'unlinked_prs': sorted(unlinked),
             'edited_fleet_comments': edited, 'clock_skew_comments': skewed}
    return r.fact('stalls', 'partial', started, window=r.window(), value=value, prerequisites=[HISTORY['stalls']],
                  src=source('collector/factory/stalls.json', 'github.rest.issues.comments', canonical(value)),
                  evidence=['%s/%s' % (r.web, link) for link in links])


def cost(r, started):
    if not (r.since.hour == r.since.minute == r.since.second == 0 and r.until - r.since == timedelta(days=1)):
        return unavailable('cost', 'Cost is read for one whole UTC day: billing and usage are daily.',
                           window=r.window())
    date = r.since.strftime('%Y-%m-%d')
    actions = M.actions_costs(r.repo, r.since, 0)
    try:
        M.read_usage(r.usage, date)
        complete, reason = True, 'Complete daily owner-supplied export'
    except M.ReadError as error:
        complete, reason = False, str(error)
    cloud = M.cloud_costs(r.usage, date, 0)

    def total(provider, unit):
        value = cloud[provider][unit]['total']
        return int(value) if unit == 'tokens' and value is not None else value
    usage = {'complete': complete, 'reason': reason,
             **{p: {u: total(p, u) for u in M.USAGE_UNITS[p]} for p in ('claude', 'gpt', 'sandbox')}}
    value = {'date': date, 'actions_billing': {'minutes': actions['minutes']['total'], 'usd': actions['usd']['total'],
                                               'reason': actions['reason']}, 'usage': usage}
    gaps_ = [NO_LINK]
    if value['actions_billing']['usd'] is None:
        gaps_.append('Actions billing unknown: ' + actions['reason'])
    if not complete:
        gaps_.append('CloudRoom usage unknown: ' + reason)
    return r.fact('cost', 'partial', started, window=r.window(), value=value, prerequisites=gaps_,
                  src=source('collector/factory/cost.json', 'closedwiz.factory-metrics.costs.v1', canonical(value)))


def record_of(line):
    """The latest fleet record's kind and head, as the stall alarm accepts it; anything else refuses the read."""
    M.require(A.PR_RECORD.match(line) is not None, 'unknown fleet record')
    found = RECORD_KIND.match(line)
    M.require(found is not None, 'unknown fleet record')
    return found[1], found[2]


def check_result(context):
    kind = context.get('__typename')
    if kind == 'CheckRun':
        name, status, conclusion = context.get('name'), context.get('status'), context.get('conclusion')
        M.require(type(name) is str and type(status) is str and (conclusion is None or type(conclusion) is str),
                  'invalid check run')
        result = ('pending' if status != 'COMPLETED' else 'success' if conclusion == 'SUCCESS'
                  else 'failure' if conclusion in FAILED else 'other')
    elif kind == 'StatusContext':
        name, state = context.get('context'), context.get('state')
        M.require(type(name) is str and type(state) is str, 'invalid status context')
        result = ROLLUP.get(state, 'other')
    else:
        raise M.ReadError('unknown check kind')
    return {'name': name, 'result': result}


def pull_of(node):
    pull = M.obj(node)
    number, draft, base, head = pull.get('number'), pull.get('isDraft'), pull.get('baseRefName'), pull.get('headRefOid')
    M.require(type(number) is int and number > 0 and type(draft) is bool and type(base) is str and bool(base) and
              type(head) is str and SHA.fullmatch(head) is not None and
              pull.get('mergeable') in ('MERGEABLE', 'CONFLICTING', 'UNKNOWN'), 'invalid open PR')
    comments = M.obj(pull.get('comments'))
    M.require(M.obj(comments.get('pageInfo')).get('hasPreviousPage') is False, 'more than 100 comments on a PR')
    records, verdicts, seen = [], [], set()
    for value in M.array(comments.get('nodes')):
        c = M.obj(value)
        cid, body = c.get('databaseId'), c.get('body')
        M.require(type(cid) is int and cid > 0 and cid not in seen and type(body) is str, 'invalid PR comment')
        seen.add(cid)
        created, edited = M.timestamp(c.get('createdAt')), M.timestamp(c.get('updatedAt'))
        M.require(edited >= created, 'a comment edited before it was created')
        line = next((part.strip() for part in body.splitlines() if part.strip()), '')
        if line.startswith('launch-fleet:'):
            kind, sha = record_of(line)
            records.append((edited, cid, {'kind': kind, 'head': sha, 'comment_id': cid, 'at': M.iso(edited)}))
        if body.startswith('VERDICT: '):
            word = re.match(r'VERDICT: (APPROVE|CHANGES)\b', line)
            at = re.search(r'\bat ([0-9a-f]{40})\b', line)
            verdicts.append((cid, {'verdict': word[1] if word else 'other', 'head': at[1] if at else None,
                                   'comment_id': cid, 'at': M.iso(edited)}))
    commits = M.array(M.obj(pull.get('commits')).get('nodes'))
    M.require(len(commits) == 1, 'invalid head commit')
    commit = M.obj(M.obj(commits[0]).get('commit'))
    M.require(commit.get('oid') == head, 'the head moved during the read')
    M.require('statusCheckRollup' in commit, 'missing status rollup')
    rollup, checks = commit['statusCheckRollup'], []
    if rollup is not None:
        rollup = M.obj(rollup)
        M.require(rollup.get('state') in ROLLUP, 'invalid status rollup')
        contexts = M.obj(rollup.get('contexts'))
        M.require(M.obj(contexts.get('pageInfo')).get('hasNextPage') is False, 'more than 100 checks on a PR')
        checks = [check_result(M.obj(c)) for c in M.array(contexts.get('nodes'))]
        rollup = ROLLUP[rollup['state']]
    return {'number': number, 'draft': draft, 'base': base, 'head': head, 'mergeable': pull['mergeable'],
            'rollup': rollup, 'checks': checks, 'verdict': max(verdicts, key=lambda v: v[0])[1] if verdicts else None,
            'record': max(records, key=lambda v: (v[0], v[1]))[2] if records else None}


def open_prs(r, started):
    pulls, default, cursor, cursors = {}, None, None, set()
    while True:
        repo = M.graphql(r.repo, OPEN, cursor)
        name = M.obj(repo.get('defaultBranchRef')).get('name')
        M.require(type(name) is str and bool(name) and default in (None, name), 'invalid default branch')
        default = name
        nodes, following = M.connection(repo.get('pullRequests'))
        for node in nodes:
            pull = pull_of(node)
            M.require(pull['number'] not in pulls, 'duplicate open PR')
            pulls[pull['number']] = pull
        if following is None:
            break
        M.require(following not in cursors, 'repeated open-PR cursor')
        cursors.add(following)
        cursor = following
    value = {'default_branch': default, 'base': r.base or default, 'checks': list(r.checks),
             'pull_requests': [pulls[n] for n in sorted(pulls)]}
    ended = r.clock()
    return dict(r.fact('open_prs', 'known', started, point=ended, value=value,
                       src=source('collector/factory/open-prs.json', 'github.graphql.pullRequests', canonical(value)),
                       evidence=['%s/pull/%d' % (r.web, n) for n in sorted(pulls)]),
                read={'started_at': started, 'ended_at': ended})


def journeys(r, started):
    merged = r.merged()
    tickets = sorted({t for p in merged.values() for t in p['tickets']})
    if not tickets:
        return unavailable('journeys', 'No PR merged in the window closes a ticket of this repository.',
                           read={'started_at': started, 'ended_at': r.clock()}, window=r.window())
    doc = J.collect(r.repo, tickets, [])
    data = written(doc)
    document = suite._decode(data.decode())
    J.validate(document)
    value = {'cohort': {'window': r.window(), 'pull_requests': list(merged)}, 'document': document, 'outcomes': None}
    return r.fact('journeys', 'partial', started, window=r.window(), value=value, prerequisites=[HISTORY['journeys']],
                  src=source('collector/factory/journeys.json', 'closedwiz.journey.v1', data),
                  evidence=['%s/pull/%d' % (r.web, n) for n in merged])


def stage_waits(r, started):
    if not r.tickets:
        return unavailable('stage_waits', "Stage waits need the tickets to read: the board graph's open approved "
                                          'tickets and the merged cohort\'s (--ticket).')
    read_at, sidecar = r.clock(), {}
    doc = J.collect(r.repo, sorted(r.tickets), [], stage_export=sidecar, read_at=read_at)
    journey, side = suite._decode(written(doc).decode()), written(sidecar)
    sidecar = suite._decode(side.decode())
    J.validate_stage_waits(sidecar, journey)
    raw = (ROOT / LIMITS).read_bytes()
    settings, limits_at = J.limits_module().read(ROOT / LIMITS), r.clock()
    bench = suite._decode(json.dumps(J.stage_bench(sidecar, settings), default=float))
    value = {'journey': journey, 'sidecar': sidecar, 'bench': bench,
             'limits': {'schema': settings['schema'], 'path': LIMITS, 'sha256': hashlib.sha256(raw).hexdigest(),
                        'read_at': limits_at}}
    return r.fact('stage_waits', 'partial', started, point=read_at, value=value, prerequisites=[HISTORY['stage_waits']],
                  src=source('collector/factory/stage-waits.json', J.STAGE_SCHEMA, side),
                  evidence=['%s/issues/%d' % (r.web, t) for t in sorted(r.tickets)])


def prs_per_hour(r, started):
    """ci-bench's headline, exactly as `bench.py collect` and `measure` produce it, for this repository."""
    before = os.environ.get('GH_REPO')
    os.environ['GH_REPO'] = r.repo  # gh fills bench_measure's {owner}/{repo} from GH_REPO
    with tempfile.TemporaryDirectory(prefix='collect-factory-') as tmp:
        out = Path(tmp) / 'window'
        out.mkdir()
        try:
            for step, run in (('collect', lambda: B.collect(iso(r.since), iso(r.until), str(out))),
                              ('measure', lambda: B.measure(str(out), r.robots, 'collector', allow_empty=True,
                                                            allow_timing_gaps=True))):
                try:
                    with contextlib.redirect_stdout(io.StringIO()):
                        run()
                except (B.Fail, OSError, ValueError, TypeError, KeyError) as error:
                    # Never copy the bench's error text: it can carry an upstream answer.
                    raise M.ReadError('ci-bench %s failed' % step) from error
        finally:
            if before is None:
                os.environ.pop('GH_REPO', None)
            else:
                os.environ['GH_REPO'] = before
        raw = (out / 'point.json').read_bytes()
        runs = sorted({json.loads(line)['run'] for line in (out / 'jobs.jsonl').read_text().splitlines() if line})
        numbers = [p['number'] for p in json.loads((out / 'merged.json').read_text())]
    point = suite._decode(raw.decode())
    code = point['code_runs']
    value = {'robots': point['robots'], 'code_runs': code['runs'] if code else 0,
             'robot_minutes_per_code_run': code['robot_minutes_per_run'] if code else None,
             'capacity_prs_per_hour': code['prs_per_hour'] if code else None,
             'merged_prs': point['merged_prs'], 'merged_per_hour': point['merged_per_hour'], 'baseline': None}
    gap = [] if code else ['No successful code run in the window: capacity is unknown, never zero.']
    return r.fact('prs_per_hour', 'partial' if gap else 'known', started, window=r.window(), value=value,
                  prerequisites=gap, src=source('collector/factory/prs-per-hour.json', point['schema'], raw),
                  evidence=['%s/actions/runs/%d' % (r.web, n) for n in runs] + ['%s/pull/%d' % (r.web, n) for n in numbers])


READERS = {'merges': merges, 'prs_per_hour': prs_per_hour, 'stage_waits': stage_waits, 'stalls': stalls,
           'open_prs': open_prs, 'journeys': journeys, 'cost': cost}
UNREADABLE = {
    'merges': 'Merges unavailable: the PR inventory or its closing tickets could not be read completely '
              '(read-only gh access to pull requests and issues).',
    'prs_per_hour': "PRs an hour unavailable: ci-bench's collect or measure of ci.yml's runs failed "
                    '(read-only gh access to Actions runs and pull requests).',
    'stage_waits': "Stage waits unavailable: journey.py's stage collection or TL1's limits read was refused.",
    'stalls': 'Stalls unavailable: the PR inventory or every page of issue comments could not be read.',
    'open_prs': "Open PRs unavailable: the open-PR read failed, was truncated (over 100 comments or checks), or held "
                'an unknown fleet record.',
    'journeys': "Journeys unavailable: journey.py collect over the window's merged cohort failed.",
    'cost': 'Cost unavailable: the read failed.',
}


def window(since, until, requested):
    """The read's window as (since, until) UTC text: both given, or neither for the last whole UTC day
    before REQUESTED. Raise ValueError for half a window or one that ends after REQUESTED. The one
    decision gather.snapshot and read both use, so the factory and CI groups get the same bounds."""
    suite.require((since is None) == (until is None), 'since and until go together')
    if since is None:
        end = when(requested).replace(hour=0, minute=0, second=0)
        since, until = iso(end - timedelta(days=1)), iso(end)
    suite.require(when(since) < when(until) <= when(requested), 'the window must end by the read')
    return since, until


def read(repository, facts, *, since=None, until=None, usage=None, robots=ROBOTS, tickets=None, base=None,
         checks=('ci',), clock=now):
    """One on-demand read envelope of FACTS (collector.v1.md, "The on-demand read")."""
    suite.require(type(repository) is str and REPO.fullmatch(repository) is not None, 'invalid repository')
    facts = list(facts)
    suite.require(facts and len(set(facts)) == len(facts) and set(facts) <= set(FACTS), 'invalid facts')
    suite.require(type(robots) is int and robots >= 1, 'invalid robots')
    requested = clock()
    since, until = (when(t) for t in window(since, until, requested))
    r = Read(repository, since, until, clock, None if usage is None else Path(usage), robots, tickets, base, tuple(checks))
    out = {}
    for name in FACTS:
        if name not in facts:
            continue
        started = clock()
        try:
            out[name] = READERS[name](r, started)
            validate(out[name])
        except (M.ReadError, OSError, ValueError, TypeError, KeyError, IndexError, AttributeError,
                subprocess.TimeoutExpired):
            # Only a fixed reason: a source's error text can carry a private value.
            out[name] = unavailable(name, UNREADABLE[name], read={'started_at': started, 'ended_at': clock()},
                                    window=None if name in ('open_prs', 'stage_waits') else r.window())
    doc = {'schema': READ, 'repository': repository, 'requested_at': requested, 'factory': out, 'ci': {}}
    scan(doc)
    return doc


def scan(doc):
    """The war room's privacy scan (gather.scan_bytes) over the whole document; a hit refuses it all."""
    try:
        collector_runtime.scan_bytes(json.dumps(doc, sort_keys=True).encode())
    except collector_runtime.Fail:
        raise Refused('the privacy scan refused the read')


# --- The contract's cross-field rules, for one factory fact ------------------

def validate(fact):
    """Raise ValueError unless FACT keeps collector.v1.md's rules for its kind."""
    require = suite.require
    require(type(fact) is dict and fact.get('fact') in FACTS, 'not a factory fact')
    name = fact['fact']
    suite._shape(fact, SCHEMA['$defs']['fact_' + name], SCHEMA)
    state, value, gaps_, read_ = fact['state'], fact['value'], fact['prerequisites'], fact['read']
    if state == 'known':
        require(value is not None and not gaps_ and read_ is not None and fact['source'] is not None and
                (fact['point'] or fact['window']), 'a known fact needs a value, a read, a source and a time')
        nothing = name in ('merges', 'open_prs') and not value['pull_requests']
        require(fact['evidence'] or nothing, 'a known fact needs evidence links')
        require(name not in NEVER_KNOWN, '%s is never known: its history is unknown' % name)
    elif state == 'partial':
        require(value is not None and gaps_, 'a partial fact needs a value and prerequisites')
    else:
        require(value is None and gaps_, 'an unavailable fact has no value and names its prerequisites')
    require(not (fact['point'] and fact['window']), 'a point or a window, never both')
    window = fact['window'] and (when(fact['window']['since']), when(fact['window']['until']))
    require(window is None or window[0] < window[1], 'a window ends after it starts')
    if read_ is not None:
        lo, hi = when(read_['started_at']), when(read_['ended_at'])
        require(lo <= hi, 'a read ends after it starts')
        require(fact['point'] is None or lo <= when(fact['point']) <= hi, 'a point lies inside its read')
        require(window is None or window[1] <= hi, 'a window ends by its read')
    if value is None:
        return
    if name == 'merges':
        numbers = [p['number'] for p in value['pull_requests']]
        require(len(set(numbers)) == len(numbers), 'a PR merged twice')
        require(window is not None and all(window[0] <= when(p['merged_at']) < window[1] for p in value['pull_requests']),
                'every merge lies in the window')
    elif name == 'stalls':
        require(window is not None and len(value['hours']) == (window[1] - window[0]).total_seconds() // 3600 and
                [h['start'] for h in value['hours']] ==
                [iso(window[0] + timedelta(hours=h)) for h in range(len(value['hours']))], 'one row per hour')
        require(abs(sum(h['idle_minutes'] for h in value['hours']) - value['idle_minutes']) < 1e-3, 'hours sum')
        require(all(window[0] <= when(s['from']) < when(s['until']) <= window[1] for s in value['stalls']),
                'every stall lies in the window')
    elif name == 'cost':
        require(window is not None and window[1] - window[0] == timedelta(days=1) and
                iso(window[0]) == value['date'] + 'T00:00:00Z', 'cost is one UTC day')
    elif name == 'open_prs':
        numbers = [p['number'] for p in value['pull_requests']]
        require(len(set(numbers)) == len(numbers), 'a PR listed twice')
        require(all(p['checks'] == [] for p in value['pull_requests'] if p['rollup'] is None),
                'a null rollup has no checks')
    elif name == 'journeys':
        require(value['cohort']['window'] == fact['window'], 'the cohort is the window')
    elif name == 'stage_waits':
        require(type(value['sidecar']) is dict and fact['point'] == value['sidecar'].get('read_at'),
                "the point is TL2's read time")
        require(when(value['limits']['read_at']) >= when(fact['point']), 'limits read at or after TL2')
    elif name == 'prs_per_hour':
        require((value['robot_minutes_per_code_run'] is None) == (value['capacity_prs_per_hour'] is None),
                'capacity needs robot-minutes')


# --- CLI ---------------------------------------------------------------------

def main(argv):
    def utc(text):
        try:
            when(text)
        except ValueError:
            raise argparse.ArgumentTypeError('expected YYYY-MM-DDTHH:MM:SSZ')
        return text

    def repo(text):
        if not REPO.fullmatch(text):
            raise argparse.ArgumentTypeError('expected OWNER/NAME')
        return text

    def positive(text):
        if not re.fullmatch(r'[1-9][0-9]{0,5}', text):
            raise argparse.ArgumentTypeError('expected a positive integer')
        return int(text)

    parser = argparse.ArgumentParser(description="The war room collector's factory facts (MT2). Reads only.")
    sub = parser.add_subparsers(dest='command', required=True)
    r = sub.add_parser('read', help='print one on-demand read envelope')
    r.add_argument('--repo', type=repo, required=True, help='OWNER/NAME')
    r.add_argument('--fact', action='append', choices=FACTS, required=True, help='a factory fact (repeat)')
    r.add_argument('--since', type=utc, help='window start, UTC (with --until; default: the last whole UTC day)')
    r.add_argument('--until', type=utc, help='window end, UTC, exclusive')
    r.add_argument('--usage', type=Path, help="factory-metrics' daily CloudRoom usage export, for cost")
    r.add_argument('--robots', type=positive, default=ROBOTS, help='capacity assumption for prs_per_hour (default 5)')
    r.add_argument('--ticket', type=positive, action='append', help='a ticket whose stage waits are read (repeat)')
    r.add_argument('--base', help="the base open_prs judges (default: the repository's default branch)")
    r.add_argument('--check', action='append', help='a required check open_prs judges (repeat; default: ci)')
    r.add_argument('--now', type=utc, help='a fixed clock, for fixture proofs')
    a = parser.parse_args(argv)
    if len(set(a.fact)) != len(a.fact):
        parser.error('a fact is named twice')
    if (a.since is None) != (a.until is None):
        parser.error('--since and --until go together')
    if a.since is not None and not when(a.since) < when(a.until):
        parser.error('--until must be after --since')
    if a.ticket and len(set(a.ticket)) != len(a.ticket):
        parser.error('a ticket is named twice')
    if a.base is not None and not re.fullmatch(r'[A-Za-z0-9_./-]+', a.base):
        parser.error('invalid --base')
    clock = (lambda: a.now) if a.now else now
    try:
        doc = read(a.repo, a.fact, since=a.since, until=a.until, usage=a.usage, robots=a.robots, tickets=a.ticket,
                   base=a.base, checks=tuple(a.check or ['ci']), clock=clock)
    except Refused as error:
        print('collect_factory: %s; nothing printed' % error, file=sys.stderr)
        return 1
    except ValueError as error:  # the arguments, refused before any read
        print('collect_factory: %s' % error, file=sys.stderr)
        return 2
    print(json.dumps(doc, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
