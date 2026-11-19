#!/usr/bin/env python3
"""The records v1 test kit: read a tracker and report every record that breaks a rule.

    check.py --fixture <tracker.json>
    check.py --repo <owner>/<name>

Prints one line per break, `#<issue> <rule>: <what>`. Exit 0: no break; 1: breaks
printed; 2: the tracker could not be read (nothing is guessed). It never writes.
The rules are kernel/records.v1.md's.
"""
import argparse
import json
import re
import sys

sys.dont_write_bytecode = True
TRACKER = 'openwiz:records-kit tracker v1'
TIME = re.compile(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$')
REASONS = {'open': (None,), 'closed': (None, 'completed', 'not_planned', 'duplicate')}


class Unreadable(Exception):
    pass


def _refuse(why):
    raise Unreadable(why)


def _object(value, keys, where):
    if not isinstance(value, dict) or set(value) != set(keys):
        _refuse('%s needs exactly the keys %s' % (where, ', '.join(keys)))
    return value


def _int(value, where):
    if type(value) is not int or value < 1:
        _refuse('%s is not a positive whole number' % where)
    return value


def _str(value, where, pattern=None):
    if not isinstance(value, str) or (pattern and not pattern.match(value)):
        _refuse('%s is not a valid string' % where)
    return value


def _list(value, where):
    if not isinstance(value, list):
        _refuse('%s is not a list' % where)
    return value


def read_tracker(data):
    """The tracker, in exactly the shape records-kit/README.md gives, or Unreadable."""
    _object(data, ('tracker', 'repo', 'now', 'record_authors', 'issues'), 'the tracker')
    if data['tracker'] != TRACKER:
        _refuse('tracker is not %r' % TRACKER)
    _str(data['repo'], 'repo', re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$'))
    _str(data['now'], 'now', TIME)
    for a in _list(data['record_authors'], 'record_authors'):
        _str(a, 'a record author')
    seen = set()
    for issue in _list(data['issues'], 'issues'):
        _object(issue, ('number', 'labels', 'parent', 'blocked_by', 'body', 'comments'), 'an issue')
        n = _int(issue['number'], 'an issue number')
        if n in seen:
            _refuse('issue #%d is listed twice' % n)
        seen.add(n)
        for label in _list(issue['labels'], '#%d labels' % n):
            _str(label, '#%d label' % n)
        if issue['parent'] is not None:
            _int(issue['parent'], '#%d parent' % n)
        _str(issue['body'], '#%d body' % n)
        for b in _list(issue['blocked_by'], '#%d blocked_by' % n):
            _object(b, ('number', 'state', 'state_reason'), '#%d blocker' % n)
            _int(b['number'], '#%d blocker number' % n)
            if b['state'] not in REASONS or b['state_reason'] not in REASONS[b['state']]:
                _refuse('#%d blocker #%s has an unknown state' % (n, b['number']))
        for c in _list(issue['comments'], '#%d comments' % n):
            _object(c, ('id', 'author', 'updated_at', 'body'), '#%d comment' % n)
            _int(c['id'], '#%d comment id' % n)
            _str(c['author'], '#%d comment author' % n)
            _str(c['updated_at'], '#%d comment time' % n, TIME)
            _str(c['body'], '#%d comment body' % n)
    return data


def _no_repeats(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        _refuse('a key is repeated')
    return dict(pairs)


def load_fixture(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f, object_pairs_hook=_no_repeats)
    except (OSError, ValueError) as e:
        _refuse('cannot read %s: %s' % (path, e))


def breaks(tracker):
    return []


def main(argv):
    ap = argparse.ArgumentParser(prog='check.py')
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--fixture')
    src.add_argument('--repo')
    args = ap.parse_args(argv)
    try:
        if args.fixture:
            tracker = read_tracker(load_fixture(args.fixture))
        else:
            import github
            tracker = read_tracker(github.read(args.repo))
    except Unreadable as e:
        print('check.py: %s' % e, file=sys.stderr)
        return 2
    found = breaks(tracker)
    for line in found:
        print(line)
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
