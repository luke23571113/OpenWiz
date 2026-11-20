#!/usr/bin/env python3
"""Proof P1 of #1840: the feedback-loop fixtures and template hold under the contract.

Run: python3 -I contracts/fixtures/feedback-loop/test_check.py
"""
import json
from pathlib import Path
import shutil
import sys
import tempfile
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


def planted(edit):
    """Run the check on a copy of the contract, fixtures and template after `edit(root)`."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel in (check.CONTRACT, check.FIXTURES, '.github/ISSUE_TEMPLATE/feedback.yml'):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            copy = shutil.copytree if (ROOT / rel).is_dir() else shutil.copyfile
            copy(ROOT / rel, root / rel)
        edit(root)
        return check.check(root)


def case(name, change):
    def edit(root):
        path = root / check.FIXTURES / f'{name}.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        change(data)
        path.write_text(json.dumps(data), encoding='utf-8')
    return edit


def template(old, new):
    def edit(root):
        path = root / '.github/ISSUE_TEMPLATE/feedback.yml'
        text = path.read_text(encoding='utf-8')
        assert old in text
        path.write_text(text.replace(old, new), encoding='utf-8')
    return edit


class PlantedBreaks(unittest.TestCase):
    """Each guard refuses the break it exists for, and names only it."""

    def refused(self, edit, *expected):
        self.assertEqual(planted(edit), list(expected))

    def test_a_failed_criterion_never_goes_to_a_fleet(self):
        # catches: a report failing a small-and-clear code still sent to a fleet.
        self.refused(case('triage-to-a-fleet', lambda d: d['input']['criteria'].update(no_instructions=False)),
                     'triage-to-a-fleet.json: outcome must be held', 'fixtures: no to a fleet case')

    def test_an_instruction_carrying_report_is_held(self):
        # catches: a report addressed to agents sent to a fleet.
        def send(d):
            d['input']['criteria']['no_instructions'] = True
            d['expect']['outcome'] = 'held'
        self.refused(case('triage-held-instruction', send), 'triage-held-instruction.json: outcome must be fleet')

    def test_the_brief_copies_no_link_or_code_from_the_report(self):
        # catches: a report's link or command carried into a builder's brief.
        def copy(d):
            d['input']['report']['body'] = 'See https://synthetic.example/x\n\n' + d['input']['report']['body']
            d['expect']['brief']['body'] += '\nhttps://synthetic.example/x'
        self.refused(case('triage-to-a-fleet', copy), 'triage-to-a-fleet.json: the brief copies a link or code from the report')

    def test_triage_posts_no_comment_on_the_report(self):
        # catches: triage replying on a report without the owner's yes.
        self.refused(case('triage-held-too-big', lambda d: d['expect']['report_comments'].append('Thanks!')),
                     'triage-held-too-big.json: triage posts no comment on the report')

    def test_a_held_report_keeps_needs_triage(self):
        # catches: a held report labelled as if it were sent on.
        self.refused(case('triage-held-too-big', lambda d: d['expect'].update(report_labels=['feedback'])),
                     "triage-held-too-big.json: the report must be labelled exactly ['feedback', 'needs-triage']")

    def test_a_second_merge_posts_nothing(self):
        # catches: a second landed comment on the same report.
        self.refused(case('landed-second-merge', lambda d: d['expect']['posts'].append([9101, 'x'])),
                     'landed-second-merge.json: posts must be []')

    def test_only_a_record_authors_landed_comment_counts(self):
        # catches: anyone silencing the landed comment by posting its form first.
        def forge(d):
            d['input']['issues']['9101']['comments'][0]['author'] = 'synthetic-user'
        self.refused(case('landed-second-merge', forge),
                     'landed-second-merge.json: posts must be [[9101, '
                     "'Landed: the fix for this report merged in #9202 and will ship in OpenWiz 9.4.2.']]",
                     'fixtures: no second merge case')

    def test_no_landed_comment_without_a_version_or_a_merge(self):
        # catches: a landed comment naming no release, or posted for a closed, unmerged pull request.
        self.refused(case('landed', lambda d: d['input']['issues']['9101'].update(milestone='next')),
                     'landed.json: posts must be []', 'fixtures: no landed case')
        self.refused(case('landed', lambda d: d['input']['pull_request'].update(merged=False)),
                     'landed.json: posts must be []', 'fixtures: no landed case')

    def test_a_marker_counts_only_as_the_last_line(self):
        # catches: an issue quoting a marker mid-body treated as a report.
        self.refused(case('not-a-report', lambda d: d['expect'].update(is_report=True)),
                     'not-a-report.json: is_report is False, the case expects True')

    def test_a_case_with_an_unknown_or_repeated_key_is_refused(self):
        # catches: a reader that silently accepts an extra or repeated key.
        self.refused(case('landed', lambda d: d['expect'].update(note='x')),
                     "landed.json: unreadable: a landed expectation must have exactly the keys ['posts']",
                     'fixtures: no landed case')

        def repeat(root):
            path = root / check.FIXTURES / 'landed.json'
            path.write_text('{"kind": "landed", ' + path.read_text(encoding='utf-8')[1:], encoding='utf-8')
        self.refused(repeat, 'landed.json: unreadable: a repeated key', 'fixtures: no landed case')
        self.refused(case('landed', lambda d: d['input']['pull_request'].update(merged='false')),
                     'landed.json: unreadable: merged is true or false and closes is a list',
                     'fixtures: no landed case')

    def test_the_template_asks_only_for_public_words(self):
        # catches: a template that asks for logs or files, drops the public notice or the label.
        log = '  - type: textarea\n    id: logs\n    attributes:\n      label: Logs\n      render: shell\n'
        fields = "{'type': 'textarea', 'id': 'logs', 'required': False}"
        found = planted(template('  - type: checkboxes', log + '  - type: checkboxes'))
        self.assertEqual(len(found), 2)
        self.assertEqual(found[0], 'template: field logs asks for more than words')
        self.assertIn(fields, found[1])
        self.refused(template('Everything you write here is public: anyone can read it.', 'Tell us.'),
                     'template: the template must open with the public notice')
        self.refused(template('labels: [feedback]', 'labels: [bug]'),
                     "template: the template must be named 'Report a problem' and labelled exactly ['feedback']")
        found = planted(template('      value: "Everything', '      value: |\n        "Everything'))
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0].startswith('template: unreadable: unsupported YAML'))
        found = planted(template('          required: true', '          required: false'))
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0].startswith('template: the template fields must be exactly'))


if __name__ == '__main__':
    unittest.main()
