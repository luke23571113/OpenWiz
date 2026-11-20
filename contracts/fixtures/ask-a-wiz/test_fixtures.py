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
TERMINAL = ('done', 'not_covered', 'refused')
STORE_KEY = re.compile(r'^(cap|visitor:[0-9a-f]{32}:([01][0-9]|2[0-3]))$')
SALT = re.compile(r'^[0-9a-f]{64}$')
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


def sent_passages(pin, case):
    """The ranked passages that fit the call, in order: stop at the first that makes too many or too big."""
    lim, prompt = pin['limits'], pin['prompt']
    tail = prompt['question'].format(question=question_of(case))
    sent, blocks = [], ''
    for p in case.get('retrieved') or []:
        block = prompt['passage'].format(n=len(sent) + 1, url=p['source']['url'], text=p['text'])
        size = len((prompt['system'] + blocks + block + tail).encode())
        if len(sent) == lim['max_passages'] or size > lim['max_prompt_bytes']:
            break
        sent.append(p)
        blocks += block
    return sent, blocks + tail


def expected_request(pin, case):
    sent, user = sent_passages(pin, case)
    prices = {'prompt': price(pin, case['settings'], 'max_prompt_price'),
              'completion': price(pin, case['settings'], 'max_completion_price')}
    return {'model': case['settings'][pin['names']['model']], 'stream': True,
            'provider': {'max_price': prices, **pin['upstream']['provider']},
            'max_tokens': pin['limits']['max_output_tokens'], 'temperature': pin['upstream']['temperature'],
            'messages': [{'role': 'system', 'content': pin['prompt']['system']}, {'role': 'user', 'content': user}]}


def fitting(pin, chunks):
    """The answer pieces passed on: whole pieces while the text stays within max_answer_bytes."""
    out, total = [], 0
    for chunk in chunks:
        total += len(chunk.encode())
        if total > pin['limits']['max_answer_bytes']:
            break
        out.append(chunk)
    return out


def price(pin, settings, name):
    """A max price setting as a number, or None when unset or invalid (which fails closed)."""
    value = settings.get(pin['names'][name])
    if not isinstance(value, str) or not re.fullmatch(pin['prices']['pattern'], value):
        return None
    number = float(value)
    return number if pin['prices']['min_exclusive'] < number <= pin['prices']['max'] else None


def utc(text):
    return datetime.datetime.fromisoformat(text)


def run(pin, case):
    """The contract's order of checks on a fake store: (outcome, store after, the clock a 429 counts from)."""
    names, request, settings = pin['names'], case['request'], case['settings']
    store = copy.deepcopy(case['store'])
    now = utc(case['now'])
    if settings.get(names['switch']) != names['switch_on']:
        return 'off', store, now
    if request['method'] == 'GET':
        return 'probe', store, now
    if not all(settings.get(names[k]) for k in ('secret', 'model', 'store')) \
            or price(pin, settings, 'max_prompt_price') is None or price(pin, settings, 'max_completion_price') is None:
        return 'unavailable', store, now
    headers = {k.lower(): v for k, v in request['headers'].items()}
    question = question_of(case)
    if (request['method'] != 'POST' or headers.get('content-type') != pin['request']['content_type']
            or headers.get('origin') != 'https://openwiz.dev' or question is None
            or len(request['body'].encode()) > pin['request']['max_body_bytes'] or not question):
        return 'bad_request', store, now
    if len(question) > pin['request']['max_question_chars']:
        return 'too_long', store, now
    if case.get('store_fails'):
        return 'unavailable', store, now  # every store operation fails: nothing changes, nothing is sent

    def first_write(day):  # every write first deletes earlier days' rows
        for table in ('salts', 'counters'):
            store[table] = [r for r in store[table] if r['day'] >= day]

    def count(day, key, limit):  # the conditional update: add one only below the limit
        first_write(day)
        row = next((r for r in store['counters'] if r['day'] == day and r['key'] == key), None)
        if row is None:
            row = {'day': day, 'key': key, 'count': 0}
            store['counters'].append(row)
        if row['count'] >= limit:
            return False
        row['count'] += 1
        return True

    day, hour = now.strftime('%Y-%m-%d'), now.strftime('%H')
    first_write(day)
    if not any(r['day'] == day for r in store['salts']):  # INSERT ... ON CONFLICT (day) DO NOTHING
        store['salts'].append({'day': day, 'salt': case.get('rival_salt') or case['new_salt']})
    salt = next(r['salt'] for r in store['salts'] if r['day'] == day)  # then every writer reads the one salt
    if not count(day, visitor_key(salt, headers.get('cf-connecting-ip', ''), hour), pin['rate_limit']['per_visitor']):
        return 'rate_limited', store, now
    if case['upstream'] is None and case.get('retrieved') == []:
        return 'not_covered', store, now
    try:
        cap = int(settings.get(names['daily_cap'], ''))
    except ValueError:
        cap = 0
    if not pin['daily_cap']['min'] <= cap <= pin['daily_cap']['max']:
        cap = 0
    if not count(day, 'cap', cap):
        return 'daily_cap', store, now
    sent = utc(case.get('dispatch_at', case['now']))  # the day changed before dispatch: reserve on the new day
    if sent.strftime('%Y-%m-%d') != day and not count(sent.strftime('%Y-%m-%d'), 'cap', cap):
        return 'daily_cap', store, sent
    upstream = case['upstream'] or {}
    if upstream.get('fails') and not upstream.get('after_chunks') or not fitting(pin, upstream.get('chunks', [])):
        return 'upstream_error', store, sent
    return 'stream', store, sent


