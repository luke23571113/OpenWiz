#!/usr/bin/env python3
"""Synthetic exact-call gh for the collector's factory proofs, never a network fallback.

FAKE_GH_WORLD names a JSON file mapping each exact call (its argument list, as
JSON) to {"stdout": <text>, "exit": <status>}. Every call is appended to
FAKE_GH_LOG. A call the world does not know exits 9: nobody expected it.
"""
import json
import os
import sys

args = sys.argv[1:]
with open(os.environ['FAKE_GH_LOG'], 'a') as log:
    log.write(json.dumps(args) + '\n')
with open(os.environ['FAKE_GH_WORLD']) as f:
    world = json.load(f)
answer = world.get(json.dumps(args), {'exit': 9, 'stdout': ''})
sys.stdout.write(answer['stdout'])
sys.exit(answer.get('exit', 0))
