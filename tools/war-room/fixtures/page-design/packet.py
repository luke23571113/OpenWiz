#!/usr/bin/env python3
"""WRD3 (#631): the frozen synthetic content packet for the v3 page.

    python3 -I tools/war-room/fixtures/page-design/packet.py OUT_DIR

Writes a synthetic source root and history through the real select/compose/save path,
runs the real chart build (charts/build.py, locked Plot under Node) and writes
OUT_DIR/page.html, OUT_DIR/charts/ and OUT_DIR/packet.json (the inputs' hashes).
Every value is synthetic. The packet holds the cases a design must survive: a low
ready stock, a missing day, an older CI cohort, a re-measured day, a credit span
across a PST midnight, a failed main CI run, a partial queue wait, an open and a
held stage wait, a long label, and benches that are unavailable with a prerequisite.
No network, no live read.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile

PUBLIC_ROOT = Path(__file__).resolve().parents[3] / 'collector'
sys.dont_write_bytecode = True
TOOL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOOL))
sys.path.insert(0, str(PUBLIC_ROOT))
import health  # noqa: E402
import history  # noqa: E402
import page  # noqa: E402
import sources  # noqa: E402
import suite  # noqa: E402

REPO = 'synthetic-owner/work'
LINK = 'https://github.com/synthetic-owner/work/issues/4001'
AT = '2030-01-14T10:00:00Z'          # the build time: PST day 2030-01-14
DAYS = ['2030-01-%02d' % d for d in range(7, 14)]
CURRENT = 'workflow created to last job completed'


def native_build():
    spec = __import__('importlib.util').util.spec_from_file_location('wrd3_charts_build', TOOL / 'charts' / 'build.py')
    module = __import__('importlib.util').util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _next(day):
    return '2030-01-%02d' % (int(day[-2:]) + 1)


def ci_point(day, merged, code, current=True):
    runs, median, p90, robot = code
    p = {'schema': 'closedwiz.ci-bench.v1', 'label': 'synthetic', 'since': day + 'T08:00:00Z',
         'until': _next(day) + 'T08:00:00Z', 'hours': 24, 'robots': 3, 'runs': runs + 4, 'jobs': 2 * runs + 8,
         'merged_prs': merged, 'merged_per_hour': round(merged / 24, 4),
         'code_runs': {'rule': 'synthetic', 'runs': runs, 'robot_seconds': int(robot * 60 * runs),
                       'robot_minutes_per_run': robot, 'prs_per_hour': 1.5,
                       'categories': {'web': 4, 'setup': 1, 'rust': 6, 'build': 2, 'skills': 1},
                       'split': {'waiting': 2, 'setup': 1, 'running': 9},
                       'queued_to_done': {'median': median, 'p90': p90, 'max': p90 + 6}},
         'legacy': None}
    if current:
        p['latency_basis'] = CURRENT
    return p


def board_row(at, day, ready, building, sample='run'):
    values = [sources.PLAN_LINKS, 'history', sample, at, day, REPO, 34, 9, 26, 0, 1, ready, building,
              (2 * (10 * ready) + building) // (2 * building) / 10 if building else None, ready < 2 * building]
    return json.dumps(dict(zip(sources.HISTORY_KEYS, values)))


# Ready stock against builders; the last day is below the board's goal (ready >= 2 x building).
BOARD = '\n'.join([board_row(d + 'T23:30:00Z', d, r, b) for d, r, b in
                   zip(DAYS, (22, 20, 24, 17, 19, 15, 11), (8, 9, 9, 10, 9, 8, 7))]) + '\n'
# Remaining balance samples: drops of 60, 85, 0 (a rise), 70 and 40; one span crosses PST midnight.
CREDITS = '\n'.join(json.dumps({'at': at, 'credits': used, 'credits_limit': 4000, 'extra_credits': 0,
                                'extra_credits_total': 0}) for at, used in [
    ('2030-01-12T14:00:00Z', 1000), ('2030-01-12T22:00:00Z', 1060), ('2030-01-13T06:00:00Z', 1145),
    ('2030-01-13T12:00:00Z', 1130), ('2030-01-13T20:00:00Z', 1200), ('2030-01-14T04:00:00Z', 1240)]) + '\n'


def metric(mid, group, label, value, unit, *, state='known', statistic='count', window=None, observed_at,
           ident=None, prerequisites=(), schema='synthetic.packet.v1', identities=('synthetic-1',)):
    """One synthetic metric in the suite's exact v1 metric shape."""
    dims = {'direction': None, 'pool': None, 'stage': None, 'ticket': None, 'cohort': 'synthetic'}
    dims.update(ident or {})
    return {'id': mid, 'group': group, 'label': label, 'state': state, 'value': value, 'unit': unit,
            'native_unit': unit, 'statistic': statistic,
            'window': window or {'since': '2030-01-13T08:00:00Z', 'until': '2030-01-14T08:00:00Z',
                                 'timezone': 'PST-fixed-UTC-08:00'},
            'observed_at': observed_at, 'fresh_until': None, 'freshness': 'unknown',
            'source': {'path': 'packet/' + mid.split(':')[0] + '.json', 'schema': schema,
                       'sha256': hashlib.sha256(mid.encode()).hexdigest()},
            'evidence': [LINK], 'sample': {'observed': len(identities), 'expected': len(identities),
                                           'identities': list(identities), 'numerator': None, 'denominator': None},
            'dimensions': dims, 'interval': None, 'prerequisites': list(prerequisites)}


