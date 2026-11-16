#!/usr/bin/env python3
"""MT2 (#821) red-first stub: every factory fact unavailable. Replaced by the collector."""
import argparse
from datetime import datetime, timezone
import json
import sys

FACTS = ('merges', 'prs_per_hour', 'stage_waits', 'stalls', 'open_prs', 'journeys', 'cost')


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def unavailable(name):
    return {'fact': name, 'state': 'unavailable', 'read': None, 'point': None, 'window': None, 'fresh_until': None,
            'freshness': 'unknown', 'source': None, 'evidence': [], 'prerequisites': ['Not collected yet.'],
            'value': None}


def read(repository, facts, *, since=None, until=None, clock=now, **_):
    return {'schema': 'openwiz.war-room.collector.read.v1', 'repository': repository, 'requested_at': clock(),
            'factory': {name: unavailable(name) for name in facts}, 'ci': {}}


def validate(fact):
    pass


def main(argv):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    r = sub.add_parser('read')
    r.add_argument('--repo', required=True)
    r.add_argument('--fact', action='append', choices=FACTS, required=True)
    for name in ('--since', '--until', '--usage', '--now', '--robots'):
        r.add_argument(name)
    r.add_argument('--ticket', action='append')
    a = parser.parse_args(argv)
    print(json.dumps(read(a.repo, a.fact, clock=(lambda: a.now) if a.now else now)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
