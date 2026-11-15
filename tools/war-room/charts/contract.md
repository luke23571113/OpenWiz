# War room chart contract v1

WRD2 (#630), spec #626. The build turns validated history (`openwiz.war-room.v1`
and `openwiz.war-room.v2` samples, read through `history.read_all`) and
explicitly selected native artifacts into finished static SVG figures, a
plotted-values table and a provenance manifest. Its input is the **v2 record as
WRD1 defines it** in [`../contract.v2.md`](../contract.v2.md); v1 samples are
read through the same readers and show health as unobserved (`suite.health`).
WRD3 (#631) consumes this interface: [`input.schema.json`](input.schema.json),
the bundle below and the files `build.py --out` writes.

Fixture proofs are offline. Live sources, complete history and the published
page remain Unverified.

## One build, three steps

```text
history samples ─┐
                 ├─ prepare.py ─▶ chart input (input.schema.json) ─▶ render.mjs (Plot, build only) ─▶ SVG
native artifacts ┘                    │                                                        │
                                      └────────── values.json ◀── build.py checks ──▶ manifest.json
```

1. **Prepare** (`prepare.prepare(records, at, natives)`): select values from the
   validated records and native artifacts, deduplicate repeated observations,
   keep missing days and bases explicit, sanitize every retained text and
   validate the result against `input.schema.json` and its cross-field rules.
2. **Render** (`render.mjs`): Node runs the locked Observable Plot once per
   figure over the prepared rows, with a minimal build-time DOM (`dom.mjs`), and
   writes each SVG. It reads only the prepared input and `palette.json`; it has
   no network or file-write path.
3. **Check** (`build.py`): every SVG passes an element/attribute allowlist (no
   script, link, image, foreign object, event handler, `href`, `url(` or style
   element) and **reconciles with its rows**: the SVG's mark titles are exactly
   the rows' labels, one mark per row. Any refusal fails the whole build.

`build.build(history_root, *, at, source_root=None, selections=(), out=None)`
returns the bundle and, with `out`, writes `<figure id>.svg`, `values.json` and
`manifest.json` there. The CLI is `python3 -I charts/build.py --history DIR --at
UTC [--source-root DIR --selection FILE] --out DIR`. Each figure is rendered
once per build; the page and every image export use those same SVG bytes. The
same input gives byte-identical output.

**Runtime:** the browser receives finished SVG and HTML tables. No Plot, D3,
chart script, hydration, module, font, image or data request reaches the page.

## Inputs

- **History:** every sample in the history root, v1 and v2, validated by
  `history.read_all` (strict JSON, `suite.validate`, the privacy rules).
- **Native artifacts:** selection entries of the same shape as `sources.select`
  (`kind`, `slot`, `path`, `sha256`, `observed_at`, `evidence`). The chart
  build reads only `board_history` (the board's `history.jsonl`, validated row
  by row with the board's own `sources.board_valid_row`); other kinds are
  ignored here and read through history. Each file must stay inside the source
  root, match its SHA-256 and have been observed at or before the build time. A
  selected artifact that fails refuses the build.

A refusal anywhere raises `ValueError`: nothing is written, the page is not
replaced and history is never touched (the build only reads it).

## The prepared input (`input.schema.json`)

`openwiz.war-room.charts-input.v1`: `{schema, built_at, history, figures}`.
`history` counts the samples read by version. Each figure has:

| Field | Meaning |
| --- | --- |
| `id` | `00a`–`00e` for the five headline figures; `body-…` for body figures, stable across builds. WRD3 numbers the body |
| `kind` | `daily-line`, `daily-bar`, `spans`, `bars`, `distribution`, `limits` or `readiness` |
| `title`, `caption` | Fixed sanitized text; one short plain caption |
| `unit` | The native unit, or null for states. A figure never mixes units |
| `window` | The figure's own actual window `{since, until, timezone}`, or null |
| `domain` | The category axis in order: the figure's PST days, slots, stages or metric ids |
| `series` | `{key, label, role}`; `role` picks the palette entry (`primary`, `secondary`, `reference`, `older`, `muted`) |
| `rows` | One plotted mark each: `{key, series, x, x2, y, state, label}` |
| `coverage` | `{observed, expected, missing}` |
| `gaps` | What the figure cannot show, in plain words |
| `sources` | `{slot, metric, path, schema, sha256, evidence, samples}`: each selected observation's source and the sample ids that carried it |

A row's `label` is its accessible mark title and its values-table text. `y` is
the plotted number or null. `state` is the source's (`known`, `partial`,
`unavailable`) or `missing` (no observation for that day or span). A null `y`
is drawn as a labelled text mark ("no sample", "Unknown"), never as zero.
`partial` values are lower bounds or partial evidence and are drawn hollow.

Cross-field rules, checked after the schema: unique figure ids, unique row keys
in a figure, every row's series declared, category rows inside `domain`, at
least one row per figure (an empty figure carries one `unavailable` row naming
its prerequisite), and `coverage.observed` equal to the rows with a value.

## The headline figures

Each keeps its own window: the seven fixed-PST days (08:00 UTC boundaries)
ending at its own latest observed day, labelled with those dates. Missing days
stay in the domain as `missing` rows. A latest day older than the build's PST
day is named in `gaps`.

| Id | Figure | Source and rule |
| --- | --- | --- |
| `00a` | Ready & building | Selected native board `history.jsonl`: per PST `day`, the board's daily row (last `at`, a tie goes to the later line); the synthetic baseline row is skipped. Ready stock, builders running and the board's goal, ready at least `2 × building`, as a dashed reference |
| `00b` | Main merges | `ci_bench` `merged` over native full days only: a `PST-fixed-UTC-08:00` 24-hour window. Other windows are excluded and counted in `gaps`. `factory_metrics`' all-base UTC days are never substituted; they stay a separately labelled body figure |
| `00c` | CI latency | `ci_bench` `queued-to-done-median` and `-p90` per native day, each with its run count. The basis in its label is part of the series: `workflow created to last job completed` is current; any other basis (the older `first job created` cohort) is its own `older` series. No line joins two bases or a missing day |
| `00d` | Runner time | `ci_bench` `robot-minutes` per successful code run, with its run count (the denominator) in every label |
| `00e` | Credit burn | `credits` sampled drops: one span per native credit interval, drawn over its actual start and end, never split at midnight. A span is assigned to the PST day of its end; one that crosses a PST midnight says so. Time between spans is a `missing` gap row. Sampled balance drops are approximate, not billing |

**Repeated observations.** A value repeated across five-minute samples (the
same slot, metric id, native window and source SHA-256; credit spans by their
interval id) is one observation; `sources[].samples` lists every sample that
carried it. A source carried forward as `partial` after a failed read is the
same observation. Two different observations of the same native window keep
the latest observed one and say so in `gaps`. Values are never summed across
samples, medians and p90s are never averaged, and no day is interpolated.

## The body figures

From the latest sample, without new statistics:

- `body-readiness`: every provider (the 17 v1 slots) and the three health slots,
  one cell each, by state. Prerequisites are in the labels.
- `body-main-ci`: the current main result with its head, run and attempt, or
  Unknown (a v1 sample is unobserved).
- `body-ci-queue-count` (bars) and `body-ci-queue-wait` (limits): counts and
  queued waits per exact pool. No source owns a queue limit: each pool has an
  `Unknown` limit row.
- `body-stage-health` and `body-stage-waits` (limits): waits per stage against
  the loaded limit; open or edited waits are lower bounds; held, stale and
  unknown waits have no value.
- `body-journey` (distribution): ready-to-merge hours per ticket.
- `body-<slot>-<unit>` (bars): every other provider's metrics of one unit, by
  metric id, latest sample only. `factory_metrics`' all-base UTC counts are here.

## Colour and shape

`palette.json` holds the role colours, dash and symbol. `palette.py` simulates
protanopia, deuteranopia and tritanopia (Machado et al. 2009, severity 1) on
those colours and requires every pair of series roles to stay apart (CIE76
ΔE ≥ 12) and every mark colour to contrast at least 3:1 with the page ground;
`python3 -I charts/palette.py` prints the inputs and results kept in
`fixtures/charts/palette-check.json`. Dash and symbol differ by role, so no
figure depends on colour alone.

## Synthetic proof

`test_charts.py` owns the cases, on synthetic fixtures in `fixtures/charts/`.
They prove the build at the generated SVG and values boundary, not live data.
