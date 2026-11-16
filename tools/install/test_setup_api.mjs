// Read-only setup contract at the actual web API client seam; no browser.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readSetup } from '../../apps/web/src/api.ts';

const example = () => ({ schema: 'openwiz.setup.v1', ready: false,
  components: ['cloudroom', 'harness', 'personal_github', 'github_app', 'project', 'remote_access']
    .map((id) => ({ id, state: 'unknown', reason: 'Synthetic unverified prerequisite.', next: 'Ask your installing agent to verify it.' })),
  engine: 'unselected', cost: { provenance: 'unknown', credits: null, window_s: null, monthly_projection: null, free_allowance: null, reason: 'Cloud Credits have not been measured.' }, operations: [] });
async function read(body) {
  let calls = 0;
  const result = await readSetup(async (url, init) => {
    calls++;
    assert.equal(url, '/api/v1/setup');
    assert.equal(init.method, 'GET');
    assert.equal(init.body, undefined);
    assert.equal(init.cache, 'no-store');
    return { type: 'basic', status: 200, headers: { get: () => 'application/json' }, text: async () => body };
  }, new AbortController().signal);
  assert.equal(calls, 1);
  return result;
}

test('setup reader accepts independent unknowns and refuses malformed or falsely ready reports', async () => {
  assert.equal((await read(JSON.stringify(example()))).kind, 'ok');
  const wrong = [
    (v) => { v.extra = true; },
    (v) => { v.components[0].state = { verified: null }; },
    (v) => { v.components[0].state = 'ready'; },
    (v) => { v.components[0].id = 'harness'; },
    (v) => { delete v.components[0].next; },
    (v) => { v.cost.credits = 0; },
    (v) => { v.cost.provenance = 'measured'; v.cost.window_s = 0; },
    (v) => { v.ready = true; },
    // #873: setup has no engine step, so an engine row is unreadable.
    (v) => { v.components.push({ id: 'engine', state: 'missing', reason: 'Synthetic engine row.', next: 'Synthetic.' }); },
  ];
  for (const mutate of wrong) {
    const value = example();
    mutate(value);
    assert.equal((await read(JSON.stringify(value))).kind, 'error', JSON.stringify(value));
  }
  for (const text of [JSON.stringify(example()).replace('"ready":false', '"ready":false,"ready":false'),
    JSON.stringify(example()).replace('"ready":false', '"ready":false,"\\u0072eady":false'), '[]', '{']) {
    assert.equal((await read(text)).kind, 'error', text);
  }
});

// #633 (setup.v1's 0.0.16 expansion): catches the page refusing the server's
// identity field (an error instead of the acting login), or accepting a
// report that shows ready without the App when the owner did not skip it.
const skip = () => ({ selected: 'personal_login', app_choice: 'skip', acting_login: 'synthetic-owner' });
const readyWithoutApp = (identity) => {
  const value = example();
  value.ready = true;
  value.engine = 'local';
  for (const c of value.components) c.state = c.id === 'github_app' ? 'missing' : c.id === 'remote_access' ? 'unknown' : 'verified';
  if (identity !== undefined) value.identity = identity;
  return value;
};

test('setup reader takes the optional identity and its revised ready rule, and nothing looser', async () => {
  const withSkip = { ...example(), identity: skip() };
  const read1 = await read(JSON.stringify(withSkip));
  assert.equal(read1.kind, 'ok');
  assert.deepEqual(read1.envelope.identity, skip());
  assert.equal((await read(JSON.stringify(example()))).envelope.identity, undefined, 'an old response has no identity');
  assert.equal((await read(JSON.stringify(readyWithoutApp(skip())))).kind, 'ok', 'the explicit skip carries the identity part');
  for (const ok of [{ selected: 'unselected', app_choice: 'undecided', acting_login: null },
    { selected: 'app', app_choice: 'reuse', acting_login: null }]) {
    assert.equal((await read(JSON.stringify({ ...example(), identity: ok }))).kind, 'ok', JSON.stringify(ok));
  }
  const refused = [
    readyWithoutApp(undefined),                                                       // no choice: the App rule
    readyWithoutApp({ selected: 'app', app_choice: 'create', acting_login: null }),
    readyWithoutApp({ selected: 'unselected', app_choice: 'skip', acting_login: null }),
    { ...readyWithoutApp(skip()), components: readyWithoutApp(skip()).components.map((c) => c.id === 'personal_github' ? { ...c, state: 'refused' } : c) },
    { ...example(), identity: { ...skip(), app_choice: 'create' } },
    { ...example(), identity: { ...skip(), acting_login: null } },
    { ...example(), identity: { ...skip(), acting_login: 'synthetic/owner' } },
    { ...example(), identity: { ...skip(), acting_login: 'x'.repeat(40) } },
    { ...example(), identity: { ...skip(), extra: true } },
    { ...example(), identity: { selected: 'personal_login', app_choice: 'skip' } },
    { ...example(), identity: { ...skip(), selected: 'fallback' } },
    { ...example(), identity: null },
    { ...example(), identity: ['personal_login', 'skip', 'synthetic-owner'] },
  ];
  for (const value of refused) assert.equal((await read(JSON.stringify(value))).kind, 'error', JSON.stringify(value));
});
