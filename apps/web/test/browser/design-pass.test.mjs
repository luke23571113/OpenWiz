// The design pass (#75): presentation proofs at 390 and 1440 px. The selected
// row has a shape, not only a tint; the core's words are shown whole and as
// reported; shapes keep 3:1 contrast and targets 44 px.

import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';

import { DESKTOP, launchBrowser, openPage, PHONE, readDetail, readView, waitFor } from '../support/browser.mjs';
import { json } from '../support/fake-api.mjs';
import { clock } from '../support/expect.mjs';
import { fakeSite } from '../support/harness.mjs';
import { decodePng, inkMask, maskDifference } from '../support/png.mjs';
import { inventory, session, sessionView, statusSessions, T0 } from '../support/synthetic.ts';

const LONG_STATUS = `syn-very-long-status-word-${'x'.repeat(40)}`;
const rows = [
  ...statusSessions(),
  session(6, { group: { kind: 'ungrouped', reason: 'no project id reported' } }),
  session(7, { group: { kind: 'project', id: 'prj_web_0002', name: { known: 'Synthetic mixedCase Project' } }, status: { known: LONG_STATUS } }),
  session(8, { group: { kind: 'project', id: 'prj_web_0003', name: { unknown: 'project list did not name it' } } }),
  session(9, { group: { kind: 'project', id: 'prj_web_0004', name: { known: 'Synthetic twin project' } } }),
  session(10, { group: { kind: 'project', id: 'prj_web_0005', name: { known: 'Synthetic twin project' } }, status: { known: 'error' } }),
];
const gaps = [{ kind: 'timed_out', subject: null, detail: 'machine list timed out after 15 s' }];

let browser;
let fx;
before(async () => {
  browser = await launchBrowser();
  fx = await fakeSite();
  fx.api.setList(() => json(200, inventory(rows, { state: 'partial', gaps })));
  fx.api.setDetail((id) => json(200, sessionView(rows.find((r) => r.id === id) ?? session(1))));
});
after(async () => {
  await fx.close();
  await browser.close();
});

async function ready(viewport) {
  const p = await openPage(browser, fx.site.origin, { viewport });
  await waitFor(async () => (await readView(p.page)).groups.length > 0, { what: 'rows' });
  return p;
}

async function open(p, id) {
  await p.page.click(`[data-session-id="${id}"]`);
  await waitFor(async () => (await readDetail(p.page))?.id === id && (await readDetail(p.page)).title !== null, { what: 'the detail' });
}

/** A greyscale mask of the row `id`, with 16 px of canvas on each side (the selection bar sits in the gutter) and 4 px above and below. */
async function rowMask(page, id) {
  await page.mouse.move(DESKTOP.width - 8, 8);
  const box = await page.locator(`main [data-session-id="${id}"]`).boundingBox();
  await page.evaluate(() => (document.documentElement.style.filter = 'grayscale(1)'));
  const png = await page.screenshot({ clip: { x: box.x - 16, y: box.y - 4, width: box.width + 32, height: box.height + 8 } });
  await page.evaluate(() => (document.documentElement.style.filter = ''));
  return inkMask(decodePng(png));
}

test('the selected row is told apart by shape, not by a tint alone', async () => {
  const p = await ready(DESKTOP);
  try {
    const plain = await rowMask(p.page, 'thr_web_0003');
    await open(p, 'thr_web_0003');
    const selected = await rowMask(p.page, 'thr_web_0003');
    const diff = maskDifference(plain, selected);
    assert.ok(diff >= 20, `the selected row's greyscale shape differs from the plain row's (${diff} px)`);
  } finally {
    await p.close();
  }
});

test('a status word is shown whole, never cut with an ellipsis', async () => {
  for (const viewport of [PHONE, DESKTOP]) {
    const p = await ready(viewport);
    try {
      const cut = await p.page.$$eval('main [data-part=status] .word', (els) =>
        els.filter((w) => w.scrollWidth > w.clientWidth + 1).map((w) => w.textContent),
      );
      assert.deepEqual(cut, [], `at ${viewport.width}px`);
      const wide = await p.page.evaluate(() => document.documentElement.scrollWidth);
      assert.ok(wide <= viewport.width, `no sideways overflow at ${viewport.width}px (${wide})`);
    } finally {
      await p.close();
    }
  }
});

test('group headings show the project name as reported, not re-cased', async () => {
  const p = await ready(PHONE);
  try {
    const recased = await p.page.$$eval('[data-group-key] h2', (hs) => hs.filter((h) => h.innerText !== h.textContent).map((h) => h.textContent));
    assert.deepEqual(recased, []);
  } finally {
    await p.close();
  }
});

