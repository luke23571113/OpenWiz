# #873 target brief: Setup and First hour without the engine step

## Taste brief
Project and surface: OpenWiz web view, Setup page (`/setup`) and First hour (`#first-hour`).
Hard rules: dark only; the existing design system (Inter-like sans, near-black surfaces, soft rounded panels, gold for attention, glyph tiers: check = verified, gold diamond = needs you, dashed circle = unknown); compact on phone, room on desktop.
Observed patterns (not requirements): terminal-like structure, one gold-bordered "next" panel.
This is a small change (rows and panels removed, wording changed), not a new screen or flow.

## App brief
Person: a new owner who just installed OpenWiz (synthetic).
Task: finish connecting tools before starting a first fleet.
Scope: the setup report of one synthetic project, `synthetic-owner/first-idea`.
Main question: are my connections done, and what is next?
Important finding: every connection is verified; phone access is still unknown (optional, reported only).
Next action: give one small idea to the OpenWiz onboarding skill. There is no engine choice anymore.

## Design specification (what changes, what stays)
- Setup prerequisites list: six rows, in order CloudRoom, Agent harness, Personal GitHub, OpenWiz GitHub App, Project (all "verified", check glyph), Phone access ("unknown", dashed circle). **No Engine row.**
- Right column: gold-bordered panel "Connections verified" / "Next, give one small idea to the OpenWiz onboarding skill. Nothing starts without your approval." Then the unchanged Cost panel. **No Engine panel.**
- Footer: "No agents have been started." with the Refresh button. Never the word "engine".
- First hour, step "Connect your accounts": "done" with check glyph, "Setup reports every connection verified." Step "Give your first idea": gold diamond, "your turn". **No "Choose where the engine runs next."**
- Everything else (header, navigation, spacing, type, colours, Cost wording) stays exactly as on `main`.
- Phone (390 CSS px): single column, the prerequisites list first, then the next panel, the cost panel, the footer.

## Content packet (synthetic)
| Component | State | Reason |
| --- | --- | --- |
| CloudRoom | verified | CloudRoom is signed in on this host. |
| Agent harness | verified | Claude Code is listed with its model and effort. |
| Personal GitHub | verified | synthetic-owner can push to synthetic-owner/first-idea. |
| OpenWiz GitHub App | verified | The OpenWiz GitHub App can reach synthetic-owner/first-idea. |
| Project | verified | synthetic-owner/first-idea is set up with CI and review. |
| Phone access | unknown | Authenticated phone access has not been verified. |

First hour steps: Install OpenWiz (done), Connect your accounts (done), Give your first idea (your turn: "Give one small idea to the OpenWiz onboarding skill. Nothing is created without your yes."), Confirm the spec and approve the plan (waiting), Watch the fleet build (waiting), First verified merge (waiting).
Empty/missing cases are covered by the existing tests; this target shows the all-verified state, the one where the engine step used to appear.

## Generation route
One image helper (Codex, Sol 6.1, medium effort) used its built-in OpenAI image tool, with the four `ref/` screenshots of `main` (72374af, synthetic setup report, served by a stub) passed as references. Its exact per-picture prompts are in `generated-prompts.md`. Raster sizes differ from the CSS widths (1440 and 390); the pictures are design targets, not screenshots. The First-hour targets keep the reference's failed fleet read (the "Unknown" panel and "error" status) because only the Setup report was stubbed; those parts are unchanged by this ticket.
