#!/usr/bin/env python3
"""WRD2 (#630): build-time static SVG charts, proved at the generated SVG and values boundary.

A synthetic history is written through the real selection, composition and save path
(sources.select, suite.compose, history.save), then the real chart build runs the locked
Observable Plot under Node. Expected values are the fixture's own literals, never
recomputed the way the build computes them. Needs `npm ci --ignore-scripts` in
tools/war-room. No network, no live read.
"""
from collections import Counter
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import health  # noqa: E402
import history  # noqa: E402
import main  # noqa: E402
import page  # noqa: E402
import sources  # noqa: E402
import suite  # noqa: E402

REPO = 'synthetic-owner/work'
LINK = 'https://github.com/synthetic-owner/work/issues/4001'
BUILD_AT = '2030-01-08T10:00:00Z'
DAYS = ['2030-01-0%d' % d for d in range(1, 8)]
SVG = '{http://www.w3.org/2000/svg}'
CURRENT = 'workflow created to last job completed'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = load('war_room_charts_build', HERE / 'charts' / 'build.py')
palette = load('war_room_charts_palette', HERE / 'charts' / 'palette.py')
publish = load('war_room_publish', HERE / 'publish.py')


def cohort(runs, median, p90, robot):
    return {'rule': 'synthetic', 'runs': runs, 'robot_seconds': int(robot * 60 * runs),
            'robot_minutes_per_run': robot, 'prs_per_hour': 1.0,
            'categories': {k: 0 for k in ('web', 'setup', 'rust', 'build', 'skills')},
            'split': {'waiting': 0, 'setup': 0, 'running': 0},
            'queued_to_done': {'median': median, 'p90': p90, 'max': p90}}


def point(since, until, hours, merged, code=None, current=True):
    p = {'schema': 'closedwiz.ci-bench.v1', 'label': 'synthetic', 'since': since, 'until': until,
         'hours': hours, 'robots': 2, 'runs': 9, 'jobs': 18, 'merged_prs': merged,
         'merged_per_hour': round(merged / hours, 4), 'code_runs': None if code is None else cohort(*code),
         'legacy': None}
    if current:
        p['latency_basis'] = CURRENT
    return p


def day_point(day, merged, code=None, current=True):
    nxt = DAYS[DAYS.index(day) + 1] if day != DAYS[-1] else '2030-01-08'
    return point(day + 'T08:00:00Z', nxt + 'T08:00:00Z', 24, merged, code, current)


