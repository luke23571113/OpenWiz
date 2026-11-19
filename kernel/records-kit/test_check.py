#!/usr/bin/env python3
"""R1: the records kit passes a valid tracker and reports each planted break.

Run: python3 -I kernel/records-kit/test_check.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, 'fixtures')

# Each planted break, with the exact lines the kit must print for it, and nothing else.
BREAKS = {
    'wrong-label': ['#2 L1: label building says what an agent is doing; read it from GitHub'],
    'held-and-ready': ['#2 L2: held beside ready-for-agent'],
    'ticket-carries-spec': ['#2 L3: a ticket carries spec'],
    'spec-lacks-label': ['#2 L3: its spec #1 lacks spec', '#4 L3: its spec #1 lacks spec'],
    'two-live-notes': ['#2 S1: 2 live builder notes: 202, 208'],
    'unreadable-note': ['#2 S2: note 208 does not read as openwiz:status v1'],
    'missing-template-part': ['#2 T1: ticket lacks ## Proof', '#2 T1: ticket lacks **Relies on:**'],
    'spec-missing-section': ['#1 T1: spec lacks ## Out of Scope'],
    'human-missing-done-by': ['#4 T1: ticket lacks ## Done by'],
    'blocker-not-completed': ['#2 B2: blocker #9 is closed as not_planned, not completed',
                              '#2 B2: blocker #10 is closed as duplicate, not completed'],
}


def run(path):
    p = subprocess.run([sys.executable, '-I', os.path.join(HERE, 'check.py'), '--fixture', path],
                       capture_output=True, text=True, timeout=60)
    return p.returncode, p.stdout.splitlines(), p.stderr


def valid():
    with open(os.path.join(FIXTURES, 'valid.json')) as f:
        return json.load(f)


class Kit(unittest.TestCase):
    def test_valid_tracker_passes(self):
        # catches: a rule that flags a valid record (a lapsed note counted live, a heading in a code
        # block, a record author's name in another case, another version's note, a project's own label)
        code, out, err = run(os.path.join(FIXTURES, 'valid.json'))
        self.assertEqual((code, out), (0, []), err)

    def test_each_planted_break_is_reported(self):
        # catches: a rule that misses its break, or reports the wrong issue, rule or count
        names = sorted(n[len('broken-'):-len('.json')] for n in os.listdir(FIXTURES) if n.startswith('broken-'))
        self.assertEqual(names, sorted(BREAKS))
        for name, want in BREAKS.items():
            with self.subTest(name):
                code, out, err = run(os.path.join(FIXTURES, 'broken-%s.json' % name))
                self.assertEqual((code, out), (1, want), err)

    def test_reader_refuses_any_other_shape(self):
        # catches: a reader that guesses at a malformed tracker and reports it clean (exit 0)
        def drop(d, k):
            del d[k]
        bad = {
            'unknown top key': lambda d: d.update(extra=1),
            'missing top key': lambda d: drop(d, 'now'),
            'unknown issue key': lambda d: d['issues'][0].update(state='open'),
            'labels not a list': lambda d: d['issues'][0].update(labels='spec'),
            'number as text': lambda d: d['issues'][0].update(number='1'),
            'number as true': lambda d: d['issues'][0].update(number=True),
            'repeated number': lambda d: d['issues'][1].update(number=1),
            'bad blocker reason': lambda d: d['issues'][1]['blocked_by'][0].update(state_reason='done'),
            'open blocker with reason': lambda d: d['issues'][1]['blocked_by'][0].update(state='open'),
            'bad time': lambda d: d.update(now='2030-01-02 04:00'),
            'impossible time': lambda d: d.update(now='2030-13-02T04:00:00Z'),
            'comment author missing': lambda d: drop(d['issues'][1]['comments'][0], 'author'),
            'other tracker version': lambda d: d.update(tracker='openwiz:records-kit tracker v2'),
        }
        with tempfile.TemporaryDirectory() as tmp:
            for name, plant in bad.items():
                with self.subTest(name):
                    d = valid()
                    plant(d)
                    path = os.path.join(tmp, 'bad.json')
                    with open(path, 'w') as f:
                        json.dump(d, f)
                    code, out, err = run(path)
                    self.assertEqual((code, out), (2, []))
                    self.assertTrue(err.startswith('check.py: '), err)
            path = os.path.join(tmp, 'dup.json')
            with open(path, 'w') as f:
                f.write(json.dumps(valid())[:-1] + ', "now": "2030-01-02T04:00:00Z"}')
            code, out, err = run(path)
            self.assertEqual((code, out), (2, []), 'a repeated key must be refused, never replaced')


if __name__ == '__main__':
    unittest.main(verbosity=2)
