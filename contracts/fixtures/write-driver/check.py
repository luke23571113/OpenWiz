#!/usr/bin/env python3
"""Read every write-driver fixture as contracts/write-driver.v1.md says and compare it with expected.json.

The forms come from the contract's one `write-driver-v1` block; the readings
below follow its prose. It also checks that the block's four words and five
checks are exactly the driver contract's and the kit's. Exit 0 when every
fixture reads as expected.json says, 1 naming each one that doesn't. Run from
anywhere: python3 -I contracts/fixtures/write-driver/check.py
"""
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONTRACT = ROOT / 'contracts' / 'write-driver.v1.md'
DRIVER = ROOT / 'kernel' / 'driver.v1.md'
KIT = ROOT / 'kernel' / 'driver-kit' / 'README.md'
# A credential word, even joined to others by `_`, `-` or digits (`EXAMPLE_API_TOKEN`).
CREDENTIAL = re.compile(r'(?i)(?<![a-z])(?:logins?|tokens?|keys?|apikeys?|passwords?|passphrases?|secrets?|credentials?'
                        r'|cookies?|pats?|oauth|bearer)(?![a-z])')
SIGN_IN = re.compile(r'(?i)\bsign(?:ed)? ?in\b|\blog ?in\b')


def block():
    """The contract's `write-driver-v1` block, or None when it can't be read."""
    try:
        text = CONTRACT.read_text(encoding='utf-8')
        blocks = re.findall(r'^```write-driver-v1\n(.*?)^```$', text, re.M | re.S)
        return json.loads(blocks[0]) if len(blocks) == 1 else None
    except (OSError, ValueError):
        return None


def pattern(form, fields):
    """A form's regex: literal text, each `<field>` its field's pattern, a repeat the same value."""
    out, seen = [], set()
    for i, part in enumerate(re.split(r'<([a-z]+)>', form)):
        if i % 2 == 0:
            out.append(re.escape(part))
        elif part in seen:
            out.append(f'(?P={part})')
        else:
            seen.add(part)
            out.append(f'(?P<{part}>{fields[part]})')
    return re.compile(''.join(out))


class Repeated(ValueError):
    pass


def strict(text):
    """JSON with each key once: a repeated key is refused, never replaced."""
    def pairs(items):
        keys = [k for k, _ in items]
        if len(set(keys)) != len(keys):
            raise Repeated
        return dict(items)
    return json.loads(text, object_pairs_hook=pairs)


def text_of(path):
    """A fixture's text without its one final newline."""
    text = path.read_text(encoding='utf-8')
    return text[:-1] if text.endswith('\n') else text


def minutes(time):
    return int(time.split(' ')[0])


def read_copy(text, b, f):
    return {'result': 'valid'} if text == b['copy_line'] else {'result': 'invalid', 'code': 'copy-line'}


def read_fleet(text, b, f):
    m = pattern(b['fleet_file'], f).fullmatch(text)
    return {'result': 'valid', 'account': m['account']} if m else {'result': 'invalid', 'code': 'fleet-file'}


def read_ticket(text, b, f):
    try:
        t = strict(text)
    except Repeated:
        t = None
    if (not isinstance(t, dict) or set(t) != {'title', 'body', 'labels'} or not isinstance(t['title'], str)
            or not isinstance(t['body'], str) or not isinstance(t['labels'], list)
            or not all(isinstance(x, str) for x in t['labels'])):
        return {'result': 'invalid', 'code': 'ticket-fields'}
    title = pattern(b['ticket_title'], f).fullmatch(t['title'])
    body = pattern(b['ticket_body'], f).fullmatch(t['body'])
    if not title or not body or title['host'] != body['host']:
        return {'result': 'invalid', 'code': 'ticket-text'}
    if sorted(t['labels']) != sorted(b['ticket_labels']):
        return {'result': 'invalid', 'code': 'ticket-labels'}
    return {'result': 'valid', 'host': title['host']}


def read_start(text, b, f):
    m = pattern(b['start_record'], f).fullmatch(text)
    return {'result': 'valid', 'host': m['host']} if m else {'result': 'invalid', 'code': 'start-record'}


