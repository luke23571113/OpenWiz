#!/usr/bin/env python3
"""Synthetic gh for the health proofs only: exact fixture keys, then `re:` keys. No network."""
import json
import os
import re
import sys

args = sys.argv[1:]
if args[:2] == ['api', 'graphql']:
    fields = dict(arg.split('=', 1) for arg in args if '=' in arg)
    key = 'graph:' + fields.get('number', 'prs') + ':' + fields.get('cursor', '')
elif args[:1] == ['api'] and len(args) == 2:
    key = args[1]
else:
    sys.exit(2)
with open(os.environ['HEALTH_FIXTURE'], encoding='utf-8') as stream:
    answers = json.load(stream)
found = answers.get(key)
if found is None:
    found = next((v for k, v in answers.items() if k.startswith('re:') and re.fullmatch(k[3:], key)), None)
if found is None:
    print('synthetic source unavailable', file=sys.stderr)
    sys.exit(1)
print(json.dumps(found))
