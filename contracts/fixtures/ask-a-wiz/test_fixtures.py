"""P1 of spec #1898: the Ask-a-Wiz contract's fixtures hold to its pin.

Run: python3 -I contracts/fixtures/ask-a-wiz/test_fixtures.py
Standard library only. Every value in the fixtures is synthetic.
"""
import copy
import datetime
import hashlib
import json
import pathlib
import re
import unittest

HERE = pathlib.Path(__file__).resolve().parent
CONTRACT = HERE.parent.parent / 'ask-a-wiz.v1.md'
FAKE_KEY = 'fake-openrouter-key'
RAW = ('<', '>', '&', ' ', ' ')
TERMINAL = ('done', 'not_covered', 'refused')
STORE_KEY = re.compile(r'^(cap|salt:[0-9a-f]{64}|visitor:[0-9a-f]{32}:([01][0-9]|2[0-3]))$')
DAY = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def load_pin():
    text = CONTRACT.read_text(encoding='utf-8')
    block = text.split('## The pin', 1)[1].split('```json\n', 1)[1].split('\n```', 1)[0]
    return json.loads(block)


def load(name):
    if not (HERE / f'{name}.json').is_file():
        raise AssertionError(f'missing fixture: {name}.json')
    return json.loads((HERE / f'{name}.json').read_text(encoding='utf-8'))


def visitor_key(salt, ip, hour):
    return f"visitor:{hashlib.sha256(f'{salt}:{ip}'.encode()).hexdigest()[:32]}:{hour}"


def events_of(body):
    """The events of an NDJSON body, or a problem string."""
    if not body.endswith('\n'):
        return 'the body does not end its last line'
    try:
        return [json.loads(line) for line in body[:-1].split('\n')]
    except ValueError:
        return 'a line is not JSON'


def question_of(case):
    try:
        body = json.loads(case['request']['body'])
    except (TypeError, ValueError):
        return None
    if not isinstance(body, dict) or list(body) != ['question'] or not isinstance(body['question'], str):
        return None
    return body['question'].strip()


def outcome(pin, case):
    """What the contract's order of checks gives for this case: a reason, 'off', 'probe' or 'stream'."""
    names, request, settings = pin['names'], case['request'], case['settings']
    if settings.get(names['switch']) != pin['names']['switch_on']:
        return 'off'
    if request['method'] == 'GET':
        return 'probe'
    if not all(settings.get(names[k]) for k in ('secret', 'model')) or not settings.get(names['store']):
        return 'unavailable'
    headers = {k.lower(): v for k, v in request['headers'].items()}
    question = question_of(case)
    if (request['method'] != 'POST' or headers.get('content-type') != pin['request']['content_type']
            or headers.get('origin') != 'https://openwiz.dev' or question is None
            or len(request['body'].encode()) > pin['request']['max_body_bytes'] or not question):
        return 'bad_request'
    if len(question) > pin['request']['max_question_chars']:
        return 'too_long'
    now = datetime.datetime.fromisoformat(case['now'])
    day, hour = now.strftime('%Y-%m-%d'), now.strftime('%H')
    rows = {r['key']: r['count'] for r in case['store'] if r['day'] == day}
    salts = [k[len('salt:'):] for k in rows if k.startswith('salt:')]
    if salts and rows.get(visitor_key(salts[0], headers.get('cf-connecting-ip', ''), hour), 0) \
            >= pin['rate_limit']['per_visitor']:
        return 'rate_limited'
    if case['upstream'] is None and not case.get('passages', True):
        return 'not_covered'
    try:
        cap = int(settings.get(names['daily_cap'], ''))
    except ValueError:
        cap = 0
    if not pin['daily_cap']['min'] <= cap <= pin['daily_cap']['max']:
        cap = 0
    if rows.get('cap', 0) >= cap:
        return 'daily_cap'
    upstream = case['upstream'] or {}
    if upstream.get('fails') and not upstream.get('after_chunks'):
        return 'upstream_error'
    return 'stream'


