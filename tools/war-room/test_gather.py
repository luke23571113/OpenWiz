#!/usr/bin/env python3
"""WR10: gather the real War room sources into one pinned WR2 selection.

A local bare origin holds a synthetic `board` branch (graph, history,
credits.jsonl); a synthetic gh answers WR8's reads (fixtures/activity/fake_gh.py); journeys, their cohort and an
answer-time projection are fixture artifacts. No network, no live read.
"""
import base64
import contextlib
import copy
import functools
import hashlib
import html
import importlib.util
import io
import itertools
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
FIX = HERE / 'fixtures'
REPO = 'synthetic-owner/work'
RUN = 'https://github.com/synthetic-owner/work/actions/runs/9001'
STARTED, ENDED = '2030-01-02T12:29:00Z', '2030-01-02T12:30:00Z'
PUBLISH_AT = '2030-01-02T12:33:00Z'
BOARD_AT = '2030-01-02T12:20:00Z'
LISTED = 'repos/synthetic-owner/work/actions/workflows/ci.yml/runs?'
ACTIVE = ('in_progress', 'queued', 'waiting', 'pending', 'requested')
STATUS = LISTED + 'status=%s&per_page=100&page=1'
DONE = LISTED + 'created=2030-01-02T00:00:00Z..' + ENDED + '&status=completed&per_page=100&page=1'
GATHERED = {'activity', 'board', 'journey', 'cost', 'credits', 'answer_time', 'rework'}
# #827: the CI bench retired; its slot is always an explained gap, never a stale point.
RETIRED = {'ci_bench'}
# WRD1: also selected, with explicit reasons where this world has no source.
HEALTH = {'main_ci', 'ci_queue', 'stage_waits', 'stage_health'}
# #2565: the shape of the real gathered page of 2026-11-13, counts only: per card, its metrics,
# each incomplete metric's prerequisites and each measured metric's evidence links. Real chromium
# measured that page at 57,625 CSS px (1200 wide) and 49,909 (400 wide, drawn 2x). Its journey
# card's 8 metrics are left out: the fixture's journey card has none to copy.
# #883 follow-up: REAL_SCALE times this puts the complete page's phone picture past MAX_HEIGHT.
TALL = 3
REAL_SCALE = {'activity': (12, 0, 18), 'board': (8, 1, 1), 'ci_bench': (7, 0, 1),
              'cost': (74, 5, 1), 'credits': (25, 1, 1), 'rework': (7, 6, 48)}


def real_scale(providers, times=1):
    """The gathered fixture's providers grown to REAL_SCALE (times `times` metrics) with synthetic copies."""
    providers, n = copy.deepcopy(providers), 0
    for p in providers:
        if p['slot'] not in REAL_SCALE or not p['metrics']:
            continue
        count, prerequisites, links = REAL_SCALE[p['slot']]
        count *= times
        base = list(p['metrics'])
        while len(p['metrics']) < count:
            k = len(p['metrics'])
            m = copy.deepcopy(base[k % len(base)])
            m['id'] += '-copy-%d' % k
            m['label'] += ' (copy %d)' % k
            p['metrics'].append(m)
        for m in p['metrics']:
            if m['state'] != 'known':
                m['prerequisites'] += ['Synthetic prerequisite %d' % i for i in range(len(m['prerequisites']), prerequisites)]
            while m['evidence'] and len(m['evidence']) < links:
                n += 1
                m['evidence'].append('https://github.com/synthetic-owner/work/issues/%d' % (900000 + n))
    return providers


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, str(HERE))
import history  # noqa: E402
import sources  # noqa: E402
import suite  # noqa: E402
import answer_time  # noqa: E402
import rework  # noqa: E402
WR8 = load('wr8_fixture', HERE / 'test_activity.py')


def publish_module():
    import publish
    return publish


@functools.lru_cache(maxsize=None)
def gatherer():
    return load('gather', HERE / 'gather.py')


def probed(page, width, script):
    """What `script` (a JS expression, run on load) finds in `page` as real chromium lays it out at `width`."""
    probe = "<script>addEventListener('load',()=>{document.body.dataset.probe=JSON.stringify(%s)})</script></body>"
    with tempfile.TemporaryDirectory(prefix='war-room-probe-') as d:
        path = Path(d) / 'page.html'
        path.write_text(page.replace('</body>', probe % script), encoding='utf-8')
        dom = subprocess.run([publish_module().chromium(), '--headless=new', '--no-sandbox', '--disable-gpu',
                              '--user-data-dir=' + d + '/chr', '--window-size=%d,800' % width,
                              '--dump-dom', path.as_uri()], check=True, capture_output=True, text=True, timeout=90).stdout
    return json.loads(html.unescape(re.search(r'data-probe="([^"]*)"', dom).group(1)))


def width(phone):
    """The CSS width publish.py draws each picture at (WRD3: 1440, and 390 for the phone)."""
    return publish_module().PHONE_WIDTH if phone else publish_module().WIDTH


def visible_cards(page, phone):
    """Each value card's text as real chromium shows it in the drawn picture (innerText skips hidden rows)."""
    return probed(publish_module().drawable(page, phone), width(phone),
                  "[...document.querySelectorAll('article.metric')].map(a=>a.innerText)")


# #2586: the label of the page's last card, so a picture whose lower part was never painted
# (a correctly sized PNG, blank from some height down) is told from a whole one.
MARKER = 'Synthetic bottom-page marker'


