#!/usr/bin/env python3
"""MT2 (#821): the collector's factory facts, on the source tools' own fixtures.

Every world is synthetic (fixtures/collector-factory/README.md says where each
comes from). The daily world is factory-metrics' own test world, worked by hand
in tools/collector/test_metrics.py: 3 merges (01:15, 02:20, 04:30) on 2030-01-02;
gaps 10 + 45 + 20 + 90 + 10 = 175 idle minutes, by hour 00h 40, 01h 15, 02h 20,
03h 60, 04h 30, 23h 10; the biggest is ticket 14's 90 minutes; Actions 12
minutes and $0.60, Claude 3000 tokens / 6 credits / $3, GPT 6000 / 9 / $6,
sandbox 6 hours / $3. The journey and stage worlds are test_journey.py's, the
bench world ci-bench's test.py's, and the open-PR world is the contract's
read-stall.json, as GitHub would answer it.

Each case names the bug it catches. Run: python3 -I tools/collector/test_collect_factory.py
"""
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
# ci-bench's `collect` and `measure` commands, now bench_measure.py's functions (#827), run as the CLI ran them.
BENCH = ['-c', 'import sys; sys.path.insert(0, sys.argv.pop(1)); import bench_measure as B; a = sys.argv[1:]; '
         '(B.collect(a[2], a[4], a[6]) if a[0] == "collect" else '
         'B.measure(a[1], int(a[3]), a[5], allow_empty=True, allow_timing_gaps=True))', str(ROOT / 'tools/collector')]
FIX = HERE / 'fixtures' / 'collector-factory'
COLLECTOR = HERE / 'fixtures' / 'collector'
SCRIPT = HERE / 'collect_factory.py'
DAILY_REPO, OPEN_REPO = 'example/factory', 'synthetic-owner/synthetic-repo'
DAY = ('2030-01-02T00:00:00Z', '2030-01-03T00:00:00Z')
C_LIMITS = 'tools/collector/limits.conf'  # TL1's settings file, which collect_factory reads
FACTS = ['merges', 'prs_per_hour', 'stage_waits', 'stalls', 'open_prs', 'journeys', 'cost', 'flow']


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


suite = load('suite', HERE / 'suite.py')
SCHEMA = json.loads((HERE / 'collector.v1.schema.json').read_text())


@contextlib.contextmanager
def fake_gh(world, edit=None):
    """PATH holds the exact-call fake gh over WORLD (a fixture name); yields the call log."""
    data = json.loads((FIX / world).read_text())
    if edit:
        edit(data)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / 'gh').symlink_to(FIX / 'fake_gh.py')
        (tmp / 'world.json').write_text(json.dumps(data))
        log = tmp / 'calls'
        log.write_text('')
        env = {'PATH': str(tmp) + os.pathsep + os.environ['PATH'], 'FAKE_GH_WORLD': str(tmp / 'world.json'),
               'FAKE_GH_LOG': str(log), 'PYTHONDONTWRITEBYTECODE': '1'}
        with patch.dict(os.environ, env):
            yield tmp, (lambda: [json.loads(line) for line in log.read_text().splitlines()])


def cli(world, *args, edit=None):
    with fake_gh(world, edit) as (tmp, calls):
        p = subprocess.run([sys.executable, '-I', str(SCRIPT), *args], capture_output=True, text=True,
                           timeout=60, env=dict(os.environ))
        return p, calls()


def envelope(p):
    assert p.returncode == 0, p.stderr
    doc = json.loads(p.stdout)
    suite._shape(doc, SCHEMA['$defs']['read_envelope'], SCHEMA)
    return doc


@contextlib.contextmanager
def run_tool(world, argv):
    """One of the source tools themselves, on the same world: the numbers to compare against."""
    with fake_gh(world) as (tmp, _):
        p = subprocess.run([sys.executable, '-I', *argv(tmp)], capture_output=True, text=True, timeout=60,
                           env=dict(os.environ, GH_TOKEN='synthetic-app-token'))
        assert p.returncode == 0, p.stderr
        yield tmp


