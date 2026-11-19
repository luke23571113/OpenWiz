# OpenWiz

## What this is

OpenWiz is developed in the public repository `openwizdev/OpenWiz`; ClosedWiz stays private for exact decision words, grills, live evidence, machine details and orchestration state. These instructions are prepared in ClosedWiz until the separately approved cut-over; this edit activates nothing. See the [open development contract](contracts/open-development.v1.md). OpenWiz 0.0.1 is one outcome: a read-only Rust inventory of real CloudRoom sessions, read through `room-cli`.

**The app lives at [openwiz.dev/app](https://openwiz.dev/app).** This repository is the command, the adapters and the engine (spec #1223); the old web view, the act-from-the-UI pieces, the site copy, the server, the service and the store went in #1264.

**Build and acceptance are separate.** The 0.0.1 inventory is implemented; the 0.0.3 send and 0.0.4 new-thread and attachment commands went in #1264. 0.0.5 was accepted with recorded gaps ([#106](https://github.com/jparker2006/ClosedWiz/issues/106#issuecomment-6550891204)). Check [STATUS.md](STATUS.md) and each version's acceptance record for its current gates; fixture tests alone never prove live behaviour.

**First step for any agent: if `.wizskills/` is missing, run `python3 -I tools/wizskills/install.py` from the repository root.** It installs the pinned WizSkills release, so every `skills/<name>/SKILL.md` path resolves.

Always true:
- **Private.** No personal context, transcripts, credentials, live session content or real identifiers in any file. Fixtures are synthetic only.
- **Two write shapes: `tell` and `spawn`.** OpenWiz never launches or merges anything. The `openwiz send` and `openwiz new` commands went in #1264; the allowlist keeps their two write shapes:
  - one text message to one existing session, through `room-cli thread tell <id> --mode queue|steer --json -- <text>` (documented, not observed; the argument shape must be rechecked on the owner's endpoint before any live send);
  - one new Cloud thread in one existing project, through `room-cli thread spawn --project <id> --machine cloud --provider <p> --model <m> --reasoning-level <l> --request-id <rid> --json --prompt <text>` (its flags observed in spike run 3's help, the call itself never run). There is no retry (sheet A-3).
  - **Attachments (0.0.4, #15, sheet B-1 to B-10)** ride on those two writes and add no other call: `--file <path>` and `--image <path>`, only with a staged copy's absolute path (B-7), after `--json` and before the text's `--` or `--prompt`, built only by the allowlist's `attachment_args`. Steer can't carry them. `room-cli` uploads each file to CloudRoom, which keeps its own copy (B-1): that is part of the write. Never a separate upload (`project attachment upload`).

  Every `room-cli` call must come from the allowlist in `crates/adapters/cloudroom/src/allowlist.rs`. **The `room-cli` version is not a gate**, for the writes and the reads (#37; version policy, recorded 2026-11-07: report the version without making it a gate; [private record](https://github.com/jparker2006/ClosedWiz/issues/1275#issuecomment-6704671951)): it is reported, and every other safeguard still applies. Live effects require the existing scoped kit authority; the future public-source release path follows ADR 0020 after verified cut-over, without per-step prompts or wider permissions.
- **Proof first.** A claim without its evidence stays Unverified. Tests never prove live behaviour.
- **Frozen:** the 0.0.0 files under `release/openwiz/` never change.

**Current status, in plain English:** [STATUS.md](STATUS.md). Keep it current after every real change.

## Where things are

| Path | What |
| --- | --- |
| `crates/core` (`openwiz-core`) | The inventory model, the honest envelope, the `SessionSource` interface, and the `list`/`show` operations. Depends on no other crate here |
| `crates/adapters/cloudroom` | The `room-cli` allowlist and the CloudRoom `SessionSource`. Depends on the core |
| `crates/cli` (`openwiz-cli`, program `openwiz`) | Parses commands and prints results; its `state` module is the owner's state directory (start records, loop switches). Depends on the core and the adapters |
| `skills` | The fleet skills, from [WizSkills](https://github.com/openwizdev/WizSkills): a tracked link to the gitignored `.wizskills/skills`, installed from the release `wizskills.lock` pins; `.claude/skills/` and `.agents/skills/` link through it. Change a skill in WizSkills and move the pin; ClosedWiz's remaining checks over them read the installed copy (`tests/checks/skills.rs`): see [tools/wizskills/README.md](tools/wizskills/README.md) |
| `contracts/inventory.v1.schema.json` | The `openwiz.inventory.v1` JSON envelope |
| `tests/proof/` | Proof cases P1 to P12, one module each |
| `tests/checks/` | Dependency direction, the fixture scan, schema conformance, the pending list |
| `tests/fixtures/` | Synthetic `room-cli` 0.43.1 responses, with their provenance in its `README.md` |
| `tests/fake-room-cli/` | The fake `room-cli` the tests run |
| Pull request proof records | Red run, dependencies, review results and gaps; private evidence remains in ClosedWiz, linked by private-record comment pointers |

Dependencies point inward: `cli → adapter → core`, `cli → core`. The core never depends on an adapter or a client.

## Commands

Rust 1.99.1 with `rustfmt` and `clippy`, and zsh (`sudo apt-get install -y zsh`), which some fleet proofs run printed commands in. There is deliberately no `rust-toolchain.toml`.

```sh
cargo build --workspace
cargo test --workspace                                         # P1-P12, the kept M, N and AP cases and the checks, on the fake room-cli only
cargo test -p openwiz-tests --test messaging                   # M12: the allowlist's tell shape
cargo test -p openwiz-tests --test new-thread                  # the kept N cases: the core's new-thread rules the engine starts agents through
cargo test -p openwiz-tests --test attachments                 # the kept AP cases: the core attachment and prompt rules (#15's AD8, AD11)
cargo fmt --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test -p openwiz-tests --test checks pending              # the pending markers match tests/pending-ticket-2.txt (empty after ticket 2)
cargo build --release                                          # target/release/openwiz
cargo run -q -p openwiz-cli -- --help                          # usage, sort order and exit codes; reads nothing
```

**CI** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml), #1262) writes one [selection record](contracts/ci-selection.v1.md) in `changes`. Every run executes format, classifier/selector proofs and the cheap architecture/privacy/static checks. The selected Rust, release and individual skill jobs start independently. Each lane reads the persisted plan, and `ci` requires every planned job and individual matrix receipt to pass. Failed, cancelled or missing work fails. The orchestrator changes the ruleset's required checks to `ci` at merge and reads it back; the temporary `web-test` bridge follows `ci` during that transition.

Only a ready PR's first ordinary attempt against `main`, with current live base/head and a trusted measured map, can narrow coverage. Nightly runs, reruns, release branches, merge groups, ready-for-review, stale events, unknown paths, empty/failed diffs and selector doubts run everything. A push to `main` keeps `main-light` (format; `privacy.yml` also checks it) and reads the newest cached signed map in `changes`: only a verified map older than 120 minutes admits a full traced plan and signing, while unreadable age refuses the decision (#1055); the nightly run stays full, also signs the map and refreshes the trusted caches. A draft fails. Before a lane runs it prunes its legacy classifier reader's unused files and `private/` outside [ci-reads.txt](.github/actions/docs-only/ci-reads.txt); a newly required file needs its reader row. Hosted fork routing, guarded setup and trusted cache writes remain as #1265 defined them. Tests use synthetic fixtures and no application secrets. The classifier retains `.claude/skills/export-review/SKILL.md` and `.claude/skills/live-quick-check/SKILL.md` for its Rust reader; other local skill entrypoints remain skippable.

- **Never retarget a PR; close it and open a new one against the other base.** CI judges a PR against the base it ran with, and changing the base starts no new run.
- **Every code run deletes the rest of `private/` first.** A test that must read another file there fails in CI until that file is added to `ci-reads.txt`. A test that reads such a file only if it exists, or finds its cases by walking a directory under `private/`, would instead pass without it: don't write one.

`sh .github/actions/docs-only/test.sh` checks the classifier, diff/event guard, prune/checkout, Rust runner, plan, dispatch and final-job boundary. The Rust lane uses `ci/rust-tests.sh --only` for the exact planned IDs, retaining its cgroup-aware concurrency and sequential fallback. The checks binary runs once in the always lane; by hand, `cargo test --workspace` remains the full command.

`openwiz ls`, `openwiz show` and `openwiz fleet <spec>` run the verified bundled `room-cli`, never one found on `PATH`. Outside the tests that is a **live read**: ask Jake first. In-process tests inject an absolute fake program. Subprocess tests run the test-only fixture CLI example with an isolated bundle around the fake (`OPENWIZ_FIXTURE_PROGRAM` is read only by that fixture entrypoint), and point `OPENWIZ_STATE_DIR` (the start records and loop switches) at a private test directory. The production binaries have no fixture environment or feature bypass.

[Jake approved macOS App signing](https://github.com/jparker2006/ClosedWiz/issues/1102#issuecomment-6672035698) to run only absolute `/usr/bin/python3 -I -c <compiled-in reviewed security.py> inspect|sign <private root>`, with `.env_clear()`, no `PATH`, fallback or production override (2026-11-05; this adds no store program). The tests use a private state directory and synthetic files they write themselves.

## Doing the work

- **Install the pre-push hook first,** once per clone: `git config core.hooksPath .githooks`. The hook checks the commits being pushed for privacy violations and stops the push if the check refuses them ([.githooks/pre-push](.githooks/pre-push)). CI runs format, lint and tests.
- One ticket attempt, one owner, one branch. Stay inside the ticket's owned paths.
- **Live tests and spikes (ADR 0015).** Full live tests run on the PC (the always-on CloudRoom hub), from a Local thread there. Under ADR 0016, an approved live kit covers its own steps without per-step prompts; use only its throwaway test threads within approved counts, allowlist and spending. ADR 0020's future public-source release path retains this scope; it creates no live authority before verified cut-over.
  A quick Mac check is optional feedback after publication under ADR 0020, not another pre-publish human gate. Any separately authorized check records the version, result and limits; no Mac installation or access is authorized by this paragraph.
  The Mac-only checks stay on the Mac: the Mac's fixed `room-cli` location, adding the Mac to the PC's CloudRoom, and the Mac shut for a day.
  The standing approval for read-only discovery spikes covers the PC as well as the Mac.
  **Live spike first.** For a live claim, run a read-only discovery spike on the machine the claim concerns before writing procedures or fixture tests, under the recorded standing approval ([private record](https://github.com/jparker2006/ClosedWiz/issues/1275#issuecomment-6704671951)). Record what is really there. See [ADR 0015](docs/adr/0015-live-tests-on-the-pc.md).
- Write the proof first: define each claim and its evidence, write the test, run it red, keep private evidence in ClosedWiz and reference it by a private-record comment pointer.
- **Fail closed:** anything that guards a write or read path uses an allowlist, never a blocklist. Size each live gate to its risk, and put all of a version's approvals on one sheet.
- A test for later behaviour is `#[ignore = "pending: ticket N"]` and listed in `tests/pending-ticket-2.txt`. No other `#[ignore]`.
- Only `serde` and `serde_json`. Record every locked crate in that ticket's `dependencies.md`.
- New fixture values must be synthetic. Label every shape that was not observed in the scenario's `synthetic_assumptions`.
- Keep the core free of I/O and formatting, the adapter free of product rules, and the CLI thin.

## Done means verified

- All four commands above pass. The pending list is exact.
- Each claim names its evidence class: fixture test, live observation, or independent review.
- The builder hands over the exact branch, head and tree, test results, the red run, internal review results and gaps.
- The 1 + 1 rule: each pull request gets one review plus one re-check; after it, an open security, privacy or data-loss blocker gets one fresh, stronger fix round and then parks for Jake, and any other open blocker is logged as a follow-up and the pull request merges ([review-loops contract](contracts/review-loops.v2.md)). A review binds only to the head it read.

## Ask Jake first

- Any new dependency, toolchain file or tool on the Mac.
- Any live `room-cli` read, or anything on the Mac, outside an already approved scoped kit (only via `room-cli mac run`; no new install or machine authority). The exception is read-only discovery spikes within the recorded standing approval ([private record](https://github.com/jparker2006/ClosedWiz/issues/1275#issuecomment-6704671951)); machine paths remain private.
- Changing the allowlist, the approved limits, or the `release/openwiz/` files.
- Merging follows the standing development merge rules. After verified O17 cut-over, public-source releasing follows [ADR 0020](docs/adr/0020-release-on-demand.md): Jake's actual ship instruction and exact changelog approval are the only human release actions; agents execute candidate-bound CI, privacy/claims, product verification, combined smoke and applicable send/new/App-permission/spending live checks within existing kit authority. No export-plan/final-diff/standalone Sol-export, mandatory device or per-step publish approval. Before cut-over, no successor-path publication; O16/O17 authorization, prerequisites and holds remain. Historical backfill stays separately gated. Never force-push or rewrite immutable releases.

## Read when relevant

- [workflow.md](release/openwiz/docs/workflow.md): PDD; this frozen 0.0.0 doc keeps the old 2 + 1 wording, and the live 1 + 1 rule is in the skills ([proof-driven development](release/openwiz/docs/workflow.md#proof-driven-development), [failure and rework](release/openwiz/docs/workflow.md#failure-and-rework)).
- [architecture.md](release/openwiz/docs/architecture.md): layout and dependency direction.
- [RELEASING.md](release/openwiz/RELEASING.md): versions, export review, what a release may claim.
- [tests/fixtures/README.md](tests/fixtures/README.md): where the 0.43.1 shapes come from.
- Machine details and access instructions stay in ClosedWiz; consult its private record only when authorized work needs them.
- Standing discovery approval: Jake, 2026-10-27, extended 2026-11-01, permits the recorded read-only discovery spikes ([private record](https://github.com/jparker2006/ClosedWiz/issues/1275#issuecomment-6704671951)); release installs and other live work retain their gates.
- [Fleet settings](docs/agents/fleet.md) and [helper settings](docs/agents/helpers.md): public work and merges on OpenWiz, with handoff and runtime identities kept in ClosedWiz or CloudRoom. Public records carry neither thread ids nor exact decision words.
- Rust: [API Guidelines](https://rust-lang.github.io/api-guidelines/), [Clippy](https://doc.rust-lang.org/clippy/), [rustfmt](https://rust-lang.github.io/rustfmt/).
