#!/usr/bin/env python3
"""A recording fake `gh` for the onboarding journey (#1108).

It answers the demo-repository creation and read-back the onboarding helper
makes (`repo create OWNER/NAME --private` and `repo view OWNER/NAME --json
nameWithOwner,isPrivate`), from the synthetic list in $FAKE_GH_REPOS
(JSON: {"repos": {"owner/name": {"private": bool}}, "create": "ok" | "lost" | "fail",
"fail_after_create": N, the N reads after a create failing as a network error would}),
and logs each to $FAKE_GH_CREATE_LOG. "lost" creates the repository but exits 1
with no answer, as a timed-out create. It also answers the launch's read of a
spec's comments (#636: `api --paginate repos/R/issues/N/comments?per_page=100
--jq EXPR`) from launch-fleet's synthetic world, through jq as gh does, or
fails it when $FAKE_GH_COMMENTS_FAIL is set. Every other call goes to
launch-fleet's fake gh unchanged, which refuses writes. All values are synthetic.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

FLEET_GH = Path(__file__).resolve().parents[4] / 'skills/launch-fleet/scripts/fixtures/gh.py'


def main(argv):
    if argv[:2] == ['repo', 'create'] or (argv[:2] == ['repo', 'view'] and len(argv) > 2 and not argv[2].startswith('-')):
        path = os.environ['FAKE_GH_REPOS']
        state = json.loads(Path(path).read_text())
        with open(os.environ['FAKE_GH_CREATE_LOG'], 'a') as log:
            log.write(json.dumps(argv) + '\n')
        name = argv[2]
        if argv[1] == 'view' and state.get('view_fails', 0) > 0:
            state['view_fails'] -= 1
            Path(path).write_text(json.dumps(state))
            sys.stderr.write('synthetic network error\n')
            return 1
        if argv[1] == 'view':
            if argv[3:] != ['--json', 'nameWithOwner,isPrivate'] or name not in state['repos']:
                sys.stderr.write("GraphQL: Could not resolve to a Repository with the name '%s'.\n" % name)
                return 1
            print(json.dumps({'nameWithOwner': name, 'isPrivate': state['repos'][name]['private']}))
            return 0
        if argv[3:] != ['--private'] or name in state['repos'] or state.get('create') == 'fail':
            sys.stderr.write('synthetic create refused\n')
            return 1
        state['repos'][name] = {'private': True}
        state['view_fails'] = state.get('fail_after_create', 0)
        Path(path).write_text(json.dumps(state))
        if state.get('create') == 'lost':
            return 1
        print('https://github.com/%s' % name)
        return 0
    if argv[:2] == ['api', '--paginate'] and len(argv) == 5 and argv[3] == '--jq':
        match = re.fullmatch(r'repos/([^/]+/[^/]+)/issues/([0-9]+)/comments\?per_page=100', argv[2])
        world = json.loads(Path(os.environ['FAKE_GH_WORLD']).read_text())
        if not match or match[1] != world['repo'] or os.environ.get('FAKE_GH_COMMENTS_FAIL'):
            sys.stderr.write('synthetic: HTTP 404\n')
            return 1
        issue = [i for i in world['issues'] if i['number'] == int(match[2])]
        page = [{'body': c['body']} for c in (issue[0]['comments'] if issue else [])]
        return subprocess.run(['jq', '-r', argv[4]], input=json.dumps(page), text=True).returncode
    os.execv(sys.executable, [sys.executable, '-I', '-S', str(FLEET_GH), *argv])


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
