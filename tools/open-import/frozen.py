#!/usr/bin/env python3
"""Frozen old code check: after the cut-over, refuse changes to ClosedWiz's old code."""
import argparse
import datetime
import importlib.util
import os
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


# The importer's own classifier and the carriage guard's list reader, loaded
# rather than copied, so this check and the importer cannot disagree.
importer = _load('open_import', HERE / 'import.py')
guard = _load('open_import_guard', HERE / 'guard.py')
guard.importer = importer

# The private records stay editable in ClosedWiz: private/ (its orchestration
# and evidence folders included) and the grills. Everything else the importer
# leaves out of the public tree retires with the old code.
RECORDS = ('private', 'docs/grills')

REFUSAL = """ClosedWiz's old code is a frozen copy since the cut-over: it is kept for
history until it is deleted (#1287), never edited here.
Product work goes to openwizdev/openwiz: make this change there instead.
Only private records change here: private/ and docs/grills/."""

# #1287 deletes the old tree: its pull request is the one named exception, for
# deleted frozen paths only. It is named by its title, or in a merge group by
# its queue ref.
EXCEPTION = '#1287'
EXCEPTION_REF = re.compile(r'refs/heads/gh-readonly-queue/.+/pr-1287-[0-9a-f]{40}')


def frozen(name, rules):
    """True when the importer carries the path, or it retires (not a private record)."""
    if importer.carries(name, rules):
        return True
    record = any(name == r or name.startswith(r + '/') for r in RECORDS)
    return importer.private_or_retired(name) and not record


def activation(value):
    """The recorded switch date, or None before the switch; anything else is refused."""
    if not value:
        return None
    if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        raise ValueError('activation value')
    datetime.date.fromisoformat(value)
    return value


def excepted(title, queue_ref):
    """True only for #1287's own pull request or its merge group."""
    return title.startswith(EXCEPTION + ':') or bool(EXCEPTION_REF.fullmatch(queue_ref))


def touched(repo, base, head):
    # Paths the change itself adds, modifies or deletes: different at head from
    # both main and the branch point, so main's own later changes are not judged.
    fork = importer.git(repo, 'merge-base', base, head).decode().strip()
    at_base, at_fork, at_head = (importer.entries(repo, c) for c in (base, fork, head))
    paths = sorted(n for n in at_base.keys() | at_fork.keys() | at_head.keys()
                   if at_head.get(n) != at_base.get(n) and at_head.get(n) != at_fork.get(n))
    return paths, {n for n in paths if n not in at_head}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path('.'))
    parser.add_argument('--base', required=True, help='the target branch commit (main)')
    parser.add_argument('--head', default='HEAD', help='the change as it would land')
    args = parser.parse_args()
    try:
        since = activation(os.environ.get('FROZEN_SINCE', ''))
        repo = importer.repository(args.repo)
        base, head = importer.oid(repo, args.base), importer.oid(repo, args.head)
        # The list at the base: a change cannot unfreeze its own paths.
        rules = guard.rules_at(repo, base)
        paths, deleted = touched(repo, base, head)
        hits = [n for n in paths if frozen(n, rules)]
        exception = excepted(os.environ.get('PR_TITLE', ''), os.environ.get('QUEUE_REF', ''))
    except (importer.Refused, OSError, ValueError, UnicodeError):
        # Fail closed; never echo Git stderr or file contents.
        error = sys.exc_info()[1]
        detail = str(error) if isinstance(error, importer.Refused) else 'unreadable input or invalid shape'
        print(f'frozen check error: {detail} (activation, base, head or {guard.LIST})', file=sys.stderr)
        return 2
    if since is None:
        print(f'frozen check: off (no switch recorded); would refuse {len(hits)} paths')
    elif exception and hits and set(hits) <= deleted:
        print(f"frozen check: on since {since}; {EXCEPTION}'s deletion of the old tree, "
              f'the one named exception: {len(hits)} frozen paths deleted')
        return 0
    elif exception and hits:
        hits = [n for n in hits if n not in deleted]
        print(f"frozen check: on since {since}; {EXCEPTION}'s exception covers deleted frozen paths only; "
              f'{len(hits)} touched frozen paths are not deletions.')
    elif hits:
        print(f'frozen check: on since {since}; {len(hits)} of {len(paths)} touched paths are frozen.')
    else:
        print(f'frozen check: on since {since}; no frozen path touched ({len(paths)} touched)')
        return 0
    print('Touched frozen paths:')
    print('\n'.join(hits))
    print()
    if since is None:
        return 0
    print(REFUSAL)
    return 1


if __name__ == '__main__':
    sys.exit(main())
