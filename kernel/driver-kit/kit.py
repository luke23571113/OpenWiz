#!/usr/bin/env python3
"""The driver v1 test kit: run the five checks against one driver on a throwaway ticket.

Red skeleton: it reads its arguments and the schema, and checks nothing yet.
"""
import argparse
import json
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))


def _unique(pairs):
    if len({k for k, _ in pairs}) != len(pairs):
        raise ValueError('a key is repeated')
    return dict(pairs)


def parse(text):
    return json.loads(text, object_pairs_hook=_unique)


def load_schema():
    with open(os.path.join(HERE, 'schema.json')) as f:
        return parse(f.read())


def invalid(value, schema, at='the answer'):
    return None


def main(argv):
    ap = argparse.ArgumentParser(prog='kit.py')
    for name in ('--driver', '--repo', '--harness', '--model'):
        ap.add_argument(name, required=True)
    ap.add_argument('--ticket', type=int, required=True)
    ap.add_argument('--skill', default='build-ticket')
    ap.add_argument('--tracker')
    ap.add_argument('--wait', type=int, default=900)
    ap.parse_args(argv)
    load_schema()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
