#!/usr/bin/env python3
"""WR9: the War room published like the board, on a local bare origin only.

Fake chromium and gh (fixtures/publish/), a synthetic CI point as the one
selected source, and git read-back of every ref. No network, no live read.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FAKES = HERE / 'fixtures' / 'publish'
AT = '2030-01-02T12:03:00Z'
NEXT = '2030-01-02T13:07:00Z'
LINK = 'https://github.com/synthetic-owner/work/issues/4001'
# WRD4 (#877): the original page HTML is published beside its pictures, in the same commit.
# WRD5 (#883): the whole site, home (war-room.html) and its five child pages, in that one commit.
SITE = ['war-room-cost.html', 'war-room-health.html', 'war-room-quality.html', 'war-room-skills.html',
        'war-room-speed.html', 'war-room.html']
PAGES = sorted(['README.md', 'war-room-phone.png', 'war-room.png'] + SITE)
FILES = sorted(PAGES + ['samples/2030-01-02T12-00-00Z.json'])


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(cwd, *args):
    return subprocess.run(['git', '-C', str(cwd), *args], check=True, capture_output=True, text=True).stdout


def png_size(data):
    assert data[:8] == b'\x89PNG\r\n\x1a\n' and data[12:16] == b'IHDR'
    return struct.unpack('>II', data[16:24])


class Publish(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='war-room-publish-'))
        self.addCleanup(shutil.rmtree, self.tmp)
        self.origin = self.tmp / 'origin.git'
        git(self.tmp, 'init', '-q', '--bare', str(self.origin))
        seed = self.tmp / 'seed'
        git(self.tmp, 'init', '-q', '-b', 'main', str(seed))
        (seed / 'note.txt').write_text('synthetic main\n')
        git(seed, 'add', 'note.txt')
        git(seed, '-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.invalid',
            'commit', '-q', '-m', 'synthetic main')
        git(seed, 'push', '-q', str(self.origin), 'HEAD:refs/heads/main', 'HEAD:refs/heads/other',
            'HEAD:refs/tags/v0')
        self.before = self.refs()
        # One selected synthetic source: an existing CI bench point.
        self.sources = self.tmp / 'sources'
        self.sources.mkdir()
        point = {'schema': 'closedwiz.ci-bench.v1', 'label': 'synthetic window',
                 'since': '2030-01-01T08:00:00Z', 'until': '2030-01-02T08:00:00Z',
                 'hours': 24, 'robots': 5, 'runs': 4, 'jobs': 8, 'merged_prs': 3,
                 'merged_per_hour': 0.125, 'code_runs': None, 'legacy': None}
        raw = json.dumps(point)
        (self.sources / 'point.json').write_text(raw)
        self.selection = self.tmp / 'selection.json'
        self.selection.write_text(json.dumps([{
            'kind': 'ci_bench', 'slot': 'ci_bench', 'path': 'point.json',
            'sha256': hashlib.sha256(raw.encode()).hexdigest(),
            'observed_at': '2030-01-02T12:00:00Z', 'evidence': [LINK]}]))
        self.chromium_log = self.tmp / 'chromium.log'
        self.gh_log = self.tmp / 'gh.log'
        self.env = dict(os.environ, PATH=str(FAKES) + os.pathsep + os.environ['PATH'],
                        FAKE_CHROMIUM_LOG=str(self.chromium_log), FAKE_GH_LOG=str(self.gh_log))
        self.env.pop('FAKE_CHROMIUM_FAIL', None)

    def refs(self):
        return dict(line.split(' ', 1)[::-1] for line in
                    git(self.origin, 'for-each-ref', '--format=%(objectname) %(refname)').splitlines())

    def publish(self, at=AT, selection=None, **env):
        selection = self.selection if selection is None else selection
        return subprocess.run([sys.executable, '-I', str(HERE / 'publish.py'), 'publish',
                               '--remote', str(self.origin), '--at', at,
                               '--source-root', str(self.sources), '--selection', str(selection)],
                              env=dict(self.env, **env), capture_output=True, text=True)

    def collect(self, at):
        return subprocess.run([sys.executable, '-I', str(HERE / 'publish.py'), 'collect',
                               '--remote', str(self.origin), '--at', at,
                               '--source-root', str(self.sources), '--selection', str(self.selection)],
                              env=self.env, capture_output=True, text=True)

    def branch(self):
        return self.refs().get('refs/heads/war-room')

    def files(self, ref='refs/heads/war-room'):
        return sorted(git(self.origin, 'ls-tree', '-r', '--name-only', ref).split())

    def show(self, path, ref='refs/heads/war-room'):
        return subprocess.run(['git', '-C', str(self.origin), 'show', ref + ':' + path],
                              check=True, capture_output=True).stdout

    def test_publish_writes_only_the_war_room_branch(self):
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        after = self.refs()
        self.assertEqual({k: v for k, v in after.items() if k != 'refs/heads/war-room'}, self.before)
        self.assertEqual(self.files(), FILES)
        readme = self.show('README.md').decode()
        self.assertIn('**Last good render:** 2030-01-02T12:03:00Z', readme)
        self.assertIn('<picture><source media="(max-width: 700px)" srcset="war-room-phone.png">'
                      '<img alt="The War room" src="war-room.png"></picture>', readme)
        # Every bench is listed in text a phone reads natively; the CI bench is measured.
        self.assertIn('| CI bench | known | 2 of 2 |', readme)
        self.assertIn('| All-in cost per merged PR | unavailable | 0 of 0 |', readme)
        for bench in ('EB6', 'EB7', 'EB8', 'EB9', 'Skills eval', 'Ticket journeys', 'Rework rate'):
            self.assertIn('| %s |' % bench, readme)
        # WRD3: the v3 page's own widths, 1440 CSS px and its 390 px phone layout drawn at 2x.
        self.assertEqual(png_size(self.show('war-room-phone.png')), (780, 3000))
        self.assertEqual(png_size(self.show('war-room.png')), (1440, 1500))
        self.assertIn('390,1500 2 screenshot', self.chromium_log.read_text())
        sample = json.loads(self.show('samples/2030-01-02T12-00-00Z.json'))
        self.assertEqual(sample['sample_at'], '2030-01-02T12:00:00Z')
        self.assertFalse(self.gh_log.exists(), 'the publish reads nothing from GitHub')

    def test_consecutive_ticks_carry_history_forward(self):
        self.assertEqual(self.publish().returncode, 0)
        first = self.show('samples/2030-01-02T12-00-00Z.json')
        self.assertEqual(self.publish(NEXT).returncode, 0)
        # The same five-minute boundary again reuses its saved sample; nothing is duplicated.
        self.assertEqual(self.publish('2030-01-02T13:09:59Z').returncode, 0)
        self.assertEqual(self.files(), sorted(PAGES + ['samples/2030-01-02T12-00-00Z.json',
                                                       'samples/2030-01-02T13-05-00Z.json']))
        self.assertEqual(self.show('samples/2030-01-02T12-00-00Z.json'), first)
        changed = git(self.origin, 'log', '--format=', '--name-status', 'refs/heads/war-room', '--', 'samples')
        self.assertEqual(sorted(changed.split()), ['A', 'A', 'samples/2030-01-02T12-00-00Z.json',
                                                   'samples/2030-01-02T13-05-00Z.json'])
        self.assertEqual(len(git(self.origin, 'rev-list', 'refs/heads/war-room').split()), 3)
        readme = self.show('README.md').decode()
        self.assertIn('**Last good render:** 2030-01-02T13:09:59Z', readme)
        self.assertIn('sample 2030-01-02T13:05:00Z', readme)
        self.assertIn('2 saved samples', readme)

    def test_a_failed_read_or_render_publishes_nothing(self):
        self.assertEqual(self.publish().returncode, 0)
        good, good_html = self.branch(), self.show('war-room.html')
        bad_selection = self.tmp / 'bad.json'
        bad_selection.write_text('{"not": "a selection"}')
        for name, result in (
                ('render', self.publish(NEXT, FAKE_CHROMIUM_FAIL='1')),
                ('blank render', self.publish(NEXT, FAKE_CHROMIUM_HEIGHT='0')),
                ('read', self.publish(NEXT, selection=bad_selection)),
                ('bad time', self.publish('2030-01-02 13:07'))):
            with self.subTest(name):
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('nothing published', result.stderr)
                self.assertEqual(self.branch(), good)
        self.assertIn('**Last good render:** 2030-01-02T12:03:00Z', self.show('README.md').decode())
        self.assertEqual(self.show('war-room.html'), good_html)

    def test_a_failed_child_page_publishes_nothing_and_keeps_the_previous_site(self):
        # catches: a publication that fails after one child page (render, then any later step) yet
        # pushes a new home beside stale or missing children, or touches the saved samples. P11.
        publish = load(HERE / 'publish.py', 'wrd5_publish')
        self.assertEqual(self.publish().returncode, 0)
        good = self.branch()
        site = {name: self.show(name) for name in SITE}
        sample = self.show('samples/2030-01-02T12-00-00Z.json')
        real = publish.page.child
        calls = []

        def fail_after_one(slug, *args, **kwargs):
            calls.append(slug)
            if len(calls) == 2:
                raise ValueError('synthetic child failure')
            return real(slug, *args, **kwargs)
        read = publish.selection_reader(self.sources, self.selection)
        with mock.patch.dict(os.environ, {'PATH': self.env['PATH'], 'FAKE_CHROMIUM_LOG': str(self.chromium_log)}), \
                mock.patch.object(publish.page, 'child', side_effect=fail_after_one), self.assertRaises(ValueError):
            publish.publish(str(self.origin), NEXT, read)
        self.assertEqual(calls, ['speed', 'health'])
        self.assertEqual(self.branch(), good)
        self.assertEqual({name: self.show(name) for name in SITE}, site)
        self.assertEqual(self.show('samples/2030-01-02T12-00-00Z.json'), sample)
        # The scan reads every child too: a planted value in one child refuses the whole site.
        with mock.patch.dict(os.environ, {'PATH': self.env['PATH'], 'FAKE_CHROMIUM_LOG': str(self.chromium_log)}), \
                mock.patch.object(publish.page, 'child', side_effect=lambda slug, *a, **k: real(slug, *a, **k).replace(
                    '</main>', ('ghp' + '_' + 'Synthetic0123456789abcdef' if slug == 'skills' else '') + '</main>')), \
                self.assertRaises(publish.Fail):
            publish.publish(str(self.origin), NEXT, read)
        self.assertEqual(self.branch(), good)

    def test_the_first_site_publication_replaces_a_one_page_branch(self):
        # catches: the first WRD5 publication refusing the existing WRD4 branch (one war-room.html,
        # no child pages), or leaving its old one-page home beside the new children.
        self.assertEqual(self.publish().returncode, 0)
        work = self.tmp / 'one-page'
        git(self.tmp, 'clone', '-q', '-b', 'war-room', str(self.origin), str(work))
        for name in SITE[:-1]:
            (work / name).unlink()
        (work / 'war-room.html').write_text('<!doctype html><title>one page</title>\n')
        git(work, 'add', '--all')
        git(work, '-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.invalid', 'commit', '-q', '-m', 'one page')
        git(work, 'push', '-q', 'origin', 'HEAD:refs/heads/war-room')
        result = self.publish(NEXT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([f for f in self.files() if not f.startswith('samples/')], PAGES)
        self.assertNotIn(b'one page', self.show('war-room.html'))
        self.assertIn(b'<nav class="site"', self.show('war-room-speed.html'))

    def test_the_height_bound_is_in_device_pixels(self):
        # #2432 R1: a full gathered page is over 20,000 CSS px tall. The bound is on the drawn
        # picture, CSS height times scale, at most 65,000 device px: the phone picture (2x) binds.
        for height, drawn in (('28302', True), ('32500', True), ('32501', False), ('65001', False)):
            with self.subTest(height):
                before = self.branch()
                result = self.publish(NEXT if before else AT, FAKE_CHROMIUM_HEIGHT=height)
                if drawn:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(png_size(self.show('war-room.png')), (1440, int(height)))
                    self.assertEqual(png_size(self.show('war-room-phone.png')), (780, 2 * int(height)))
                    git(self.origin, 'update-ref', '-d', 'refs/heads/war-room')
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('the page is too tall to draw; nothing published', result.stderr)
                    self.assertIsNone(self.branch())

    def test_a_failed_selected_artifact_publishes_nothing(self):
        # R3: a valid selection whose pinned artifact is missing or corrupt is a failed read.
        self.assertEqual(self.publish().returncode, 0)
        good = self.branch()
        point = self.sources / 'point.json'
        raw = point.read_bytes()
        for name, change in (('missing', point.unlink), ('corrupt', lambda: point.write_bytes(raw + b' '))):
            with self.subTest(name):
                change()
                for run in (self.publish, self.collect):
                    result = run(NEXT)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('a selected source could not be read; nothing published', result.stderr)
                    self.assertEqual(self.branch(), good)
                point.write_bytes(raw)
        self.assertIn('**Last good render:** 2030-01-02T12:03:00Z', self.show('README.md').decode())

    def test_five_minute_collection_survives_hourly_publication(self):
        # R2: twelve boundaries an hour are collected; one genuinely missed stays absent.
        boundaries = ['2030-01-02T12-%02d-00Z' % m for m in range(0, 60, 5) if m != 25]
        for name in boundaries:
            result = self.collect(name[:13] + ':' + name[14:16] + ':30Z')
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.chromium_log.exists(), 'collection draws nothing')
        self.assertEqual(self.files(), ['samples/%s.json' % n for n in boundaries])
        collected = {n: self.show('samples/%s.json' % n) for n in boundaries}
        result = self.publish('2030-01-02T13:02:00Z')
        self.assertEqual(result.returncode, 0, result.stderr)
        saved = ['samples/%s.json' % n for n in boundaries + ['2030-01-02T13-00-00Z']]
        self.assertEqual(self.files(), sorted(PAGES + saved))
        self.assertNotIn('samples/2030-01-02T12-25-00Z.json', self.files())
        for n, data in collected.items():
            self.assertEqual(self.show('samples/%s.json' % n), data)
        self.assertIn('12 saved samples', self.show('README.md').decode())
        self.assertEqual(self.refs()['refs/heads/main'], self.before['refs/heads/main'])

    def push_to_branch(self, path, data):
        work = self.tmp / 'edit'
        shutil.rmtree(work, ignore_errors=True)
        git(self.tmp, 'clone', '-q', '-b', 'war-room', str(self.origin), str(work))
        (work / path).parent.mkdir(parents=True, exist_ok=True)
        (work / path).write_bytes(data)
        git(work, 'add', '--all')
        git(work, '-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.invalid',
            'commit', '-q', '-m', 'synthetic edit')
        git(work, 'push', '-q', 'origin', 'HEAD:refs/heads/war-room')
        return self.branch()

    def test_the_gathered_snapshot_is_published_scanned_and_only_while_drawn(self):
        # catches (MT13, #1049): the snapshot the PRs-an-hour chart is drawn from left off the branch,
        # refused as an unexpected file by the next publish, published unscanned or as any JSON, a
        # second snapshot-like file let through, or an old snapshot kept beside a page not drawn from it.
        publish = load(HERE / 'publish.py', 'mt13_publish')
        doc = json.loads((HERE / 'fixtures' / 'collector' / 'snapshot.json').read_text())
        doc['collected_at'] = '2030-01-02T11:00:00Z'  # gathered before this render
        raw = json.dumps(doc).encode()
        beside = self.selection.parent / 'snapshot.json'  # where gather.py writes it
        beside.write_bytes(raw)
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.files(), sorted(FILES + ['snapshot.json']))
        self.assertEqual(self.show('snapshot.json'), raw)
        self.assertIn(b'id="figure-body-ci-bench-headline"', b''.join(self.show(name) for name in SITE))
        result = self.publish(NEXT)  # the saved snapshot is an allowed file on the branch
        self.assertEqual(result.returncode, 0, result.stderr)
        tree = self.tmp / 'tree'
        git(self.tmp, 'clone', '-q', '-b', 'war-room', str(self.origin), str(tree))
        shutil.rmtree(tree / '.git')
        page = '<html><body>synthetic page</body></html>'
        publish.scan(tree, page)
        for name, path, data in (('planted token', 'snapshot.json', raw.replace(b'"repository": "', b'"repository": "ghp' + b'_Synthetic0123456789abcdef', 1)),
                                 ('not a snapshot', 'snapshot.json', b'{"schema": "synthetic"}\n'),
                                 ('another snapshot', 'snapshot-old.json', raw)):
            with self.subTest(name):
                copy = self.tmp / 'copy'
                shutil.rmtree(copy, ignore_errors=True)
                shutil.copytree(tree, copy)
                (copy / path).write_bytes(data)
                with self.assertRaises(publish.Fail):
                    publish.scan(copy, page)
        beside.unlink()
        result = self.publish('2030-01-02T14:11:00Z')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('snapshot.json', self.files())

    def test_a_broken_branch_publishes_nothing(self):
        self.assertEqual(self.publish().returncode, 0)
        sample = self.show('samples/2030-01-02T12-00-00Z.json')
        record = json.loads(sample)
        record['assembled_at'] = '2030-01-02T12:01:00Z'
        cases = (('unexpected file', 'notes.txt', b'synthetic\n'),
                 # WRD5: only the six site pages; a seventh page is not part of the site.
                 ('unexpected page', 'war-room-extra.html', self.show('war-room.html')),
                 ('rewritten sample', 'samples/2030-01-02T12-00-00Z.json',
                  (json.dumps(record, sort_keys=True, separators=(',', ':')) + '\n').encode()),
                 ('malformed sample', 'samples/2030-01-02T12-05-00Z.json', b'{}\n'))
        for name, path, data in cases:
            with self.subTest(name):
                broken = self.push_to_branch(path, data)
                result = self.publish(NEXT)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('nothing published', result.stderr)
                self.assertEqual(self.branch(), broken)
                git(self.origin, 'update-ref', 'refs/heads/war-room', broken + '~1')

    def test_a_sample_rewritten_in_a_merge_publishes_nothing(self):
        # R4: a rewrite made only while resolving a merge is still a rewrite.
        self.assertEqual(self.publish().returncode, 0)
        work = self.tmp / 'merge'
        git(self.tmp, 'clone', '-q', '-b', 'war-room', str(self.origin), str(work))
        git(work, 'config', 'user.name', 'Synthetic')
        git(work, 'config', 'user.email', 'synthetic@example.invalid')
        git(work, 'checkout', '-q', '-b', 'side')
        readme = work / 'README.md'
        readme.write_text(readme.read_text().replace('# War room', '# War room side', 1))
        git(work, 'commit', '-qam', 'side')
        git(work, 'checkout', '-q', 'war-room')
        readme.write_text(readme.read_text() + 'synthetic\n')
        git(work, 'commit', '-qam', 'main side')
        git(work, 'merge', '-q', '--no-ff', '--no-commit', 'side')
        name = 'samples/2030-01-02T12-00-00Z.json'
        record = json.loads((work / name).read_text())
        record['assembled_at'] = '2030-01-02T12:04:00Z'
        (work / name).write_text(json.dumps(record, sort_keys=True, separators=(',', ':')) + '\n')
        git(work, 'add', name)
        git(work, 'commit', '-qm', 'merge')
        git(work, 'push', '-q', 'origin', 'HEAD:refs/heads/war-room')
        broken = self.branch()
        result = self.publish(NEXT)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('a saved sample was rewritten on the branch; nothing published', result.stderr)
        self.assertEqual(self.branch(), broken)

    def test_a_link_or_odd_mode_on_the_branch_publishes_nothing(self):
        # R5: an allowed name that is a link (or not a plain file) is refused before anything is written.
        self.assertEqual(self.publish().returncode, 0)
        good = self.branch()
        outside = self.tmp / 'outside.txt'
        for name, change in (('README.md', 'link'), ('war-room.png', 'link'), ('war-room.html', 'link'),
                             ('war-room-health.html', 'link'),
                             ('samples/2030-01-02T12-00-00Z.json', 'link'), ('war-room.png', 'executable')):
            with self.subTest(name, change=change):
                git(self.origin, 'update-ref', 'refs/heads/war-room', good)
                outside.write_text('synthetic original\n')
                work = self.tmp / 'link'
                shutil.rmtree(work, ignore_errors=True)
                git(self.tmp, 'clone', '-q', '-b', 'war-room', str(self.origin), str(work))
                if change == 'link':
                    (work / name).unlink()
                    (work / name).symlink_to(outside)
                else:
                    (work / name).chmod(0o755)
                git(work, 'add', '--all')
                git(work, '-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.invalid',
                    'commit', '-q', '-m', change)
                git(work, 'push', '-q', 'origin', 'HEAD:refs/heads/war-room')
                broken = self.branch()
                result = self.publish(NEXT)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('the branch holds an unexpected file; nothing published', result.stderr)
                self.assertEqual(self.branch(), broken)
                self.assertEqual(outside.read_text(), 'synthetic original\n')

    def test_privacy_scan_refuses_a_planted_secret(self):
        publish = load(HERE / 'publish.py', 'wr9_publish')
        self.assertEqual(self.publish().returncode, 0)
        tree = self.tmp / 'tree'
        git(self.tmp, 'clone', '-q', '-b', 'war-room', str(self.origin), str(tree))
        shutil.rmtree(tree / '.git')
        page = '<html><body>synthetic page</body></html>'
        publish.scan(tree, page)  # the published files pass
        sample = (tree / 'samples/2030-01-02T12-00-00Z.json').read_text()
        # Each planted value is assembled here, so no committed file carries one.
        plants = {'token': 'ghp' + '_' + 'Synthetic0123456789abcdef',
                  'thread id': 'thr' + '_' + 'abc123real',
                  'bearer credential': 'Authorization' + ': Bearer synthetic',
                  'email': 'jdoe' + '@' + 'corp-mail.net',
                  'private key': '-----BEGIN ' + 'RSA PRIVATE KEY-----',
                  'home path': '/home' + '/jdoe/notes',
                  'cloud id': 'proj' + '_' + 'Abc123',
                  'quoted decision': 'Ja' + 'ke: ' + '"ship it"'}
        for name, secret in plants.items():
            for target in ('README.md', 'war-room.html', 'war-room-cost.html', 'samples/2030-01-02T12-00-00Z.json', 'page'):
                with self.subTest(name, target=target):
                    copy = self.tmp / 'copy'
                    shutil.rmtree(copy, ignore_errors=True)
                    shutil.copytree(tree, copy)
                    planted_page = page
                    if target.endswith(('.md', '.html')):
                        (copy / target).write_text((tree / target).read_text() + secret + '\n')
                    elif target == 'page':
                        planted_page = page.replace('synthetic page', secret)
                    else:
                        planted = sample.replace('"label":"', '"label":"' + secret.replace('"', '\\"') + ' ', 1)
                        self.assertNotEqual(planted, sample)
                        (copy / target).write_text(planted)
                    with self.assertRaises(publish.Fail):
                        publish.scan(copy, planted_page)
        # A picture is checked as a picture; the page it was drawn from is scanned above.
        (tree / 'war-room.png').write_bytes(b'not a picture')
        with self.assertRaises(publish.Fail):
            publish.scan(tree, page)

    def test_publish_sh_runs_its_tests_first(self):
        # publish.sh beside a stub test file and a shim to the real publish.py.
        folder = self.tmp / 'sh'
        folder.mkdir()
        shutil.copy(HERE / 'publish.sh', folder)
        marker = self.tmp / 'tests-ran'
        (folder / 'test_publish.py').write_text(
            'import os, sys\nopen(os.environ["MARKER"], "a").write("ran\\n")\n'
            'sys.exit(int(os.environ["STUB_EXIT"]))\n')
        (folder / 'publish.py').write_text(
            'import os, runpy, sys\nsys.argv[0] = os.environ["REAL"]\n'
            'runpy.run_path(os.environ["REAL"], run_name="__main__")\n')
        env = dict(self.env, MARKER=str(marker), REAL=str(HERE / 'publish.py'))
        run = lambda code: subprocess.run(
            # The run time comes from the clock, so no 2030 source is selected here.
            ['sh', str(folder / 'publish.sh'), str(self.origin)], env=dict(env, STUB_EXIT=code), capture_output=True, text=True)
        failed = run('1')
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(marker.read_text(), 'ran\n')
        self.assertIsNone(self.branch(), 'a failed test publishes nothing')
        self.assertFalse(self.chromium_log.exists())
        passed = run('0')
        self.assertEqual(passed.returncode, 0, passed.stderr)
        self.assertEqual(marker.read_text(), 'ran\nran\n')
        # The run time comes from the clock here, so the one sample's name does too.
        files = self.files()
        self.assertEqual([f for f in files if not f.startswith('samples/')], PAGES)
        samples = [f for f in files if f.startswith('samples/')]
        self.assertEqual(len(samples), 1, samples)
        self.assertRegex(samples[0], r'^samples/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-00Z\.json$')
        self.assertEqual({k: v for k, v in self.refs().items() if k != 'refs/heads/war-room'}, self.before)

    def test_preview_draws_and_publishes_nothing(self):
        out = self.tmp / 'preview'
        result = subprocess.run([sys.executable, '-I', str(HERE / 'publish.py'), 'preview', '--out', str(out),
                                 '--at', AT, '--source-root', str(self.sources), '--selection', str(self.selection)],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sorted(p.name for p in out.iterdir()), PAGES)
        self.assertEqual(self.refs(), self.before)


class Workflow(unittest.TestCase):
    """The workflow, read with the repository's restricted YAML reader."""

    def setUp(self):
        reader = load(ROOT / 'tools/privacy-check/workflow.py', 'wr9_workflow')
        self.flow = reader.parse((ROOT / '.github/workflows/war-room.yml').read_text())
        self.jobs = self.flow['jobs']
        # #827: the proofs run from their own pull-request-only, read-only workflow.
        self.proof = reader.parse((ROOT / '.github/workflows/war-room-proof.yml').read_text())

    def test_hosted_runners_and_pull_request_only_proof(self):
        self.assertEqual(sorted(self.jobs), ['preview', 'publish'])
        self.assertEqual(sorted(self.proof['jobs']), ['proof'])
        for name, job in [*self.jobs.items(), *self.proof['jobs'].items()]:
            with self.subTest(name):
                self.assertEqual(job['runs-on'], 'ubuntu-24.04')
        for job in (self.proof['jobs']['proof'], self.jobs['preview']):
            self.assertEqual(job['if'], "github.event_name == 'pull_request'")
        # catches (#827): the proof workflow gaining a write, a schedule or a dispatch.
        self.assertEqual(set(self.proof['on']), {'pull_request'})
        self.assertEqual(self.proof['permissions'], {'contents': 'read'})
        self.assertNotIn('permissions', self.proof['jobs']['proof'])
        # R1: default off; nothing publishes until the orchestrator sets WAR_ROOM_PUBLISH to on.
        self.assertEqual(self.jobs['publish']['if'],
                         "vars.WAR_ROOM_PUBLISH == 'on' && github.event_name != 'pull_request' "
                         "&& github.ref == 'refs/heads/main'")
        self.assertNotIn('needs', self.jobs['publish'])
        self.assertEqual(set(self.flow['on']), {'schedule', 'workflow_dispatch', 'pull_request'})
        self.assertEqual(self.flow['on']['schedule'], [{'cron': '37 */6 * * *'}])

    def test_only_publish_writes_and_publication_is_serialised(self):
        self.assertEqual(self.flow['permissions'], {'contents': 'read'})
        for name, job in self.jobs.items():
            with self.subTest(name):
                permissions = job.get('permissions', {})
                writes = {k for k, v in permissions.items() if v == 'write'}
                self.assertEqual(writes, {'contents'} if name == 'publish' else set())
        self.assertEqual(self.jobs['publish']['concurrency'],
                         {'group': 'war-room-publication', 'cancel-in-progress': 'false'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