class DailyNumbers(unittest.TestCase):
    """AC1: every factory-metrics number the inventory lists, out of the collector."""

    @classmethod
    def setUpClass(cls):
        p, cls.calls = cli('daily-world.json', 'read', '--repo', DAILY_REPO, '--fact', 'merges', '--fact', 'stalls',
                           '--fact', 'cost', '--since', DAY[0], '--until', DAY[1], '--usage', str(FIX / 'daily-usage.json'),
                           '--now', '2030-01-03T06:00:00Z')
        cls.doc = envelope(p)
        cls.f = cls.doc['factory']

    # catches: a merge on another base dropped (factory-metrics counts all bases), a PR merged
    # after the window counted, or a direction taken from the wrong closing ticket.
    def test_merges_count_every_base_with_direction(self):
        merges = self.f['merges']
        self.assertEqual(merges['state'], 'known')
        self.assertEqual(merges['value']['pull_requests'], [
            {'number': 31, 'merged_at': '2030-01-02T01:15:00Z', 'base': 'main', 'tickets': [12, 15], 'direction': 'forward'},
            {'number': 32, 'merged_at': '2030-01-02T02:20:00Z', 'base': 'main', 'tickets': [13], 'direction': 'backwards'},
            {'number': 33, 'merged_at': '2030-01-02T04:30:00Z', 'base': 'release-0.0.9', 'tickets': [14],
             'direction': 'sideways'}])
        self.assertEqual(merges['window'], {'since': DAY[0], 'until': DAY[1], 'timezone': 'UTC'})
        self.assertEqual(merges['evidence'], ['https://github.com/example/factory/pull/%d' % n for n in (31, 32, 33)])

    # catches: a gap not capped at its merge, carry-in before midnight lost, an open tail not
    # clipped at the window's end, or a two-ticket start counted twice.
    def test_stalls_are_factory_metrics_gaps(self):
        stalls = self.f['stalls']
        self.assertEqual(stalls['state'], 'partial')
        v = stalls['value']
        self.assertEqual(v['idle_minutes'], 175)
        self.assertEqual([h['idle_minutes'] for h in v['hours']], [40, 15, 20, 60, 30] + [0] * 18 + [10])
        self.assertEqual(v['hours'][23]['start'], '2030-01-02T23:00:00Z')
        self.assertEqual([(s['tickets'], s['minutes']) for s in v['stalls']],
                         [([14], 90), ([12, 15], 45), ([13], 20), ([12], 10), ([], 10)])
        last = next(s for s in v['stalls'] if s['pull_request'] == 35)
        self.assertEqual((last['from'], last['until'], last['open_at_end']),
                         ('2030-01-02T23:50:00Z', '2030-01-03T00:00:00Z', True))
        self.assertEqual(v['unlinked_prs'], [35])
        self.assertEqual((v['edited_fleet_comments'], v['clock_skew_comments']), (1, 0))

    # catches: a unit added to another, storage USD dropped from Actions, or the export's
    # thread keys kept.
    def test_cost_keeps_each_source_and_unit(self):
        cost = self.f['cost']['value']
        self.assertEqual(cost['date'], '2030-01-02')
        self.assertEqual((cost['actions_billing']['minutes'], cost['actions_billing']['usd']), (12, 0.6))
        usage = cost['usage']
        self.assertEqual(usage['complete'], True)
        self.assertEqual(usage['claude'], {'tokens': 3000, 'credits': 6, 'usd': 3})
        self.assertEqual(usage['gpt'], {'tokens': 6000, 'credits': 9, 'usd': 6})
        self.assertEqual(usage['sandbox'], {'hours': 6, 'usd': 3})
        # A reader's factory total over known components, as factory-metrics prints it: $12.60.
        total = cost['actions_billing']['usd'] + sum(usage[k]['usd'] for k in ('claude', 'gpt', 'sandbox'))
        self.assertAlmostEqual(total, 12.6)
        self.assertNotIn('synthetic-a', json.dumps(self.doc))

    # catches: the collector drifting from factory-metrics on the same fixture: compared, number
    # by number, with metrics.py's own report on the same world.
    def test_same_numbers_as_metrics_py(self):
        with run_tool('daily-world.json', lambda tmp: [
                str(HERE / 'metrics.py'), '--date', '2030-01-02', '--repo', DAILY_REPO,
                '--out', str(tmp / 'out'), '--usage', str(FIX / 'daily-usage.json')]) as tmp:
            report = json.loads((tmp / 'out' / 'report.json').read_text())
        merged = self.f['merges']['value']['pull_requests']
        self.assertEqual(len(merged), report['merged_prs'])
        self.assertEqual([sum(int(p['merged_at'][11:13]) == h for p in merged) for h in range(24)],
                         [h['merged_prs'] for h in report['hours']])
        stalls = self.f['stalls']['value']
        self.assertEqual(stalls['idle_minutes'], report['idle_minutes'])
        self.assertEqual([h['idle_minutes'] for h in stalls['hours']], [h['idle_minutes'] for h in report['hours']])
        renamed = [{('open_at_end' if k == 'open_at_midnight' else k): v for k, v in s.items()} for s in report['stalls']]
        self.assertEqual(stalls['stalls'], renamed)
        self.assertEqual(stalls['edited_fleet_comments'], report['edited_fleet_comments'])
        self.assertEqual(stalls['clock_skew_comments'], report['clock_skew_comments'])
        cost, costs = self.f['cost']['value'], report['costs']
        self.assertEqual(cost['actions_billing']['minutes'], costs['actions']['minutes']['total'])
        self.assertEqual(cost['actions_billing']['usd'], costs['actions']['usd']['total'])
        for provider, units in (('claude', ('tokens', 'credits', 'usd')), ('gpt', ('tokens', 'credits', 'usd')),
                                ('sandbox', ('hours', 'usd'))):
            for unit in units:
                self.assertEqual(cost['usage'][provider][unit], costs[provider][unit]['total'], (provider, unit))

    # catches: a fact that breaks the contract's cross-field rules (read bounds, window, state).
    def test_every_fact_passes_validate(self):
        C = load('collect_factory', SCRIPT)
        for name, fact in self.f.items():
            C.validate(fact)
        self.assertGreaterEqual(self.f['merges']['read']['started_at'], self.doc['requested_at'])


