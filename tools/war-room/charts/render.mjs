// WRD2 (#630): draw each prepared figure once with the locked Observable Plot, at build time.
//
//   node --permission --allow-fs-read=<tools/war-room> charts/render.mjs < input.json > output.json
//
// Reads only the prepared chart input (stdin, already validated by prepare.py) and
// palette.json. Writes one JSON object, {figures: [{id, svg}]}, to stdout. Every row gets
// exactly one mark carrying its label as <title>, so build.py can reconcile the picture
// with the values table. A null value is a labelled text mark, never a zero.
import { readFileSync } from 'node:fs';
import * as Plot from '@observablehq/plot';
import { BuildDocument, serialize } from './dom.mjs';

const SVG_NS = 'http://www.w3.org/2000/svg';
const palette = JSON.parse(readFileSync(new URL('./palette.json', import.meta.url), 'utf8'));
const INK = '#e8edf4';
const WIDTH = 440;
// The five headline figures are drawn at the page's card width (WRD3), so their text is not shrunk.
const CARD = { width: 260, height: 180 };
const card = (fig) => /^00[a-e]$/.test(fig.id);
const dayTick = (fig) => (d) => (card(fig) ? d.slice(8) : d.slice(5));
const FONT = 12;

const colour = (fig, key) => palette.roles[fig.series.find((s) => s.key === key).role];
const mark = (fig, key) => palette.marks[fig.series.find((s) => s.key === key).role];
const hollow = (row) => row.state === 'partial';
const valued = (rows) => rows.filter((r) => r.y !== null);
const empty = (rows) => rows.filter((r) => r.y === null);
const title = (r) => r.label;
const time = (t) => new Date(t);
const shortValue = (y) => (Number.isInteger(y) ? String(y) : String(Math.round(y * 10) / 10));
const nullWord = (r) => (r.state === 'missing' ? 'no sample' : 'Unknown');
// On a shared axis, many null rows can fall on one day: each gets a small stacked glyph
// (its full words are its title and its values-table row; the page's caption keys the glyph).
const NULL_GLYPH = '∅';
const LIMIT_BAR = { draw(context) { context.moveTo(-14, 0); context.lineTo(14, 0); } };
// Body-chart margins sized to their own labels, so no category or value text is cut off at the
// SVG edge (#631, comment 6901463537). About 7.2 units per character at the 12-unit font.
const CHAR = 7.2;
const leftFor = (labels) => Math.min(240, 18 + CHAR * Math.max(...labels.map((d) => d.length)));
const valueText = (r) => shortValue(r.y) + (hollow(r) ? ' (partial)' : '');

function seriesStyle(fig, extra = {}) {
  return {
    stroke: (r) => colour(fig, r.series),
    fill: (r) => (hollow(r) ? 'none' : colour(fig, r.series)),
    symbol: (r) => mark(fig, r.series).symbol,
    title,
    ...extra,
  };
}

// Null rows as labelled words on the baseline, stacked so two series on one day stay legible.
function nullMarks(fig, rows, { x, y = () => 0, lineAnchor = 'bottom', dyStep = -11 }) {
  // Plot takes a constant dy, so one mark per series.
  return fig.series.map((s, i) => Plot.text(empty(rows).filter((r) => r.series === s.key), {
    x, y, text: () => NULL_GLYPH, title, fill: fig.series.length > 1 ? palette.roles[s.role] : palette.roles.muted,
    lineAnchor, dy: -3 + i * dyStep, fontSize: FONT - 1,
  }));
}

