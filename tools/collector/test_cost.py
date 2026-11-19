#!/usr/bin/env python3
"""FM4 (#1172): the one-line cost of a merged pull request, on FM2's synthetic flow world.

The world is fixtures/flow/world.json (its README works the numbers by hand):
ticket 4101, closed by PR 4201, merged 2030-01-02 03:15; the builder used 7
credits and 550 tokens, the reviewer 2 credits and 130 tokens; CI took
4 + 4 + 2 PR and 3 + 2 merge-group runner minutes, 15 in all. Each test adds
only GitHub's answer to "which tickets does PR 4201 close?".

Each case names the bug it catches. Run: python3 -I tools/collector/test_cost.py
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
FLOW = HERE / 'fixtures' / 'flow'
FAKE_GH = HERE / 'fixtures' / 'collector-factory' / 'fake_gh.py'
SCRIPT = HERE / 'cost.py'
REPO, PR, NOW = 'example/factory', '4201', '2030-01-03T06:00:00Z'
USAGE = ('--flow-threads', str(FLOW / 'assignments.json'), '--flow-usage', str(FLOW / 'usage.json'))
# GitHub's answer for one PR: its own merge time and its closing issues.
LINKS = ['api', 'graphql', '-f', 'query=query($owner:String!,$name:String!,$number:Int!,$cursor:String)'
         '{repository(owner:$owner,name:$name){pullRequest(number:$number){mergedAt closingIssuesReferences'
         '(first:100,after:$cursor){nodes{number repository{nameWithOwner}} pageInfo{hasNextPage endCursor}}}}}',
         '-f', 'owner=example', '-f', 'name=factory', '-F', 'number=' + PR]


def closes(*tickets, merged='2030-01-02T03:15:00Z'):
    nodes = [{'number': t, 'repository': {'nameWithOwner': REPO}} for t in tickets]
    page = {'nodes': nodes, 'pageInfo': {'hasNextPage': False, 'endCursor': None}}
    pull = {'mergedAt': merged, 'closingIssuesReferences': page}
    return {'stdout': json.dumps({'data': {'repository': {'pullRequest': pull}}})}


def without(*fragments):
    def edit(world):
        for fragment in fragments:
            del world[next(key for key in world if fragment in key)]
    return edit


def superseded(world):
    """PR 4201 closed unmerged; a replacement, PR 4299, merged ticket 4101 at the same time."""
    key = next(key for key in world if 'closedByPullRequestsReferences' in key)
    answer = json.loads(world[key]['stdout'])
    nodes = answer['data']['repository']['issue']['closedByPullRequestsReferences']['nodes']
    replacement = json.loads(json.dumps(nodes[0]))
    replacement['number'] = 4299
    nodes[0]['mergedAt'] = None
    nodes.append(replacement)
    world[key]['stdout'] = json.dumps(answer)
    key = next(key for key in world if 'pullRequest(number:$number)' in key and '"number=4201"' in key)
    world[key]['stdout'] = world[key]['stdout'].replace('"mergedAt":"2030-01-02T03:15:00Z"', '"mergedAt":null')


def run(*args, links=closes(4101), edit=None):
    world = json.loads((FLOW / 'world.json').read_text())
    if links is not None:
        world[json.dumps(LINKS)] = links
    if edit:
        edit(world)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / 'gh').symlink_to(FAKE_GH)
        (tmp / 'world.json').write_text(json.dumps(world))
        (tmp / 'calls').write_text('')
        env = dict(os.environ, PATH=str(tmp) + os.pathsep + os.environ['PATH'], FAKE_GH_WORLD=str(tmp / 'world.json'),
                   FAKE_GH_LOG=str(tmp / 'calls'), PYTHONDONTWRITEBYTECODE='1')
        return subprocess.run([sys.executable, '-I', str(SCRIPT), '--repo', REPO, '--pr', PR, *args],
                              capture_output=True, text=True, timeout=60, env=env)


class CostLine(unittest.TestCase):
    # catches: a role's credits and tokens swapped or summed across roles, runner minutes
    # added into credits or tokens, the PR's number printed as the ticket, or more than one line.
    def test_line_from_synthetic_facts(self):
        p = run('--now', NOW, *USAGE)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, 'Ticket #4101 cost (PR #4201): builder 7 credits, 550 tokens; '
                                   'reviewer 2 credits, 130 tokens; CI 15 runner minutes; '
                                   'total 9 credits, 680 tokens, 15 runner minutes\n')

    # catches: an unreadable part printed as 0 or dropped, a known part lost because another
    # part is unknown, or a whole unreadable flow read failing instead of saying so.
    def test_unreadable_parts_are_unknown(self):
        cases = {
            'no private usage': ((), None,
                                 'builder unknown; reviewer unknown; CI 15 runner minutes; '
                                 'total unknown credits, unknown tokens, 15 runner minutes'),
            'a CI job unreadable': (USAGE, without('runs/6101/attempts/1/jobs'),
                                    'builder 7 credits, 550 tokens; reviewer 2 credits, 130 tokens; CI unknown; '
                                    'total 9 credits, 680 tokens, unknown runner minutes'),
            'nothing readable': ((), without('closedByPullRequestsReferences'),
                                 'builder unknown; reviewer unknown; CI unknown; total unknown'),
        }
        for scenario, (usage, edit, parts) in cases.items():
            with self.subTest(scenario):
                p = run('--now', NOW, *usage, edit=edit)
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(p.stdout, 'Ticket #4101 cost (PR #4201): ' + parts + '\n')

    # catches: a cost posted for a PR that is not merged (even when another PR merged its
    # ticket), that closes no ticket or several, or whose tickets cannot be read: each prints
    # nothing and exits 1 with its reason.
    def test_no_line_without_one_merged_ticket(self):
        cases = {
            'not merged yet': (('--now', '2030-01-02T02:30:00Z'), closes(4101), None, 'not merged'),
            'superseded by a merged PR': (('--now', NOW, *USAGE), closes(4101, merged=None), superseded, 'not merged'),
            'no ticket': (('--now', NOW), closes(), None, 'closes no ticket'),
            'two tickets': (('--now', NOW), closes(4101, 4102), None, 'closes more than one ticket'),
            'links unreadable': (('--now', NOW), None, None, 'closing tickets could not be read'),
        }
        for scenario, (args, links, edit, reason) in cases.items():
            with self.subTest(scenario):
                p = run(*args, links=links, edit=edit)
                self.assertEqual((p.returncode, p.stdout), (1, ''))
                self.assertIn(reason, p.stderr)

    # catches: a malformed command line reaching GitHub instead of exiting 2.
    def test_bad_command_line(self):
        for args in (('--pr', '0'), ('--repo', 'not-a-repo'), ('--now', 'yesterday')):
            with self.subTest(args):
                p = subprocess.run([sys.executable, '-I', str(SCRIPT), '--repo', REPO, '--pr', PR, *args],
                                   capture_output=True, text=True, timeout=60,
                                   env=dict(os.environ, PATH=str(HERE / 'no-gh-here')))
                self.assertEqual((p.returncode, p.stdout), (2, ''))


if __name__ == '__main__':
    unittest.main(verbosity=2)