class DailyEdges(unittest.TestCase):
    # catches: an open gap with no later record at all closed at the window's end as if it ended
    # there (factory-metrics: an open tail is open at midnight).
    def test_open_tail_with_no_later_record(self):
        def edit(world):
            key = next(k for k in world if 'issues/comments' in k)
            world[key]['stdout'] = json.dumps([c for c in json.loads(world[key]['stdout']) if c['id'] != 13])
        p, _ = cli('daily-world.json', 'read', '--repo', DAILY_REPO, '--fact', 'stalls', '--since', DAY[0],
                   '--until', DAY[1], '--now', '2030-01-03T06:00:00Z', edit=edit)
        tail = next(s for s in envelope(p)['factory']['stalls']['value']['stalls'] if s['pull_request'] == 35)
        self.assertEqual((tail['minutes'], tail['open_at_end']), (10, True))

    # catches: a direction guessed for a merge whose tickets disagree or that closes none
    # (the contract says unknown).
    def test_direction_unknown_when_tickets_disagree_or_none_link(self):
        def edit(world):
            key = next(k for k in world if 'number=15' in k and 'milestone' in k)
            world[key]['stdout'] = world[key]['stdout'].replace('0.0.9', 'Infra')
        p, _ = cli('daily-world.json', 'read', '--repo', DAILY_REPO, '--fact', 'merges', '--since', DAY[0],
                   '--until', '2030-01-04T00:00:00Z', '--now', '2030-01-04T06:00:00Z', edit=edit)
        directions = {m['number']: m['direction'] for m in envelope(p)['factory']['merges']['value']['pull_requests']}
        self.assertEqual(directions, {31: 'unknown', 32: 'backwards', 33: 'sideways', 34: 'unknown'})