def board_row(at, day, ready, building, sample='run'):
    keys = sources.HISTORY_KEYS
    values = [sources.PLAN_LINKS, 'history', sample, at, day, REPO, 10, 4, 40, 0, 0, ready, building,
              (2 * (10 * ready) + building) // (2 * building) / 10 if building else None, ready < 2 * building]
    return json.dumps(dict(zip(keys, values)))


# The board's history: a synthetic baseline first (never plotted), two samples on 01-02
# (the later one is the daily row), a tie on 01-06 (the later line wins), 01-01 and 01-04 absent.
BOARD = '\n'.join([
    json.dumps(dict(zip(sources.HISTORY_KEYS, [sources.PLAN_LINKS, 'history', 'baseline', '2030-01-01T23:50:00Z',
                                                '2030-01-01', REPO, 80, 20, 25] + [None] * 6))),
    board_row('2030-01-02T10:00:00Z', '2030-01-02', 1, 1),
    board_row('2030-01-03T07:00:00Z', '2030-01-02', 3, 2),
    board_row('2030-01-03T12:00:00Z', '2030-01-03', 4, 2),
    board_row('2030-01-05T20:00:00Z', '2030-01-05', 2, 3),
    board_row('2030-01-06T21:00:00Z', '2030-01-06', 5, 2),
    board_row('2030-01-06T21:00:00Z', '2030-01-06', 6, 2),
    board_row('2030-01-08T07:30:00Z', '2030-01-07', 9, 4),
]) + '\n'

# Credit samples: the remaining balance (limit - used + extra) drops 30, 50, 0 (a rise counts 0), 20.
# The span 01-07T02:00Z -> 01-07T10:00Z crosses the PST midnight at 08:00Z.
CREDITS = '\n'.join(json.dumps({'at': at, 'credits': used, 'credits_limit': 1000, 'extra_credits': 0,
                                'extra_credits_total': 0}) for at, used in [
    ('2030-01-06T20:00:00Z', 100), ('2030-01-07T02:00:00Z', 130), ('2030-01-07T10:00:00Z', 180),
    ('2030-01-07T20:00:00Z', 170), ('2030-01-08T01:00:00Z', 190)]) + '\n'


def main_ci_provider(at, status='completed', conclusion='success'):
    """WRD1's own main_ci over a synthetic run at the head (a success unless told otherwise)."""
    head = 'a1' * 20
    run = {'id': 77, 'run_attempt': 1, 'status': status, 'conclusion': conclusion, 'head_sha': head,
           'head_branch': 'main', 'event': 'push', 'created_at': '2030-01-08T09:00:00Z'}
    api = 'repos/' + REPO

    def read(path):
        if path == api + '/branches/main':
            return {'name': 'main', 'commit': {'sha': head}}
        if path.startswith(api + '/actions/workflows/ci.yml/runs?'):
            return {'total_count': 1, 'workflow_runs': [copy.deepcopy(run)]}
        if path == api + '/actions/runs/77':
            return copy.deepcopy(run)
        raise health.B.Fail('synthetic source unavailable')
    times = iter(['2030-01-08T09:20:00Z', '2030-01-08T09:20:05Z'])
    provider, _ = health.main_ci(REPO, read, lambda: next(times))
    return provider


def stage_health_provider():
    """WRD1's own observation shapes: a loaded limit, a known wait, an open wait and a held one."""
    read = {'started_at': '2030-01-08T09:20:00Z', 'ended_at': '2030-01-08T09:21:00Z'}
    tl1 = {'path': 'tools/factory-metrics/limits.conf', 'schema': 'closedwiz.factory-limits.v1', 'sha256': '1' * 64}
    tl2 = {'path': 'stage-waits.json', 'schema': 'openwiz.stage-waits.v1', 'sha256': '2' * 64}
    limit = {'minutes': 30, 'owner': 'tools/factory-metrics/limits.conf', 'schema': 'closedwiz.factory-limits.v1',
             'sha256': '1' * 64, 'read_at': '2030-01-08T09:21:00Z'}

    def wait(key, result, state, value, gaps=()):
        return health.observation(
            'wait:' + key, 'Builder start wait: ' + result.replace('_', ' '), state=state, statistic='observation',
            unit='minutes', result=result, value=value, read=read, source=tl2, point='2030-01-08T09:20:00Z',
            evidence=[LINK], evidence_class='producer_fact', cohort='tl2-stage-health',
            identity={'stage': 'builder_start', 'interval': key, 'ticket': 4001},
            interval={'id': key, 'started_at': '2030-01-08T08:00:00Z',
                      'ended_at': '2030-01-08T08:12:00Z' if state == 'known' else None},
            limit=limit, identities=[key], prerequisites=gaps)
    items = [health.observation('limit:builder_start', 'Builder start limit (TL1 setting)', state='known',
                                statistic='limit', unit='minutes', value=30, read=read, source=tl1,
                                point='2030-01-08T09:21:00Z', evidence=[LINK], evidence_class='settings_read',
                                cohort='tl1-limits', identity={'stage': 'builder_start'}, limit=limit),
             wait('w1', 'not_missed', 'known', 12),
             wait('w2', 'missed', 'partial', 45, ['Open at the TL2 read: a lower bound.']),
             wait('w3', 'gated', 'partial', None, ['TL2 gated: held.']),
             wait('w4', 'gated', 'partial', None, ['TL2 gated: held.'])]
    return health.provider('stage_health', items, ['Synthetic stage history.'])


class World:
    """A synthetic source root and history, written through the real select/compose/save path."""

    def __init__(self, root):
        self.root, self.history = Path(root) / 'sources', Path(root) / 'history'
        self.root.mkdir(parents=True)
        self.previous = None

    def put(self, name, text):
        (self.root / name).write_text(text, encoding='utf-8')
        return hashlib.sha256(text.encode()).hexdigest()

    def entry(self, kind, slot, name, text, observed_at):
        return {'kind': kind, 'slot': slot, 'path': name, 'sha256': self.put(name, text),
                'observed_at': observed_at, 'evidence': [LINK]}

    def sample(self, at, selection, version=2, extra=()):
        providers = sources.select(self.root, selection, at, self.previous) + list(extra)
        moment = suite._time(at)
        sample_at = moment.replace(minute=moment.minute // 5 * 5, second=0).strftime('%Y-%m-%dT%H:%M:%SZ')
        record = suite.compose(sample_at, providers, assembled_at=at)
        if version == 1:
            record = {k: v for k, v in record.items() if k != 'health'}
            record['schema'] = suite.V1
            suite.validate(record)
        history.save(self.history, record)
        self.previous = record
        return record

    def ci(self, at, name, p):
        return self.sample(at, [self.entry('ci_bench', 'ci_bench', name, json.dumps(p), at)],
                           version=1 if at < '2030-01-04' else 2)


def full_world(root):
    w = World(root)
    w.ci('2030-01-02T09:00:00Z', 'd1.json', day_point('2030-01-01', 4, (3, 10.5, 20.0, 12.0), current=False))
    w.ci('2030-01-03T09:00:00Z', 'd2.json', day_point('2030-01-02', 6, (4, 9.0, 15.5, 11.0)))
    w.ci('2030-01-04T09:00:00Z', 'd3.json', day_point('2030-01-03', 2))
    for at in ('2030-01-06T09:00:00Z', '2030-01-06T09:05:00Z', '2030-01-06T09:10:00Z'):  # one point, three samples
        w.ci(at, 'd5.json', day_point('2030-01-05', 5, (5, 8.0, 14.0, 10.5)))
    w.ci('2030-01-07T09:00:00Z', 'd6a.json', day_point('2030-01-06', 3, (2, 6.0, 9.0, 9.0)))
    w.ci('2030-01-07T11:00:00Z', 'd6b.json', day_point('2030-01-06', 7, (4, 6.5, 9.5, 9.25)))
    w.ci('2030-01-07T13:00:00Z', 'hour.json', point('2030-01-07T12:00:00Z', '2030-01-07T13:00:00Z', 1, 1))
    w.ci('2030-01-08T09:00:00Z', 'd7.json', day_point('2030-01-07', 8, (6, 7.5, 12.0, 9.5)))
    # The last sample: credits and main CI only, so the CI point is carried forward as partial.
    w.sample('2030-01-08T09:30:00Z', [w.entry('credits', 'credits', 'credits.jsonl', CREDITS, '2030-01-08T09:30:00Z')],
             extra=[main_ci_provider('2030-01-08T09:30:00Z'), stage_health_provider()])
    board = w.entry('board_history', 'board', 'board-history.jsonl', BOARD, '2030-01-08T09:40:00Z')
    return w, [board]


def titles(svg):
    """Every mark title in a finished SVG, read independently of the build."""
    tree = ET.fromstring(svg)
    return Counter(t.text for t in tree.iter(SVG + 'title'))


def figure(bundle, fid):
    return next(f for f in bundle['figures'] if f['id'] == fid)


def by_day(fig, series):
    return {r['x']: r['y'] for r in fig['rows'] if r['series'] == series}


class Charts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='war-room-charts-'))
        cls.world, cls.natives = full_world(cls.tmp / 'full')
        cls.bundle = build.build(cls.world.history, at=BUILD_AT, source_root=cls.world.root,
                                 selections=cls.natives, out=cls.tmp / 'out')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_every_figure_draws_one_titled_mark_per_value_row(self):
        # catches: a renderer that drops a null row, draws a mark with no values row, or
        # titles marks differently from the table, so the picture and the table disagree.
        ids = [f['id'] for f in self.bundle['figures']]
        self.assertEqual(ids[:5], ['00a', '00b', '00c', '00d', '00e'])
        for fig in self.bundle['figures']:
            with self.subTest(fig['id']):
                self.assertEqual(titles(fig['svg']), Counter(r['label'] for r in fig['rows']))
                self.assertEqual(ET.fromstring(fig['svg']).get('aria-label'), fig['title'])

    def test_main_merges_are_native_days_once_each_with_gaps_kept(self):
        # catches: summing a point repeated over three samples, an hourly window or the
        # all-base UTC day counted as a main day, a re-measured day averaged, a missing
        # day drawn as zero, or a carried-forward copy replacing the known value.
        fig = figure(self.bundle, '00b')
        self.assertEqual(fig['domain'], DAYS)
        self.assertEqual(by_day(fig, 'merged'), {'2030-01-01': 4, '2030-01-02': 6, '2030-01-03': 2, '2030-01-04': None,
                                                 '2030-01-05': 5, '2030-01-06': 7, '2030-01-07': 8})
        states = {r['x']: r['state'] for r in fig['rows']}
        self.assertEqual(states['2030-01-04'], 'missing')
        self.assertEqual(states['2030-01-07'], 'known')
        self.assertEqual(fig['coverage'], {'observed': 6, 'expected': 7, 'missing': ['2030-01-04']})
        self.assertEqual(fig['window'], {'since': '2030-01-01T08:00:00Z', 'until': '2030-01-08T08:00:00Z',
                                         'timezone': 'PST-fixed-UTC-08:00'})
        carried = next(s for s in fig['sources'] if s['samples'][0] == '2030-01-06T09:00:00Z')
        self.assertEqual(carried['samples'], ['2030-01-06T09:00:00Z', '2030-01-06T09:05:00Z', '2030-01-06T09:10:00Z'])
        gaps = ' '.join(fig['gaps'])
        self.assertIn('2030-01-06: re-measured', gaps)
        self.assertIn('1 window that is not a full native PST day', gaps)

    def test_ci_latency_keeps_each_cohort_and_native_quantile(self):
        # catches: the older first-job cohort joined into the current line, a re-measured
        # day's medians averaged (6.25) instead of its latest observation (6.5), or a day
        # without successful code runs drawn as zero.
        fig = figure(self.bundle, '00c')
        current = 'median|workflow-created-to-last-job-completed'
        older = 'median|first-job-created-to-last-job-completed'
        self.assertEqual(by_day(fig, current), {'2030-01-01': None, '2030-01-02': 9.0, '2030-01-03': None,
                                                '2030-01-04': None, '2030-01-05': 8.0, '2030-01-06': 6.5,
                                                '2030-01-07': 7.5})
        self.assertEqual({d: v for d, v in by_day(fig, older).items() if v is not None}, {'2030-01-01': 10.5})
        self.assertEqual(by_day(fig, 'p90|workflow-created-to-last-job-completed')['2030-01-06'], 9.5)
        self.assertEqual({s['key']: s['role'] for s in fig['series']}[older], 'older')
        label = next(r['label'] for r in fig['rows'] if r['series'] == current and r['x'] == '2030-01-05')
        self.assertIn('5 successful code runs', label)

    def test_runner_time_names_its_denominator(self):
        # catches: runner minutes shown without the per-successful-code-run denominator.
        fig = figure(self.bundle, '00d')
        self.assertEqual(fig['unit'], 'robot_minutes_per_code_run')
        row = next(r for r in fig['rows'] if r['x'] == '2030-01-07')
        self.assertEqual(row['y'], 9.5)
        self.assertIn('per successful code run (6 successful code runs)', row['label'])

    def test_ready_and_building_use_the_board_daily_row_and_its_goal(self):
        # catches: the synthetic baseline plotted, a day's first sample used instead of its
        # last, a tie resolved to the earlier line, or a day without a row drawn as zero.
        fig = figure(self.bundle, '00a')
        self.assertEqual(by_day(fig, 'ready'), {'2030-01-01': None, '2030-01-02': 3, '2030-01-03': 4,
                                                '2030-01-04': None, '2030-01-05': 2, '2030-01-06': 6,
                                                '2030-01-07': 9})
        self.assertEqual(by_day(fig, 'building')['2030-01-07'], 4)
        self.assertEqual(by_day(fig, 'goal')['2030-01-05'], 6)
        self.assertEqual(fig['coverage']['missing'], ['2030-01-01', '2030-01-04'])
        self.assertEqual(fig['sources'][0]['sha256'], self.natives[0]['sha256'])

    def test_credit_spans_keep_their_actual_length_and_are_never_split(self):
        # catches: a span cut at the PST midnight, spans summed into an invented daily
        # billing total, the sampled/not-billing qualification dropped, or a coverage that
        # counts spans against days (R4: "4 of 7" when only 2 days were observed).
        fig = figure(self.bundle, '00e')
        spans = [(r['x'], r['x2'], r['y']) for r in fig['rows'] if r['state'] != 'missing']
        self.assertEqual(spans, [('2030-01-06T20:00:00Z', '2030-01-07T02:00:00Z', 30),
                                 ('2030-01-07T02:00:00Z', '2030-01-07T10:00:00Z', 50),
                                 ('2030-01-07T10:00:00Z', '2030-01-07T20:00:00Z', 0),
                                 ('2030-01-07T20:00:00Z', '2030-01-08T01:00:00Z', 20)])
        crossing = next(r for r in fig['rows'] if r['x'] == '2030-01-07T02:00:00Z')
        self.assertIn('crosses a PST midnight', crossing['label'])
        self.assertIn('8 h', crossing['label'])
        self.assertIn('not billing', fig['caption'])
        self.assertEqual(fig['coverage']['missing'], DAYS[:5])
        # R4: four spans end on two PST days; coverage counts days, never spans against days.
        self.assertEqual(fig['coverage']['observed'], 2)

    def test_body_figures_cover_readiness_health_and_old_samples(self):
        # catches: a v1 sample's missing health read as a green main CI, a provider left
        # out of the readiness inventory, an open wait shown as complete or a held wait as
        # zero, a limits figure the renderer cannot draw, or two held waits on one stage
        # sharing a label so the whole build refuses (R3).
        ready = figure(self.bundle, 'body-readiness')
        self.assertEqual(len(ready['rows']), 20)
        main_ci = figure(self.bundle, 'body-main-ci')
        self.assertEqual([(r['state'], r['x']) for r in main_ci['rows']], [('known', 'main')])
        self.assertIn('success', main_ci['rows'][0]['label'])
        self.assertIn('a1a1a1a', main_ci['rows'][0]['label'])
        stage = figure(self.bundle, 'body-stage-health')
        rows = {r['key']: (r['series'], r['y'], r['state']) for r in stage['rows']}
        self.assertEqual(rows, {'limit:builder_start': ('limit', 30, 'known'), 'wait:w1': ('wait', 12, 'known'),
                                'wait:w2': ('wait', 45, 'partial'), 'wait:w3': ('wait', None, 'partial'),
                                'wait:w4': ('wait', None, 'partial')})
        self.assertIn('at least 45 min', next(r['label'] for r in stage['rows'] if r['key'] == 'wait:w2'))
        with tempfile.TemporaryDirectory() as d:
            old = World(d)
            old.ci('2030-01-02T09:00:00Z', 'd1.json', day_point('2030-01-01', 4))
            row = figure(build.build(old.history, at=BUILD_AT), 'body-main-ci')['rows'][0]
            self.assertEqual(row['state'], 'unavailable')
            self.assertIn(suite.PREDATES, row['label'])

    def test_pages_and_svgs_carry_no_chart_runtime_and_escape_text(self):
        # catches: a chart script, module, font, image or fetch reaching the page, or an
        # untrusted label becoming markup inside the SVG or the values table.
        with tempfile.TemporaryDirectory() as d:
            w = World(d)
            evil = {'slot': 'eb7', 'state': 'partial', 'prerequisites': ['synthetic'], 'metrics': [
                sources.metric({'observed_at': '2030-01-02T09:00:00Z', 'path': 'eb6.json', 'sha256': '0' * 64,
                                'evidence': [LINK]}, 'synthetic.v1', 'x', 'board',
                               '<script>alert(1)</script> & co', 2, 'count',
                               sources.window('2030-01-01T00:00:00Z', '2030-01-02T00:00:00Z'), state='partial',
                               prerequisites=['synthetic'])]}
            record = w.sample('2030-01-02T09:00:00Z', [], extra=[evil])
            bundle = build.build(w.history, at=BUILD_AT)
            html = page.render(record, charts=bundle)
        start = html.index('<section id="figures">')
        figures = html[start:html.index('</section>', start)]
        for banned in ('<script', 'src=', '<link', 'url(', '@import', 'fetch(', '<foreignobject', '<image', 'href='):
            self.assertNotIn(banned, figures.lower())
        self.assertNotRegex(figures, r'\son[a-z]+=')
        self.assertIn('‹script›alert(1)‹/script› &amp; co', figures)
        for fig in bundle['figures']:
            names = {e.tag.removeprefix(SVG) for e in ET.fromstring(fig['svg']).iter()}
            self.assertLessEqual(names, {'svg', 'g', 'path', 'line', 'rect', 'circle', 'text', 'tspan', 'title'})
        self.assertEqual(html.count('<svg '), len(bundle['figures']))

    def test_the_svg_check_refuses_planted_breaks(self):
        # catches: an allowlist or reconciliation that passes everything, so a script, an
        # event handler, an external reference, an undrawable position or a dropped mark
        # would reach the page.
        fig = figure(self.bundle, '00b')
        good = fig['svg']
        build.check_svg(good, fig)
        first_title = '<title>%s</title>' % fig['rows'][0]['label']
        planted = {
            'script': good.replace('</svg>', '<script>alert(1)</script></svg>'),
            'handler': good.replace('<svg ', '<svg onload="alert(1)" ', 1),
            'href': good.replace('</svg>', '<a href="https://example.invalid/">x</a></svg>'),
            'url': good.replace('fill="#101722"', 'fill="url(https://example.invalid/p)"', 1),
            'nan': good.replace('<svg ', '<svg x="NaN" ', 1),
            'dropped mark': good.replace(first_title, '', 1),
            'renamed': good.replace('aria-label="Main merges"', 'aria-label="Other"', 1),
        }
        for name, svg in planted.items():
            with self.subTest(name):
                self.assertNotEqual(svg, good)
                with self.assertRaises(ValueError):
                    build.check_svg(svg, fig)

    def test_same_input_builds_the_same_bytes_used_by_page_and_export(self):
        # catches: a nondeterministic id or time in the output, or the page and the image
        # export drawing two different renders of one figure.
        again = build.build(self.world.history, at=BUILD_AT, source_root=self.world.root, selections=self.natives)
        self.assertEqual([f['svg'] for f in again['figures']], [f['svg'] for f in self.bundle['figures']])
        self.assertEqual(again['manifest'], self.bundle['manifest'])
        html = page.render(history.latest(self.world.history), charts=self.bundle)
        out = self.tmp / 'out'
        for fig in self.bundle['figures']:
            written = (out / (fig['id'] + '.svg')).read_text(encoding='utf-8')
            self.assertEqual(written, fig['svg'])
            self.assertIn(written, html)
            entry = next(m for m in self.bundle['manifest']['figures'] if m['id'] == fig['id'])
            self.assertEqual(entry['svg_sha256'], hashlib.sha256(written.encode()).hexdigest())
        self.assertEqual(json.loads((out / 'values.json').read_text())['figures'][1]['rows'],
                         figure(self.bundle, '00b')['rows'])

    def test_the_png_drawing_accepts_a_page_with_charts(self):
        # catches: chart markup that breaks publish.drawable's one-style/one-details shape
        # check, so an hourly publication with figures would refuse to draw.
        html = page.render(history.latest(self.world.history), charts=self.bundle)
        for phone in (False, True):
            drawn = publish.drawable(html, phone)
            self.assertEqual(drawn.count('<svg '), len(self.bundle['figures']))

    def test_bad_native_input_refuses_the_whole_build(self):
        # catches: a tampered, escaping, late or malformed native artifact drawn anyway.
        board = self.natives[0]
        bad_row = BOARD.replace('"ready_stock": 9', '"ready_stock": -1')
        (self.world.root / 'bad.jsonl').write_text(bad_row)
        cases = {'hash': dict(board, sha256='f' * 64),
                 'escape': dict(board, path='../full/sources/board-history.jsonl'),
                 'late': dict(board, observed_at='2030-01-09T00:00:00Z'),
                 'row': dict(board, path='bad.jsonl', sha256=hashlib.sha256(bad_row.encode()).hexdigest()),
                 'kind': dict(board, kind='ci_bench')}
        for name, entry in cases.items():
            with self.subTest(name), self.assertRaises(ValueError):
                build.build(self.world.history, at=BUILD_AT, source_root=self.world.root, selections=[entry])

    def test_a_failed_chart_build_keeps_the_last_good_page_and_samples(self):
        # catches: a chart failure that replaces the last good page or touches saved samples.
        with tempfile.TemporaryDirectory() as d:
            w, natives = full_world(Path(d) / 'w')
            page_path = Path(d) / 'page' / 'page.html'
            good = lambda root: build.build(root, at=BUILD_AT, source_root=w.root, selections=natives)  # noqa: E731
            read = lambda at, previous: sources.select(w.root, [], at, previous)  # noqa: E731
            main.tick('2030-01-08T09:50:00Z', w.history, page_path, read, charts=good)
            before_page = page_path.read_bytes()
            self.assertIn(b'<section id="figures">', before_page)
            before = {p.name: p.read_bytes() for p in (w.history / 'samples').glob('*.json')}
            broken = [dict(natives[0], sha256='f' * 64)]
            bad = lambda root: build.build(root, at=BUILD_AT, source_root=w.root, selections=broken)  # noqa: E731
            with self.assertRaises(ValueError):
                main.tick('2030-01-08T09:55:00Z', w.history, page_path, read, charts=bad)
            self.assertEqual(page_path.read_bytes(), before_page)
            after = {p.name: p.read_bytes() for p in (w.history / 'samples').glob('*.json')}
            self.assertEqual({k: after[k] for k in before}, before)

    def test_a_refused_chart_build_publishes_nothing(self):
        # catches: an hourly publication that pushes a page, pictures or sample after its
        # chart build refused (here: Node, the build prerequisite, is absent), replacing the
        # war-room branch's last good render.
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            origin = d / 'origin.git'
            subprocess.run(['git', 'init', '-q', '--bare', str(origin)], check=True)
            w = World(d / 'w')
            point = json.dumps(day_point('2030-01-07', 8, (6, 7.5, 12.0, 9.5)))
            ci = w.entry('ci_bench', 'ci_bench', 'd7.json', point, '2030-01-08T09:00:00Z')
            board = w.entry('board_history', 'board', 'board-history.jsonl', BOARD, '2030-01-08T09:40:00Z')
            env = dict(os.environ, PATH=str(HERE / 'fixtures' / 'publish') + os.pathsep + os.environ['PATH'])

            # A PATH with git, python3 and the fake chromium, but no node.
            bare = d / 'bin'
            bare.mkdir()
            (bare / 'git').symlink_to(shutil.which('git'))
            (bare / 'python3').symlink_to(sys.executable)
            no_node = dict(env, PATH=str(HERE / 'fixtures' / 'publish') + os.pathsep + str(bare))

            def run(at, selection, env=env):
                (d / 'selection.json').write_text(json.dumps(selection))
                return subprocess.run([sys.executable, '-I', str(HERE / 'publish.py'), 'publish', '--remote', str(origin),
                                       '--at', at, '--source-root', str(w.root), '--selection', str(d / 'selection.json')],
                                      env=env, capture_output=True, text=True)

            def head():
                return subprocess.run(['git', '-C', str(origin), 'rev-parse', 'refs/heads/war-room'],
                                      capture_output=True, text=True).stdout.strip()
            good = run('2030-01-08T10:00:00Z', [ci, board])
            self.assertEqual(good.returncode, 0, good.stderr)
            before = head()
            bad = run('2030-01-08T11:00:00Z', [ci, board], env=no_node)
            self.assertEqual(bad.returncode, 1)
            self.assertIn('the chart build refused', bad.stderr)
            self.assertEqual(head(), before)

    def test_main_ci_result_is_visible_without_hover(self):
        # catches (R1): success, failure, pending and cancelled drawn as the same "known"
        # cell, so a picture of a failing or pending main looks green.
        shapes = {}
        for status, conclusion, word in (('completed', 'success', 'success'), ('completed', 'failure', 'failure'),
                                         ('in_progress', None, 'pending'), ('completed', 'cancelled', 'cancelled')):
            with self.subTest(word), tempfile.TemporaryDirectory() as d:
                w = World(d)
                w.sample('2030-01-08T09:30:00Z', [], extra=[main_ci_provider('2030-01-08T09:30:00Z', status, conclusion)])
                tree = ET.fromstring(figure(build.build(w.history, at=BUILD_AT), 'body-main-ci')['svg'])
                for parent in tree.iter():
                    for child in [c for c in parent if c.tag == SVG + 'title']:
                        parent.remove(child)
                visible = [''.join(e.itertext()) for e in tree.iter(SVG + 'text')]
                self.assertIn(word, visible)
                shapes[word] = ET.tostring(tree)
        self.assertEqual(len(set(shapes.values())), 4)

    def test_a_gathered_projected_board_feeds_ready_and_building(self):
        # catches (R2): gather selects the board as a projected provider over its raw
        # history (its ratios citing graph.json), and the chart build ignored it, so 00a
        # was Unknown on the normal gathered publication.
        import test_gather
        case = test_gather.Gather()
        case.setUp()
        try:
            root, selection = case.gather()
            self.assertEqual([s['kind'] for s in selection if s['slot'] == 'board'], ['projected'])
            board = next(json.loads((root / s['path']).read_text()) for s in selection if s['slot'] == 'board')
            counts = {m['id']: m['value'] for m in board['metrics'] if m['id'] in ('ready-stock', 'builders-running')}
            build_chart = publish.chart_builder(root, case.tmp / 'out' / 'selection.json', test_gather.PUBLISH_AT)
            fig = figure(build_chart(case.tmp / 'no-history'), '00a')
            latest = fig['domain'][-1]
            self.assertEqual((by_day(fig, 'ready')[latest], by_day(fig, 'building')[latest]),
                             (counts['ready-stock'], counts['builders-running']))
            self.assertEqual(fig['sources'][0]['path'], 'board/history.jsonl')
            # The projected provider pins the raw bytes: changed raw history still refuses.
            (root / 'board' / 'history.jsonl').write_text((root / 'board' / 'history.jsonl').read_text() + '\n')
            with self.assertRaises(publish.Fail):
                build_chart(case.tmp / 'no-history')
        finally:
            case.doCleanups()

    def test_credit_seed_spans_keep_their_extra_only_basis(self):
        # catches (R5): an extra-only seed span merged into the full-balance series, so an
        # unchanged extra balance reads as zero overall credit burn.
        rows = [{'at': '2030-01-07T00:00:00Z', 'extra_credits': 100, 'only': 'extra_credits'},
                {'at': '2030-01-07T06:00:00Z', 'credits': 800, 'credits_limit': 1000, 'extra_credits': 100,
                 'extra_credits_total': 100},
                {'at': '2030-01-07T12:00:00Z', 'credits': 850, 'credits_limit': 1000, 'extra_credits': 100,
                 'extra_credits_total': 100}]
        with tempfile.TemporaryDirectory() as d:
            w = World(d)
            text = '\n'.join(map(json.dumps, rows)) + '\n'
            w.sample('2030-01-08T09:30:00Z', [w.entry('credits', 'credits', 'credits.jsonl', text, '2030-01-08T09:30:00Z')])
            fig = figure(build.build(w.history, at=BUILD_AT), '00e')
        spans = {r['x']: (r['series'], r['y']) for r in fig['rows'] if r['state'] != 'missing'}
        self.assertEqual(spans, {'2030-01-07T00:00:00Z': ('drop:extra-only', 0),
                                 '2030-01-07T06:00:00Z': ('drop:full-balance', 50)})
        seed = next(r for r in fig['rows'] if r['x'] == '2030-01-07T00:00:00Z')
        self.assertIn('extra-only seed; overall balance change unknown', seed['label'])
        self.assertIn('Extra-only seed spans compare extra credits only', ' '.join(fig['gaps']))

    def test_the_palette_survives_colour_vision_simulation(self):
        # catches: a validator that never simulates: red and green differ to normal
        # vision but merge under deuteranopia, so they must fail.
        result = palette.check(palette.load())
        self.assertTrue(result['pass'], result)
        self.assertEqual(set(result['simulations']), {'normal', 'protanopia', 'deuteranopia', 'tritanopia'})
        bad = palette.check({'ground': '#101722', 'roles': {'a': '#d62728', 'b': '#2ca02c'}})
        self.assertTrue(bad['simulations']['normal']['pass'])
        self.assertFalse(bad['simulations']['deuteranopia']['pass'])
        kept = json.loads((HERE / 'fixtures' / 'charts' / 'palette-check.json').read_text())
        self.assertEqual(kept, result)

    def test_charts_survive_a_browser_without_scripts_or_network(self):
        # catches: figures that need JavaScript or a network read to show their marks,
        # labels and tables. A real browser with every host unresolvable loads the page under
        # its own CSP; a planted canary script proves no script runs there.
        html = page.render(history.latest(self.world.history), charts=self.bundle)
        self.assertIn("default-src 'none'", html)
        self.assertNotIn('script-src', html)
        canary = html.replace('</body>', '<script>document.body.dataset.ran="yes"</script></body>')
        with tempfile.TemporaryDirectory(prefix='war-room-charts-browser-') as d:
            path = Path(d) / 'page.html'
            path.write_text(canary, encoding='utf-8')
            dom = subprocess.run([publish.chromium(), '--headless=new', '--no-sandbox', '--disable-gpu',
                                  '--user-data-dir=' + os.path.join(d, 'profile'),
                                  '--host-resolver-rules=MAP * ~NOTFOUND', '--proxy-server=127.0.0.1:9',
                                  '--window-size=390,844', '--dump-dom', path.as_uri()],
                                 check=True, capture_output=True, text=True, timeout=90).stdout
        self.assertIn('<svg', dom)
        self.assertNotIn('data-ran', dom)
        for fig in self.bundle['figures']:
            with self.subTest(fig['id']):
                self.assertIn('aria-label="%s"' % fig['title'].replace('&', '&amp;'), dom)
                self.assertIn('id="figure-%s"' % fig['id'], dom)
        self.assertEqual(dom.count('<svg'), len(self.bundle['figures']))
        self.assertEqual(dom.count('<table class="values"'), len(self.bundle['figures']))

if __name__ == '__main__':
    unittest.main()