def marked(providers):
    """The providers with the last card the page draws (last group, last provider, last metric) labelled MARKER."""
    order = [d['slot'] for d in suite.PROVIDERS]
    last = max(((suite.GROUPS.index(m['group']), order.index(p['slot']), i), m)
               for p in providers if 'metrics' in p for i, m in enumerate(p['metrics']))[1]
    last['label'] = MARKER
    return providers


def marker_pixels(page, png, phone, find=None):
    """How many of the picture's pixels inside the marker (by default the marker card's heading; `find`,
    a JS expression for a list of elements, picks another) have its text and its card's colour."""
    find = find or "[...document.querySelectorAll('h4')].filter(e=>e.textContent===%s)" % json.dumps(MARKER)
    found = probed(publish_module().drawable(page, phone), width(phone), (
        "(()=>{const h=%s;"
        "if(h.length!==1)return null;const r=h[0].getBoundingClientRect();"
        "return {box:[r.left,r.top+scrollY,r.width,r.height],text:getComputedStyle(h[0]).color,"
        "card:getComputedStyle(h[0].closest('article')||document.body).backgroundColor}})()") % find)
    assert found, 'the marker is not on the drawn page once'
    scale = 2 if phone else 1
    x, y, w, h = (round(v * scale) for v in found['box'])
    # The picture, decoded by chromium: only the marker's box is copied to a canvas.
    count = ("(()=>{const c=document.createElement('canvas');c.width=%d;c.height=%d;const g=c.getContext('2d');"
             "const i=document.images[0];g.drawImage(i,%d,%d,%d,%d,0,0,%d,%d);i.remove();"
             "const d=g.getImageData(0,0,%d,%d).data;const near=s=>{const [r,G,b]=s.match(/[0-9]+/g).map(Number);"
             "let n=0;for(let k=0;k<d.length;k+=4)n+=Math.abs(d[k]-r)+Math.abs(d[k+1]-G)+Math.abs(d[k+2]-b)<=12;return n};"
             "return {size:[i.naturalWidth,i.naturalHeight],text:near(%s),card:near(%s)}})()") % (
        w, h, x, y, w, h, w, h, w, h, json.dumps(found['text']), json.dumps(found['card']))
    image = '<html><body><img src="data:image/png;base64,%s"></body></html>' % base64.b64encode(png).decode()
    return probed(image, publish_module().PHONE_WIDTH, count)


def git(cwd, *args, env=None):
    return subprocess.run(['git', '-C', str(cwd), *args], check=True, capture_output=True, text=True,
                          env=env).stdout


