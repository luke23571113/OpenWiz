#!/usr/bin/env python3
"""The War room site (WRD5, #883; the v3 page of WRD3, #631): one saved suite record and one
chart build, as static HTML.

`site` renders six pages: home (the masthead, the evidence-backed status strip, the five headline
chart cards 00a-00e and every benchmark worst first) and five question-led child pages (Speed,
Health, Cost, Quality, Skills and evals) holding the numbered body figures and the Sources of
their benchmarks (benchmarks.json `pages`). `render` is the complete one-document view of the same
content (every chart once), which main.tick keeps locally and the published pictures draw. Charts
are the chart build's finished SVGs (charts/build.py), embedded byte for byte; no page adds a
script, font, image or data request. A figure's face is its title, one sentence and its value or
chart; its dates, coverage, gaps, values and sources are in its native, closed <details>.
"""
import base64
from datetime import datetime, timedelta
from html import escape
import json
from pathlib import Path
import re

import suite
from sources import safe_record

HERE = Path(__file__).resolve().parent
INVENTORY = json.loads((HERE / 'benchmarks.json').read_text(encoding='utf-8'))
# The engraving is decoration drawn in CSS (assets/citadel.css): no image, no request and no CSP change,
# and the page's only <svg> elements stay the chart build's figures.
ART = (HERE / 'assets' / 'citadel.css').read_text(encoding='utf-8')
# Oswald Bold, Basic Latin, for headings only (J85; provenance and hashes in assets/README.md). Embedded
# as data, so the page makes no font request; the CSP allows only `font-src data:` for it.
FONT = ('@font-face{font-family:"Oswald WR";font-weight:700;font-style:normal;font-display:block;'
        'src:url(data:font/woff2;base64,' + base64.b64encode((HERE / 'assets' / 'oswald-bold-latin.woff2').read_bytes()).decode()
        + ') format("woff2")}')
NAMES = {'activity': 'Current activity', 'stage_waits': 'Stage waits',
         'board': 'Board', 'ci_bench': 'CI bench', 'factory_metrics': 'Daily factory',
         'journey': 'Ticket journeys', 'skills_eval': 'Skills eval',
         'cost': 'All-in cost per merged PR', 'credits': 'Credits',
         'claude_usage': 'Claude usage', 'decisions': 'Decision records',
         'answer_time': 'Orchestrator answer time', 'rework': 'Rework rate',
         'eb6': 'EB6', 'eb7': 'EB7', 'eb8': 'EB8', 'eb9': 'EB9',
         'main_ci': 'Main CI', 'ci_queue': 'CI queue', 'stage_health': 'Stage health'}
NO_BUILD = 'Chart build not run for this page: render it through charts/build.py (publish.py does).'

