# #873 real-page screenshots

Captured with `skills/image/scripts/screenshot.py` (390 x 844 and 1440 x 900) from `apps/web/out` built at this branch, served by `capture-stub.mjs` (`node capture-stub.mjs apps/web/out 7392 new`). The stub answers only `GET /api/v1/setup`, with a synthetic six-component report (five verified, phone access unknown); every other API route answers 503.

- Setup (`/setup`): matches the target: six rows, no Engine panel, "Connections verified. Next, give one small idea to the OpenWiz onboarding skill.", footer "No agents have been started."
- First hour (`#first-hour`): "Connect your accounts" is done with "Setup reports every connection verified." and no engine wording, as in the target. The idea, plan, build and merge steps differ from the target only because Decisions and Fleets are not served here; the target's "your turn" idea state is proven on fixtures by `test/browser/first-hour-pages.test.mjs` (state `start`).
