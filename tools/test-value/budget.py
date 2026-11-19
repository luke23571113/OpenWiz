#!/usr/bin/env python3
"""PR test-line budget. Reads committed Git diffs and the PR event's body only."""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

TEST_LINE_CEILING = 400
ALLOWANCE_PREFIX = 'Test budget allowance:'
ALLOWANCE = re.compile(r'Test budget allowance: ([0-9]+) lines\. Why: (\S.*)')


class BudgetError(Exception):
    pass


def git(*args):
    try:
        return subprocess.run(['git', *args], check=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise BudgetError('unreadable git diff or history') from error


def commit(ref, label):
    try:
        if not ref:
            raise BudgetError('empty revision')
        return git('rev-parse', '--verify', '--end-of-options',
                   ref + '^{commit}').decode('ascii').strip()
    except (BudgetError, UnicodeError) as error:
        raise BudgetError(f'unreadable {label}: a commit is required') from error


def test_path(name):
    path = PurePosixPath(name)
    parts = path.parts
    return (name.startswith('tests/')
            or (len(parts) >= 4 and parts[0] == 'crates' and parts[2] == 'tests')
            or '__tests__' in parts[:-1]
            or (path.name.startswith('test_') and path.name.endswith('.py'))
            or path.name.endswith(('_test.py', '.test.mjs', '.test.ts', '.test.tsx')))


def counts(base, head):
    # A PR's diff starts at the common ancestor: newer main-only tests must
    # never appear as deletion credit. Disabling renames accounts for each
    # side independently when a move crosses the test-path boundary.
    fork = git('merge-base', base, head).decode('ascii').strip()
    if not fork:
        raise BudgetError('unreadable git diff: no common ancestor')
    diff = git('diff', '--numstat', '-z', '--no-renames', '--no-ext-diff',
               '--no-textconv', '--ignore-submodules=none', fork, head, '--')
    added = deleted = 0
    if not diff:
        return added, deleted
    records = diff.split(b'\0')
    if records.pop() != b'':
        raise BudgetError('unreadable git diff: incomplete records')
    for record in records:
        fields = record.split(b'\t', 2)
        if len(fields) != 3:
            raise BudgetError('unreadable git diff: invalid record')
        plus, minus, raw_name = fields
        if not test_path(raw_name.decode('utf-8', errors='surrogateescape')):
            continue
        if not plus.isdigit() or not minus.isdigit():
            raise BudgetError('uncountable test diff: binary or unknown line counts')
        added += int(plus)
        deleted += int(minus)
    return added, deleted


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate event key')
        result[key] = value
    return result


def description(event):
    try:
        data = json.loads(Path(event).read_text(encoding='utf-8'),
                          object_pairs_hook=unique_object)
        body = data['pull_request']['body']
        if body is None:  # GitHub uses null for a readable, empty body.
            return ''
        if not isinstance(body, str):
            raise ValueError('body must be text')
        return body
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise BudgetError('unreadable description: PR event body is required') from error


def allowance(body):
    lines = [line for line in body.splitlines() if line.startswith(ALLOWANCE_PREFIX)]
    if not lines:
        return 0
    match = ALLOWANCE.fullmatch(lines[0])
    if len(lines) != 1 or match is None:
        raise BudgetError('invalid allowance: use one Test budget allowance: <N> lines. Why: <reason> line')
    return int(match[1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True, help='PR base commit')
    parser.add_argument('--head', required=True, help='PR head commit, not the merge ref')
    parser.add_argument('--event', required=True, help='GitHub PR event JSON containing its description')
    args = parser.parse_args()
    try:
        base, head = commit(args.base, 'base'), commit(args.head, 'head')
        allowed = allowance(description(args.event))
        added, deleted = counts(base, head)
        net = added - deleted
        print(f'test budget: added={added} deleted={deleted} net={net} '
              f'ceiling={TEST_LINE_CEILING} allowance={allowed}')
        if net > TEST_LINE_CEILING + allowed:
            print(f'test budget: FAIL; offset growth or record an allowance of at least '
                  f'{net - TEST_LINE_CEILING} lines with a reason')
            return 1
        print('test budget: PASS; reviewer must judge any allowance reason')
        return 0
    except (BudgetError, ValueError) as error:
        print(f'test budget: FAIL; {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
