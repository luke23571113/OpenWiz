VERDICT: CHANGES at 1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d

Final check by Codex, Sol 6.1, High. CI green on this commit: ci.

- **R1 [blocking]** Logged as follow-up #4310 at the re-check.
  User path: a cook exports twice in one day; the second export silently replaces the first, and the first is lost.
- **R2 [blocking]** still open after 2 rounds: the token is still written on the retry path.
  Risk: privacy: any reader of the log sees a live token.
- **R4 [blocking]** resolved at 9e8d7c6: the refusal now exits with status 3.

- **Ruling 1** upheld: the ticket's "existing destination" covers folders.
- **Ruling 2** overturned as R4: the CLI contract gives every refusal status 3.

Next: park R2 as a decision for Jake.
