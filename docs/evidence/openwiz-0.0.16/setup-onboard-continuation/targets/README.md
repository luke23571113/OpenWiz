# First-hour continuation targets (#636)

Design targets made before the visible copy change, synthetic data only. They are
pictures to compare against, not proof of how the real page renders.

- **State:** the First hour page with every connection verified and no engine
  selected. Step 2, "Connect your accounts", reads `done` and names the acting
  identity. `skip-*` shows the explicit App skip (personal login acts); `app-*`
  shows the user's own App. Step 3 is the next step; no text mentions an engine.
- **Viewports:** described at 390 CSS px (phone, no sidebar) and 1440 CSS px
  (desktop, sidebar). The rasters are 856 and 1487 pixels wide; the generator does
  not emit CSS pixel sizes.
- **Route:** OpenAI's built-in image generation through a Codex helper on Sol 6.1
  at medium effort, as the image skill says. The generated PNGs were re-encoded
  as JPEG (quality 72) with headless Chromium to keep the repository small.
- **Prompts:** `prompts.txt`, one per picture, with the exact copy.
- **Scope:** copy only, inside the existing first-hour step layout; no redesign.
  The reviewer compares phone and desktop screenshots of the real page in the
  matching fixture states (`connections-skipped`, `connections-app` in
  `apps/web/test/fixtures/first-hour-pages/states.mjs`).
