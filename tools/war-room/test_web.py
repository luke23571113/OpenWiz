#!/usr/bin/env python3
"""WRD4 (#877), P8: the published page served privately over local HTTP.

The real publisher (with the fake picture drawer) publishes to a local bare `war-room`
branch; the web adapter fetches it and serves it on loopback; real Chromium, page scripts
disabled, reads it at 1440 and 390 CSS px. Synthetic input only.
"""
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
FAKES = HERE / 'fixtures' / 'publish'
SERVE = HERE / 'web' / 'serve.py'
AT, NEXT = '2030-01-02T12:03:00Z', '2030-01-02T13:07:00Z'
sys.path.insert(0, str(HERE))
import publish  # noqa: E402

# Measured by DevTools inside the page; the page's own scripts are disabled.
PROBE = r"""
import { spawn } from 'node:child_process';
import { mkdtempSync, readFileSync, existsSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
const [chromium, url] = process.argv.slice(2);
const profile = mkdtempSync(join(tmpdir(), 'war-room-web-probe-'));
const browser = spawn(chromium, ['--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
  '--remote-debugging-port=0', '--user-data-dir=' + profile, 'about:blank'], { stdio: 'ignore' });
const fail = (why) => { console.error('probe: ' + why); browser.kill('SIGKILL'); process.exit(1); };
const deadline = setTimeout(() => fail('timed out'), 120000);
let port = null;
for (let i = 0; i < 200 && !port; i++) {
  const file = join(profile, 'DevToolsActivePort');
  if (existsSync(file)) port = readFileSync(file, 'utf8').split('\n')[0] || null;
  if (!port) await new Promise((r) => setTimeout(r, 50));
}
if (!port) fail('no DevTools port');
const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
let seq = 0; const pending = new Map(); const waiters = [];
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id); pending.delete(msg.id);
    msg.error ? reject(new Error(msg.error.message)) : resolve(msg.result);
  } else if (msg.method) {
    for (const w of waiters.filter((x) => x.method === msg.method)) { waiters.splice(waiters.indexOf(w), 1); w.resolve(msg.params); }
  }
};
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const id = ++seq; pending.set(id, { resolve, reject }); ws.send(JSON.stringify({ id, method, params }));
});
const once = (method) => new Promise((resolve) => waiters.push({ method, resolve }));
const evaluate = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) fail('evaluation failed: ' + r.exceptionDetails.text);
  return r.result.value;
};
const key = async (name, code, vk, text) => {
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: name, code, windowsVirtualKeyCode: vk, ...(text ? { text } : {}) });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: name, code, windowsVirtualKeyCode: vk });
};
const open = async (href) => {
  const loaded = once('Page.loadEventFired');
  await send('Page.navigate', { url: href });
  await loaded;
  if (href !== 'about:blank') await evaluate('document.fonts.ready.then(() => true)');
};
const top = (id) => `Math.round(document.getElementById(${JSON.stringify(id)}).getBoundingClientRect().top)`;
const out = [];
await send('Page.enable');
await send('Emulation.setScriptExecutionDisabled', { value: true });
for (const width of [1440, 390]) {
  await send('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: false });
  await open(url);
  const page = await evaluate(`(() => ({
    contentType: document.contentType, scripts: document.scripts.length,
    scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth,
    svgs: document.querySelectorAll('figure svg').length,
    tables: document.querySelectorAll('details table').length,
    fonts: [...document.fonts].filter((f) => f.status === 'loaded').map((f) => f.family),
    selectable: getComputedStyle(document.querySelector('h1')).userSelect,
    links: [...document.querySelectorAll('nav.toc a')].map((a) => ({ href: a.getAttribute('href'), text: a.textContent,
      target: !!document.getElementById(a.getAttribute('href').slice(1)), shown: a.getBoundingClientRect().width > 0 })),
  }))()`);
  // Keyboard: Tab from the top reaches the section links; Enter on one brings its section to the top.
  const tabs = [];
  for (let i = 0; i < 3; i++) {
    await key('Tab', 'Tab', 9);
    tabs.push(await evaluate(`(() => { const a = document.activeElement; return { href: a.getAttribute('href'), inNav: !!a.closest('nav.toc') }; })()`));
  }
  const chosen = (tabs[tabs.length - 1].href || '#').slice(1);
  let followed = null;
  if (tabs[tabs.length - 1].inNav) {
    await key('Enter', 'Enter', 13, '\r');
    await new Promise((r) => setTimeout(r, 300));
    followed = { id: chosen, top: await evaluate(top(chosen)), hash: await evaluate('location.hash') };
  }
  // A native disclosure opens from the keyboard and shows its values table.
  await evaluate(`document.querySelector('figure details summary').focus()`);
  await key('Enter', 'Enter', 13, '\r');
  const disclosure = await evaluate(`(() => { const d = document.querySelector('figure details');
    const t = d.querySelector('table'); return { open: d.open, table: !!t && t.getBoundingClientRect().height > 0 }; })()`);
  // An authenticated deep link: a fresh load of /#sources lands on the Sources section.
  await open('about:blank');
  await open(url + '#sources');
  const deep = { top: await evaluate(top('sources')), scrolled: await evaluate('scrollY') };
  out.push({ width, ...page, tabs, followed, disclosure, deep });
}
console.log(JSON.stringify(out));
clearTimeout(deadline);
ws.close(); browser.kill('SIGKILL');
rmSync(profile, { recursive: true, force: true });
"""


