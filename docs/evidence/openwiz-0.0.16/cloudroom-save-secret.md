# CloudRoom save-secret contribution: availability receipt (0.0.16 T4, #634)

Recorded 2026-11-14. Evidence class: source reading and fixture tests against
the upstream source. Nothing here is a live observation.

**A prepared patch is not a shipped save-secret capability.** The patch below is
prepared and not yet submitted upstream. Until CloudRoom ships it and a real save
and later delivery are observed, OpenWiz's route is the one protected paste into
CloudRoom's own secret prompt (`room-cli secret request`), which stays available.

## Upstream source

- Repository `davidondrej/cloudroom` at `3208e7901159a20b9354907efa9e463196298bb8`
  (tags `gui-v153`, `core-v0.1.110`).
- Changed paths:
  - `gui/apps/cli/src/commands/cloudroom.ts`
  - `gui/apps/cli/src/__tests__/command-output/cloud-env-set.test.ts` (new)
  - `gui/plugins/cloudroom-guide/skills/room-cli/references/command-index.md`
- Route: the existing fork-and-pull-request route used for earlier CloudRoom
  contributions; the contribution owner submits it.

## What upstream offers at that revision

- **The secret system:** Settings → Cloud environment keys, stored by the
  CloudRoom website and given to every new Cloud sandbox as environment
  variables (and to loops that pick them).
- **Local threads:** `room-cli cloud env set NAME` already saves a key, reading
  the value from stdin. At the pinned revision every failure exits 1, `--json`
  prints the whole environment including the last 4 characters of the saved
  value, and success is not checked against the answer.
- **Cloud threads:** no save command; only `room-cli secret request`, which a
  person fills in.

## What the patch changes

`room-cli cloud env set NAME` exits 0 when the answer lists the name (saved), 3
when CloudRoom refused it (nothing saved) and 4 when it may or may not be saved
(service unavailable, timeout, lost connection, or an answer without the name).
`--json` prints only the name and outcome. An empty value sends nothing. No
output carries the value or any part of it.

| Proof | Result |
| --- | --- |
| New upstream test, unpatched revision | 7 of 7 fail at their assertions |
| Same test, patched | 7 of 7 pass |
| Upstream CLI suite, unpatched vs patched | the same pre-existing environment failures in both; nothing newly broken |

## Status

| Step | State |
| --- | --- |
| Prepared (source-bound patch and red/green test) | done |
| Submitted upstream | pending: the contribution owner's action |
| Accepted for review | no |
| Shipped in a CloudRoom release | no |
| Live save and later delivery observed | no; belongs to the installed/live consumers once shipped |

Not covered: a save from a Cloud thread (it would need a website interface that
is not in the public source), and website-side behaviour, which is closed
source. The patch assumes a refusal saves nothing and the answer lists only
saved names.