class PublicBoardReaders(unittest.TestCase):
    """#629: the board's offline readers live in sources.py; no private module is loaded.

    Expected values are literals read off the synthetic fixtures (fixtures/page-history/
    board-graph.json, fixtures/gather/history.jsonl and credits.jsonl), pinned once
    against the board's existing readers before their extraction."""
    AT = '2030-01-02T12:30:00Z'
    LINK = 'https://github.com/synthetic-owner/work/commit/' + 'c' * 40

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='war-room-board-'))
        self.addCleanup(shutil.rmtree, self.root)
        graph = json.loads((FIX / 'page-history/board-graph.json').read_text())
        graph['repo'] = REPO
        self.graph = graph
        self.inputs = {'board_graph': json.dumps(graph),
                       'board_history': (FIX / 'gather/history.jsonl').read_text(),
                       'credits': (FIX / 'gather/credits.jsonl').read_text()}

    def select(self, kind, wire):
        (self.root / kind).write_text(wire)
        entry = {'kind': kind, 'slot': sources.SLOTS[kind], 'path': kind, 'observed_at': self.AT,
                 'sha256': hashlib.sha256(wire.encode()).hexdigest(), 'evidence': [self.LINK]}
        return sources.select(self.root, [entry], self.AT)[0], entry

    def test_no_private_module_is_loaded_and_each_board_source_still_reads(self):
        real = sources.native

        def public_only(path):
            if path.startswith('private/'):
                raise AssertionError('a private module was loaded: ' + path)
            return real(path)
        with patch.object(sources, 'native', side_effect=public_only):
            for kind, wire in self.inputs.items():
                with self.subTest(kind):
                    provider, entry = self.select(kind, wire)
                    self.assertNotEqual(provider, sources._failed(entry['slot'], None, self.AT))
            board = dict(self.graph, source={'kind': 'board'})
            self.assertEqual(gatherer().open_approved(json.dumps(board).encode(), REPO),
                             [9001, 9002, 9003, 9004, 9005, 9006])

    def test_board_graph_measures_and_states_keep_the_source_definitions(self):
        report = sources.board_check_links(self.graph)
        self.assertEqual((report['kind'], report['repo'], len(report['links'])), ('report', REPO, 4))
        m = sources.board_measures(self.graph, report)
        self.assertEqual({k: m[k] for k in sources.BOARD_MEASURE_KEYS},
                         {'open_approved': 6, 'can_start': 2, 'startable_percent': 33, 'file_links': 0,
                          'unlabelled_links': 0, 'ready_stock': 2, 'builders_running': 0,
                          'fed_ratio': None, 'low_stock': False})
        self.assertEqual([(t['number'], sources.board_state(t)) for t in sources.board_open_approved(self.graph)],
                         [(9001, 'ready'), (9002, 'blocked'), (9003, 'blocked'), (9004, 'blocked'),
                          (9005, 'ready'), (9006, 'blocked')])
        provider, _ = self.select('board_graph', self.inputs['board_graph'])
        self.assertEqual(len(provider['metrics']), 7)  # readiness plus one point per open approved ticket

    def test_half_up_rounding_and_undefined_ratios(self):
        def ticket(n, building=False, blocked=False):
            return {'number': n, 'title': 'Synthetic', 'state': 'OPEN', 'labels': ['ready-for-agent'],
                    'milestone': None, 'parent': None, 'body': '', 'start_recorded': building,
                    'pull_requests': [], 'blocked_by': [{'number': 1, 'state': 'OPEN'}] if blocked else []}
        report = {'kind': 'report', 'repo': REPO, 'links': []}
        # 2 startable of 3 = 66.67 -> 67; 1 ready per 3 building = 0.33 -> 0.3.
        graph = {'tickets': [ticket(1, True), ticket(2, True), ticket(3, True, blocked=True)]}
        m = sources.board_measures(graph, report)
        self.assertEqual((m['startable_percent'], m['fed_ratio'], m['low_stock']), (67, 0.0, True))  # 0 ready per 3 building
        graph = {'tickets': [ticket(1), ticket(2, True), ticket(3, True), ticket(4, True)]}
        m = sources.board_measures(graph, report)
        self.assertEqual((m['ready_stock'], m['builders_running'], m['fed_ratio']), (1, 3, 0.3))
        m = sources.board_measures({'tickets': []}, report)  # zero denominators stay undefined, never zero
        self.assertEqual((m['startable_percent'], m['fed_ratio']), (None, None))

    def test_history_rows_are_strict(self):
        rows = [sources.board_strict(l) for l in self.inputs['board_history'].splitlines() if l.strip()]
        self.assertTrue(all(sources.board_valid_row(r, False) for r in rows))
        with self.assertRaises(ValueError):
            sources.board_strict('{"at": 1, "at": 2}')
        good = rows[0]
        bad = [dict(good, open_approved=-1), dict(good, low_stock=1), dict(good, day='2030-01-03'),
               dict(good, at='2030-02-30T11:00:00Z'), dict(good, fed_ratio='3.0'),
               {k: good[k] for k in reversed(list(good))}, dict(good, sample='baseline')]
        for row in bad:
            with self.subTest(row=row):
                self.assertFalse(sources.board_valid_row(row, False))
        # A legacy baseline is admitted only as the first row, by its shape.
        baseline = dict(good, sample='baseline', file_links=None, unlabelled_links=None, ready_stock=None,
                        builders_running=None, fed_ratio=None, low_stock=None)
        self.assertTrue(sources.board_valid_row(baseline, True))
        self.assertFalse(sources.board_valid_row(baseline, False))
        self.assertFalse(sources.board_valid_row(good, True))
        self.assertFalse(sources.board_valid_row(dict(baseline, open_approved=None), True))

    def test_credit_samples_and_their_sampled_drops(self):
        samples = sources.read_credits(self.inputs['credits'])
        self.assertEqual([sources.credit_spent(a, b) for a, b in zip(samples, samples[1:])], [30, 15])
        rise = dict(samples[1], at='2030-01-02T13:00:00Z', extra_credits=900)
        self.assertEqual(sources.credit_spent(samples[1], rise), 0)  # a rise counts as zero
        seed = {'at': '2030-01-02T09:00:00Z', 'extra_credits': 520, 'only': 'extra_credits'}
        self.assertEqual(sources.credit_spent(seed, samples[0]), 20)  # extra-only spans compare extra only
        line = self.inputs['credits'].splitlines()[0]
        for text in (line + '\n' + line, line.replace('"credits":1000', '"credits":-1'),
                     line.replace('"credits":1000', '"credits":"1000"'), '{"at":"2030-01-02T09:00:00Z"}',
                     json.dumps(dict(seed, only='credits'))):
            with self.subTest(text=text), self.assertRaises(ValueError):
                sources.read_credits(text)