def git(cwd, *args):
    return subprocess.run(['git', '-C', str(cwd), *args], check=True, capture_output=True).stdout


class Web(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='war-room-web-'))
        self.addCleanup(shutil.rmtree, self.tmp)
        self.origin = self.tmp / 'origin.git'
        git(self.tmp, 'init', '-q', '--bare', str(self.origin))
        self.env = dict(os.environ, PATH=str(FAKES) + os.pathsep + os.environ['PATH'],
                        FAKE_CHROMIUM_LOG=str(self.tmp / 'chromium.log'), FAKE_GH_LOG=str(self.tmp / 'gh.log'))
        self.env.pop('FAKE_CHROMIUM_FAIL', None)
        self.served = self.tmp / 'served'

    def publish(self, at=AT, **env):
        return subprocess.run([sys.executable, '-I', str(HERE / 'publish.py'), 'publish', '--remote', str(self.origin),
                               '--at', at], env=dict(self.env, **env), capture_output=True, text=True)

    def fetch(self, remote=None):
        return subprocess.run([sys.executable, '-I', str(SERVE), 'fetch', '--remote', str(remote or self.origin),
                               '--into', str(self.served)], capture_output=True, text=True)

    def published(self):
        return git(self.origin, 'show', 'refs/heads/war-room:war-room.html'), \
            git(self.origin, 'rev-parse', 'refs/heads/war-room').decode().strip()

    def start(self):
        server = subprocess.Popen([sys.executable, '-I', str(SERVE), 'serve', '--root', str(self.served), '--port', '0'],
                                  stdout=subprocess.PIPE, text=True)
        self.addCleanup(server.stdout.close)
        self.addCleanup(server.wait)
        self.addCleanup(server.kill)
        line = server.stdout.readline().split()
        self.assertEqual(line[:2], ['serving', 'on'])
        host, port = line[2].rsplit(':', 1)
        self.assertEqual(host, '127.0.0.1')  # loopback only: the tunnel is the one way in
        return int(port)

    def request(self, port, path, method='GET'):
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
        conn.request(method, path)
        answer = conn.getresponse()
        body = answer.read()
        conn.close()
        return answer.status, {k.lower(): v for k, v in answer.getheaders()}, body

    def test_the_published_page_is_served_as_html_over_http(self):
        # catches: no page on the branch (only pictures), a wrapper or transformed page served
        # instead of the original, a type the browser downloads or shows as text, a cacheable
        # private page, a dropped security policy, or a served page whose source commit is unknown.
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        fetched = self.fetch()
        self.assertEqual(fetched.returncode, 0, fetched.stderr)
        page, commit = self.published()
        port = self.start()
        status, headers, body = self.request(port, '/')
        self.assertEqual(status, 200)
        self.assertEqual(body, page)
        self.assertNotIn(b'<script', body.lower())
        self.assertEqual(headers['content-type'], 'text/html; charset=utf-8')
        self.assertEqual(headers['cache-control'], 'no-store')
        self.assertEqual(headers['x-content-type-options'], 'nosniff')
        self.assertEqual(headers['content-security-policy'],
                         "default-src 'none'; style-src 'unsafe-inline'; font-src data:; base-uri 'none'; "
                         "form-action 'none'; frame-ancestors 'none'")
        self.assertEqual(headers['etag'], '"%s"' % hashlib.sha256(page).hexdigest())
        self.assertEqual(headers['x-war-room-commit'], commit)
        status, headers, body = self.request(port, '/', 'HEAD')
        self.assertEqual((status, body, headers['content-length']), (200, b'', str(len(page))))

    def test_only_the_page_is_served(self):
        # catches: the origin serving arbitrary branch, sample, identity or controller files,
        # a path escape, or a write method answered.
        self.assertEqual(self.publish().returncode, 0)
        self.assertEqual(self.fetch().returncode, 0)
        (self.served / 'notes.txt').write_text('synthetic\n')
        port = self.start()
        for path in ('/war-room.html', '/identity.json', '/notes.txt', '/README.md', '/war-room.png',
                     '/samples/2030-01-02T12-00-00Z.json', '/.git/config', '/../served/war-room.html',
                     '/%2e%2e/served/war-room.html', '/index.html', '/x/../identity.json'):
            with self.subTest(path):
                status, _, body = self.request(port, path)
                self.assertEqual(status, 404)
                self.assertNotIn(b'<html', body.lower())
        for method in ('POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'):
            with self.subTest(method):
                status, headers, _ = self.request(port, '/', method)
                self.assertEqual((status, headers['allow']), (405, 'GET, HEAD'))

    def test_a_failed_fetch_or_publication_keeps_the_last_good_page(self):
        # catches: a failed render, a bad or missing page on the branch, or an unreachable
        # remote replacing or blanking the page already served.
        self.assertEqual(self.publish().returncode, 0)
        self.assertEqual(self.fetch().returncode, 0)
        good = (self.served / 'war-room.html').read_bytes()
        port = self.start()
        failed = self.publish(NEXT, FAKE_CHROMIUM_FAIL='1')
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn('nothing published', failed.stderr)
        self.assertEqual(self.published()[0], good)
        work = self.tmp / 'edit'
        git(self.tmp, 'clone', '-q', '-b', 'war-room', str(self.origin), str(work))
        head = git(work, 'rev-parse', 'HEAD').decode().strip()
        cases = (('script', lambda p: p.write_bytes(good.replace(b'</body>', b'<script>alert(1)</script></body>'))),
                 ('no policy', lambda p: p.write_bytes(good.replace(b'Content-Security-Policy', b'X-Policy'))),
                 ('not the page', lambda p: p.write_bytes(b'\x89PNG\r\n\x1a\n')),
                 ('a link', lambda p: (p.unlink(), p.symlink_to('README.md'))),
                 ('removed', lambda p: p.unlink()))
        for name, change in cases:
            with self.subTest(name):
                git(work, 'reset', '-q', '--hard', head)
                change(work / 'war-room.html')
                git(work, 'add', '--all')
                git(work, '-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.invalid',
                    'commit', '-q', '-m', name)
                git(work, 'push', '-q', '-f', 'origin', 'HEAD:refs/heads/war-room')
                result = self.fetch()
                self.assertEqual(result.returncode, 1)
                self.assertIn('the last good page stays', result.stderr)
                self.assertEqual(self.request(port, '/')[2], good)
        unreachable = self.fetch(self.tmp / 'absent.git')
        self.assertEqual(unreachable.returncode, 1)
        self.assertNotIn('absent.git', unreachable.stderr)
        self.assertEqual(self.request(port, '/')[2], good)

    def test_real_browser_reads_the_served_page_without_scripts(self):
        # catches: a served page that needs a script or a remote fetch to show its charts and
        # values; top section links that are missing, point at no real section, cannot be reached
        # or followed from the keyboard, or are cut off on a phone; a deep link that does not
        # land; a disclosure that cannot be opened; sideways scrolling at 390 px.
        self.assertEqual(self.publish().returncode, 0)
        self.assertEqual(self.fetch().returncode, 0)
        port = self.start()
        run = subprocess.run(['node', '--input-type=module', '-', publish.chromium(), 'http://127.0.0.1:%d/' % port],
                             input=PROBE, capture_output=True, text=True, timeout=180)
        self.assertEqual(run.returncode, 0, run.stderr)
        views = json.loads(run.stdout)
        self.assertEqual([v['width'] for v in views], [1440, 390])
        for v in views:
            with self.subTest(width=v['width']):
                self.assertEqual(v['contentType'], 'text/html')
                self.assertEqual(v['scripts'], 0)
                self.assertGreater(v['svgs'], 0)
                self.assertGreater(v['tables'], 0)
                self.assertIn('Oswald WR', v['fonts'])
                self.assertNotEqual(v['selectable'], 'none')
                self.assertLessEqual(v['scrollWidth'], v['clientWidth'])
                hrefs = [link['href'] for link in v['links']]
                self.assertEqual(hrefs[:1], ['#figures'])
                self.assertEqual(hrefs[-2:], ['#sources', '#inventory'])
                self.assertEqual(len(hrefs), 3 + len(publish.page.INVENTORY['sections']))
                for link in v['links']:
                    self.assertTrue(link['target'], link)
                    self.assertTrue(link['shown'], link)
                self.assertTrue(all(t['inNav'] for t in v['tabs'][1:]), v['tabs'])
                self.assertIsNotNone(v['followed'])
                self.assertEqual(v['followed']['hash'], '#' + v['followed']['id'])
                self.assertLessEqual(abs(v['followed']['top']), 10, v['followed'])
                self.assertEqual(v['disclosure'], {'open': True, 'table': True})
                self.assertGreater(v['deep']['scrolled'], 0)
                # Sources sits near the page's end, so it lands in view rather than at the very top.
                self.assertTrue(0 <= v['deep']['top'] < 900 - 40, v['deep'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