def read_ask(text, b, f):
    for kind in ('ask', 'sign_in'):
        m = pattern(b[kind], f).fullmatch(text)
        if m:
            words = m['step'] if kind == 'ask' else m['harness'] + ' ' + m['host']
            if CREDENTIAL.search(words):
                return {'result': 'invalid', 'code': 'credential'}
            got = {'result': 'valid', 'kind': 'cost-or-machine' if kind == 'ask' else 'sign-in'}
            return {**got, 'effect': m['effect']} if kind == 'ask' else got
    return {'result': 'invalid', 'code': 'ask-form'}


def shape(value, at=''):
    """A JSON reply's shape: each leaf's key path and type, never its value."""
    if isinstance(value, dict):
        return sorted(p for k, v in value.items() for p in shape(v, f'{at}.{k}' if at else k))
    if isinstance(value, list):
        return sorted({p for v in value for p in shape(v, at + '[]')}) or [f'{at}[]: empty']
    kind = {bool: 'bool', int: 'number', float: 'number', str: 'string', type(None): 'null'}[type(value)]
    return [f'{at}: {kind}']


def skeleton(text):
    """A text reply's shape: its lines, each value (a run of letters, digits, `.`, `_` or `-`) as `w`."""
    return [re.sub(r'[A-Za-z0-9._-]+', 'w', line) for line in text.split('\n')]


def read_lesson(text, b, f):
    try:
        r = strict(text)
    except Repeated:
        r = None
    name = r.get('lesson') if isinstance(r, dict) else None
    text_or_json = lambda v: isinstance(v, (str, dict, list))
    flag = lambda v: isinstance(v, bool)
    fields = {'live-shape': {'lesson': str, 'live': text_or_json, 'fixture': text_or_json},
              'wake-after-turn': {'lesson': str, 'turn_ended': flag, 'wake': lambda v: v in ('answered', 'error'),
                                  'note_edited': flag, 'second_note': flag},
              'expired-login': {'lesson': str, 'exit': lambda v: type(v) is int, 'left_running': flag,
                                'answer': lambda v: isinstance(v, dict) and all(isinstance(x, str) for x in v.values())}}
    want = fields.get(name) if name in b['lessons'] else None
    if not want or set(r) != set(want) or not all(
            (isinstance(r[k], t) if isinstance(t, type) else t(r[k])) for k, t in want.items()):
        return {'result': 'invalid', 'code': 'lesson-fields'}
    if name == 'live-shape':
        if isinstance(r['live'], str) != isinstance(r['fixture'], str):
            return {'result': 'fail', 'code': 'shape-differs'}
        ok = (skeleton(r['live']) == skeleton(r['fixture']) if isinstance(r['live'], str)
              else shape(r['live']) == shape(r['fixture']))
        return {'result': 'pass'} if ok else {'result': 'fail', 'code': 'shape-differs'}
    if name == 'wake-after-turn':
        if not r['turn_ended']:
            return {'result': 'fail', 'code': 'turn-still-running'}
        if r['wake'] != 'answered' or not r['note_edited']:
            return {'result': 'fail', 'code': 'not-woken'}
        if r['second_note']:
            return {'result': 'fail', 'code': 'second-note'}
        return {'result': 'pass'}
    answer = r['answer']
    if r['exit'] == 0:
        return {'result': 'fail', 'code': 'silent-start'}
    if r['exit'] != 1 or set(answer) != {'error', 'next'} or not SIGN_IN.search(answer['next']):
        return {'result': 'fail', 'code': 'no-sign-in-next'}
    if r['left_running']:
        return {'result': 'fail', 'code': 'left-running'}
    return {'result': 'pass'}


def results_line(lead, names, results, line):
    """Each name's result from `<lead>: <name> <result>, ...` in the contract's order, or None."""
    alt = '|'.join(map(re.escape, results))
    m = re.fullmatch(re.escape(lead) + ': ' + ', '.join(f'{re.escape(n)} ({alt})' for n in names), line)
    return list(m.groups()) if m else None


