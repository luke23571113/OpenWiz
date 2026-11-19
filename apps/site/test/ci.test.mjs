import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

test('R1: CI runs separate site and release jobs with the pinned Python fallback', () => {
  const workflow = readFileSync(new URL('../../../.github/workflows/ci.yml', import.meta.url), 'utf8');
  const runner = readFileSync(new URL('../../../.github/actions/docs-only/run.py', import.meta.url), 'utf8');
  const fallback = readFileSync(new URL('../../../.github/actions/docs-only/python.sh', import.meta.url), 'utf8');
  const job = name => workflow.split(/^  (?=[a-z][a-z-]*:)/m).find(block => block.startsWith(`${name}:\n`));
  for (const [name, title] of [['site', 'Build and test the public static site'], ['release', 'The release proofs']]) {
    const block = job(name);
    assert.ok(block.includes(`needs.changes.outputs.${name} == 'true'`));
    assert.ok(block.includes(`- name: ${title}\n`));
    assert.ok(block.includes(`run.py execute "$RUNNER_TEMP/ci-plan" ${name}`));
    assert.ok(block.includes('run: sh .github/actions/docs-only/python.sh'));
  }
  // Commands moved to the plan executor; preserve every previous obligation.
  for (const command of ["'site:build': ['npm', 'run', 'build']", "'site:test': ['npm', 'test']",
    "'site:ci': ['npm', 'run', 'test:ci']", "'release:test': ['python3', 'tools/release/test.py']"]) {
    assert.ok(runner.includes(command), `the plan executor retains ${command}`);
  }
  assert.ok(runner.includes("cwd='apps/site' if test.startswith('site:') else None"));
  for (const line of [
    'python3 --version',
    'x86_64) sum=df15fe60d3ff55bf9dcf25824b5572756bb8816ff93865a273d3301d7066a8b7 ;;',
    'aarch64) sum=578d9da1983463ffb0c8c98ab0da2f18177f44069328eb0af847860c1eb05c3e ;;',
    'echo "$sum  $RUNNER_TEMP/python.tar.gz" | sha256sum -c -',
    'export PATH="$python/bin:$PATH"',
  ]) assert.ok(fallback.includes(line), `CI retains ${line}`);
  assert.ok(fallback.includes('/20261026/cpython-3.13.18+20261026-$(uname -m)-unknown-linux-gnu-install_only_stripped.tar.gz'));
});
