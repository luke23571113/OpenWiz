# Bounded ops acceptance kit (#2190, OB8)

The prepared kit for spec #2185's agent-run acceptance and its offline result
validator. Python 3 standard library only.

```sh
python3 -I tools/ops-live/acceptance.py kit tools/ops-live/kit.json        # 0 consistent, 1 refused, 2 usage/unreadable
python3 -I tools/ops-live/acceptance.py results tools/ops-live/kit.json <results.json>
python3 -I tools/ops-live/test_acceptance.py                               # the red/green proofs, synthetic
```

Both commands read only the named files: no network, GitHub, `room-cli`,
thread or write. **A pass is not permission and not a result.** This folder
authorizes no live, machine, write, activation, spending or merge step.

## The kit (`kit.json`)

`status` is `prepared`. Its `controls` sub-object is #2219's
`ops-live-kit-controls/1` document, checked unchanged by `controls/kit.py`:
candidate heads, rule and contract blobs, limits, permission classes, stop,
restoration and cleanup. Around it the kit pins host roles, Cloud exposure,
permitted effects (ops-dispatch v1 actions only; `merge` only with a merge
grant), claims P1–P8 and the eight measures.

The pinned head, blobs and limits are the proposal at preparation time. The
approval that admits the final kit decides each value; the live agent re-pins
the current heads and blobs before seeking it.

**#2244's findings live in one place:** `discovery_2244` (revision 10). Its
`record` points to #2244's read-only PC discovery and `decisions` to the
revision that adopted J55 and J56. Each finding is `unknown`, `documented`
(help only; the live run must observe it), `observed` or `absent`:
no read-only lost-start lookup, no proof of negative execution, independent
wakes documented, no author-bound reviewer output. While the record is missing
or any finding is `unknown`, the gate stays closed and P3, P4, P5 and P7
cannot pass.

- **J55, counted at-most-once re-spawn:** after a lost `builder_start` or
  `review_start`, recovery may re-run `room-cli thread spawn` once with the
  same caller-generated `--request-id`. `max_per_lost_start` is exactly 1,
  and a lost start recorded as never executed is refused as unprovable.
- **J56, verdicts read by id:** a reviewer verdict counts only when it matches
  that reviewer thread's own `thread output`, read by id from a context with
  access. A same-account GitHub comment alone never counts.

**The grant and its limits:** each needed permission cites Jake's recorded
OB8 approval, read back (`read_back` holds the record's SHA-256). Merge stays
not needed and not granted. `cloud_threads` holds the recorded Cloud-thread
grant (2) and J60, whose record raises it to 3 active and 6 total, only in
`test_repository` and only after its `after` run. A kit whose thread limits
exceed the grant keeps the gate closed. Every test-owned ticket, branch and
pull request lives in `test_repository`, a throwaway, never a real repository.

**Ordering:** `start_after` names runs that must finish, with their evidence
posted, first. #1110's timed live run uses the same throwaway repository, so
until its `record` is set the gate stays closed, `authorized` is refused and a
live result is refused.

**The live gate** (`kit` command, AC1) stays closed while any needed permission
is not granted, any grant's record is not read back (`read_back.<class>` holds
the digest of the read-back record) or #2244 is Unknown. A kit marked
`authorized` with a closed gate is refused. An open gate is open on paper only:
every record is re-read immediately before any step.

## Results (`ops-live-results/1`, AC2)

One strict JSON object, every key required:

| Key | Shape |
| --- | --- |
| `format`, `kit` | `ops-live-results/1`; the SHA-256 of the exact kit file |
| `live` | `true` only for a run under an `authorized` kit, with every `start_after` met |
| `repository` | The kit's `test_repository` |
| `window` | `{start, end}` in milliseconds, within the kit's duration |
| `threads` | `{alias, role, start, end}`; role is a kit host role, `end` null means never ended |
| `operations` | `{operation_key, intent_id, action, request_id, respawn, start, end, completion, ack}`; ops-dispatch v1 actions and completion states; `request_id` set for spawns, null otherwise; every repeated spawn must set `respawn` true and retain its original key, action, request id and intent; the original must be `uncertain` and end before or when recovery starts; `ack` null or `{operation_key, intent_id, recipient, evidence}` |
| `respawns` | The count of J55 re-spawns; must equal the repeat count derived independently of the `respawn` flags |
| `fencing` | `{boundary: effect, advisory or unknown, evidence}` |
| `reviewer_output` | `{access: verified, absent or unknown, evidence}` |
| `verdicts` | `{reviewer, verdict: APPROVE or CHANGES, comment, thread_output, matches}`; authenticated (J56) only with an observed by-id `thread_output` that `matches` |
| `cleanup` | `{step, state: done or accounted, evidence}` for every kit restoration and cleanup step |
| `claims` | P1–P8 in order: `{claim, status: pass, fail, partial or unverified, evidence}` |
| `measures` | Each of the kit's measures: `{value, denominator}`; null value only when named in `gaps` |
| `gaps` | Plain technical strings |

Evidence entries are ops-dispatch v1's `{evidence_class, source, digest}`: a
`fixture:` source for fixtures, a private-record comment pointer otherwise.

It refuses, among others:

- **Fabricated concurrency:** more threads or operations active at once, or in
  total, than the kit allows, or more Cloud threads than the recorded grant; spans outside the run window, ending before they
  start or counted twice; a window longer than the duration.
- **Missing acknowledgements:** a completed builder start, review start or
  delivery without the recipient's observed ACK of the same operation key and
  intent; P4 passing without an acknowledged delivery.
- **Advisory-only fencing:** P5 passing without an observed `effect` boundary,
  or with a duplicate completed effect.
- **Absent reviewer-output access:** P7 passing, or any completed merge,
  without observed `verified` access; P7 passing without an authenticated
  verdict or with any unauthenticated one; a merge without an authenticated
  APPROVE (J56).
- **Uncounted or repeated re-spawns (J55):** a second re-spawn of one lost
  start, an unflagged repeat, a re-spawn without a lost start or under another
  action, request id or intent, recovery before its original attempt ended,
  a missing or wrong `respawns` count, or a start recorded as never executed.
- **Incomplete cleanup:** a kit step missing, repeated, pending or without
  evidence; a thread that never ended.
- **False live passes:** a pass without `live`, without observed evidence
  (fixture or review alone), while #2244 is Unknown, before a `start_after`
  run's evidence, outside the throwaway repository, against another kit, or
  with a duplicate count or measure that its records contradict. Completed
  effects outside `permitted_effects` are refused.

A consistent result is not acceptance: each pass still needs its observed
evidence read back and independently reviewed. Exact outputs stay in private
evidence; public records carry the claim/evidence/gap matrix only.

### Recovery cross-check proofs (#2975)

At the existing J55 result boundary, extend the synthetic `with_respawn` table
one slice at a time, running and committing each failing proof before its fix:

- Derive recovery attempts from repeated spawn identities, independently of
  `respawn`; refuse an unflagged repeat, a second recovery and a mismatched
  aggregate `respawns` count. Existing cases cover only flagged recoveries.
- Bind a recovery to its original intent, even when its own ACK agrees with
  a different intent. Existing ACK checks compare only with the recovery.
- Require recovery to follow its original attempt in time. Existing interval
  checks validate each span separately, so a recovery can precede its origin.

Evidence is fixture testing only, appended to the existing acceptance
`red.log` and `green.log`. This changes no live authority or acceptance claim.

## Not here

The kit's control bounds are #2219's (`controls/`). The live run, its records,
read-backs and restoration are later steps of #2190, gated as above.
