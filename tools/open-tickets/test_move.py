#!/usr/bin/env python3
"""P8/P11 issue lifecycle: public CLI, mutable synthetic gh, actual O3 guard."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
from test_graph import snapshot  # noqa: E402

CHECKER = HERE.parent / 'privacy-check' / 'check.py'


def fixture():
    return {'graph': snapshot(), 'bodies': {'9001': 'Synthetic spec body.',
            '9002': 'Ja' 'ke: "synthetic approval"\nBuilder thr_synmoving1.',
            '9003': 'Synthetic dependency body.'}, 'target': 'synthetic-org/openwiz', 'date': '2030-01-02',
            'merges': {'9004': [{'pull_request': 9900, 'merge': 'a' * 40}]}}


class MoveContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.plan = self.root / 'plan.json'
        self.plan.write_text(json.dumps(fixture()))
        self.world = self.root / 'world.json'
        self.world.write_text(json.dumps({'move': fixture(), 'created': {}, 'comments': {}, 'writes': 0}))
        self.map = self.root / 'map.tsv'
        self.state = self.root / 'state'
        self.literals = self.root / 'literals'
        self.literals.write_text('synthetic-unused-literal\n')
        self.sleeps = self.root / 'sleeps'
        self.env = dict(os.environ, OPEN_TICKETS_WORLD=str(self.world),
                        OPEN_TICKETS_LOG=str(self.root / 'gh.jsonl'), OPEN_TICKETS_SLEEPS=str(self.sleeps))
        # Pauses are recorded, not slept: the same move.py, with time.sleep logged.
        self.mover = self.root / 'mover.py'
        self.mover.write_text('import os, runpy, time\n'
            'def logged(seconds):\n'
            '    with open(os.environ["OPEN_TICKETS_SLEEPS"], "a") as log:\n'
            '        log.write(repr(seconds) + "\\n")\n'
            f'time.sleep = logged\nrunpy.run_path({str(HERE / "move.py")!r}, run_name="__main__")\n')

    def slept(self):
        return [float(v) for v in self.sleeps.read_text().split()] if self.sleeps.exists() else []

    def gh_log(self):
        return [json.loads(line) for line in (self.root / 'gh.jsonl').read_text().splitlines()]

    def direct_reads(self):
        prefix = 'repos/synthetic-org/openwiz/issues/'
        return [int(a[-1][len(prefix):]) for a in self.gh_log()
                if a[:3] == ['api', '--method', 'GET'] and len(a) == 4 and a[-1].startswith(prefix)]

    def run_move(self, *args, ok=True, program=None):
        result = subprocess.run([sys.executable, '-I', str(program or self.mover), '--plan', str(self.plan),
                                 '--state-dir', str(self.state), '--map-out', str(self.map),
                                 '--checker', str(CHECKER), '--literals', str(self.literals),
                                 '--gh', str(HERE / 'fake-gh'), *args],
                                capture_output=True, text=True, env=self.env)
        self.assertEqual(result.returncode == 0, ok, result.stderr or result.stdout)
        return result

    def test_closure_records_are_rechecked_before_apply_and_verify(self):
        # A local disposition must not bypass a changed native state/record at apply.
        proposal = fixture()
        proposal['graph']['items'][-1]['state'] = 'completed'
        proposal['merges'] = {}
        extra = dict(proposal['graph']['items'][-1], number=9005, state='not_planned')
        proposal['graph']['items'].append(extra)
        proposal['graph']['items'][1]['blockers'].append(9005)
        proposal['closures'] = {}
        comments = {}
        for n, body, state, replacement in [(9004, 'Completed synthetic work.', 'completed', None),
                                            (9005, 'Superseded by #9010.', 'not_planned', 9010)]:
            c = 9000000000 + n
            comments[str(n)] = [dict(id=c, body=body)]
            proposal['closures'][str(n)] = dict(state=state, comment=c,
                sha256=hashlib.sha256(body.encode()).hexdigest(), superseded_by=replacement)
        self.plan.write_text(json.dumps(proposal))
        initial = dict(move=proposal, created={}, comments=comments, writes=0,
                       state_reasons={'9004': 'COMPLETED', '9005': 'NOT_PLANNED'})
        bad = json.loads(json.dumps(initial))
        bad['comments']['9004'][0]['body'] += ' changed'
        self.world.write_text(json.dumps(bad))
        before = self.world.read_bytes()
        self.run_move('--apply', ok=False)
        self.assertEqual(self.world.read_bytes(), before)
        self.world.write_text(json.dumps(initial))
        self.run_move('--apply')
        world = json.loads(self.world.read_text())
        self.assertEqual(world['created']['4002']['blockedBy']['nodes'], [{'number': 4003}])
        self.assertIn('#issuecomment-9000009004', world['created']['4002']['body'])
        self.assertNotIn('/issues/9005', world['created']['4002']['body'])
        self.run_move('--verify')
        world['state_reasons']['9005'] = 'COMPLETED'
        self.world.write_text(json.dumps(world))
        before = self.world.read_bytes()
        self.run_move('--verify', ok=False)
        self.assertEqual(self.world.read_bytes(), before)

    def test_held_private_prerequisite_is_a_private_link_never_a_dropped_edge(self):
        # An open blocker that stays on ClosedWiz (excluded and bound) has no
        # destination; it was refused even in dry mode, blocking the whole move.
        proposal = fixture()
        proposal['graph']['items'] += [
            dict(number=1257, kind='issue', title='Synthetic migration spec', labels=[], milestone=None,
                 parent=None, blockers=[], state='open'),
            dict(number=1283, kind='issue', title='Synthetic remaining work', labels=[], milestone=None,
                 parent=1257, blockers=[], state='open')]
        proposal['graph']['exclude'] = [1257, 1283]
        proposal['graph']['items'][1]['blockers'].append(1283)
        binding = {'1283': dict(url='https://github.com/jparker2006/ClosedWiz/issues/1283', parent=1257,
                                source_sha256='0' * 64)}
        for bound, ok in [(binding, True), ({}, False)]:
            with self.subTest(bound=bool(bound)):
                proposal['excluded_targets'] = bound
                self.plan.write_text(json.dumps(proposal))
                result = self.run_move(ok=ok)
                if ok:
                    self.assertEqual(json.loads(result.stdout)['issues'], 3)
                else:
                    self.assertIn('held prerequisite #1283 has no excluded-target binding', result.stderr)
                self.assertFalse(self.state.exists())

    def test_stays_private_pull_is_in_scope_only_while_all_its_files_are_private(self):
        proposal = fixture()
        proposal['graph']['items'].append(dict(number=9010, kind='pull_request', title='Synthetic private PR',
            labels=[], milestone=None, parent=None, blockers=[], state='open'))
        proposal['graph']['exclude'] = [9010]
        self.plan.write_text(json.dumps(proposal))
        world = dict(move=proposal, created={}, comments={}, writes=0)
        # Turned mixed since the proposal: complete current scope differs, before any effect.
        self.world.write_text(json.dumps(dict(world, pull_files={'9010': ['private/a.md', 'crates/core/src/lib.rs']})))
        before = self.world.read_bytes()
        self.assertIn('complete current move scope', self.run_move('--apply', ok=False).stderr)
        self.assertEqual(self.world.read_bytes(), before)
        self.assertFalse(self.map.exists())
        self.world.write_text(json.dumps(dict(world, pull_files={'9010': ['private/a.md', 'docs/grills/b.md']})))
        self.run_move('--apply')
        self.assertNotIn('9010', self.map.read_text())
        self.assertEqual(sorted(map(int, json.loads(self.world.read_text())['created'])), [4001, 4002, 4003])
        self.run_move('--verify')

    def test_listed_stays_private_pull_is_in_scope_only_while_listed(self):
        proposal = fixture()
        proposal['graph']['items'].append(dict(number=9010, kind='pull_request', title='Synthetic grill PR',
            labels=[], milestone=None, parent=None, blockers=[], state='open'))
        proposal['graph']['exclude'] = [9010]
        world = dict(move=proposal, created={}, comments={}, writes=0,
                     pull_files={'9010': ['docs/grills/synthetic.md', 'docs/grills/README.md']})
        self.world.write_text(json.dumps(world))
        before = self.world.read_bytes()
        self.plan.write_text(json.dumps(proposal))  # unlisted, with a public file: it moves, so scope differs
        self.assertIn('complete current move scope', self.run_move('--apply', ok=False).stderr)
        self.assertEqual(self.world.read_bytes(), before)
        entry = {'number': 9010, 'reason': 'Synthetic index line only.', 'ruling': 'https://github.com/jparker2006/ClosedWiz/issues/325#issuecomment-9000000325'}
        proposal['stays_private_prs'] = [entry]  # the reviewed state unbound: refused as malformed
        self.plan.write_text(json.dumps(proposal))
        self.assertIn('stays-private list entry', self.run_move('--apply', ok=False).stderr)
        self.assertEqual(self.world.read_bytes(), before)
        binding = dict(entry, changed_files=2, head_sha='b' * 40, files_sha256=hashlib.sha256(
            b'docs/grills/README.md\ndocs/grills/synthetic.md\n').hexdigest())
        for name, change in [('public file', dict(pull_files={'9010': ['docs/grills/synthetic.md', 'crates/core/src/lib.rs']})),
                             ('new head', dict(pull_heads={'9010': 'c' * 40}))]:
            with self.subTest(name):
                proposal['stays_private_prs'] = [binding]
                self.plan.write_text(json.dumps(proposal))
                self.world.write_text(json.dumps(dict(world, **change)))
                changed = self.world.read_bytes()
                self.assertIn('listed stays-private PR changed', self.run_move('--apply', ok=False).stderr)
                self.assertEqual(self.world.read_bytes(), changed)
                self.assertFalse(self.map.exists())
        self.world.write_text(json.dumps(world))
        self.run_move('--apply')
        self.assertNotIn('9010', self.map.read_text())
        self.run_move('--verify')

    def assert_complete(self):
        world = json.loads(self.world.read_text())
        self.assertEqual(world['move'], fixture())  # source title/body/graph never changed
        self.assertEqual(sorted(map(int, world['created'])), [4001, 4002, 4003])
        self.assertEqual(self.map.read_text(), 'kind\tclosedwiz\topenwiz\nissue\t9001\t4001\n'
                         'issue\t9002\t4002\nissue\t9003\t4003\n')
        self.assertEqual(world['created']['4002']['parent'], {'number': 4001})
        self.assertEqual(world['created']['4002']['blockedBy']['nodes'], [{'number': 4003}])
        self.assertEqual(world['created']['4002']['milestone'], {'number': 7, 'title': 'Infra'})
        self.assertEqual(world['created']['4002']['labels'], [{'name': 'bug'}])
        self.assertEqual([len(world['comments'].get(str(n), [])) for n in [9001, 9002, 9003]], [1, 2, 1])
        for old, new in [(9001, 4001), (9002, 4002), (9003, 4003)]:
            self.assertTrue(world['created'][str(new)]['body'].endswith(
                f'was [ClosedWiz #{old}](https://github.com/jparker2006/ClosedWiz/issues/{old})'))
            self.assertEqual(sum(c['body'] == f'moved to [OpenWiz #{new}]'
                f'(https://github.com/openwizdev/openwiz/issues/{new})'
                for c in world['comments'][str(old)]), 1)
        self.assertNotIn('thr_', world['created']['4002']['body'])
        self.assertNotIn('synthetic approval', world['created']['4002']['body'])
        self.assertIn('1. "synthetic approval"', world['comments']['9002'][0]['body'])
        self.run_move('--verify')

    def test_p8_p11_graph_moves_crosslinks_mapping_and_source_preservation(self):
        self.run_move('--apply')
        self.assert_complete()

    def test_p8_claimed_merged_blocker_requires_current_verified_merge(self):
        world = json.loads(self.world.read_text())
        world['unmerged_blocker'] = True
        self.world.write_text(json.dumps(world))
        before = self.world.read_bytes()
        self.run_move('--apply', ok=False)
        self.assertEqual(self.world.read_bytes(), before)

    def test_p8_native_graph_readback_keeps_extra_gh_metadata(self):
        world = json.loads(self.world.read_text())
        world['native_graph_shape'] = True
        self.world.write_text(json.dumps(world))
        self.run_move('--apply')
        self.assert_complete()

    def test_p11_lost_response_after_each_effect_resumes_without_duplicates(self):
        original = self.world.read_text()
        # Three creates/bodies, two parents, one blocker, one private record, three moved comments.
        for stop in range(1, 14):
            with self.subTest(after_effect=stop):
                world = json.loads(original)
                world['stop_after_write'] = stop
                self.world.write_text(json.dumps(world))
                self.state = self.root / ('state-' + str(stop))
                self.map = self.root / ('map-' + str(stop) + '.tsv')
                self.run_move('--apply', ok=False)
                self.run_move('--apply')
                self.assert_complete()

    def test_c1_listed_late_creation_is_adopted_by_direct_read_without_duplicate(self):
        # GitHub's list omits a just-created item while GET issues/<n> returns it.
        original = self.world.read_text()
        for stop in [None, 1]:
            with self.subTest(lost_response_after_effect=stop):
                world = dict(json.loads(original), list_lag=-1)
                if stop:
                    world['stop_after_write'] = stop
                self.world.write_text(json.dumps(world))
                self.state = self.root / ('state-late-' + str(stop))
                self.map = self.root / ('map-late-' + str(stop) + '.tsv')
                if stop:
                    self.assertIn('effect/read outcome unconfirmed', self.run_move('--apply', ok=False).stderr)
                self.run_move('--apply')
                self.assert_complete()
                self.assertTrue(set(self.direct_reads()) <= {4001, 4002, 4003, 4004})

    def test_c1_confirm_read_retries_then_adopts_listed_late_creation(self):
        world = dict(json.loads(self.world.read_text()), list_lag=3, direct_missing=True)
        self.world.write_text(json.dumps(world))
        self.run_move('--apply')
        self.assert_complete()
        # Each create: one pacing pause before the POST, then three 5 s retries.
        self.assertEqual(self.slept()[:4], [1.0, 5.0, 5.0, 5.0])
        self.assertEqual(self.slept().count(1.0), 3)
        self.assertEqual(self.slept().count(5.0), 9)

    def test_c1_unconfirmed_after_last_retry_still_refuses_then_resumes_once(self):
        world = dict(json.loads(self.world.read_text()), list_lag=-1, direct_missing=True)
        self.world.write_text(json.dumps(world))
        self.assertIn('create outcome unconfirmed', self.run_move('--apply', ok=False).stderr)
        self.assertEqual(self.slept(), [1.0] + [5.0] * 8)
        world = json.loads(self.world.read_text())
        self.assertEqual(list(world['created']), ['4001'])
        before = self.world.read_bytes()
        self.assertIn('create outcome unknown', self.run_move('--apply', ok=False).stderr)
        self.assertEqual(self.world.read_bytes(), before)
        for key in ['listed_from', 'list_lag', 'direct_missing']:
            world.pop(key)
        self.world.write_text(json.dumps(world))
        self.run_move('--apply')
        self.assert_complete()

    def test_c1_direct_reads_stop_at_five_and_at_the_first_missing_number(self):
        world = json.loads(self.world.read_text())
        for n in range(4001, 4007):
            world['created'][str(n)] = {'number': n, 'title': 'Other synthetic work', 'body': 'Other.',
                'labels': [], 'milestone': None, 'parent': None, 'blockedBy': {'nodes': [], 'totalCount': 0}}
        world['listed_from'] = {str(n): -1 for n in range(4002, 4007)}
        world['list_lag'] = -1
        self.world.write_text(json.dumps(world))
        # 4001 is listed; 4002..4006 are listed late; the new 4007 lies beyond five direct reads.
        self.assertIn('create outcome unconfirmed', self.run_move('--apply', ok=False).stderr)
        self.assertEqual(sorted(set(self.direct_reads())), [4002, 4003, 4004, 4005, 4006])
        self.assertEqual(sorted(map(int, json.loads(self.world.read_text())['created'])), list(range(4001, 4008)))
        # With nothing listed late, each find reads only the first number past the list.
        (self.root / 'gh.jsonl').write_text('')
        self.state, self.map = self.root / 'state-plain', self.root / 'map-plain.tsv'
        self.world.write_text(json.dumps({'move': fixture(), 'created': {}, 'comments': {}, 'writes': 0}))
        self.run_move('--apply')
        self.assertEqual(sorted(set(self.direct_reads())), [4001, 4002, 4003, 4004])

    def test_c1_listed_and_direct_matches_together_are_ambiguous(self):
        world = json.loads(self.world.read_text())
        for n in [4001, 4002]:
            world['created'][str(n)] = {'number': n, 'title': 'Other public work',
                'body': 'Other.\n\nwas [ClosedWiz #9001](https://github.com/jparker2006/ClosedWiz/issues/9001)',
                'labels': [], 'milestone': None, 'parent': None, 'blockedBy': {'nodes': [], 'totalCount': 0}}
        world['listed_from'] = {'4002': -1}
        self.world.write_text(json.dumps(world))
        before = self.world.read_bytes()
        self.assertIn('ambiguous destination', self.run_move('--apply', ok=False).stderr)
        self.assertEqual(self.world.read_bytes(), before)

    def test_p11_uncertain_comment_is_not_retried_when_readback_is_empty(self):
        world = json.loads(self.world.read_text())
        world['stop_after_write'] = 5
        self.world.write_text(json.dumps(world))
        self.run_move('--apply', ok=False)
        world = json.loads(self.world.read_text())
        world['hide_comments_for'] = '9001'
        self.world.write_text(json.dumps(world))
        before = self.world.read_bytes()
        self.run_move('--apply', ok=False)
        self.assertEqual(self.world.read_bytes(), before)
        self.assertEqual(len(world['comments']['9001']), 1)

    def test_p11_existing_destination_without_journal_is_not_adopted(self):
        world = json.loads(self.world.read_text())
        world['created']['4001'] = {'number': 4001, 'title': 'Other public work',
            'body': 'Other public text.\n\nwas [ClosedWiz #9001]'
                    '(https://github.com/jparker2006/ClosedWiz/issues/9001)',
            'labels': [], 'milestone': None, 'parent': None,
            'blockedBy': {'nodes': [], 'totalCount': 0}}
        self.world.write_text(json.dumps(world))
        before = self.world.read_bytes()
        self.run_move('--apply', ok=False)
        self.assertEqual(self.world.read_bytes(), before)

    def test_p11_unowned_existing_mapping_is_not_overwritten(self):
        self.map.write_text('user-owned synthetic map\n')
        before = self.world.read_bytes()
        self.run_move('--apply', ok=False)
        self.assertEqual(self.world.read_bytes(), before)
        self.assertEqual(self.map.read_text(), 'user-owned synthetic map\n')

    def test_p11_missing_map_and_each_missing_link_fail_read_only_check(self):
        self.run_move('--apply')
        good_world, good_map = self.world.read_text(), self.map.read_text()
        self.map.write_text(good_map.replace('issue\t9002\t4002\n', ''))
        self.run_move('--verify', ok=False)
        self.map.write_text(good_map)
        for missing in ['public', 'private']:
            world = json.loads(good_world)
            if missing == 'public':
                world['created']['4002']['body'] = 'Missing origin link'
            else:
                world['comments']['9002'].pop()
            self.world.write_text(json.dumps(world))
            before = self.world.read_bytes()
            self.run_move('--verify', ok=False)
            self.assertEqual(self.world.read_bytes(), before)

    def test_b2_completed_graph_preserves_later_public_removals(self):
        self.run_move('--apply')
        saved = self.world.read_bytes()
        for field, value in [('parent', None), ('blockedBy', {'nodes': [], 'totalCount': 0})]:
            with self.subTest(field=field):
                world = json.loads(saved)
                world['created']['4002'][field] = value
                self.world.write_text(json.dumps(world))
                before = self.world.read_bytes()
                self.run_move('--apply', ok=False)
                self.assertEqual(self.world.read_bytes(), before)

    def test_b2_confirmed_parent_is_not_restored_after_other_effect_is_lost(self):
        world = json.loads(self.world.read_text())
        world['stop_after_write'] = 9
        self.world.write_text(json.dumps(world))
        self.run_move('--apply', ok=False)
        world = json.loads(self.world.read_text())
        self.assertEqual(world['writes'], 9)
        self.assertEqual(world['created']['4002']['parent'], {'number': 4001})
        world['created']['4002']['parent'] = None
        self.world.write_text(json.dumps(world))
        before = self.world.read_bytes()
        self.run_move('--apply', ok=False)
        self.assertEqual(self.world.read_bytes(), before)

    def test_r1_uncertain_blocker_removed_after_lost_response_is_not_replayed(self):
        world = json.loads(self.world.read_text())
        world['stop_after_write'] = 9
        self.world.write_text(json.dumps(world))
        self.run_move('--apply', ok=False)
        world = json.loads(self.world.read_text())
        self.assertEqual(world['created']['4002']['blockedBy']['nodes'], [{'number': 4003}])
        world['created']['4002']['blockedBy'] = {'nodes': [], 'totalCount': 0}
        self.world.write_text(json.dumps(world))
        before, journal = self.world.read_bytes(), (self.state / 'state.json').read_bytes()
        self.run_move('--apply', ok=False)
        self.assertEqual(self.world.read_bytes(), before)
        self.assertEqual((self.state / 'state.json').read_bytes(), journal)

    def test_r2_parent_confirmation_and_intent_clear_are_one_durable_save(self):
        wrapper = self.root / 'crash-after-parent.py'
        wrapper.write_text('import json, os, runpy, sys\nfrom pathlib import Path\n' +
            f'module = runpy.run_path({str(HERE / "move.py")!r}, run_name="mover_crash_fixture")\n' +
            'Mover = module["Mover"]\noriginal_save = Mover.save\n' +
            'def crash_after_parent(self):\n    original_save(self)\n' +
            '    world = json.loads(Path(os.environ["OPEN_TICKETS_WORLD"]).read_text())\n' +
            '    if world["writes"] == 8:\n        os._exit(75)\n' +
            'Mover.save = crash_after_parent\nsys.exit(module["main"]())\n')
        result = self.run_move('--apply', ok=False, program=wrapper)
        self.assertEqual(result.returncode, 75, result.stderr)
        world = json.loads(self.world.read_text())
        self.assertEqual(world['writes'], 8)
        self.assertEqual(world['created']['4002']['parent'], {'number': 4001})
        world['created']['4002']['parent'] = None
        self.world.write_text(json.dumps(world))
        before = self.world.read_bytes()
        self.run_move('--apply', ok=False)
        self.assertEqual(self.world.read_bytes(), before)

    def test_r4_unlabelled_parent_with_closed_children_requires_current_approval(self):
        source = fixture()
        source['graph']['items'][0]['labels'].remove('spec')
        source['graph']['items'][1]['state'] = 'closed'
        source['graph']['items'][2]['state'] = 'closed'
        proposal = fixture()
        proposal['graph']['items'] = [source['graph']['items'][0]]
        proposal['merges'] = {}
        proposal['bodies'] = {'9001': source['bodies']['9001']}
        self.plan.write_text(json.dumps(proposal))
        stale = '**Plan graph approved by Synthetic, 2030-01-02:** approved\nFingerprint: `' + '0' * 64 + '`'
        self.world.write_text(json.dumps(dict(move=source, created={},
            comments={'9001': [{'id': 9000000001, 'body': stale}]}, writes=0)))
        before = self.world.read_bytes()
        result = self.run_move('--apply', ok=False)
        self.assertEqual(result.stderr,
                         'refused: source: approved graph #9001 fingerprint is stale or unreadable\n')
        self.assertEqual(self.world.read_bytes(), before)

    def test_b3_conflicting_source_comments_refuse_before_any_effect(self):
        for body in ['moved to [OpenWiz #4999](https://github.com/openwizdev/openwiz/issues/4999)',
                     '**Private record for OpenWiz #4999, 2030-01-02:**\n\n1. "synthetic conflict"\n']:
            with self.subTest(family=body.split()[0]):
                self.state = self.root / ('comments-' + str(len(body)))
                self.map = self.root / ('comment-map-' + str(len(body)))
                world = dict(move=fixture(), created={}, comments={'9002': [{'id': 9000000001, 'body': body}]}, writes=0)
                self.world.write_text(json.dumps(world))
                before = self.world.read_bytes()
                self.run_move('--apply', ok=False)
                self.assertEqual(self.world.read_bytes(), before)

    def test_b4_scope_requires_every_current_open_item_and_only_migration_exclusions(self):
        for excluded in [False, True]:
            with self.subTest(arbitrary_exclusion=excluded):
                self.state = self.root / ('scope-' + str(excluded))
                self.map = self.root / ('scope-map-' + str(excluded))
                proposal = fixture()
                world = dict(move=fixture(), created={}, comments={}, writes=0)
                extra = dict(number=9008, kind='issue', title='Synthetic independent ticket', labels=[],
                             milestone='Infra', parent=None, blockers=[], state='open')
                world['move']['graph']['items'].append(extra)
                world['move']['bodies']['9008'] = 'Synthetic independent body.'
                if excluded:
                    proposal['graph']['items'].append(extra)
                    proposal['graph']['exclude'].append(9008)
                self.plan.write_text(json.dumps(proposal))
                self.world.write_text(json.dumps(world))
                before = self.world.read_bytes()
                self.run_move('--apply', ok=False)
                self.assertEqual(self.world.read_bytes(), before)

        self.state, self.map = self.root / 'scope-verified', self.root / 'scope-map-verified'
        self.plan.write_text(json.dumps(fixture()))
        self.world.write_text(json.dumps(dict(move=fixture(), created={}, comments={}, writes=0)))
        self.run_move('--apply')
        world = json.loads(self.world.read_text())
        world['move']['graph']['items'].append(extra)
        world['move']['bodies']['9008'] = 'Synthetic independent body.'
        self.world.write_text(json.dumps(world))
        before = self.world.read_bytes()
        self.run_move('--verify', ok=False)
        self.assertEqual(self.world.read_bytes(), before)

    def test_b8_reapproval_representation_is_checked_before_effects(self):
        proposal = fixture()
        proposal['graph']['items'][1]['title'] = 'Synthetic | ticket'
        fingerprint = '225b9a8fd57792f72a52bd96367ab6f5895daa33fde9512859e18ccd55d6b2ce'
        proposal['approvals'] = {'9001': {'comment': 9000000001, 'fingerprint': fingerprint}}
        self.plan.write_text(json.dumps(proposal))
        comment = '**Plan graph approved by Synthetic, 2030-01-02:** approved\nFingerprint: `' + fingerprint + '`'
        world = dict(move=proposal, created={}, comments={'9001': [{'id': 9000000001, 'body': comment}]}, writes=0)
        self.world.write_text(json.dumps(world))
        before = self.world.read_bytes()
        self.run_move('--apply', ok=False)
        self.assertEqual(self.world.read_bytes(), before)

    def test_a1_resume_preserves_subsequent_public_body(self):
        self.run_move('--apply')
        world = json.loads(self.world.read_text())
        world['created']['4002']['body'] = 'Synthetic human addition.\n' + world['created']['4002']['body']
        self.world.write_text(json.dumps(world))
        before = self.world.read_bytes()
        self.run_move('--apply', ok=False)
        self.assertEqual(self.world.read_bytes(), before)

    def test_a2_uncertain_creation_requires_own_identity_and_payload(self):
        for field, value in [('title', 'Other synthetic creation'),
                             ('body', 'Other synthetic operation.\n\nwas [ClosedWiz #9001]'
                                      '(https://github.com/jparker2006/ClosedWiz/issues/9001)'),
                             ('labels', [{'name': 'other'}]),
                             ('milestone', None)]:
            with self.subTest(field=field):
                world = {'move': fixture(), 'created': {}, 'comments': {}, 'writes': 0, 'stop_after_write': 1}
                self.world.write_text(json.dumps(world))
                self.state = self.root / ('state-identity-' + field)
                self.map = self.root / ('map-identity-' + field)
                self.run_move('--apply', ok=False)
                world = json.loads(self.world.read_text())
                world['created']['4001'][field] = value
                self.world.write_text(json.dumps(world))
                before = self.world.read_bytes()
                self.run_move('--apply', ok=False)
                self.assertEqual(self.world.read_bytes(), before)

    def test_a3_map_cannot_alias_journal(self):
        self.state.mkdir()
        self.map = self.state / 'state.json'
        before = self.world.read_bytes()
        self.run_move('--apply', ok=False)
        self.assertEqual(self.world.read_bytes(), before)
        self.assertFalse(self.map.exists())

    def test_a4_comma_label_is_one_opaque_label(self):
        proposal = fixture()
        proposal['graph']['items'][0]['labels'] = ['bug,ready-for-agent']
        self.plan.write_text(json.dumps(proposal))
        self.world.write_text(json.dumps({'move': proposal, 'created': {}, 'comments': {}, 'writes': 0}))
        self.run_move('--apply')
        world = json.loads(self.world.read_text())
        self.assertEqual(world['created']['4001']['labels'], [{'name': 'bug,ready-for-agent'}])
        self.run_move('--verify')

    def test_a5_foreign_relationship_numbers_do_not_match(self):
        self.run_move('--apply')
        world = json.loads(self.world.read_text())
        world['foreign_graph_urls'] = True
        self.world.write_text(json.dumps(world))
        before = self.world.read_bytes()
        self.run_move('--verify', ok=False)
        self.run_move('--apply', ok=False)
        self.assertEqual(self.world.read_bytes(), before)

    def test_a6_complete_migration_comment_set_must_be_unambiguous(self):
        self.run_move('--apply')
        original = self.world.read_text()
        for conflict in ['moved to [OpenWiz #4999](https://github.com/openwizdev/openwiz/issues/4999)',
                         '**Private record for OpenWiz #4999, 2030-01-02:**\n\n1. "synthetic conflict"']:
            with self.subTest(conflict=conflict):
                world = json.loads(original)
                world['comments']['9002'].append({'id': 9000000999, 'body': conflict})
                self.world.write_text(json.dumps(world))
                before = self.world.read_bytes()
                self.run_move('--verify', ok=False)
                self.run_move('--apply', ok=False)
                self.assertEqual(self.world.read_bytes(), before)

        world = json.loads(original)  # the legacy address at the right number is not the contract's form
        world['comments']['9002'] = [dict(c, body=c['body'].replace(
            'https://github.com/openwizdev/openwiz/', 'https://github.com/jparker2006/OpenWiz/'))
            for c in world['comments']['9002']]
        self.assertIn('moved to [OpenWiz #4002](https://github.com/jparker2006/OpenWiz/issues/4002)',
                      [c['body'] for c in world['comments']['9002']])
        self.world.write_text(json.dumps(world))
        before = self.world.read_bytes()
        self.assertIn('conflicting or duplicate migration comments', self.run_move('--verify', ok=False).stderr)
        self.run_move('--apply', ok=False)
        self.assertEqual(self.world.read_bytes(), before)

    def test_a7_source_state_metadata_and_migration_exclusions_are_current(self):
        cases = [('state', 'closed'), ('labels', ['changed']), ('milestone', 'Changed'),
                 ('parent', None), ('blockers', [9001]), ('remaining', [1283, 9002])]
        for field, value in cases:
            with self.subTest(field=field):
                world = {'move': fixture(), 'created': {}, 'comments': {}, 'writes': 0}
                if field == 'remaining':
                    world['remaining'] = value
                else:
                    world['move']['graph']['items'][1][field] = value
                self.world.write_text(json.dumps(world))
                self.state = self.root / ('state-source-' + field)
                self.map = self.root / ('map-source-' + field)
                before = self.world.read_bytes()
                self.run_move('--apply', ok=False)
                self.assertEqual(self.world.read_bytes(), before)
        self.state = self.root / 'state-preservation'
        self.map = self.root / 'map-preservation'
        self.world.write_text(json.dumps({'move': fixture(), 'created': {}, 'comments': {}, 'writes': 0}))
        self.run_move('--apply')
        world = json.loads(self.world.read_text())
        world['move']['bodies']['9002'] = 'Synthetic source changed after move.'
        self.world.write_text(json.dumps(world))
        before = self.world.read_bytes()
        self.run_move('--verify', ok=False)
        self.assertEqual(self.world.read_bytes(), before)

    def test_a9_multiple_open_blockers_survive_addition_and_resume(self):
        proposal = fixture()
        proposal['graph']['items'][1]['blockers'] = [9001, 9003, 9004]
        self.plan.write_text(json.dumps(proposal))
        for stop in [None, 9, 10]:
            with self.subTest(after_effect=stop):
                world = {'move': proposal, 'created': {}, 'comments': {}, 'writes': 0}
                if stop:
                    world['stop_after_write'] = stop
                self.world.write_text(json.dumps(world))
                self.state = self.root / ('state-multiple-' + str(stop))
                self.map = self.root / ('map-multiple-' + str(stop))
                self.run_move('--apply', ok=not stop)
                if stop:
                    self.run_move('--apply')
                actual = json.loads(self.world.read_text())
                self.assertEqual(actual['created']['4002']['blockedBy'],
                                 {'nodes': [{'number': 4001}, {'number': 4003}], 'totalCount': 2})
                self.assertEqual([len(actual['comments'][str(n)]) for n in [9001, 9002, 9003]], [1, 2, 1])
                self.run_move('--verify')

    def test_p3_dry_run_and_unavailable_pr_seam_make_no_network_writes(self):
        before = self.world.read_bytes()
        self.run_move()
        self.assertEqual(self.world.read_bytes(), before)
        self.assertFalse(self.state.exists())
        self.assertFalse(self.map.exists())
        bad = fixture()
        bad['graph']['items'][0]['kind'] = 'pull_request'
        self.plan.write_text(json.dumps(bad))
        self.run_move('--apply', ok=False)
        self.assertEqual(self.world.read_bytes(), before)
        self.assertFalse(self.state.exists())
        bad = fixture()
        bad['graph']['items'][0]['title'] = 'Investigate prj_' + 'planted42'
        self.plan.write_text(json.dumps(bad))
        self.run_move('--apply', ok=False)
        self.assertFalse(self.state.exists())
        self.assertEqual(self.world.read_bytes(), before)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--checker', type=Path, default=CHECKER)
    options, remaining = parser.parse_known_args()
    CHECKER = options.checker
    unittest.main(argv=[sys.argv[0], *remaining])
