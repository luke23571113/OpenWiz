# #1335 (FF5): fast CI evidence

## Red first

- [red-resolve.log](red-resolve.log): `test_trace.py Repo` before the
  `resolve.py` fix. Library artifacts, a registry crate, a shared test name,
  an uplifted program, a read through a skill link, and (second slice) an
  example's hashed unit each fail at the claim's own assertion, as "a build
  product it can't trace".
- [red-select.log](red-select.log): `test_pick.py Synthetic PullRequestPlan`
  before the `pick.py` and `steps.py` changes. New docs and skills are full
  runs (`unknown_path`). A docs-only and a skills-only pull request plan the
  Rust, web and export jobs.

## Why Rust never skipped (observed)

The nightly map on `main` (run 44367525793, the `select-map` job's log) mapped
94 tests and left out 19: every Rust test, and one browser test that runs a
Rust program. Each was "a build product it can't trace to its sources": a
registry or workspace library's `lib<crate>-<hash>.rlib`/`.rmeta`, or a test
binary whose name two packages share. `rust:test:checks` reads git's objects
and stays left out (it runs in the always lane).

Of 56 recent pull-request plans (first attempts), 55 were full runs. The
reasons: CI files changed on `main` since the signed map (drift: `ci_change`),
and new files the map can't place (`unknown_path`), mostly new docs and
evidence.

## Local trace after the fix

On a local checkout at the fix commit, with Rust 1.99.1 and
`strace`, `trace.py rust` mapped `rust:lib:openwiz-adapter-cloudroom`,
`openwiz-adapter-github`, `openwiz-cli`, `openwiz-core`, `openwiz-server`,
`openwiz-store` and `rust:test:attachments` (all left out on main before). The
local run was stopped after these; the pull request's own CI run traces every
test (it changes the tracer) and its `select-map` artifact is the full map.
Every build product of a full local `cargo test --workspace --no-run` and the
release example (132 files under `target/`) resolves.

## Helpers

None: the ticket names no helper agents.
