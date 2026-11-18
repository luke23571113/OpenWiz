#!/usr/bin/env python3
"""WRD2 (#630): the War room chart build. Validated history in, finished static SVG out.

    python3 -I charts/build.py --history DIR --at UTC [--source-root DIR --selection FILE] [--snapshot FILE] --out DIR

prepare.py selects the values; render.mjs draws each figure once with the locked
Observable Plot under Node (build time only); this module refuses any SVG outside the
allowlist or whose mark titles differ from its rows, then writes `<id>.svg`,
`values.json` and `manifest.json`. A refusal raises ValueError and writes nothing.
History is only read. See contract.md.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
TOOL = HERE.parent
sys.path.insert(0, str(TOOL))
sys.path.insert(0, str(HERE))
import history  # noqa: E402
import prepare  # noqa: E402
import prs_per_hour  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'collector'))
import suite  # noqa: E402

MANIFEST = 'openwiz.war-room.charts-manifest.v1'
VALUES = 'openwiz.war-room.charts-values.v1'
PLOT = TOOL / 'node_modules' / '@observablehq' / 'plot' / 'package.json'
PREREQUISITE = 'chart build prerequisite: run `npm ci --ignore-scripts` in tools/war-room with Node 24.22.1'
SVG_NS = '{http://www.w3.org/2000/svg}'
ELEMENTS = {'svg', 'g', 'path', 'line', 'rect', 'circle', 'text', 'tspan', 'title'}
ATTRIBUTES = {'xmlns', 'width', 'height', 'viewBox', 'class', 'fill', 'fill-opacity', 'stroke', 'stroke-width',
              'stroke-opacity', 'stroke-dasharray', 'stroke-linecap', 'stroke-linejoin', 'stroke-miterlimit',
              'opacity', 'font-family', 'font-size', 'font-variant', 'font-weight', 'text-anchor', 'paint-order',
              'transform', 'x', 'y', 'x1', 'x2', 'y1', 'y2', 'dx', 'dy', 'cx', 'cy', 'r', 'd', 'color',
              'aria-label', 'aria-description', 'aria-hidden', 'role'}


def _locked_plot():
    lock = json.loads((TOOL / 'package-lock.json').read_text(encoding='utf-8'))
    return lock['packages']['node_modules/@observablehq/plot']['version']


def _node():
    node = shutil.which('node')
    suite.require(node is not None and PLOT.is_file(), PREREQUISITE)
    installed = json.loads(PLOT.read_text(encoding='utf-8'))['version']
    suite.require(installed == _locked_plot(), PREREQUISITE + ' (installed Plot differs from the lock)')
    return node


def render(doc):
    """{figure id: svg text}: one Node run, one Plot drawing per figure."""
    node = _node()
    try:
        out = subprocess.run([node, '--permission', '--allow-fs-read=' + str(TOOL), str(HERE / 'render.mjs')],
                             input=json.dumps(doc), capture_output=True, text=True, timeout=120,
                             cwd=str(HERE), env={'PATH': os.environ.get('PATH', ''), 'NODE_OPTIONS': ''})
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError('the chart renderer did not run') from error
    # Only the reason class: renderer output can echo input text.
    suite.require(out.returncode == 0, 'the chart renderer failed')
    drawn = suite._decode(out.stdout)
    suite.require([f['id'] for f in drawn['figures']] == [f['id'] for f in doc['figures']], 'the renderer skipped a figure')
    return {f['id']: f['svg'] for f in drawn['figures']}


def check_svg(svg, figure):
    """The allowlist, then reconciliation: the mark titles are exactly the rows' labels."""
    try:
        tree = ET.fromstring(svg)
    except ET.ParseError as error:
        raise ValueError('a chart SVG is not well formed') from error
    suite.require(tree.tag == SVG_NS + 'svg', 'a chart is not an SVG')
    titles = []
    for element in tree.iter():
        suite.require(element.tag.startswith(SVG_NS) and element.tag[len(SVG_NS):] in ELEMENTS,
                      'a chart SVG holds a disallowed element')
        for name, value in element.attrib.items():
            suite.require(name in ATTRIBUTES and 'url(' not in value.lower() and 'javascript:' not in value.lower(),
                          'a chart SVG holds a disallowed attribute')
            suite.require('NaN' not in value and 'Infinity' not in value, 'a chart SVG holds an undrawable position')
        if element.tag == SVG_NS + 'title':
            titles.append(element.text)
    suite.require(tree.get('aria-label') == figure['title'], 'a chart SVG lost its accessible name')
    suite.require(sorted(titles) == sorted(r['label'] for r in figure['rows']), 'a chart SVG disagrees with its values')


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def build(history_root, *, at, source_root=None, selections=(), out=None, snapshot=None):
    """The bundle {figures, manifest, values}; with `out`, also its files. Raises ValueError.

    `snapshot` (MT4) is one collector snapshot file: it adds PRs an hour against the baseline."""
    records = history.read_all(history_root) if (Path(history_root) / 'samples').is_dir() else []
    natives = prepare.read_natives(source_root, list(selections), at)
    extra = [] if snapshot is None else [prs_per_hour.figure(prs_per_hour.read(snapshot, at))]
    doc = prepare.prepare(records, at, natives, extra)
    svgs = render(doc)
    figures = []
    for f in doc['figures']:
        check_svg(svgs[f['id']], f)
        figures.append(dict(f, svg=svgs[f['id']]))
    renderer = {name: _sha((HERE / name).read_text(encoding='utf-8')) for name in ('render.mjs', 'dom.mjs', 'palette.json')}
    manifest = {
        'schema': MANIFEST, 'built_at': at, 'input_sha256': _sha(json.dumps(doc, sort_keys=True)),
        'history': doc['history'],
        'renderer': {'plot': _locked_plot(), 'package_lock_sha256': _sha((TOOL / 'package-lock.json').read_text(encoding='utf-8')),
                     **{k.replace('.', '_') + '_sha256': v for k, v in renderer.items()}},
        'figures': [{'id': f['id'], 'file': f['id'] + '.svg', 'svg_sha256': _sha(f['svg']), 'kind': f['kind'],
                     'title': f['title'], 'unit': f['unit'], 'window': f['window'], 'coverage': f['coverage'],
                     'gaps': f['gaps'], 'sources': f['sources'], 'rows': len(f['rows'])} for f in figures]}
    values = {'schema': VALUES, 'built_at': at,
              'figures': [{'id': f['id'], 'unit': f['unit'], 'rows': f['rows']} for f in figures]}
    bundle = {'figures': figures, 'manifest': manifest, 'values': values}
    if out is not None:
        write(bundle, out)
    return bundle


