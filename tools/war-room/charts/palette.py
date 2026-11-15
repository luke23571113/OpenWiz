#!/usr/bin/env python3
"""WRD2 (#630): the chart palette and its colour-vision check. Python standard library only.

Simulates protanopia, deuteranopia and tritanopia with Machado, Oliveira and Fernandes
(2009) at severity 1.0 on linear sRGB, then requires every pair of series roles to stay
apart (CIE76 ΔE in CIELAB, D65) and every role to contrast with the ground (WCAG 2).

    python3 -I charts/palette.py     print the inputs and results (fixtures/charts/palette-check.json)
"""
import itertools
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
VALIDATOR = 'Machado 2009 CVD simulation, severity 1.0, linear sRGB; CIE76 delta E in CIELAB D65; WCAG 2 contrast'
MACHADO = {
    'protanopia': ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    'deuteranopia': ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    'tritanopia': ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
}
DEFAULTS = {'delta_e': 12, 'contrast': 3}


def load():
    return json.loads((HERE / 'palette.json').read_text(encoding='utf-8'))


def _linear(hex_colour):
    if not (isinstance(hex_colour, str) and len(hex_colour) == 7 and hex_colour[0] == '#'):
        raise ValueError('a palette colour is #rrggbb')
    channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]


def _simulate(rgb, matrix):
    return [min(1.0, max(0.0, sum(matrix[i][j] * rgb[j] for j in range(3)))) for i in range(3)]


def _lab(rgb):
    x = (0.4124 * rgb[0] + 0.3576 * rgb[1] + 0.1805 * rgb[2]) / 0.95047
    y = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    z = (0.0193 * rgb[0] + 0.1192 * rgb[1] + 0.9505 * rgb[2]) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116
    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def _luminance(rgb):
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def check(palette):
    """The validator's inputs and results; `pass` only when every view and contrast passes."""
    limits = dict(DEFAULTS, **palette.get('thresholds', {}))
    roles = palette['roles']
    simulations = {}
    for name, matrix in [('normal', None)] + list(MACHADO.items()):
        lab = {k: _lab(_linear(v) if matrix is None else _simulate(_linear(v), matrix)) for k, v in roles.items()}
        distance, a, b = min((sum((p - q) ** 2 for p, q in zip(lab[a], lab[b])) ** 0.5, a, b)
                             for a, b in itertools.combinations(sorted(lab), 2))
        simulations[name] = {'min_delta_e': round(distance, 2), 'closest': [a, b], 'pass': distance >= limits['delta_e']}
    ground = _luminance(_linear(palette['ground']))
    contrast = {}
    for role, colour in sorted(roles.items()):
        mark = _luminance(_linear(colour))
        contrast[role] = round((max(mark, ground) + 0.05) / (min(mark, ground) + 0.05), 2)
    return {'validator': VALIDATOR, 'inputs': {'ground': palette['ground'], 'roles': dict(sorted(roles.items()))},
            'thresholds': limits, 'simulations': simulations, 'contrast': contrast,
            'pass': all(s['pass'] for s in simulations.values()) and all(c >= limits['contrast'] for c in contrast.values())}


if __name__ == '__main__':
    result = check(load())
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result['pass'] else 1)
