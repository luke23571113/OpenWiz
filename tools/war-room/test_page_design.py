#!/usr/bin/env python3
"""WRD3 (#631): the v3 page, proved at the generated HTML and in a real browser.

The frozen synthetic packet (fixtures/page-design/packet.py) is written through the real
select/compose/save path and the real chart build (locked Plot under Node); the page is
page.render over it. Expected values are the packet's own literals. The browser proof opens
the page in Chromium with page scripts disabled and every host unresolvable
(fixtures/page-design/probe.mjs). Needs `npm ci --ignore-scripts` in tools/war-room, Node
and Chromium. Synthetic data only; no network, no live read.
"""
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import page  # noqa: E402
import suite  # noqa: E402

DESIGN = HERE / 'fixtures' / 'page-design'
CARDS = ['00a', '00b', '00c', '00d', '00e']
# The page's readability floor for chart text, in CSS px as drawn (design/brief.md).
MIN_CHART_FONT = 8.5
# The embedded Oswald 4.103 Bold Basic Latin subset (J85; assets/README.md records its chain).
FONT_SHA256 = '299fca03acfe32ccf0b401b692ec66861173dd097ba3c5b61667117ff0afe033'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


packet = load('wrd3_packet', DESIGN / 'packet.py')
publish = load('wrd3_publish', HERE / 'publish.py')
palette = load('wrd3_palette', HERE / 'charts' / 'palette.py')


def between(html, start, end):
    i = html.index(start)
    return html[i:html.index(end, i)]


def figure_html(html, number):
    i = html.rindex('<figure', 0, html.index(f'id="fig-{number}"'))
    return html[i:html.index('</figure>', i)]


def outside_details(fragment):
    return re.sub(r'<details.*?</details>', '', fragment, flags=re.S)


def contrast(fg, bg):
    def lum(css):
        r, g, b = [int(v) / 255 for v in re.match(r'rgba?\(([^)]*)\)', css).group(1).split(',')[:3]]
        lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    a, b = lum(fg), lum(bg)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