# Ground, ink and the one blue. Measured pairs are in design/brief.md and test_page_design.py.
CSS = (
    ':root{color-scheme:dark;--ground:#000;--ink:#f2f5f8;--soft:#b9c3cf;--muted:#8d97a5;--blue:#4da3ff;'
    '--rule:#f2f5f8;--line:#3a4250;--head:"Oswald WR","Nimbus Sans",Arial,sans-serif;'
    '--cond:"Nimbus Sans","Helvetica Neue",Helvetica,Arial,"Liberation Sans",'
    'sans-serif;--mono:"DejaVu Sans Mono","Liberation Mono",'
    'ui-monospace,Menlo,monospace}'
    '*{box-sizing:border-box}html{background:var(--ground)}'
    'body{margin:0;background:var(--ground);color:var(--ink);font:15px/1.45 var(--mono)}'
    'main{max-width:1440px;margin:0 auto;padding:0 24px 32px}'
    'a{color:var(--blue)}a:focus-visible,summary:focus-visible{outline:2px solid var(--blue);outline-offset:2px}'
    '.skip{position:absolute;left:-9999px}.skip:focus{left:8px;top:8px;background:#000;padding:6px;z-index:2}'
    'h1,h2,h3{font-family:var(--head)}.value{font-family:var(--cond)}'
    'h1,h2,h3,.value{font-weight:700;text-transform:uppercase;'
    'letter-spacing:-.01em;margin:0;line-height:.95}'
    '.mast{display:grid;grid-template-columns:minmax(600px,1.25fr) minmax(0,1fr);border-bottom:2px solid var(--rule);'
    'min-height:280px;position:relative}'
    '.mast .art{grid-column:2;grid-row:1/span 2;min-height:260px}'
    '.brand{grid-column:1;padding:18px 0 0}.brand .kicker{display:block;font-size:34px;'
    'text-transform:uppercase;line-height:1;margin:0}'
    'h1{font-size:104px;line-height:.86;margin:2px 0 10px}'
    '.when{font-size:17px;letter-spacing:.14em;text-transform:uppercase;margin:0;padding:8px 0;'
    'border-top:2px solid var(--rule);border-bottom:2px solid var(--rule)}'
    '.strip{grid-column:1;display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 14px;padding:10px 0 14px}'
    '.strip .flag{font-size:40px;margin:0}.flag.calm{color:var(--soft)}.facts{font-size:15px;text-transform:uppercase;letter-spacing:.06em;'
    'border-left:2px solid var(--rule);padding-left:12px;margin:0}'
    '.gaps{flex-basis:100%;display:flex;flex-wrap:wrap;gap:0 14px;margin:2px 0 0;padding:0;list-style:none;font-size:13px;color:var(--soft)}'
    '.gaps li::before{content:"Gap · ";color:var(--blue)}'
    '.cards{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px;padding:18px 0;'
    'border-bottom:2px solid var(--rule)}'
    '.fig{border:2px solid var(--rule);padding:12px 12px 10px;margin:0;min-width:0;display:flex;flex-direction:column}'
    '.fig h3{font-size:22px}.card-head{display:contents}'
    '.card .value{font-size:32px;margin:8px 0 2px}.card .stamp{font-size:12px;color:var(--soft);margin:0 0 6px;'
    'text-transform:uppercase;letter-spacing:.06em}'
    '.chart{margin:6px 0 0}.chart svg{display:block;width:100%;height:auto}'
    '.chart svg>rect[aria-hidden="true"]:first-child{fill:var(--ground)}'
    '.cap{margin:auto 0 0;padding-top:8px;border-top:2px solid var(--rule);font-size:13px;text-transform:uppercase;'
    'letter-spacing:.04em}'
    '.meta{font-size:12px;color:var(--soft);margin:6px 0 0;overflow-wrap:anywhere}'
    '.meta .gap{display:block;color:var(--ink)}.meta .gap::before{content:"Gap · ";color:var(--blue)}'
    'details{margin:8px 0 0;font-size:12px}summary{cursor:pointer;color:var(--blue);text-transform:uppercase;'
    'letter-spacing:.06em}'
    'table{border-collapse:collapse;width:100%;margin:6px 0}th,td{border-top:1px solid var(--line);padding:3px 6px;'
    'text-align:left;vertical-align:top;overflow-wrap:anywhere}table.values td+td,table.values th+th{white-space:nowrap;width:1%}'
    '.section{border-bottom:2px solid var(--rule);padding:22px 0 18px}'
    'h2{font-size:64px;margin:0 0 16px}'
    '.figs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}'
    '.figs .fig h3{font-family:var(--mono);font-weight:700;font-size:17px;letter-spacing:.06em;'
    'padding-bottom:8px;border-bottom:2px solid var(--rule);margin-bottom:6px}'
    '.panel{margin:8px 0 0}.panel h4{margin:6px 0 0;font-size:13px;color:var(--soft);font-weight:400;'
    'text-transform:uppercase;letter-spacing:.06em}'
    '.panels{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(440px,100%),1fr));gap:4px 16px}'
    '.panel .chart svg{max-width:440px}'
    '.fig.unavailable{border-color:var(--muted);color:var(--soft)}.fig.unavailable h3{border-color:var(--muted)}'
    '.need{margin:10px 0;font-size:14px;color:var(--ink)}.need b{color:var(--muted);font-weight:400;'
    'text-transform:uppercase;letter-spacing:.06em}'
    '.sources,.inventory{overflow-wrap:anywhere}.sources{padding:16px 0 8px;border-bottom:2px solid var(--rule)}.sources h2{font-size:34px;margin:18px 0 6px}'
    '.provider h3{font-size:18px;margin:10px 0 4px}'
    '.metric,.observation{border-top:1px solid var(--line);padding:6px 0}.metric h4,.observation h4{margin:0;font-size:12px}'
    '.metric strong{font-size:14px}.detail{font-size:11px;color:var(--soft);margin:2px 0;overflow-wrap:anywhere}'
    '.badge{font-size:11px;border:1px solid var(--muted);padding:0 6px;margin-left:6px;text-transform:uppercase}'
    'footer{padding:16px 0;font-size:12px;color:var(--soft)}'
    '@media (max-width:760px){main{padding:0 10px 24px}.fig{padding:10px 8px}'
    '.mast{display:block;min-height:0}.mast .art{position:absolute;inset:0 0 auto 46%;height:150px;min-height:0;'
    'opacity:.9}.brand{position:relative;z-index:1;padding-top:12px;text-shadow:0 0 8px #000,0 0 3px #000}.brand .kicker{font-size:22px}h1{font-size:56px;margin-bottom:6px;max-width:62%}'
    '.when{font-size:13px;border:0;padding:0;background:linear-gradient(90deg,#000 60%,transparent)}'
    '.strip{position:relative;display:block;border:2px solid var(--rule);margin:14px 0 0;padding:10px;background:#000}'
    '.strip .flag{font-size:32px}.facts{border:0;padding:4px 0 0}'
    '.cards{grid-template-columns:1fr;gap:12px;padding:12px 0}'
    '.card{display:grid;grid-template-columns:minmax(0,1fr) auto;column-gap:10px}'
    '.card>*{grid-column:1/-1}.card-head{display:flex;flex-wrap:wrap;gap:4px 10px}'
    '.card h3{flex:1 0 160px;font-size:18px}.card .value{flex:1 0 auto;font-size:26px;'
    'margin:0;text-align:right}.card .stamp{flex-basis:100%;text-align:right}'
    'h2{font-size:44px}.figs{grid-template-columns:1fr}.panels{grid-template-columns:1fr}}'
)
# WRD5 (#883): the six-page navigation, native links only; the low-text figure faces (a figure's facts
# are in its disclosure, so the disclosure carries the figure's closing rule); the every-benchmark list.
SITE_CSS = (
    '.site{border-bottom:2px solid var(--rule)}.site ol{display:flex;flex-wrap:wrap;margin:0;padding:0;list-style:none}'
    '.site li{border-right:2px solid var(--rule)}.site a{display:block;padding:12px 18px;font:700 15px/1 var(--mono);'
    'text-transform:uppercase;letter-spacing:.06em;color:var(--ink);text-decoration:none}.site a[aria-current]{background:var(--ink);color:#000}'
    '.site a:hover{color:var(--blue)}'
    '.q{font-size:20px;text-transform:uppercase;letter-spacing:.06em;margin:6px 0 12px;color:var(--soft)}'
    '.fig .cap{border:0;margin:6px 0 0;padding:0;text-transform:none;letter-spacing:0;font-size:14px;color:var(--soft)}'
    '.fig details{margin-top:auto;padding-top:8px;border-top:2px solid var(--rule)}.fig details .meta{margin:4px 0}'
    '.need{margin:10px 0 6px}.need .short{display:block;color:var(--soft);font-size:13px;margin-top:2px}'
    '.figs{align-items:start}'
    '.list{padding:22px 0 18px;border-bottom:2px solid var(--rule)}.list table{font-size:15px;margin:0;max-width:980px}'
    '.list td,.list th{padding:8px;border-top:1px solid var(--line)}.list th{font-size:12px;color:var(--soft);'
    'text-transform:uppercase;letter-spacing:.08em;font-weight:400}.list th.v{text-align:right}'
    '.list .state{white-space:nowrap;text-transform:uppercase;letter-spacing:.06em;font-size:13px}'
    '.list .v{font-family:var(--cond);font-weight:700;text-align:right}'
    '.s-off{color:#000;background:var(--ink);padding:1px 6px}.s-partial{border:1px solid var(--ink);padding:0 5px}'
    '.s-healthy{color:var(--soft)}.s-none{color:var(--muted)}'
    '.gapsd{grid-column:1;padding:0 0 12px;font-size:13px}.gapsd ul{margin:4px 0 0;padding-left:18px;color:var(--soft)}'
    '.child .mast{min-height:200px}.child h1{font-size:88px}.child .brand .kicker a{color:var(--ink);text-decoration:none}'
    '#figures,.section,#benchmarks,#sources,#inventory,.provider{scroll-margin-top:8px}'
    '@media (max-width:760px){.site ol{display:grid;grid-template-columns:repeat(3,1fr);margin-bottom:-2px}'
    '.site li{border-bottom:2px solid var(--rule)}.site li:nth-child(3n){border-right:0}'
    '.site a{padding:10px 6px;font-size:13px;text-align:center}.list table{font-size:13px}'
    '.list td,.list th{padding:6px 4px}.list .name{overflow-wrap:anywhere}.child h1{font-size:52px}'
    '.q{font-size:15px;max-width:62%}}'
)
# A prerequisite this short stays on an unavailable figure's face; a longer one is in its disclosure.
SHORT = 90
STATES = ('off limit', 'partial', 'healthy', 'not measured')
STATE_CLASS = {'off limit': 's-off', 'partial': 's-partial', 'healthy': 's-healthy', 'not measured': 's-none'}