def provider(slot, metrics, prerequisites=()):
    known = all(m['state'] == 'known' for m in metrics) and not prerequisites
    gaps = list(dict.fromkeys(list(prerequisites) + [p for m in metrics for p in m['prerequisites']]))
    return {'slot': slot, 'state': 'known' if known else 'partial', 'prerequisites': gaps, 'metrics': metrics}


def activity(at):
    hour = {'since': '2030-01-14T08:00:00Z', 'until': '2030-01-14T09:00:00Z', 'timezone': 'UTC'}
    return provider('activity', [
        metric('merged-hour-forward', 'throughput', 'Merged this UTC hour forward', 3, 'count', window=hour,
               observed_at=at, ident={'direction': 'forward'}, identities=('pr-4101', 'pr-4102', 'pr-4103')),
        metric('merged-hour-backwards', 'throughput', 'Merged this UTC hour backwards', 1, 'count', window=hour,
               observed_at=at, ident={'direction': 'backwards'}, identities=('pr-4104',)),
        metric('merged-hour-unknown', 'throughput', 'Merged this UTC hour with an unknown direction', None,
               'count', state='partial', window=hour, observed_at=at,
               ident={'direction': 'unknown'}, prerequisites=['Closing-ticket direction metadata is missing for one synthetic PR.'])])


def rework(at):
    week = {'since': '2030-01-07T08:00:00Z', 'until': '2030-01-14T08:00:00Z', 'timezone': 'PST-fixed-UTC-08:00'}
    return provider('rework', [
        metric('review-rounds', 'board', 'Independent review rounds over merged PRs', 14, 'count', window=week,
               observed_at=at),
        metric('fix-rounds', 'board', 'Fix rounds after CHANGES', 4, 'count', window=week, observed_at=at),
        metric('ci-reruns', 'board', 'CI reruns (counted apart from review rework)', 2, 'count', window=week,
               observed_at=at)])


def answer_time(at):
    week = {'since': '2030-01-07T08:00:00Z', 'until': '2030-01-14T08:00:00Z', 'timezone': 'PST-fixed-UTC-08:00'}
    return provider('answer_time', [
        metric('answer-median', 'decisions', 'Substantive answer time, median', 38, 'minutes', statistic='median',
               window=week, observed_at=at, identities=('request-1', 'request-2', 'request-3', 'request-4')),
        metric('answer-p90', 'decisions', 'Substantive answer time, p90', 212, 'minutes', statistic='p90',
               window=week, observed_at=at, identities=('request-1', 'request-2', 'request-3', 'request-4'))])


def main_ci(conclusion='failure'):
    head = 'b7' * 20
    run = {'id': 9123, 'run_attempt': 2, 'status': 'completed', 'conclusion': conclusion, 'head_sha': head,
           'head_branch': 'main', 'event': 'push', 'created_at': '2030-01-14T09:10:00Z'}
    api = 'repos/' + REPO

    def read(path):
        if path == api + '/branches/main':
            return {'name': 'main', 'commit': {'sha': head}}
        if path.startswith(api + '/actions/workflows/ci.yml/runs?'):
            return {'total_count': 1, 'workflow_runs': [copy.deepcopy(run)]}
        if path == api + '/actions/runs/9123':
            return copy.deepcopy(run)
        raise health.B.Fail('synthetic source unavailable')
    times = iter(['2030-01-14T09:50:00Z', '2030-01-14T09:50:04Z'])
    return health.main_ci(REPO, read, lambda: next(times))[0]