class Gather(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='war-room-gather-'))
        self.addCleanup(shutil.rmtree, self.tmp)
        self.origin = self.tmp / 'origin.git'
        git(self.tmp, 'init', '-q', '--bare', str(self.origin))
        graph = json.loads((FIX / 'page-history/board-graph.json').read_text())
        graph['repo'] = REPO
        graph['source'] = {'kind': 'board'}  # the board's own repository-wide read
        self.branch('board', BOARD_AT, {
            'graph.json': json.dumps(graph, indent=2) + '\n',
            'history.jsonl': (FIX / 'gather/history.jsonl').read_text(),
            'credits.jsonl': (FIX / 'gather/credits.jsonl').read_text(),
            'README.md': 'synthetic board\n'})
        self.refs_before = self.refs()
        # WR8's synthetic gh, answering WR8's own fixture reads.
        bin_dir = self.tmp / 'bin'
        bin_dir.mkdir()
        (bin_dir / 'gh').symlink_to(FIX / 'activity/fake_gh.py')
        self.answers = self.tmp / 'gh.json'
        self.answer(WR8.fixture())
        self.env = {'PATH': str(bin_dir) + os.pathsep + os.environ['PATH'], 'WR8_FIXTURE': str(self.answers)}
        # WR5's own projection of its synthetic pairs: the answer-time artifact.
        pairs = json.loads((FIX / 'answer-time/pairs.json').read_text())['projection']
        facts = json.dumps(pairs, sort_keys=True).encode()
        provider = answer_time.project(
            pairs['sample_at'], source={'path': 'answer-time/pairs.json', 'schema': 'openwiz.war-room.answer-time.synthetic',
                                        'sha256': hashlib.sha256(facts).hexdigest()},
            window=pairs['window'], observed_at=pairs['observed_at'], cohort=pairs['cohort'],
            requests=pairs['requests'], dispositions=pairs['dispositions'], expected=pairs['expected'],
            history=pairs['history'])
        self.answer_time = self.tmp / 'answer-time.json'
        self.answer_time.write_text(json.dumps(provider))
        self.journeys = FIX / 'rework/journeys.json'
        self.cohort = FIX / 'gather/cohort.json'

    def answer(self, answers, current=None):
        """WR8's synthetic gh answers, with ci.yml's runs also listed by status and the day's completed cohort."""
        listed = answers[WR8.RUNS]['workflow_runs']
        current = {s: [r for r in listed if r['status'] == s] for s in ACTIVE} if current is None else current
        for status in ACTIVE:
            runs = current.get(status, [])
            answers[STATUS % status] = {'total_count': len(runs), 'workflow_runs': runs}
        done = current.get('completed', [])
        answers[DONE] = {'total_count': len(done), 'workflow_runs': done}
        self.answers.write_text(json.dumps(answers))
        return answers

    def branch(self, name, at, files):
        work = Path(tempfile.mkdtemp(prefix='seed-', dir=self.tmp))
        git(self.tmp, 'init', '-q', str(work))
        for path, text in files.items():
            (work / path).parent.mkdir(parents=True, exist_ok=True)
            (work / path).write_text(text)
        stamp = dict(os.environ, GIT_AUTHOR_DATE=at, GIT_COMMITTER_DATE=at)
        git(work, 'add', '-A')
        git(work, '-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.invalid',
            'commit', '-q', '-m', 'synthetic ' + name, env=stamp)
        git(work, 'push', '-q', '-f', str(self.origin), 'HEAD:refs/heads/' + name)
        return git(work, 'rev-parse', 'HEAD').strip()

    def refs(self):
        return git(self.origin, 'for-each-ref', '--format=%(objectname) %(refname)')

    def gather(self, out=None, **overrides):
        out = self.tmp / 'out' if out is None else out
        clock = itertools.chain([STARTED], itertools.repeat(ENDED))  # WRD1: health reads stamp the clock too
        args = dict(remote=str(self.origin), repo=REPO, run_url=RUN, clock=lambda: next(clock),
                    pools=WR8.POOLS, journeys=self.journeys, cohort=self.cohort, answer_time=self.answer_time)
        args.update(overrides)
        with patch.dict(os.environ, self.env):
            gatherer().gather(out, **args)
        return out / 'root', json.loads((out / 'selection.json').read_text())

    def publish(self, root, selection_path):
        fakes = FIX / 'publish'
        env = dict(os.environ, PATH=str(fakes) + os.pathsep + os.environ['PATH'],
                   FAKE_CHROMIUM_LOG=str(self.tmp / 'chromium.log'), FAKE_GH_LOG=str(self.tmp / 'gh.log'))
        result = subprocess.run([sys.executable, '-I', str(HERE / 'publish.py'), 'publish', '--remote', str(self.origin),
                                 '--at', PUBLISH_AT, '--source-root', str(root), '--selection', str(selection_path)],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        sample = subprocess.run(['git', '-C', str(self.origin), 'show',
                                 'refs/heads/war-room:samples/2030-01-02T12-30-00Z.json'],
                                check=True, capture_output=True).stdout
        record = suite.loads(sample.decode())
        return {p['slot']: p for p in record['providers']}

    def values(self, provider):
        return {m['id']: m['value'] for m in provider['metrics'] if m['value'] is not None}

    def test_gather_writes_a_selection_sources_select_accepts(self):
        root, selection = self.gather()
        self.assertEqual({s['slot'] for s in selection}, GATHERED | HEALTH | RETIRED)
        for s in selection:
            with self.subTest(s['slot']):
                # Pinned by sha256 of the gathered bytes and an observed time no later than the read.
                self.assertEqual(hashlib.sha256((root / s['path']).read_bytes()).hexdigest(), s['sha256'])
                self.assertLessEqual(s['observed_at'], ENDED)
                self.assertTrue(s['evidence'])
        by_slot = {s['slot']: s for s in selection}
        self.assertEqual(by_slot['credits']['kind'], 'credits')
        self.assertEqual(by_slot['journey']['kind'], 'journey')
        self.assertEqual(by_slot['board']['observed_at'], BOARD_AT)
        self.assertEqual(by_slot['credits']['observed_at'], BOARD_AT)
        self.assertEqual(by_slot['activity']['observed_at'], ENDED)
        self.assertEqual(by_slot['rework']['observed_at'], '2030-01-02T12:00:00Z')
        self.assertRegex(by_slot['credits']['evidence'][0], r'^https://github\.com/synthetic-owner/work/commit/[0-9a-f]{40}$')
        # catches (#827): a retired CI bench point selected as if it were current.
        self.assertTrue(by_slot['ci_bench']['path'].startswith('missing/'))
        self.assertIn('CI bench retired (#827)', json.loads((root / by_slot['ci_bench']['path']).read_text())['prerequisites'][0])
        providers = sources.select(root, selection, ENDED)
        for s, p in zip(selection, providers):
            with self.subTest(s['slot']):
                self.assertNotEqual(p, sources._failed(s['slot'], None, ENDED))
        # WRD1: the queue is WR8's same read projected again, so the two counts agree.
        chosen = {p['slot']: p for p in providers}
        activity = {m['id']: m['value'] for m in chosen['activity']['metrics']}
        queue = {o['id']: o['value'] for o in chosen['ci_queue']['observations']}
        self.assertEqual(queue['queued:ubuntu-24.04'], activity['ci-queued-ubuntu-24.04'])
        self.assertEqual(queue['running:ubuntu-slim'], activity['ci-running-ubuntu-slim'])
        self.assertEqual(chosen['main_ci']['state'], 'unavailable')  # this world answers no main reads
        # board is only read: every ref of the origin is unchanged.
        self.assertEqual(self.refs(), self.refs_before)

    def test_data_branches_on_a_second_remote_are_read_with_data_remote(self):
        # WRD4 (#877): the code repository has no board branch; it lives on a
        # second (private) repository. Without --data-remote they stay unavailable, as before;
        # with it they are read from there, only read, and their evidence names that repository.
        data = self.tmp / 'data.git'
        git(self.tmp, 'clone', '-q', '--bare', str(self.origin), str(data))
        for name in ('board',):
            git(self.origin, 'update-ref', '-d', 'refs/heads/' + name)
        before = (self.refs(), git(data, 'for-each-ref', '--format=%(objectname) %(refname)'))
        _, selection = self.gather(out=self.tmp / 'code-only')
        missing = {s['slot'] for s in selection if s['path'].startswith('missing/')}
        self.assertLessEqual({'board', 'credits', 'ci_bench'}, missing)
        # A GitHub-shaped data remote, mapped onto the local bare repository by git's own config.
        url = 'https://github.com/synthetic-owner/private-data.git'
        mapped = {'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'url.%s.insteadOf' % data, 'GIT_CONFIG_VALUE_0': url}
        with patch.dict(os.environ, mapped):
            root, selection = self.gather(out=self.tmp / 'with-data', data_remote=url)
        by_slot = {s['slot']: s for s in selection}
        self.assertFalse(by_slot['board']['path'].startswith('missing/'))
        for slot in ('credits',):
            with self.subTest(slot):
                self.assertFalse(by_slot[slot]['path'].startswith('missing/'))
                self.assertRegex(by_slot[slot]['evidence'][0],
                                 r'^https://github\.com/synthetic-owner/private-data/commit/[0-9a-f]{40}$')
        self.assertEqual(by_slot['board']['observed_at'], BOARD_AT)
        # Every other source still reads and links the code repository.
        self.assertEqual(by_slot['activity']['evidence'][0], RUN)
        providers = {p['slot']: p for p in sources.select(root, selection, ENDED)}
        self.assertTrue(self.values(providers['credits']))
        self.assertEqual(before, (self.refs(), git(data, 'for-each-ref', '--format=%(objectname) %(refname)')))

    def test_stage_reads_cover_open_approved_work_and_the_merged_cohort(self):
        # WRD1: TL2 is collected for unfinished work too: the board graph's six open
        # ready-for-agent tickets (9001-9006, blocked ones included) and ticket 94, which
        # the merged cohort's PR closes (WR8's synthetic PR pages).
        seen = []
        with patch.object(gatherer(), 'stage_evidence', side_effect=lambda repo, tickets, clock: seen.append(sorted(tickets))):
            _, selection = self.gather(journeys=None, cohort=None)
        self.assertEqual(seen, [[94, 9001, 9002, 9003, 9004, 9005, 9006]])
        # Its collection failed here, so both stage cards name their prerequisite.
        missing = {s['slot'] for s in selection if s['path'].startswith('missing/')}
        self.assertLessEqual({'stage_waits', 'stage_health'}, missing)

    def test_r2_without_a_complete_ticket_enumeration_stage_health_is_not_collected(self):
        # A missing or refused board graph, or failed PR pages, cannot enumerate the unfinished
        # work, so no stage cohort is collected that silently omits it.
        graph = json.loads((FIX / 'page-history/board-graph.json').read_text())
        graph.update(repo=REPO, source={'kind': 'board'})
        board = {'history.jsonl': (FIX / 'gather/history.jsonl').read_text(),
                 'credits.jsonl': (FIX / 'gather/credits.jsonl').read_text()}
        broken = dict(graph, tickets='not a list')
        # R9: a valid graph of one spec, or another repository's board, enumerates no unfinished work here.
        spec = dict(graph, source={'kind': 'spec', 'spec': 9000})
        foreign = dict(graph, repo='synthetic-owner/other')
        cases = {'no graph': (board, None), 'refused graph': (dict(board, **{'graph.json': json.dumps(broken)}), None),
                 'failed PR pages': (dict(board, **{'graph.json': json.dumps(graph)}), 'graph:prs:'),
                 'spec graph': (dict(board, **{'graph.json': json.dumps(spec)}), None),
                 'foreign board graph': (dict(board, **{'graph.json': json.dumps(foreign)}), None)}
        for name, (files, drop) in cases.items():
            with self.subTest(name):
                self.branch('board', BOARD_AT, files)
                answers = WR8.fixture()
                answers.pop(drop, None)
                self.answer(answers)
                seen = []
                out = self.tmp / ('out-' + name.replace(' ', '-'))
                with patch.object(gatherer(), 'stage_evidence', side_effect=lambda r, t, c: seen.append(t)):
                    root, selection = self.gather(out, journeys=None, cohort=None)
                self.assertEqual(seen, [])
                for slot in ('stage_waits', 'stage_health'):
                    entry = next(s for s in selection if s['slot'] == slot)
                    self.assertTrue(entry['path'].startswith('missing/'))
                    reason = json.loads((root / entry['path']).read_text())['prerequisites'][0]
                    self.assertIn('unfinished', reason)
                # Collector to history: the saved v2 sample keeps stage health unavailable, with that reason.
                saved, _ = history.collect(out / 'history', ENDED,
                                           publish_module().selection_reader(root, out / 'selection.json'))
                stage = next(h for h in saved['health'] if h['slot'] == 'stage_health')
                self.assertEqual((stage['state'], stage['observations']), ('unavailable', []))
                self.assertTrue(any('unfinished' in p for p in stage['prerequisites']))

    def test_publish_shows_measured_values_with_provenance(self):
        root, selection = self.gather()
        cards = self.publish(root, self.tmp / 'out/selection.json')
        board = self.values(cards['board'])
        self.assertEqual((board['open-approved'], board['can-start'], board['ready-stock'],
                          board['builders-running'], board['startable-percent']), (6, 2, 2, 0, 33))
        self.assertEqual(sorted(self.values(cards['credits']).values()), [15, 30])
        self.assertEqual(self.values(cards['activity'])['ci-queued-ubuntu-24.04'], 1)
        self.assertEqual(self.values(cards['rework'])['review-changes-share'], 0.5)
        self.assertEqual(self.values(cards['answer_time'])['answer-coverage'], 1 / 3)
        # #827: cost reads journeys only now; without a CI bench point its CI share is Unknown, explained.
        self.assertTrue(all(m['value'] is None and m['prerequisites'] for m in cards['cost']['metrics']))
        for slot in GATHERED - {'journey', 'cost'}:
            with self.subTest(slot):
                shown = [m for m in cards[slot]['metrics'] if m['value'] is not None]
                self.assertTrue(shown, slot + ' shows no measured value')
                for m in shown:
                    self.assertRegex(m['source']['sha256'], '^[0-9a-f]{64}$')
                    self.assertTrue(m['evidence'] and m['observed_at'] and m['window'])
        # A point the source cannot divide stays Unknown with its reason, never zero.
        fed = next(m for m in cards['board']['metrics'] if m['id'] == 'fed-ratio')
        self.assertIsNone(fed['value'])
        self.assertTrue(any('builders running' in p for p in fed['prerequisites']))

    def test_the_full_gathered_selection_publishes_with_real_chromium(self):
        # #2432 R1: the whole gathered page, drawn by the real chromium at both widths, publishes;
        # the fake chromium's fixed height hid that it is far taller than the old 8,000 px cap.
        root, selection = self.gather()
        self.assertTrue(publish_module().chromium(), 'the real chromium is required')
        env = dict(os.environ)
        env.pop('FAKE_CHROMIUM_HEIGHT', None)
        result = subprocess.run([sys.executable, '-I', str(HERE / 'publish.py'), 'publish', '--remote', str(self.origin),
                                 '--at', PUBLISH_AT, '--source-root', str(root),
                                 '--selection', str(self.tmp / 'out/selection.json')],
                                env=env, capture_output=True, text=True, timeout=600)
        self.assertEqual(result.returncode, 0, result.stderr)
        files = git(self.origin, 'ls-tree', '-r', '--name-only', 'refs/heads/war-room').split()
        # WRD5 (#883): the six site pages beside the pictures, in the same commit.
        self.assertEqual(sorted(files), sorted(['README.md', 'samples/2030-01-02T12-30-00Z.json', 'snapshot.json', 'war-room-phone.png',
                                                'war-room.png', *publish_module().SITE.values()]))
        sizes = {}
        for name in ('war-room.png', 'war-room-phone.png'):
            data = subprocess.run(['git', '-C', str(self.origin), 'show', 'refs/heads/war-room:' + name],
                                  check=True, capture_output=True).stdout
            self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
            sizes[name] = struct.unpack('>II', data[16:24])
        self.assertEqual(sizes['war-room.png'][0], width(False))
        self.assertEqual(sizes['war-room-phone.png'][0], 2 * width(True))
        # #883: the pictures are of the home page, whole, not a clip of it.
        home = git(self.origin, 'show', 'refs/heads/war-room:war-room.html')
        for name, phone in (('war-room.png', False), ('war-room-phone.png', True)):
            whole = probed(publish_module().drawable(home, phone), width(phone), 'document.documentElement.scrollHeight')
            # Two separate Chromium layouts of one page can differ by a few px (font settling).
            self.assertLessEqual(abs(sizes[name][1] - (2 if phone else 1) * whole), 2 * 8, name)
        # Every gathered card, with measured values, is on the page that was drawn: all 65 metrics the
        # review counted for this fixture. The board shows its six counts and the startable percent;
        # the fed ratio is undefined with no builders running.
        readme = git(self.origin, 'show', 'refs/heads/war-room:README.md')
        self.assertIn('| Board | partial | 7 of 8 |', readme)
        rows = {}
        for line in readme.splitlines():
            cells = [c.strip() for c in line.strip('|').split('|')]
            if len(cells) == 3 and ' of ' in cells[2]:
                rows[cells[0]] = [int(n) for n in cells[2].split(' of ')]
        cards = ('Board', 'Credits', 'Current activity', 'Rework rate', 'Orchestrator answer time')
        self.assertTrue(all(rows[card][0] > 0 for card in cards), rows)
        self.assertEqual(sum(rows[card][1] for card in cards), 36)
        # #827: the retired CI bench draws nothing, and cost without its point is Unknown, never zero.
        self.assertEqual((rows['CI bench'], rows['All-in cost per merged PR']), ([0, 0], [0, 25]))

    def test_each_picture_card_shows_what_tells_it_apart(self):
        # #2565 R1: cards can share a label (a credit drop per interval), so
        # each picture card shows its window, freshness, statistic and dimensions; its long
        # provenance and evidence links stay in the published sample.
        root, _ = self.gather()
        read = publish_module().selection_reader(root, self.tmp / 'out/selection.json')
        page = publish_module().tick(self.tmp / 'private' / 'history', PUBLISH_AT, read).read_text(encoding='utf-8')
        record = suite.load(next((self.tmp / 'private' / 'history' / 'samples').glob('*.json')))
        labels = {}
        for p in record['providers']:
            for m in p['metrics']:
                labels.setdefault((p['slot'], m['label']), []).append(m)
        shared = {slot for (slot, _), ms in labels.items() if len(ms) > 1}
        self.assertLessEqual({'credits'}, shared, 'cards that share a label: credit drops')
        # The page shows the cards group by group; the same order, rebuilt from the record.
        metrics = [m for g in suite.GROUPS for p, d in zip(record['providers'], suite.PROVIDERS)
                   if g in d['groups'] for m in p['metrics'] if m['group'] == g]
        for phone in (False, True):
            cards = visible_cards(page, phone)
            self.assertEqual(len(cards), len(metrics))
            for m, card in zip(metrics, cards):
                with self.subTest(phone=phone, metric=m['id']):
                    self.assertIn(m['label'], card)
                    if m['window'] is not None:
                        self.assertIn(m['window']['since'], card)
                        self.assertIn(m['window']['until'], card)
                    self.assertIn(m['statistic'], card)
                    self.assertIn(m['freshness'], card)
                    for v in m['dimensions'].values():
                        if v is not None:
                            self.assertIn(str(v), card)
                    if m['source'] is not None:
                        self.assertNotIn(m['source']['sha256'], card)
                    self.assertNotIn('source 1', card)
            for (slot, label), ms in labels.items():
                shown = [cards[metrics.index(m)] for m in ms]
                self.assertEqual(len(set(shown)), len(shown), (slot, label))

    def test_a_real_scale_gathered_page_draws_with_real_chromium(self):
        # #2565: the real gathered page grew past the bound (57,625 CSS px; the phone picture 99,818
        # device px), so every main publish refused it. The same page shape, synthetic, must draw.
        # #883: the pictures are now of the home page; #2586's painted-to-the-bottom check reads its
        # last line, the footer, since the Sources cards are on the child pages.
        root, _ = self.gather()
        read = publish_module().selection_reader(root, self.tmp / 'out/selection.json')
        out = self.tmp / 'pictures'
        out.mkdir()
        page = publish_module().render(out, self.tmp / 'private' / 'history', PUBLISH_AT,
                                       lambda at, previous: marked(real_scale(read(at, previous))))
        record = suite.load(next((self.tmp / 'private' / 'history' / 'samples').glob('*.json')))
        self.assertEqual(sum(len(p['metrics']) for p in record['providers'] if p['slot'] in REAL_SCALE), 126)
        for name, drawn_width, phone in (('war-room.png', width(False), False), ('war-room-phone.png', 2 * width(True), True)):
            with self.subTest(name):
                data = (out / name).read_bytes()
                self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
                drawn, height = struct.unpack('>II', data[16:24])
                self.assertEqual(drawn, drawn_width)
                self.assertLessEqual(height, publish_module().MAX_HEIGHT)
                # #2586: and painted to the bottom: the home page's last line shows its text.
                pixels = marker_pixels(page, data, phone, "[...document.querySelectorAll('footer')]")
                self.assertEqual(pixels['size'], [drawn, height])
                self.assertGreater(pixels['text'], 50, 'the footer text is not painted')

    def test_a_full_page_past_the_height_bound_still_publishes_pictures_of_home(self):
        # catches (#883 follow-up): every hourly publication refusing with "the page is too tall to
        # draw" once the complete one-document page outgrew the picture bound, so the site went stale.
        # The pictures are of the home page, whole, within the unchanged bound.
        root, _ = self.gather()
        read = publish_module().selection_reader(root, self.tmp / 'out/selection.json')
        out = self.tmp / 'pictures'
        out.mkdir()
        history = self.tmp / 'private' / 'history'
        home = publish_module().render(out, history, PUBLISH_AT,
                                       lambda at, previous: real_scale(read(at, previous), times=TALL))
        self.assertEqual(home, (out / 'war-room.html').read_text(encoding='utf-8'))
        complete = (history.parent / 'page' / 'page.html').read_text(encoding='utf-8')
        tall = probed(publish_module().drawable(complete, True), width(True), 'document.documentElement.scrollHeight')
        self.assertGreater(2 * tall, publish_module().MAX_HEIGHT, 'the complete page is past the bound')
        for name, phone in (('war-room.png', False), ('war-room-phone.png', True)):
            with self.subTest(name):
                data = (out / name).read_bytes()
                drawn, height = struct.unpack('>II', data[16:24])
                scale = 2 if phone else 1
                self.assertEqual(drawn, scale * width(phone))
                self.assertLessEqual(height, publish_module().MAX_HEIGHT)
                whole = probed(publish_module().drawable(home, phone), width(phone), 'document.documentElement.scrollHeight')
                # Two separate Chromium layouts of one page can differ by a few px (font settling).
                self.assertLessEqual(abs(height - scale * whole), 2 * 8, 'the whole home page, not a clip of it')

    def test_a_removed_or_unreadable_source_greys_only_its_own_card(self):
        self.branch('board', BOARD_AT, {'history.jsonl': (FIX / 'gather/history.jsonl').read_text(),
                                        'credits.jsonl': 'not a credit sample\n'})
        root, selection = self.gather()
        cards = self.publish(root, self.tmp / 'out/selection.json')
        for slot, source, prerequisite in (
                ('ci_bench', 'CI bench retired (#827)', 'collector snapshot'),
                ('credits', 'credits.jsonl', 'credit sampler')):
            with self.subTest(slot):
                self.assertEqual(cards[slot]['state'], 'unavailable')
                reason = ' '.join(cards[slot]['prerequisites'])
                self.assertIn(source, reason)
                self.assertIn(prerequisite, reason)
        for slot in ('board', 'activity', 'rework', 'answer_time'):
            with self.subTest(slot):
                self.assertTrue(self.values(cards[slot]), slot + ' lost its values')
        # Without a graph on the branch, the ratios name it as their prerequisite.
        ratio = next(m for m in cards['board']['metrics'] if m['id'] == 'startable-percent')
        self.assertIsNone(ratio['value'])
        self.assertTrue(any('graph.json' in p for p in ratio['prerequisites']))

    def test_without_journeys_or_answer_records_each_card_names_its_prerequisite(self):
        # No fake gh answers journey reads: collection fails, and only those cards grey.
        root, selection = self.gather(journeys=None, cohort=None, answer_time=None)
        cards = {p['slot']: p for p in sources.select(root, selection, ENDED)}
        self.assertEqual(cards['answer_time'], answer_time.unavailable())
        for slot in ('journey', 'rework'):
            with self.subTest(slot):
                self.assertEqual(cards[slot]['state'], 'unavailable')
                self.assertIn('journey.py collect', ' '.join(cards[slot]['prerequisites']))
        self.assertTrue(self.values(cards['board']))

    def test_a_planted_secret_turns_the_privacy_scan_red(self):
        provider = json.loads(self.answer_time.read_text())
        for planted in ('ghp_' + 'A' * 36, 'thr_' + 'synthetic9'):
            with self.subTest(planted[:4]):
                provider['prerequisites'] = provider['prerequisites'] + ['planted ' + planted]
                self.answer_time.write_text(json.dumps(provider))
                out = self.tmp / ('planted-' + planted[:3])
                with self.assertRaises(gatherer().Fail) as refused, contextlib.redirect_stdout(io.StringIO()):
                    self.gather(out)
                self.assertIn('privacy scan', str(refused.exception))
                self.assertNotIn(planted, str(refused.exception))
                self.assertFalse((out / 'selection.json').exists(), 'a refused gather selects nothing')
                provider['prerequisites'] = provider['prerequisites'][:-1]

    def test_a_long_run_history_keeps_the_current_ci_counts(self):
        # R2: ci.yml's whole history is over the API's 1000-item limit; the current runs are few.
        answers = WR8.fixture()
        old = {'id': 7, 'run_attempt': 1, 'status': 'completed', 'conclusion': 'success',
               'created_at': '2029-06-01T10:00:00Z'}
        answers[WR8.RUNS] = {'total_count': 3315, 'workflow_runs': [old] * 100}
        run = WR8.fixture()[WR8.RUNS]['workflow_runs'][0]
        self.answer(answers, current={'in_progress': [run]})
        root, selection = self.gather()
        cards = {p['slot']: p for p in sources.select(root, selection, ENDED)}
        self.assertEqual({k: v for k, v in self.values(cards['activity']).items() if k.startswith('ci-')},
                         {'ci-running-ubuntu-24.04': 1, 'ci-queued-ubuntu-24.04': 1,
                          'ci-running-ubuntu-slim': 0, 'ci-queued-ubuntu-slim': 1, 'ci-cost-today-estimate': 0})

    def test_an_inconsistent_status_listing_gives_no_ci_counts(self):
        # Fail closed: a run in two status listings, or listed under a status it does not have, is no count.
        run = WR8.fixture()[WR8.RUNS]['workflow_runs'][0]
        for name, current in (('twice', {'in_progress': [run], 'queued': [run]}),
                              ('mislabelled', {'queued': [run]})):
            with self.subTest(name):
                self.answer(WR8.fixture(), current=current)
                root, selection = self.gather(self.tmp / name)
                cards = {p['slot']: p for p in sources.select(root, selection, ENDED)}
                ci = [m for m in cards['activity']['metrics'] if m['id'].startswith('ci-running')
                      or m['id'].startswith('ci-queued')]
                self.assertEqual(len(ci), 4)
                self.assertTrue(all(m['value'] is None for m in ci), name)

    def test_an_escaped_secret_in_a_valid_journey_refuses_the_gather(self):
        # R3: JSON escapes hide a credential from a byte scan; the native journey reader still accepts it.
        doc = json.loads(self.journeys.read_text())
        for planted, escaped in (('ghp_' + 'A' * 36, '\\u0067hp_' + 'A' * 36),
                                 ('github_pat_' + 'B' * 22, 'github\\u005fpat_' + 'B' * 22)):
            with self.subTest(planted[:4]):
                marker = 'synthetic-escape-marker'
                doc['sources']['s1'] = doc['sources']['s1'].split('-x-')[0] + '-x-' + marker
                wire = json.dumps(doc, indent=2).replace(marker, escaped)
                self.assertNotIn(planted, wire)
                decoded = json.loads(wire)
                self.assertIn(planted, decoded['sources']['s1'])
                gatherer()  # loads the journey reader
                rework.J.validate(decoded)  # a valid native artifact
                journeys = self.tmp / ('escaped-' + planted[:3] + '.json')
                journeys.write_text(wire)
                out = self.tmp / ('escaped-' + planted[:3])
                with self.assertRaises(gatherer().Fail) as refused:
                    self.gather(out, journeys=journeys)
                self.assertIn('privacy scan', str(refused.exception))
                self.assertNotIn(planted, str(refused.exception))
                self.assertFalse(out.exists(), 'a refused gather writes nothing')


if __name__ == '__main__':
    unittest.main()
