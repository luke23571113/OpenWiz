#!/usr/bin/env python3
import json
import subprocess
import sys

if sys.argv[1] == 'count':
    rev = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    tally = {'rev': rev, 'files': 0, 'comment_lines': 0, 'disallowed_lines': 0, 'languages': {}}
    print(json.dumps({'schema': 'openwiz.comments.v1', 'paths': [], 'docs': [], 'exclude': [], 'before': None, 'after': tally}))