const DRAW = {
  'daily-line'(fig) {
    const lines = fig.series.map((s) => {
      const rows = fig.domain.map((d) => fig.rows.find((r) => r.series === s.key && r.x === d) ?? { x: d, y: null });
      return Plot.line(rows, { x: 'x', y: 'y', stroke: palette.roles[s.role], strokeDasharray: palette.marks[s.role].dash ?? undefined, strokeWidth: 1.5 });
    });
    return {
      x: { type: 'point', domain: fig.domain, padding: 0.4, label: null, tickFormat: dayTick(fig) },
      y: { grid: true, nice: true, zero: true, label: fig.unit },
      marks: [Plot.ruleY([0], { stroke: palette.roles.muted }), ...lines,
        Plot.dot(valued(fig.rows), seriesStyle(fig, { x: 'x', y: 'y', r: 3.5, strokeWidth: 1.5 })),
        ...nullMarks(fig, fig.rows, { x: 'x' })],
    };
  },
  'daily-bar'(fig) {
    return {
      x: { type: 'band', domain: fig.domain, padding: 0.2, label: null, tickFormat: dayTick(fig) },
      y: { grid: true, nice: true, zero: true, label: fig.unit },
      marks: [
        Plot.barY(valued(fig.rows), { x: 'x', y: 'y', fill: (r) => colour(fig, r.series), title }),
        Plot.text(valued(fig.rows), { x: 'x', y: 'y', text: (r) => shortValue(r.y), dy: -7, fill: INK }),
        Plot.ruleY([0], { stroke: palette.roles.muted }),
        ...nullMarks(fig, fig.rows, { x: 'x' })],
    };
  },
  spans(fig) {
    const spans = fig.rows.filter((r) => r.state !== 'missing');
    const missing = fig.rows.filter((r) => r.state === 'missing');
    const days = fig.domain.map((d) => time(d + 'T08:00:00Z'));
    const mid = (r) => new Date((time(r.x).getTime() + time(r.x2).getTime()) / 2);
    if (card(fig)) {
      // 00e at card width (#631 grant, comment 6903517509): the left margin fits the largest tick
      // label, and a span's value label is drawn only where it fits inside the plot without overlapping
      // a larger value's label. Every value stays in its mark's title and the values table.
      const maxY = Math.max(0, ...valued(spans).map((r) => r.y));
      const marginLeft = Math.max(46, 16 + CHAR * Math.round(maxY * 1.25).toLocaleString('en-US').length);
      const t0 = time(fig.window.since).getTime();
      const t1 = time(fig.window.until).getTime();
      const right = CARD.width - 16;
      const kept = [];
      for (const r of [...valued(spans)].sort((a, b) => b.y - a.y)) {
        const c = marginLeft + ((mid(r).getTime() - t0) / (t1 - t0)) * (right - marginLeft);
        const half = (CHAR * shortValue(r.y).length) / 2 + 2;
        if (c - half < marginLeft || c + half > right || kept.some((k) => c - half < k.hi && c + half > k.lo)) continue;
        kept.push({ r, lo: c - half, hi: c + half });
      }
      return {
        marginLeft,
        x: { type: 'utc', domain: [time(fig.window.since), time(fig.window.until)], ticks: days, tickFormat: (d) => dayTick(fig)(d.toISOString().slice(0, 10)), label: 'PST day starts', labelOffset: 34 },
        y: { grid: true, nice: true, zero: true, label: fig.unit },
        marks: [
          Plot.rectY(spans, { x1: (r) => time(r.x), x2: (r) => time(r.x2), y: 'y', fill: (r) => colour(fig, r.series), fillOpacity: 0.85, stroke: palette.roles.primary, strokeWidth: 0.5, inset: 0.5, title }),
          Plot.text(kept.map((k) => k.r), { x: mid, y: 'y', text: (r) => shortValue(r.y), dy: -7, fill: INK }),
          Plot.ruleY([0], { stroke: palette.roles.muted }),
          Plot.text(missing, { x: mid, y: 0, text: () => NULL_GLYPH, lineAnchor: 'bottom', dy: -3, fill: palette.roles.muted, fontSize: FONT - 1, title }),
        ],
      };
    }
    return {
      x: { type: 'utc', domain: [time(fig.window.since), time(fig.window.until)], ticks: days, tickFormat: (d) => dayTick(fig)(d.toISOString().slice(0, 10)), label: 'PST day starts' },
      y: { grid: true, nice: true, zero: true, label: fig.unit },
      marks: [
        Plot.rectY(spans, { x1: (r) => time(r.x), x2: (r) => time(r.x2), y: 'y', fill: (r) => colour(fig, r.series), fillOpacity: 0.85, stroke: palette.roles.primary, strokeWidth: 0.5, inset: 0.5, title }),
        Plot.text(spans, { x: (r) => new Date((time(r.x).getTime() + time(r.x2).getTime()) / 2), y: 'y', text: (r) => shortValue(r.y), dy: -7, fill: INK }),
        Plot.ruleY([0], { stroke: palette.roles.muted }),
        Plot.text(missing, { x: (r) => new Date((time(r.x).getTime() + time(r.x2).getTime()) / 2), y: 0, text: () => NULL_GLYPH, lineAnchor: 'bottom', dy: -3, fill: palette.roles.muted, fontSize: FONT - 1, title }),
      ],
    };
  },
  bars(fig) {
    return {
      height: 64 + 24 * fig.domain.length,
      marginLeft: leftFor(fig.domain),
      marginRight: Math.max(16, 10 + CHAR * Math.max(0, ...valued(fig.rows).map((r) => valueText(r).length))),
      y: { type: 'band', domain: fig.domain, label: null, padding: 0.25 },
      x: { grid: true, nice: true, zero: true, label: fig.unit },
      marks: [
        Plot.barX(valued(fig.rows), { y: 'x', x: 'y', fill: (r) => (hollow(r) ? 'none' : colour(fig, r.series)), stroke: (r) => colour(fig, r.series), title }),
        Plot.text(valued(fig.rows), { y: 'x', x: 'y', text: valueText, textAnchor: 'start', dx: 4, fill: INK }),
        Plot.text(empty(fig.rows), { y: 'x', x: 0, text: nullWord, textAnchor: 'start', dx: 4, fill: palette.roles.muted, title }),
        Plot.ruleX([0], { stroke: palette.roles.muted }),
      ],
    };
  },
  distribution(fig) {
    return {
      height: 110,
      y: { type: 'band', domain: fig.series.map((s) => s.key), label: null, axis: null },
      x: { grid: true, nice: true, zero: true, label: fig.unit },
      marks: [
        Plot.dot(valued(fig.rows), seriesStyle(fig, { x: 'y', y: 'series', r: 4 })),
        Plot.text(empty(fig.rows), { x: 0, y: 'series', text: nullWord, textAnchor: 'start', fill: palette.roles.muted, title }),
      ],
    };
  },
  limits(fig) {
    const limits = fig.rows.filter((r) => r.series === 'limit');
    const waits = fig.rows.filter((r) => r.series !== 'limit');
    return {
      x: { type: 'point', domain: fig.domain, padding: 0.5, label: null },
      y: { grid: true, nice: true, zero: true, label: fig.unit },
      marks: [
        // A limit is a short horizontal bar on its stage's point (a band-scale tick cannot share this axis).
        Plot.dot(valued(limits), { x: 'x', y: 'y', symbol: LIMIT_BAR, r: 7, fill: 'none', stroke: palette.roles.reference, strokeWidth: 2.5, title }),
        Plot.dot(valued(waits), seriesStyle(fig, { x: 'x', y: 'y', r: 4, strokeWidth: 1.5 })),
        Plot.ruleY([0], { stroke: palette.roles.muted }),
        ...nullMarks(fig, fig.rows, { x: 'x' }),
      ],
    };
  },
  readiness(fig) {
    const fill = { known: palette.roles.primary, partial: palette.roles.secondary, unavailable: palette.roles.muted, missing: palette.roles.muted };
    return {
      height: 60 + 24 * fig.domain.length,
      marginLeft: leftFor(fig.domain),
      y: { type: 'band', domain: fig.domain, label: null, padding: 0.1 },
      x: { axis: null },
      marks: [
        Plot.cell(fig.rows, { y: 'x', fill: (r) => fill[r.state], inset: 1, title }),
        // The row's own visible word: a main-CI result or a provider state, never only a title.
        Plot.text(fig.rows, { y: 'x', text: (r) => r.text ?? r.state, fill: palette.ground, fontWeight: 'bold' }),
      ],
    };
  },
};