class CarriedJourneys(unittest.TestCase):
    """The journeys and stage waits, carried exactly as journey.py collects and benches them."""

    # catches: a cohort that misses a merged PR closing a ticket, or a document changed on the way.
    def test_journeys_are_journey_collect_unchanged(self):
        p, _ = cli('journey-world.json', 'read', '--repo', DAILY_REPO, '--fact', 'journeys',
                   '--since', DAY[0], '--until', DAY[1], '--now', '2030-01-03T06:00:00Z')
        fact = envelope(p)['factory']['journeys']
        self.assertEqual(fact['state'], 'partial')
        self.assertEqual(fact['value']['cohort'], {'window': {'since': DAY[0], 'until': DAY[1], 'timezone': 'UTC'},
                                                   'pull_requests': [4201, 4202]})
        with run_tool('journey-world.json', lambda tmp: [
                str(HERE / 'journey.py'), 'collect', '--repo', DAILY_REPO,
                '--ticket', '4101', '--ticket', '4103', '--out', str(tmp / 'out')]) as tmp:
            written = (tmp / 'out' / 'journeys.json').read_bytes()
        self.assertEqual(fact['value']['document'], json.loads(written))
        self.assertEqual(fact['source']['sha256'], hashlib.sha256(written).hexdigest())
        self.assertIsNone(fact['value']['outcomes'])

    # catches: a sidecar or bench recomputed differently from TL2's, or limits read from another file.
    def test_stage_waits_are_tl2_unchanged(self):
        at = '2030-03-01T12:00:00Z'
        tickets = ['--ticket', '4301', '--ticket', '4302', '--ticket', '4303', '--ticket', '4304']
        p, _ = cli('stage-world.json', 'read', '--repo', DAILY_REPO, '--fact', 'stage_waits', *tickets, '--now', at)
        fact = envelope(p)['factory']['stage_waits']
        self.assertEqual((fact['state'], fact['point']), ('partial', at))
        with run_tool('stage-world.json', lambda tmp: [
                str(HERE / 'journey.py'), 'collect', '--repo', DAILY_REPO, *tickets,
                '--stage-waits', '--as-of', at, '--out', str(tmp / 'out')]) as tmp:
            side = (tmp / 'out' / 'stage-waits.json').read_bytes()
            journey = json.loads((tmp / 'out' / 'journeys.json').read_text())
            bench = subprocess.run([sys.executable, '-I', str(HERE / 'journey.py'), 'bench',
                                    str(tmp / 'out' / 'journeys.json'), '--stage-waits', str(tmp / 'out' / 'stage-waits.json')],
                                   capture_output=True, text=True, timeout=60)
        self.assertEqual(fact['value']['sidecar'], json.loads(side))
        self.assertEqual(fact['value']['journey'], journey)
        self.assertEqual(fact['source']['sha256'], hashlib.sha256(side).hexdigest())
        self.assertEqual(fact['value']['bench'], json.loads(bench.stdout)['stage_waits'])
        conf = (ROOT / C_LIMITS).read_bytes()
        self.assertEqual(fact['value']['limits']['sha256'], hashlib.sha256(conf).hexdigest())
        self.assertGreaterEqual(fact['value']['limits']['read_at'], fact['value']['sidecar']['read_at'])

    # catches: stage waits invented for no tickets instead of saying what is missing.
    def test_stage_waits_without_tickets_are_unavailable(self):
        p, calls = cli('stage-world.json', 'read', '--repo', DAILY_REPO, '--fact', 'stage_waits')
        fact = envelope(p)['factory']['stage_waits']
        self.assertEqual((fact['state'], fact['value']), ('unavailable', None))
        self.assertTrue(fact['prerequisites'])
        self.assertEqual(calls, [])


def add_comment_history(world, node, created, updated, edited, original, current):
    query = ('query($id:ID!){node(id:$id){...on IssueComment{id createdAt updatedAt '
             'userContentEdits(first:100){totalCount pageInfo{hasNextPage} '
             'nodes{editedAt deletedAt diff}}}}}')
    key = json.dumps(['api', 'graphql', '-f', f'query={query}', '-f', f'id={node}'])
    history = [{'editedAt': at, 'deletedAt': None, 'diff': body}
               for at, body in ((edited, current), (created, original))]
    response = {'data': {'node': {'id': node, 'createdAt': created, 'updatedAt': updated,
                                  'userContentEdits': {'totalCount': 2, 'pageInfo': {'hasNextPage': False},
                                                       'nodes': history}}}}
    world[key] = {'stdout': json.dumps(response)}