def ci_queue():
    jobs = [{'id': 701, 'run': 9124, 'attempt': 1, 'status': 'queued', 'pool': 'ubuntu-24.04'},
            {'id': 702, 'run': 9124, 'attempt': 1, 'status': 'queued', 'pool': 'ubuntu-24.04'},
            {'id': 703, 'run': 9125, 'attempt': 1, 'status': 'in_progress', 'pool': 'ubuntu-24.04'},
            {'id': 704, 'run': 9125, 'attempt': 1, 'status': 'in_progress', 'pool': 'ubuntu-slim'}]
    raw = {701: {'created_at': '2030-01-14T09:38:00Z'}, 702: {'created_at': '2030-01-14T09:46:00Z'},
           703: {'created_at': '2030-01-14T09:30:00Z'}, 704: {'created_at': '2030-01-14T09:31:00Z'}}
    return health.ci_queue(REPO, ['ubuntu-24.04', 'ubuntu-slim'], {'jobs': jobs}, raw,
                           '2030-01-14T09:50:00Z', '2030-01-14T09:50:20Z')[0]


def stage_health():
    read = {'started_at': '2030-01-14T09:50:00Z', 'ended_at': '2030-01-14T09:51:00Z'}
    tl1 = {'path': 'tools/factory-metrics/limits.conf', 'schema': 'closedwiz.factory-limits.v1', 'sha256': '1' * 64}
    tl2 = {'path': 'stage-waits.json', 'schema': 'openwiz.stage-waits.v1', 'sha256': '2' * 64}
    items = []
    for stage, minutes in (('builder_start', 30), ('reviewer_start', 45), ('merge', 60)):
        limit = {'minutes': minutes, 'owner': 'tools/factory-metrics/limits.conf',
                 'schema': 'closedwiz.factory-limits.v1', 'sha256': '1' * 64, 'read_at': '2030-01-14T09:51:00Z'}
        items.append(health.observation(
            'limit:' + stage, stage.replace('_', ' ').capitalize() + ' limit (TL1 setting)', state='known',
            statistic='limit', unit='minutes', value=minutes, read=read, source=tl1, point='2030-01-14T09:51:00Z',
            evidence=[LINK], evidence_class='settings_read', cohort='tl1-limits', identity={'stage': stage},
            limit=limit))
        for n, (result, state, value, gaps) in enumerate({
                'builder_start': [('not_missed', 'known', 12, ()), ('missed', 'partial', 41, ['Open at the TL2 read: a lower bound.'])],
                'reviewer_start': [('not_missed', 'known', 20, ()), ('gated', 'partial', None, ['TL2 gated: held.'])],
                'merge': [('not_missed', 'known', 33, ())]}[stage]):
            key = f'{stage}:p44{n}{len(stage)}:' + 'c3' * 20 + f':2030-01-14t0{n}:00:00z'
            items.append(health.observation(
                'wait:' + key, stage.replace('_', ' ').capitalize() + ' wait: ' + result.replace('_', ' '),
                state=state, statistic='observation', unit='minutes', result=result, value=value, read=read,
                source=tl2, point='2030-01-14T09:50:00Z', evidence=[LINK], evidence_class='producer_fact',
                cohort='tl2-stage-health', identity={'stage': stage, 'interval': key, 'ticket': 4100 + n},
                interval={'id': key, 'started_at': '2030-01-14T08:00:00Z',
                          'ended_at': '2030-01-14T08:20:00Z' if state == 'known' else None},
                limit=limit, identities=[key], prerequisites=gaps))
    return health.provider('stage_health', items, ['Synthetic stage history.'])


class World:
    def __init__(self, root):
        self.root, self.history = Path(root) / 'sources', Path(root) / 'history'
        self.root.mkdir(parents=True)
        self.previous = None

    def entry(self, kind, slot, name, text, observed_at):
        (self.root / name).write_text(text, encoding='utf-8')
        return {'kind': kind, 'slot': slot, 'path': name, 'sha256': hashlib.sha256(text.encode()).hexdigest(),
                'observed_at': observed_at, 'evidence': [LINK]}

    def sample(self, at, selection, extra=(), version=2):
        providers = sources.select(self.root, selection, at, self.previous) + list(extra)
        record = suite.compose(at, providers, assembled_at=at)
        if version == 1:
            record = {k: v for k, v in record.items() if k != 'health'}
            record['schema'] = suite.V1
            suite.validate(record)
        history.save(self.history, record)
        self.previous = record
        return record


