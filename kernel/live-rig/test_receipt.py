#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
RECEIPT = os.path.join(HERE, 'receipt.py')
FIXTURES = os.path.join(HERE, 'fixtures', 'receipts')
RECORDS = os.path.join(FIXTURES, 'records')
EXPECTED = os.path.join(FIXTURES, 'expected')
WIZMARKET_FIXTURE = os.path.join(FIXTURES, 'wizmarket', 'verified-driver.txt')
WIZMARKET_SOURCE = 'fixtures/valid/verified-driver/receipts/example-driver/2026-11-01-aaaaaaaaaaaa.txt'
TOKEN = 'gh' + 'p_' + 'Synthetic0Receipt0Value' * 2
AGENT_CLIS = ('claude codex cursor-agent agent pi opencode copilot goose gemini kimi qwen cline kilo crush vibe '
              'auggie kiro-cli junie amp agy oz sculpt hermes acpx droid').split()


def stubs():
    d = tempfile.mkdtemp(prefix='receipt-stubs-')
    for name in AGENT_CLIS:
        path = os.path.join(d, name)
        with open(path, 'w') as f:
            f.write('#!/bin/sh\necho "refused: %s is a test stub" >&2\nexit 1\n' % name)
        os.chmod(path, 0o755)
    return d


STUBS = stubs()


def record(name, **changes):
    with open(os.path.join(RECORDS, name)) as f:
        r = json.load(f)
    r.update(changes)
    return r


def files(root):
    return sorted(os.path.relpath(os.path.join(d, f), root) for d, _, fs in os.walk(root) for f in fs)


class Receipt(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='receipt-test-')
        self.out = os.path.join(self.tmp, 'out')
        os.mkdir(self.out)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_receipt(self, rec, listing='local', run_by='example-runner', env=None):
        path = os.path.join(self.tmp, 'record.json')
        with open(path, 'w') as f:
            json.dump(rec, f)
        e = dict(os.environ, PATH=STUBS + os.pathsep + os.environ.get('PATH', ''))
        e.pop('OPENWIZ_GITHUB_APP_KEY', None)
        e.update(env or {})
        return subprocess.run([sys.executable, '-I', RECEIPT, path, '--listing', listing, '--run-by=' + run_by,
                               '-o', self.out], capture_output=True, text=True, env=e, timeout=60)

    def written(self, rel):
        with open(os.path.join(self.out, rel), 'rb') as f:
            return f.read()

    def refused(self, rec, why, **kw):
        p = self.run_receipt(rec, **kw)
        self.assertEqual(p.returncode, 1, p.stderr)
        lines = p.stderr.splitlines()
        self.assertEqual(len(lines), 1, p.stderr)
        self.assertTrue(lines[0].startswith('receipt.py: '), p.stderr)
        self.assertIn(why, lines[0])
        self.assertEqual(files(self.out), [], 'a refused record wrote a file')
        return lines[0]

    def test_five_of_five_gives_the_byte_exact_receipt(self):
        p = self.run_receipt(record('5-of-5.json'))
        self.assertEqual(p.returncode, 0, p.stderr)
        rel = os.path.join('receipts', 'local', '2026-11-01-aaaaaaaaaaaa.txt')
        self.assertEqual(files(self.out), [rel])
        with open(os.path.join(EXPECTED, rel), 'rb') as f:
            self.assertEqual(self.written(rel), f.read())
        self.assertEqual(p.stdout, os.path.join(self.out, rel) + '\n')

    def test_receipt_matches_wizmarkets_own_valid_fixture(self):
        self.assertEqual(self.run_receipt(record('5-of-5.json')).returncode, 0)
        ours = self.written(os.path.join('receipts', 'local', '2026-11-01-aaaaaaaaaaaa.txt')).decode()
        with open(WIZMARKET_FIXTURE) as f:
            theirs = f.read()
        self.assertEqual(len(ours.splitlines(True)), 14)
        self.assertEqual([l.split(': ', 1)[0] for l in ours.splitlines(True)[:8]],
                         [l.split(': ', 1)[0] for l in theirs.splitlines(True)[:8]])
        self.assertEqual(ours.splitlines(True)[8:], theirs.splitlines(True)[8:])

    def test_four_of_five_writes_nothing(self):
        self.refused(record('4-of-5.json'), 'kit.py exited 1')

    def test_a_fail_line_with_exit_0_writes_nothing(self):
        self.refused(record('4-of-5.json', kit_exit=0), '4 of 5 pass')

    def test_skipped_record_writes_nothing(self):
        self.refused(record('skipped.json'), 'skipped: not signed in: example-tool')

    def test_lines_out_of_order_write_nothing(self):
        self.refused(record('out-of-order.json'), 'out of order')

    def test_a_missing_or_extra_line_writes_nothing(self):
        lines = record('5-of-5.json')['stdout'].splitlines(True)
        self.refused(record('5-of-5.json', stdout=''.join(lines[:4])), '4 lines')
        self.refused(record('5-of-5.json', stdout=''.join(lines) + 'pass extra: more\n'), '6 lines')

    def test_a_planted_credential_writes_nothing(self):
        stdout = record('5-of-5.json')['stdout'].replace('driver v1', 'driver v1 ' + TOKEN)
        line = self.refused(record('5-of-5.json', stdout=stdout), 'credential')
        self.assertNotIn(TOKEN, line)

    def test_a_secret_from_the_environment_writes_nothing(self):
        value = 'synthetic-environment-value-0001'
        line = self.refused(record('5-of-5.json', model=value), 'credential', env={'EXAMPLE_SERVICE_TOKEN': value})
        self.assertNotIn(value, line)

    def test_a_machine_path_writes_nothing(self):
        self.refused(record('5-of-5.json', model='/home/example/model'), 'machine path')
        self.refused(record('5-of-5.json', harness='C:\\Users\\example\\claude'), 'machine path')

    def test_start_and_wake_must_be_kits_text(self):
        stdout = record('5-of-5.json')['stdout'].replace('posted builder status note', 'posted note')
        self.refused(record('5-of-5.json', stdout=stdout), 'start')
        stdout = record('5-of-5.json')['stdout'].replace('note 1000000001\npass stop', 'note <note>\npass stop')
        self.refused(record('5-of-5.json', stdout=stdout), 'wake')

    def test_the_token_line_must_be_kits_only_passing_line(self):
        stdout = record('5-of-5.json')['stdout'].replace('no login or token passed', 'nothing passed')
        self.refused(record('5-of-5.json', stdout=stdout), 'token')

    def test_a_malformed_record_writes_nothing(self):
        self.refused(record('5-of-5.json', driver_commit='a' * 12), 'driver_commit')
        self.refused(record('5-of-5.json', kit_commit='B' * 40), 'kit_commit')
        self.refused(record('5-of-5.json', date='2026-11-1'), 'date')
        self.refused(record('5-of-5.json', model='two\nlines'), 'model')
        self.refused(record('5-of-5.json', harness=''), 'harness')
        rec = record('5-of-5.json')
        del rec['seconds']
        self.refused(rec, 'keys')

    def test_an_unmapped_host_writes_nothing(self):
        self.refused(record('5-of-5.json', host='example-host'), 'example-host')

    def test_a_listing_that_is_not_this_runs_writes_nothing(self):
        self.refused(record('5-of-5.json'), 'local/claude', listing='claude')
        self.refused(record('5-of-5.json'), 'boat-dev', listing='boat-dev')

    def test_mapped_hosts_name_their_listing(self):
        for host, listing in (('boat.dev', 'boat-dev'), ('Cloudroom', 'cloudroom'), ('Hermes', 'hermes'),
                              ('Pane', 'pane'), ('Factory', 'factory'), ('Conductor', 'conductor'),
                              ('Cursor', 'cursor-cloud-agents')):
            p = self.run_receipt(record('5-of-5.json', host=host), listing=listing)
            self.assertEqual(p.returncode, 0, p.stderr)
            text = self.written(os.path.join('receipts', listing, '2026-11-01-aaaaaaaaaaaa.txt')).decode()
            self.assertTrue(text.startswith('# listing: %s\n# host: %s\n' % (listing, host)), text)

    def test_run_by_must_be_a_login(self):
        self.refused(record('5-of-5.json'), 'run-by', run_by='/home/example')
        self.refused(record('5-of-5.json'), 'run-by', run_by='-example')

    def test_the_first_receipt_is_kept(self):
        self.assertEqual(self.run_receipt(record('5-of-5.json')).returncode, 0)
        rel = os.path.join('receipts', 'local', '2026-11-01-aaaaaaaaaaaa.txt')
        first = self.written(rel)
        p = self.run_receipt(record('5-of-5.json', harness='codex', model='other-model'))
        self.assertEqual(p.returncode, 1)
        self.assertIn('already', p.stderr)
        self.assertEqual(self.written(rel), first)
        self.assertEqual(files(self.out), [rel])

    def test_listings_json_maps_the_three_drivers(self):
        with open(os.path.join(HERE, 'listings.json')) as f:
            listings = json.load(f)
        self.assertEqual({k: listings[k] for k in ('local', 'boat.dev', 'Cloudroom')},
                         {'local': 'local', 'boat.dev': 'boat-dev', 'Cloudroom': 'cloudroom'})


