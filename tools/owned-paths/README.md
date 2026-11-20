# Owned paths (#1418)

CI fails a pull request that edits a file outside its ticket's owned paths, so the reviewer doesn't have to catch it by reading.

```sh
python3 tools/owned-paths/check.py --pr N                    # a pull request, as CI checks it
python3 tools/owned-paths/check.py --ticket N [--base REF]   # this branch, before you push (default base origin/main)
python3 -I tools/owned-paths/test_check.py                   # its proofs, on synthetic fixtures and a fake gh
```

It reads GitHub only through `gh api graphql`. In CI it is the `owned-paths` job in `.github/workflows/ci.yml`, with the workflow's own read token.

## What covers a file

- **The linked tickets' `## Owned paths`** for this repository, parsed as build-ticket's `ticket.py` parses them: each bullet's backticked paths, bound to its `` in `owner/name` `` qualifier or else to the ticket's repository. Shared and annotated bullets count as owned. A path ending in `/`, or naming a folder, covers everything under it; `*` matches within one folder, `**` across folders.
- **"X and its tests"** (#1639): an owned path whose backticks are followed by "and its tests" or ", plus its tests" (or with that wording inside them), ending the bullet or followed only by `` in `owner/name` `` and a `(...)` annotation, also covers X's tests beside it. With X's folder `D`, X's stem `S` (its name before the first dot) and `D`'s own name `F`, those are:
  - a test file directly in `D`, `test_*.py`, `*_test.py`, `*.test.ts`, `*.test.tsx`, `*.test.mjs`, `*_test.rs` or `*_tests.rs`, whose name, without that test marker and extension, has `S` or `F` as a word (`tools/install/test_install.py` for `tools/install/harness.py`);
  - any file under `D/tests/` or `D/test/` whose path below that folder, without a test file's marker and extension, has `S` as a word;
  - `D/S/tests.rs`, a Rust module's tests.

  A word is a part of the name split at `_`, `.`, `-` and `/`, never `test` or `tests` itself. "And its tests are excluded …" covers nothing. A non-test file beside X, another module's tests and a glob's tests stay outside, and a path without that wording keeps the rule above. The output names what admitted each file: `owned: <file> (tests of `X`)`, or `(by `<path>`)` for the rest.
- **The standing supporting-edit rule** in `docs/agents/fleet.md` (read at the pull request's base, never its head): the backticked paths of its numbered kinds, with `<ticket>` read as the linked ticket's number.
- **An `F4 supporting edit granted` comment** on the ticket or the pull request from a record author (the `Record authors` row of `docs/agents/fleet.md`'s `## GitHub identity` table): every backticked path after the marker, unless the grant names only other repositories.

A file none of these covers fails the check, named with the ticket. Move it out, or ask on the ticket for a grant that names the path in backticks. Prose a check can't read (a bullet with no backticked path, "and its schema") covers nothing.

## Linked tickets

GitHub's closing references, and `Closes`, `Fixes`, `Resolves` or `Part of` followed by `#N`, `owner/name#N` or the issue's URL. Only this repository's issues are checked; a ticket in another repository is noted. A pull request that links no ticket, or only issues without an `## Owned paths` section, passes with a note.

The job runs on the pull request's own events (opened, pushed, reopened, ready for review). Editing the body or adding a grant starts no run: re-run the job.