def outcome(pin, case):
    return run(pin, case)[0]


def canon(store):
    return {k: sorted(json.dumps(r, sort_keys=True) for r in v) for k, v in store.items()}


def store_problems(store):
    if not isinstance(store, dict) or sorted(store) != ['counters', 'salts']:
        return ['the store is not just its counters and salts']
    out = [f'counter row not allowed: {r}' for r in store['counters'] if sorted(r) != ['count', 'day', 'key']
           or not DAY.match(r['day']) or not STORE_KEY.match(r['key']) or not isinstance(r['count'], int)]
    days = [r.get('day') for r in store['salts']]
    out += [f'salt row not allowed: {r}' for r in store['salts'] if sorted(r) != ['day', 'salt']
            or not DAY.match(r['day']) or not SALT.match(r['salt'])]
    return out + (['two salts for one day'] if len(set(days)) != len(days) else [])


def problems(pin, case, name):
    out = []
    if case.get('case') != name:
        out.append('case name does not match its file')
    if set(case) - {'case', 'now', 'request', 'settings', 'store', 'store_after', 'upstream', 'retrieved', 'response',
                    'new_salt', 'rival_salt', 'dispatch_at', 'store_fails'}:
        out.append('unknown case keys')
    response = case['response']
    headers = {k.lower(): v for k, v in response['headers'].items()}
    body = response['body']
    seen = json.dumps(case['response'])
    if FAKE_KEY in seen or 'Bearer' in seen:
        out.append('the key reaches the response')
    shape = store_problems(case['store']) + store_problems(case.get('store_after'))
    if shape:
        return out + shape
    expected, after, clock = run(pin, case)
    if canon(case['store_after']) != canon(after):
        out.append('the store after is not what the order of checks writes')
    if expected in ('off', 'probe') and case['upstream'] is not None:
        out.append('a call went upstream while off or on a probe')
    if case['upstream'] is not None and case['upstream'].get('request') != expected_request(pin, case):
        out.append('the model call is not the bounded request the contract builds')
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
        if headers.get('content-type') != 'application/json':
            out.append('the probe is not JSON')
        return out
    if headers.get('content-type') != pin['response']['content_type']:
        out.append('wrong content type')
    if headers.get('cache-control') != pin['response']['cache_control']:
        out.append('the response is cacheable')
    if any(ch in body for ch in pin['response']['escaped']):
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
            left = end - ((clock.minute * 60 + clock.second) if end == 3600 else
                          (clock.hour * 3600 + clock.minute * 60 + clock.second))
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
    chunks = upstream.get('chunks', [])
    allowed = chunks[:upstream.get('after_chunks', 0)] if upstream.get('fails') else fitting(pin, chunks)
    if pieces != allowed:
        out.append('the pieces are not the ones the fake upstream sent that fit')
    if upstream.get('fails') or allowed != chunks:
        if types[len(pieces):] != ['refused'] or last['reason'] != 'upstream_error' \
                or last['message'] != pin['refusals']['upstream_error']['message']:
            out.append('a failure or an overflow mid-answer must end on one upstream_error')
        return out
    if types[len(pieces):] != ['sources', 'done']:
        out.append('an answer ends with sources, then done')
        return out
    sources = events[-2]['sources']
    urls = [s.get('url') for s in sources]
    used = [p['source'] for p in sent_passages(pin, case)[0]]
    if sources != [x for i, x in enumerate(used) if x not in used[:i]]:
        out.append('sources are not the sent passages\' sources, each once, in order')
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
        if sorted(s) != ['title', 'url'] or not 1 <= len(s['title']) <= 200 or not 1 <= len(s['url']) <= 200 \
                or not s['url'].startswith(tuple(pin['source_url_prefixes'])):
            out.append(f'bad index source: {s}')
    if not passages:
        out.append('the index has no passage')
    for p in passages:
        if sorted(p) != ['source', 'text'] or not isinstance(p['source'], int) \
                or not 0 <= p['source'] < len(sources) \
                or not 1 <= len(p['text']) <= pin['limits']['max_passage_chars']:
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

    def test_one_call_is_bounded_so_the_cap_bounds_spend(self):
        pin = load_pin()
        lim, prompt = pin['limits'], pin['prompt']
        # The largest call: the longest question (4 bytes a code point), one longest passage with a 200-character URL.
        question = prompt['question'].format(question='\U0001F600' * pin['request']['max_question_chars'])
        passage = prompt['passage'].format(n=1, url='u' * 200, text='\U0001F600' * lim['max_passage_chars'])
        self.assertLessEqual(len((prompt['system'] + passage + question).encode()), lim['max_prompt_bytes'],
                             'the best passage must always fit')
        self.assertEqual(lim['max_prompt_tokens'], lim['max_prompt_bytes'] + lim['framing_tokens'],
                         'one token per byte at most, plus the framing margin')
        self.assertEqual(pin['spend']['per_call'], '(max_prompt_tokens * ASK_A_WIZ_MAX_PROMPT_PRICE'
                         ' + max_output_tokens * ASK_A_WIZ_MAX_COMPLETION_PRICE) / 1000000')
        self.assertEqual(pin['upstream']['retries'], 0, 'every attempt is one counted call')
        self.assertEqual(pin['spend']['per_day'], 'ASK_A_WIZ_DAILY_CAP * per_call')

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
        store = {k: v for k, v in load('store').items() if k != 'note'}
        self.assertTrue(store['salts'] and store['counters'])
        self.assertEqual(store_problems(store), [])

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
            'an IP in the store': ('rate-limited', lambda c: c['store_after']['counters'].append(
                {'day': c['store']['counters'][0]['day'], 'key': 'visitor:192.0.2.1:00', 'count': 1})),
            'no max price on the call': ('answer', lambda c: c['upstream']['request'].pop('provider')),
            'a call sent while off': ('off-not-exact', lambda c: c.update(
                upstream={'request': expected_request(load_pin(), c), 'chunks': ['x']})),
            'a call sent on a probe': ('probe-on', lambda c: c.update(upstream={'chunks': []})),
            'the old day pays after midnight': ('midnight-cap', lambda c: c.pop('dispatch_at')),
            'its own salt, not the stored one': ('first-write-race', lambda c: c.pop('rival_salt')),
            'a failed store still answered': ('store-error', lambda c: c.pop('store_fails')),
            'max_tokens raised': ('answer', lambda c: c['upstream']['request'].update(max_tokens=4000)),
            'a seventh passage sent': ('answer-trimmed-count', lambda c: c['upstream']['request']['messages'][1].update(
                content='Passage 7 from x:\nx\n\n' + c['upstream']['request']['messages'][1]['content'])),
            'skipping a too-big passage for a smaller one': ('answer-trimmed-bytes', lambda c: c['retrieved'].pop(
                len(sent_passages(load_pin(), c)[0]))),
            'an overflowing answer passed on': ('answer-overflow', lambda c: c['response'].update(body=''.join(
                json.dumps({'type': 'text', 'text': x}, separators=(',', ':')) + '\n'
                for x in c['upstream']['chunks']) + '{"type":"done"}\n')),
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
