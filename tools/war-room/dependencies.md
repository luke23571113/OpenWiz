# War room chart dependencies (WRD2, #630)

**Purpose: build only.** Node runs the locked Observable Plot once per figure at build
time (`charts/render.mjs`) to draw static SVG. No package, script or module reaches the
page: browsers get finished SVG and HTML tables. Installed with
`npm ci --ignore-scripts` in `tools/war-room/` into `node_modules/` (git-ignored).

**Approval:** Observable Plot is approved for build-time charts in spec #626
("Observable Plot is already approved by Jake in the grill"; private record pointer as
in the spec: https://github.com/jparker2006/ClosedWiz/pull/2869#issuecomment-6871067954).
It is the **only direct dependency**. No D3 module or other helper is a direct dependency:
Plot's transitive packages below are installed because Plot requires them, and the
renderer imports only `@observablehq/plot`. The build-time DOM Plot needs is our own
`charts/dom.mjs`, so no DOM package (jsdom, linkedom) is added. Any other direct helper
needs its own decision first.

Node 24.22.1 (the repository's pinned Node). `package-lock.json` lockfileVersion 3,
42 packages: 1 direct, 41 transitive. No install scripts run (`--ignore-scripts`).

| Package | Version | Licence | Kind | Integrity (prefix) |
| --- | --- | --- | --- | --- |
| `@observablehq/plot` | 0.6.19 | ISC | direct | `sha512-8Tg8+doIBD…` |
| `binary-search-bounds` | 2.0.5 | MIT | transitive | `sha512-H0ea4Fd3lS…` |
| `commander` | 7.2.0 | MIT | transitive | `sha512-QrWXB+ZQSV…` |
| `d3` | 7.9.2 | ISC | transitive | `sha512-ZKb/mONPVK…` |
| `d3-array` | 3.2.5 | ISC | transitive | `sha512-Th8qGXoBal…` |
| `d3-axis` | 3.0.1 | ISC | transitive | `sha512-E5QCXfaf/u…` |
| `d3-brush` | 3.0.1 | ISC | transitive | `sha512-L5Glqa/Gb7…` |
| `d3-chord` | 3.0.2 | ISC | transitive | `sha512-cGmADo5M2P…` |
| `d3-color` | 3.1.1 | ISC | transitive | `sha512-lfab8x0Bj0…` |
| `d3-contour` | 4.0.3 | ISC | transitive | `sha512-5DYURc8KwX…` |
| `d3-delaunay` | 6.0.6 | ISC | transitive | `sha512-DMQIEvSJhZ…` |
| `d3-dispatch` | 3.0.2 | ISC | transitive | `sha512-sAzH4Y4nsL…` |
| `d3-drag` | 3.0.1 | ISC | transitive | `sha512-OWeoayCq8J…` |
| `d3-dsv` | 3.0.2 | ISC | transitive | `sha512-FUnXhX7I4/…` |
| `d3-ease` | 3.0.2 | BSD-3-Clause | transitive | `sha512-B5znKqRmKR…` |
| `d3-fetch` | 3.0.2 | ISC | transitive | `sha512-1wGF62bgjM…` |
| `d3-force` | 3.0.1 | ISC | transitive | `sha512-kAaaHLFebB…` |
| `d3-format` | 3.1.3 | ISC | transitive | `sha512-+F+/49swqm…` |
| `d3-geo` | 3.1.2 | ISC | transitive | `sha512-5R8ZgDQorI…` |
| `d3-hierarchy` | 3.1.3 | ISC | transitive | `sha512-GRajN5ZcnE…` |
| `d3-interpolate` | 3.0.2 | ISC | transitive | `sha512-IRzGU62Dtx…` |
| `d3-path` | 3.1.1 | ISC | transitive | `sha512-jsbgV8zIT3…` |
| `d3-polygon` | 3.0.2 | ISC | transitive | `sha512-WAUvPudGU1…` |
| `d3-quadtree` | 3.0.2 | ISC | transitive | `sha512-9Lu9mqJKRb…` |
| `d3-random` | 3.0.2 | ISC | transitive | `sha512-PxJi9LNV+7…` |
| `d3-scale` | 4.0.3 | ISC | transitive | `sha512-66cWobCNzc…` |
| `d3-scale-chromatic` | 3.1.1 | ISC | transitive | `sha512-lA5gfN2yMv…` |
| `d3-selection` | 3.0.1 | ISC | transitive | `sha512-ODSf35vqCr…` |
| `d3-shape` | 3.2.1 | ISC | transitive | `sha512-dm2o+lbKdz…` |
| `d3-time` | 3.1.1 | ISC | transitive | `sha512-Ze7rjrhMzd…` |
| `d3-time-format` | 4.1.1 | ISC | transitive | `sha512-22XaqjyCjp…` |
| `d3-timer` | 3.0.2 | ISC | transitive | `sha512-1Il1aliroV…` |
| `d3-transition` | 3.0.2 | ISC | transitive | `sha512-RcjCsdFgyF…` |
| `d3-zoom` | 3.0.1 | ISC | transitive | `sha512-kfjD3BDQu/…` |
| `delaunator` | 5.1.0 | ISC | transitive | `sha512-AGrQ4QSgss…` |
| `iconv-lite` | 0.6.3 | MIT | transitive | `sha512-4fCk79wshM…` |
| `internmap` | 2.0.3 | ISC | transitive | `sha512-5Hh7Y1wQbv…` |
| `interval-tree-1d` | 1.0.4 | MIT | transitive | `sha512-wY8QJH+6wN…` |
| `isoformat` | 0.2.1 | ISC | transitive | `sha512-tFLRAygk9N…` |
| `robust-predicates` | 3.0.3 | Unlicense | transitive | `sha512-NS3levdsRI…` |
| `rw` | 1.3.3 | BSD-3-Clause | transitive | `sha512-PdhdWy89Si…` |
| `safer-buffer` | 2.1.2 | MIT | transitive | `sha512-YZo3K82SD7…` |

Licences: ISC (Plot, D3 and most of its modules, delaunator, isoformat, internmap),
MIT, BSD-3-Clause (`d3-ease`, `rw`) and Unlicense (`robust-predicates`); all permissive.
The full integrity hashes and resolved URLs are in `package-lock.json`.
