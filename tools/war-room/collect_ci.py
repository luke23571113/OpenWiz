#!/usr/bin/env python3
"""MT3 (#822): the collector's CI facts (collector.v1.md). Red-run stub: it reads nothing yet.

  python3 -I collect_ci.py read --repo OWNER/NAME --fact NAME [--fact NAME ...] [--since UTC --until UTC]
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
FACTS = ('runs', 'minutes', 'ci3', 'activity', 'queue')


def read(repository, facts, *, since=None, until=None):
    """Every named fact unavailable: the collector is not built yet."""
    ci = {f: {'fact': f, 'state': 'unavailable', 'read': None, 'point': None, 'window': None, 'fresh_until': None,
              'freshness': 'unknown', 'source': None, 'evidence': [], 'prerequisites': ['not collected yet'],
              'value': None} for f in facts}
    return {'schema': 'openwiz.war-room.collector.read.v1', 'repository': repository,
            'requested_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'factory': {}, 'ci': ci}


def main(argv=None):
    parser = argparse.ArgumentParser(prog='collect_ci.py')
    sub = parser.add_subparsers(dest='command', required=True)
    r = sub.add_parser('read')
    r.add_argument('--repo', required=True)
    r.add_argument('--fact', action='append', required=True, choices=FACTS)
    r.add_argument('--since')
    r.add_argument('--until')
    args = parser.parse_args(argv)
    print(json.dumps(read(args.repo, args.fact, since=args.since, until=args.until), indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
