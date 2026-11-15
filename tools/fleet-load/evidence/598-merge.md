# #598 / PR #619: merge current OpenWiz main

Approved head: `a11d17b9664acb9c4b2d385b52e48028f9c00da8`.
Merged main: `f171ce36a695220ccfeccf89f605871b9f1f8140`.
Merge commit: `85150346fe713e44f217b4405a67a330e2457db4`.
Evidence class: synthetic fixture tests and modeled request measurements.

The merge preserves both parents. The only textual conflict was the declared
shell case total: main's 783 cases plus this PR's three snapshot regressions
are all retained, for 786. No cases or assertions were removed. Main's person
completion/blocker behavior and extra closed-blocker issue probe remain; the
approved priming order, merged-PR CI exclusion and CPU optimizations remain.
All other main changes were inherited without a conflict edit.

**No new test:** this is merge-only reconciliation. Existing named keepers
already protect the behaviors at the supported CLI/fake-command boundary:

- WZ-PROBE's three cases catch irrelevant merged CI invalidating replay, and
  extra GraphQL on the tick immediately following change or expiry; every due
  line is compared with an empty-cache full read.
- GI1's 16 cases catch stale replay after changed facts, identity/cache errors,
  or clock-based due work being lost.
- Main's 21 person-blocker cases and 13 completion-request/external-blocker
  cases catch dependent work being wrongly released or kept blocked, and
  missing completion evidence failing to prompt the user. The cached add/delete
  completion cases cover the new blocker probes together with snapshot reuse.
- The existing load proofs protect ownership, exactly-once work, quiet agents,
  execution limits, verified merges, complete HTTP accounting and budget bounds.

No test was added to check source structure, a compiler, a stub, an unreachable
path or a target count. Existing polish issue #704 remains separate from this
merge. The 600-second Workload deadline and the existing load cases/guards are
unchanged. Tests and measurement use synthetic/recorded command endpoints only;
there are no live room-cli or live GitHub API calls in them.

The paired measurement uses the archived main reader above with the merged
recording model. It retains all nine ticks, including changed-then-unchanged and
expired-then-unchanged, and refuses any candidate increase in GraphQL commands,
modeled requests or modeled points on any tick, or any due-output hash change.

## Results at the merge commit

- `598-merge-snapshot.txt`: three WZ-PROBE cases pass. Changed/recovery reads
  are `4 4 0 4 0 4 0`; expiry/recovery reads are `4 4 0 4 0`.
- `598-merge-cache.txt`: all 16 GI1 cases pass, including changed facts,
  identity, time and damaged-cache fallback, with complete due-line parity.
- `598-merge-person.txt`: all 21 person-blocker cases pass, including cached
  evidence addition/deletion; `598-merge-completion.txt` and
  `598-merge-external.txt` pass all 10 and three request/external-blocker cases.
  Total: **53 scoped shell cases**, with no assertion changes.
- `598-merge-main.json`, `598-merge-after.json`, `598-merge-measure.txt`:
  all **nine paired ticks** pass. GraphQL commands, modeled requests and points
  equal main on every tick. Both recovery ticks are zero for all three measures;
  all nine complete due-output hashes match. Both 20-response/event bytecode
  parity samples remain. The candidate reader's recorded hash matches the
  tested source. Timing and request-cost observations remain synthetic.
- `598-merge-carried.txt`: two carried-source proofs pass;
  `598-merge-router.txt`: 15 router proofs pass;
  `598-merge-seams.txt`: all seven existing seam proofs pass.
- `598-merge-load.txt`: all **14 default load proofs pass in 631.972 s**:
  100 tickets, five specs, 49 spec ticks, 6727 check questions, peak 308/1250
  GraphQL points per simulated hour, 100 verified synthetic merges and 200
  archives. The **600-second Workload guard passes unchanged**. The whole
  invocation also runs the other proofs and verification; 631.972 s is not
  described as a sub-600-second whole-command result. The fixture CLI was
  prebuilt with the existing locked Cargo dependencies before this invocation.
- `598-merge-fmt.txt`: format check passes (empty success output).
  Shell syntax and diff checks pass. `598-merge-standalone.txt`: standalone
  and privacy dry runs pass at the merge commit.

The load harness, fake, default 14-case suite and seam assertions are unchanged
from approved `a11d17b9664acb9c4b2d385b52e48028f9c00da8`. The final green
commit adds only these results and this ticket's STATUS entry. Existing R1 red
records remain unchanged; no new bug fix or new failing-first test is needed
for the counter-only conflict resolution.

A final refresh found main at `1189d6666ab2537739b652a554104f1e1d3cfdb0`.
Its reader is byte-identical to the measured main, and the merge-tree check
reports no conflict. Being behind alone does not require another merge.
All changes beyond the approved head came from main, except the reconciled
case total and this ticket's evidence/status records. Internal diff/checklist
review found no unresolved issue. Helpers: zero. CI at the new pushed head and
its independent review remain separate; the full 786-case shell suite is left
to CI. No live HTTP behavior or cost is claimed.
