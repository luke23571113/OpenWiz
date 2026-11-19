#!/usr/bin/env python3
"""WZ4 (#2634): launch-fleet's carried helpers stay byte-identical to their ClosedWiz sources.

python3 -I tools/fleet-load/test_carried.py

The skill carries shared sources from tools/ and owns its GitHub reader.
Shared copies must match, except for the mint script's docstring during the
reader migration. Missing copies and unlisted files fail by name.
"""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
CARRIED = 'skills/launch-fleet/scripts/carried/'
# Shared copies: copy -> OpenWiz source. The reader is maintained in WizSkills.
PAIRS = {
    'alarm.py': 'tools/ci-overload/alarm.py',
    'healthy.json': 'tools/ci-overload/fixtures/healthy.json',
    'limits.py': 'tools/collector/limits.py',
    'limits.conf': 'tools/collector/limits.conf',
    # read.py finds these through its own parents[1]: scripts/github-app/ beside carried/.
    '../github-app/app.py': 'tools/github-app/app.py',
    '../github-app/mint-token.py': 'tools/github-app/mint-token.py',
    '../github-app/manifest.json': 'tools/github-app/manifest.json',
    # A fixture copy: TL2's sanitized stage bench, read by three of the skill's proofs.
    '../../test/ops-inbox/stage-waits-bench.json': 'tools/collector/fixtures/stage-waits/bench.json',
}


def drift(root, pairs=PAIRS, skill_owned=()):
    """Each copy (repository-relative) that is missing, unreadable, different or unlisted."""
    found = []
    for copy, source in pairs.items():
        copy_path = (root / CARRIED / copy).resolve()
        name = str(copy_path.relative_to(root.resolve()))
        try:
            carried, original = copy_path.read_bytes(), (root / source).read_bytes()
            if source == 'tools/github-app/mint-token.py':
                # WizSkills retains the old reader path in the module docstring.
                # Compare everything before and after it byte for byte.
                carried_parts = carried.split(b'"""', 2)
                original_parts = original.split(b'"""', 2)
                if len(carried_parts) == len(original_parts) == 3:
                    carried_parts[1] = original_parts[1]
                    carried = b'"""'.join(carried_parts)
            same = carried == original
        except OSError:
            same = False
        if not same:
            found.append(name)
    listed = {(root / CARRIED / copy).resolve() for copy in (*pairs, *skill_owned)}
    for name in skill_owned:
        path = root / CARRIED / name
        if not path.is_file():
            found.append(CARRIED + name)
    # Every folder holding only carried copies: anything else in it is unlisted.
    folders = {path.parent for path in listed if path.parent.name in ('carried', 'github-app')}
    for folder in sorted(folders):
        for path in sorted(folder.iterdir()) if folder.is_dir() else ():
            if path.resolve() not in listed and path.name != '__pycache__':  # Python's own cache
                found.append(str(path.resolve().relative_to(root.resolve())))
    return found


class Carried(unittest.TestCase):
    def test_every_carried_copy_matches_its_source(self):
        self.assertEqual(drift(ROOT, skill_owned=('read.py',)), [])

    def test_a_changed_missing_or_unlisted_copy_is_named(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            pairs = {'a.py': 'tools/a/a.py', 'b.conf': 'tools/b/b.conf', 'c.json': 'tools/c/c.json'}
            for copy, source in pairs.items():
                for path in (root / CARRIED / copy, root / source):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b'synthetic\n')
            self.assertEqual(drift(root, pairs), [])
            (root / CARRIED / 'a.py').write_bytes(b'synthetic \n')
            (root / CARRIED / 'b.conf').unlink()
            (root / CARRIED / 'extra.py').write_bytes(b'synthetic\n')
            self.assertEqual(drift(root, pairs), [CARRIED + 'a.py', CARRIED + 'b.conf', CARRIED + 'extra.py'])


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    unittest.main()