def world(root):
    """(World, chart selections): the packet's history and its native board history."""
    w = World(root)
    codes = {'2030-01-07': (9, 11.0, 24.5, 15.5), '2030-01-08': (10, 10.5, 22.0, 15.0),
             '2030-01-09': (8, 9.5, 23.0, 14.0), '2030-01-11': (12, 9.0, 19.5, 13.5),
             '2030-01-12': (11, 8.5, 18.0, 13.0), '2030-01-13': (13, 8.0, 17.5, 12.5)}
    merged = {'2030-01-07': 28, '2030-01-08': 33, '2030-01-09': 30, '2030-01-11': 36, '2030-01-12': 41,
              '2030-01-13': 39}
    for day in DAYS:
        if day == '2030-01-10':
            continue  # no CI bench point that day: a visible gap, never zero
        at = _next(day) + 'T09:00:00Z'
        # The first day is the older first-job-created cohort, in a v1 sample.
        w.sample(at, [w.entry('ci_bench', 'ci_bench', day + '.json',
                              json.dumps(ci_point(day, merged[day], codes[day], current=day != DAYS[0])), at)],
                 version=1 if day == DAYS[0] else 2)
    # 2030-01-12 re-measured later the same morning: the latest observation is the one shown.
    w.sample('2030-01-13T11:00:00Z', [w.entry('ci_bench', 'ci_bench', '2030-01-12b.json',
                                              json.dumps(ci_point('2030-01-12', 42, (11, 8.5, 18.0, 13.0))),
                                              '2030-01-13T11:00:00Z')])
    final = '2030-01-14T09:55:00Z'
    journeys = (PUBLIC_ROOT / 'fixtures/journey/journeys.json').read_text(encoding='utf-8')
    w.sample(final, [w.entry('credits', 'credits', 'credits.jsonl', CREDITS, final),
                     w.entry('ci_bench', 'ci_bench', 'latest.json',
                             json.dumps(ci_point(DAYS[-1], merged[DAYS[-1]], codes[DAYS[-1]])), final),
                     w.entry('journey', 'journey', 'journeys.json', journeys, final)],
             extra=[activity(final), rework(final), answer_time(final), main_ci(), ci_queue(), stage_health()])
    board = w.entry('board_history', 'board', 'board-history.jsonl', BOARD, '2030-01-14T09:58:00Z')
    return w, [board]


# The edge packet (WRD3 R and the two granted renderer fixes): no board history and no CI bench,
# so cards 00a-00d have no numeric value at all, and dense hourly credit samples, the first span a
# legacy extra-credits-only seed, so 00e has many short spans with 30,000-scale drops.
def dense_credits():
    rows = [{'at': '2030-01-13T08:00:00Z', 'extra_credits': 50000, 'only': 'extra_credits'}]
    used = 10000
    for hour, drop in enumerate((31000, 0, 2500, 21500, 900, 1200, 0, 7300, 450, 12000, 3000, 600)):
        used += drop
        rows.append({'at': '2030-01-13T%02d:00:00Z' % (9 + hour), 'credits': used, 'credits_limit': 400000,
                     'extra_credits': 50000, 'extra_credits_total': 50000})
    return '\n'.join(json.dumps(r) for r in rows) + '\n'


def edge_world(root):
    w = World(root)
    at = '2030-01-14T09:55:00Z'
    w.sample(at, [w.entry('credits', 'credits', 'credits.jsonl', dense_credits(), at)])
    return w


def render_edge(out):
    """The edge packet's page and chart bundle (no natives selected)."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='war-room-edge-') as tmp:
        w = edge_world(tmp)
        bundle = native_build().build(w.history, at=AT, source_root=w.root, selections=[], out=out / 'charts')
        html = page.render(history.latest(w.history), charts=bundle)
    (out / 'page.html').write_text(html, encoding='utf-8')
    return html, bundle


def render(out):
    """The packet's page: the real chart build, then page.render over the latest sample."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='war-room-packet-') as tmp:
        w, natives = world(tmp)
        bundle = native_build().build(w.history, at=AT, source_root=w.root, selections=natives, out=out / 'charts')
        record = history.latest(w.history)
        html = page.render(record, charts=bundle)
    (out / 'page.html').write_text(html, encoding='utf-8')
    (out / 'packet.json').write_text(json.dumps({
        'schema': 'openwiz.war-room.page-packet.v1', 'built_at': AT, 'sample_at': record['sample_at'],
        'input_sha256': bundle['manifest']['input_sha256'],
        'page_sha256': hashlib.sha256(html.encode()).hexdigest()}, indent=2) + '\n', encoding='utf-8')
    return html, bundle, record


if __name__ == '__main__':
    render(sys.argv[1])
    print(sys.argv[1])
