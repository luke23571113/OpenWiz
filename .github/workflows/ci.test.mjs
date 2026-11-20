// Fixture model of GitHub's documented single-pending concurrency policy.
// This checks the committed expressions, not GitHub's live scheduler.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { runInNewContext } from 'node:vm';

const workflow = readFileSync(new URL('./ci.yml', import.meta.url), 'utf8');
const block = workflow.match(/^concurrency:\n((?:[ \t].*\n|\n)*)/m)?.[1];
assert.ok(block, 'workflow-level concurrency exists');
const group = block.match(/^  group: (.+)$/m)?.[1];
const cancel = block.match(/^  cancel-in-progress: \$\{\{ (.+) \}\}$/m)?.[1];
assert.ok(group);
assert.ok(cancel);

function policy(event, ref = 'refs/heads/main', number) {
  const github = { event_name: event, ref, event: { pull_request: { number } } };
  return {
    group: group.replace(/\$\{\{ (.+?) \}\}/g, (_, expression) =>
      runInNewContext(expression, { github }, { timeout: 100 })),
    cancel: runInNewContext(cancel, { github }, { timeout: 100 }),
  };
}

function scheduler() {
  const groups = new Map();
  const cancelled = [];
  return {
    groups, cancelled,
    enqueue(id, policy) {
      const state = groups.get(policy.group) ?? { running: null, pending: null };
      if (state.pending) cancelled.push(state.pending);
      state.pending = null;
      if (policy.cancel && state.running) {
        cancelled.push(state.running);
        state.running = null;
      }
      if (state.running) state.pending = id;
      else state.running = id;
      groups.set(policy.group, state);
    },
  };
}

test('The Rust lane reads the plan\'s planted output', () => {
  const changes = workflow.match(/^  changes:\n((?:    .*\n|\n)*)/m)?.[1];
  assert.match(changes, /^      planted: \$\{\{ steps\.plan\.outputs\.planted \}\}$/m);
  for (const lane of ['rust']) {
    const job = workflow.match(new RegExp(`^  ${lane}:\\n((?:    .*\\n|\\n)*)`, 'm'))?.[1];
    assert.ok(job, `${lane} job exists`);
    assert.match(job, /^    needs: changes$/m);
  }
});

test('nightly remains admitted when later main pushes arrive', () => {
  const queue = scheduler();
  queue.enqueue('push-running', policy('push'));
  queue.enqueue('prior-nightly', policy('schedule'));
  queue.enqueue('nightly', policy('schedule'));
  queue.enqueue('push-pending', policy('push'));
  queue.enqueue('push-latest', policy('push'));
  assert.notEqual(policy('schedule').group, policy('push').group);
  assert.ok(!queue.cancelled.includes('nightly'), 'nightly was replaced by a push');
  assert.deepEqual(queue.groups.get(policy('schedule').group), { running: 'prior-nightly', pending: 'nightly' });
});

test('new main pushes cancel obsolete main pushes without cancelling other refs', () => {
  const queue = scheduler();
  for (const id of ['running', 'pending', 'latest']) queue.enqueue(id, policy('push'));
  assert.deepEqual(queue.groups.get(policy('push').group), { running: 'latest', pending: null });
  assert.deepEqual(queue.cancelled, ['running', 'pending']);
  assert.equal(policy('push', 'refs/heads/release-synthetic').cancel, false);
  assert.equal(policy('schedule').cancel, false);
});

test('PR updates cancel obsolete work for that PR only', () => {
  const queue = scheduler();
  queue.enqueue('pr-7-old', policy('pull_request', 'refs/pull/7/merge', 7));
  queue.enqueue('pr-8', policy('pull_request', 'refs/pull/8/merge', 8));
  queue.enqueue('pr-7-new', policy('pull_request', 'refs/pull/7/merge', 7));
  assert.deepEqual(queue.cancelled, ['pr-7-old']);
  assert.equal(queue.groups.get(policy('pull_request', 'refs/pull/8/merge', 8).group).running, 'pr-8');
});

test('merge groups retain independent groups and do not cancel running work', () => {
  const first = policy('merge_group', 'refs/heads/gh-readonly-queue/main/pr-7');
  const second = policy('merge_group', 'refs/heads/gh-readonly-queue/main/pr-8');
  assert.notEqual(first.group, second.group);
  assert.notEqual(first.group, policy('schedule').group);
  assert.equal(first.cancel, false);
});

// #744: which jobs run for each event, simulated over the committed job graph
// with GitHub's documented job rules: a job runs only when its needs finished
// and its `if:` holds, and an `if:` without a status function implies
// success(), which a skipped need fails. A full plan's outputs feed the lanes.
// catches: a condition that drops a required check (or the full suite) from
// pull_request or merge_group, where a skipped required check passes silently,
// and a main push that ignores the signed-map age decision.
function jobGraph(source) {
  const body = source.slice(source.indexOf('\njobs:\n') + 7);
  return new Map([...body.matchAll(/^  ([a-z][a-z0-9-]*):\n((?:    .*\n|\n)*)/gm)].map(([, name, block]) => {
    const needs = block.match(/^    needs: (?:\[(.*)\]|(.*))$/m);
    const condition = block.match(/^    if: (.+)$/m)?.[1].replace(/^\$\{\{ (.*) \}\}$/, '$1');
    return [name, { needs: needs ? (needs[1] ?? needs[2]).split(', ') : [], condition }];
  }));
}

