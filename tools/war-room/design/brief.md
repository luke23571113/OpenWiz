# War room v3: frozen design brief (WRD3, #631)

The public inputs the page was built to, and that every hill-climb builder and
judge gets unchanged for a stretch. Rubric version **v3-r1**. Private originals,
exact decision words, evaluation material and controller records stay in the
private repository (`private/evidence/war-room-redesign/`). This brief carries
only plain public constraints and record pointers.

## Pins

| What | Pin |
| --- | --- |
| Spec and ticket | #626 (revision 3), #631 |
| Accepted direction | v3 pair on private PR #2887 at `d8d22a6702eaf1340115ee359c8323e1210aa5f5`: desktop 1440 × 1025 (SHA-256 `2cd718945ceb4e4fc1c0199b03e11bff2374cd9e3c73e1513cd5e1905442b7ba`), phone 390 × 1170 (SHA-256 `cb03fcd797e7897a7f818763d8b3227fa7afdbfcf4f9cba629ec241bb8e4c666`). Not a page asset, never copied here |
| Decision record | Jake, 2026-11-14: health and throughput lead, option 2's five charts, build-time Plot, v3 with the C-style body and short plain captions ([private record](https://github.com/jparker2006/ClosedWiz/pull/2869#issuecomment-6871067954)) |
| Starting page | `tools/war-room/page.py` at `ccb874eaf64668bd7d92c57f3391b623eac80104` (main after #630) |
| Content packet | [`fixtures/page-design/packet.py`](../fixtures/page-design/packet.py), synthetic, built through the real history and chart path |
| Inventory | [`benchmarks.json`](../benchmarks.json) |
| Heading font | Oswald 4.103 Bold, Basic Latin, data-embedded (J85; [`assets/README.md`](../assets/README.md)) |

## Taste brief

- **Hard rules:** dark only, black ground. Every chart mark comes from measured
  rows, never from the target's illustrative geometry or numbers. No cockpit
  content: no waiting-on-Jake panel, request wording or answer control. No
  script, remote font, image or data request. Unknown is never drawn as zero or
  as green.
- **Explicit preferences** (Jake, 2026-11-14, private record above, in my words):
  a deep-blue engraved citadel masthead; condensed uppercase headings; black
  surfaces with crisp white rules and square figure borders; restrained white
  and blue chart marks; compact mono labels; five chart cards in one row on
  desktop, each stacked and composed on its own on the phone; numbered figures,
  each with one short plain caption.
- **Observed patterns in v3** (not requirements): the masthead takes the top
  quarter; the status strip reads as one big phrase, then a fact line; card
  captions are a short uppercase line under a rule; body figures have mono
  titles over a rule.

## Surface brief (app)

- **Person:** Jake, at a desk or on a phone, checking the factory.
- **Task:** see how healthy the factory is and how fast it is going, then find
  any benchmark.
- **Main question:** is anything wrong right now, and is throughput steady?
- **Important finding:** the status strip's evidenced anomalies and gaps.
- **Next action:** read a card, or open a figure's values and sources. The page
  has no controls.

## Design specification

| Role | Decision |
| --- | --- |
| Headings (h1–h3) | Oswald WR 700, uppercase; h1 104 px desktop / 56 px phone; section h2 64 / 44 px; card h3 22 / 18 px |
| Values | Nimbus Sans / Helvetica / Arial bold (system), 32 px desktop / 26 px phone |
| Labels and body | DejaVu Sans Mono / Liberation Mono, 12–17 px, uppercase with tracking for labels |
| Colour roles | ground `#000`; ink `#f2f5f8`; soft `#b9c3cf`; muted `#8d97a5`; blue `#4da3ff` (focus, links, gap markers); chart roles from `charts/palette.json` |
| Rules | 2 px ink rules and borders; 1 px `#3a4250` table rules |
| Layout | max 1440 px; 24 px gutters desktop, 10 px phone; cards in 5 columns, 14 px gap; body figures in 2 columns; one column under 760 px |
| Charts | the chart build's SVGs, unchanged; cards drawn at 260 × 180, body figures at 440 wide and never shrunk below it on desktop |
| Readability floor | chart text at least 8.5 CSS px as drawn, at both standard widths |
| Phone | the masthead art sits behind the title's right; each card puts its value beside its title |

Measured text pairs on the page ground (WCAG 2 contrast, required 4.5:1):
ink 19.19, soft 11.77, muted 7.1, blue 8.0 against `#000`. The chart palette on
the page ground is rechecked in
[`fixtures/page-design/palette-page.json`](../fixtures/page-design/palette-page.json)
(protanopia, deuteranopia and tritanopia simulations, ΔE ≥ 12, marks ≥ 3:1).
The browser proof measures every visible text pair as rendered.

## Content packet

`packet.py` writes eight five-minute samples (one v1, seven v2) and a board
history, then runs the real chart build at 2030-01-14T10:00Z. It covers low ready
stock, a missing CI day (01-10), an older CI cohort (01-07), a re-measured day
(01-12), a credit span across a PST midnight and a rise counted as zero, a
failed main CI run, a partial queue wait, an open and a held stage wait, one
unknown merge direction, and 11 of 20 benches unavailable with their
prerequisites. `packet.json` records the chart input and page SHA-256 of each
run.

## Hill-climb run plan (not started)

Fixed by the ticket. Nothing here starts a round: rounds wait for the
orchestrator to confirm spending and thread authority on #631.

- **Schedule:** one resumable round wake every 30 minutes (a CloudRoom Loop,
  only once authorized); at most two fresh candidate threads per round; a Jake
  checkpoint after every three completed candidate rounds; a stall at three
  completed unchanged selected-winner rounds. No total round, token, time or
  spend cap is implied.
- **Builders:** cheap rounds use Codex `gpt-6.1-terra` and Claude Haiku 5.5;
  checkpoint candidates use Codex `gpt-6.1-sol` and Claude Opus 5.5. Routes are
  verified before use. Each candidate changes one concrete visual issue from the
  best-so-far commit, inside `page.py`'s CSS and markup, `assets/citadel.css`
  and this brief's fixed roles.
- **Council:** three judges across at least two families, fresh contexts,
  frozen categories hierarchy, typography, colour and contrast, consistency,
  clarity. They see blind desktop/phone pairs, never builder identities, earlier
  scores or the stop. v3 and any authorized, pinned reference screenshots are
  scored beside candidates. The cheapest judge runs first.
- **Eligibility:** `test_page_design.py`, `test_charts.py` and `test_publish.py`
  pass, plus a held-out check kept in the controller's private workspace. A
  failed check excludes a candidate from taste judging.
- **Round 0:** this page, unchanged, captured from the packet at 390 × 844 and
  1440 × 900 (full page), plus 390 × 1170 and 1440 × 1025 for target comparison.
- **Isolation:** controller and judge files stay outside candidate exports;
  denied read/write probes and a planted bad candidate are verified before
  round 1. Unreadable candidate logs stop the run.
- **Records:** every round keeps target, prompt, commit, both screenshots,
  capture manifest, critique passes, scores and decision, including crashes and
  losers. Checkpoints show Jake the best three eligible candidates with letters,
  annotated before/after screenshots and the score table. His picks are
  recorded here in my own words, with the date and a private-record pointer.
  A pending checkpoint is not completion; a final Jake visual checkpoint is
  required before the page is called accepted.

## Changes to this brief

None yet. A checkpoint choice starts a new stretch and rubric version here; the
earlier version stays.
