# Collector factory fixtures (MT2, #821)

Synthetic only. Each world maps an exact `gh` call (its argument list, as
JSON) to its answer, for [`fake_gh.py`](fake_gh.py), the exact-call fake the
proofs put on `PATH`. An unexpected call exits 9: nothing falls back to a
network. The worlds are the source tools' **own** test worlds, so the
collector is compared with each tool on the same fixture.

| File | From | Proves |
| --- | --- | --- |
| `daily-world.json`, `daily-usage.json` | `tools/factory-metrics/test.py`'s `world()` and `usage()`, unchanged, plus the collector's two extra reads: the same PR inventory answered again for the collector's query (which adds `baseRefName`; PR 33 merged into `release-0.0.9`, the rest into `main`), and WR8's direction query for tickets 12 and 15 (milestone `0.0.9`: forward), 13 (`polish`: backwards) and 14 (milestone `Infra`: sideways) | `merges`, `stalls`, `cost`: factory-metrics' hand-worked day (its test.py docstring) |
| `journey-world.json` | `tools/factory-metrics/test_journey.py`'s `world()`, unchanged, plus its PR inventory answered again for the collector's query (every base `main`) | `journeys`: the cohort of 2030-01-02 is PRs 4201 and 4202 (tickets 4101 and 4103); the document is `journey.py collect` over those tickets |
| `stage-world.json` | `test_journey.py`'s `stage_world()`, unchanged | `stage_waits`: TL2's sidecar for tickets 4301–4304 at 2030-03-01T12:00:00Z, and its bench |
| `bench-world.json` | `tools/ci-bench/test.py`'s `world()`, its space-joined calls split into argument lists | `prs_per_hour`: ci-bench's headline for 2030-01-01 00:00–02:00 |
| `open-world.json` | Written here: [`../collector/read-stall.json`](../collector/read-stall.json)'s four open PRs as GitHub's GraphQL would answer them, plus a PR inventory whose one merge (PR 4209, 11:03:59) falls just before the alarm's hour | `open_prs` equals that contract fixture's value; `merges` for `[11:04, 12:04)` is a complete read of nothing |
| `red-first.log` | The first run of `test_collect_factory.py`, against a stub that answered every fact `unavailable` | Red first: each case failed at its own claim |

The worlds were written once from those test modules, at this ticket's base,
by a throwaway script that imported each module and dumped its world with
`json.dumps(world, indent=1, sort_keys=True)`; only the additions named above
were made. When a source tool's own world changes, these copies do not: they
are fixtures, not mirrors.
