// WRD3 (#631): open the page in a real Chromium with page scripts disabled and every host
// unresolvable, then measure it at each viewport and capture it. No dependency: Node's own
// fetch and WebSocket speak the DevTools protocol.
//
//   node probe.mjs CHROMIUM PAGE.html OUT_DIR
//
// Writes OUT_DIR/probe.json and, per viewport, OUT_DIR/<name>.png (a full-page capture for
// the standard viewports, the viewport alone for the target-comparison sizes).
import { spawn } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync, existsSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const [chromium, pagePath, out] = process.argv.slice(2);
const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900, full: true },
  { name: 'phone', width: 390, height: 844, full: true },
  { name: 'desktop-target', width: 1440, height: 1025, full: false },
  { name: 'phone-target', width: 390, height: 1170, full: false },
];
const profile = mkdtempSync(join(tmpdir(), 'war-room-probe-'));
const browser = spawn(chromium, ['--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
  '--remote-debugging-port=0', '--user-data-dir=' + profile, '--host-resolver-rules=MAP * ~NOTFOUND',
  '--proxy-server=127.0.0.1:9', '--force-color-profile=srgb', 'about:blank'], { stdio: 'ignore' });
const fail = (why) => { console.error('probe: ' + why); browser.kill('SIGKILL'); process.exit(1); };
const deadline = setTimeout(() => fail('timed out'), 120000);

async function port() {
  const file = join(profile, 'DevToolsActivePort');
  for (let i = 0; i < 200; i++) {
    if (existsSync(file)) {
      const [p] = readFileSync(file, 'utf8').split('\n');
      if (p) return p;
    }
    await new Promise((r) => setTimeout(r, 50));
  }
  fail('no DevTools port');
}

const p = await port();
const target = await (await fetch(`http://127.0.0.1:${p}/json/new?about:blank`, { method: 'PUT' })).json();
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
let seq = 0;
const pending = new Map();
const waiters = [];
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id);
    pending.delete(msg.id);
    msg.error ? reject(new Error(msg.error.message)) : resolve(msg.result);
  } else if (msg.method) {
    for (const w of waiters.filter((x) => x.method === msg.method)) {
      waiters.splice(waiters.indexOf(w), 1);
      w.resolve(msg.params);
    }
  }
};
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const id = ++seq;
  pending.set(id, { resolve, reject });
  ws.send(JSON.stringify({ id, method, params }));
});
const once = (method) => new Promise((resolve) => waiters.push({ method, resolve }));
const evaluate = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, returnByValue: true });
  if (r.exceptionDetails) fail('evaluation failed: ' + r.exceptionDetails.text);
  return r.result.value;
};

// Measured inside the page by DevTools, never by a page script (page scripts are disabled).
const MEASURE = `(() => {
  const rect = (e) => { const r = e.getBoundingClientRect(); return { x: r.x + scrollX, y: r.y + scrollY, w: r.width, h: r.height }; };
  const shown = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden'; };
  const ground = (e) => {
    for (let n = e; n; n = n.parentElement) {
      const c = getComputedStyle(n).backgroundColor;
      const m = c.match(/rgba?\\(([^)]+)\\)/); const v = m[1].split(',').map(Number);
      if (v.length < 4 || v[3] === 1) return c;
      if (v[3] > 0) return 'translucent ' + c;
    }
    return getComputedStyle(document.documentElement).backgroundColor;
  };
  const text = [];
  for (const e of document.querySelectorAll('body *')) {
    if (e.closest('svg') || !shown(e)) continue;
    const own = [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (!own) continue;
    const s = getComputedStyle(e);
    text.push({ tag: e.tagName.toLowerCase(), cls: e.className, sample: e.textContent.trim().slice(0, 40),
                color: s.color, background: ground(e), size: parseFloat(s.fontSize), weight: Number(s.fontWeight),
                family: s.fontFamily, heading: !!e.closest('h1,h2,h3') });
  }
  return {
    viewport: { width: innerWidth, height: innerHeight },
    scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth,
    height: document.documentElement.scrollHeight,
    scripts: document.scripts.length,
    fonts: [...document.fonts].map((f) => ({ family: f.family, weight: f.weight, status: f.status })),
    figures: [...document.querySelectorAll('figure.fig')].map((f) => ({ id: f.id, ...rect(f),
      caption: (f.querySelector('figcaption') || {}).textContent || null,
      charts: [...f.querySelectorAll('.chart svg')].map((s) => ({ ...rect(s), label: s.getAttribute('aria-label'),
        marks: s.querySelectorAll('title').length,
        // The font size a reader sees: the SVG's own size scaled by how wide it is drawn.
        minFont: Math.min(...[...s.querySelectorAll('text')].filter(shown)
          .map((t) => parseFloat(getComputedStyle(t).fontSize) * s.getBoundingClientRect().width / s.viewBox.baseVal.width)) })) })),
    text,
  };
})()`;

const results = [];
await send('Page.enable');
await send('Emulation.setScriptExecutionDisabled', { value: true });
for (const v of VIEWPORTS) {
  await send('Emulation.setDeviceMetricsOverride', { width: v.width, height: v.height, deviceScaleFactor: 1, mobile: false });
  const loaded = once('Page.loadEventFired');
  await send('Page.navigate', { url: pathToFileURL(pagePath).href });
  await loaded;
  await evaluate('document.fonts.ready.then(() => true)');
  const measured = await evaluate(MEASURE);
  // The capture first, as loaded: before the keyboard check scrolls or opens anything.
  const shot = await send('Page.captureScreenshot', v.full
    ? { format: 'png', captureBeyondViewport: true, clip: { x: 0, y: 0, width: v.width, height: measured.height, scale: 1 } }
    : { format: 'png' });
  writeFileSync(join(out, v.name + '.png'), Buffer.from(shot.data, 'base64'));
  // Keyboard: Tab from the top; the first disclosure reached opens with Enter.
  const focus = [];
  let opened = null;
  for (let i = 0; i < 4 && opened === null; i++) {
    await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 });
    await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 });
    const at = await evaluate(`(() => { const a = document.activeElement; return { tag: a.tagName.toLowerCase(),
      text: a.textContent.trim().slice(0, 30), visible: getComputedStyle(a).outlineStyle !== 'none' || a.matches(':focus-visible') }; })()`);
    focus.push(at);
    if (at.tag === 'summary') {
      await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, text: '\r' });
      await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 });
      opened = await evaluate('document.activeElement.parentElement.open');
    }
  }
  results.push({ ...v, ...measured, focus, opened });
}
writeFileSync(join(out, 'probe.json'), JSON.stringify({ page: pagePath.split('/').pop(), viewports: results }, null, 1));
clearTimeout(deadline);
ws.close();
browser.kill('SIGKILL');
rmSync(profile, { recursive: true, force: true });