// A key under multi-series figures: each series' own symbol, colour and label. No title:
// the key is not a plotted value.
const GLYPH = { circle: '●', square: '■', diamond: '◆', triangle: '▲', times: '×' };
function key(fig, base) {
  const keyed = fig.series.filter((s) => s.key !== 'missing');
  if (keyed.length < 2 || !['daily-line', 'limits', 'spans'].includes(fig.kind)) return { extra: 0, marks: [] };
  const items = keyed.map((s, i) => ({ i, text: `${GLYPH[palette.marks[s.role].symbol]} ${s.label}`, fill: palette.roles[s.role] }));
  if (card(fig)) return cardKey(items, base);
  return {
    extra: 15 * items.length,
    marks: items.map((d) => Plot.text([d], { frameAnchor: 'bottom-left', textAnchor: 'start', dx: -30, dy: base + 15 * d.i, text: 'text', fill: 'fill', fontSize: FONT - 1 })),
  };
}

// A headline card's key (WRD3): each label wrapped at word breaks to the card's width, one line
// per 13 px, and the key's whole height reserved, so no label is cut off at 260 units (#759 R1).
const CARD_KEY_CHARS = 34;
function wrap(text) {
  const lines = [];
  for (const word of text.split(' ')) {
    const last = lines.length - 1;
    if (last >= 0 && (lines[last] + ' ' + word).length <= CARD_KEY_CHARS) lines[last] += ' ' + word;
    else lines.push(word);
  }
  return lines;
}
function cardKey(items, base) {
  let offset = 0;
  const marks = items.map((d) => {
    const lines = wrap(d.text);
    const mark = Plot.text([d], { frameAnchor: 'bottom-left', textAnchor: 'start', lineAnchor: 'top', dx: -30, dy: base - 6 + offset,
      text: () => lines.join('\n'), lineHeight: 13 / (FONT - 1), fill: 'fill', fontSize: FONT - 1 });
    offset += 13 * lines.length + 2;
    return mark;
  });
  return { extra: offset, marks };
}

