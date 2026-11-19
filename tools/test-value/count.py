#!/usr/bin/env python3
"""Report test lines by area at a Git revision."""
import argparse
import json
import os
from pathlib import Path
import runpy
import sys

# Load the shared classifier even under Python's isolated mode.
budget = runpy.run_path(str(Path(__file__).with_name('budget.py')))
BudgetError = budget['BudgetError']
commit = budget['commit']
git = budget['git']
test_path = budget['test_path']


def snapshot(revision):
    empty_tree = git('hash-object', '-t', 'tree', os.devnull).decode('ascii').strip()
    diff = git(f'--attr-source={revision}', 'diff', '--numstat', '-z',
               '--no-renames', '--no-relative', '--no-ext-diff', '--no-textconv',
               '--ignore-submodules=none', empty_tree, revision, '--')
    for record in diff.split(b'\0')[:-1]:
        added, _, name = record.split(b'\t', 2)
        # Git reports binary files with a dash instead of a line count.
        yield name.decode('utf-8', errors='surrogateescape'), (
            0 if added == b'-' else int(added)
        )


def area(name, crate_roots):
    parts = name.split('/')
    if parts[0] == 'tests':
        return '/'.join(parts[:2]) if len(parts) >= 3 else 'tests/'
    if parts[0] == 'apps' and len(parts) >= 3:
        return '/'.join(parts[:2])
    if parts[0] == 'crates' and len(parts) >= 3:
        for end in range(len(parts) - 1, 2, -1):
            parent = '/'.join(parts[:end])
            if parent in crate_roots:
                return parent
        return '/'.join(parts[:2])
    for prefix in ('tools/', 'ci/', '.github/', 'contracts/fixtures/'):
        if name.startswith(prefix):
            return prefix
    return 'other'


def count(revision):
    files = list(snapshot(revision))
    crate_roots = {
        name.removesuffix('/Cargo.toml') for name, _ in files
        if name.startswith('crates/') and name.endswith('/Cargo.toml')
    }
    by_area = dict.fromkeys(
        ('tests/', 'tools/', 'ci/', '.github/', 'contracts/fixtures/', 'other'), 0)
    for name, lines in files:
        key = area(name, crate_roots)
        by_area.setdefault(key, 0)
        if test_path(name):
            by_area[key] += lines
    test_lines = sum(by_area.values())
    total_lines = sum(lines for _, lines in files)
    return {
        'revision': revision,
        'by_area': by_area,
        'test_lines': test_lines,
        'total_lines': total_lines,
        'test_share_percent': round(100 * test_lines / total_lines, 2) if total_lines else 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('revision', nargs='?', default='HEAD', help='Git commit (default: HEAD)')
    args = parser.parse_args()
    try:
        revision = commit(args.revision, 'revision')
        print(json.dumps(count(revision), indent=2, sort_keys=True))
    except (BudgetError, ValueError) as error:
        parser.exit(1, f'test line count failed: {error}\n')


if __name__ == '__main__':
    main()