class FlowFacts(unittest.TestCase):
    fixture = HERE / 'fixtures' / 'flow'
    args = ('read', '--repo', DAILY_REPO, '--fact', 'flow', '--spec', '4001',
            '--now', '2030-01-03T06:00:00Z')

    # catches: missing merge-group jobs, charging rerun jobs twice, using edited times for claims, counting
    # impostors or duplicate verdicts, and conflating ticket time with spec span.
    def test_merged_ticket_and_whole_spec(self):
        p, _ = cli('../flow/world.json', *self.args,
                   '--flow-threads', str(self.fixture / 'assignments.json'),
                   '--flow-usage', str(self.fixture / 'usage.json'))
        fact = envelope(p)['factory']['flow']
        value = fact['value']
        ticket, = value['tickets']
        spec, = value['specs']
        self.assertEqual((ticket['ticket'], ticket['pull_requests'], ticket['state']), (4101, [4201], 'merged'))
        self.assertEqual(ticket['cost'], {
            'builder': {'credits': 7, 'tokens': 550}, 'reviewer': {'credits': 2, 'tokens': 130},
            'total': {'credits': 9, 'tokens': 680}, 'ci_minutes': 15})
        self.assertEqual(ticket['stages_seconds'], {
            'waiting_to_start': 900, 'building': 5100, 'in_review': 1080, 'in_queue': 900})
        self.assertEqual((ticket['elapsed_seconds'], ticket['review_rounds'], ticket['stall_count']), (9000, 1, 2))
        self.assertEqual(ticket['progress']['commit_at'], '2030-01-02T01:58:00Z')
        self.assertEqual(spec['stall_count'], 2)
        self.assertEqual((spec['spec'], spec['tickets'], spec['span_seconds']), (4001, [4101], 11700))
        self.assertEqual((spec['cost'], spec['stages_seconds'], spec['elapsed_seconds'], spec['review_rounds']),
                         (ticket['cost'], ticket['stages_seconds'], 9000, 1))

    # catches (FM3, #1171): undated or missing stall gaps, gaps past the merge or before the claim, an open
    # ticket's history dropped, or a latest record kind taken from the wrong record or with its head kept.
    def test_progress_dates_gaps_and_names_the_latest_record(self):
        p, _ = cli('../flow/world.json', *self.args)
        progress = envelope(p)['factory']['flow']['value']['tickets'][0]['progress']
        # By hand from the world: claim edit 01:00, push 01:58, verdict 02:30, merge queued 03:00, merge 03:15.
        self.assertEqual(progress.get('gaps'), [
            {'from': '2030-01-02T01:00:00Z', 'until': '2030-01-02T01:58:00Z'},
            {'from': '2030-01-02T02:30:00Z', 'until': '2030-01-02T03:00:00Z'}])
        self.assertEqual(progress.get('last_record'), 'merge queued')
        # Read before the merge: the ticket is open, and the 02:30 gap is not over yet, so it is not a past gap.
        args = (*self.args[:-1], '2030-01-02T02:45:00Z')
        ticket = envelope(cli('../flow/world.json', *args)[0])['factory']['flow']['value']['tickets'][0]
        self.assertEqual((ticket['state'], ticket['progress'].get('gaps')), (
            'open', [{'from': '2030-01-02T01:00:00Z', 'until': '2030-01-02T01:58:00Z'}]))
        self.assertEqual(ticket['progress'].get('last_record'), 'review started')
        for line, kind in ((f'launch-fleet: parked {"a" * 40}: R2 for Jake', 'parked'),
                           ('launch-fleet: builder fallback due, branch room/4101-synthetic', 'builder fallback due'),
                           ('launch-fleet: asked the orchestrator', 'asked the orchestrator')):
            def late_record(world, line=line):
                key = next(key for key in world if 'pullRequest(number:$number)' in key and 'body author{login}' in key)
                response = json.loads(world[key]['stdout'])
                response['data']['repository']['pullRequest']['comments']['nodes'].append(
                    {'id': 'synthetic-late', 'databaseId': 5299, 'author': {'login': 'openwiz[bot]'},
                     'url': 'https://github.com/example/factory/pull/4201#issuecomment-5299',
                     'createdAt': '2030-01-02T03:10:00Z', 'updatedAt': '2030-01-02T03:10:00Z', 'body': line})
                world[key]['stdout'] = json.dumps(response)

            with self.subTest(kind):
                p, _ = cli('../flow/world.json', *self.args, edit=late_record)
                progress = envelope(p)['factory']['flow']['value']['tickets'][0]['progress']
                self.assertEqual(progress.get('last_record'), kind)

    # catches: dropping a second spec member or counting a shared PR's
    # review twice at spec level or assigning all its runner minutes to each ticket.
    def test_whole_spec_counts_shared_pull_once(self):
        p, _ = cli('../flow/world-shared.json', *self.args)
        value = envelope(p)['factory']['flow']['value']
        self.assertEqual([t['ticket'] for t in value['tickets']], [4101, 4102])
        spec, = value['specs']
        self.assertEqual((spec['tickets'], spec['elapsed_seconds'], spec['review_rounds']), ([4101, 4102], 18000, 1))
        self.assertEqual([t['cost']['ci_minutes'] for t in value['tickets']], [None, None])
        self.assertEqual(spec['cost']['ci_minutes'], 15)

    # catches: a per-ticket read depending on the repository-wide PR inventory
    # and losing its facts when an unrelated inventory page cannot be read.
    def test_ticket_read_needs_only_its_linked_pulls(self):
        def without_inventory(world):
            del world[next(key for key in world if 'pullRequests(first:100' in key)]

        p, _ = cli('../flow/world.json', 'read', '--repo', DAILY_REPO, '--fact', 'flow', '--ticket', '4101',
                   '--now', '2030-01-03T06:00:00Z', edit=without_inventory)
        value = envelope(p)['factory']['flow']['value']
        self.assertIsNotNone(value, 'the ticket has readable linked pulls')
        ticket, = value['tickets']
        self.assertEqual((ticket['ticket'], ticket['pull_requests'], ticket['cost']['ci_minutes']), (4101, [4201], 15))

    # catches: an edited CHANGES disappearing or unprovable verdict history
    # producing partial round counts and attributing review time to building.
    def test_edited_verdict_history_keeps_only_supported_rounds(self):
        head = 'a' * 40
        original = f'VERDICT: CHANGES at {head}\n\nFull review by a synthetic reviewer.'
        current = original + '\n\nPolish issue recorded.'
        cases = {
            'body only': original,
            'changed verdict': original.replace('CHANGES', 'APPROVE'),
            'changed head': original.replace(head, 'b' * 40),
            'removed verdict': current,
            'missing history': None,
        }
        for scenario, previous in cases.items():
            def edit(world):
                key = next(key for key in world if 'pullRequest(number:$number)' in key and 'body author{login}' in key)
                response = json.loads(world[key]['stdout'])
                comments = response['data']['repository']['pullRequest']['comments']['nodes']
                opened, updated = '2030-01-02T02:09:00Z', '2030-01-02T02:11:00Z'
                visible = 'See the review discussion.' if scenario == 'removed verdict' else current
                comments.extend([
                    {'id': 'synthetic-review-start', 'databaseId': 5291, 'author': {'login': 'openwiz[bot]'},
                     'url': 'https://github.com/example/factory/pull/4201#issuecomment-5291',
                     'createdAt': '2030-01-02T02:05:00Z', 'updatedAt': '2030-01-02T02:05:00Z',
                     'body': f'launch-fleet: review started {head}'},
                    {'id': 'synthetic-verdict', 'databaseId': 5292, 'author': {'login': 'openwiz[bot]'},
                     'url': 'https://github.com/example/factory/pull/4201#issuecomment-5292',
                     'createdAt': opened, 'updatedAt': updated, 'body': visible},
                ])
                world[key]['stdout'] = json.dumps(response)
                if previous is not None:
                    add_comment_history(world, 'synthetic-verdict', opened, updated, '2030-01-02T02:10:59Z', previous, visible)

            with self.subTest(scenario):
                p, _ = cli('../flow/world.json', *self.args, edit=edit)
                fact = envelope(p)['factory']['flow']
                supported = scenario == 'body only'
                for row in (*fact['value']['tickets'], *fact['value']['specs']):
                    self.assertEqual(row['review_rounds'], 2 if supported else None)
                    self.assertEqual(row['elapsed_seconds'], 9000)
                    self.assertEqual(row['cost']['ci_minutes'], 15)
                    self.assertEqual(row['stages_seconds'], {
                        'waiting_to_start': 900, 'building': 4860 if supported else None,
                        'in_review': 1320 if supported else None, 'in_queue': 900 if supported else None})
                ticket, = fact['value']['tickets']
                self.assertEqual(ticket['progress']['complete'], supported)
                self.assertEqual(ticket['progress']['verdict_at'], '2030-01-02T02:30:00Z' if supported else None)
                self.assertEqual(ticket['stall_count'], 2 if supported else None)

    # catches: unreadable jobs or missing usage emitted as zero, or a missing
    # cost source taking unrelated timing and progress away.
    def test_missing_sources_keep_independent_facts(self):
        def without_sources(world):
            for fragment in ('runs/6101/attempts/1/jobs', '/activity?ref='):
                key = next(key for key in world if fragment in key)
                del world[key]

        p, _ = cli('../flow/world.json', *self.args, edit=without_sources)
        fact = envelope(p)['factory']['flow']
        self.assertEqual(fact['state'], 'partial')
        ticket, = fact['value']['tickets']
        spec, = fact['value']['specs']
        for row in (ticket, spec):
            self.assertEqual(row['cost'], {
                'builder': {'credits': None, 'tokens': None}, 'reviewer': {'credits': None, 'tokens': None},
                'total': {'credits': None, 'tokens': None}, 'ci_minutes': None})
            self.assertEqual((row['elapsed_seconds'], row['review_rounds'], row['stall_count']), (9000, 1, None))
        self.assertEqual(ticket['progress']['last_observed_at'], '2030-01-02T03:15:00Z')
        self.assertIsNone(ticket['progress'].get('gaps', 'absent'))  # FM3: an incomplete history has no dated gaps


