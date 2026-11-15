#!/usr/bin/env python3
"""WRD2 (#630): the chart input, prepared from validated history and selected native artifacts.

`prepare(records, at, natives)` returns one `openwiz.war-room.charts-input.v1` document
(input.schema.json), checked structurally and by the cross-field rules in contract.md.
It reads no clock and no network; records come from `history.read_all`, natives from
`read_natives`. Every value keeps its source window, unit, statistic and cohort; nothing
is summed across samples, averaged or interpolated, and a missing day stays missing.
"""
from datetime import timedelta
import hashlib
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import sources  # noqa: E402
import suite  # noqa: E402

SCHEMA_ID = 'openwiz.war-room.charts-input.v1'
INPUT_SCHEMA = suite._decode((HERE / 'input.schema.json').read_text(encoding='utf-8'))
PST = 'PST-fixed-UTC-08:00'
CURRENT_BASIS = 'workflow created to last job completed'
OLDER_BASIS = 'first job created to last job completed'
NATIVE_KINDS = {'board_history'}
NAMES = dict({'main_ci': 'Main CI', 'ci_queue': 'CI queue', 'stage_health': 'Stage health'},
             **{p['slot']: p['slot'].replace('_', ' ').capitalize() for p in suite.PROVIDERS})
# The page's own names where it has them.
try:
    import page as _page  # noqa: E402
    NAMES.update(_page.NAMES)
except ImportError:  # pragma: no cover - page.py ships beside this file
    pass
CONTROL = re.compile(r'[\x00-\x1f\x7f]+')


# --- text and time ------------------------------------------------------------

def clean(text):
    """Retained text: control characters to spaces, markup brackets to guillemets, bounded."""
    suite.require(isinstance(text, str), 'chart text must be a string')
    text = CONTROL.sub(' ', text).replace('<', '‹').replace('>', '›')
    text = ' '.join(text.split())
    text = text if len(text) <= 400 else text[:399] + '…'
    suite.require(bool(text), 'empty chart text')
    return text


def _iso(moment):
    return moment.strftime('%Y-%m-%dT%H:%M:%SZ')


def pst_day(at):
    return (suite._time(at) - timedelta(hours=8)).strftime('%Y-%m-%d')


def day_start(day):
    return _iso(suite._time(day + 'T08:00:00Z'))


def day_after(day):
    return (suite._time(day + 'T00:00:00Z') + timedelta(days=1)).strftime('%Y-%m-%d')


