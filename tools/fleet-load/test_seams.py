#!/usr/bin/env python3
"""Review regressions at identity and installed-candidate process boundaries.

R1: changed cost/approval-read semantics must change the measurement model;
the original snapshot omitted reused sources, and only tested replay I/O.
R2: an existing binary must reflect changed candidate source; the original
frontier proof began with an already-current binary and missed stale reuse.
All changed sources here belong to private temporary fixtures, never the repo.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class FixtureBytecodeProof(unittest.TestCase):
    def test_equal_size_equal_timestamp_source_change_invalidates_the_cache(self):
        load = module('bytecode_load', HERE / 'load.py')
        with tempfile.TemporaryDirectory(prefix='fixture-bytecode-') as directory:
            root = Path(directory)
            source = root / 'synthetic.py'
            alias = root / 'alias.py'
            alias.symlink_to(source)
            for module_path in (source, alias):
                with self.subTest(source=module_path.name):
                    source.write_text('answer = "before"\n')
                    cache = root / ('cache-' + module_path.stem)
                    load.prepare_bytecode(cache, [module_path])
                    program = ('import importlib.util,sys; '
                               's=importlib.util.spec_from_file_location("synthetic",sys.argv[1]); '
                               'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(m.answer)')
                    def read():
                        return subprocess.check_output([sys.executable, '-I', '-B', '-X', 'pycache_prefix=' + str(cache),
                                                        '-c', program, str(module_path)], text=True).strip()
                    self.assertEqual(read(), 'before')
                    timestamp = source.stat().st_mtime_ns
                    source.write_text('answer = "after!"\n')
                    os.utime(source, ns=(timestamp, timestamp))
                    self.assertEqual(read(), 'after!', 'recording cache hid a changed fixture source')



class MeasurementIdentityProof(unittest.TestCase):
    def test_changed_response_or_revision_model_cannot_compare_silently(self):
        with tempfile.TemporaryDirectory(prefix='scale-model-') as directory:
            root = Path(directory)
            shutil.copytree(HERE, root / HERE.relative_to(ROOT))
            for relative in ['docs/agents/fleet.md', 'skills/launch-fleet/scripts/fixtures/check.json',
                             'skills/launch-fleet/scripts/fixtures/gh.py', 'skills/launch-fleet/scripts/fixtures/revision.sh',
                             'skills/launch-fleet/scripts/fleet.sh', 'tests/fleet/b5_fake.rs',
                             'tests/fixture-entrypoints/cli.rs', 'tests/fixture-entrypoints/fixture.rs']:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            scale = module('model_copy', root / 'tools/fleet-load/scale.py')
            installed = dict(binary_sha256='a' * 64, fixture_sha256='b' * 64)
            fleet = root / 'skills/launch-fleet/scripts/fleet.sh'
            before = scale.identity(fleet, installed)
            for relative, old, new in [
                ('skills/launch-fleet/scripts/fixtures/gh.py', "'cost': cost,", "'cost': cost + 7,"),
                ('skills/launch-fleet/scripts/fixtures/revision.sh', '--json body', '--json title'),
            ]:
                with self.subTest(source=relative):
                    path = root / relative
                    original = path.read_text()
                    self.assertIn(old, original)
                    path.write_text(original.replace(old, new))
                    after = scale.identity(fleet, installed)
                    self.assertNotEqual(before, after, 'changed measurement semantics retained the entire identity')
                    # The public comparator must treat this as a model change,
                    # rather than an allowed candidate optimization.
                    baseline = scale.api.read(root / 'tools/fleet-load/scale-50/fixtures/report-v1.json')
                    candidate = copy.deepcopy(baseline)
                    baseline['measurement_model'] = before['measurement_model']
                    candidate['measurement_model'] = after['measurement_model']
                    self.assertEqual(before['candidate'], after['candidate'])
                    scale.api.validate(baseline); scale.api.validate(candidate)
                    with self.assertRaisesRegex(ValueError, 'measurement_model'):
                        scale.api.compare(baseline, candidate)
                    path.write_text(original)


class InstalledBuildProof(unittest.TestCase):
    def test_source_change_refreshes_existing_example(self):
        load = module('seam_load', HERE / 'load.py')
        installed = load.extension('installed')
        with tempfile.TemporaryDirectory(prefix='scale-build-') as directory:
            root = Path(directory)
            # The normal FA3 constructor supplies the same approved frontier.
            workload = root / 'workload'; workload.mkdir()
            world = load.Workload(workload, load.SCRIPTS / 'fleet.sh').world
            host = next(line.split(': ', 1)[1] for line in subprocess.check_output(
                ['rustc', '-vV'], text=True).splitlines() if line.startswith('host: '))
            for setting in ('env', 'config'):
                with self.subTest(target_setting=setting):
                    checkout = root / ('candidate-' + setting); checkout.mkdir()
                    for relative in ['docs/agents/fleet.md', 'tests/fleet/b5_fake.rs']:
                        target = checkout / relative; target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(ROOT / relative, target)
                    (checkout / 'Cargo.toml').write_text('[package]\nname="openwiz-tests"\nversion="0.0.0"\nedition="2024"\n')
                    (checkout / 'Cargo.lock').write_text('version = 4\n\n[[package]]\nname = "openwiz-tests"\nversion = "0.0.0"\n')
                    examples = checkout / 'examples'; examples.mkdir()
                    source = examples / 'openwiz.rs'
                    def write_program(marker):
                        # This std-only Cargo fixture tests build provenance, not tick
                        # semantics (the real dispatcher has its own frontier proof).
                        doc = dict(schema='openwiz.fleet-tick.v1', mode='dry_run', marker=marker,
                                   actions=[dict(ticket=n, kind='start_builder', rule='frontier',
                                                 outcome=dict(state='planned')) for n in range(1001, 1101) if n % 20])
                        source.write_text('fn main() { std::fs::write("calls.log", "").unwrap(); println!("{}", r###"' + json.dumps(doc) + '"###); }\n')
                    write_program('old compiled candidate')
                    initial_env = dict(os.environ, CARGO_TARGET_DIR=str(checkout / 'target'))
                    initial_env.pop('CARGO_BUILD_TARGET', None)
                    subprocess.run(['cargo', 'build', '--locked', '-p', 'openwiz-tests', '--example', 'openwiz', '-j', '2'],
                                   cwd=checkout, check=True, capture_output=True, timeout=60,
                                   env=initial_env)
                    build_env = dict(initial_env, CARGO_TARGET_DIR=str(root / 'ambient-target'))
                    if setting == 'env':
                        build_env['CARGO_BUILD_TARGET'] = host
                    else:
                        config = checkout / '.cargo'; config.mkdir()
                        (config / 'config.toml').write_text('[build]\ntarget="' + host + '"\n')
                    with mock.patch.object(installed, 'ROOT', checkout), \
                         mock.patch.dict(os.environ, build_env, clear=True):
                        before = installed.run(world)
                        previous = source.stat().st_mtime_ns
                        write_program('new candidate source with a different compiled marker')
                        os.utime(source, ns=(previous + 2_000_000_000, previous + 2_000_000_000))
                        after = installed.run(world)
                    self.assertNotEqual(before['binary_sha256'], after['binary_sha256'],
                                        'existing example ignored the changed Rust candidate source')


def rest(endpoint, etag=None, next=None):
    """One recorded REST read, with the next page its response's Link named (fake.py's `next`)."""
    args = ['api', '--include', '-H', 'Accept: application/vnd.github+json']
    return dict(tool='gh', args=args + (['-H', f'If-None-Match: {etag}'] if etag else []) + [endpoint], next=next)


GRAPHQL = dict(tool='gh', args=['api', 'graphql', '-f', 'query=query Spec { synthetic }'])
REPO = 'repos/synthetic-owner/synthetic-repo'


class BackOffGate(unittest.TestCase):
    """S4 (#2634 R2): a back-off tick makes its one GraphQL read, after only GI1's saved probes (#2543)."""

    @classmethod
    def setUpClass(cls):
        reader = module('gate_load', HERE / 'load.py')
        cls.gate = staticmethod(reader.backoff_gate)
        cls.saved_probe = staticmethod(reader.saved_ticket_probe)

    def test_cold_cache_allows_the_one_graphql_read_only(self):
        self.assertTrue(self.gate([GRAPHQL], None))
        # The review's candidate: an unconditional repository GET before the first GraphQL read.
        self.assertFalse(self.gate([rest(REPO), GRAPHQL], None))

    def test_changed_primer_requires_a_known_baseline_and_current_clock(self):
        endpoint = REPO + '/issues/5/sub_issues?per_page=100'
        probe = dict(endpoint=endpoint, etags=['"a"'])
        calls = [dict(rest(endpoint, '"a"'), http_status=200, status=0, etag='"b"'), GRAPHQL]
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            for replayable, tags, at, now, allowed in [
                    (False, ['"a"'], 0, 60, True),
                    (False, ['"-"'], 0, 60, False),
                    (True, ['"a"'], 0, 60, True),
                    (False, ['"a"'], 0, 1800, False),
                    (False, ['"a"'], 60, 0, False)]:
                with self.subTest(replayable=replayable, tags=tags, at=at, now=now):
                    body = dict(repo='synthetic-owner/synthetic-repo', replayable=replayable,
                                read_at=at, probes=[dict(probe, etags=tags)])
                    (cache / 'unchanged-spec-5.json').write_text(json.dumps(dict(body=json.dumps(body))))
                    cut = self.saved_probe(cache, 5, now)
                    self.assertEqual(self.gate(calls, [REPO, endpoint], cut), allowed)

    def test_changed_ticket_list_requires_observed_change_and_complete_pages(self):
        endpoint = REPO + '/issues/5/sub_issues?per_page=100'
        page2 = 'repositories/1/issues/5/sub_issues?per_page=100&page=2'
        cut = dict(endpoint=endpoint, etags=['"a"', '"b"'])
        saved = [REPO, endpoint]
        probes = [dict(rest(endpoint, '"a"', next=page2), http_status=304, status=1, etag='"a"'),
                  dict(rest(page2, '"b"'), http_status=200, status=0, etag='"c"')]
        self.assertTrue(self.gate(probes + [GRAPHQL], saved, cut))
        unchanged = copy.deepcopy(probes)
        unchanged[1].update(http_status=304, status=1, etag='"b"')
        self.assertFalse(self.gate(unchanged + [GRAPHQL], saved, cut))
        self.assertFalse(self.gate(probes[:1] + [GRAPHQL], saved, cut))
        self.assertFalse(self.gate(probes + [GRAPHQL], saved))
        self.assertFalse(self.gate(probes + [rest(REPO + '/pulls/9'), GRAPHQL], saved, cut))
        for field in ['etag', 'http_status', 'status']:
            missing = copy.deepcopy(probes)
            del missing[1][field]
            self.assertFalse(self.gate(missing + [GRAPHQL], saved, cut))
        # Fresh pagination metadata matters even when every page says 304.
        longer = dict(cut, etags=['"a"'])
        self.assertTrue(self.gate(unchanged + [GRAPHQL], saved, longer))

    def test_warm_cache_allows_exactly_the_saved_probes_once(self):
        saved = [REPO, REPO + '/issues/5/timeline?per_page=100']
        page2 = 'repositories/1/issues/5/timeline?per_page=100&page=2'
        probes = [rest(REPO, '"a"'), rest(REPO + '/issues/5/timeline?per_page=100', '"b"', next=page2),
                  rest(page2, '"c"')]
        self.assertTrue(self.gate(probes + [GRAPHQL], saved))
        refused = {
            'unrelated read': probes + [rest(REPO + '/pulls/9'), GRAPHQL],
            'repeated probe': probes + [rest(REPO, '"a"'), GRAPHQL],
            'missing probe': probes[1:] + [GRAPHQL],
            'stray later page': probes + [rest('repositories/1/issues/6/timeline?per_page=100&page=2'), GRAPHQL],
            'write': probes + [dict(tool='gh', args=['api', '--method', 'PATCH', REPO + '/issues/comments/1']), GRAPHQL],
            'read after graphql': probes + [GRAPHQL, rest(REPO + '/pulls/9')],
            # The re-check's candidate: a later page of a saved path that no response linked to.
            'unlinked later page': probes + [rest('repositories/1/issues/5/timeline?per_page=100&page=50'), GRAPHQL],
            'page before its link': [probes[2]] + probes[:2] + [GRAPHQL],
            'linked page read twice': probes + [rest(page2, '"c"'), GRAPHQL],
            'no graphql': probes,
        }
        for name, calls in refused.items():
            with self.subTest(name):
                self.assertFalse(self.gate(calls, saved))
        self.assertTrue(self.gate([GRAPHQL], saved))  # a saved entry fleet.sh did not use: no probe


if __name__ == '__main__':
    unittest.main()