test('the gaps toggle: a small dashed tag in a 44 px target, showing whether it is open', async () => {
  const p = await ready(PHONE);
  try {
    const look = () =>
      p.page.$eval('button:has([data-part=coverage]), button[data-part=coverage]', (b) => {
        const dashed = [b, ...b.querySelectorAll('*')].find((el) => getComputedStyle(el).borderTopStyle === 'dashed');
        return { target: b.getBoundingClientRect().height, tag: dashed ? dashed.getBoundingClientRect().height : null, text: b.innerText };
      });
    const closed = await look();
    assert.equal(await p.page.locator('.gap-summary').isVisible(), true, 'the gap summary is visible before expanding');
    assert.equal(await p.page.locator('.gap-summary').textContent(), gaps[0].detail, 'the gap detail remains verbatim');
    assert.ok(closed.target >= 44, `target ${closed.target}`);
    assert.ok(closed.tag !== null && closed.tag <= 24, `the dashed tag is ${closed.tag} px tall`);
    await p.page.click('[data-part=coverage]');
    const opened = await look();
    assert.equal(await p.page.locator('button.cov').getAttribute('aria-expanded'), 'true', 'the disclosure announces its open state');
    assert.equal(await p.page.locator('button.cov svg.open').count(), 1, 'the chevron turns when opened');
    assert.equal((await readView(p.page)).coverage, 'partial · 1 gap', 'the coverage words are unchanged');
  } finally {
    await p.close();
  }
});

test('G2: headings that share a name end with the project id\'s last 4 characters, and only those', async () => {
  const p = await ready(PHONE);
  try {
    assert.deepEqual(
      (await readView(p.page)).groups.map((g) => g.heading),
      [
        'Synthetic web project one',
        'ungrouped',
        'Synthetic mixedCase Project',
        'unknown (project list did not name it)',
        'Synthetic twin project · 0004',
        'Synthetic twin project · 0005',
      ],
    );
  } finally {
    await p.close();
  }
});

/** The rendered contrast of each element's own (or its `::before`'s) top border against the surface behind it. */
const borderContrast = (page, selector, pseudo = null) =>
  page.$$eval(
    selector,
    (els, pseudo) => {
      const rgb = (c) => (c.match(/[\d.]+/g) ?? []).map(Number);
      const lum = ([r, g, b]) => {
        const ch = (v) => ((v /= 255) <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
        return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b);
      };
      const behind = (el) => {
        for (let e = el; e; e = e.parentElement) {
          const c = rgb(getComputedStyle(e).backgroundColor);
          if (c.length === 3 || (c.length === 4 && c[3] === 1)) return c.slice(0, 3);
        }
        return rgb(getComputedStyle(document.documentElement).backgroundColor).slice(0, 3);
      };
      return els.map((el) => {
        const s = getComputedStyle(el, pseudo);
        const [a, b] = [lum(rgb(s.borderTopColor)), lum(behind(el))].sort((x, y) => y - x);
        return { text: el.textContent, style: s.borderTopStyle, ratio: (a + 0.05) / (b + 0.05) };
      });
    },
    pseudo,
  );

test('partial\'s dashed tag, with gaps and with none, and the t5 marker\'s box are at least 3:1 as rendered (Sol round 1)', async () => {
  const zero = await fakeSite();
  zero.api.setList(() => json(200, inventory(rows, { state: 'partial', gaps: [] })));
  try {
    for (const [origin, what] of [
      [fx.site.origin, 'partial · 1 gap'],
      [zero.site.origin, 'partial · 0 gaps'],
    ]) {
      const p = await openPage(browser, origin, { viewport: PHONE });
      try {
        await waitFor(async () => (await readView(p.page)).groups.length > 0, { what: 'rows' });
        const shapes = [...(await borderContrast(p.page, '.coverage-chip')), ...(await borderContrast(p.page, 'main [data-tier=t5] .glyph svg'))];
        assert.equal(shapes[0]?.text, `${what}· read ${clock(T0, await p.page.evaluate(() => Date.now()))}`);
        assert.equal(shapes[0]?.style, 'dashed', `${what} is a dashed tag`);
        assert.ok(await p.page.locator('main [data-tier=t5] svg circle[stroke-dasharray]').count() >= 1, 'unknown has a dashed SVG ring');
        for (const s of shapes) assert.ok(s.ratio >= 3, `${s.text}: its ${s.style} border is ${s.ratio.toFixed(2)}:1`);
      } finally {
        await p.close();
      }
    }
  } finally {
    await zero.close();
  }
});

test('Projects links name the current groups and counts and only navigate to their anchors', async () => {
  const p = await ready(DESKTOP);
  try {
    const groups = (await readView(p.page)).groups.filter((g) => g.key.startsWith('project:'));
    const links = await p.page.locator('nav[aria-label=Projects] a').evaluateAll((els) => els.map((a) => ({ target: a.getAttribute('href').slice(1), name: a.children[1].textContent, count: a.children[2].textContent })));
    assert.deepEqual(links, groups.map((g) => ({ target: `project-${g.key}`, name: g.heading.replace(/ · 000[45]$/, ''), count: String(g.rows.length) })));
    await p.page.locator('nav[aria-label=Projects] a').last().click();
    const target = await p.page.evaluate(() => document.getElementById(decodeURIComponent(location.hash.slice(1)))?.getAttribute('data-group-key'));
    assert.equal(target, groups.at(-1).key);
    assert.equal(p.requests.filter((r) => r.method !== 'GET').length, 0, 'project navigation never writes');
    assert.equal(await p.page.locator('[data-part=detail][open]').count(), 0, 'project navigation opens no dialog');
  } finally {
    await p.close();
  }
});