class WizMarket(unittest.TestCase):

    def checkout(self):
        root = os.environ.get('WIZMARKET')
        if not root or not os.path.isdir(os.path.join(root, 'contracts')):
            self.skipTest('skipped: no WizMarket checkout reachable (set WIZMARKET to one)')
        return root

    def test_our_copy_of_the_fixture_is_wizmarkets(self):
        root = self.checkout()
        with open(os.path.join(root, WIZMARKET_SOURCE), 'rb') as a, open(WIZMARKET_FIXTURE, 'rb') as b:
            self.assertEqual(a.read(), b.read())

    def test_wizmarkets_checker_accepts_the_receipt(self):
        root = self.checkout()
        check = os.path.join(root, 'check', 'check.py')
        if not os.path.isfile(check):
            self.skipTest('skipped: WizMarket ships no check/check.py at this checkout')
        reg = tempfile.mkdtemp(prefix='receipt-registry-')
        try:
            rel = os.path.join('receipts', 'local', '2026-11-01-aaaaaaaaaaaa.txt')
            os.makedirs(os.path.join(reg, 'listings'))
            os.makedirs(os.path.join(reg, os.path.dirname(rel)))
            shutil.copy(os.path.join(EXPECTED, rel), os.path.join(reg, rel))
            with open(os.path.join(reg, 'listings', 'local.json'), 'w') as f:
                json.dump({'name': 'Local', 'summary': 'Runs builders on your own computer.', 'tags': ['driver'],
                           'url': 'https://github.com/openwizdev/OpenWiz', 'plugs_into': 'The OpenWiz driver interface',
                           'publisher': 'example-runner', 'stage': 'available', 'status': 'verified',
                           'proof': {'receipt': rel.replace(os.sep, '/')}}, f, indent=2)
                f.write('\n')
            p = subprocess.run([sys.executable, '-I', check, 'check'], cwd=reg, capture_output=True, text=True,
                               timeout=120)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        finally:
            shutil.rmtree(reg)


if __name__ == '__main__':
    unittest.main(verbosity=2)