function simulate(source, event_name, outputs = {}, initialResults = {}) {
  const graph = jobGraph(source);
  const results = { ...initialResults };
  const github = { event_name, ref: 'refs/heads/main', event: { merge_group: { base_ref: 'refs/heads/main' } } };
  const settle = (name) => {
    if (name in results) return results[name];
    const job = graph.get(name);
    assert.ok(job, `job ${name} exists`);
    // GitHub exposes a skipped step's missing output as an empty string.
    const needs = Object.fromEntries(job.needs.map((n) => [n, { result: settle(n),
      outputs: new Proxy(outputs[n] ?? {}, { get: (values, key) => values[key] ?? '' }),
    }]));
    const done = Object.values(needs).map((n) => n.result);
    const success = () => done.every((r) => r === 'success');
    const condition = job.condition ?? 'success()';
    const status = /\b(?:always|success|failure|cancelled)\(\)/.test(condition);
    // GitHub reads hyphenated names with a dot; JavaScript needs brackets.
    const code = (status ? condition : `success() && (${condition})`).replace(/\.([a-z]+(?:-[a-z]+)+)/g, "['$1']");
    const runs = runInNewContext(code, {
      github, needs, always: () => true, cancelled: () => false, success,
      // GitHub's contains(): a case-insensitive substring test on strings.
      contains: (a, b) => String(a).toLowerCase().includes(String(b).toLowerCase()),
      failure: () => done.includes('failure'),
    }, { timeout: 100 });
    return (results[name] = runs ? 'success' : 'skipped');
  };
  for (const name of graph.keys()) settle(name);
  return Object.keys(results).filter((name) => results[name] === 'success').sort();
}

// A full plan (every reason forces one on these events): every lane.
const FULL_PLAN = { changes: { rust: 'true', release: 'true', skills: '["image","launch-fleet"]',
  'skill-jobs': '["image"]', trace: 'false', planted: 'false' } };
// #743: launch-fleet and release retain their sharded jobs on a full run.
const FULL_SUITE = ['always', 'changes', 'ci', 'launch-fleet', 'release', 'rust', 'skills', 'web-test'];

test('PR, nightly and merge-group coverage stays full; main pushes follow the map-age decision', () => {
  // #1418: the owned-paths check runs beside the suite on pull requests only.
  assert.deepEqual(simulate(workflow, 'pull_request', FULL_PLAN), [...FULL_SUITE, 'owned-paths'].sort(), 'pull_request');
  assert.deepEqual(simulate(workflow, 'merge_group', FULL_PLAN), FULL_SUITE, 'merge_group');
  assert.deepEqual(simulate(workflow, 'schedule', FULL_PLAN), FULL_SUITE, 'nightly');
  assert.deepEqual(simulate(workflow, 'push', { changes: {} }), ['changes', 'main-light'], 'fresh map: no plan or heavy lanes');

  // The light check is format (privacy runs in privacy.yml on every main push).
  const light = workflow.match(/^  main-light:\n((?:    .*\n|\n)*)/m)?.[1] ?? '';
  assert.match(light, /^          cargo fmt --check$/m);
  const privacy = readFileSync(new URL('./privacy.yml', import.meta.url), 'utf8');
  for (const event of ['pull_request', 'merge_group', 'push']) {
    assert.deepEqual(simulate(privacy, event), ['privacy'], `privacy on ${event}`);
    assert.match(privacy.match(/^on:\n((?:  .*\n|\n)*)/m)?.[1] ?? '', new RegExp(`^  ${event}:`, 'm'));
  }
  // The simulator itself: a required check gated to pull requests only is
  // dropped from merge groups, and one gated off pushes stays on both.
  const ci = /^  ci:\n    needs: (.*)\n    if: .*$/m;
  const dropped = workflow.replace(ci, "  ci:\n    needs: $1\n    if: ${{ always() && github.event_name == 'pull_request' }}");
  assert.ok(!simulate(dropped, 'merge_group', FULL_PLAN).includes('ci'));
  const kept = workflow.replace(ci, "  ci:\n    needs: $1\n    if: ${{ always() && github.event_name != 'push' }}");
  assert.ok(simulate(kept, 'merge_group', FULL_PLAN).includes('ci'));
});

test('an unreadable main-map gate still schedules the final failure check', () => {
  // catches: a failed age read being reported as a successful light push.
  const ran = simulate(workflow, 'push', { changes: {} }, { changes: 'failure' });
  assert.deepEqual(ran, ['ci', 'main-light', 'web-test']);
});

test('main pushes with an old map run the traced full plan and sign; nightly signing stays unconditional', () => {
  const traced = { changes: { ...FULL_PLAN.changes, trace: 'true' } };
  assert.deepEqual(simulate(workflow, 'push', traced), [...FULL_SUITE, 'main-light'].sort(), '121-minute map: traced full run signs');
  assert.deepEqual(simulate(workflow, 'schedule', traced), [...FULL_SUITE].sort(), 'nightly still signs');
});