def esc(value):
    return escape(str(value), quote=True)


def metric_html(metric):
    m = metric
    value = 'Unknown' if m['value'] is None else f"{m['value']} {m['unit']}"
    window = m['window']
    span = 'Window unavailable' if window is None else f"[{window['since']}, {window['until']}) {window['timezone']}"
    source = m['source']
    provenance = 'Source unavailable' if source is None else f"{source['path']} · {source['schema']} · SHA-256 {source['sha256']}"
    bound = 'unknown validity bound' if m['fresh_until'] is None else 'fresh through ' + m['fresh_until']
    dimensions = ' · '.join(k + ': ' + str(v) for k, v in m['dimensions'].items() if v is not None)
    links = ' '.join(f'<a href="{esc(url)}" rel="noreferrer noopener">source {i}</a>'
                     for i, url in enumerate(m['evidence'], 1))
    details = [('window', span), ('observed', f"Observed {m['observed_at'] or 'Unknown'} · {m['freshness']} · {bound}"),
               ('statistic', f"{m['statistic']} · native unit {m['native_unit']} · "
                f"coverage {m['sample']['observed']}/{m['sample']['expected'] if m['sample']['expected'] is not None else 'Unknown'}"),
               ('dimensions', dimensions), ('source', provenance)]
    if m['interval'] is not None:
        details.append(('interval', 'Interval ' + json.dumps(m['interval'], sort_keys=True)))
    details.extend(('prerequisite', p) for p in m['prerequisites'])
    return (f'<article class="metric {esc(m["state"])} {esc(m["freshness"])}">'
            f'<h4>{esc(m["label"])}</h4><strong>{esc(value)}</strong> '
            f'<span class="badge">{esc(m["state"])}</span>'
            + ''.join(f'<p class="detail {kind}">{esc(d)}</p>' for kind, d in details if d)
            + f'<p class="links">{links}</p></article>')


def observation_html(o):
    """A v2 health observation's provenance, in the same detail-row form."""
    value = o['result'] if o['value'] is None and o['result'] else ('Unknown' if o['value'] is None else f"{o['value']} {o['unit']}")
    when = o['point'] or (f"[{o['window']['since']}, {o['window']['until']})" if o['window'] else 'Unknown')
    src = o['source']
    rows = [f"Observed {when} · read {o['read']['started_at']} to {o['read']['ended_at']} · {o['evidence_class']}",
            f"{o['statistic']} · coverage {o['sample']['observed']}/{'Unknown' if o['sample']['expected'] is None else o['sample']['expected']}",
            'Source unavailable' if src is None else f"{src['path']} · {src['schema']} · SHA-256 {src['sha256']}"]
    if o['limit']:
        rows.append(f"Limit {o['limit']['minutes']} min from {o['limit']['owner']}, read {o['limit']['read_at']}")
    rows.extend(o['prerequisites'])
    links = ' '.join(f'<a href="{esc(u)}" rel="noreferrer noopener">source {i}</a>' for i, u in enumerate(o['evidence'], 1))
    return (f'<article class="observation {esc(o["state"])}"><h4>{esc(o["label"])}</h4><strong>{esc(value)}</strong> '
            f'<span class="badge">{esc(o["state"])}</span>' + ''.join(f'<p class="detail">{esc(r)}</p>' for r in rows)
            + f'<p class="links">{links}</p></article>')