def read_report(text, b, f):
    lines = text.split('\n')
    bad = {'result': 'invalid', 'code': 'report-form'}
    passed = pattern(b['report_passed'], f).fullmatch(lines[0])
    reached = pattern(b['report_not_passing'], f).fullmatch(lines[0])
    if not (passed or reached) or len(lines) != (5 if passed else 4):
        return bad
    kit = results_line('Kit', b['checks'], b['results'], lines[1])
    lessons = results_line('Live lessons', b['lessons'], b['results'], lines[2])
    stopped = pattern(b['stopped'], f).fullmatch(lines[3])
    if kit is None or lessons is None or not (stopped or pattern(b['not_stopped'], f).fullmatch(lines[3])):
        return bad
    if passed and not pattern(b['pull_request'], f).fullmatch(lines[4]):
        return bad
    every = kit.count('pass') == len(kit) and lessons.count('pass') == len(lessons)
    if passed and not every:
        return {'result': 'invalid', 'code': 'report-not-passing'}
    if reached and (every or int(reached['k']) != kit.count('pass')):
        return {'result': 'invalid', 'code': 'report-count'}
    m = passed or reached
    return {'result': 'passed' if passed else 'not-passing', 'host': m['host'],
            'minutes': minutes(m['time']), 'stopped': bool(stopped), 'share_offer': bool(passed and stopped)}


def read_share(text, b, f):
    m = pattern(b['share_line'], f).fullmatch(text)
    if not m:
        return {'result': 'refused', 'code': 'share-line'}
    return {'result': 'valid', 'host': m['host'], 'minutes': minutes(m['time'])}


def read_preview(text, b, f):
    m = pattern(b['share_preview'], f).fullmatch(text)
    if not m:
        return {'result': 'refused', 'code': 'share-preview'}
    return {'result': 'valid', 'issue': int(m['issue']), 'account': m['account'],
            'host': m['host'], 'minutes': minutes(m['time'])}


READERS = {'copy-line': read_copy, 'fleet': read_fleet, 'ticket': read_ticket, 'start': read_start,
           'ask': read_ask, 'lesson': read_lesson, 'report': read_report, 'share': read_share,
           'preview': read_preview}


def reuse(b):
    """The problems with the block's words and checks against the driver contract and the kit."""
    problems = []
    driver = DRIVER.read_text(encoding='utf-8')
    commands_at = re.search(r'^## 1\. Commands\n(.*?)^## 2\. ', driver, re.M | re.S)
    checks_at = re.search(r"^## 3\. The kit's five checks\n(.*?)(?=^## |\Z)", driver, re.M | re.S)
    if not commands_at or not checks_at:
        return ['the driver contract has no Commands or five-checks section to read']
    commands = re.findall(r'^\| `([a-z]+)` \|', commands_at.group(1), re.M)
    if not b.get('words') or not set(b['words']) <= set(commands) or len(b['words']) != 4:
        problems.append('words: not four of the driver contract\'s commands')
    kit_rows = re.findall(r'^\| ([a-z]+) \|', checks_at.group(1), re.M)
    order = re.search(r'in the order ([a-z, ]+)[.:]', KIT.read_text(encoding='utf-8'))
    kit_order = order.group(1).split(', ') if order else None
    if b.get('checks') != kit_order or sorted(kit_rows) != sorted(kit_order or []):
        problems.append('checks: not the kit\'s five checks in its order')
    return problems


def main():
    expected = json.loads((HERE / 'expected.json').read_text(encoding='utf-8'))
    b = block()
    failures = reuse(b) if b else ['the contract has no single readable write-driver-v1 block']
    for kind, cases in expected['fixtures'].items():
        for name, want in cases.items():
            if b is None:
                failures.append(f'{name}: no form to read it by')
                continue
            try:
                got = READERS[kind](text_of(HERE / name), b, b['fields'])
            except (OSError, ValueError, KeyError, TypeError) as e:
                got = {'result': 'unreadable', 'why': type(e).__name__}
            if got != want:
                failures.append(f'{name}: expected {json.dumps(want)}, read {json.dumps(got)}')
    listed = {n for cases in expected['fixtures'].values() for n in cases}
    on_disk = {p.relative_to(HERE).as_posix() for p in HERE.rglob('*')
               if p.is_file() and p.name not in ('check.py', 'expected.json')}
    failures += [f'{n}: on disk but not in expected.json' for n in sorted(on_disk - listed)]
    for line in failures:
        print('fail ' + line)
    print(f'{len(listed)} fixtures, {len(failures)} failures')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
