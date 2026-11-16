VERDICT: CHANGES at 9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2f1e0d

Re-check by Codex, Sol 6.1, High. CI green on this commit: ci.

- **R1 [blocking]** still open after 1 round: a second export still replaces the first. Logged as follow-up #4310.
  User path: a cook exports twice in one day; the second export silently replaces the first, and the first is lost.
- **R2 [blocking]** still open after 1 round: the token is still written on the error path.
  Risk: privacy: any reader of the log sees a live token.
- **R3 [polish]** Polish issue: #4302.
- **R4 [blocking]** resolved at 9e8d7c6: the refusal now exits with status 3.

- **Ruling 1** upheld: the ticket's "existing destination" covers folders.
- **Ruling 2** overturned as R4: the CLI contract gives every refusal status 3.

Next: a fresh, stronger builder fixes R2 once, then one final check.
