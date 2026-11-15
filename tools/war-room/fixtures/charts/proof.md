# WRD2 proof record (#630)

Synthetic fixtures only. No live source, page or publication is claimed. The chart
input is WRD1's v2 record (`../../contract.v2.md`); v1 samples read as health unobserved.

| Claim (AC) | Evidence | Kind |
| --- | --- | --- |
| Plot locked and recorded, build only, one direct dependency (1) | `../../package.json`, `../../package-lock.json`, `../../dependencies.md` | Review |
| Chart contract binds values/windows/units/coverage to SVG, values and manifest; selection validated, text sanitized (2) | `../../charts/contract.md`, `../../charts/input.schema.json`; `test_bad_native_input_refuses_the_whole_build`, `test_pages_and_svgs_carry_no_chart_runtime_and_escape_text` | Fixture test |
| Five headline definitions and generic body figures (3) | `test_main_merges…`, `test_ci_latency…`, `test_runner_time…`, `test_ready_and_building…`, `test_credit_spans…`, `test_body_figures…` | Fixture test |
| Computed once; the same bytes serve page and export; no chart runtime (4) | `test_same_input_builds_the_same_bytes_used_by_page_and_export`, `test_pages_and_svgs_carry_no_chart_runtime…`, `test_the_svg_check_refuses_planted_breaks` | Fixture test |
| Missing days, repeats, old cohorts, censored waits and bases stay explicit; no averaged quantiles (5) | The headline tests above; `test_body_figures…` (open and held waits) | Fixture test |
| Accessible names, labels, units, tables and validated colour/shape survive no-script viewing at both widths (6) | `test_every_figure_draws_one_titled_mark_per_value_row`, `test_charts_survive_a_browser_without_scripts_or_network`, `test_the_palette_survives_colour_vision_simulation`, `palette-check.json`, `browser-1440.png`, `browser-390.png` | Fixture test, browser capture |
| Bad input or build failure keeps the last good page and history; PNG publication works with SVG (7) | `test_a_failed_chart_build_keeps_the_last_good_page_and_samples`, `test_a_refused_chart_build_publishes_nothing`, `test_the_png_drawing_accepts_a_page_with_charts`; `test_publish.py` and `test_gather.py`'s real-chromium draws pass with figures embedded | Fixture test |

Red runs, each committed before its fix: `red-first.log` (every chart proof against the
contract stubs), `red-publish.log` (a publication without Node published anyway),
`red-limits.log` (a limits figure crashed the renderer; found by `test_gather.py`'s
real-shaped queue data). Green: `green.log`.

Review 1 (R1–R5 at `a482ae0`): `red-review-1.log` holds each finding's own red before
its fix. Equal held waits refused the whole build (R3); main CI drew `known` for every
result (R1); gather's projected board left 00a empty (R2); credit coverage counted
spans against days (R4); an extra-only seed span joined the full-balance series (R5).
R1, R2, R4 and R5 were run without the R3 row, because that row alone fails the shared
setup at `a482ae0`. `green.log` is the fixed head's run.

R3 re-check (`92ae903`): native stage interval keys end in timestamps, so a label that
kept only the id's last segment collided (`…08:50:00z` and `…08:55:00z` both gave
`00z`). `red-review-2.log` is that red on the strengthened fixture. Labels now carry the
whole observation id.

The browser captures come from `capture.py OUT_DIR` (real Chromium, every host
unresolvable, the page's own `default-src 'none'` CSP) at 1440 and 390 CSS px wide,
full figure section; re-running it gives byte-identical PNGs. Headless Chromium cannot
dump a page with `scriptEnabled=false`, so the no-script proof is the CSP plus a planted
canary script that must not run.

Helpers: none were started; every line was written and checked by the builder.
