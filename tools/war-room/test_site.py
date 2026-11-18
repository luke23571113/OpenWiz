#!/usr/bin/env python3
"""WRD5 (#883), P10: the War room as a small static site (home and five child pages).

The frozen synthetic packet (fixtures/page-design/packet.py) is built through the real
select/compose/save path and the real chart build; `page.site` renders the six pages from that
one saved sample and bundle. Expected values are the packet's own literals. Synthetic data only;
no network, no live read. Needs `npm ci --ignore-scripts` in tools/war-room and Node.
"""
import copy
import importlib.util
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import history  # noqa: E402
import page  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'collector'))
import suite  # noqa: E402

ROUTES = ['', 'speed', 'health', 'cost', 'quality', 'skills']
CARDS = ['00a', '00b', '00c', '00d', '00e']
# Each bench and health signal's one child page (the spec's page questions, #883).
BENCH_PAGE = {'activity': 'speed', 'journey': 'speed', 'ci_bench': 'speed', 'board': 'speed', 'answer_time': 'speed',
              'decisions': 'speed', 'main_ci': 'health', 'ci_queue': 'health', 'stage_health': 'health',
              'stage_waits': 'health', 'credits': 'cost', 'factory_metrics': 'cost', 'claude_usage': 'cost',
              'cost': 'cost', 'rework': 'quality', 'skills_eval': 'skills', 'eb6': 'skills', 'eb7': 'skills',
              'eb8': 'skills', 'eb9': 'skills'}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


packet = load('wrd5_packet', HERE / 'fixtures' / 'page-design' / 'packet.py')


def build(tmp):
    """The packet's saved sample and chart bundle, as packet.render builds them."""
    w, natives = packet.world(tmp)
    bundle = packet.native_build().build(w.history, at=packet.AT, source_root=w.root, selections=natives,
                                         out=Path(tmp) / 'charts')
    return history.latest(w.history), bundle


def outside_details(fragment):
    return re.sub(r'<details.*?</details>', '', fragment, flags=re.S)


def figures(html):
    """{figure id: its HTML} for every <figure> on a page."""
    return {m.group(1): html[m.start():html.index('</figure>', m.start())]
            for m in re.finditer(r'<figure class="[^"]*" id="fig-([\w-]+)"', html)}


def rows(home):
    body = home[home.index('id="benchmarks"'):]
    body = body[:body.index('</table>')]
    return re.findall(r'<tr class="row"><td class="name"><a href="([^"]*)">([^<]*)</a></td>'
                      r'<td class="state"><span[^>]*>([^<]*)</span></td><td class="v">([^<]*)</td></tr>', body)