# The Sources appendix keeps the record's own groups (record.schema.json), under plain titles.
GROUP_TITLES = {'throughput': 'Throughput', 'stage_waits': 'Stage waits', 'board': 'Board, benches and experiments',
                'ci': 'CI', 'usage': 'Usage and cost', 'decisions': 'Answer time'}


def sources_html(record, slots=None, bench_route=None):
    """The Sources appendix: one disclosure holding every value's card, group by group as the
    record orders them, then the three health signals. Each card has its window, freshness,
    statistic, dimensions, provenance and evidence links. Links stay out of the figures section
    (the chart seam carries no href). WRD5: a child page holds only its own benches (`slots`);
    each bench's first block carries the id `bench-<slot>` its home row links to, and a closed
    disclosure opens when that link is followed."""
    homes = {s: c['figure'] for c in INVENTORY['cards'] for s in c['providers']}
    homes.update({s: f['figure'] for sec in INVENTORY['sections'] for f in sec['figures'] for s in f['providers']})
    titles = {p['slug']: p['title'] for p in INVENTORY['pages']}
    seen = set()

    def provider(p, items):
        slot = p['slot']
        anchor = '' if slot in seen else f' id="bench-{esc(slot)}"'
        seen.add(slot)
        where = f'Fig. {homes[slot]}' + ('' if bench_route is None else f' · {titles[bench_route[slot]]} page')
        out = [f'<div class="provider {esc(p["state"])}"{anchor} data-slot="{esc(slot)}"><h3>{esc(NAMES[slot])} '
               f'<span class="badge">{esc(p["state"])}</span> <span class="detail">{esc(where)}</span></h3>']
        out.extend(f'<p class="detail">Prerequisite: {esc(x)}</p>' for x in p['prerequisites'])
        out.extend(metric_html(m) if 'group' in m else observation_html(m) for m in items)
        if not items:
            out.append('<p class="detail">No measured values. Unknown, never zero.</p>')
        return out + ['</div>']
    keep = (lambda slot: True) if slots is None else (lambda slot: slot in slots)
    parts = ['<details class="sources" id="sources"><summary>Sources: every value, its window and its evidence</summary>']
    for group in suite.GROUPS:
        chosen = [(p, d) for p, d in zip(record['providers'], suite.PROVIDERS) if group in d['groups'] and keep(p['slot'])]
        if not chosen:
            continue
        parts.append(f'<section id="{esc(group)}"><h2>{esc(GROUP_TITLES[group])}</h2>')
        for p, _ in chosen:
            parts.extend(provider(p, [m for m in p['metrics'] if m['group'] == group]))
        parts.append('</section>')
    signals = [p for p in suite.health(record) if keep(p['slot'])]
    if signals:
        parts.append('<section id="health"><h2>Health signals</h2>')
        for p in signals:
            parts.extend(provider(p, p['observations']))
        parts.append('</section>')
    return ''.join(parts) + '</details>'


def source_note(slots, bench_route=None):
    """Where a figure's provenance is, in words (no link inside the figures section): each bench's
    Sources entry, on its child page."""
    if not slots:
        return ''
    titles = {p['slug']: p['title'] for p in INVENTORY['pages']}
    where = ', '.join(NAMES[s] + ('' if bench_route is None else f' ({titles[bench_route[s]]} page)') for s in slots)
    return f'<p class="detail">Sources and evidence links: {esc(where)}, under Sources.</p>'


# --- the chart build's figures -------------------------------------------------

def _pst_days(window):
    """'2030-01-07 to 2030-01-13 PST' for a fixed-PST day window, else its exact bounds."""
    if window is None:
        return 'no window'
    since, until = suite._time(window['since']), suite._time(window['until'])
    if window['timezone'] == 'PST-fixed-UTC-08:00' and since.hour == until.hour == 8 and not since.minute + until.minute:
        last = (until - timedelta(days=1)).strftime('%Y-%m-%d')
        first = since.strftime('%Y-%m-%d')
        return (first if first == last else f'{first} to {last}') + ' PST'
    return f"{window['since']} to {window['until']} {'UTC' if window['timezone'] == 'UTC' else 'PST'}"


def _unit(f):
    return 'state' if f['unit'] is None else f['unit'].replace('_', ' ')


def periods(f, record):
    """The chart's own window, or else (#759 R3) the periods of the values it plots, read from the
    record: each metric's window, or a point observation's read time. Distinct periods stay apart;
    a value with no period says so."""
    if f['window'] is not None:
        return [_pst_days(f['window'])]
    found = {(p['slot'], m['id']): m for p in record['providers'] for m in p['metrics']}
    found.update({(p['slot'], o['id']): o for p in suite.health(record) for o in p['observations']})
    out = []
    for src in f['sources']:
        m = found.get((src['slot'], src['metric']))
        if m is None:
            continue
        if m.get('window'):
            out.append(_pst_days(m['window']))
        elif m.get('point'):
            out.append('read at ' + m['point'])
        else:
            out.append('no period, observed ' + (m.get('observed_at') or 'Unknown'))
    plotted = {src['metric'] for src in f['sources']}
    if any(r['key'] not in plotted for r in f['rows']):
        out.append('some values have no source period')
    return list(dict.fromkeys(out)) or ['latest sample ' + record['sample_at']]


def meta_html(f, record):
    """The facts that qualify a chart: unit, dates, coverage, missing points and gaps. WRD5: they sit
    in the figure's values-and-sources disclosure, first, never dropped."""
    cov = f['coverage']
    coverage = f"coverage {cov['observed']} of {'Unknown' if cov['expected'] is None else cov['expected']}"
    missing = f" · missing {', '.join(cov['missing'])}" if cov['missing'] else ''
    nulls = ' · ∅ no sample or Unknown' if any(r['y'] is None for r in f['rows']) else ''
    return (f'<p class="meta">{esc(_unit(f))} · {esc("; ".join(periods(f, record)))} · {esc(coverage + missing + nulls)}'
            + ''.join(f'<span class="gap">{esc(g)}</span>' for g in f['gaps']) + '</p>')


