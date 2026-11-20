#!/usr/bin/env python3
"""#1954 (#1423): `install skills` when a harness's parent folder is a link.

A common dotfiles home links ~/.config elsewhere. An absent harness under it
must be reported `absent` and block nothing; a present one behind the link is
refused on its own row with a plain next step. Synthetic homes only, through
the real `tools/install/install skills`, reusing test_install.py's helpers.
"""
import importlib.util
import os
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
INSTALL = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('test_install', INSTALL / 'test_install.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


class LinkedConfig(base.HarnessSkills):
    def linked_config(self, opencode):
        dotfiles = self.base / 'dotfiles'
        (dotfiles / ('opencode' if opencode else 'other')).mkdir(parents=True)
        os.symlink(dotfiles, self.home / '.config')
        (self.home / '.claude').mkdir()
        return dotfiles

    def test_an_absent_harness_under_a_linked_config_blocks_nothing(self):
        # catches (#1423): an absent OpenCode under a linked ~/.config refusing the whole step (exit 5),
        # so a Claude-Code-only user gets no skills anywhere
        dotfiles = self.linked_config(opencode=False)
        code, result = self.skills()
        self.assertEqual((code, result.get('outcome')), (0, 'installed'), result)
        rows = {r['id']: r for r in result['harnesses']}
        self.assertEqual(rows['opencode']['state'], 'absent')
        self.assertEqual(rows['claude-code']['state'], 'installed')
        self.assertEqual(base.skill_files(self.home / '.claude/skills'),
                         base.skill_files(self.root / 'current/runtime/skills'))
        self.assertEqual(base.snapshot(dotfiles), {'other': 'dir'})

    def test_a_present_harness_behind_a_linked_config_is_refused_on_its_own_row(self):
        # catches: a write through a linked ~/.config into the link's target; a refusal whose next is the bare
        # installer text with no folder or step; the refusal spilling onto the other harnesses' rows
        dotfiles = self.linked_config(opencode=True)
        before = base.snapshot(self.home), base.snapshot(dotfiles)
        code, result = self.skills()
        self.assertEqual((code, result.get('outcome')), (5, 'refused'), result)
        self.assertEqual((base.snapshot(self.home), base.snapshot(dotfiles)), before)
        rows = {r['id']: r for r in result['harnesses']}
        self.assertEqual({h: r['state'] for h, r in rows.items()},
                         {'claude-code': 'installed', 'codex': 'absent', 'cursor': 'absent',
                          'opencode': 'refused', 'grok': 'absent'})
        self.assertIn(str(self.home / '.config'), rows['opencode']['next'])
        self.assertIn('link', rows['opencode']['next'])
        self.assertIn('run this again', rows['opencode']['next'])


def load_tests(loader, tests, pattern):
    """Only this file's cases; the inherited ones run in test_install.py."""
    return loader.loadTestsFromNames(sorted(name for name in LinkedConfig.__dict__ if name.startswith('test_')),
                                     LinkedConfig)


if __name__ == '__main__':
    unittest.main()