def seven_days(last):
    first = suite._time(last + 'T00:00:00Z') - timedelta(days=6)
    return [(first + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]


def pst_window(days):
    return {'since': day_start(days[0]), 'until': day_start(day_after(days[-1])), 'timezone': PST}


def native_day(window):
    """The PST day of a full native fixed-PST 24-hour window, or None."""
    if window is None or window['timezone'] != PST:
        return None
    since, until = suite._time(window['since']), suite._time(window['until'])
    if since.strftime('%H:%M:%S') != '08:00:00' or until - since != timedelta(days=1):
        return None
    return pst_day(window['since'])


def stale_gap(days, at):
    built = pst_day(at)
    if days and days[-1] < built and day_after(days[-1]) != built:
        return [f'Latest observed day {days[-1]} is before the build day {built}; this is a historical week.']
    return []


# --- native artifacts -----------------------------------------------------------

def chart_selections(selection):
    """The entries of a publish selection the chart build reads: a native board history, or
    the projected board provider gather writes over its pinned raw history (R2)."""
    return [s for s in selection if isinstance(s, dict) and (
        s.get('kind') in NATIVE_KINDS or (s.get('kind') == 'projected' and s.get('slot') == 'board'))]


def _checked_bytes(root, s, at):
    suite.require(type(s) is dict and set(s) == sources.REQUIRED, 'invalid chart selection fields')
    suite.require(type(s['path']) is str and re.fullmatch(r'[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*', s['path'])
                  and not any(x in ('.', '..') for x in s['path'].split('/')), 'invalid chart source path')
    suite.require(type(s['sha256']) is str and re.fullmatch('[0-9a-f]{64}', s['sha256']), 'invalid chart source hash')
    suite.require(type(s['evidence']) is list and s['evidence']
                  and all(type(u) is str and sources.LINK.fullmatch(u) for u in s['evidence']), 'invalid chart source links')
    suite.require(suite._time(s['observed_at']) <= suite._time(at), 'chart source observed after the build')
    suite.require(root is not None, 'a chart selection needs its source root')
    base = Path(root).resolve()
    path = (base / s['path']).resolve()
    suite.require(path.is_relative_to(base), 'chart source escapes its root')
    raw = path.read_bytes()
    suite.require(hashlib.sha256(raw).hexdigest() == s['sha256'], 'chart source hash mismatch')
    return raw


BOARD_COUNTS = ('ready-stock', 'builders-running')


def board_from_projected(root, s, at):
    """The native board history a projected board provider was built from, or None.

    Its ready-stock and builders-running counts, the two 00a plots, pin one raw
    `history.jsonl` (path, SHA-256, observation time, evidence); that becomes a
    board_history selection, then passes read_natives' own checks. Other metrics can
    cite other files (the ratios cite graph.json) and are not this history."""
    provider = suite._decode(_checked_bytes(root, s, at).decode('utf-8'))
    suite.require(type(provider) is dict and provider.get('slot') == 'board', 'projected board slot mismatch')
    pinned = {(m['source']['path'], m['source']['sha256'], m['observed_at'], tuple(m['evidence']))
              for m in provider.get('metrics', [])
              if type(m) is dict and m.get('id') in BOARD_COUNTS and type(m.get('source')) is dict
              and m['source'].get('schema') == sources.PLAN_LINKS}
    if not pinned:
        return None  # an unavailable or graph-only board: nothing to chart
    suite.require(len(pinned) == 1, 'a projected board names more than one history')
    path, sha, observed, evidence = pinned.pop()
    return {'kind': 'board_history', 'slot': 'board', 'path': path, 'sha256': sha,
            'observed_at': observed, 'evidence': list(evidence)}


def read_natives(root, selections, at):
    """Selected native artifacts the chart build reads itself: board history only.

    Each entry has the sources.select shape; its bytes must match their SHA-256, stay
    inside the root and have been observed at or before the build. A projected board
    provider stands for the raw history it pins. Any refusal raises.
    """
    suite._time(at)
    suite.require(type(selections) in (list, tuple), 'chart selection must be an array')
    suite.require(len({s.get('slot') for s in selections if type(s) is dict}) == len(selections),
                  'one chart selection per slot')
    out = []
    for s in selections:
        if type(s) is dict and s.get('kind') == 'projected' and s.get('slot') == 'board':
            s = board_from_projected(root, s, at)
            if s is None:
                continue
        suite.require(type(s) is dict and set(s) == sources.REQUIRED, 'invalid chart selection fields')
        suite.require(s['kind'] in NATIVE_KINDS and s['slot'] == sources.SLOTS[s['kind']], 'unsupported chart selection')
        raw = _checked_bytes(root, s, at)
        lines = [line for line in raw.decode('utf-8').splitlines() if line.strip()]
        rows = [sources.board_strict(line) for line in lines]
        suite.require(bool(rows), 'empty board history')
        for i, row in enumerate(rows):
            suite._finite(row)
            suite.require(sources.board_valid_row(row, i == 0 and row.get('sample') == 'baseline'), 'invalid board history row')
            suite.require(row['at'] <= s['observed_at'], 'board row after its observation')
        out.append({'selection': s, 'rows': rows})
    suite.require(len({n['selection']['kind'] for n in out}) == len(out), 'duplicate chart selection kind')
    return out


# --- history observations -------------------------------------------------------

def _source(slot, metric, source, evidence, samples):
    return {'slot': slot, 'metric': metric, 'path': source['path'], 'schema': clean(source['schema']),
            'sha256': source['sha256'], 'evidence': list(evidence), 'samples': list(samples)}


def observations(records, slot, wanted, key=None):
    """One entry per distinct observation of `slot`'s metrics with `wanted(id)` and a window.

    Repeated across samples (same id, window and source hash, or `key`) it is one
    observation listing every sample that carried it; a known copy wins over a copy
    carried forward as partial after a failed read.
    """
    seen = {}
    for record in records:
        for provider in record['providers']:
            if provider['slot'] != slot:
                continue
            for m in provider['metrics']:
                if not wanted(m['id']) or m['window'] is None or m['source'] is None:
                    continue
                k = key(m) if key else (m['id'], m['window']['since'], m['window']['until'], m['source']['sha256'])
                entry = seen.setdefault(k, {'metric': m, 'samples': []})
                entry['samples'].append(record['sample_id'])
                if entry['metric']['state'] != 'known' and m['state'] == 'known':
                    entry['metric'] = m
    return list(seen.values())


def latest_per_day(entries):
    """The latest-observed entry per native day, and the days observed more than once."""
    by_day, again = {}, set()
    for e in sorted(entries, key=lambda e: (e['metric']['observed_at'], e['samples'][0])):
        day = native_day(e['metric']['window'])
        if day in by_day and by_day[day]['metric']['source']['sha256'] != e['metric']['source']['sha256']:
            again.add(day)
        by_day[day] = e
    return by_day, again


def _figure(fid, kind, title, caption, unit, window, domain, series, rows, gaps, srcs, expected):
    observed = sum(1 for r in rows if r['y'] is not None)
    missing = sorted({r['x'] for r in rows if r['state'] == 'missing' and r['x'] is not None})
    if kind == 'spans':
        missing = sorted({r['key'].removeprefix('missing:') for r in rows if r['state'] == 'missing'})
    return {'id': fid, 'kind': kind, 'title': clean(title), 'caption': clean(caption), 'unit': unit,
            'window': window, 'domain': list(domain), 'series': series, 'rows': rows,
            'coverage': {'observed': observed, 'expected': expected, 'missing': missing},
            'gaps': [clean(g) for g in dict.fromkeys(gaps)], 'srcs': srcs}


def _row(key, series, x, y, state, label, x2=None, text=None):
    """One mark. `text` is a short word drawn visibly on cell figures (a result, a state)."""
    return {'key': key, 'series': series, 'x': x, 'x2': x2, 'y': y, 'state': state, 'text': text,
            'label': clean(label)}


def _unknown_figure(fid, kind, title, caption, unit, reason):
    row = _row('unknown', 'unknown', 'unknown' if kind in ('bars', 'readiness', 'limits') else None, None,
               'unavailable', f'{title}: Unknown. {reason}')
    if kind in ('daily-line', 'daily-bar', 'spans', 'distribution'):
        kind = 'distribution'  # One labelled Unknown word; no axis pretends to a window.
    domain = ['unknown'] if kind in ('bars', 'readiness', 'limits') else []
    return _figure(fid, kind, title, caption, unit, None, domain,
                   [{'key': 'unknown', 'label': 'Unknown', 'role': 'muted'}], [row], [reason], [], None)


def _num(value):
    return int(value) if isinstance(value, float) and value.is_integer() else value


def _fmt(value):
    value = _num(value)
    return str(value) if isinstance(value, int) else ('%g' % value)


# --- the five headline figures --------------------------------------------------

def ready_building(natives, at):
    title = 'Ready & building'
    caption = 'Ready stock and builders running per PST day, from the board\'s last sample that day; the goal is at least twice as many ready as building.'
    board = next((n for n in natives if n['selection']['kind'] == 'board_history'), None)
    if board is None:
        return _unknown_figure('00a', 'daily-line', title, caption, 'count', 'No board history is selected for this build.')
    daily = {}
    for i, row in enumerate(board['rows']):
        if row['sample'] != 'run':
            continue  # The synthetic baseline is not a factory measurement.
        current = daily.get(row['day'])
        if current is None or (row['at'], i) >= (current[0]['at'], current[1]):
            daily[row['day']] = (row, i)
    if not daily:
        return _unknown_figure('00a', 'daily-line', title, caption, 'count', 'The selected board history has no run rows.')
    days = seven_days(max(daily))
    rows = []
    for key, label in (('ready', 'Ready stock'), ('building', 'Builders running'), ('goal', 'Goal (2 × building)')):
        for day in days:
            if day not in daily:
                rows.append(_row(f'{key}:{day}', key, day, None, 'missing', f'{label} {day}: no board sample that PST day'))
                continue
            r = daily[day][0]
            if key == 'goal':
                value = 2 * r['builders_running']
                text = f'Goal {day}: at least {value} ready (2 × {r["builders_running"]} building)'
            else:
                value = r['ready_stock'] if key == 'ready' else r['builders_running']
                text = f'{label} {day}: {value}' + (' (below goal)' if key == 'ready' and r['low_stock'] else '') + f'; last sample {r["at"]}'
            rows.append(_row(f'{key}:{day}', key, day, value, 'known', text))
    s = board['selection']
    srcs = [_source('board', None, {'path': s['path'], 'schema': sources.PLAN_LINKS, 'sha256': s['sha256']},
                    s['evidence'], [])]
    series = [{'key': 'ready', 'label': 'Ready stock', 'role': 'primary'},
              {'key': 'building', 'label': 'Builders running', 'role': 'secondary'},
              {'key': 'goal', 'label': 'Goal: ready at least 2 × building', 'role': 'reference'}]
    fig = _figure('00a', 'daily-line', title, caption, 'count', pst_window(days), days, series, rows,
                  stale_gap(days, at), srcs, 7)
    fig['coverage']['observed'] = sum(1 for d in days if d in daily)
    fig['coverage']['missing'] = [d for d in days if d not in daily]
    return fig


def _daily_ci(records, at, fid, title, caption, unit, metrics, describe, empty_reason):
    """Daily ci_bench figure: one series per (metric, basis), native PST days only."""
    rows, gaps, srcs, series, observed = [], [], [], [], {}
    excluded = set()
    per_series = {}
    for metric_id, statistic in metrics:
        entries = observations(records, 'ci_bench', lambda i, m=metric_id: i == m)
        for e in entries:
            if native_day(e['metric']['window']) is None:
                excluded.add((e['metric']['window']['since'], e['metric']['window']['until']))
                continue
            label = e['metric']['label']
            basis = label[label.index('(') + 1:label.rindex(')')] if '(' in label else None
            per_series.setdefault((metric_id, statistic, basis), []).append(e)
    for (metric_id, statistic, basis), entries in per_series.items():
        by_day, again = latest_per_day(entries)
        for day in again:
            gaps.append(f'{day}: re-measured; the latest observation is shown, never an average.')
        for day, e in by_day.items():
            observed.setdefault((metric_id, statistic, basis), {})[day] = e
    if not observed:
        return _unknown_figure(fid, 'daily-line', title, caption, unit, empty_reason)
    days = seven_days(max(d for v in observed.values() for d in v))
    if excluded:
        n = len(excluded)
        gaps.append(f'Excluded {n} window{"s" if n != 1 else ""} that {"are" if n != 1 else "is"} not a full native PST day.'.replace(
            f'Excluded {n} window that is', f'Excluded {n} window that is'))
    seen_days = set()
    for (metric_id, statistic, basis) in sorted(observed, key=lambda k: (k[2] != CURRENT_BASIS and k[2] is not None, k[1], k[2] or '')):
        older = basis not in (None, CURRENT_BASIS)
        key = statistic if basis is None else f'{statistic}|' + re.sub('[^a-z0-9]+', '-', basis.lower()).strip('-')
        first = statistic in ('median', 'total')
        role = ('older' if first else 'reference') if older else ('primary' if first else 'secondary')
        series.append({'key': key, 'label': clean(statistic + ('' if basis is None else ' · ' + basis + (' (older cohort)' if older else ''))),
                       'role': role})
        for day in days:
            e = observed[(metric_id, statistic, basis)].get(day)
            if e is None:
                rows.append(_row(f'{key}:{day}', key, day, None, 'missing', f'{title} {statistic} {day}: no observation' + (
                    f' ({basis})' if basis else '')))
                continue
            m = e['metric']
            seen_days.add(day)
            rows.append(_row(f'{key}:{day}', key, day, _num(m['value']), m['state'] if m['state'] != 'unavailable' else 'unavailable',
                             describe(m, day, statistic, basis)))
            srcs.append(_source('ci_bench', metric_id, m['source'], m['evidence'], e['samples']))
    gaps.extend(stale_gap(days, at))
    fig = _figure(fid, 'daily-bar' if fid == '00b' else 'daily-line', title, caption, unit, pst_window(days), days,
                  series, rows, gaps, srcs, 7)
    fig['coverage']['observed'] = len(seen_days)
    fig['coverage']['missing'] = [d for d in days if d not in seen_days]
    return fig


def main_merges(records, at):
    return _daily_ci(
        records, at, '00b', 'Main merges',
        'Merged main PRs per native PST day from the CI bench; all-base UTC activity is a separate body figure.',
        'count', [('merged', 'merged')],
        lambda m, day, s, b: f'Main merges {day}: {_fmt(m["value"])} merged PRs (PST day)',
        'No ci_bench native-day merge observation in the history.')


def ci_latency(records, at):
    def describe(m, day, statistic, basis):
        runs = m['sample']['observed']
        return (f'CI latency {statistic} {day}: {_fmt(m["value"])} min over {runs} successful code runs'
                + (f' ({basis})' if basis else ''))
    return _daily_ci(
        records, at, '00c', 'CI latency',
        'Source median and p90 of CI runs per PST day, in minutes; each cohort basis is its own line.',
        'minutes', [('queued-to-done-median', 'median'), ('queued-to-done-p90', 'p90')], describe,
        'No ci_bench native-day latency observation in the history.')


def runner_time(records, at):
    def describe(m, day, statistic, basis):
        runs = m['sample']['observed']
        return f'Runner time {day}: {_fmt(m["value"])} robot-minutes per successful code run ({runs} successful code runs)'
    return _daily_ci(
        records, at, '00d', 'Runner time',
        'Robot-minutes per successful code run per PST day; not wall latency or minutes per merged PR.',
        'robot_minutes_per_code_run', [('robot-minutes', 'total')], describe,
        'No ci_bench native-day runner-time observation in the history.')


def _hours(since, until):
    minutes = int((suite._time(until) - suite._time(since)).total_seconds() // 60)
    h, m = divmod(minutes, 60)
    return f'{h} h' + (f' {m} min' if m else '')


def credit_burn(records, at):
    title = 'Credit burn'
    caption = 'Sampled credit balance drops over each actual span; approximate, not billing, and a rise counts zero.'
    entries = observations(records, 'credits', lambda i: i.startswith('sampled-drop-'), key=lambda m: m['id'])
    if not entries:
        return _unknown_figure('00e', 'spans', title, caption, 'credits', 'No sampled credit spans in the history.')
    by_end = {}
    for e in entries:
        by_end.setdefault(pst_day(_iso(suite._time(e['metric']['window']['until']) - timedelta(seconds=1))), []).append(e)
    days = seven_days(max(by_end))
    rows, srcs, used = [], [], []
    for e in sorted((e for d in days for e in by_end.get(d, [])), key=lambda e: e['metric']['window']['since']):
        m = e['metric']
        since, until = m['window']['since'], m['window']['until']
        end_day = pst_day(_iso(suite._time(until) - timedelta(seconds=1)))
        crosses = pst_day(since) != end_day
        basis = credit_basis(m['id'], since, until)
        used.append(basis)
        label = (f'Credit span {since} to {until} ({_hours(since, until)}): {_fmt(m["value"])} {BASIS_WORDS[basis]}, '
                 f'PST day {end_day}' + ('; crosses a PST midnight, not split' if crosses else '') + '; sampled, not billing')
        rows.append(_row(m['id'], 'drop:' + basis, since, _num(m['value']),
                         'partial' if m['state'] != 'known' else 'known', label, x2=until))
        srcs.append(_source('credits', m['id'], m['source'], m['evidence'], e['samples']))
    for day in days:
        if day not in by_end:
            rows.append(_row('missing:' + day, 'missing', day_start(day), None, 'missing',
                             f'PST day {day}: no sampled credit span ends this day', x2=day_start(day_after(day))))
    window = pst_window(days)
    # A span that starts before the window's first day is drawn from the window's start.
    window['since'] = min([window['since']] + [r['x'] for r in rows])
    # R5: each measurement basis is its own series; an unknown basis is never full-balance evidence.
    series = [{'key': 'drop:' + b, 'label': BASIS_SERIES[b], 'role': BASIS_ROLE[b]} for b in BASES if b in used]
    series.append({'key': 'missing', 'label': 'No span ends this PST day', 'role': 'muted'})
    gaps = ['Sampled balance drops are approximate, not complete daily usage or a billing total.']
    if 'extra-only' in used:
        gaps.append('Extra-only seed spans compare extra credits only; the overall balance change over them is unknown.')
    if 'unknown' in used:
        gaps.append('A span whose basis cannot be recovered from its interval id is shown apart, never as full-balance.')
    observed_days = [d for d in days if d in by_end]
    gaps.append(f'{len(used)} sampled span{"s" if len(used) != 1 else ""} end on {len(observed_days)} of 7 PST days.')
    gaps += stale_gap(days, at)
    fig = _figure('00e', 'spans', title, caption, 'credits', window, days, series, rows, gaps, srcs, 7)
    # R4: day coverage counts PST days with a span ending, never spans against days.
    fig['coverage']['observed'] = len(observed_days)
    return fig


# The native credit reader names each span by sha256(since|until|basis) (sources.credits), so
# the basis is recovered exactly by matching both candidates; anything else stays unknown.
BASES = ('full-balance', 'extra-only', 'unknown')
BASIS_WORDS = {'full-balance': 'credits dropped (full balance)',
               'extra-only': 'extra credits dropped (extra-only seed; overall balance change unknown)',
               'unknown': 'credits dropped (basis unknown)'}
BASIS_SERIES = {'full-balance': 'Sampled drop, full balance', 'extra-only': 'Sampled drop, extra credits only (seed)',
                'unknown': 'Sampled drop, basis unknown'}
BASIS_ROLE = {'full-balance': 'secondary', 'extra-only': 'older', 'unknown': 'reference'}


def credit_basis(metric_id, since, until):
    for basis in BASES[:2]:
        if metric_id == 'sampled-drop-' + hashlib.sha256('|'.join((since, until, basis)).encode('ascii')).hexdigest():
            return basis
    return 'unknown'


# --- body figures ---------------------------------------------------------------

def _provider_rows(provider):
    return [m for m in provider['metrics']]


def readiness(record):
    rows = []
    domain = []
    for p in record['providers'] + suite.health(record):
        name = NAMES.get(p['slot'], p['slot'])
        label = f'{name}: {p["state"]}' + (f'. {p["prerequisites"][0]}' if p['prerequisites'] else '')
        rows.append(_row(p['slot'], 'state', p['slot'], None, p['state'], label, text=p['state']))
        domain.append(p['slot'])
    series = [{'key': 'state', 'label': 'Provider state', 'role': 'primary'}]
    fig = _figure('body-readiness', 'readiness', 'Bench readiness',
                  'Every bench and health signal in the latest sample, by state; grey ones name what they need.',
                  None, None, domain, series, rows, [], [], len(rows))
    fig['coverage']['observed'] = sum(1 for p in rows if p['state'] == 'known')
    return fig


def main_ci_figure(record):
    provider = next(p for p in suite.health(record) if p['slot'] == 'main_ci')
    rows = []
    for o in provider['observations'] or [None]:
        if o is None:
            rows.append(_row('main', 'result', 'main', None, 'unavailable',
                             'Main CI: Unknown. ' + '; '.join(provider['prerequisites']), text='unknown'))
            continue
        ident = o['identity']
        where = (f' at {ident["head_sha"][:7]}' if ident['head_sha'] else '') + (
            f', run {ident["run_id"]} attempt {ident["run_attempt"]}' if ident['run_id'] else '')
        text = f'Main CI{where}: {o["result"]}' + (f' (read {o["point"]})' if o['point'] else '')
        if o['prerequisites']:
            text += '. ' + '; '.join(o['prerequisites'])
        # R1: the result itself is drawn, not only the evidence state: success, failure,
        # pending, cancelled and unknown must look different without hover or disclosure.
        rows.append(_row('main', 'result', 'main', None, o['state'], text, text=o['result'] or 'unknown'))
    srcs = [_source('main_ci', o['id'], o['source'], o['evidence'], [record['sample_id']])
            for o in provider['observations'] if o['source']]
    return _figure('body-main-ci', 'readiness', 'Main CI now',
                   'The latest ci.yml push run on the current main head; anything else is Unknown, never green.',
                   None, None, ['main'], [{'key': 'result', 'label': 'Main CI result', 'role': 'primary'}],
                   rows, [], srcs, 1)


def _limits_figure(fid, title, caption, waits, limits, sample_id, slot, unknown_limit=None):
    """Waits per stage or pool against their loaded limits; open waits are lower bounds."""
    domain = sorted({x for x, _ in waits} | {x for x, _ in limits} | set(unknown_limit or ()))
    rows, srcs = [], []
    for x, o in waits:
        lower = o['state'] == 'partial' and o['value'] is not None
        # R3: the observation's whole stable id (its job or native interval key), never a
        # segment of it: interval keys end in timestamps whose last segment repeats.
        text = f'{o["label"]} ({x}, {o["id"]}): ' + ('Unknown' if o['value'] is None else ('at least ' if lower else '') + f'{_fmt(o["value"])} min')
        rows.append(_row(o['id'], 'wait', x, o['value'], o['state'], text))
        if o['source']:
            srcs.append(_source(slot, o['id'], o['source'], o['evidence'], [sample_id]))
    for x, o in limits:
        rows.append(_row(o['id'], 'limit', x, o['value'], o['state'],
                         f'{x} limit: ' + ('Unknown' if o['value'] is None else f'{_fmt(o["value"])} min')))
    for x in unknown_limit or ():
        rows.append(_row('limit:' + x, 'limit', x, None, 'unavailable', f'{x} limit: Unknown; no source owns a queue limit'))
    if not rows:
        return None
    series = [{'key': 'wait', 'label': 'Wait (hollow: lower bound)', 'role': 'primary'},
              {'key': 'limit', 'label': 'Loaded limit', 'role': 'reference'}]
    return _figure(fid, 'limits', title, caption, 'minutes', None, domain, series, rows, [], srcs, None)


def health_figures(record):
    figs = []
    health = {p['slot']: p for p in suite.health(record)}
    queue = health['ci_queue']['observations']
    counts = [o for o in queue if o['statistic'] == 'count']
    if counts:
        rows = [_row(o['id'], 'count', o['id'], o['value'], o['state'],
                     f'{o["label"]} ({o["id"]}): ' + ('Unknown' if o['value'] is None else _fmt(o['value']))) for o in counts]
        srcs = [_source('ci_queue', o['id'], o['source'], o['evidence'], [record['sample_id']]) for o in counts if o['source']]
        figs.append(_figure('body-ci-queue-count', 'bars', 'CI queue now',
                            'Queued and running CI jobs per exact pool at the read; an incomplete read is Unknown, never zero.',
                            'count', None, [o['id'] for o in counts],
                            [{'key': 'count', 'label': 'Jobs', 'role': 'primary'}], rows, [], srcs, len(rows)))
    waits = [(o['identity']['pool'], o) for o in queue if o['statistic'] in ('max', 'observation')]
    pools = sorted({o['identity']['pool'] for o in queue if o['identity']['pool']})
    fig = _limits_figure('body-ci-queue-wait', 'CI queue waits', 'Queued job waits per exact pool at the read, as lower bounds; no source owns a queue limit.',
                         waits, [], record['sample_id'], 'ci_queue', unknown_limit=pools)
    if fig:
        figs.append(fig)
    stage = health['stage_health']['observations']
    fig = _limits_figure('body-stage-health', 'Stage health',
                         'Stage waits against their loaded limits; open waits are lower bounds and held ones have no value.',
                         [(o['identity']['stage'], o) for o in stage if o['statistic'] == 'observation'],
                         [(o['identity']['stage'], o) for o in stage if o['statistic'] == 'limit'],
                         record['sample_id'], 'stage_health')
    if fig:
        figs.append(fig)
    return figs


def body_figures(record):
    figs = [readiness(record), main_ci_figure(record)] + health_figures(record)
    for provider in record['providers']:
        slot = provider['slot']
        metrics = provider['metrics']
        if slot == 'credits' or not metrics:
            continue  # Credit spans are 00e; an empty provider is in the readiness figure.
        name = NAMES.get(slot, slot)
        if slot == 'stage_waits':
            fig = _limits_figure('body-stage-waits', 'Stage waits', 'Detailed stage waits against their loaded limits, every stage.',
                                 [(m['dimensions']['stage'], m) for m in metrics if m['id'].startswith('wait:')],
                                 [(m['dimensions']['stage'], m) for m in metrics if m['id'].startswith('limit:')],
                                 record['sample_id'], slot)
            if fig:
                figs.append(fig)
            metrics = [m for m in metrics if not m['id'].startswith(('wait:', 'limit:'))]
        if slot == 'journey':
            rows = [_row(m['id'], 'ticket', None, m['value'], m['state'],
                         f'Ticket {m["dimensions"]["ticket"]} ({m["id"]}): {_fmt(m["value"])} h ready to merge') for m in metrics]
            srcs = [_source(slot, m['id'], m['source'], m['evidence'], [record['sample_id']]) for m in metrics if m['source']]
            figs.append(_figure('body-journey', 'distribution', 'Ticket ready to merge',
                                'Hours from ready to first closing merge, one dot per recorded ticket; coverage is unknown.',
                                'hours', None, [], [{'key': 'ticket', 'label': 'Ticket', 'role': 'primary'}],
                                rows, ['Journey historical completeness is unknown.'], srcs, None))
            continue
        for unit in sorted({m['unit'] for m in metrics}):
            mine = [m for m in metrics if m['unit'] == unit]
            rows = [_row(m['id'], 'value', m['id'], m['value'], m['state'],
                         f'{m["label"]} ({m["id"]}): ' + ('Unknown' if m['value'] is None else f'{_fmt(m["value"])} {unit}')
                         + (f' [{m["window"]["since"]}, {m["window"]["until"]})' if m['window'] else '')) for m in mine]
            srcs = [_source(slot, m['id'], m['source'], m['evidence'], [record['sample_id']]) for m in mine if m['source']]
            fid = 'body-' + re.sub('[^a-z0-9]+', '-', f'{slot}-{unit}').strip('-')
            figs.append(_figure(fid, 'bars', f'{name}, {unit.replace("_", " ")}',
                                f'{name} values in {unit.replace("_", " ")} from the latest sample; hollow bars are partial.',
                                unit, None, [m['id'] for m in mine],
                                [{'key': 'value', 'label': name, 'role': 'primary'}], rows,
                                list(dict.fromkeys(p for p in provider['prerequisites'])), srcs, None))
    return figs


# --- the document ---------------------------------------------------------------

def check(doc):
    """input.schema.json, then the cross-field rules; raises ValueError."""
    suite._shape(doc, INPUT_SCHEMA, INPUT_SCHEMA)
    ids = [f['id'] for f in doc['figures']]
    suite.require(len(ids) == len(set(ids)), 'duplicate chart figure id')
    for f in doc['figures']:
        keys = [r['key'] for r in f['rows']]
        suite.require(len(keys) == len(set(keys)), 'duplicate chart row key')
        series = {s['key'] for s in f['series']}
        suite.require(all(r['series'] in series for r in f['rows']), 'chart row of an undeclared series')
        if f['kind'] in ('daily-line', 'daily-bar', 'bars', 'limits', 'readiness'):
            suite.require(all(r['x'] in f['domain'] for r in f['rows']), 'chart row outside its domain')
        if f['kind'] == 'spans':
            suite.require(f['window'] is not None and all(r['x'] and r['x2'] for r in f['rows']), 'span without its ends')
            for r in f['rows']:
                suite.require(suite._time(r['x']) < suite._time(r['x2']), 'reversed span')
        labels = [r['label'] for r in f['rows']]
        suite.require(len(labels) == len(set(labels)), 'two marks with one label')
    # The same privacy rules as every saved record, on every retained string.
    checker_module = sources.native('tools/privacy-check/check.py')

    class Quiet(checker_module.Checker):
        def refuse(self, *args, **kwargs):
            self.findings += 1
    checker = Quiet()

    def strings(value):
        if isinstance(value, str):
            checker.text(value, 'chart input')
            suite.require(not sources.CREDENTIAL.search(value), 'private payload refused')
        elif isinstance(value, dict):
            for item in value.values():
                strings(item)
        elif isinstance(value, list):
            for item in value:
                strings(item)
    strings(doc)
    suite.require(checker.findings == 0, 'private payload refused')
    return doc


def prepare(records, at, natives=()):
    suite._time(at)
    records = sorted(records, key=lambda r: r['sample_id'])
    figures = [ready_building(natives, at), main_merges(records, at), ci_latency(records, at),
               runner_time(records, at), credit_burn(records, at)]
    if records:
        figures += body_figures(records[-1])
    for f in figures:
        f['sources'] = f.pop('srcs')
    versions = [suite.schema_of(r) for r in records]
    doc = {'schema': SCHEMA_ID, 'built_at': at,
           'history': {'samples': len(records), 'v1': versions.count(suite.V1), 'v2': versions.count(suite.V2),
                       'first': records[0]['sample_id'] if records else None,
                       'last': records[-1]['sample_id'] if records else None},
           'figures': figures}
    return check(doc)