def values_html(f):
    rows = ''.join(f'<tr class="{esc(r["state"])}"><td>{esc(r["label"])}</td>'
                   f'<td>{"Unknown" if r["y"] is None else esc(r["y"])}</td><td>{esc(r["state"])}</td></tr>'
                   for r in f['rows'])
    srcs = ''.join(f'<li>{esc(s["slot"])} · {esc(s["metric"])} · {esc(s["path"])} · {esc(s["schema"])} · '
                   f'SHA-256 {esc(s["sha256"])} · samples {esc(", ".join(s["samples"]))}</li>' for s in f['sources'])
    return (f'<table class="values"><caption class="detail">{esc(f["title"])}: plotted values ({esc(_unit(f))})</caption>'
            f'<thead><tr><th>Value</th><th>Plotted</th><th>State</th></tr></thead><tbody>{rows}</tbody></table>'
            + (f'<ul class="detail">{srcs}</ul>' if srcs else ''))


def _latest(f, series):
    """(y, x) of the series' last plotted value in domain order, or (None, None)."""
    order = {d: i for i, d in enumerate(f['domain'])}
    known = [r for r in f['rows'] if r['series'] == series and r['y'] is not None]
    if not known:
        return None, None
    row = max(known, key=lambda r: (order.get(r['x'], -1), r['x']))
    return row['y'], row['x']


def _num(y):
    return 'Unknown' if y is None else (str(int(y)) if float(y).is_integer() else f'{y:.1f}')


def headline(f):
    """The card's value, read from the plotted rows: (text, stamp). Each keeps its own day."""
    if f is None:
        return 'Unknown', 'chart build not run'
    keys = [s['key'] for s in f['series']]
    if f['id'] == '00a':
        (r, day), (b, _) = _latest(f, 'ready'), _latest(f, 'building')
        return f'{_num(r)} / {_num(b)}', f'ready / building · {day or "no day"}'
    if f['id'] == '00c':
        # Only the current basis heads the card; an older cohort stays a separate line in the chart.
        (m, day), (p, _) = (_latest(f, f'{stat}|workflow-created-to-last-job-completed') for stat in ('median', 'p90'))
        return f'{_num(m)} / {_num(p)} min', f'median / p90 · {day or "no day"}'
    if f['id'] == '00e':
        spans = [r for r in f['rows'] if r['y'] is not None and r['x2']]
        if not spans:
            return 'Unknown', 'no sampled span'
        last = max(spans, key=lambda r: r['x2'])
        hours = (suite._time(last['x2']) - suite._time(last['x'])).total_seconds() / 3600
        return f'{_num(last["y"])} credits / {_num(hours)} h', f'last sampled span · ends {last["x2"][:16]}Z'
    y, day = _latest(f, keys[0])
    unit = {'00b': ' / day', '00d': ' min/run'}.get(f['id'], '')
    return _num(y) + ('' if y is None else unit), day or 'no day'


def claim(figures):
    """{figure number: [chart figures]}: every chart claimed by exactly one inventory figure."""
    claimed = {}
    entries = [(c['figure'], [c['chart']]) for c in INVENTORY['cards']]
    entries += [(f['figure'], f['charts']) for s in INVENTORY['sections'] for f in s['figures']]
    for f in figures:
        owners = [n for n, patterns in entries
                  if any(f['id'] == p or (p.endswith('*') and f['id'].startswith(p[:-1])) for p in patterns)]
        suite.require(len(owners) == 1, 'a chart has no single place in the benchmark inventory')
        claimed.setdefault(owners[0], []).append(f)
    return claimed


# --- the page --------------------------------------------------------------------

def status(record, claimed):
    """(flag, alarm, facts, gaps): only what the saved sample and the plotted rows show."""
    health = {p['slot']: p for p in suite.health(record)}
    flags, facts, gaps = [], [], []
    ready = claimed.get('00a', [None])[0]
    if ready is not None:
        (r, day), (b, _), (goal, _) = _latest(ready, 'ready'), _latest(ready, 'building'), _latest(ready, 'goal')
        if r is not None and b is not None:
            facts.append(f'{_num(r)} ready / {_num(b)} building ({day})')
            if goal is not None and r < goal:
                flags.append('Low ready stock')
        else:
            gaps.append('Ready and building unobserved')
    main = health['main_ci']['observations']
    result = main[0]['result'] if main else None
    if result in (None, 'unknown'):
        facts.append('main CI unknown')
    else:
        facts.append(f'main CI {result}')
        if result == 'failure':
            flags.insert(0, 'Main CI failing')
        elif result in ('pending', 'cancelled'):
            gaps.append(f'Main CI {result}: no current result')
    misses = sum(1 for o in health['stage_health']['observations'] if o['result'] == 'missed')
    if misses:
        flags.append(f'{misses} stage limit missed' if misses == 1 else f'{misses} stage limits missed')
    queued = [o for o in health['ci_queue']['observations'] if o['id'].startswith('queued:')]
    if queued and all(o['value'] is not None for o in queued):
        facts.append(f"{_num(sum(o['value'] for o in queued))} CI jobs queued")
    for slot in ('main_ci', 'ci_queue', 'stage_health'):
        if health[slot]['state'] == 'unavailable':
            gaps.append(f'{NAMES[slot]} unobserved')
    for fid in ('00a', '00b', '00c', '00d', '00e'):
        f = claimed.get(fid, [None])[0]
        if f is None:
            gaps.append(f'Fig. {fid}: chart build not run')
        elif f['coverage']['missing']:
            gaps.append(f"Fig. {fid}: {len(f['coverage']['missing'])} of {f['coverage']['expected']} days missing")
    down = [p for p in record['providers'] + suite.health(record) if p['state'] == 'unavailable']
    if down:
        gaps.append(f'{len(down)} of {len(record["providers"]) + 3} benches unavailable')
    if flags:
        return ' · '.join(flags), True, facts, gaps
    # No anomaly is only claimed when nothing is missing: an absent source is not green.
    return ('No anomaly observed' if not gaps else 'Not every signal observed'), False, facts, gaps


