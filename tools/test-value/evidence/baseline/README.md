# Baseline (#803)

The campaign's starting numbers: one `measure.py` result per test target in
`tests/` (`tests/Cargo.toml`'s twelve `[[test]]` targets), each measured on
its own, as `<target>.json`. The measured `tests/`, `crates/`, `apps/`,
`Cargo.toml` and `Cargo.lock` are byte for byte `main` at `69f0e72` (after
TV2's fixture prune, #853); only `tools/test-value/`, CI registration rows and
`paths.json` rows differ. Measured on one
Linux aarch64 sandbox with Rust 1.99.1 and `cargo-llvm-cov` 0.9.1.

Size is the group's compiled Rust sources (README, "Size"), so it counts
only files rustc reads. `service`, for one, compiles 14 files: its
`main.rs` names three modules, and 56 of the 66 `.rs` files in
`tests/service/` are read by no build of the workspace (no test target, bin
or example); TV11 (#813) decides them. Coverage counts children a test starts with a cleared environment
(service's installed-service startup: `crates/service/src/bootstrap.rs`,
`main.rs`).

Each group still measures its own before at its pull request's base: this
table is the reference, not every group's before. Coverage is all crates'
covered over total lines, for that target's binaries only: never add rows
up or compare one row with another (README, "The coverage method").

| Target | Tests | Files | Bytes | Lines | Coverage (lines) | Seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `attachments` | 67 | 26 | 259813 | 7235 | 2132/50175 (4.25%) | 18.6 |
| `checks` | 145 | 18 | 457840 | 12654 | 248/50144 (0.49%) | 180.5 |
| `cli-agent` | 55 | 17 | 344580 | 9133 | 5585/50144 (11.14%) | 25.7 |
| `fleet` | 294 | 38 | 865194 | 24109 | 10364/50159 (20.66%) | 75.3 |
| `loops` | 32 | 12 | 103864 | 3303 | 2228/50144 (4.44%) | 3.3 |
| `messaging` | 189 | 28 | 395635 | 11045 | 5453/50148 (10.87%) | 23.1 |
| `new-thread` | 113 | 40 | 397556 | 11067 | 6932/50148 (13.82%) | 21.1 |
| `notifications` | 23 | 8 | 105990 | 2886 | 1536/50144 (3.06%) | 40.2 |
| `proof` | 125 | 25 | 541179 | 14526 | 2144/50147 (4.28%) | 35.5 |
| `service` | 65 | 14 | 278435 | 7327 | 7163/50149 (14.28%) | 100.2 |
| `terminal` | 104 | 16 | 328383 | 9054 | 10025/50144 (19.99%) | 23.2 |
| `web-api` | 360 | 73 | 961313 | 26531 | 18465/50190 (36.79%) | 79.7 |

## The repeat run

Every target was measured a second time on the same tree, straight after
the first pass; [`repeat.txt`](repeat.txt) holds `measure.py compare` for
each pair.

- **Identical coverage, test count and size (11):** `attachments` (18.6 s, then 18.3 s), `checks` (180.5 s, then 180.5 s), `cli-agent` (25.7 s, then 24.2 s), `fleet` (75.3 s, then 75.5 s), `loops` (3.3 s, then 3.1 s), `messaging` (23.1 s, then 22.8 s), `new-thread` (21.1 s, then 21.0 s), `notifications` (40.2 s, then 40.2 s), `proof` (35.5 s, then 35.0 s), `service` (100.2 s, then 100.0 s), `terminal` (23.2 s, then 23.0 s).
- **Not identical (1):** `web-api` (79.7 s, then 75.0 s): `web-api` covers one `openwiz-store`
  line fewer the second time. Run time differs everywhere, as the README says
  it will.

These are race branches whose execution depends on timing, not the script:

- **This baseline:** three runs of `web-api` differ only in
  `crates/store/src/lib.rs:238` (a directory another request made first) and
  `crates/store/src/lib.rs:568-572` (waiting on a lock another request holds).
- **The first baseline (before #884's R2 and R3 fixes):** `loops` and
  `web-api` varied in `openwiz-server` instead; three runs of `loops` differed
  only in `crates/server/src/http.rs:350` (the drain loop after a response)
  and `crates/server/src/send.rs:241-248` (the body-read loop), which run or
  not depending on whether a request body arrives in one TCP read. Neither
  varied this time, but they can.

**Ruling** (orchestrator, 2026-11-16, on #803): the repeat criterion is met for
the script, with this variance written down. Any group whose coverage drop
is confined to `crates/server/src/http.rs:350` or
`crates/server/src/send.rs:241-248` reruns its measure before calling the
drop real. Making those paths deterministic under test is #892, not this kit.
