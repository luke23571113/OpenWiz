#!/usr/bin/env python3
"""The proposal builder: a checked dry run plus fresh bound reads become one
private move.py proposal; drift, refused patches and stale bindings refuse."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_move import fixture  # noqa: E402

CHECKER = HERE.parent / 'privacy-check/check.py'
IMPORTER = HERE.parent / 'open-import/import.py'
TARGET = 'synthetic-org/openwiz'


class Proposal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.repo('source')
        self.public = self.repo('public')
        self.base = self.git(self.public, 'rev-parse', 'HEAD').strip()
        self.source_base = self.git(self.source, 'rev-parse', 'HEAD').strip()
        (self.source / 'crates/core/src/lib.rs').write_text('public change\n')
        (self.source / 'private').mkdir()
        (self.source / 'private/record').write_text('synthetic private record\n')
        self.git(self.source, 'add', '.')
        self.git(self.source, 'commit', '-qm', 'synthetic source change')
        self.source_head = self.git(self.source, 'rev-parse', 'HEAD').strip()
        # The real O3 checker, anchored at the synthetic public root (as test_carriage does).
        self.checker = self.root / 'checker.py'
        self.checker.write_text('import sys\nsys.dont_write_bytecode=True\n' +
            f'sys.path.insert(0, {str(CHECKER.parent)!r})\nimport check\n' +
            f'check.PUBLIC_ROOT={self.base!r}\ncheck.PUBLIC_ANCHOR={self.base!r}\n' +
            'sys.exit(check.main())\n')
        self.literals = self.root / 'literals'
        self.literals.write_text('synthetic-unused-literal\n')
        world = fixture()
        world['graph']['items'].append(dict(number=9010, kind='pull_request', title='Synthetic PR',
            labels=['bug'], milestone='Infra', parent=None, blockers=[], state='open'))
        world['bodies']['9010'] = 'Closes #9002.\nSynthetic PR body.'
        world['pulls'] = {'9010': dict(source_base=self.source_base, observed_base=self.source_base,
                                       source_head=self.source_head)}
        self.world = self.root / 'world.json'
        self.world.write_text(json.dumps(dict(move=world, created={}, comments={}, writes=0,
                                              refs={}, public_base=self.base)))
        self.env = dict(os.environ, OPEN_TICKETS_WORLD=str(self.world), OPEN_TICKETS_LOG=str(self.root / 'calls'))
        self.dry = self.root / 'dry-run'
        self.out = self.root / 'private-proposal'

    def repo(self, name):
        root = self.root / name
        root.mkdir()
        self.git(root, 'init', '-qb', 'main')
        self.git(root, 'config', 'user.name', 'Synthetic')
        self.git(root, 'config', 'user.email', 'synthetic@users.noreply.github.com')
        p = root / 'crates/core/src/lib.rs'
        p.parent.mkdir(parents=True)
        p.write_text('old\n')
        self.git(root, 'add', '.')
        self.git(root, 'commit', '-qm', 'synthetic baseline')
        return root

    def git(self, root, *args):
        r = subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def cli(self, program, *flags, ok=True):
        r = subprocess.run([sys.executable, '-I', str(HERE / program), *flags],
                           capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode == 0, ok, r.stdout + r.stderr)
        if not ok:
            self.assertTrue(r.stderr.startswith('refused:'), r.stderr)
            self.assertNotIn('Traceback', r.stderr)
        return r

    def collect(self, *extra):
        common = ['--gh', str(HERE / 'fake-gh'), '--target', TARGET, '--out', str(self.dry),
                  '--checker', str(self.checker), '--literals', str(self.literals), '--snapshot-attempts', '1', *extra]
        self.cli('collect.py', *common)
        self.cli('collect.py', *[v for v in common if v not in extra], '--check')

    def build(self, *extra, ok=True, out=None):
        return self.cli('proposal.py', '--dry-run', str(self.dry), '--out', str(out or self.out),
                        '--gh', str(HERE / 'fake-gh'), '--checker', str(self.checker),
                        '--literals', str(self.literals), '--importer', str(IMPORTER),
                        '--source-repo', str(self.source), '--destination', str(self.public),
                        '--destination-main', self.base, '--date', '2030-01-02', *extra, ok=ok)

    def move_dry(self, plan, ok=True):
        return self.cli('move.py', '--plan', str(plan), '--state-dir', str(self.root / 'state'),
                        '--map-out', str(self.root / 'map.tsv'), '--checker', str(self.checker),
                        '--literals', str(self.literals), '--importer', str(IMPORTER),
                        '--git', str(HERE / 'fake-git'), '--gh', str(HERE / 'fake-gh'), ok=ok)

    def move_apply(self, plan, ok=True):
        return self.cli('move.py', '--plan', str(plan), '--state-dir', str(self.root / 'state'),
                        '--map-out', str(self.root / 'map.tsv'), '--checker', str(self.checker),
                        '--literals', str(self.literals), '--importer', str(IMPORTER),
                        '--git', str(HERE / 'fake-git'), '--gh', str(HERE / 'fake-gh'), '--apply', ok=ok)

    def world_edit(self, change):
        world = json.loads(self.world.read_text())
        change(world)
        self.world.write_text(json.dumps(world))

    def test_complete_private_proposal_is_accepted_by_move_dry_mode(self):
        self.collect()
        before = self.world.read_bytes()
        summary = json.loads(self.build().stdout)
        self.assertEqual(self.world.read_bytes(), before)  # no write of any kind
        plan = self.out / 'proposal.json'
        self.assertEqual(stat.S_IMODE(self.out.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(plan.stat().st_mode), 0o600)
        for path in (self.out / 'patches').rglob('*'):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode) & 0o077, 0, path)
        proposal = json.loads(plan.read_text())
        self.assertEqual(summary['proposal_sha256'], hashlib.sha256(plan.read_bytes()).hexdigest())
        self.assertEqual(sorted(proposal), ['approvals', 'bodies', 'closures', 'date', 'excluded_targets',
                                            'graph', 'merges', 'pulls', 'stays_private_prs', 'target'])
        self.assertEqual(proposal['stays_private_prs'], [])
        self.assertEqual(proposal['target'], TARGET)
        self.assertEqual(proposal['date'], '2030-01-02')
        # Raw source bodies, keyed by old number, for every moving item only.
        self.assertEqual(proposal['bodies'], {k: v for k, v in fixture()['bodies'].items()} |
                         {'9010': 'Closes #9002.\nSynthetic PR body.'})
        self.assertEqual(proposal['merges'], {'9004': [{'pull_request': 9900, 'merge': 'a' * 40}]})
        self.assertEqual(proposal['closures'], {})
        self.assertEqual(proposal['graph']['milestones'], [{'title': 'Infra', 'number': 7}])
        self.assertEqual(proposal['graph']['exclude'], [])
        items = {i['number']: i for i in proposal['graph']['items']}
        self.assertEqual(sorted(items), [9001, 9002, 9003, 9004, 9010])
        self.assertEqual(items[9002], dict(number=9002, kind='issue', title='Synthetic ticket',
            labels=['bug', 'ready-for-agent'], milestone='Infra', parent=9001, blockers=[9003, 9004], state='open'))
        self.assertEqual(items[9004]['state'], 'merged')
        handoff = proposal['pulls']['9010']
        self.assertEqual({k: handoff[k] for k in ['source_base', 'observed_base', 'source_head']},
                         dict(source_base=self.source_base, observed_base=self.source_base,
                              source_head=self.source_head))
        self.assertEqual(handoff['destination'], str(self.public))
        binding = Path(handoff['patch_dir']) / 'binding.json'
        self.assertTrue(Path(handoff['patch_dir']).is_relative_to(self.out))
        self.assertEqual(hashlib.sha256(binding.read_bytes()).hexdigest(), handoff['binding_sha256'])
        self.assertEqual(json.loads(binding.read_text())['destination_base'], self.base)
        result = json.loads(self.move_dry(plan).stdout)
        self.assertEqual(result['status'], 'dry_run')
        self.assertEqual(result['issues'], 4)
        self.assertFalse((self.root / 'state').exists())
        self.assertEqual(self.world.read_bytes(), before)
        self.assertEqual(self.git(self.public, 'rev-parse', 'refs/heads/main').strip(), self.base)
        # An existing output folder is never reused or overwritten.
        saved = plan.read_bytes()
        self.assertIn('output already exists', self.build(ok=False).stderr)
        self.assertEqual(plan.read_bytes(), saved)

    def test_stays_private_pull_is_excluded_and_turning_mixed_is_drift(self):
        self.world_edit(lambda w: (w['move']['graph']['items'].append(dict(number=9011, kind='pull_request',
            title='Synthetic private PR', labels=[], milestone=None, parent=None, blockers=[], state='open')),
            w.update(pull_files={'9011': ['private/synthetic.md']})))
        self.collect()
        summary = json.loads(self.build().stdout)
        self.assertEqual(summary['private_pulls'], [9011])
        proposal = json.loads((self.out / 'proposal.json').read_text())
        self.assertIn(9011, proposal['graph']['exclude'])
        self.assertEqual(sorted(proposal['pulls']), ['9010'])
        self.assertNotIn('9011', proposal['bodies'])
        self.move_dry(self.out / 'proposal.json')
        self.world_edit(lambda w: w['pull_files'].update({'9011': ['private/synthetic.md', 'crates/core/src/lib.rs']}))
        out = self.root / 'turned-mixed'
        result = self.build(ok=False, out=out)
        self.assertIn('drift', result.stderr)
        self.assertIn('9011', result.stderr)
        self.assertFalse(out.exists())

    def test_listed_stays_private_pull_is_carried_to_move(self):
        entry = {'number': 9011, 'reason': 'Synthetic index line only.', 'ruling': 'https://github.com/jparker2006/ClosedWiz/issues/325#issuecomment-9000000325'}
        listing = self.root / 'stays-private.json'
        listing.write_text(json.dumps([entry]))
        self.world_edit(lambda w: (w['move']['graph']['items'].append(dict(number=9011, kind='pull_request',
            title='Synthetic grill PR', labels=[], milestone=None, parent=None, blockers=[], state='open')),
            w.update(pull_files={'9011': ['docs/grills/synthetic.md', 'docs/grills/README.md']})))
        self.collect('--stays-private-prs', str(listing))
        summary = json.loads(self.build().stdout)
        self.assertEqual(summary['private_pulls'], [9011])
        proposal = json.loads((self.out / 'proposal.json').read_text())
        listing_digest = hashlib.sha256(b'docs/grills/README.md\ndocs/grills/synthetic.md\n').hexdigest()
        self.assertEqual(proposal['stays_private_prs'], [dict(entry, changed_files=2, files_sha256=listing_digest,
                                                              head_sha='b' * 40)])
        self.assertIn(9011, proposal['graph']['exclude'])
        self.move_dry(self.out / 'proposal.json')
        # Changed since review (a public file added, or new commits at the same paths): apply refuses before any write.
        reviewed = json.loads(self.world.read_text())
        for name, change in [('public file', lambda w: w['pull_files']['9011'].append('crates/core/src/lib.rs')),
                             ('new head', lambda w: w.update(pull_heads={'9011': 'c' * 40}))]:
            with self.subTest(name):
                self.world.write_text(json.dumps(reviewed))
                self.world_edit(change)
                before = self.world.read_bytes()
                result = self.move_apply(self.out / 'proposal.json', ok=False)
                self.assertIn('listed stays-private PR changed since the proposal', result.stderr)
                self.assertEqual(self.world.read_bytes(), before)
                self.assertEqual(json.loads(self.world.read_text())['writes'], 0)
                self.assertFalse((self.root / 'map.tsv').exists())
        self.world.write_text(json.dumps(reviewed))
        self.move_apply(self.out / 'proposal.json')
        self.assertNotIn('9011', (self.root / 'map.tsv').read_text())

    def test_output_inside_any_git_work_tree_refuses_and_writes_nothing(self):
        self.collect()
        other = self.repo('unrelated-public-checkout')
        worktree = self.root / 'linked-worktree'
        self.git(other, 'worktree', 'add', '-q', str(worktree))
        for out in [other / 'move-proposal', other / 'deep/new/move-proposal', worktree / 'move-proposal']:
            with self.subTest(str(out.relative_to(self.root))):
                self.assertIn('inside a repository', self.build(ok=False, out=out).stderr)
                self.assertFalse(out.exists())
                self.assertFalse((other / 'deep').exists())
        self.assertEqual(self.git(other, 'status', '--porcelain'), '')

    def test_drift_from_the_dry_run_refuses_and_names_it(self):
        self.collect()
        cases = {
            'body': lambda w: w['move']['bodies'].update({'9002': w['move']['bodies']['9002'] + ' edited'}),
            'labels': lambda w: w['move']['graph']['items'][2]['labels'].append('triage'),
            'pr-head': lambda w: w['move']['pulls']['9010'].update(source_head='c' * 40),
            'new-open-issue': lambda w: w['move']['graph']['items'].append(dict(
                number=9020, kind='issue', title='Synthetic newcomer', labels=[], milestone=None,
                parent=None, blockers=[], state='open')),
        }
        initial = self.world.read_bytes()
        for name, change in cases.items():
            with self.subTest(drift=name):
                self.world.write_bytes(initial)
                self.world_edit(change)
                if name == 'new-open-issue':
                    self.world_edit(lambda w: w['move']['bodies'].update({'9020': 'Synthetic.'}))
                out = self.root / ('drift-' + name)
                result = self.build(ok=False, out=out)
                self.assertFalse(out.exists())
                self.assertIn('drift', result.stderr)
                expected = {'body': '9002', 'labels': '9003', 'pr-head': '9010', 'new-open-issue': '9020'}[name]
                self.assertIn(expected, result.stderr)

    def test_tampered_or_unbindable_dry_runs_refuse(self):
        self.collect()
        saved = {p.name: p.read_bytes() for p in self.dry.iterdir()}
        report = json.loads(saved['report.json'])
        report['source_sha256'] = '0' * 64
        (self.dry / 'report.json').write_text(json.dumps(report))
        self.assertIn('dry-run', self.build(ok=False).stderr)
        self.assertFalse(self.out.exists())
        (self.dry / 'report.json').write_bytes(saved['report.json'])
        # A destination clone not at the imported main, or the output inside it.
        self.assertIn('main is not the imported main', self.build('--destination-main', 'b' * 40, ok=False).stderr)
        self.assertFalse(self.out.exists())
        inside = self.public / 'proposal'
        self.assertIn('public tree', self.build(ok=False, out=inside).stderr)
        self.assertFalse(inside.exists())

    def test_refused_patch_names_the_pull_request_and_saves_nothing(self):
        # A PR whose change carries no public path: O14 patch refuses.
        (self.source / 'private/record').write_text('another synthetic private record\n')
        self.git(self.source, 'commit', '-qam', 'synthetic private-only change')
        head = self.git(self.source, 'rev-parse', 'HEAD').strip()
        self.world_edit(lambda w: w['move']['pulls']['9010'].update(source_base=self.source_head,
                                                                   observed_base=self.source_head, source_head=head))
        self.collect()
        result = self.build(ok=False)
        self.assertIn('PR #9010', result.stderr)
        self.assertFalse(self.out.exists())

    def test_stale_approvals_and_held_prerequisites_are_carried_and_accepted(self):
        # A stale original approval (J51) is carried as the original binding and
        # reported; move.py's dry mode accepts it, and apply's own read refuses it.
        self.world_edit(lambda w: w.update(collect_fault='stale-approval'))
        self.collect()
        summary = json.loads(self.build().stdout)
        self.assertEqual(summary['stale_approvals'], [9001])
        proposal = json.loads((self.out / 'proposal.json').read_text())
        self.assertEqual(proposal['approvals'], {'9001': dict(comment=9000000001, fingerprint='0' * 64)})
        self.move_dry(self.out / 'proposal.json')
        # A HELD private prerequisite (open, staying on ClosedWiz) has no destination: it is
        # carried with the collector's excluded-target binding, and move.py's dry mode accepts it.
        self.world_edit(lambda w: (w.pop('collect_fault'), w['move']['graph']['items'].extend([
            dict(number=1257, kind='issue', title='Synthetic migration spec', labels=[], milestone=None,
                 parent=None, blockers=[], state='open'),
            dict(number=1283, kind='issue', title='Synthetic remaining work', labels=[], milestone=None,
                 parent=1257, blockers=[], state='open')]),
            w['move']['bodies'].update({'1257': 'Synthetic migration.', '1283': 'Synthetic remaining work.'}),
            w['move']['graph']['items'][1]['blockers'].append(1283)))
        self.dry, out = self.root / 'held-dry-run', self.root / 'held-proposal'
        self.collect()
        summary = json.loads(self.build(out=out).stdout)
        self.assertEqual(summary['held_prerequisites'], [1283])
        proposal = json.loads((out / 'proposal.json').read_text())
        self.assertEqual(proposal['graph']['exclude'], [1257, 1283])
        self.assertEqual(sorted(proposal['excluded_targets']), ['1257', '1283'])
        items = {i['number']: i for i in proposal['graph']['items']}
        self.assertEqual(items[9002]['blockers'], [1283, 9003, 9004])  # no blocker link dropped
        self.assertEqual(items[1283]['state'], 'open')
        self.assertNotIn('1283', proposal['bodies'])
        self.move_dry(out / 'proposal.json')

if __name__ == '__main__':
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument('--checker', type=Path, default=CHECKER)
    p.add_argument('--importer', type=Path, default=IMPORTER)
    options, rest = p.parse_known_args()
    CHECKER, IMPORTER = options.checker.resolve(), options.importer.resolve()
    unittest.main(argv=[sys.argv[0], *rest])