def card_html(card, f, record, bench_route=None):
    """A headline card: title and value, one sentence, the chart; its stamp, facts, values and sources
    behind its disclosure."""
    value, stamp = headline(f)
    if f is None:
        body = f'<p class="need"><b>Unavailable</b><span class="short">{esc(NO_BUILD)}</span></p>'
        inner = ''
    else:
        body = f'<div class="chart" id="figure-{esc(f["id"])}">{f["svg"]}</div>'
        inner = f'<p class="detail stamp">Value as of: {esc(stamp)}</p>' + meta_html(f, record) + values_html(f)
    inner += source_note(card['providers'], bench_route)
    return (f'<figure class="fig card" id="fig-{esc(card["figure"])}" aria-labelledby="t-{esc(card["figure"])}">'
            f'<div class="card-head"><h3 id="t-{esc(card["figure"])}"><span class="no">Fig. {esc(card["figure"])}</span> / {esc(card["title"])}</h3>'
            f'<p class="value">{esc(value)}</p></div><figcaption class="cap">{esc(card["caption"])}</figcaption>{body}'
            + (f'<details><summary>Values and sources</summary>{inner}</details>' if inner else '') + '</figure>')


def body_figure_html(entry, charts, record, bench_route=None):
    """A body figure: title, one sentence, its chart panels, or Unavailable with a short prerequisite;
    a longer prerequisite, each chart's facts and values, and its sources behind its disclosure."""
    number = entry['figure']
    head = (f'<figure class="fig{"" if charts else " unavailable"}" id="fig-{esc(number)}" aria-labelledby="t-{esc(number)}">'
            f'<h3 id="t-{esc(number)}">Fig. {esc(number)} / {esc(entry["title"])}</h3>'
            f'<figcaption class="cap">{esc(entry["caption"])}</figcaption>')
    need = entry['prerequisite']
    if charts:
        many = len(charts) > 1
        panels = ''.join(f'<div class="panel" id="figure-{esc(f["id"])}">' + (f'<h4>{esc(f["title"])}</h4>' if many else '')
                         + f'<div class="chart">{f["svg"]}</div></div>' for f in charts)
        body, inner = f'<div class="panels">{panels}</div>', ''
    elif len(need) <= SHORT:
        body, inner = f'<p class="need"><b>Unavailable</b><span class="short">Needs: {esc(need)}</span></p>', ''
    else:
        body, inner = '<p class="need"><b>Unavailable</b></p>', f'<p class="detail need-full">Needs: {esc(need)}</p>'
    inner += ''.join(meta_html(f, record) + values_html(f) for f in charts) + source_note(entry['providers'], bench_route)
    return (head + body + (f'<details><summary>Values and sources</summary>{inner}</details>' if inner else '') + '</figure>')


def inventory_html(record, claimed, link):
    """The audit: every measured family and the figures that show it, on whichever page holds them."""
    _, figure_route = membership()
    titles = {s['number']: s['title'] for s in INVENTORY['sections']}
    fams = ''.join(f'<tr><td>{esc(titles[x["section"]])}</td><td>{esc(x["measure"])}</td><td>'
                   + ', '.join(f'<a href="{esc(link(figure_route[n], "fig-" + n))}">Fig. {esc(n)}</a>'
                               f'{"" if n in claimed else " (unavailable)"}' for n in x['figures']) + '</td></tr>'
                   for x in INVENTORY['families'])
    return ('<details class="inventory" id="inventory"><summary>Benchmark inventory audit</summary>'
            '<table><caption class="detail">Every measured family and the figures that show it</caption>'
            f'<thead><tr><th>Section</th><th>Measure</th><th>Figures</th></tr></thead><tbody>{fams}</tbody></table></details>')


# --- the site --------------------------------------------------------------------

def routes():
    """'' (home) then each child page's slug, in navigation order."""
    return [''] + [p['slug'] for p in INVENTORY['pages']]


def site_files(home):
    """{route: file name} for a home file name: war-room.html, war-room-speed.html, ..."""
    suite.require(home.endswith('.html'), 'the home page is an HTML file')
    return {r: home if not r else f'{home[:-5]}-{r}.html' for r in routes()}


def site_link(route, anchor=None):
    """A link between the served pages, relative to the site root: './', 'speed', 'speed#fig-01'."""
    return (route or './') + ('#' + anchor if anchor else '')


def view_link(route, anchor=None):
    """The same link inside the complete one-document view: an in-page anchor."""
    return '#' + (anchor or ('p-' + route if route else 'figures'))