function figureSvg(fig, document) {
  const spec = DRAW[fig.kind](fig);
  // A headline card with no numeric value draws no numeric axis, grid or ticks: Unknown has no
  // scale (#631 grant, comment 6903517509). Its marks, titles and values are unchanged.
  if (card(fig) && valued(fig.rows).length === 0) {
    const axis = ['bars', 'distribution'].includes(fig.kind) ? 'x' : 'y';
    spec[axis] = { ...(spec[axis] || {}), axis: null, grid: false, label: null };
  }
  // 00e's key starts below its x-axis label, so the two never overlap (#631 grant).
  const base = card(fig) && fig.kind === 'spans' ? 56 : 40;
  const legend = key(fig, base);
  legend.extra += base - 40;
  spec.marks = [...spec.marks, ...legend.marks];
  const svg = Plot.plot({
    document, width: card(fig) ? CARD.width : WIDTH, height: (card(fig) ? CARD.height : 220) + legend.extra, marginTop: 22, marginBottom: 34 + legend.extra, marginLeft: 46,
    marginRight: 16, ariaLabel: fig.title, ariaDescription: fig.caption, style: null, ...spec,
  });
  // A self-contained figure: no style element, the page's ground and ink as attributes.
  for (const child of [...svg.childNodes]) if (child.tagName === 'style') svg.removeChild(child);
  svg.setAttribute('xmlns', SVG_NS);
  svg.setAttribute('font-size', String(FONT));
  svg.setAttribute('color', INK);
  svg.removeAttribute('class');
  const ground = document.createElementNS(SVG_NS, 'rect');
  for (const [k, v] of Object.entries({ width: '100%', height: '100%', fill: palette.ground, 'aria-hidden': 'true' })) ground.setAttribute(k, v);
  svg.insertBefore(ground, svg.firstChild);
  return serialize(svg);
}

const input = JSON.parse(readFileSync(0, 'utf8'));
const document = new BuildDocument();
process.stdout.write(JSON.stringify({ figures: input.figures.map((fig) => ({ id: fig.id, svg: figureSvg(fig, document) })) }));
