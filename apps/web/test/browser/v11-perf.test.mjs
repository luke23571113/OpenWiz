// V11, synthetic half: refresh measurements for performance-targets.md. The
// targets are PENDING (no A9 baseline), so these record numbers; the only
// assertions are the issue's fixed ones: no layout shift on refresh, and at
// most one list and one detail read in flight.

import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync } from 'node:fs';
import { after, before, test } from 'node:test';

import { TIMING } from '../../src/timing.ts';
import { DESKTOP, launchBrowser, openPage, readDetail, readView, waitFor } from '../support/browser.mjs';
import { json } from '../support/fake-api.mjs';
import { fakeSite } from '../support/harness.mjs';
import { RESULTS_DIR } from '../support/paths.mjs';
import { inventory, manyRows, session, sessionView } from '../support/synthetic.ts';

const START = new Date('2027-01-15T08:00:00Z');
const results = {};

let browser;
before(async () => {
  browser = await launchBrowser();
});
after(async () => {
  await browser.close();
  mkdirSync(RESULTS_DIR, { recursive: true });
  writeFileSync(`${RESULTS_DIR}/v11-perf.json`, `${JSON.stringify(results, null, 2)}\n`);
});

async function siteWith(rows, delayMs = 0) {
  const fx = await fakeSite();
  const body = json(200, inventory(manyRows(rows), { matched: rows }));
  fx.api.setList(() => ({ ...body, delayMs }));
  fx.api.setDetail((id) => ({ ...json(200, sessionView(session(Number(id.slice(-4))))), delayMs }));
  return { fx, body };
}

test('P4, P6, P7, P8: bytes, main-thread work and layout shift per refresh', async () => {
  results.refresh = {};
  for (const rows of [6, 100, 200]) {
    const { fx } = await siteWith(rows);
    let n = 0;
    // Every refresh changes the statuses, so each one renders.
    fx.api.setList(() => {
      n++;
      return json(
        200,
        inventory(
          manyRows(rows).map((s, i) => ({ ...s, status: { known: ['idle', 'active', 'error'][(i + n) % 3] } })),
          { matched: rows },
        ),
      );
    });
    const p = await openPage(browser, fx.site.origin, { viewport: DESKTOP, clock: START });
    const cdp = await p.context.newCDPSession(p.page);
    try {
      await waitFor(async () => (await readView(p.page)).groups.length > 0, { what: 'rows' });
      await p.page.click('[data-session-id="thr_web_0001"]');
      await waitFor(async () => (await readDetail(p.page))?.title === 'Synthetic web session 1', { what: 'detail' });
      await p.page.evaluate(() => {
        // No input occurs during this measurement. Count late preview updates
        // even inside the opening click's recent-input window: a faster runner
        // must not hide a real movement that a slower runner reports.
        window.__shifts = 0;
        window.__shiftEntries = [];
        new PerformanceObserver((list) => {
          for (const e of list.getEntries()) {
            const entry = {
              value: e.value, hadRecentInput: e.hadRecentInput, startTime: e.startTime,
              sources: e.sources.map((s) => ({
                element: s.node?.outerHTML?.slice(0, 1000),
                previousRect: s.previousRect.toJSON(), currentRect: s.currentRect.toJSON(),
              })),
            };
            window.__shiftEntries.push(entry);
            window.__shifts += e.value;
          }
        }).observe({ type: 'layout-shift' });
      });
      await cdp.send('Performance.enable');
      const metric = async () => Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map((m) => [m.name, m.value]));
      const before = await metric();
      const refreshes = 20;
      const refreshBytes = [];
      for (let i = 0; i < refreshes; i++) {
        const k = fx.api.reads('list').length;
        await p.page.clock.runFor(TIMING.listIntervalMs);
        await waitFor(() => fx.api.reads('list').length > k && fx.api.reads('list').at(-1).endedAt !== null, { what: 'refresh' });
        await waitFor(async () => (await p.page.evaluate(() => document.querySelector('[data-snapshot-seq]')?.dataset.snapshotSeq)) === String(k + 1), {
          what: 'render',
        });
        // The response listener reads the body asynchronously; wait for this
        // refresh's bytes, excluding the initial load and detail responses.
        const reply = await waitFor(() => {
          const replies = p.responses.filter((r) => r.path === '/api/v1/inventory');
          return replies.length === k + 1 && replies[k].body !== null && replies[k];
        }, { what: 'refresh response body' });
        refreshBytes.push(Buffer.byteLength(reply.body));
      }
      const after = await metric();
      const per = (key) => ((after[key] - before[key]) * 1000) / refreshes;
      const shifts = await p.page.evaluate(() => window.__shifts);
      results.refresh[`${rows} rows`] = {
        bytesPerRefresh: refreshBytes.reduce((sum, bytes) => sum + bytes, 0) / refreshes,
        mainThreadMsPerRefresh: { task: per('TaskDuration'), script: per('ScriptDuration'), layout: per('LayoutDuration'), style: per('RecalcStyleDuration') },
        layoutShift: shifts,
        layoutShiftEntries: await p.page.evaluate(() => window.__shiftEntries),
        maxInFlight: fx.api.maxInFlight,
      };
      if (shifts) console.log(JSON.stringify({ rows, layoutShiftEntries: results.refresh[`${rows} rows`].layoutShiftEntries }));
      assert.equal(shifts, 0, `layout shift on refresh with ${rows} rows`);
      assert.ok(fx.api.maxInFlight.list <= 1 && fx.api.maxInFlight.detail <= 1);
    } finally {
      await p.close();
      await fx.close();
    }
  }
});
