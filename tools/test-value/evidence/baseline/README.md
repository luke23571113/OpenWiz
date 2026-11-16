# Baseline (#803)

The campaign's starting numbers: one `measure.py` result per test target in
`tests/` (`tests/Cargo.toml`'s twelve `[[test]]` targets), each measured on
its own, as `<target>.json`. The measured `tests/`, `crates/`, `apps/`,
`Cargo.toml` and `Cargo.lock` are byte for byte `main` at `192f6e4`; only
`tools/test-value/` and two CI registration rows differ. Measured on one
Linux aarch64 sandbox with Rust 1.99.1 and `cargo-llvm-cov` 0.9.1.

Each group still measures its own before at its pull request's base: this
table is the reference, not every group's before. Coverage is all crates'
covered over total lines, for that target's binaries only: never add rows
up or compare one row with another (README, "The coverage method").

| Target | Tests | Files | Bytes | Lines | Coverage (lines) | Seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `attachments` | 67 | 25 | 238627 | 6655 | 2132/50164 (4.25%) | 19.2 |
| `checks` | 145 | 15 | 419776 | 11590 | 248/50133 (0.49%) | 184.3 |
| `cli-agent` | 55 | 6 | 124372 | 3496 | 5562/50133 (11.09%) | 26.3 |
| `fleet` | 294 | 55 | 913713 | 24706 | 10364/50148 (20.67%) | 75.2 |
| `loops` | 32 | 13 | 112364 | 3544 | 2225/50133 (4.44%) | 3.2 |
| `messaging` | 189 | 23 | 360999 | 10094 | 5453/50137 (10.88%) | 23.4 |
| `new-thread` | 113 | 35 | 362920 | 10116 | 6932/50137 (13.83%) | 22.1 |
| `notifications` | 23 | 7 | 82672 | 2236 | 1191/50133 (2.38%) | 41.7 |
| `proof` | 125 | 16 | 312686 | 8478 | 2144/50136 (4.28%) | 36.5 |
| `service` | 65 | 68 | 1188089 | 31379 | 6300/50138 (12.57%) | 100.2 |
| `terminal` | 104 | 29 | 320400 | 9483 | 9495/50133 (18.94%) | 23.0 |
| `web-api` | 360 | 60 | 818477 | 22469 | 18460/50179 (36.79%) | 94.9 |

## The repeat run

Every target was measured a second time on the same tree, straight after
the first pass; [`repeat.txt`](repeat.txt) holds `measure.py compare` for
each pair.

- **Identical coverage, test count and size (10):** `attachments` (19.2 s, then 18.7 s), `checks` (184.3 s, then 189.4 s), `cli-agent` (26.3 s, then 26.3 s), `fleet` (75.2 s, then 75.3 s), `messaging` (23.4 s, then 23.0 s), `new-thread` (22.1 s, then 21.1 s), `notifications` (41.7 s, then 40.5 s), `proof` (36.5 s, then 36.9 s), `service` (100.2 s, then 100.3 s), `terminal` (23.0 s, then 23.3 s).
- **Not identical (2):** `loops` covers one `openwiz-server` line fewer the
  second time, and `web-api` two more. Run time differs everywhere, as the
  README says it will.

The two are socket timing in the server, not the script. Three runs of
`loops` differ only in `crates/server/src/http.rs:350` (the drain loop after
a response) and `crates/server/src/send.rs:241-248` (the body-read loop): they
run or not depending on whether a request body arrives in one TCP read.
`web-api`'s two lines are also in `openwiz-server`; their exact lines were
not traced.

**Ruling** (orchestrator, 2026-11-16, on #803): the repeat criterion is met for
the script, with this variance written down. Any group whose coverage drop
is confined to `crates/server/src/http.rs:350` or
`crates/server/src/send.rs:241-248` reruns its measure before calling the
drop real. Making those paths deterministic under test is #892, not this kit.
