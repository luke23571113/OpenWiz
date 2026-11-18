#!/usr/bin/env python3
"""WM2 runtime equivalence against pinned pre-extraction definitions; synthetic inputs only."""
import copy
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
import unittest
from urllib.parse import parse_qs

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import activity
import sources
import collector_runtime as current

BASELINE = json.loads((HERE / 'fixtures/runtime-baseline.json').read_text())
old_text = {'re': re}
exec(compile(BASELINE['tools/war-room/publish.py']['definitions'], '<pinned-publish>', 'exec'), old_text)
old = {'re': re, 'json': json, 'B': activity.B, 'sources': sources,
       'publish': SimpleNamespace(text_scan=old_text['text_scan'])}
exec(compile(BASELINE['tools/war-room/gather.py']['definitions'], '<pinned-gather>', 'exec'), old)


def outcome(call):
    try:
        return ('return', call())
    except Exception as error:
        return ('refused', type(error).__name__, str(error))


class RuntimeEquivalence(unittest.TestCase):
    # catches: extraction losing the bounded status union, refresh or refusal
    # behavior that the collector uses instead of listing the whole run history.
    def test_current_runs_matches_old_outputs_reads_and_refusals(self):
        repo = 'synthetic-owner/work'
        since, until = '2030-01-02T00:00:00Z', '2030-01-03T00:00:00Z'
        base = f'repos/{repo}/actions/workflows/ci.yml/runs?'
        for case in ('valid', 'duplicate', 'wrong status', 'outside window'):
            def exercise(function):
                trace = []
                def read(path):
                    trace.append(path)
                    if not path.startswith(base):
                        return {'synthetic': 'passthrough'}
                    status = parse_qs(path.split('?', 1)[1]).get('status', ['whole'])[0]
                    run = {'id': 9 if status == 'completed' else 7, 'status': status,
                           'created_at': '2030-01-02T12:00:00Z'}
                    rows = [run] if status in ('in_progress', 'completed') else []
                    if case == 'duplicate' and status == 'queued':
                        rows = [dict(run, id=7)]
                    if case == 'wrong status' and status == 'queued':
                        rows = [dict(run, id=8, status='in_progress')]
                    if case == 'outside window' and status == 'completed':
                        rows = [dict(run, created_at='2029-01-01T00:00:00Z')]
                    return {'total_count': len(rows), 'workflow_runs': copy.deepcopy(rows)}
                reader = function(repo, since, until, read)
                result = outcome(lambda: [reader(base + 'per_page=100&page=1'),
                                          reader(base + 'per_page=100&page=2'),
                                          reader(base + 'per_page=100&page=1'), reader('synthetic/other')])
                return result, trace
            with self.subTest(case=case):
                expected = exercise(old['current_runs'])
                if case == 'valid':
                    self.assertEqual([r['id'] for r in expected[0][1][0]['workflow_runs']], [9, 7])
                    self.assertEqual(expected[0][1][-1], {'synthetic': 'passthrough'})
                else:
                    self.assertEqual(expected[0][0], 'refused')
                self.assertEqual(exercise(current.current_runs), expected)

    # catches: extraction permitting a secret (including escaped JSON), binary
    # input or undecodable string that the existing privacy fixtures refuse.
    def test_privacy_scanner_matches_existing_fixture_refusals(self):
        fixture = BASELINE['clean_fixture']
        plants = {}
        exec(compile(BASELINE['privacy_plants'], '<existing-privacy-plants>', 'exec'), plants)
        cases = [('clean fixture', fixture.encode()), ('binary', b'\xff'),
                 ('invalid escape', b'"\\uZZZZ"')]
        for name, value in plants['plants'].items():
            cases.append((name, (fixture + '\n' + value).encode()))
            escaped = ''.join('\\u%04x' % ord(c) for c in value)
            cases.append((name + ' escaped', ('{"value":"' + escaped + '"}').encode()))
        for name, data in cases:
            with self.subTest(case=name):
                expected = outcome(lambda: old['scan_bytes'](data))
                self.assertEqual(expected[0], 'return' if name == 'clean fixture' else 'refused')
                self.assertEqual(outcome(lambda: current.scan_bytes(data)), expected)
                before, after = sources.native('tools/privacy-check/check.py').Checker(), sources.native('tools/privacy-check/check.py').Checker()
                before.refuse = lambda *args, **kwargs: setattr(before, 'findings', before.findings + 1)
                after.refuse = lambda *args, **kwargs: setattr(after, 'findings', after.findings + 1)
                text = data.decode('utf-8', errors='replace')
                old_text['text_scan'](text, before)
                current.text_scan(text, after)
                self.assertEqual(after.findings, before.findings)


if __name__ == '__main__':
    unittest.main()
