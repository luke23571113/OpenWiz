#!/usr/bin/env python3
"""The AC6 read-only collectors, exported for the public kit (#772).

Each prints one structure-only JSON document for the run sheet's `*_argv`
bindings, or nothing with exit 2 when any read fails or has another shape,
so a readback can never pass on a failed read. Reads only, through the given
absolute programs, with fixed argument forms; standard library only.

  fleet     the scratch fleet's spec and tickets: state, needs-info, and each
            ticket's merged pull requests into the scratch branch of the same
            repository (a closed issue alone is never a merge)
  delivery  how many events of one thread after a recorded sequence carry an
            exact text, by `thread log <id> --json [--after-seq S] --limit 100`
            pages (the observer's standing-approval method); never the text,
            the id or any content
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

LIMIT = 8 * 1024 * 1024
WINDOW = 100
ISSUE_FIELDS = 'number,state,stateReason,labels,closedByPullRequestsReferences'
PR_FIELDS = 'number,state,baseRefName,headRefOid,mergeCommit'
REPOSITORY = re.compile(r'[A-Za-z0-9-]+/[A-Za-z0-9_.-]+')
OID = re.compile(r'[0-9a-f]{40}')


class Failed(Exception):
    pass


def need(condition):
    if not condition:
        raise Failed()


def pairs(items):
    seen = {}
    for key, value in items:
        need(key not in seen)
        seen[key] = value
    return seen


def constant(_):
    raise Failed()  # NaN and Infinity are not JSON


def read(program, argv):
    """One read: exit 0 and one strict JSON document, or Failed."""
    try:
        done = subprocess.run([program, *argv], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=30)
    except (OSError, subprocess.SubprocessError) as error:
        raise Failed() from error
    need(done.returncode == 0 and len(done.stdout) <= LIMIT)
    try:
        return json.loads(done.stdout, object_pairs_hook=pairs, parse_constant=constant)
    except ValueError as error:
        raise Failed() from error


def text(value):
    need(type(value) is str)
    return value


def number(value):
    need(type(value) is int and value > 0)
    return value


def fleet(args):
    owner, name = args.repo.split('/')

    def issue(n):
        doc = read(args.gh, ['issue', 'view', str(n), '--repo', args.repo, '--json', ISSUE_FIELDS])
        need(type(doc) is dict and set(doc) == set(ISSUE_FIELDS.split(','))
             and number(doc.get('number')) == n and type(doc.get('labels')) is list
             and type(doc.get('closedByPullRequestsReferences')) is list)
        labels = [text(label.get('name')) if type(label) is dict else need(False) for label in doc['labels']]
        return doc, {'number': n, 'state': text(doc.get('state')), 'state_reason': text(doc.get('stateReason')),
                     'needs_info': 'needs-info' in labels}

    def merged(doc):
        found = []
        for ref in doc['closedByPullRequestsReferences']:
            need(type(ref) is dict and type(ref.get('repository')) is dict
                 and type(ref['repository'].get('owner')) is dict)
            pr = number(ref.get('number'))
            if (text(ref['repository']['owner'].get('login')).lower(), text(ref['repository'].get('name')).lower()) \
                    != (owner.lower(), name.lower()):
                continue  # another repository's pull request never merges this ticket
            view = read(args.gh, ['pr', 'view', str(pr), '--repo', args.repo, '--json', PR_FIELDS])
            need(type(view) is dict and set(view) == set(PR_FIELDS.split(',')) and number(view.get('number')) == pr)
            head = text(view.get('headRefOid'))
            if text(view.get('state')) != 'MERGED' or text(view.get('baseRefName')) != args.branch:
                continue
            need(type(view.get('mergeCommit')) is dict and OID.fullmatch(head)
                 and OID.fullmatch(text(view['mergeCommit'].get('oid'))))
            found.append({'number': pr, 'head': head, 'merge_commit': view['mergeCommit']['oid']})
        return found

    spec_doc, spec = issue(args.spec)
    tickets = []
    for n in args.ticket:
        doc, row = issue(n)
        tickets.append(dict(row, merged=merged(doc)))
    return {'schema': 'openwiz.live-smoke-fleet.v1', 'branch': args.branch,
            'spec': spec, 'tickets': tickets,
            'merged_tickets': sum(1 for t in tickets if t['merged'])}


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)


def delivery(args):
    events, after = [], args.after_seq
    for _ in range(100):
        argv = ['thread', 'log', args.thread, '--json', '--limit', str(WINDOW)]
        if after is not None:
            argv[4:4] = ['--after-seq', str(after)]
        rows = read(args.room_cli, argv)
        need(type(rows) is list and len(rows) <= WINDOW)
        for row in rows:
            need(type(row) is dict and type(row.get('seq')) is int)
            need(row['seq'] > (after if after is not None else 0))
            after = row['seq']
            events.append(row)
        if len(rows) < WINDOW:
            break
    else:
        raise Failed()
    exact, wrapped, per_type = 0, 0, {}
    for event in events:
        values = list(strings(event.get('data', event)))
        if any(v == args.text for v in values):
            exact += 1
            kind = event.get('type') if type(event.get('type')) is str else ''
            per_type[kind] = per_type.get(kind, 0) + 1
        elif any(args.text in v for v in values):
            wrapped += 1
    return {'schema': 'openwiz.live-smoke-delivery.v1', 'events': len(events), 'exact': exact,
            'wrapped': wrapped, 'exact_types': len(per_type), 'max_exact_per_type': max(per_type.values(), default=0)}


def program(value):
    path = Path(value)
    if not path.is_absolute():
        raise argparse.ArgumentTypeError('an absolute program')
    return str(path)


def repository(value):
    if not REPOSITORY.fullmatch(value):
        raise argparse.ArgumentTypeError('OWNER/NAME')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='collector', required=True)
    one = sub.add_parser('fleet')
    one.add_argument('--gh', required=True, type=program)
    one.add_argument('--repo', required=True, type=repository)
    one.add_argument('--branch', required=True)
    one.add_argument('--spec', required=True, type=int)
    one.add_argument('--ticket', required=True, type=int, action='append')
    two = sub.add_parser('delivery')
    two.add_argument('--room-cli', required=True, type=program)
    two.add_argument('--thread', required=True)
    two.add_argument('--after-seq', type=int)
    two.add_argument('--text', required=True)
    args = parser.parse_args()
    try:
        if args.collector == 'delivery' and (not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_-]{0,127}', args.thread)
                                             or (args.after_seq is not None and args.after_seq < 1)):
            raise Failed()
        doc = fleet(args) if args.collector == 'fleet' else delivery(args)
    except Failed:
        return 2
    sys.stdout.write(json.dumps(doc, sort_keys=True) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
