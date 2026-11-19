#!/usr/bin/env python3
"""MT2 (#821): the war room collector's factory facts (collector.v1.md). Reads only.

  python3 -I tools/collector/collect_factory.py read --repo OWNER/NAME --fact NAME [--fact NAME ...]
      [--since UTC --until UTC] [--usage FILE] [--robots N] [--ticket N ...] [--base NAME] [--check NAME ...]
      [--now UTC]

Prints one `openwiz.war-room.collector.read.v1` envelope holding the named
factory facts, read now: merges, prs_per_hour, stage_waits, stalls, open_prs,
journeys, cost and flow. Without --since/--until the window is the last complete UTC
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
from decimal import Decimal
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
from urllib.parse import quote

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

    def __init__(self, repo, since, until, clock, usage, robots, tickets, base, checks, specs, flow_threads, flow_usage):
        self.repo, self.since, self.until, self.clock = repo, since, until, clock
        self.usage, self.robots, self.tickets, self.base, self.checks = usage, robots, tickets, base, checks
        self.specs, self.flow_threads, self.flow_usage = specs, flow_threads, flow_usage
        self.web = 'https://github.com/' + repo
        self._prs = None

    def window(self):
        return {'since': iso(self.since), 'until': iso(self.until), 'timezone': 'UTC'}

    def fact(self, name, state, started, *, point=None, window=None, src=None, evidence=(), prerequisites=(),
             value=None):
        return {'fact': name, 'state': state, 'read': {'started_at': started, 'ended_at': self.clock()},
                'point': point, 'window': window, 'fresh_until': None, 'freshness': 'unknown', 'source': src,
                'evidence': list(dict.fromkeys(evidence)), 'prerequisites': list(prerequisites), 'value': value}

    def pull_links(self, pr, n):
        """The same complete forward links for inventory and one-ticket reads."""
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
        return {'merged': None if pr['mergedAt'] is None else M.timestamp(pr['mergedAt']),
                  'closed': None if pr['closedAt'] is None else M.timestamp(pr['closedAt']),
                  'tickets': sorted(tickets), 'base': base}

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
                prs[n] = self.pull_links(pr, n)
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


# --- FM2: ticket and spec facts ----------------------------------------------

FLOW_ISSUE = J.ISSUE.replace('updatedAt body', 'updatedAt body author{login}')
FLOW_PULL = J.PULL.replace('updatedAt body', 'updatedAt body author{login} id')
FLOW_COMMENT_HISTORY = ('query($id:ID!){node(id:$id){...on IssueComment{id createdAt updatedAt '
                        'userContentEdits(first:100){totalCount pageInfo{hasNextPage} '
                        'nodes{editedAt deletedAt diff}}}}}')
FLOW_SPEC = ('query($owner:String!,$name:String!,$number:Int!,$cursor:String)'
             '{repository(owner:$owner,name:$name){issue(number:$number){number createdAt '
             'subIssues(first:100,after:$cursor){nodes{number repository{nameWithOwner}} '
             'pageInfo{hasNextPage endCursor}}}}}')
FLOW_TICKET_PRS = ('query($owner:String!,$name:String!,$number:Int!,$cursor:String)'
                   '{repository(owner:$owner,name:$name){issue(number:$number){number '
                   'closedByPullRequestsReferences(first:100,after:$cursor,includeClosedPrs:true)'
                   '{nodes{number repository{nameWithOwner} baseRefName mergedAt closedAt '
                   'closingIssuesReferences(first:100){nodes{number repository{nameWithOwner}} '
                   'pageInfo{hasNextPage endCursor}}} pageInfo{hasNextPage endCursor}}}}}')
FLOW_REVIEW_START = re.compile(r'launch-fleet: (?:review started|re-check sent) ([0-9a-f]{40})')
FLOW_QUEUE = re.compile(r'launch-fleet: merge queued ([0-9a-f]{40}): .+')
FLOW_PUSH = re.compile(r'First successful push: [0-9a-f]{40} at (\S+)')
FLOW_STAGES = ('waiting_to_start', 'building', 'in_review', 'in_queue')
FLOW_ROLES = ('builder', 'reviewer')
FLOW_UNITS = ('credits', 'tokens')
FLOW_PREREQUISITES = {
    'scope': 'Complete ticket or spec membership could not be established.',
    'github': 'Some GitHub timing or review records were unavailable or could not be paired.',
    'usage': 'Some role-attributed, complete daily token or credit readings were missing.',
    'ci': 'Some PR jobs or attempt attribution could not be established.',
    'progress': 'Some progress sources or their timing were unavailable.',
    'stalls': 'Complete per-ticket stall observations are unavailable.',
}


def flow_read(fn, *args):
    """Keep a failed source local to the fields it can prove."""
    try:
        return fn(*args)
    except (M.ReadError, B.Fail, OSError, ValueError, TypeError, KeyError):
        return None


def flow_authors():
    setting = (ROOT / 'docs/agents/fleet.md').read_text(encoding='utf-8')
    rows = re.findall(r'^\| Record authors \| (.+) \|$', setting, re.M)
    atom = r'`([A-Za-z0-9-]+(?:\[bot\])?)`'
    M.require(len(rows) == 1 and re.fullmatch(atom + r'(?:, ' + atom + ')*', rows[0]), 'invalid record authors')
    return {login.casefold() for login in re.findall(atom, rows[0])}


def flow_subject(c, query, kind, n, authors):
    top, nodes = c.pages(query, n, (kind, 'comments'), lambda row: M.integer(row.get('databaseId')))
    M.require(top.get('number') == n, 'an answer for another subject')
    nodes = [row for row in nodes if row.get('author') is not None
             and J.text(M.obj(row['author']).get('login')).casefold() in authors]
    comments = c.comments(nodes)
    if kind == 'pullRequest':
        for comment, node in zip(comments, nodes):
            comment['node_id'] = node.get('id')
    return top, comments


def flow_members(c, n):
    top, nodes = c.pages(FLOW_SPEC, n, ('issue', 'subIssues'), lambda row: (
        J.text(M.obj(row.get('repository')).get('nameWithOwner')).casefold(), M.integer(row.get('number'))))
    M.require(top.get('number') == n, 'an answer for another spec')
    created = J.when(top.get('createdAt'))
    local = sorted(row['number'] for row in nodes
                   if row['repository']['nameWithOwner'].casefold() == c.repo.casefold())
    return created, local if len(local) == len(nodes) else None


def flow_linked_pulls(r, c, n):
    def identity(pr):
        return J.text(M.obj(pr.get('repository')).get('nameWithOwner')).casefold(), M.integer(pr.get('number'))

    top, nodes = c.pages(FLOW_TICKET_PRS, n, ('issue', 'closedByPullRequestsReferences'), identity)
    M.require(top.get('number') == n, 'links for another ticket')
    pulls = {}
    for pr in nodes:
        repo, number = identity(pr)
        M.require(repo == r.repo.casefold(), 'cross-repository closing PR')
        data = r.pull_links(pr, number)
        M.require(n in data['tickets'], 'reverse and forward PR links disagree')
        pulls[number] = data
    return pulls


def flow_totals(values):
    values = list(values)
    return sum(values) if values and all(value is not None for value in values) else None


def flow_seconds(start, end):
    return int((when(end) - when(start)).total_seconds()) if start and end and start <= end else None


def flow_usage(repo, manifest, paths):
    """Private role attribution plus the existing complete UTC-day usage exports."""
    if manifest is None or not paths:
        return {}, {}
    bindings = M.obj(M.load(Path(manifest).read_text(encoding='utf-8')))
    M.exact(bindings, ('repository', 'tickets'))
    M.require(J.text(bindings['repository']).casefold() == repo.casefold(), 'another usage repository')
    groups = M.obj(bindings['tickets'])
    seen = set()
    for ticket, roles in groups.items():
        M.require(re.fullmatch(r'[1-9][0-9]*', ticket), 'invalid usage ticket')
        M.exact(M.obj(roles), FLOW_ROLES)
        for role in FLOW_ROLES:
            for thread in M.array(roles[role]):
                M.require(J.text(thread) and thread not in seen, 'missing or ambiguous thread assignment')
                seen.add(thread)
    daily = {}
    for path in paths:
        data = flow_read(M.read_usage, Path(path))
        if data is None:
            continue
        day = data['date']
        M.require(day not in daily, 'ambiguous daily usage')
        rows = {}
        for provider in ('claude', 'gpt'):
            for row in data[provider]:
                M.require(row['thread'] not in rows, 'ambiguous daily thread')
                rows[row['thread']] = row
        daily[day] = rows
    return groups, daily


def flow_role_cost(data, ticket, claim, end):
    bindings, daily = data
    roles = bindings.get(str(ticket), {})
    days = []
    if claim and claim <= end:
        day, last = when(claim).date(), when(end).date()
        while day <= last:
            days.append(day.isoformat())
            day += timedelta(days=1)
    costs = {}
    for role in FLOW_ROLES:
        threads = roles.get(role) or []
        rows = [daily.get(day, {}).get(thread) for day in days for thread in threads]
        costs[role] = {unit: flow_totals(row[unit] if row is not None else None for row in rows)
                       for unit in FLOW_UNITS}
        if costs[role]['credits'] is not None:
            costs[role]['credits'] = J.number(costs[role]['credits'])
    return costs


def flow_attempt_jobs(repo, rid, attempt):
    path = f'repos/{repo}/actions/runs/{rid}/attempts/{attempt}/jobs?per_page={B.PAGE}'
    rows = B.pages(path, 'jobs', 'jobs', M.rest)
    owned, seen = [], set()
    for job, _ in rows:
        key = M.integer(M.obj(job).get('id'))
        origin = M.integer(job.get('run_attempt'))
        M.require(key not in seen and origin <= attempt, 'ambiguous job attempt')
        seen.add(key)
        if origin < attempt:
            continue  # Reused result from an earlier attempt, counted there.
        if (job.get('status') == 'completed' and job.get('conclusion') in ('skipped', 'cancelled')
                and job.get('steps') == [] and 'runner_name' in job and B.never_ran(job)):
            continue
        begin = J.when(J.field(job, 'started_at'), True)
        end = J.when(J.field(job, 'completed_at'), True)
        owned.append(flow_seconds(begin, end) if job.get('status') == 'completed' else None)
    return flow_totals(owned) if owned else (0 if rows else None)


def flow_attempt(repo, run, rid, attempt, latest):
    if attempt != latest:
        run = M.obj(M.rest(f'repos/{repo}/actions/runs/{rid}/attempts/{attempt}'))
        M.require(M.integer(run.get('id')) == rid and M.integer(run.get('run_attempt')) == attempt,
                  'a result for another attempt')
    status = run.get('status')
    M.require(status in ('completed', 'queued', 'in_progress', 'requested', 'waiting', 'pending'),
              'unknown run status')
    return status, J.when(run.get('updated_at')) if status == 'completed' else None


def flow_queue_runs(repo, workflow, n, base, entered, cutoff):
    path = (f'repos/{repo}/actions/workflows/{workflow}/runs?event=merge_group'
            f'&created={entered}..{cutoff}&per_page={B.PAGE}')
    branch = re.compile(rf'gh-readonly-queue/{re.escape(base)}/pr-{n}-[0-9a-f]{{40}}')
    matched = []
    for run, _ in B.pages(path, 'workflow_runs', 'merge groups', M.rest):
        M.require(M.obj(run).get('event') == 'merge_group', 'non-group run in group search')
        ref = J.text(run.get('head_branch'))
        if not branch.fullmatch(ref):
            continue
        J.commit(run.get('head_sha'))
        if entered <= J.when(run.get('created_at')) <= cutoff:
            matched.append(run)
    return matched


def flow_ci(repo, workflow, pull, base, queued, cutoff):
    n, branch, opened, closed = (pull[key] for key in ('number', 'headRefName', 'createdAt', 'closedAt'))
    path = (f'repos/{repo}/actions/workflows/{workflow}/runs?branch={quote(branch, safe="")}'
            f'&event=pull_request&per_page={B.PAGE}')
    rows = B.pages(path, 'workflow_runs', 'runs', M.rest)
    groups = flow_read(flow_queue_runs, repo, workflow, n, base, queued, cutoff) if queued else []
    group_gap = groups is None or (queued and pull['mergedAt'] == cutoff and not groups)
    matched = list(groups or [])
    for run, _ in rows:
        M.require(M.obj(run).get('head_branch') == branch and run.get('event') == 'pull_request',
                  'run for another branch or event')
        links = {M.integer(M.obj(link).get('number')) for link in M.array(run.get('pull_requests'))}
        created = J.when(run.get('created_at'))
        if created > cutoff or (links and n not in links):
            continue
        if not links:
            if created < opened or (closed is not None and created > closed):
                continue
            head_repo = M.obj(run.get('head_repository')).get('full_name')
            if J.text(head_repo).casefold() != repo.casefold():
                continue  # A same-named branch in a fork.
        M.require(not (links - {n}), 'run linked to multiple pull requests')
        matched.append(run)
    results, seconds, seen, active, complete = [], [], set(), False, not group_gap
    for run in matched:
        rid = M.integer(run.get('id'))
        M.require(rid not in seen, 'ambiguous PR run')
        seen.add(rid)
        created = J.when(run.get('created_at'))
        latest = M.integer(run.get('run_attempt'))
        for attempt in range(1, latest + 1):
            result = flow_read(flow_attempt, repo, run, rid, attempt, latest)
            if result is None:
                complete = False
            else:
                status, at = result
                complete &= (at is not None and at >= created) or (status != 'completed' and attempt == latest)
                if at is not None and created <= at <= cutoff:
                    results.append(at)
                if attempt == latest:
                    active |= status != 'completed' or (at is not None and at > cutoff)
            seconds.append(flow_read(flow_attempt_jobs, repo, rid, attempt))
    return {'seconds': None if group_gap else flow_totals(seconds), 'results': results,
            'complete': bool(seconds) and complete,
            'pending': active if seconds else None}


def flow_verdict_identity(body):
    line = J.first_line(body)
    if not line.startswith('VERDICT:'):
        return None
    independent = J.first_line(body, 1).startswith(('Full review by ', 'Re-check '))
    return line, independent


def flow_stable_verdict(comment):
    """Only complete revisions can establish that an edit preserved verdict identity."""
    node_id = J.text(comment['node_id'])
    M.require(bool(node_id), 'missing comment identity')
    doc = M.obj(M.gh('api', 'graphql', '-f', 'query=' + FLOW_COMMENT_HISTORY, '-f', 'id=' + node_id))
    M.require(not doc.get('errors'), 'comment history unavailable')
    node = M.obj(M.obj(doc.get('data')).get('node'))
    M.require((node.get('id'), node.get('createdAt'), node.get('updatedAt')) ==
              (node_id, comment['at'], comment['updated']), 'comment changed during the read')
    history = M.obj(node.get('userContentEdits'))
    edits = M.array(history.get('nodes'))
    M.require(M.obj(history.get('pageInfo')).get('hasNextPage') is False and
              M.integer(history.get('totalCount')) == len(edits), 'incomplete edit history')
    versions = {}
    for item in edits:
        edit = M.obj(item)
        at = J.when(edit.get('editedAt'))
        M.require(J.field(edit, 'deletedAt') is None and at not in versions and
                  comment['at'] <= at <= comment['updated'], 'unavailable or ambiguous edit')
        versions[at] = J.text(edit.get('diff'))
    # GitHub can record updatedAt after the last user-content edit.
    M.require(comment['at'] in versions and versions[max(versions)] == comment['body'],
              'missing original or current comment body')
    identity = flow_verdict_identity(comment['body'])
    return all(flow_verdict_identity(body) == identity for body in versions.values())


def flow_pr(c, n, base, authors, cutoff):
    top, comments = flow_subject(c, FLOW_PULL, 'pullRequest', n, authors)
    J.when(top.get('createdAt'))
    J.when(J.field(top, 'closedAt'), True)
    J.when(J.field(top, 'mergedAt'), True)
    head, branch = J.commit(top.get('headRefOid')), J.text(top.get('headRefName'))
    M.require(bool(branch), 'missing PR branch')
    if top['createdAt'] > cutoff:
        return None
    comments = [com for com in comments if com['at'] <= cutoff]
    supported = [com for com in comments if not com['edited'] or flow_read(flow_stable_verdict, com)]
    events, _ = J.pr_events(c, {'created': top['createdAt'], 'url': c.link(top.get('url')),
                               'comments': supported, 'merged': None}, [])
    verdicts = [e for e in events if J.rounds_of(e)]
    verdict_history = len(comments) == len(supported)
    records = [(J.first_line(com['body']), com['at'], com['updated'])
               for com in comments if J.first_line(com['body']).startswith('launch-fleet:')]
    pushes = [m[1] for com in comments if not com['edited'] and (m := FLOW_PUSH.fullmatch(J.first_line(com['body'])))
              and flow_read(when, m[1]) is not None and m[1] <= com['at']]
    tips = flow_read(J.head_windows, c, branch, head)
    pushes.extend(at for _, at, _ in tips or [] if at <= cutoff)
    queued = min((at for line, at, _ in records if FLOW_QUEUE.fullmatch(line)), default=None)
    ci = [flow_read(flow_ci, c.repo, workflow, top, base, queued, cutoff)
          for workflow in ('ci.yml', 'privacy.yml')]
    ci_seconds = flow_totals(item['seconds'] if item else None for item in ci)
    pending = [item['pending'] if item else None for item in ci]
    return {'number': n, 'head': head, 'verdicts': verdicts, 'verdict_history': verdict_history, 'records': records,
            'pushes': pushes, 'head_history': tips is not None,
            'ci_seconds': ci_seconds, 'ci_history': all(item and item['complete'] for item in ci),
            'ci_results': [at for item in ci if item for at in item['results']],
            'ci_pending': True if True in pending else False if pending == [False, False] else None}


def flow_stage_times(claim, ready, merge, pr):
    stages = dict.fromkeys(FLOW_STAGES)
    stages['waiting_to_start'] = flow_seconds(ready, claim)
    if claim is None or pr is None or not pr['verdict_history'] or not pr['verdicts']:
        return stages
    available = [(m[1], at, updated) for line, at, updated in pr['records']
                 if (m := FLOW_REVIEW_START.fullmatch(line))]
    build, review, start = [], [], claim
    for verdict in pr['verdicts']:
        ends = [(at, updated) for head, at, updated in available
                if head == verdict['head'] and start <= at <= updated <= verdict['at']]
        if not ends:
            return stages
        requested, review_at = min(ends)
        build.append(flow_seconds(start, requested))
        review.append(flow_seconds(review_at, verdict['at']))
        start = verdict['at']
    last = pr['verdicts'][-1]
    if last['verdict'] == 'APPROVE' and last['head'] == pr['head']:
        stages['building'], stages['in_review'] = flow_totals(build), flow_totals(review)
        queued = min((at for line, at, _ in pr['records'] if last['at'] <= at
                      and (m := FLOW_QUEUE.fullmatch(line)) and m[1] == last['head']), default=None)
        stages['in_queue'] = flow_seconds(queued, merge)
    return stages


def flow_progress(issue_at, claim, merge, records, prs, cutoff, covered):
    pushes = [at for p in prs for at in p['pushes']]
    changes = [at for _, created, updated in records for at in (created, updated) if at <= cutoff]
    results = [at for p in prs for at in p['ci_results']]
    verdicts = [v['at'] for p in prs for v in p['verdicts']]
    timeline = sorted({at for at in (*pushes, *changes, *results, *verdicts, issue_at, claim, merge) if at})
    pending = [p['ci_pending'] for p in prs]
    return {
        'commit_at': max(pushes, default=None), 'record_at': max(changes, default=None),
        'ci_result_at': max(results, default=None),
        'verdict_at': max(verdicts, default=None) if all(p['verdict_history'] for p in prs) else None,
        'last_observed_at': timeline[-1] if timeline else None,
        'complete': covered, 'ci_pending': True if True in pending else False if pending and set(pending) == {False}
        else None,
    }, timeline


def flow_stall_count(claim, merge, covered, timeline):
    if not covered or flow_seconds(claim, merge) is None:
        return None
    times = [at for at in timeline if claim <= at <= merge]
    return sum(flow_seconds(a, b) >= 30 * 60 for a, b in zip(times, times[1:]))


def flow_units(costs, unit):
    values = [cost[unit] for cost in costs]
    if unit == 'credits':
        credits = flow_totals(Decimal(str(value)) if value is not None else None for value in values)
        return J.number(credits) if credits is not None else None
    return flow_totals(values)


def flow_cost(roles, ci_seconds):
    return {**roles, 'total': {unit: flow_units(roles.values(), unit) for unit in FLOW_UNITS},
            'ci_minutes': None if ci_seconds is None else round(ci_seconds / 60, 6)}


def flow_ticket(c, n, issue, pulls, authors, usage, as_of, pr_cache, links_known):
    top, comments = issue if issue is not None else ({}, [])
    parent = top.get('parent')
    prs = sorted(p for p, data in pulls.items() if links_known and n in data['tickets'])
    merged = sorted(M.iso(pulls[p]['merged']) for p in prs if pulls[p]['merged'] is not None and M.iso(pulls[p]['merged']) <= as_of)
    merge = merged[-1] if merged else None
    closed = top.get('closedAt')
    cutoff = merge or (closed if closed and closed <= as_of else as_of)
    opened = top.get('createdAt')
    issue_records = [(J.first_line(com['body']), com['at'], com['updated']) for com in comments
                     if com['at'] <= cutoff and J.first_line(com['body']).startswith('launch-fleet:')]
    claim = min((at for line, at, _ in issue_records if line == 'launch-fleet: starting' or J.STARTED.fullmatch(line)),
                default=None)
    ready = flow_read(c.ready, n) if issue is not None else None
    for p in prs:
        if (p, cutoff) not in pr_cache:
            pr_cache[p, cutoff] = flow_read(flow_pr, c, p, pulls[p]['base'], authors, cutoff)
    observed = [pr_cache[p, cutoff] for p in prs if pr_cache[p, cutoff] is not None]
    records = issue_records + [rec for p in observed for rec in p['records']]
    fully_read = links_known and issue is not None and len(observed) == len(prs)
    stage_pr = observed[0] if fully_read and len(observed) == 1 else None
    stages = flow_stage_times(claim, ready, merge, stage_pr)
    review_counts = {p['number']: (len(p['verdicts']) or None) if p['verdict_history'] else None
                     for p in observed}
    rounds = flow_totals(review_counts.get(p) for p in prs) if fully_read else None
    covered = fully_read and bool(observed) and all(
        p['head_history'] and p['ci_history'] and p['verdict_history'] for p in observed)
    progress, timeline = flow_progress(opened, claim, merge, records, observed, cutoff, covered)
    roles = flow_role_cost(usage, n, claim, cutoff)
    ci = {p['number']: p['ci_seconds'] for p in observed}
    # A shared PR's work cannot be charged in full to each ticket.
    cost = flow_cost(roles, flow_totals(ci.get(p) for p in prs)
                     if all(pulls[p]['tickets'] == [n] for p in prs) else None)
    return {
        'ticket': n, 'spec': parent['number'] if parent else None, 'pull_requests': prs,
        'state': ('merged' if merge else 'unknown' if not (issue and links_known) else
                  'closed' if closed and closed <= as_of else 'open'),
        'claimed_at': claim, 'merged_at': merge,
        'elapsed_seconds': flow_seconds(claim, merge), 'stages_seconds': stages,
        'review_rounds': rounds, 'stall_count': flow_stall_count(claim, merge, covered, timeline), 'cost': cost,
        'progress': progress,
    }, ci, review_counts, covered


def flow_spec(n, members, tickets, pulls, job_seconds, review_counts):
    created, numbers = members if members is not None else (None, None)
    rows = [tickets[t] for t in numbers or []]
    complete = bool(rows) and all(row['spec'] == n for row in rows)
    rows = rows if complete else []
    merged = [row['merged_at'] for row in rows]
    latest = max(merged) if merged and all(merged) else None
    cohort = {p for row in rows for p in row['pull_requests']}
    owns_cohort = complete and all(set(pulls[p]['tickets']) <= set(numbers) for p in cohort)
    ci = flow_totals(job_seconds.get(p) for p in cohort) if owns_cohort else None
    rounds = (flow_totals(review_counts.get(p) for p in cohort)
              if owns_cohort and all(t['review_rounds'] is not None for t in rows) else None)
    roles = {role: {unit: flow_units((t['cost'][role] for t in rows), unit) for unit in FLOW_UNITS}
             for role in FLOW_ROLES}
    return {
        'spec': n, 'tickets': numbers, 'created_at': created, 'last_merge_at': latest,
        'span_seconds': flow_seconds(created, latest),
        'elapsed_seconds': flow_totals(t['elapsed_seconds'] for t in rows),
        'stages_seconds': {stage: flow_totals(t['stages_seconds'][stage] for t in rows) for stage in FLOW_STAGES},
        'review_rounds': rounds,
        'stall_count': flow_totals(t['stall_count'] for t in rows), 'cost': flow_cost(roles, ci),
    }


def flow(r, started):
    c = J.Collector(r.repo)
    authors = flow_authors()
    requested = set(r.tickets or [])
    specs = set(r.specs)
    implicit = not requested and not specs
    if implicit:
        requested.update(t for pr in r.merged().values() for t in pr['tickets'])

    def read_issue(n):
        top, comments = flow_subject(c, FLOW_ISSUE, 'issue', n, authors)
        J.when(top.get('createdAt'))
        J.when(J.field(top, 'closedAt'), True)
        if J.field(top, 'parent') is not None:
            M.integer(M.obj(top['parent']).get('number'))
        return top, comments

    issues = {n: flow_read(read_issue, n) for n in sorted(requested)}
    if implicit:
        specs.update(i[0]['parent']['number'] for i in issues.values() if i and i[0]['parent'])
    membership = {n: flow_read(flow_members, c, n) for n in sorted(specs)}
    for member in membership.values():
        if member and member[1] is not None:
            requested.update(member[1])
    for n in sorted(requested - issues.keys()):
        issues[n] = flow_read(read_issue, n)
    incomplete_links = set()
    if implicit or specs:
        pulls = {p: data for p, data in r.prs().items() if requested.intersection(data['tickets'])}
    else:
        pulls = {}
        for n in sorted(requested):
            linked = flow_read(flow_linked_pulls, r, c, n)
            if linked is None:
                incomplete_links.add(n)
                continue
            for p, pr in linked.items():
                paths = pulls.get(p)
                if paths is not None and paths != pr:
                    incomplete_links.update(set(paths['tickets']) | set(pr['tickets']))
                pulls[p] = pr
    usage = flow_read(flow_usage, r.repo, r.flow_threads, r.flow_usage) or ({}, {})
    tickets, jobs, reviews, pr_cache = {}, {}, {}, {}
    incomplete_progress = False
    for n, issue in issues.items():
        ticket, ci, counts, covered = flow_ticket(
            c, n, issue, pulls, authors, usage, started, pr_cache, n not in incomplete_links)
        tickets[n] = ticket
        for totals, observed in ((jobs, ci), (reviews, counts)):
            for p, measurement in observed.items():
                # A shared PR is read with each ticket's cutoff. Only agreement survives.
                if p in totals and totals[p] != measurement:
                    totals[p] = None
                else:
                    totals[p] = measurement
        incomplete_progress |= not covered
    spec_rows = [flow_spec(n, members, tickets, pulls, jobs, reviews) for n, members in membership.items()]
    value = {'tickets': [tickets[n] for n in sorted(tickets)], 'specs': spec_rows}
    rows = value['tickets'] + spec_rows
    gaps = {
        'scope': bool(incomplete_links) or any(i is None for i in issues.values()) or
                 any(s['tickets'] is None for s in spec_rows),
        'github': any(t['elapsed_seconds'] is None or t['review_rounds'] is None or
                      None in t['stages_seconds'].values() for t in rows) or
                  any(s['span_seconds'] is None for s in spec_rows),
        'usage': any(None in t['cost']['total'].values() for t in rows),
        'ci': any(t['cost']['ci_minutes'] is None for t in rows),
        'progress': incomplete_progress,
        'stalls': any(t['stall_count'] is None for t in rows),
    }
    missing = [FLOW_PREREQUISITES[key] for key, unknown in gaps.items() if unknown]
    return r.fact('flow', 'partial' if missing else 'known', started, point=started, value=value,
                  src=source('collector/factory/flow.json', 'github.flow-and-usage', canonical(value)),
                  prerequisites=missing, evidence=[f'{r.web}/issues/{n}' for n in sorted(requested | specs)] +
                  [f'{r.web}/pull/{p}' for p in sorted(pulls)])


READERS = {'merges': merges, 'prs_per_hour': prs_per_hour, 'stage_waits': stage_waits, 'stalls': stalls,
           'open_prs': open_prs, 'journeys': journeys, 'cost': cost, 'flow': flow}
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
    'flow': 'Flow unavailable: the closing-ticket inventory or factory identity could not be read.',
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
         checks=('ci',), clock=now, specs=(), flow_threads=None, flow_usage=()):
    """One on-demand read envelope of FACTS (collector.v1.md, "The on-demand read")."""
    suite.require(type(repository) is str and REPO.fullmatch(repository) is not None, 'invalid repository')
    facts = list(facts)
    suite.require(facts and len(set(facts)) == len(facts) and set(facts) <= set(FACTS), 'invalid facts')
    suite.require(type(robots) is int and robots >= 1, 'invalid robots')
    requested = clock()
    since, until = (when(t) for t in window(since, until, requested))
    r = Read(repository, since, until, clock, None if usage is None else Path(usage), robots, tickets, base, tuple(checks),
             specs, flow_threads, flow_usage)
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
                                    window=None if name in ('open_prs', 'stage_waits', 'flow') else r.window())
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
        nothing = (name in ('merges', 'open_prs') and not value['pull_requests'] or
                   name == 'flow' and not value['tickets'] and not value['specs'])
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
    elif name == 'flow':
        validate_flow(value, fact['point'])
    elif name == 'prs_per_hour':
        require((value['robot_minutes_per_code_run'] is None) == (value['capacity_prs_per_hour'] is None),
                'capacity needs robot-minutes')


def validate_flow(value, point):
    require = suite.require
    require(point is not None, 'flow needs its observation point')
    tickets = {row['ticket']: row for row in value['tickets']}
    specs = {row['spec']: row for row in value['specs']}
    require(len(tickets) == len(value['tickets']) and len(specs) == len(value['specs']),
            'flow lists a ticket or spec twice')
    for row in tickets.values():
        require(row['elapsed_seconds'] == flow_seconds(row['claimed_at'], row['merged_at']),
                'elapsed time must match its endpoints')
        require((row['state'] == 'merged') == (row['merged_at'] is not None), 'merged state needs the merge time')
        progress = row['progress']
        observed = progress['last_observed_at']
        require(observed is None or when(observed) <= when(point), 'progress lies after the observation')
        require(all(at is None or (observed and when(at) <= when(observed)) for key, at in progress.items()
                    if key.endswith('_at')), 'progress sources lie by the latest observation')
        require(row['stall_count'] is None or (progress['complete'] and row['elapsed_seconds'] is not None),
                'stall counts need a bounded progress history')
    for row in specs.values():
        require(row['span_seconds'] == flow_seconds(row['created_at'], row['last_merge_at']),
                'span must match its endpoints')
        require(row['tickets'] is None or set(row['tickets']) <= tickets.keys(), 'a spec member is missing')


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
    r.add_argument('--ticket', type=positive, action='append', help='a ticket whose stage waits or flow are read (repeat)')
    r.add_argument('--spec', type=positive, action='append', help='a spec whose complete flow is read (repeat)')
    r.add_argument('--flow-threads', type=Path, help='private ticket-to-role usage assignments')
    r.add_argument('--flow-usage', type=Path, action='append', help='complete private daily usage export (repeat)')
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
    if a.spec and len(set(a.spec)) != len(a.spec):
        parser.error('a spec is named twice')
    if a.base is not None and not re.fullmatch(r'[A-Za-z0-9_./-]+', a.base):
        parser.error('invalid --base')
    clock = (lambda: a.now) if a.now else now
    try:
        doc = read(a.repo, a.fact, since=a.since, until=a.until, usage=a.usage, robots=a.robots, tickets=a.ticket,
                   base=a.base, checks=tuple(a.check or ['ci']), clock=clock, specs=a.spec or (),
                   flow_threads=a.flow_threads, flow_usage=a.flow_usage or ())
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