class Site(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='war-room-site-'))
        cls.record, cls.bundle = build(cls.tmp)
        cls.site = page.site(cls.record, charts=cls.bundle)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_six_pages_place_every_figure_chart_and_benchmark_once(self):
        # catches: a seventh or missing page, a body figure on no page or two, a home card copied onto a
        # child, a chart the build drew that the site never shows (or shows twice), or a bench's values
        # and evidence on no child page, on two, or on the home page.
        self.assertEqual(list(self.site), ROUTES)
        placed = {route: list(figures(html)) for route, html in self.site.items()}
        self.assertEqual(placed[''], CARDS)
        body = [f['figure'] for s in page.INVENTORY['sections'] for f in s['figures']]
        children = [n for r in ROUTES[1:] for n in placed[r]]
        self.assertEqual(sorted(children), sorted(body))
        for chart in self.bundle['figures']:
            where = [r for r, html in self.site.items() if chart['svg'] in html]
            self.assertEqual(len(where), 1, chart['id'])
            self.assertEqual(self.site[where[0]].count(chart['svg']), 1, chart['id'])
        for slot, route in BENCH_PAGE.items():
            self.assertEqual([r for r, html in self.site.items() if f'id="bench-{slot}"' in html], [route], slot)
        self.assertEqual(len(BENCH_PAGE), len(suite.PROVIDERS) + len(suite.HEALTH))
        # The chart seam holds on every page: no link inside a figures section.
        for route, html in self.site.items():
            start = html.index('<section id="figures">')
            self.assertNotIn('href=', html[start:html.index('</section>', start)], route)

    def test_a_benchmark_or_figure_without_a_page_is_refused(self):
        # catches: a new figure or bench added to the inventory without page membership being
        # silently left off the site, or a figure claimed by two pages.
        cases = {}
        inv = copy.deepcopy(page.INVENTORY)
        inv['pages'][0]['figures'].remove('01')
        cases['figure on no page'] = inv
        inv = copy.deepcopy(page.INVENTORY)
        inv['pages'][1]['figures'].append('01')
        cases['figure on two pages'] = inv
        inv = copy.deepcopy(page.INVENTORY)
        del inv['cards'][4]['page']
        cases['card bench with no page'] = inv
        inv = copy.deepcopy(page.INVENTORY)
        inv['cards'][4]['providers'] = []
        cases['bench with no figure'] = inv
        for name, inv in cases.items():
            with self.subTest(name), mock.patch.object(page, 'INVENTORY', inv), self.assertRaises(ValueError):
                page.site(self.record, charts=self.bundle)

    def test_home_lists_every_benchmark_worst_first(self):
        # catches: rows ordered by name or inventory alone, an unavailable bench shown as zero or as
        # healthy, a measured bench with no limit read as off limit, a tie order that moves between
        # builds, or a row whose link lands nowhere. Packet literals: main CI failed, one stage wait
        # missed its limit and ready (11) is below twice building (7).
        got = rows(self.site[''])
        self.assertEqual([(name, state, value) for _, name, state, value in got], [
            ('Board', 'off limit', '11 / 7'),
            ('Main CI', 'off limit', 'Failure'),
            ('Stage health', 'off limit', '1 of 4 waits over limit'),
            ('Current activity', 'partial', '3 merged forward this hour'),
            ('Ticket journeys', 'partial', '19 h'),
            ('Credits', 'partial', '40 credits / 8 h'),
            ('CI queue', 'partial', '2 queued'),
            ('CI bench', 'healthy', '1.6 merged PRs/h'),
            ('Orchestrator answer time', 'healthy', '38 min median'),
            ('Rework rate', 'healthy', '14 review rounds'),
            *[(page.NAMES[s], 'not measured', 'Unavailable') for s in (
                'stage_waits', 'factory_metrics', 'skills_eval', 'cost', 'claude_usage', 'decisions',
                'eb6', 'eb7', 'eb8', 'eb9')]])
        slots = {page.NAMES[s]: s for s in BENCH_PAGE}
        for href, name, _, _ in got:
            self.assertEqual(href, f'{BENCH_PAGE[slots[name]]}#bench-{slots[name]}')
        # A real zero stays a measured zero; an unknown value never becomes one.
        record = copy.deepcopy(self.record)
        rework = next(p for p in record['providers'] if p['slot'] == 'rework')
        next(m for m in rework['metrics'] if m['id'] == 'review-rounds')['value'] = 0
        answer = next(p for p in record['providers'] if p['slot'] == 'answer_time')
        answer.update(state='partial', prerequisites=['A synthetic median read.'])
        next(m for m in answer['metrics'] if m['id'] == 'answer-median').update(
            state='unavailable', value=None, prerequisites=['A synthetic median read.'])
        got = {name: (state, value) for _, name, state, value in rows(page.site(record, charts=self.bundle)[''])}
        self.assertEqual(got['Rework rate'], ('healthy', '0 review rounds'))
        self.assertEqual(got['Orchestrator answer time'], ('partial', 'Unknown'))

    def test_row_states_follow_each_producers_own_results(self):
        # catches (#926 R1, R2): a measured stage-limit miss (fix or answer stage, which stage health
        # does not cover) left as merely partial, a zero miss count read as a breach, and a
        # pending or cancelled main CI run, with no current result, labelled healthy. Real producers on
        # their own synthetic fixtures: TL2's stage waits and the main-CI collector's runs. A stage whose
        # measured misses are all zero is not off limit.
        stage = load('wrd5_stage_proof', HERE / 'test_stage_waits.py')
        case = stage.StageWaits()
        case.setUp()
        try:
            provider = case.provider()
        finally:
            case.doCleanups()
        misses = {m['dimensions']['stage']: m['value'] for m in provider['metrics'] if m['id'].startswith('miss:')}
        self.assertTrue(misses.get('fix_after_changes') and misses.get('builder_question_answer'), misses)
        row = lambda record, slot: next((st, v) for _, n, st, v in rows(page.site(record)['']) if n == page.NAMES[slot])  # noqa: E731
        with self.subTest('measured stage misses'):
            self.assertEqual(row(suite.compose(stage.AT, [provider], assembled_at=stage.AT), 'stage_waits')[0], 'off limit')
        cleared = copy.deepcopy(provider)
        for m in cleared['metrics']:
            if m['id'].startswith('miss:'):
                m['value'] = 0
        with self.subTest('no measured miss'):
            self.assertEqual(row(suite.compose(stage.AT, [cleared], assembled_at=stage.AT), 'stage_waits')[0], 'partial')
        health = load('wrd5_health_proof', HERE / 'test_health.py')
        for status, conclusion, want in (('completed', 'success', ('healthy', 'Success')),
                                         ('completed', 'failure', ('off limit', 'Failure')),
                                         ('in_progress', None, ('partial', 'Pending')),
                                         ('completed', 'cancelled', ('partial', 'Cancelled'))):
            with self.subTest(conclusion or status):
                main, _ = health.health().main_ci(health.REPO, health.main_world(
                    listed=[health.run(501, status=status, conclusion=conclusion)]), health.Clock('2030-03-01T12:05:01Z'))
                record = suite.compose('2030-03-01T12:05:00Z', [main], assembled_at='2030-03-01T12:09:00Z')
                self.assertEqual(row(record, 'main_ci'), want)
        self.assertEqual(row(suite.compose('2030-03-01T12:05:00Z'), 'main_ci'), ('not measured', 'Unavailable'))

    def test_each_figure_face_is_title_sentence_and_value_with_facts_behind_its_disclosure(self):
        # catches: dates, coverage, missing days, gap notes, unit notes or provenance left on a figure's
        # face, or moved behind its disclosure and lost; an unavailable figure that stops saying so.
        charts = {c['id']: c for c in self.bundle['figures']}
        inventory = {f['figure']: f for s in page.INVENTORY['sections'] for f in s['figures']}
        inventory.update({c['figure']: c for c in page.INVENTORY['cards']})
        for route, html in self.site.items():
            for number, fig in figures(html).items():
                with self.subTest(route=route, figure=number):
                    face = outside_details(fig)
                    entry = inventory[number]
                    self.assertIn(page.esc(entry['caption']), face)
                    words = re.sub(r'<svg.*?</svg>|<figcaption.*?</figcaption>', '', face, flags=re.S)
                    self.assertNotIn('class="meta"', words)
                    self.assertNotRegex(words, r'coverage [0-9]+ of|SHA-256|PST|Value as of|Gap')
                    self.assertNotIn('<details', face)
                    self.assertEqual(fig.count('<details'), fig.count('</details>'))
                    self.assertLessEqual(fig.count('<details'), 1)
                    shown = [charts[i] for i in re.findall(r'id="figure-([\w-]+)"', fig)]
                    if not shown:
                        self.assertIn('Unavailable', face)
                        need = page.esc(entry.get('prerequisite') or page.NO_BUILD)
                        self.assertIn(need, face if len(entry.get('prerequisite') or '') <= page.SHORT else fig)
                    hidden = fig[fig.index('<details'):] if shown else ''
                    for f in shown:
                        self.assertIn(f['svg'], face)
                        self.assertIn(page._unit(f), hidden)
                        self.assertIn(f"coverage {f['coverage']['observed']} of", hidden)
                        for day in f['coverage']['missing']:
                            self.assertIn(day, hidden)
                        for gap in f['gaps']:
                            self.assertIn(page.esc(gap), hidden)
        # The packet's dated cards keep their own window and stamp, behind the disclosure.
        card = figures(self.site[''])['00b']
        self.assertIn('2030-01-07 to 2030-01-13 PST', card)
        self.assertNotIn('2030-01-07 to 2030-01-13 PST', outside_details(card))

    def test_every_plotted_mark_reconciles_with_its_values_table(self):
        # catches: a chart shown beside another chart's values, or a values table that drops or adds
        # a row, so the marks and the readable values disagree somewhere on the site.
        for chart in self.bundle['figures']:
            html = next(h for h in self.site.values() if chart['svg'] in h)
            caption = f'{page.esc(chart["title"])}: plotted values'
            table = html[html.index(caption):]
            table = table[:table.index('</table>')]
            cells = re.findall(r'<tr class="[^"]*"><td>([^<]*)</td><td>([^<]*)</td>', table)
            self.assertEqual(cells, [(page.esc(r['label']), 'Unknown' if r['y'] is None else page.esc(r['y']))
                                     for r in chart['rows']], chart['id'])
            self.assertEqual(len(cells), chart['svg'].count('<title>'), chart['id'])

    def test_every_site_link_lands_and_nothing_needs_a_script(self):
        # catches: a navigation link to a page that does not exist, a figure or bench link with no
        # target, a page with a script or a remote reference, or a page that is not reachable from
        # every other page's navigation.
        ids = {r: set(re.findall(r'\sid="([^"]+)"', html)) for r, html in self.site.items()}
        for route, html in self.site.items():
            with self.subTest(route=route):
                self.assertTrue(html.startswith('<!doctype html>'))
                self.assertNotIn('<script', html.lower())
                nav = html[html.index('<nav class="site"'):html.index('</nav>')]
                self.assertEqual(re.findall(r'href="([^"]*)"', nav), ['./', 'speed', 'health', 'cost', 'quality', 'skills'])
                self.assertEqual(nav.count('aria-current="page"'), 1)
                for href in re.findall(r'href="([^"]*)"', html):
                    if href.startswith('https://'):
                        continue
                    target, _, anchor = href.partition('#')
                    target = route if target == '' else ('' if target == './' else target)
                    self.assertIn(target, ROUTES, href)
                    if anchor:
                        self.assertIn(anchor, ids[target], href)
                for href in re.findall(r'href="(https://[^"]*)"', html):
                    self.assertIn(href, html[html.index('<details class="sources"'):], 'evidence links stay in Sources')


