# Setup-onboard contract proof (#632)

All values in the proof inputs are synthetic. This proves interface consistency
and CI registration only: no installation, sign-in, App, saved secret, init,
timing, action count or merge is proven.

**History.** This proof was built in the private ClosedWiz repository as
[ClosedWiz #2940](https://github.com/jparker2006/ClosedWiz/issues/2940) (its PR
[ClosedWiz #2970](https://github.com/jparker2006/ClosedWiz/pull/2970)) and moved unchanged to OpenWiz as #632 and PR #644. The
commit ids below are ClosedWiz commits from before that move; they are kept as
the historical record and are not in this repository's history, where the move
landed as one commit. The logs below are those runs' unchanged output.

## Red first

`red-run.log` is the original failing-first run, committed in
ClosedWiz `8d6f156fd68ae5bd97ead80d4b4ee088bbbba26a` with the contract, schemas, fixtures
and tests and an accept-all `check.py` stub. 18 tests ran: 151 failures and one
error. The failures are the claims' own assertions (every example and variant
gives the wrong codes, the code table is empty, credentials pass, weak setup
views validate); the error is AC2's red: `setup.v1.schema.json` had no
`identity` field yet. Checkout paths are replaced with `<checkout>`.

`red-pattern-anchor.log` is a later mutation replay, not a chronological red:
with the finished checker's end-of-string anchoring temporarily undone, the
trailing-newline case fails three subtests; restored, it passes. It shows the
checker and JSON Schema refuse the same pattern values.

## Proof mapping

| Ticket criterion | Contract/fixture evidence |
| --- | --- |
| AC1: shapes without granting effects or guessing transport | `contracts/setup-onboard.v1.schema.json` (six kinds), one example of each; the upstream save-secret interface is named without a command |
| AC2: compatible setup, identity and CLI expansion; private user App, explicit factory App | `setup_views` validated against the expanded `setup.v1.schema.json` (old and new forms, both directions); the identity pin is unchanged and checked; user/factory visibility and owner-account variants |
| AC3: refuse ambiguous visibility, fake App verification, cross-account private App, duplicate or uncertain effects, leaked credentials, weak merge evidence, missing actions, synthetic/live confusion | 106 variants with hand-written expected codes, plus in-memory planted credentials in four document kinds |
| AC4: 29:59.999 with five actions can qualify; 30:00, six actions or a missing count cannot; first-hour measures unchanged | `Limits` tests on the receipt made live in memory; the first-hour schema still pins `3600000`, and this schema has no ten-minute field |
| AC5: registered offline checks; future runtime as labelled seams | `setup_onboard_contract_passes` in `tests/checks/skills.rs` (always lane) and `release:setup-onboard-contract` in the release lane; the contract's Seams table names each later ticket |

`scoped-checks.log` records the scoped local checks at the hand-back implementation commit (ClosedWiz `ffbdf22c7`): format, the checks binary (145 passed, including `setup_onboard_contract_passes`), this suite, the first-hour and identity contract suites, and the CI selection suite. No crate code changed, so no crate clippy run applies.

Helpers: none for this ticket; no swarm window.