def write(bundle, out):
    """All files into a fresh directory first, then moved into `out`: never half a build."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.charts-', dir=out) as staging:
        staging = Path(staging)
        for f in bundle['figures']:
            (staging / (f['id'] + '.svg')).write_text(f['svg'], encoding='utf-8')
        for name, data in (('values.json', bundle['values']), ('manifest.json', bundle['manifest'])):
            (staging / name).write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')
        for path in sorted(staging.iterdir()):
            os.replace(path, out / path.name)


def main(argv=None):
    parser = argparse.ArgumentParser(description='The War room chart build (WRD2).')
    parser.add_argument('--history', required=True, type=Path)
    parser.add_argument('--at', required=True, help='explicit UTC build time; no wall clock is read')
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--selection', type=Path)
    parser.add_argument('--snapshot', type=Path, help='one collector snapshot (collector.v1.md): PRs an hour')
    parser.add_argument('--out', required=True, type=Path)
    a = parser.parse_args(argv)
    try:
        chosen = [] if a.selection is None else suite._decode(a.selection.read_text(encoding='utf-8'))
        chosen = prepare.chart_selections(chosen)
        bundle = build(a.history, at=a.at, source_root=a.source_root, selections=chosen, out=a.out,
                       snapshot=a.snapshot)
    except (ValueError, OSError, UnicodeError, RecursionError) as error:
        print('war-room charts: %s; nothing written' % (error if isinstance(error, ValueError) else type(error).__name__),
              file=sys.stderr)
        return 1
    print('war-room charts: %d figures in %s' % (len(bundle['figures']), a.out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