class PageDesign(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix='war-room-page-design-'))
        cls.html, cls.bundle, cls.record = packet.render(cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_cards_lead_in_order_with_their_own_latest_values(self):
        # catches: cards out of the spec's order, a card after the body, or a headline read
        # from the wrong series or day (the packet's literals: 11 ready / 7 building on
        # 01-13, 39 merges, median 8 / p90 17.5 min, 12.5 min per run, the last 8 h span 40).
        cards = between(self.html, 'aria-label="Health and throughput"', '<div id="body">')
        self.assertEqual(re.findall(r'id="fig-(\w+)"', cards), CARDS)
        self.assertLess(self.html.index('id="fig-00e"'), self.html.index('id="fig-01"'))
        values = {n: re.search(r'<p class="value">([^<]*)</p><p class="stamp">([^<]*)</p>', figure_html(self.html, n)).groups()
                  for n in CARDS}
        self.assertEqual(values, {
            '00a': ('11 / 7', 'ready / building · 2030-01-13'), '00b': ('39 / day', '2030-01-13'),
            '00c': ('8 / 17.5 min', 'median / p90 · 2030-01-13'), '00d': ('12.5 min/run', '2030-01-13'),
            '00e': ('40 credits / 8 h', 'last sampled span · ends 2030-01-14T04:00Z')})

    def test_inventory_places_every_bench_signal_family_and_chart_once(self):
        # catches: a provider or health signal with no figure (or two), a spec family dropped
        # because nothing measures it yet, a figure number reused or skipped, or a chart the
        # build drew that the page never shows.
        inv = page.INVENTORY
        homes = [s for c in inv['cards'] for s in c['providers']]
        homes += [s for sec in inv['sections'] for f in sec['figures'] for s in f['providers']]
        slots = [p['slot'] for p in suite.PROVIDERS] + [h['slot'] for h in suite.HEALTH]
        self.assertEqual(sorted(homes), sorted(slots))
        self.assertEqual(len(slots), 20)
        self.assertEqual([s['title'] for s in inv['sections']], [
            'Flow & latency', 'Stage health', 'CI health, timing & cost', 'Usage & cost', 'Reviews & quality',
            'Skills & experiments', 'Factory load & operations', 'Engineering & proof', 'Answer latency'])
        numbers = [f['figure'] for sec in inv['sections'] for f in sec['figures']]
        self.assertEqual(numbers, ['%02d' % n for n in range(1, len(numbers) + 1)])
        known = set(numbers) | set(CARDS)
        for fam in inv['families']:
            self.assertTrue(fam['figures'] and set(fam['figures']) <= known, fam['measure'])
        self.assertEqual({fam['section'] for fam in inv['families']}, {s['number'] for s in inv['sections']})
        shown = re.findall(r'<div class="panel" id="figure-([\w-]+)"', self.html)
        self.assertEqual(sorted(shown + CARDS), sorted(f['id'] for f in self.bundle['figures']))
        for number in numbers + CARDS:
            fig = figure_html(self.html, number)
            self.assertEqual(fig.count('<figcaption'), 1, number)
        sources = between(self.html, '<details class="sources"', '</details>')
        for slot in slots:
            self.assertIn(f'data-slot="{slot}"', sources)

    def test_an_unplaced_chart_refuses_the_page(self):
        # catches: a chart the inventory does not place being silently dropped, or shown twice,
        # so the page no longer accounts for every figure the build drew.
        bundle = copy.deepcopy(self.bundle)
        bundle['figures'].append(dict(bundle['figures'][-1], id='body-unplanned-count'))
        with self.assertRaises(ValueError):
            page.render(self.record, charts=bundle)

    def test_missing_benches_stay_grey_with_their_prerequisite(self):
        # catches: an unavailable family dropped from the page, or shown without what it needs;
        # also a page that cannot render when no chart build ran (main.tick without charts).
        unavailable = [f for sec in page.INVENTORY['sections'] for f in sec['figures']
                       if not any(c['id'] in f['charts'] or any(p.endswith('*') and c['id'].startswith(p[:-1])
                                                                 for p in f['charts']) for c in self.bundle['figures'])]
        self.assertIn('04', [f['figure'] for f in unavailable])
        for f in unavailable:
            fig = figure_html(self.html, f['figure'])
            self.assertIn('class="fig unavailable"', fig)
            self.assertIn(page.esc(f['prerequisite']), outside_details(fig))
        bare = page.render(suite.compose('2030-01-14T10:00:00Z'))
        for number in CARDS + ['%02d' % n for n in range(1, 24)]:
            self.assertIn(f'id="fig-{number}"', bare)
        self.assertIn(page.NO_BUILD, bare)

    def test_status_strip_names_only_evidenced_anomalies(self):
        # catches: a strip that hides a failed main run or low ready stock, or one that reads
        # missing sources as an all-clear (an empty sample must never say "No anomaly").
        strip = between(self.html, 'class="strip"', '</section>')
        self.assertIn('Main CI failing · Low ready stock · 1 stage limit missed', strip)
        self.assertIn('11 ready / 7 building (2030-01-13) · main CI failure · 2 CI jobs queued', strip)
        self.assertIn('Fig. 00b: 1 of 7 days missing', strip)
        empty = between(page.render(suite.compose('2030-01-14T10:00:00Z')), 'class="strip"', '</section>')
        self.assertNotIn('No anomaly observed', empty)
        self.assertIn('Not every signal observed', empty)
        self.assertIn('Main CI unobserved', empty)

    def test_default_and_drawn_views_keep_each_charts_qualifying_facts(self):
        # catches: a unit, date range, coverage, missing day or gap moved into a closed
        # disclosure or styled away in the published picture, so a chart is shown without
        # the facts that qualify it.
        drawn = publish.drawable(self.html, False)
        self.assertEqual(drawn.count('<details class="sources" open id="sources">'), 1)
        style = between(drawn, '<style>', '</style>')
        self.assertNotRegex(style, r'\.meta[^{]*\{[^}]*display:\s*none')
        for f in self.bundle['figures']:
            anchor = f'id="fig-{f["id"]}"' if f['id'] in CARDS else f'id="figure-{f["id"]}"'
            for view in (self.html, drawn):
                visible = outside_details(between(view, anchor, '</figure>'))
                meta = between(visible, '<p class="meta">', '</p>')
                self.assertIn(page._unit(f), meta)
                self.assertIn(f"coverage {f['coverage']['observed']} of", meta)
                for day in f['coverage']['missing']:
                    self.assertIn(day, meta)
                for gap in f['gaps']:
                    self.assertIn(page.esc(gap), meta)
        self.assertIn('2030-01-07 to 2030-01-13 PST', figure_html(self.html, '00b'))

    def test_no_cockpit_panel_controls_or_request_wording(self):
        # catches: a waiting-on-Jake panel, an answer control, or a pending request's wording
        # reaching the war room; the answer-time benchmark itself stays in the body.
        for control in ('<form', '<button', '<input', '<textarea', '<select', '<script'):
            self.assertNotIn(control, self.html)
        headings = re.findall(r'<h[123][^>]*>(.*?)</h[123]>', self.html)
        self.assertFalse([h for h in headings if 'pending' in h.lower() or 'waiting' in h.lower()], headings)
        self.assertIn('Fig. 23 / Answer time', self.html)
        self.assertIn('id="figure-body-answer-time-minutes"', self.html)

    def test_page_ground_keeps_the_chart_palette_distinct_and_readable(self):
        # catches: a page ground (v3 black) under the charts that breaks the validated mark
        # contrast or colour-vision distinctions T2 proved on its own ground.
        result = palette.check(dict(palette.load(), ground='#000000'))
        self.assertTrue(result['pass'], result)
        kept = json.loads((DESIGN / 'palette-page.json').read_text(encoding='utf-8'))
        self.assertEqual(kept, result)

    def test_the_heading_font_is_the_pinned_asset_embedded_as_data(self):
        # catches: font bytes swapped from the recorded Oswald 4.103 Bold subset, a font
        # fetched from anywhere, or a CSP loosened beyond J85's one `font-src data:`.
        asset = (HERE / 'assets' / 'oswald-bold-latin.woff2').read_bytes()
        self.assertEqual(hashlib.sha256(asset).hexdigest(), FONT_SHA256)
        self.assertIn(FONT_SHA256, (HERE / 'assets' / 'README.md').read_text(encoding='utf-8'))
        faces = re.findall(r'@font-face\{[^}]*\}', self.html)
        self.assertEqual(len(faces), 1)
        self.assertIn('url(data:font/woff2;base64,' + base64.b64encode(asset).decode() + ')', faces[0])
        self.assertEqual(re.findall(r'url\((?!data:)', self.html), [])
        csp = re.search(r'Content-Security-Policy" content="([^"]*)"', self.html).group(1)
        self.assertEqual(csp, "default-src 'none'; style-src 'unsafe-inline'; font-src data:; "
                              "base-uri 'none'; form-action 'none'")

    def test_real_browser_without_scripts_or_network(self):
        # catches: horizontal overflow, cards out of order or not stacked on a phone, charts
        # too small to read, text below WCAG contrast, a page that needs a script, or a
        # disclosure the keyboard cannot reach and open. Chromium, page scripts disabled,
        # every host unresolvable; 390 x 844 and 1440 x 900, plus the target-comparison sizes.
        out = self.tmp / 'probe'
        out.mkdir()
        run = subprocess.run(['node', str(DESIGN / 'probe.mjs'), publish.chromium(), str(self.tmp / 'page.html'), str(out)],
                             capture_output=True, text=True, timeout=180)
        self.assertEqual(run.returncode, 0, run.stderr)
        probe = json.loads((out / 'probe.json').read_text(encoding='utf-8'))
        self.assertEqual([v['name'] for v in probe['viewports']], ['desktop', 'phone', 'desktop-target', 'phone-target'])
        for v in probe['viewports']:
            with self.subTest(v['name']):
                self.assertEqual(v['scripts'], 0)
                self.assertLessEqual(v['scrollWidth'], v['clientWidth'])
                figs = {f['id']: f for f in v['figures']}
                self.assertEqual(len(figs), 28)
                cards = [figs['fig-' + n] for n in CARDS]
                if v['width'] >= 1440:
                    self.assertEqual({round(c['y']) for c in cards}, {round(cards[0]['y'])})
                    self.assertEqual([c['x'] for c in cards], sorted(c['x'] for c in cards))
                else:
                    self.assertEqual([c['y'] for c in cards], sorted(c['y'] for c in cards))
                    self.assertEqual({round(c['x']) for c in cards}, {round(cards[0]['x'])})
                self.assertLess(max(c['y'] for c in cards), figs['fig-01']['y'])
                for f in v['figures']:
                    self.assertLessEqual(f['x'] + f['w'], v['width'] + 0.5, f['id'])
                    for c in f['charts']:
                        self.assertGreater(c['w'], 0, f['id'])
                        self.assertGreaterEqual(c['minFont'], MIN_CHART_FONT, f['id'])
                low = [(t['sample'], round(contrast(t['color'], t['background']), 2)) for t in v['text']
                       if contrast(t['color'], t['background']) < (3 if t['size'] >= 24 or (t['size'] >= 18.66 and t['weight'] >= 700) else 4.5)]
                self.assertEqual(low, [])
                self.assertTrue(all(not t['background'].startswith('translucent') for t in v['text']))
                self.assertEqual(v['focus'][-1]['tag'], 'summary')
                self.assertTrue(all(f['visible'] for f in v['focus']))
                self.assertIs(v['opened'], True)
                # J85: the face is loaded from the page itself and used by headings only.
                self.assertEqual([(f['family'], f['weight'], f['status']) for f in v['fonts']],
                                 [('Oswald WR', '700', 'loaded')])
                oswald = [t for t in v['text'] if t['family'].startswith('"Oswald WR"')]
                self.assertIn('h1', {t['tag'] for t in oswald})
                self.assertEqual([t['sample'] for t in oswald if not t['heading']], [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
