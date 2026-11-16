#!/usr/bin/env python3
"""MT4 (#823): ci-bench's headline, PRs an hour against the baseline, from one collector snapshot.

`read(path, at)` returns one validated `openwiz.war-room.collector.v1` snapshot
(collector.v1.md); `figure(snapshot)` turns its `factory.prs_per_hour` fact into the
chart figure `body-ci-bench-headline`. See contract.md, "PRs an hour against the baseline".
Values are the snapshot's own numbers, never recomputed; labels print them as ci-bench's
bench.md tables do (two decimals). Unknown stays Unknown, never zero.
"""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import prepare  # noqa: E402
import suite  # noqa: E402

ID = 'body-ci-bench-headline'
SCHEMA = suite._decode((HERE.parent / 'collector.v1.schema.json').read_text(encoding='utf-8'))
DOMAIN = ['baseline:capacity', 'baseline:merged', 'window:capacity', 'window:merged']
SERIES = [{'key': 'capacity', 'label': 'Capacity, successful code runs', 'role': 'primary'},
          {'key': 'merged', 'label': 'Merged into main', 'role': 'secondary'}]
TITLE = 'PRs an hour against the baseline'
CAPTION = ('CI capacity (robots × 60 ÷ robot-minutes per successful code run) and PRs merged into main, '
           'an hour, for the snapshot\'s window against the reviewed baseline; hollow bars are partial.')
CAPACITY_GAP = 'Capacity assumes one successful code run per PR; it is not merged throughput.'
NO_BASELINE = 'no reviewed baseline in the snapshot'


def read(path, at):
    """The snapshot at `path`, checked against the collector schema; raises ValueError.

    It must have been collected at or before the build, and its PRs-an-hour fact's state
    must agree with its value (collector.v1.md, "A fact")."""
    doc = suite._decode(Path(path).read_text(encoding='utf-8'))
    suite._shape(doc, SCHEMA, SCHEMA)
    suite.require(suite._time(doc['collected_at']) <= suite._time(at), 'collector snapshot collected after the build')
    fact = doc['factory']['prs_per_hour']
    suite.require((fact['value'] is None) == (fact['state'] == 'unavailable'), 'PRs an hour state disagrees with its value')
    suite.require(bool(fact['prerequisites']) == (fact['state'] != 'known'), 'PRs an hour prerequisites disagree with its state')
    suite.require(fact['state'] == 'unavailable' or (fact['window'] is not None and fact['source'] is not None),
                  'PRs an hour value without its window and source')
    return doc


def _window(w):
    return f"{w['since']} to {w['until']} {'UTC' if w['timezone'] == 'UTC' else 'PST'}"


def _two(v):
    return f'{v:.2f}'


def _rows(prefix, name, capacity, merged, state, capacity_note, merged_note, why):
    """The capacity and merged rows of one side (baseline or window)."""
    out = []
    for measure, value, note in (('capacity', capacity, capacity_note), ('merged', merged, merged_note)):
        word = 'capacity' if measure == 'capacity' else 'merged into main'
        if value is None:
            label = f'{name}: {word} Unknown' + (f'; {why}' if why else '')
            out.append(prepare._row(f'{prefix}:{measure}', measure, f'{prefix}:{measure}', None, 'unavailable', label))
        else:
            label = f'{name}: {word} {_two(value)} PRs an hour{note}' + (f' (partial: {why})' if state == 'partial' else '')
            out.append(prepare._row(f'{prefix}:{measure}', measure, f'{prefix}:{measure}', value, state, label))
    return out


def figure(snapshot):
    """The headline figure (prepare's figure shape, before `sources` is named)."""
    fact = snapshot['factory']['prs_per_hour']
    sample = [snapshot['collected_at']]
    v, gaps, srcs = fact['value'], list(fact['prerequisites']), []
    base = None if v is None else v['baseline']
    if base is None:
        rows = _rows('baseline', 'Baseline', None, None, 'unavailable', '', '',
                     NO_BASELINE if v is not None else 'PRs an hour unavailable')
        if v is not None:
            gaps.append('No reviewed baseline in the snapshot: the window has nothing to be drawn against.')
    else:
        name = f"Baseline, {base['label']} ({_window(base['window'])})"
        rm = base['robot_minutes_per_code_run']
        rows = _rows('baseline', name, base['capacity_prs_per_hour'], base['merged_per_hour'], 'known',
                     f" on {base['robots']} robots" + ('' if rm is None else f', {_two(rm)} robot-minutes per successful code run'),
                     '', '')
        srcs.append(prepare._source('collector', 'prs_per_hour.baseline', base['source'], [], sample))
    if v is None:
        why = '; '.join(fact['prerequisites'])
        rows += _rows('window', 'Window', None, None, 'unavailable', '', '', why)
    else:
        name = f"Window {_window(fact['window'])}"
        rm = v['robot_minutes_per_code_run']
        capacity_note = (f" on {v['robots']} robots, {v['code_runs']} successful code runs"
                         + ('' if rm is None else f' at {_two(rm)} robot-minutes each'))
        why = '; '.join(fact['prerequisites']) if fact['state'] == 'partial' else (
            'no successful code run in the window' if v['capacity_prs_per_hour'] is None else '')
        rows += _rows('window', name, v['capacity_prs_per_hour'], v['merged_per_hour'], fact['state'],
                      capacity_note, f" ({v['merged_prs']} PRs)", why)
        srcs.append(prepare._source('collector', 'prs_per_hour', fact['source'], fact['evidence'], sample))
    gaps.append(CAPACITY_GAP)
    return prepare._figure(ID, 'bars', TITLE, CAPTION, 'prs_per_hour', fact['window'], DOMAIN, SERIES, rows,
                           gaps, srcs, len(DOMAIN))