class CapacityAndOpenPrs(unittest.TestCase):
    # catches: PRs an hour computed another way than ci-bench's headline (robot-minutes per
    # successful code run). By hand: run 201's two jobs, 115 s + 180 s = 4.9167 robot-minutes;
    # 5 robots x 60 / 4.9167 = 61.0169 PRs an hour; PRs 50 and 1000 merged into main in 2 hours.
    def test_prs_per_hour_is_ci_bench_headline(self):
        since, until = '2030-01-01T00:00:00Z', '2030-01-01T02:00:00Z'
        p, _ = cli('bench-world.json', 'read', '--repo', DAILY_REPO, '--fact', 'prs_per_hour', '--since', since,
                   '--until', until, '--now', '2030-01-01T06:00:00Z')
        fact = envelope(p)['factory']['prs_per_hour']
        self.assertEqual(fact['value'], {'robots': 5, 'code_runs': 1, 'robot_minutes_per_code_run': 4.9167,
                                         'capacity_prs_per_hour': 61.0169, 'merged_prs': 2, 'merged_per_hour': 1.0,
                                         'baseline': None})
        self.assertEqual(fact['state'], 'known')
        with run_tool('bench-world.json', lambda tmp: [
                *BENCH, 'collect', '--since', since, '--until', until,
                '--out', str(tmp / 'w')]) as tmp:
            subprocess.run([sys.executable, '-I', *BENCH, 'measure', str(tmp / 'w'),
                            '--robots', '5', '--label', 'compare', '--allow-empty', '--allow-timing-gaps'],
                           check=True, capture_output=True, timeout=60)
            point = json.loads((tmp / 'w' / 'point.json').read_text())
        self.assertEqual((fact['value']['robot_minutes_per_code_run'], fact['value']['capacity_prs_per_hour'],
                          fact['value']['merged_per_hour']),
                         (point['code_runs']['robot_minutes_per_run'], point['code_runs']['prs_per_hour'],
                          point['merged_per_hour']))

    # catches: the stall alarm's view drifting: a null rollup read as pending, a verdict taken
    # from a non-verdict comment, or the hour's merges filled from outside the hour. The
    # expected value is the contract's own worked fixture.
    def test_open_prs_and_the_hour_match_read_stall(self):
        p, _ = cli('open-world.json', 'read', '--repo', OPEN_REPO, '--fact', 'open_prs', '--fact', 'merges',
                   '--since', '2030-03-01T11:04:00Z', '--until', '2030-03-01T12:04:00Z', '--now', '2030-03-01T12:04:00Z')
        got = envelope(p)['factory']
        expected = json.loads((COLLECTOR / 'read-stall.json').read_text())['factory']
        self.assertEqual(got['open_prs']['value'], expected['open_prs']['value'])
        self.assertEqual(got['open_prs']['state'], 'known')
        self.assertEqual(got['merges']['value'], {'pull_requests': []})
        self.assertEqual((got['merges']['state'], got['merges']['evidence']), ('known', []))

    # catches: a PR with over 100 comments judged on a truncated list.
    def test_truncated_comments_make_open_prs_unavailable(self):
        def edit(world):
            key = next(k for k in world if 'states:OPEN' in k)
            answer = json.loads(world[key]['stdout'])
            answer['data']['repository']['pullRequests']['nodes'][1]['comments']['pageInfo']['hasPreviousPage'] = True
            world[key]['stdout'] = json.dumps(answer)
        p, _ = cli('open-world.json', 'read', '--repo', OPEN_REPO, '--fact', 'open_prs', edit=edit)
        fact = envelope(p)['factory']['open_prs']
        self.assertEqual((fact['state'], fact['value']), ('unavailable', None))


    # catches: a failed, cancelled or pending check read as a success, for check runs and
    # commit statuses alike.
    def test_check_results_keep_their_meaning(self):
        contexts = [{'__typename': 'CheckRun', 'name': 'ci', 'status': 'COMPLETED', 'conclusion': 'FAILURE'},
                    {'__typename': 'CheckRun', 'name': 'skills', 'status': 'COMPLETED', 'conclusion': 'CANCELLED'},
                    {'__typename': 'StatusContext', 'context': 'privacy', 'state': 'PENDING'},
                    {'__typename': 'StatusContext', 'context': 'legacy', 'state': 'ERROR'},
                    {'__typename': 'StatusContext', 'context': 'old', 'state': 'SUCCESS'}]

        def edit(world):
            key = next(k for k in world if 'states:OPEN' in k)
            answer = json.loads(world[key]['stdout'])
            rollup = answer['data']['repository']['pullRequests']['nodes'][1]['commits']['nodes'][0]['commit'][
                'statusCheckRollup']
            rollup['state'], rollup['contexts']['nodes'] = 'FAILURE', contexts
            world[key]['stdout'] = json.dumps(answer)
        p, _ = cli('open-world.json', 'read', '--repo', OPEN_REPO, '--fact', 'open_prs', edit=edit)
        pull = envelope(p)['factory']['open_prs']['value']['pull_requests'][1]
        self.assertEqual((pull['number'], pull['rollup']), (4211, 'failure'))
        self.assertEqual([(c['name'], c['result']) for c in pull['checks']],
                         [('ci', 'failure'), ('skills', 'other'), ('privacy', 'pending'), ('legacy', 'failure'),
                          ('old', 'success')])


