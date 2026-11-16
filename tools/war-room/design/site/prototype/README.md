# WRD5 (#883) design prototypes: throwaway, not the build

Real HTML prototypes of the home page and one child page (Health), per the
orchestrator's ruling on #883: design targets are HTML prototypes, never generated
pictures. Built from the synthetic content packet (`fixtures/page-design/packet.py`,
2030-01-14) through the real chart build and `page.py` helpers; every value is
synthetic. Chart SVGs, data and marks are unchanged.

Captured in real headless Chromium with scripts off: the first screen at 1440 × 900
and 390 × 844 (the sizes of the posted before captures), and the full page at 1440 and
390 CSS px through `fixtures/page-design/probe.mjs` (no horizontal overflow at either
width, with every disclosure closed or open; keyboard reaches and opens a disclosure).

What the prototype shows:

- Six-page navigation (Home, Speed, Health, Cost, Quality, Skills and evals), native links.
- Each figure's face: title, one plain sentence, and its value or chart. Unavailable
  figures say Unavailable, with the prerequisite only when it is one short line.
- Dates, coverage, gaps, unit notes, values tables and provenance move into each
  figure's closed "Values and sources" disclosure; the status strip's gaps fold into
  one closed disclosure.
- Home's every-benchmark list, worst first: off limit, partial, healthy, not measured;
  inventory order breaks ties. Each row links to its figure.

Page membership, row values and states here are prototype choices for review; the
build will derive them from `benchmarks.json` and the saved sample.