def membership():
    """({bench slot: child route}, {figure: route}), or refuse. Every body figure is on exactly one
    child page and every headline card on home; every bench and health signal has exactly one home
    figure, so exactly one child page holds its values and evidence (a card names its page)."""
    pages = INVENTORY['pages']
    slugs = [p['slug'] for p in pages]
    suite.require(len(set(slugs)) == len(slugs) == 5 and all(re.fullmatch('[a-z]+', s) for s in slugs),
                  'the site has five uniquely named child pages')
    body = [f['figure'] for sec in INVENTORY['sections'] for f in sec['figures']]
    listed = [n for p in pages for n in p['figures']]
    suite.require(sorted(listed) == sorted(body), 'every body figure belongs to exactly one child page')
    figure_route = {c['figure']: '' for c in INVENTORY['cards']}
    figure_route.update({n: p['slug'] for p in pages for n in p['figures']})
    suite.require(all(c.get('page') in slugs for c in INVENTORY['cards']), 'every headline card names its child page')
    homes = [(s, c['page']) for c in INVENTORY['cards'] for s in c['providers']]
    homes += [(s, figure_route[f['figure']]) for sec in INVENTORY['sections'] for f in sec['figures'] for s in f['providers']]
    slots = [p['slot'] for p in suite.PROVIDERS] + [h['slot'] for h in suite.HEALTH]
    suite.require(sorted(s for s, _ in homes) == sorted(slots), 'every benchmark has exactly one child page')
    return dict(homes), figure_route


def assessed(record, claimed):
    """({bench: past its limit}, {benches assessed against a limit or goal by their chart alone}).
    Past means the bench's own evidence shows an existing limit or goal missed: a failed main CI run,
    a missed stage limit, ready stock below the board's goal (status's evidenced anomalies)."""
    off = {p['slot'] for p in suite.health(record) if any(o['result'] in ('failure', 'missed') for o in p['observations'])}
    charted = set()
    ready = claimed.get('00a', [None])[0]
    if ready is not None:
        (r, _), (goal, _) = _latest(ready, 'ready'), _latest(ready, 'goal')
        if r is not None and goal is not None:
            charted.add('board')
            if r < goal:
                off.add('board')
    return off, charted


UNIT = {'count': '', 'hours': 'h', 'minutes': 'min', 'prs_per_hour': 'PRs/h', 'credits': 'credits'}
# A bench's row value: the metric it leads with, and the words after the number.
ROW = {'activity': ('merged-hour-forward', 'merged forward this hour'), 'ci_bench': ('merged-per-hour', 'merged PRs/h'),
       'answer_time': ('answer-median', 'min median'), 'rework': ('review-rounds', 'review rounds')}


def bench_value(slot, p, claimed):
    """A row's existing headline value: its card's headline, a health signal's own result or count, or
    its leading metric. Unknown stays Unknown; an unavailable bench says so."""
    items = p.get('metrics', p.get('observations', []))
    card = next((c for c in INVENTORY['cards'] if slot in c['providers']), None)
    if card is not None and claimed.get(card['figure']):
        return headline(claimed[card['figure']][0])[0]
    if p['state'] == 'unavailable':
        return 'Unavailable'
    if slot == 'main_ci':
        return (items[0]['result'] or 'unknown').capitalize() if items else 'Unknown'
    if slot == 'stage_health':
        waits = [o for o in items if o['result'] in ('missed', 'not_missed')]
        return f"{sum(o['result'] == 'missed' for o in waits)} of {len(waits)} waits over limit"
    if slot == 'ci_queue':
        queued = [o['value'] for o in items if o['id'].startswith('queued:')]
        return 'Unknown' if not queued or None in queued else f'{_num(sum(queued))} queued'
    if slot in ROW:
        m = next((m for m in items if m['id'] == ROW[slot][0]), None)
        return 'Unknown' if m is None or m['value'] is None else f'{_num(m["value"])} {ROW[slot][1]}'
    m = next((m for m in items if m['value'] is not None), None)
    return 'Unknown' if m is None else f'{_num(m["value"])} {UNIT.get(m["unit"], m["unit"] or "")}'.strip()


def bench_rows(record, claimed):
    """[(state, slot, value)]: every bench and health signal, off limit, then partial, healthy and
    not measured, each state in inventory order. No threshold is invented: off limit is only an
    existing limit or goal the evidence shows missed, and unassessed data is never healthy."""
    off, charted = assessed(record, claimed)
    providers = {p['slot']: p for p in record['providers'] + suite.health(record)}
    order = [p['slot'] for p in suite.PROVIDERS] + [h['slot'] for h in suite.HEALTH]
    rows = []
    for i, slot in enumerate(order):
        p = providers[slot]
        value = bench_value(slot, p, claimed)
        if slot in off:
            state = 'off limit'
        elif p['state'] == 'partial':
            state = 'partial'
        elif p['state'] == 'known' or slot in charted:
            state = 'healthy'
        else:
            state = 'not measured'
        rows.append((STATES.index(state), i, state, slot, value))
    return [(state, slot, value) for _, _, state, slot, value in sorted(rows)]


def benchmarks_html(record, claimed, link):
    bench_route, _ = membership()
    rows = ''.join(f'<tr class="row"><td class="name"><a href="{esc(link(bench_route[slot], "bench-" + slot))}">'
                   f'{esc(NAMES[slot])}</a></td><td class="state"><span class="{STATE_CLASS[state]}">{esc(state)}</span></td>'
                   f'<td class="v">{esc(value)}</td></tr>' for state, slot, value in bench_rows(record, claimed))
    return ('<section class="list" id="benchmarks" aria-labelledby="hb"><h2 id="hb">Every benchmark, worst first</h2>'
            '<table><thead><tr><th>Benchmark</th><th>State</th><th class="v">Latest</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></section>')


def head(title):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; font-src data:; base-uri \'none\'; form-action \'none\'">'
            '<meta http-equiv="refresh" content="300"><meta name="theme-color" content="#000000">'
            f'<title>{esc(title)}</title><style>{FONT}{CSS}{ART}{SITE_CSS}</style></head>')


ENGRAVING = ('<div class="art" aria-hidden="true"><i class="ring r2"></i><i class="ring"></i><i class="planet"></i>'
             '<i class="city"></i><i class="dome d1"></i><i class="dome d2"></i><i class="ground"></i><i class="near"></i></div>')


