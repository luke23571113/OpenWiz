#!/usr/bin/env python3
"""Synthetic gh only: answers `gh api PATH` from a fixture file, never a network call.

COLLECTOR_CI_FIXTURE names a JSON list of [key, answer] pairs. A key matches
its path exactly, or, when it ends in `?` or `&`, as the path's prefix; the
first match answers. `{owner}` and `{repo}` resolve from GH_REPO, as gh's own
placeholders do, and a path needing them without GH_REPO fails. Each asked
path is appended to COLLECTOR_CI_LOG when set.
"""
import json
import os
import sys

args = sys.argv[1:]
if len(args) != 2 or args[0] != 'api':
    print('synthetic gh answers only `gh api PATH`', file=sys.stderr)
    sys.exit(2)
path = args[1]
if '{owner}' in path or '{repo}' in path:
    if '/' not in os.environ.get('GH_REPO', ''):
        print('no repository for {owner}/{repo}', file=sys.stderr)
        sys.exit(1)
    owner, repo = os.environ['GH_REPO'].split('/', 1)
    path = path.replace('{owner}', owner).replace('{repo}', repo)
if os.environ.get('COLLECTOR_CI_LOG'):
    with open(os.environ['COLLECTOR_CI_LOG'], 'a', encoding='utf-8') as log:
        log.write(path + '\n')
with open(os.environ['COLLECTOR_CI_FIXTURE'], encoding='utf-8') as stream:
    answers = json.load(stream)
for key, answer in answers:
    if path == key or (key.endswith(('?', '&')) and path.startswith(key)):
        print(json.dumps(answer))
        sys.exit(0)
print('synthetic source unavailable', file=sys.stderr)
sys.exit(1)