def problems(pin, case, name):
    out = []
    if case.get('case') != name:
        out.append('case name does not match its file')
    if set(case) - {'case', 'now', 'request', 'settings', 'store', 'upstream', 'passages', 'response'}:
        out.append('unknown case keys')
    response = case['response']
    headers = {k.lower(): v for k, v in response['headers'].items()}
    body = response['body']
    seen = json.dumps(case['response'])
    if FAKE_KEY in seen or 'Bearer' in seen:
        out.append('the key reaches the response')
    for row in case['store']:
        if not DAY.match(row['day']) or not STORE_KEY.match(row['key']) or set(row) != {'day', 'key', 'count'}:
            out.append(f'store row not allowed: {row}')
    expected = outcome(pin, case)
    if expected == 'off':
        if response['status'] != 404 or body is not None:
            out.append('the switch is off but the answer is not an empty 404')
        return out
    if expected == 'probe':
        want = {'schema': pin['schema'], 'enabled': True, 'max_question_chars': pin['request']['max_question_chars']}
        if response['status'] != 200 or json.loads(body or 'null') != want:
            out.append('the probe answer is wrong')
        if headers.get('cache-control') != pin['response']['cache_control']:
            out.append('the probe is cacheable')
        return out
    if headers.get('content-type') != pin['response']['content_type']:
        out.append('wrong content type')
    if headers.get('cache-control') != pin['response']['cache_control']:
        out.append('the response is cacheable')
    if any(ch in body for ch in RAW):
        out.append('the body holds an unescaped character')
    events = events_of(body)
    if isinstance(events, str):
        return out + [events]
    for event in events:
        keys = pin['events'].get(event.get('type'))
        if keys is None or sorted(event) != sorted(keys):
            out.append(f'event has the wrong keys: {event}')
    types = [e.get('type') for e in events]
    if not types or types[-1] not in TERMINAL or any(t in TERMINAL for t in types[:-1]):
        out.append('the stream does not end on exactly one terminal event')
        return out
    last = events[-1]
    if expected in pin['refusals']:
        ref = pin['refusals'][expected]
        if types != ['refused'] or response['status'] != ref['status']:
            out.append(f'expected one {expected} refusal at {ref["status"]}')
        elif last['reason'] != expected or last['message'] != ref['message']:
            out.append('wrong refusal reason or message')
        if response['status'] == 429:
            end = 3600 if expected == 'rate_limited' else 86400
            now = datetime.datetime.fromisoformat(case['now'])
            left = end - ((now.minute * 60 + now.second) if end == 3600 else
                          (now.hour * 3600 + now.minute * 60 + now.second))
            if headers.get('retry-after') != str(left):
                out.append('Retry-After is not the seconds left in the window')
        if (case['upstream'] is not None) != (expected == 'upstream_error'):
            out.append('only an upstream error may follow a model call')
        return out
    if expected == 'not_covered' or types == ['not_covered']:
        nc = pin['not_covered']
        chunks = (case['upstream'] or {}).get('chunks', [])
        if expected != 'not_covered' and not ''.join(chunks).strip().startswith(nc['sentinel']):
            out.append('not covered without the sentinel or a passage-less question')
        if types != ['not_covered'] or response['status'] != 200:
            out.append('the not-covered answer is not a lone event at 200')
        elif last['text'] != nc['text'] or last['links'] != nc['links']:
            out.append('the not-covered text or links differ from the pin')
        return out
    # A model answer: text pieces, then sources and done, or an upstream error mid-answer.
    upstream = case['upstream'] or {}
    pieces = [e['text'] for e in events if e['type'] == 'text']
    if response['status'] != 200 or not pieces or not all(isinstance(p, str) and p for p in pieces):
        out.append('an answer needs status 200 and non-empty text pieces')
    if types[:len(pieces)] != ['text'] * len(pieces):
        out.append('text pieces must come first')
    if pin['not_covered']['sentinel'] in ''.join(pieces):
        out.append('the sentinel reached the visitor')
    if upstream.get('fails'):
        if types[len(pieces):] != ['refused'] or last['reason'] != 'upstream_error' \
                or last['message'] != pin['refusals']['upstream_error']['message']:
            out.append('a failure mid-answer must end on one upstream_error')
        if pieces != upstream.get('chunks', [])[:upstream.get('after_chunks', 0)]:
            out.append('the pieces are not what the fake upstream sent before failing')
        return out
    if types[len(pieces):] != ['sources', 'done']:
        out.append('an answer ends with sources, then done')
        return out
    if ''.join(pieces) != ''.join(upstream.get('chunks', [])):
        out.append('the answer is not what the fake upstream streamed')
    sources = events[-2]['sources']
    urls = [s.get('url') for s in sources]
    if not 1 <= len(sources) <= pin['max_sources'] or len(set(urls)) != len(urls) \
            or any(sorted(s) != ['title', 'url'] for s in sources) \
            or not all(isinstance(u, str) and u.startswith(tuple(pin['source_url_prefixes'])) for u in urls):
        out.append('sources break the rules')
    return out


def index_problems(pin, index):
    out = []
    rules = pin['index']
    if sorted(index) != sorted(rules['keys']) or index.get('schema') != rules['schema']:
        return ['the index has the wrong keys or schema']
    if len(json.dumps(index).encode()) > rules['max_bytes']:
        out.append('the index is too big')
    sources, passages = index['sources'], index['passages']
    urls = [s.get('url') for s in sources]
    if not sources or len(set(urls)) != len(urls):
        out.append('index sources must be one or more, each URL once')
    for s in sources:
        if sorted(s) != ['title', 'url'] or not 1 <= len(s['title']) <= 200 \
                or not s['url'].startswith(tuple(pin['source_url_prefixes'])):
            out.append(f'bad index source: {s}')
    if not passages:
        out.append('the index has no passage')
    for p in passages:
        if sorted(p) != ['source', 'text'] or not isinstance(p['source'], int) \
                or not 0 <= p['source'] < len(sources) \
                or not 1 <= len(p['text']) <= pin['upstream']['max_passage_chars']:
            out.append(f'bad index passage: {str(p)[:60]}')
    return out