class Failures(unittest.TestCase):
    # catches: an unreadable source encoded as zero, or one failed fact greying the others.
    def test_failed_source_greys_only_its_fact(self):
        def edit(world):
            key = next(k for k in world if 'issues/comments' in k)
            world[key] = {'exit': 1, 'stdout': ''}
        p, _ = cli('daily-world.json', 'read', '--repo', DAILY_REPO, '--fact', 'stalls', '--fact', 'merges',
                   '--fact', 'cost', '--since', DAY[0], '--until', DAY[1], '--now', '2030-01-03T06:00:00Z', edit=edit)
        f = envelope(p)['factory']
        self.assertEqual((f['stalls']['state'], f['stalls']['value']), ('unavailable', None))
        self.assertTrue(f['stalls']['prerequisites'])
        self.assertEqual(f['merges']['state'], 'known')
        # No usage export: every CloudRoom unit is unknown (null), never zero; Actions is kept.
        usage = f['cost']['value']['usage']
        self.assertEqual((usage['complete'], usage['claude'], usage['sandbox']),
                         (False, {'tokens': None, 'credits': None, 'usd': None}, {'hours': None, 'usd': None}))
        self.assertEqual(f['cost']['value']['actions_billing']['usd'], 0.6)
        self.assertEqual(f['cost']['state'], 'partial')

    # catches: stall hours or a cost day invented for a window they cannot cover.
    def test_windows_the_facts_cannot_cover(self):
        p, _ = cli('daily-world.json', 'read', '--repo', DAILY_REPO, '--fact', 'stalls', '--fact', 'cost',
                   '--since', '2030-01-02T00:30:00Z', '--until', '2030-01-03T00:30:00Z', '--now', '2030-01-03T06:00:00Z')
        f = envelope(p)['factory']
        for name in ('stalls', 'cost'):
            self.assertEqual((f[name]['state'], f[name]['value']), ('unavailable', None), name)

    # catches: a bad command line that still reads GitHub, or a refused read that prints a document.
    def test_cli_exit_codes(self):
        for args in (['read', '--repo', 'not a repo', '--fact', 'merges'], ['read', '--repo', DAILY_REPO],
                     ['read', '--repo', DAILY_REPO, '--fact', 'runs'],
                     ['read', '--repo', DAILY_REPO, '--fact', 'merges', '--since', DAY[0]],
                     ['read', '--repo', DAILY_REPO, '--fact', 'merges', '--since', DAY[1], '--until', DAY[0]]):
            p, calls = cli('daily-world.json', *args)
            self.assertEqual((p.returncode, p.stdout, calls), (2, '', []), args)

        def plant(world):
            key = next(k for k in world if 'baseRefName' in k)
            world[key]['stdout'] = world[key]['stdout'].replace('release-0.0.9', 'ghp_' + 'A1b2C3d4' * 5)
        p, _ = cli('daily-world.json', 'read', '--repo', DAILY_REPO, '--fact', 'merges', '--since', DAY[0],
                   '--until', DAY[1], '--now', '2030-01-03T06:00:00Z', edit=plant)
        self.assertEqual((p.returncode, p.stdout), (1, ''))
        self.assertNotIn('ghp_', p.stderr)


