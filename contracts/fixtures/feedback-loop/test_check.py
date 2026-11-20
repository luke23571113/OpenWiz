#!/usr/bin/env python3
"""Proof P1 of #1840: the feedback-loop fixtures and template hold under the contract.

Run: python3 -I contracts/fixtures/feedback-loop/test_check.py
"""
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import check  # noqa: E402


class Fixtures(unittest.TestCase):
    def test_the_fixtures_and_template_hold_and_cover_the_loop(self):
        # catches: a missing case (a report, either triage outcome, a landed
        # comment, a second merge that posts nothing) or a template that drifts
        # from the contract.
        self.assertEqual(check.check(ROOT), [])


if __name__ == '__main__':
    unittest.main()
