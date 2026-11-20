#!/usr/bin/env python3
"""Read every checkpoints fixture as contracts/checkpoints.v1.md says and compare it with expected.json.

The line forms come from the contract's one `checkpoints-v1` block; the
readings below follow its prose. Exit 0 when every fixture reads as
expected.json says, 1 naming each one that doesn't. Run from anywhere:
python3 -I contracts/fixtures/checkpoints/check.py
"""
import datetime
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

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
        return {k: re.compile(v) if isinstance(v, str) else set(v) for k, v in raw.items()}
    except (OSError, ValueError, AttributeError, TypeError, re.error):
        return None


def text_of(path):
    """A fixture's text with every CRLF and lone CR turned into LF."""
    return path.read_bytes().decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')


def fenced(lines, f):
    """The indexes of lines inside fenced blocks, their fences included."""
    inside, opening = set(), None
    for i, line in enumerate(lines):
        if opening is None:
            m = f['fence'].fullmatch(line)
            if m:
                opening = m.group(1)
                inside.add(i)
            continue
        inside.add(i)
        close = re.fullmatch(r' {0,3}(`+|~+)[ \t]*', line)
        if close and close.group(1)[0] == opening[0] and len(close.group(1)) >= len(opening):
            opening = None
    return inside


def read_spec(text, f):
    lines = text.split('\n')
    inside = fenced(lines, f)
    outside = [i for i in range(len(lines)) if i not in inside]
    bad = {'result': 'invalid', 'early': True, 'late': True}
    for i in outside:
        exact = f['section'].fullmatch(lines[i])
        setext = (f['setext_text'].fullmatch(lines[i]) and i + 1 in outside
                  and f['setext_underline'].fullmatch(lines[i + 1]))
        if setext or (f['section_like'].fullmatch(lines[i]) and not exact):
            return {**bad, 'code': 'section-heading'}
    starts = [i for i in outside if f['section'].fullmatch(lines[i])]
    if not starts:
        return {'result': 'absent', 'early': True, 'late': False}
    if len(starts) > 1:
        return {**bad, 'code': 'section-repeated'}
    body = []
    for i in range(starts[0] + 1, len(lines)):
        if i not in inside and f['section_end'].fullmatch(lines[i]):
            break
        if lines[i].strip():
            body.append(lines[i])
    if len(body) < 2:
        return {**bad, 'code': 'answer-missing'}
    one = f['one_way_door'].fullmatch(body[0])
    user = f['user_visible'].fullmatch(body[1])
    if len(body) != 2 or not one or not user:
        return {**bad, 'code': 'answer-line'}
    one_way, visible = one.group(1) == 'yes', user.group(1) != 'no'
    return {'result': 'answered', 'one_way_door': one_way, 'user_visible': visible,
            'release': user.group(1) == 'yes, a release', 'early': one_way, 'late': visible}


def link_kind(url, f):
    """None for an evidence link, else its refusal code."""
    if '\\' in url:
        return 'evidence-link'
    try:
        parts = urlsplit(url)
        parts.port
    except ValueError:
        return 'evidence-link'
    host = (parts.hostname or '').rstrip('.')
    if (parts.scheme.lower() != 'https' or not url[len(parts.scheme):].startswith('://') or '@' in parts.netloc
            or not f['link_host'].fullmatch(host)):
        return 'evidence-link'
    if host in f['uploaded_hosts'] and f['uploaded_path'].fullmatch(parts.path):
        return None
    return 'evidence-code' if host in f['code_hosts'] else None


def read_ask(text, f):
    lines = [line for line in text.split('\n') if line.strip()]
    first = f['ask_opening'].fullmatch(lines[0]) if lines else None
    if not first:
        return {'result': 'invalid', 'code': 'ask-opening'}
    evidence, rest = [], lines[1:]
    while rest and (m := f['ask_evidence'].fullmatch(rest[0])):
        kind = link_kind(m.group(2), f)
        if kind:
            return {'result': 'invalid', 'code': kind}
        evidence.append({'kind': m.group(1), 'url': m.group(2)})
        rest = rest[1:]
    if not evidence:
        return {'result': 'invalid', 'code': 'evidence-missing'}
    look = f['ask_look_for'].fullmatch(rest[0]) if len(rest) == 1 else None
    if not look:
        return {'result': 'invalid', 'code': 'ask-line'}
    return {'result': 'valid', 'pr': int(first.group(1)), 'commit': first.group(2),
            'evidence': evidence, 'look_for': look.group(1)}


def real_date(text):
    try:
        datetime.date.fromisoformat(text)
    except ValueError:
        return False
    return True


def read_record(text, f):
    lines = [line for line in text.split('\n') if line.strip()]
    first = f['record_opening'].fullmatch(lines[0]) if lines else None
    if not first or not real_date(first.group(2)):
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
    spec = read_spec(text_of(HERE / scenario['spec']), f)
    if not scenario['final'] or not spec['late']:
        return {'merge': 'flows'}
    head, authors, deciders = scenario['head'], set(scenario['record_authors']), set(scenario['deciders'])
    asked, newest = False, None
    for comment in scenario['comments']:
        if comment['author'] not in authors:
            continue
        text = text_of(HERE / comment['body'])
        for reading in (read_ask(text, f), read_record(text, f)):
            if reading['result'] != 'valid' or (reading['pr'], reading['commit']) != (head['pr'], head['commit']):
                continue
            if 'evidence' in reading:
                asked = True
            elif asked and reading['decider'] in deciders:
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
                got = READERS[kind](text_of(HERE / name), f)
            if got != want:
                failures.append(f'{name}: expected {json.dumps(want)}, got {json.dumps(got)}')
    for line in failures:
        print(f'FAIL {line}')
    total = len(listed)
    print(f'checkpoints fixtures: {total - len(failures)} of {total} read as expected')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
