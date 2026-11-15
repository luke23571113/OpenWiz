// #633: GitHub browser sign-in and the explicit App skip, on the real setup
// tools (setup.py, github_login.py, store.py), server and page. Recording
// fakes only: `gh` is a synthetic script answering from a scenario file and
// logging each call; no browser sign-in, account or App is touched.
//
// catches: the page showing a skipped App as verified or offering nothing
// after sign-in; the acting login going unnamed or lost on reload; another
// signed-in account counted as the chosen one; and the read-only setup GET
// calling gh or writing state.
import assert from 'node:assert/strict';
import { execFileSync, spawn } from 'node:child_process';
import { chmodSync, copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { createServer as createNetServer } from 'node:net';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { DESKTOP, PHONE, launchBrowser, openPage, waitFor } from '../support/browser.mjs';
import { OUT_DIR, REPO_DIR, RESULTS_DIR } from '../support/paths.mjs';
import { buildBinaries } from '../support/rust.mjs';

const SERVER = join(REPO_DIR, 'target/debug/examples/openwiz-server');
const REPOSITORY = 'synthetic-owner/synthetic-consumer';
const FAKE_GH = `import json, os, sys
from pathlib import Path
here = Path(os.environ['SYNTHETIC_GH_DIR'])
scenario = json.loads((here / 'scenario.json').read_text())
with open(here / 'calls.log', 'a') as log:
    log.write(' '.join(sys.argv[1:]) + '\\n')
args = sys.argv[1:]
if args[:2] == ['auth', 'login']:
    if scenario['login'] == 'approve':
        scenario['account'] = scenario['approve_as']
        (here / 'scenario.json').write_text(json.dumps(scenario))
        sys.exit(0)
    sys.exit(1)
account = scenario['account']
if account is None:
    sys.exit(4)
if args == ['api', 'user']:
    print(json.dumps({'login': account, 'type': 'User'}))
    sys.exit(0)
if len(args) == 2 and args[1] == 'repos/${REPOSITORY}':
    print(json.dumps({'full_name': '${REPOSITORY}', 'permissions': {'push': scenario['push'].get(account, False)}}))
    sys.exit(0)
sys.exit(1)
`;

async function freePort() {
  const socket = createNetServer();
  await new Promise((resolve, reject) => { socket.once('error', reject); socket.listen(0, '127.0.0.1', resolve); });
  const port = socket.address().port;
  await new Promise((resolve) => socket.close(resolve));
  return port;
}

test('#633: browser sign-in, the explicit App skip and the acting login, at phone and desktop widths', async () => {
  buildBinaries();
  const root = mkdtempSync(join(tmpdir(), 'openwiz-github-login-page-'));
  chmodSync(root, 0o700);
  // The collector's layout: the three setup files, outside the repository.
  const runtime = join(root, 'build/runtime/setup');
  mkdirSync(runtime, { recursive: true });
  for (const name of ['setup.py', 'store.py', 'github_login.py']) copyFileSync(join(REPO_DIR, 'tools/install/setup', name), join(runtime, name));
  const ghDir = join(root, 'gh');
  mkdirSync(ghDir);
  writeFileSync(join(ghDir, 'gh'), `#!/usr/bin/env -S python3 -I\n${FAKE_GH}`);
  chmodSync(join(ghDir, 'gh'), 0o700);
  const scenario = (values) => writeFileSync(join(ghDir, 'scenario.json'), JSON.stringify(values));
  scenario({ account: null, login: 'cancel', approve_as: 'synthetic-owner', push: { 'synthetic-owner': true, 'synthetic-other': true } });
  const calls = () => existsSync(join(ghDir, 'calls.log')) ? readFileSync(join(ghDir, 'calls.log'), 'utf8').split('\n').filter(Boolean) : [];
  const state = join(root, 'state');
  mkdirSync(state, { mode: 0o700 });
  const env = { PATH: `${ghDir}:/usr/bin:/bin`, HOME: root, SYNTHETIC_GH_DIR: ghDir };
  const tool = (file, args) => JSON.parse(execFileSync('python3', ['-I', '-B', join(runtime, file), ...args, '--state-dir', state],
    { cwd: root, env, stdio: ['ignore', 'pipe', 'inherit'] }));
  const check = () => tool('setup.py', ['check']).results.personal_github;
  const prepared = ['prepare', '--repository', REPOSITORY, '--project', 'prj_synthetic', '--operator', 'synthetic-owner',
    '--service-issue', '7', '--answer-thread', 'thr_synthetic_answer', '--harness', 'claude-code', '--model', 'synthetic-model', '--effort', 'high'];
  tool('setup.py', [...prepared, '--yes', '--operation', tool('setup.py', prepared).operation_id]);

  const port = await freePort();
  const server = spawn(SERVER, ['--web-root', OUT_DIR, '--port', String(port)], {
    env: { PATH: '/usr/bin:/bin', HOME: root, OPENWIZ_STATE_DIR: state, OPENWIZ_FIXTURE_PROGRAM: join(root, 'no-room-cli') },
    stdio: ['ignore', 'ignore', 'pipe'],
  });
  server.stderr.resume();
  const origin = `http://127.0.0.1:${port}`;
  let browser;
  // Each page visit: the GitHub rows and the next step, at both widths. The
  // GETs behind it call no gh and change no state byte.
  const visit = async (name, expect) => {
    for (const [width, viewport] of [['phone', PHONE], ['desktop', DESKTOP]]) {
      const before = [readFileSync(join(state, 'setup/state.json'), 'utf8'), calls().length];
      const opened = await openPage(browser, origin, { path: '/setup', viewport });
      try {
        const { page } = opened;
        for (let load = 0; load < 2; load++) {  // a reload reads the same saved choice
          if (load) await page.reload();
          await page.waitForSelector('[data-setup-ready="true"]');
          const login = page.locator('[data-setup-component="personal_github"]');
          const app = page.locator('[data-setup-component="github_app"]');
          assert.equal(await login.locator('.setup-state').innerText(), expect.login, `${name} ${width}`);
          assert.equal(await app.locator('.setup-state').innerText(), 'missing', `${name} ${width}: a skipped or absent App is never verified`);
          await login.locator('summary').first().click();
          await app.locator('summary').first().click();
          const loginText = await login.innerText();
          const appText = await app.innerText();
          for (const pattern of expect.loginText ?? []) assert.match(loginText, pattern, `${name} ${width}: ${loginText}`);
          for (const pattern of expect.appText ?? []) assert.match(appText, pattern, `${name} ${width}: ${appText}`);
          assert.equal(await page.locator('[data-setup-identity]').count(), expect.note ? 1 : 0, `${name} ${width}`);
          if (expect.note) assert.equal(await page.locator('[data-setup-identity]').getAttribute('data-setup-identity'), expect.note);
          assert.equal(await page.locator('input').count(), 0, 'no token or password field');
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
        }
        await page.screenshot({ path: join(RESULTS_DIR, `setup-github-login-${name}-${width}.png`), fullPage: true });
      } finally { await opened.context.close(); }
      assert.deepEqual([readFileSync(join(state, 'setup/state.json'), 'utf8'), calls().length], before, `${name} ${width}: GET setup wrote or called gh`);
    }
  };
  try {
    await waitFor(() => fetch(`${origin}/api/v1/setup`).then((r) => r.status === 200, () => false), { what: 'the setup server' });
    browser = await launchBrowser();
    // Signed out: a legacy-shaped state (no identity). A cancelled browser sign-in is no login.
    assert.equal(tool('github_login.py', ['sign-in']).code, 'login_needed');
    assert.equal(tool('github_login.py', ['sign-in', '--yes']).code, 'login_cancelled');
    assert.equal(check(), 'identity_signed_out');
    await visit('signed-out', { login: 'missing', loginText: [/browser sign-in/, /never paste a token/] });
    // The browser sign-in approved: verified login, App missing, the skip offered.
    scenario({ ...JSON.parse(readFileSync(join(ghDir, 'scenario.json'), 'utf8')), login: 'approve' });
    assert.equal(tool('github_login.py', ['sign-in', '--yes']).code, 'login_verified');
    assert.equal(check(), 'identity_verified');
    await visit('offer', { login: 'verified', appText: [/not registered/, /skip it/, /verified personal login then acts/], note: 'offer' });
    // The explicit skip: the App stays missing, the acting login is named.
    tool('github_login.py', ['skip-app', '--yes', '--operation', tool('github_login.py', ['skip-app']).operation_id]);
    assert.equal(check(), 'identity_verified');
    await visit('skipped', { login: 'verified', loginText: [/Acting identity: synthetic-owner/], appText: [/^Skipped|Skipped:/], note: 'acting' });
    // Another account signs in: refused, never counted as the chosen login.
    scenario({ ...JSON.parse(readFileSync(join(ghDir, 'scenario.json'), 'utf8')), account: 'synthetic-other' });
    assert.equal(check(), 'identity_account_mismatch');
    await visit('mismatch', { login: 'refused', loginText: [/not the personal login you chose/, /synthetic-owner/], appText: [/Skipped/], note: 'chosen' });
    assert.equal(calls().filter((c) => c.startsWith('auth login')).length, 2, 'one cancelled and one approved browser sign-in, no other');
  } finally {
    await browser?.close();
    server.kill('SIGTERM');
    await new Promise((resolve) => server.once('exit', resolve));
    rmSync(root, { recursive: true, force: true });
  }
});
