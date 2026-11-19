#!/usr/bin/env python3
"""The release and launch-fleet lanes split across runners (#743).

A lane's units (each release proof command, each of launch-fleet
test.sh's groups and its other suites; `run.py` names them) go
to N shards by measured time, with the Rust balancer's rule
(`ci/shard/shard.py`: longest first, each to the least loaded shard, an
unmeasured unit counted as the longest). Each member records what it ran;
the ci job's `check` passes only when every unit ran exactly once and the
case counts the members report add up to their script's total.

    python3 -I ci/shard/lanes.py times RECORD...   # lanes.tsv's rows, the median per unit

Exit 0 done; 1 a record refused (why on stderr); 2 a bad command line.
"""
from collections import Counter
import json
from pathlib import Path
import re
import statistics
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import shard  # noqa: E402  the Rust balancer: one splitting rule for every lane

TIMES = Path(__file__).resolve().parent / 'lanes.tsv'
UNIT = re.compile(r'(?:release|site|skill):[A-Za-z0-9._/:-]+|site')
FIELDS = {'lane', 'shard', 'shards', 'plan_sha256', 'units', 'counts'}


class Refused(Exception):
    pass


def times(path=TIMES):
    """Each unit's seconds, from a TSV of `unit<TAB>seconds` ('#' lines are notes)."""
    out = {}
    text = Path(path).read_text(encoding='utf-8')
    for n, line in enumerate(text.splitlines(), 1):
        if line.startswith('#'):
            continue
        fields = line.split('\t')
        if len(fields) != 2 or not UNIT.fullmatch(fields[0]) or not shard.SECONDS.fullmatch(fields[1]):
            raise Refused(f'{path}: line {n} is not "<unit>\\t<seconds>": {line!r}')
        if fields[0] in out:
            raise Refused(f'{path}: {fields[0]} is timed twice')
        out[fields[0]] = float(fields[1])
    return out


def split(units, timed, n):
    """Exactly n shards (a member may get none): each a list of units."""
    known = {u: round(s * 100) for u, s in timed.items()}
    longest = max(known.values(), default=1)
    items = sorted(((known.get(u, longest), u) for u in units), key=lambda x: (-x[0], x[1]))
    shards, loads = shard.lpt(items, n)
    return shards, [x / 100 for x in loads]


def record(lane, k, n, plan_sha256, units, counts):
    return dict(lane=lane, shard=k, shards=n, plan_sha256=plan_sha256, units=units, counts=counts)


def check(lane, plan_sha256, expected, records):
    """Each problem with the members' records; empty when every unit ran once
    and each script's shard counts add up to its total. `expected` lists the
    lane's units; a counted script's own units (`<script>:group:<n>`) are
    expected for 1 to the group count its members report."""
    problems, ran, totals = [], Counter(), {}
    ns = {r.get('shards') for r in records}
    if not records or len(ns) != 1 or not isinstance(next(iter(ns)), int):
        return [f'{lane}: the members disagree on how many shards there are, or none reported']
    n = ns.pop()
    seen = Counter(r.get('shard') for r in records)
    for k in range(1, n + 1):
        if seen[k] != 1:
            problems.append(f'{lane}: shard {k} of {n} reported {seen[k]} times')
    for r in records:
        if set(r) != FIELDS or r['lane'] != lane or r['plan_sha256'] != plan_sha256:
            problems.append(f'{lane}: a record is malformed, or for another lane or plan')
            continue
        ran.update(list(r['units']))
        for script, c in r['counts'].items():
            totals.setdefault(script, []).append(c)
    want = list(expected)
    for script, cs in sorted(totals.items()):
        whole = {(c.get('total'), c.get('groups')) for c in cs}
        if len(whole) != 1 or len(cs) != n:
            problems.append(f'{script}: the shards disagree on its total, or not every shard counted it')
            continue
        total, groups = whole.pop()
        cases = sum(c.get('cases', 0) for c in cs)
        print(f'{script}: ' + ' + '.join(str(c['cases']) for c in cs) + f' = {cases} of {total} cases')
        if cases != total:
            problems.append(f'{script}: {cases} cases ran across the shards, not {total}')
        want += [f'{script}:group:{g}' for g in range(1, groups + 1)]
    problems += [f'{u}: never ran' for u in want if ran[u] == 0]
    problems += [f'{u}: ran {ran[u]} times' for u in want if ran[u] > 1]
    problems += [f'{u}: ran, but the lane has no such unit' for u in sorted(set(ran) - set(want))]
    if not problems:
        print(f'{lane}: every one of its {len(want)} units ran exactly once, across {n} shards')
    return problems


def median_times(paths):
    each = {}
    for path in paths:
        r = json.loads(Path(path).read_text())
        for unit, s in r['units'].items():
            each.setdefault(unit, []).append(s)
    return ''.join(f'{u}\t{statistics.median(each[u]):.2f}\n' for u in sorted(each))


if __name__ == '__main__':
    if len(sys.argv) < 3 or sys.argv[1] != 'times':
        print('usage: python3 -I ci/shard/lanes.py times RECORD...', file=sys.stderr)
        sys.exit(2)
    try:
        sys.stdout.write(median_times(sys.argv[2:]))
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f'lanes: {e}', file=sys.stderr)
        sys.exit(1)
