# Ticket mover preparation (#1283)

No live migration, publishing, settings change or activation is authorized by
this tool. `--apply` is a future, separately gated cut-over operation. Proofs use
synthetic repositories and fake GitHub publication only. PC CI and the final
review remain hand-back gates.

## Complete read-only dry run

```sh
python3 -I tools/open-tickets/collect.py --out /private/new-dry-run \
  --checker /private/reviewed/check.py --literals /private/matching-list.txt
python3 -I tools/open-tickets/collect.py --out /private/new-dry-run \
  --checker /private/reviewed/check.py --literals /private/matching-list.txt --check
```

The default API target is `openwizdev/OpenWiz`; `--target OWNER/REPO` overrides
it. This dry run never contacts the target. It reads complete open membership,
counts, source content/metadata/relationships and PR base/head twice. Observed
snapshot drift retries at most three complete pairs (`--snapshot-attempts 1|2|3`,
default 3), with no sleep or watcher. A stable pair records earlier drift;
exhaustion reports object numbers and changed fields and saves no planned run.
Malformed, partial, foreign or unproven reads still refuse. #1257 and its remaining direct tickets
are excluded. So is a **stays-private PR** (orchestrator ruling, #325): an open PR
whose changed files (renames' old names included) are all private by the importer's
own `private_or_retired`, loaded from the pinned `tools/open-import/import.py` bytes,
never copied. Its file list is read over REST and must match the PR's
`changed_files`; a PR with any public file, or none, moves. The inventory's
`private_pulls` and provenance's `private_pulls` record each one's file count and
path-list digest (no names); it gets no excluded-target binding. A PR that gains a
public file later changes the scope: drift in collection, proposal and apply.
The orchestrator may also rule a PR private that touches a carried file (for
example only the `docs/grills/README.md` index line): list it in a reviewed
`--stays-private-prs FILE` (`collect.py`, `plan.py`), a JSON list of
`{number, reason, ruling}` with the ruling's ClosedWiz comment URL. Each listed PR
is recorded in the inventory's `listed_private_pulls` and in provenance with its
reason, ruling, file count, digest and head commit (`head_sha`), and is excluded.
A listed number that is not an open PR refuses. `proposal.py` carries those
reviewed records as the proposal's `stays_private_prs`; `move.py --apply` rereads
each listed PR and refuses before any effect when its file count, path digest or
head differs (new files, or new commits at the same paths): prepare and review
again. An unlisted PR with a public file still moves. Closed work is read only for prerequisite/approval verification,
and is never carried. Merged blockers require a closing source PR merged into
main and its merge commit reachable from current main. Approved source graphs (identified by labels, native parent relationships or nonempty native child collections)
bind the latest original approval and the current revision-v2 fingerprint,
including completed direct children. A mismatch is saved as `approval stale`
in provenance and `report.json` for read-only preparation under the recorded
option-B ruling. It authorizes no move: apply and verify still require the
original approval to match the complete current source graph. Unreadable or
ambiguous fingerprints refuse even in preparation. No old comments are carried.

The 2026-11-07 preparation ruling (private ticket comment 6711486946) permits
`--body-aliases FILE` for the explicitly listed issue bodies only. The manifest
uses schema `openwiz.body-aliases.v1`, mode `dry_run_only`, the ruling's `authority`
URL, `literals_sha256`, sorted positive `issues`, and `roles` mapping literal
SHA-256 values to `home_account` or `private_name`. It contains no literal values.
Known home prefixes become `${HOME}`; complete names become `<build-account>`
or `<private-name>`. Exact quotations are extracted from the original first.
Unknown/composite names and emails stay for O3 to refuse. Titles, labels and
milestones are never aliased. The saved provenance binds this manifest and
verification still requires the matching mandatory list. This is a draft-only
interface; `move.py` has no alias-policy override. Independent semantic review
of the new drafts and separate approval of an exact move remain required.

Complete non-reference parentheses and inline code after closing verbs remain
unchanged ordinary PR prose. Reference wrappers, unknown targets, malformed or
unclosed spans, reference-style definitions and unsupported suffixes refuse.

Preparation batches independent read-only calls with at most four workers and joins each
dependent phase. Both complete source snapshots, proof sets and final inventory
must still match exactly. A drift refuses that attempt with issue numbers and changed
field names only; no source snippets are logged. Apply's reads remain sequential.

Under the recorded prerequisite disposition, native `COMPLETED` issues without
a closing PR use an explicit completion-comment binding. Pass a private
`--closure-records FILE` containing issue-number keys and values with `comment`
(positive id), `sha256` (the exact comment body's UTF-8 digest), and
`superseded_by` (`null` for completion, an issue number for supersession).
The collector rechecks the native reason and that exact comment in both reads.
Completed prerequisites get the closed-issue and completion-comment links in a
note, never a destination edge. Native `NOT_PLANNED` prerequisites are omitted
from destination edges and listed in `report.json` with their supersession
record and dependents. No replacement edge is inferred. Missing, changed or
unused bindings and unknown reasons refuse. The original graph is never edited;
its owner's next approved revision handles stale private edges.

Open prerequisites positively bound to the excluded migration spec/tickets
become explicitly `HELD` private prerequisites, with their exact issue link and
open state in both the new draft and report. They receive no public number or
completion claim. `move.py` carries the same edge (an open blocker in the
proposal's `exclude` with an `excluded_targets` binding) as that note: no
destination edge, and the source comparison still includes it, so no blocker link
is dropped. Apply rechecks each binding's open state, parent and source digest;
an unbound excluded blocker refuses, and an excluded parent still refuses.

Saved verification requires the full operation schema, repository graph references,
acyclic relations, merge/approval provenance and all inventory/map/operations/
provenance digests bound by the report. Missing or edited artifacts refuse.

Outputs: inventory/counts, canonical `map.dry-run.tsv`, planned operations with
both links, and hashes/merge/approval provenance. Only O3-clean public drafts are
saved; raw source bodies, comments, exact quotes and the real literals are not.
An operation that refuses has no saved draft. The command exits nonzero, retains
safe refusal evidence, and `--check` also refuses. Destination numbers and
milestones remain symbolic. `#issuecomment-1` is explicitly a preflight pointer
placeholder for a future exact private record, never a verified/public pointer.
`${openwiz:N}` in a planned original comment is a private substitution slot for
the actual destination number. PR plans require separately reviewed O14 artifacts;
a successful source/text plan does not claim an actual patch or publication.

`plan.py` remains the smaller inventory-only seam. Its saved inventory/map do
not prove source content, planned operations or privacy. `graph.py` prepares or
reads back a supplied graph/map and can draft mapped re-approval text/hash with
held rows. `text.py` transforms exact private-record quotes and threads, checks
O3, and writes local drafts only. Internal CRLF quotation bytes are preserved.

## Building the apply proposal

```sh
python3 -I tools/open-tickets/proposal.py --dry-run /private/move-dry-run \
  --out /private/move-proposal --checker /private/reviewed/check.py \
  --literals /private/matching-list.txt --source-repo /private/ClosedWiz \
  --destination /private/OpenWiz --destination-main IMPORTED_MAIN_SHA [--date YYYY-MM-DD]
python3 -I tools/open-tickets/move.py --plan /private/move-proposal/proposal.json \
  --state-dir /private/move-state --map-out /private/map.tsv \
  --checker /private/reviewed/check.py --literals /private/matching-list.txt
```

`proposal.py` turns one completed dry run into `move.py`'s private proposal. It
never applies, publishes or writes to either repository. It refuses an `--out`
inside any Git work tree or repository (a `.git` on the nearest existing
ancestor's path, or Git's own discovery under a clean environment; an unreadable
answer refuses too), so raw private bodies never land where `git add` reaches. It refuses unless the
dry-run folder passes `collect.py --check` unchanged and is `planned`. A `HELD`
prerequisite is carried with its excluded-target binding (above) and listed in
the summary's `held_prerequisites`. A stale original approval is carried as that original binding and
listed in the summary's `stale_approvals`: dry mode accepts it, but apply's
currentness read still refuses it until the graph is current. It then rereads
the source once through the collector's own helpers (`plan.inventory` before and
after, `collect.collect_source`): any differing open scope, node digest,
merge/closure/approval/exclusion proof or `source_sha256` refuses as `drift`,
naming the numbers. Return to a fresh dry run; never edit a proposal. One reread
costs about half a collection's GraphQL (the issue/PR views); inventory, comments,
comparisons and the destination milestones are REST.

The proposal holds `graph` (every moving item exactly as read; closed
prerequisites as state-bearing references with `merged`, `completed` or
`not_planned`, and excluded issues as open references, each with no links of
their own; the destination milestones that moving
items use, read from `repos/TARGET/milestones?state=all`, refusing a missing or
repeated title; `exclude` from the inventory), raw `bodies` by old number, the
inventory's `target`, `date` (default today, UTC), `approvals` (comment and
fingerprint), `closures`, `merges` and `excluded_targets` from `provenance.json`,
and `pulls`. For each moving PR it runs the pinned `import.py patch` from the
local ClosedWiz clone (the read range's merge base to head) against the OpenWiz
clone, which must be at `--destination-main`, into `OUT/patches/N`, and records
the handoff with its `binding_sha256`. A refused patch names the PR. The output
folder must be new and outside both clones and this checkout; it is `0700` with
owner-only files, and is removed whole on any refusal. Before success the
proposal passes `move.py`'s own default dry-mode check, which reapplies each
patch in scratch without saving. Review the proposal and its patches before apply.

## Future issue and PR lifecycle

`move.py --help` describes the private proposal, journal and map. Default mode
checks drafts/O14 artifacts without publishing or saving journal state. It
reports source provenance unverified until an apply/verify currentness read.
The proposal contains `graph` (items, destination milestone title/number pairs,
exclusions), original `bodies` keyed by old number, optional `target`, ISO `date`,
optional `approvals` (spec -> original approval comment/fingerprint) and `pulls`
(PR -> exact reviewed handoff). Keep proposals outside public repositories.
For non-merge closed prerequisites, include `closures` (issue -> the same record
binding plus `state: completed|not_planned`), matching the graph item's verified
state. `merges` binds each merged graph item to a list of
`{pull_request, merge}` proofs (source PR number and full merge commit hash).
The note links its closing PR. Apply and verify recheck these records before
effects or acceptance.

Each PR handoff has `source_base` (patch merge base), `observed_base` (current source base tip),
`source_head`, local `destination` repository,
`patch_dir`, and reviewed `binding_sha256`. It consumes O14 PR1872's verified
merge `2eb689e925d61fe8f318444c4f8b7d80fe2557e7`: `apply-patch` with the digest,
checker and required literals. The importer's bytes are pinned to that reviewed
delivery; the carriage list beside it is pinned by the reviewed binding's
`policy_sha256` digest, not a source literal, so a classification PR edits only
the list. Missing artifacts, a list other than the binding's, edited
bindings/patches, source range mismatch, stale destination main or O3 refusal
fail before remote effects.
The observed source tip/head are frozen separately; a current GitHub comparison
must confirm the patch merge base, so a normally diverged PR remains supported.
Use `--importer` for an external extraction on a branch predating that merge.

Explicit `--apply`, only after separate authorization, freezes the full proposal
and bindings by hash and rechecks source metadata/content/state, exclusions,
merged blockers and original approvals. Complete current open membership must match the proposal;
only the migration spec, its own remaining tickets and stays-private PRs (judged again at apply) may be excluded. Conflicting
original migration-comment families and unrepresentable reapproval tables refuse
before remote effects. For each PR, O14 saves only the checked
ordinary public commit above destination main. A nonce-owned branch is pushed
from an isolated temporary bare repository to the explicit target URL. Only the
checked commit and its reachable public history enter that publisher. Destination
tags/config and Git environment/global/system settings are excluded; tag following
and recursive submodule publication are disabled. The only credential helper is
the selected gh program, explicitly scoped to github.com; live authentication is
not proven by local receiver fixtures. No source branch,
commit message, author, history or private file is imported. The branch and PR
head/base/repository are read back. PR metadata uses opaque REST label arrays;
commas cannot create extra ready labels. Issue graph links are mapped and read
back. Private quotes get one exact original comment and a verified pointer.
Every move gets exactly one map row and both exact O2 links. The approved legacy
moved-to URL remains until O9's address cleanup is verified merged.

State version 5 is locked, owner-only and atomically fsynced before effects.
Lost push/create/comment responses reconcile by their durable identity and
read-back. Each edit persists its exact resource, intended value, full request and
payload digest before sending. Resume reads that specific resource; an absent or
ambiguous outcome refuses without retry or intent clearance. Other phase saves
cannot clear an unsettled effect. Edit confirmation and intent clearance share
one atomic durable write, including parent updates. Confirmed bodies, metadata, parents and individual blocker edges are
saved as phases; a later public removal refuses repair even when another effect
is interrupted. A completed row is verified and never applied again. Preparatory
older journal versions refuse; no automatic live-state migration is implemented.
An unseen uncertain outcome refuses automatic retry. A later public
edit, foreign relationship, unrelated destination/map or conflicting migration
comment refuses overwrite/adoption. Each graph update has its own read-back.
ClosedWiz originals retain their titles/bodies/state/metadata; only the permitted
private-record and moved-to comments are posted. No close/delete/transfer exists.

`--verify` reads the journal/map and both repositories without saving application
state. It rechecks originals, complete metadata, public bodies/private pointers,
comment families, both links and PR patch heads. After a completed apply, local
`reapproval.json` contains new held tables/fingerprints for bound approved specs;
no approval or readiness is posted. Old approval is never treated as new approval.

PR closing keywords map repository-local and explicit ClosedWiz references to
actual new numbers. Complete tokens are required: URL fragments/queries, other
suffixes and unsupported wrappers refuse instead of being partially rewritten.
A closing reference to the positively bound excluded migration spec or one of
its remaining direct tickets becomes `Related private issue` with the exact
repository-qualified private issue link in the new draft. No PR or reference is
dropped and no destination is invented. Collection independently compares the
spec's complete native children with the inventory, checks each excluded issue's
native parent/state, and saves its identity, parent and source digest in
`provenance.json`. Saved verification checks those bindings. Future proposals
carry the collector's `excluded_targets`; apply/verify re-read the actual scope,
parent and exact source digest before effects/acceptance. Private originals stay
unchanged. A target without that binding, a PR-route mismatch, suffix or
unsupported wrapper still refuses before effects.
Source base/head and closing references are independently bound;
old comments and commit messages are never carried. The accepted keywords,
case/colon variants and repeated-keyword syntax follow
[GitHub Docs](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue).

## Scoped fixture checks

```sh
sh tools/open-tickets/test.sh /private/reviewed/O3/check.py /private/reviewed/O14/import.py
```

CI runs this runner with merged public O3/O14 and synthetic lists, no live GitHub
or real literals. Seven Python suites own inventory, graph, text, issue lifecycle,
PR carriage and complete collection contracts. The PR proof uses real Git/O14/O3
with synthetic history anchors only in its checker harness; publication uses
fake programs. Every remote effect's lost response is tested. Missing links,
rows, source/approval drift, private text and patch tampering are planted.

O16 can reuse the collection/map/operations, graph/re-approval, text, patch binding
and verification seams. Evidence separates fixture passes, real read-only
observations/refusals, independent review and pending/live gates. The absent
grill is neither recreated nor claimed read; approved build sources are the
recorded confirmation, revision-2 approval and merged O2 per comment6705158860.
