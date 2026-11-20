#!/usr/bin/env python3
"""Read every checkpoints fixture as contracts/checkpoints.v1.md says and compare it with expected.json.

The line forms come from the contract's one `checkpoints-v1` block; the
readings below follow its prose. Exit 0 when every fixture reads as
expected.json says, 1 naming each one that doesn't. Run from anywhere:
python3 -I contracts/fixtures/checkpoints/check.py
"""
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
CONTRACT = HERE.parents[1] / 'checkpoints.v1.md'
QUOTES = '"“”'


def forms():
    """The contract's line forms, or None when its block can't be read."""
    try:
        text = CONTRACT.read_text(encoding='utf-8')
        blocks = re.findall(r'^```checkpoints-v1\n(.*?)^```$', text, re.M | re.S)
        if len(blocks) != 1:
            return None
        raw = json.loads(blocks[0])
        return {k: re.compile(v) for k, v in raw.items()}
    except (OSError, ValueError, AttributeError, TypeError, re.error):
        return None


def read_spec(text, f):
    lines = text.split('\n')
    starts = [i for i, line in enumerate(lines) if f['section'].fullmatch(line)]
    if not starts:
        return {'result': 'absent', 'early': True, 'late': False}
    bad = {'result': 'invalid', 'early': True, 'late': True}
    if len(starts) > 1:
        return {**bad, 'code': 'section-repeated'}
    body = []
    for line in lines[starts[0] + 1:]:
        if line.startswith('## '):
            break
        if line.strip():
            body.append(line)
    if len(body) < 2:
        return {**bad, 'code': 'answer-missing'}
    one = f['one_way_door'].fullmatch(body[0])
    user = f['user_visible'].fullmatch(body[1])
    if len(body) != 2 or not one or not user:
        return {**bad, 'code': 'answer-line'}
    one_way, visible = one.group(1) == 'yes', user.group(1) != 'no'
    return {'result': 'answered', 'one_way_door': one_way, 'user_visible': visible,
            'release': user.group(1) == 'yes, a release', 'early': one_way, 'late': visible}


def read_ask(text, f):
    lines = [line for line in text.split('\n') if line.strip()]
    first = f['ask_opening'].fullmatch(lines[0]) if lines else None
    if not first:
        return {'result': 'invalid', 'code': 'ask-opening'}
    evidence, rest = [], lines[1:]
    while rest and (m := f['ask_evidence'].fullmatch(rest[0])):
        if f['code_link'].match(m.group(2)):
            return {'result': 'invalid', 'code': 'evidence-code'}
        evidence.append({'kind': m.group(1), 'url': m.group(2)})
        rest = rest[1:]
    if not evidence:
        return {'result': 'invalid', 'code': 'evidence-missing'}
    look = f['ask_look_for'].fullmatch(rest[0]) if len(rest) == 1 else None
    if not look:
        return {'result': 'invalid', 'code': 'ask-line'}
    return {'result': 'valid', 'pr': int(first.group(1)), 'commit': first.group(2),
            'evidence': evidence, 'look_for': look.group(1)}


def read_record(text, f):
    lines = [line for line in text.split('\n') if line.strip()]
    first = f['record_opening'].fullmatch(lines[0]) if lines else None
    if not first:
        return {'result': 'invalid', 'code': 'record-opening'}
    if any(q in first.group(6) for q in QUOTES):
        return {'result': 'invalid', 'code': 'quoted-words'}
    if len(lines) < 2 or not lines[1].startswith('Private record: '):
        return {'result': 'invalid', 'code': 'pointer-missing'}
    pointer = f['record_pointer'].fullmatch(lines[1])
    if not pointer:
        return {'result': 'invalid', 'code': 'pointer-not-private'}
    if len(lines) != 2:
        return {'result': 'invalid', 'code': 'record-line'}
    return {'result': 'valid', 'decider': first.group(1), 'date': first.group(2),
            'pr': int(first.group(3)), 'commit': first.group(4), 'outcome': first.group(5),
            'decision': first.group(6), 'pointer': pointer.group(1)}


def read_release(scenario, f):
    spec = read_spec((HERE / scenario['spec']).read_text(encoding='utf-8'), f)
    if not scenario['final'] or not spec['late']:
        return {'merge': 'flows'}
    head, authors = scenario['head'], set(scenario['record_authors'])
    asked, newest = False, None
    for comment in scenario['comments']:
        if comment['author'] not in authors:
            continue
        text = (HERE / comment['body']).read_text(encoding='utf-8')
        for reading in (read_ask(text, f), read_record(text, f)):
            if reading['result'] != 'valid' or (reading['pr'], reading['commit']) != (head['pr'], head['commit']):
                continue
            if 'evidence' in reading:
                asked = True
            elif asked:
                newest = reading['outcome']
    if not asked:
        return {'merge': 'held', 'why': 'ask-due'}
    if newest is None:
        return {'merge': 'held', 'why': 'look-due'}
    if newest == 'approved':
        return {'merge': 'released'}
    return {'merge': 'held', 'why': 'changes-asked'}


READERS = {'spec': read_spec, 'ask': read_ask, 'record': read_record}


def main():
    expected = json.loads((HERE / 'expected.json').read_text(encoding='utf-8'))
    f = forms()
    failures = []
    on_disk = {p.relative_to(HERE).as_posix() for kind in (*READERS, 'release') for p in (HERE / kind).iterdir()}
    listed = {name for kind in (*READERS, 'release') for name in expected[kind]}
    failures += [f'{name}: on disk, not in expected.json' for name in sorted(on_disk - listed)]
    failures += [f'{name}: in expected.json, not on disk' for name in sorted(listed - on_disk)]
    for kind in (*READERS, 'release'):
        for name, want in expected[kind].items():
            if name not in on_disk:
                continue
            if f is None:
                got = {'result': 'unreadable: no checkpoints-v1 block in the contract'}
            elif kind == 'release':
                got = read_release(json.loads((HERE / name).read_text(encoding='utf-8')), f)
            else:
                got = READERS[kind]((HERE / name).read_text(encoding='utf-8'), f)
            if got != want:
                failures.append(f'{name}: expected {json.dumps(want)}, got {json.dumps(got)}')
    for line in failures:
        print(f'FAIL {line}')
    total = len(listed)
    print(f'checkpoints fixtures: {total - len(failures)} of {total} read as expected')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
