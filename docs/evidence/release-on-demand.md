# Release on demand: the first public release, v0.0.12 (#18)

RL5's one real run of the release-on-demand path ([ADR 0020](../adr/0020-release-on-demand.md)):
OpenWiz v0.0.12, the first public release, published and installed on 2026-11-16 UTC.

**Result: published and installed; the 30-minute ship-to-install target (P6) was MISSED: 315 minutes.**
Evidence class: the release command's own record and read-backs, plus an independent read-back of the
published release. Private evidence: the ship decision
([private record](https://github.com/jparker2006/ClosedWiz/issues/325#issuecomment-6909430890)) and the
run's step records on the same private issue.

## What was published

| | |
| --- | --- |
| Release | [`v0.0.12`](https://github.com/openwizdev/OpenWiz/releases/tag/v0.0.12), pre-release, immutable |
| Tag | annotated, tag object `f7184049341f7c2bac7139047abc7a16f966d309`, peels to `3e025bd2a45c6922b09461a03b825b0e4816d0cf` |
| Source | head of the protected `release-0.0.12` branch: `c1c191d3` plus the cherry-picks of #954, #915 and #974, nothing else |
| Notes | the approved changelog's 0.0.12 to 0.0.6 sections, 6,896 bytes, sha256 `27135ed4d22479e17d6f02806ccb9e8a8b33e2ef37a970e1a216800da4af9191`, byte-equal on the release |
| Build | Packages run 43851312769: three targets, 13 assets, `SHA256SUMS` checked on download |
| Candidate | `openwiz.release-candidate.v1` sha256 `2b03927e462b073d4f39deeec8f868b3c269d489599d466a9dce3280b574fa40` |

## Gates

| Gate | Result |
| --- | --- |
| Cut-over, required checks, immutable releases | pass (read by the command) |
| CI and privacy at the exact commit | pass |
| Artifact privacy (D2), with the private named-terms list | pass, no findings |
| Claims (notes are the approved cut) | pass |
| Products (programs, web export and runtime against their receipts) | pass |
| Combined live smoke, throwaway targets only | pass: all 10 kit steps; covers 0.0.12's promise. 0.0.11 to 0.0.6 are recorded as not-live gaps, as their notes say |
| send, new | live pass |
| App permissions | **waived** for 0.0.12 only, never passed; the notes say App installation permissions are unverified live |
| spending | not required (no changed path touches spending) |

## Install

The normal route: `gh release download v0.0.12` and `tools/install/install.py`, into new throwaway
folders on the PC, x86_64 Linux. It installed version 0.0.12 from source `3e025bd`, activated, with the
manifest and archive matching the release. This proves that route on that machine only.

## Timing

| Mark (UTC, 2026-11-16) | Time |
| --- | --- |
| Ship decision (the start, never reset) | 06:43:22 |
| Published | 11:57:53 |
| Install verified (the finish) | 11:58:31 |

**Ship to install: 315.1 minutes. P6 missed.** The command's own checks took 205 s, publish 189 s
and install 32 s: about 7 minutes. The rest was finding and fixing the problems below, with their
reviews and waits. The changelog was approved the evening before, so there was no changelog wait after
the ship decision.

**Preparation, reported separately:** 01:21 to 06:43 (5 h 22 min): the first build, risk
classification, the non-live gates, the receipt fix and the first candidate seal.

### Causes of the miss, in order

1. **The one-row kit against a seven-version candidate** (#915). The smoke kit live-checks only
   0.0.12, but the receipt demanded live coverage for every included version. Fixed: versions with no
   live-checked line are carried as named not-live gaps, never as covered.
2. **The kit pinned to old code, and main's installer changed.** The receipt, evaluate and publish steps
   re-verify the kit's own pinned checkout, so a fixed tool could not be used with the old kit, and
   main's newer installer refuses the older archives. Only a release branch holding the fixes on the
   original code had both.
3. **room-cli's spawn receipt drift** (#949, fixed by #954). The first live smoke created its one thread
   but read the result as uncertain, so it could not pass.
4. **The release command's main-only source rule** (#964, fixed by #974). It refused any commit that was
   not on `main`.
5. **Main had moved on.** Main carried 33 later PRs, including retirements of features the approved
   notes describe, so a rebuild from `main` would not have matched its notes.
6. **Shared GitHub rate limits and review rounds.** Each fix needed its own review, CI and queue.

## Gaps

- P6 is unverified: this run missed it. A later release must measure it again.
- App installation permissions are not verified live (waived for 0.0.12 only).
- Only the x86_64 Linux install route was observed; the macOS targets were not live-checked.
- 0.0.11 to 0.0.6 promises are not live-checked by this release's smoke; their notes say so.