def nav(current, link):
    items = [('', 'Home')] + [(p['slug'], p['title']) for p in INVENTORY['pages']]
    here = ' aria-current="page"'
    return ('<nav class="site" aria-label="Pages"><ol>' + ''.join(
        f'<li><a href="{esc(link(r))}"{here if r == current else ""}>{esc(t)}</a></li>'
        for r, t in items) + '</ol></nav>')


def footer(record):
    return (f'<footer>Saved sample {esc(record["sample_at"])} · assembled {esc(record["assembled_at"])}. '
            'Live freshness, complete source history, scheduled operation and hosting are Unverified. '
            'Pages reload every five minutes; only an explicit finite invocation creates a new sample.</footer>')


def masthead(record, claimed):
    """The home masthead and status strip; the strip's gaps fold into one closed disclosure."""
    flag, alarm, facts, gaps = status(record, claimed)
    windows = [f['window'] for n in ('00a', '00b', '00c', '00d') for f in claimed.get(n, []) if f['window']]
    span = _pst_days({'since': min(w['since'] for w in windows), 'until': max(w['until'] for w in windows),
                      'timezone': 'PST-fixed-UTC-08:00'}) if windows else 'no chart window'
    return ('<header class="mast"><div class="brand"><h1><span class="kicker">OpenWiz</span>War room</h1>'
            f'<p class="when">{esc(span)} · sample {esc(record["sample_at"])}</p></div>{ENGRAVING}'
            f'<section class="strip" aria-label="Status"><h2 class="flag{"" if alarm else " calm"}">{esc(flag)}</h2>'
            f'<p class="facts">{esc(" · ".join(facts) or "No signal observed")}</p></section>'
            + (f'<details class="gapsd"><summary>{len(gaps)} {"gap" if len(gaps) == 1 else "gaps"} in this sample</summary>'
               f'<ul class="gaps">{"".join(f"<li>{esc(g)}</li>" for g in gaps)}</ul></details>' if gaps else '')
            + '</header>')


def cards_html(record, claimed, bench_route):
    return ('<div class="cards" role="region" aria-label="Health and speed">'
            + ''.join(card_html(c, claimed.get(c['figure'], [None])[0], record, bench_route) for c in INVENTORY['cards'])
            + '</div>')


def figures_of(slug, record, claimed, bench_route):
    entries = {f['figure']: f for sec in INVENTORY['sections'] for f in sec['figures']}
    p = next(p for p in INVENTORY['pages'] if p['slug'] == slug)
    return ''.join(body_figure_html(entries[n], claimed.get(n, []), record, bench_route) for n in p['figures'])


def home(record, claimed):
    bench_route, _ = membership()
    return (head('OpenWiz War room') + '<body><a class="skip" href="#figures">Skip to the figures</a><main>'
            + masthead(record, claimed) + nav('', site_link)
            # The chart seam on every page: one section holds the page's chart figures (charts/contract.md).
            + '<section id="figures">' + cards_html(record, claimed, bench_route) + '</section>'
            + benchmarks_html(record, claimed, site_link) + inventory_html(record, claimed, site_link)
            + footer(record) + '</main></body></html>')


def child(slug, record, claimed):
    """One child page: its question, its figures and the Sources of the benches it holds."""
    bench_route, _ = membership()
    p = next(p for p in INVENTORY['pages'] if p['slug'] == slug)
    mine = {s for s, r in bench_route.items() if r == slug}
    return (head(f'{p["title"]} · OpenWiz War room')
            + '<body class="child"><a class="skip" href="#figures">Skip to the figures</a><main>'
            '<header class="mast"><div class="brand"><h1><span class="kicker"><a href="./">OpenWiz War room</a></span>'
            f'{esc(p["title"])}</h1><p class="q">{esc(p["question"])}</p></div>{ENGRAVING}</header>'
            + nav(slug, site_link)
            + f'<section id="figures"><div class="section"><div class="figs">{figures_of(slug, record, claimed, bench_route)}'
            '</div></div></section>' + sources_html(record, mine, bench_route) + footer(record) + '</main></body></html>')


def site(record, charts=None):
    """{route: HTML}: home and the five child pages, from one saved sample and one chart bundle.
    Any refusal raises before anything is returned, so a caller never holds part of a site."""
    safe_record(record)
    membership()
    claimed = {} if charts is None else claim(charts['figures'])
    return {r: home(record, claimed) if not r else child(r, record, claimed) for r in routes()}


def render(record, charts=None):
    """The complete one-document view of the site: the home masthead, every chart figure once in one
    figures section (cards, then each child page's figures), every benchmark, the whole Sources
    appendix and the inventory audit. `charts`, when given, is a chart build's bundle (charts/build.py)."""
    safe_record(record)
    bench_route, _ = membership()
    claimed = {} if charts is None else claim(charts['figures'])
    parts = [head('OpenWiz War room'), '<body><a class="skip" href="#figures">Skip to the figures</a><main>',
             masthead(record, claimed), nav('', view_link),
             '<section id="figures">', cards_html(record, claimed, bench_route), '<div id="body">']
    for p in INVENTORY['pages']:
        parts.append(f'<div class="section" role="region" id="p-{esc(p["slug"])}" aria-labelledby="h-{esc(p["slug"])}">'
                     f'<h2 id="h-{esc(p["slug"])}">{esc(p["title"])}</h2><div class="figs">'
                     + figures_of(p['slug'], record, claimed, bench_route) + '</div></div>')
    parts.append('</div></section>' + benchmarks_html(record, claimed, view_link) + sources_html(record, None, bench_route)
                 + inventory_html(record, claimed, view_link) + footer(record) + '</main></body></html>')
    return ''.join(parts)