class Validate(unittest.TestCase):
    # catches: validate accepting a fact that breaks the contract (others rely on it), or
    # refusing the contract's own worked fixtures.
    def test_validate_contract_rules(self):
        C = load('collect_factory', SCRIPT)
        snapshot = json.loads((COLLECTOR / 'snapshot.json').read_text())
        for name in snapshot['factory']:
            C.validate(snapshot['factory'][name])
            C.validate(json.loads((COLLECTOR / 'snapshot-unavailable.json').read_text())['factory'][name])
        merges = snapshot['factory']['merges']
        broken = {
            'known with a prerequisite': dict(merges, prerequisites=['x']),
            'unavailable with a value': dict(merges, state='unavailable', prerequisites=['x']),
            'read ends before it starts': dict(merges, read={'started_at': '2030-03-01T12:02:00Z',
                                                             'ended_at': '2030-03-01T12:01:00Z'}),
            'window after the read': dict(merges, window=dict(merges['window'], until='2030-03-02T00:00:00Z')),
            'point and window': dict(merges, point='2030-03-01T12:01:10Z'),
            'merge outside the window': dict(merges, value={'pull_requests': [dict(
                merges['value']['pull_requests'][0], merged_at='2030-03-01T01:00:00Z')]}),
            'another fact name': dict(merges, fact='runs'),
            'stalls known': dict(snapshot['factory']['stalls'], state='known', prerequisites=[]),
        }
        for label, fact in broken.items():
            with self.subTest(label):
                with self.assertRaises(ValueError):
                    C.validate(fact)



if __name__ == '__main__':
    unittest.main()
