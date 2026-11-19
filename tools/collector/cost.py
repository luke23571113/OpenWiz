#!/usr/bin/env python3
"""FM4 (#1172): the one-line cost of a merged pull request. Reads only.

  python3 -I tools/collector/cost.py --repo OWNER/NAME --pr N
      [--flow-threads FILE --flow-usage FILE ...] [--now UTC]

Prints one line for the PR's ticket: builder, reviewer, CI and total, from
the collector's `flow` fact (collector.v1.md, "Ticket and spec facts"). The
total adds builder and reviewer in each unit; runner minutes stay their own
unit and are never added to credits or tokens. A part the collector could
not read prints as unknown, never zero. `--flow-threads` and `--flow-usage`
are the flow fact's private role assignments and daily usage exports;
without them builder and reviewer are unknown. `--now` fixes the clock.

Exit 0 with the line; 1, with nothing on stdout, when the PR closes no
ticket or more than one, its tickets cannot be read, its ticket is not
merged, or the read is refused for privacy; 2 for a bad command line.
"""
import argparse
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import collect_factory as F  # noqa: E402

M = F.M


class NoLine(Exception):
    """The PR has no one merged ticket to cost; the reason is printed."""


def closing_tickets(repo, pr):
    """The PR's same-repository closing tickets, every page."""
    tickets, cursor, cursors = [], None, set()
    while True:
        links, cursor = M.connection(M.obj(M.graph(repo, cursor, pr).get('pullRequest')).get('closingIssuesReferences'))
        for value in links:
            issue = M.obj(value)
            owner = M.obj(issue.get('repository')).get('nameWithOwner')
            M.require(type(owner) is str, 'invalid linked issue')
            if owner.casefold() == repo.casefold():
                tickets.append(M.integer(issue.get('number')))
        if cursor is None:
            return sorted(set(tickets))
        M.require(cursor not in cursors, 'repeated link cursor')
        cursors.add(cursor)


def amount(value, unit, places):
    if value is None:
        return 'unknown ' + unit
    text = f'{round(value, places):,.{places}f}'
    return (text.rstrip('0').rstrip('.') if places else text) + ' ' + unit


def role(cost):
    if cost['credits'] is None and cost['tokens'] is None:
        return 'unknown'
    return amount(cost['credits'], 'credits', 2) + ', ' + amount(cost['tokens'], 'tokens', 0)


def line(pr, ticket, cost):
    ci = cost['ci_minutes']
    total = cost['total']
    known = [total['credits'], total['tokens'], ci]
    return (f"Ticket #{ticket} cost (PR #{pr}): builder {role(cost['builder'])}; reviewer {role(cost['reviewer'])}; "
            f"CI {'unknown' if ci is None else amount(ci, 'runner minutes', 1)}; total "
            + ('unknown' if all(v is None for v in known) else
               ', '.join((amount(total['credits'], 'credits', 2), amount(total['tokens'], 'tokens', 0),
                          amount(ci, 'runner minutes', 1)))))


UNKNOWN = {'builder': {'credits': None, 'tokens': None}, 'reviewer': {'credits': None, 'tokens': None},
           'total': {'credits': None, 'tokens': None}, 'ci_minutes': None}


def cost_line(repo, pr, *, clock=F.now, flow_threads=None, flow_usage=()):
    try:
        tickets = closing_tickets(repo, pr)
    except (M.ReadError, ValueError, TypeError, KeyError):
        raise NoLine(f"PR #{pr}'s closing tickets could not be read")
    if not tickets:
        raise NoLine(f'PR #{pr} closes no ticket')
    if len(tickets) > 1:
        raise NoLine(f'PR #{pr} closes more than one ticket')
    ticket, = tickets
    try:
        doc = F.read(repo, ['flow'], tickets=[ticket], clock=clock, flow_threads=flow_threads, flow_usage=flow_usage)
    except F.Refused:
        raise NoLine('the read was refused for privacy')
    value = doc['factory']['flow']['value']
    row = next((t for t in value['tickets'] if t['ticket'] == ticket), None) if value else None
    if row is not None and row['state'] != 'unknown' and (row['state'] != 'merged' or pr not in row['pull_requests']):
        raise NoLine(f'PR #{pr} or its ticket #{ticket} is not merged')
    return line(pr, ticket, row['cost'] if row else UNKNOWN)


def main(argv):
    def utc(text):
        try:
            F.when(text)
        except ValueError:
            raise argparse.ArgumentTypeError('expected YYYY-MM-DDTHH:MM:SSZ')
        return text

    def repo(text):
        if not F.REPO.fullmatch(text):
            raise argparse.ArgumentTypeError('expected OWNER/NAME')
        return text

    def positive(text):
        if not re.fullmatch(r'[1-9][0-9]{0,8}', text):
            raise argparse.ArgumentTypeError('expected a positive integer')
        return int(text)

    parser = argparse.ArgumentParser(description='One line: a merged pull request\'s ticket cost (FM4). Reads only.')
    parser.add_argument('--repo', type=repo, required=True, help='OWNER/NAME')
    parser.add_argument('--pr', type=positive, required=True, help='the merged pull request')
    parser.add_argument('--flow-threads', type=Path, help='private ticket-to-role usage assignments')
    parser.add_argument('--flow-usage', type=Path, action='append', help='complete private daily usage export (repeat)')
    parser.add_argument('--now', type=utc, help='a fixed clock')
    a = parser.parse_args(argv)
    try:
        print(cost_line(a.repo, a.pr, clock=(lambda: a.now) if a.now else F.now,
                        flow_threads=a.flow_threads, flow_usage=a.flow_usage or ()))
    except NoLine as reason:
        print(f'cost: {reason}; nothing printed', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
