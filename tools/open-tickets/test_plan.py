#!/usr/bin/env python3
"""P8/P11 map foundation at the command boundary, synthetic gh only."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
PLAN = HERE / 'plan.py'
FAKE = HERE / 'fake-gh'


def fixture():
    return {
        'issues': [
            {'number': 9001}, {'number': 9002}, {'number': 9003},
            {'number': 1257}, {'number': 1283},
        ],
        'pulls': [{'number': 9010}],
        'remaining': [1283],
    }


class PlanContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.world = self.root / 'world.json'
        self.log = self.root / 'gh.jsonl'
        self.env = dict(os.environ, OPEN_TICKETS_WORLD=str(self.world),
                        OPEN_TICKETS_LOG=str(self.log))
        self.world.write_text(json.dumps(fixture()))

    def run_plan(self, *args, ok=True):
        r = subprocess.run([sys.executable, '-I', str(PLAN), *map(str, args)],
                           env=self.env, text=True, capture_output=True)
        self.assertEqual(r.returncode == 0, ok, r.stderr or r.stdout)
        return r

    def generate(self):
        out = self.root / 'out'
        self.run_plan('--gh', FAKE, '--target', 'synthetic-org/openwiz', '--out', out)
        return out

    def test_p8_p11_read_only_complete_inventory_and_planned_mapping(self):
        out = self.generate()
        self.assertEqual((out / 'map.dry-run.tsv').read_text(),
                         'kind\tclosedwiz\topenwiz\n'
                         'issue\t9001\tplanned\nissue\t9002\tplanned\n'
                         'issue\t9003\tplanned\npull_request\t9010\tplanned\n')
        inventory = json.loads((out / 'inventory.json').read_text())
        self.assertEqual(inventory['excluded'], [1257, 1283])
        self.assertEqual(inventory['counts'], {'open_issues': 5, 'open_pull_requests': 1,
                                              'moving_issues': 3, 'moving_pull_requests': 1})
        self.run_plan('--check-map', out / 'map.dry-run.tsv',
                      '--inventory', out / 'inventory.json')
        # The fake refuses every command outside its read-only surface.
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertEqual(len(calls), 10)  # 8 scope reads, plus the PR's files and count
        self.assertTrue(all(c[:2] == ['api', '--method'] and c[2] == 'GET' for c in calls))

    def test_stays_private_pull_requests_are_excluded_and_mixed_ones_move(self):
        # Ruling (#325): a PR whose changed files are all private stays on ClosedWiz.
        # Before, every open PR moved, so a private-only PR could never be complete.
        world = fixture()
        world['pulls'] = [{'number': n} for n in [9010, 9011, 9012, 9013, 9014]]
        world['pull_files'] = {
            '9011': ['private/synthetic.md', 'docs/grills/synthetic.md'],     # all private: stays
            '9012': ['private/synthetic.md', 'crates/core/src/lib.rs'],       # mixed: moves
            '9013': [['docs/grills/synthetic.md', 'crates/core/src/old.rs']],  # renamed from public: moves
            '9014': ['docs/grills/README.md']}                                 # the public grills README: moves
        self.world.write_text(json.dumps(world))
        out = self.generate()
        inventory = json.loads((out / 'inventory.json').read_text())
        self.assertEqual(inventory['excluded'], [1257, 1283, 9011])
        self.assertEqual(inventory['private_pulls'], [{'number': 9011, 'changed_files': 2,
            'files_sha256': hashlib.sha256(b'docs/grills/synthetic.md\nprivate/synthetic.md\n').hexdigest()}])
        self.assertEqual(inventory['counts'], {'open_issues': 5, 'open_pull_requests': 5,
                                              'moving_issues': 3, 'moving_pull_requests': 4})
        self.assertNotIn('\t9011\t', (out / 'map.dry-run.tsv').read_text())
        self.assertIn('pull_request\t9012\tplanned\n', (out / 'map.dry-run.tsv').read_text())
        self.run_plan('--check-map', out / 'map.dry-run.tsv', '--inventory', out / 'inventory.json')
        # A saved record must name a scope PR that is excluded, and only such PRs are excluded.
        for fault in ['issue', 'not-excluded', 'unrecorded']:
            with self.subTest(fault=fault):
                bad = copy.deepcopy(inventory)
                if fault == 'issue':
                    bad['private_pulls'][0]['number'] = 9001
                elif fault == 'not-excluded':
                    bad['excluded'].remove(9011)
                else:
                    bad['private_pulls'] = []
                path = self.root / (fault + '.json')
                path.write_text(json.dumps(bad))
                self.run_plan('--check-map', out / 'map.dry-run.tsv', '--inventory', path, ok=False)
        # An incomplete file list (fewer files than the PR's count) refuses.
        world['pull_counts'] = {'9011': 3}
        self.world.write_text(json.dumps(world))
        r = self.run_plan('--gh', FAKE, '--target', 'synthetic-org/openwiz', '--out', self.root / 'partial', ok=False)
        self.assertIn('PR #9011', r.stderr)
        self.assertFalse((self.root / 'partial').exists())

    def test_listed_stays_private_pulls_are_recorded_with_their_reason(self):
        # Ruling (#325): a short reviewed list keeps PRs private that touch one carried file.
        world = fixture()
        world['pulls'] = [{'number': n} for n in [9010, 9012, 9013]]
        world['pull_files'] = {'9012': ['docs/grills/synthetic.md', 'docs/grills/README.md'],
                               '9013': ['docs/grills/synthetic.md', 'docs/grills/README.md']}
        self.world.write_text(json.dumps(world))
        ruling = 'https://github.com/jparker2006/ClosedWiz/issues/325#issuecomment-9000000325'
        listing = self.root / 'stays-private.json'
        listing.write_text(json.dumps([{'number': 9012, 'reason': 'Synthetic grill-record index line only.',
                                        'ruling': ruling}]))
        out = self.root / 'listed'
        self.run_plan('--gh', FAKE, '--target', 'synthetic-org/openwiz', '--out', out, '--stays-private-prs', listing)
        inventory = json.loads((out / 'inventory.json').read_text())
        self.assertEqual(inventory['excluded'], [1257, 1283, 9012])
        self.assertEqual(inventory['private_pulls'], [])
        self.assertEqual(inventory['listed_private_pulls'], [{'number': 9012, 'changed_files': 2,
            'files_sha256': hashlib.sha256(b'docs/grills/README.md\ndocs/grills/synthetic.md\n').hexdigest(),
            'head_sha': 'b' * 40, 'reason': 'Synthetic grill-record index line only.', 'ruling': ruling}])
        map_text = (out / 'map.dry-run.tsv').read_text()
        self.assertNotIn('\t9012\t', map_text)
        self.assertIn('pull_request\t9013\tplanned\n', map_text)  # unlisted with a public file: moves
        self.run_plan('--check-map', out / 'map.dry-run.tsv', '--inventory', out / 'inventory.json')
        for name, entries in {
                'issue': [{'number': 9001, 'reason': 'Synthetic.', 'ruling': ruling}],
                'not-open': [{'number': 9999, 'reason': 'Synthetic.', 'ruling': ruling}],
                'no-reason': [{'number': 9012, 'reason': ' ', 'ruling': ruling}],
                'foreign-ruling': [{'number': 9012, 'reason': 'Synthetic.',
                                    'ruling': 'https://example.com/synthetic#issuecomment-1'}],
                'duplicate': [{'number': 9012, 'reason': 'Synthetic.', 'ruling': ruling}] * 2}.items():
            with self.subTest(fault=name):
                listing.write_text(json.dumps(entries))
                r = self.run_plan('--gh', FAKE, '--target', 'synthetic-org/openwiz', '--out', self.root / name,
                                  '--stays-private-prs', listing, ok=False)
                self.assertIn('stays-private list', r.stderr)
                self.assertFalse((self.root / name).exists())

    def test_p11_missing_duplicate_and_malformed_rows_refused(self):
        out = self.generate()
        clean = (out / 'map.dry-run.tsv').read_text()
        cases = {
            'missing': clean.replace('issue\t9002\tplanned\n', ''),
            'duplicate': clean + 'issue\t9002\tplanned\n',
            'wrong-kind': clean.replace('pull_request\t9010', 'issue\t9010'),
            'real-number-in-dry-run': clean.replace('9010\tplanned', '9010\t4010'),
            'leading-zero': clean.replace('9002\tplanned', '09002\tplanned'),
            'unsorted': clean.replace('9001\tplanned\nissue\t9002', '9002\tplanned\nissue\t9001'),
            'crlf': clean.replace('\n', '\r\n'),
            'no-final-newline': clean.rstrip('\n'),
        }
        for name, content in cases.items():
            with self.subTest(name=name):
                bad = self.root / (name + '.tsv')
                bad.write_bytes(content.encode())
                r = self.run_plan('--check-map', bad, '--inventory', out / 'inventory.json', ok=False)
                self.assertIn('map:', r.stderr)

    def test_failed_partial_and_duplicate_reads_refuse_without_artifacts(self):
        for mode in ['failed', 'partial', 'duplicate', 'bad-number', 'truncated', 'changed', 'partial-children']:
            with self.subTest(mode=mode):
                self.log.unlink(missing_ok=True)
                world = fixture()
                world['mode'] = mode
                self.world.write_text(json.dumps(world))
                out = self.root / mode
                self.run_plan('--gh', FAKE, '--target', 'synthetic-org/openwiz',
                              '--out', out, ok=False)
                self.assertFalse(out.exists())

    def test_final_api_target_is_default_and_apply_still_refuses(self):
        out = self.root / 'default-target'
        self.run_plan('--gh', FAKE, '--out', out)
        self.assertEqual(json.loads((out / 'inventory.json').read_text())['target'], 'openwizdev/OpenWiz')
        before = self.log.read_bytes()
        self.run_plan('--gh', FAKE, '--target', 'synthetic-org/openwiz',
                      '--out', self.root / 'apply', '--apply', ok=False)
        self.assertEqual(self.log.read_bytes(), before)

    def test_inventory_tampering_refused(self):
        out = self.generate()
        path = out / 'inventory.json'
        original = json.loads(path.read_text())
        cases = []
        missing = copy.deepcopy(original)
        missing['moves'].pop()
        cases.append(missing)
        duplicate = copy.deepcopy(original)
        duplicate['moves'].append(duplicate['moves'][0])
        cases.append(duplicate)
        extra = copy.deepcopy(original)
        extra['ignored'] = True
        cases.append(extra)
        for value in cases:
            path.write_text(json.dumps(value))
            self.run_plan('--check-map', out / 'map.dry-run.tsv', '--inventory', path, ok=False)


if __name__ == '__main__':
    unittest.main()