class Tick(unittest.TestCase):
    """main.tick writes the complete site from one saved sample and one chart bundle, or nothing."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='war-room-site-tick-'))
        self.addCleanup(shutil.rmtree, self.tmp)
        import main
        self.main = main
        self.w, natives = packet.world(self.tmp / 'w')
        self.charts = lambda root: packet.native_build().build(root, at=packet.AT, source_root=self.w.root,
                                                               selections=natives)
        self.read = lambda at, previous: []

    def test_a_failed_child_page_keeps_the_previous_complete_site(self):
        # catches: a tick that writes a new home (or some children) and then fails on a later child,
        # leaving a new home beside stale or missing children; or a failure that touches samples.
        site = self.tmp / 'site'
        page_path = self.tmp / 'page' / 'page.html'
        self.main.tick('2030-01-14T09:59:00Z', self.w.history, page_path, self.read, charts=self.charts, site=site)
        names = sorted(p.name for p in site.iterdir() if not p.name.startswith('.'))
        self.assertEqual(names, sorted(page.site_files('war-room.html').values()))
        before = {p.name: p.read_bytes() for p in site.iterdir()}
        samples = {p.name: p.read_bytes() for p in (self.w.history / 'samples').glob('*.json')}
        real = page.child

        def fail_on_cost(slug, *args, **kwargs):
            if slug == 'cost':
                raise ValueError('synthetic child failure')
            return real(slug, *args, **kwargs)
        with mock.patch.object(page, 'child', side_effect=fail_on_cost), self.assertRaises(ValueError):
            self.main.tick('2030-01-14T10:04:00Z', self.w.history, page_path, self.read, charts=self.charts, site=site)
        self.assertEqual({p.name: p.read_bytes() for p in site.iterdir()}, before)
        after = {p.name: p.read_bytes() for p in (self.w.history / 'samples').glob('*.json')}
        self.assertEqual({k: after[k] for k in samples}, samples)


if __name__ == '__main__':
    unittest.main(verbosity=2)
