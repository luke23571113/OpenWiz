# Approach: #2755 (LR14), the frozen-head command's follow-ups R2, R4 to R8

Ticket #2755 under spec #2474. The findings come from the re-check of PR #2682 at `9db4bbe`. Every change is in `kernel/live-rig/heads.py`. Each one gets a red fixture in `kernel/live-rig/test_heads.py` and the fake `gh` in `kernel/live-rig/fixtures/heads/bin/gh`. No real `heads.py` run happens, with or without `--post`.

## Approach, one finding per step, red first

1. **R2, one verified identity.** The kit subprocess drops all five overrides unread: `GH_TOKEN`, `GITHUB_TOKEN`, `GH_ENTERPRISE_TOKEN`, `GITHUB_ENTERPRISE_TOKEN` and `GH_HOST`. Its `gh` calls are then pinned to `github.com` with `GH_HOST=github.com`, because the kit's own `gh` commands take no `--hostname`. The login read through `gh api user` (same environment) is stored in `publish.json` as `login`. Before its first write, every publish, fresh or resumed, reads the signed-in login again and refuses on a mismatch. The fake `gh` logs every call's effective host and the token variables it saw, and the kit's GraphQL reads are no longer excluded from the assertion.
2. **R4, ambiguous cached window.** A 304 honours a `Link` next or last header if GitHub sends one. A 304 whose cached page is full (100 comments) refuses, because page one can stay byte-identical while comment 101 adds a newer marker. A 200 still decides from its own `Link` header. Each ticket still gets exactly one comments read. The fake pages at 100 like GitHub does, which replaces the old one-comment `HEADS_PAGED` split.
3. **R5, ambiguous comment POST.** Each pending comment gets a random run id when it is planned. The id is put in its body as a hidden `<!-- openwiz:heads-run <id> -->` line. Before the POST, the journal saves `tried` with the time. After a try with no saved URL, the resume first reads that PR's comments since the try (one REST read). It adopts a comment only if the author is the stored login and the run line matches. It refuses if the window is full. It POSTs again only if no such comment exists. The WizMarket fallback lookup asks for `state=open` and accepts exactly one pull request whose head label, base, title and body all equal the intended ones.
4. **R6, replay validation.** `publish.json` is checked as a whole before anything else: its exact keys and types, run ids, receipt paths, comment indexes and stored outcome. Every pending comment must equal what the rig's line filter and the credential check produce for its fenced kit lines, under the stored login and the `--settings` repository. Every receipt and the WizMarket text must pass the credential check. Any failure exits 2 with zero GitHub calls.
5. **R7, preview with a pending publish.** Without `--post`, an unfinished `publish.json` is validated (R6) and its pending comments and receipts are printed in the fresh-run preview format. The journal is not written, and `gh` is not called. The exit status is the stored outcome (R8).
6. **R8, exit status on resume.** The session outcome (0 or 1) is saved in `publish.json` before the first write. A resume returns it. The test covers a mixed 5+4 session (1) and an all-pass session (0).

## Threat list

- A token or host in the environment sends the kit's reads to another account or host while the receipt names the stored login (R2).
- The account switches between a lost write and its resume, so the old run's comments post as someone else (R2).
- A cached page one that is unchanged hides a newer authorised frozen head on page two, so an old head runs (R4).
- A lost POST response causes a second KN comment for the same run on resume (R5).
- A closed earlier WizMarket publication from the same head is adopted as this run's pull request (R5).
- A hand-edited or corrupted `publish.json` posts a credential shape or a private value (R6).
- A plain preview leaves a pending journal unreadable, or changes or deletes it (R7).
- A resumed publish hides a failed host behind exit 0 (R8).
- A fixture mistake reaches a real agent CLI or a real GitHub host. Every test puts 37 refusing stubs first on `PATH`, and `gh` is the fixture's fake.

## What the tests can prove and can't

They can prove that `heads.py`, against the fake `gh` and the fixture kit, drops and pins the environment it gives every `gh` call (the kit's included), refuses the listed ambiguous or tampered states before any write, makes exactly one POST per run across a lost response, and returns the stored outcome.

They can't prove real GitHub's behaviour: whether a real 304 carries `Link`, whether `since=` and the pulls `head` filter behave exactly as the fake models them, or how gh picks an account on a real machine with several stored logins. Those wait for the rehearsed VPS session (#2583, after this and #2689 merge). They also can't prove the run-id line survives every GitHub rendering. The match is on the raw body that the REST API returns, and the fake returns it unchanged.