class Pin(unittest.TestCase):
    def test_names_jake_uses_are_fixed_and_the_switch_is_off_by_default(self):
        pin = load_pin()
        self.assertEqual(pin['schema'], 'openwiz.ask-a-wiz.v1')
        self.assertFalse(any(pin['authority'].values()), 'the contract grants nothing')
        self.assertEqual(pin['names']['secret'], 'OPENROUTER_API_KEY')
        self.assertEqual(pin['names']['store'], 'ASK_A_WIZ_COUNTERS')
        self.assertEqual((pin['names']['switch'], pin['names']['switch_on']), ('ASK_A_WIZ', 'on'))
        self.assertEqual(load('off')['settings'].get('ASK_A_WIZ'), None, 'off is the unset switch')

    def test_every_refusal_has_a_case(self):
        pin = load_pin()
        covered = {outcome(pin, load(n)) for n in pin['fixtures']}
        for reason in [*pin['refusals'], 'not_covered', 'off', 'probe', 'stream']:
            self.assertIn(reason, covered, f'no fixture gives {reason}')


class Fixtures(unittest.TestCase):
    def test_every_case_holds_to_the_pin(self):
        pin = load_pin()
        for name in pin['fixtures']:
            with self.subTest(case=name):
                self.assertEqual(problems(pin, load(name), name), [])

    def test_the_index_fixture_is_valid(self):
        self.assertEqual(index_problems(load_pin(), load('index')), [])

    def test_the_store_holds_only_counters(self):
        store = load('store')
        self.assertTrue(store['rows'])
        for row in store['rows']:
            self.assertEqual(sorted(row), ['count', 'day', 'key'])
            self.assertRegex(row['key'], STORE_KEY)
            self.assertRegex(row['day'], DAY)
            self.assertEqual(row['count'] == 0, row['key'].startswith('salt:'), row)

    def test_nothing_holds_a_real_key_or_private_value(self):
        for path in sorted(HERE.glob('*.json')) + [CONTRACT]:
            text = path.read_text(encoding='utf-8')
            self.assertNotRegex(text, r'sk-or-[A-Za-z0-9-]{8,}', path.name)
            self.assertNotRegex(text, r'thr_[A-Za-z0-9]', path.name)


class TheCheckCatches(unittest.TestCase):
    """Each planted break must be found, so a passing case means something."""

    def broken(self, name, change):
        pin = load_pin()
        case = copy.deepcopy(load(name))
        change(case)
        return problems(pin, case, name)

    def test_planted_breaks_are_found(self):
        msg = load_pin()['not_covered']
        plants = {
            'a raw < in the answer': ('answer-escaped', lambda c: c['response'].update(
                body=c['response']['body'].replace('\\u003c', '<', 1))),
            'the key in a refusal': ('upstream-error', lambda c: c['response']['headers'].update(
                {'X-Debug': FAKE_KEY})),
            'an answer without done': ('answer', lambda c: c['response'].update(
                body=c['response']['body'].rsplit('{"type":"done"}', 1)[0])),
            'a changed not-covered link': ('not-covered', lambda c: c['response'].update(
                body=c['response']['body'].replace('team/#book', 'team/'))),
            'the sentinel shown': ('answer', lambda c: c['response'].update(
                body=c['response']['body'].replace('"text":"', '"text":"' + msg['sentinel'], 1))),
            'too long answered': ('too-long', lambda c: c['response'].update(status=200)),
            'a wrong Retry-After': ('rate-limited', lambda c: c['response']['headers'].update(
                {'Retry-After': '60'})),
            'cap reached but the model called': ('daily-cap', lambda c: c.update(upstream={'chunks': ['x']})),
            'an IP in the store': ('rate-limited', lambda c: c['store'].append(
                {'day': c['store'][0]['day'], 'key': 'visitor:192.0.2.1:00', 'count': 1})),
            'switch off but answered': ('off', lambda c: c['response'].update(body='{"type":"done"}\n')),
        }
        for what, (name, change) in plants.items():
            with self.subTest(plant=what):
                self.assertNotEqual(self.broken(name, change), [], what)

    def test_a_bad_index_is_found(self):
        index = copy.deepcopy(load('index'))
        index['sources'][0]['url'] = 'https://example.invalid/private'
        self.assertNotEqual(index_problems(load_pin(), index), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
