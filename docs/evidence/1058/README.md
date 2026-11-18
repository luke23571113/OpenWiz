# WM2 proof plan

Authority: spec #979 revision 2, ticket #1058, and the replacement
[orchestrator ruling](https://github.com/openwizdev/OpenWiz/issues/1058#issuecomment-6969018434).
The earlier finite-target condition is superseded. Both harnesses retain their
caller-selected module inputs. No live publisher or service is changed.

| Claim / criterion | Boundary and evidence | Readiness / owner |
| --- | --- | --- |
| Only listed caller-supplied load sites add no dependency; unlisted dynamic loads still refuse | `python3 -I ci/wizroom/test_split.py`, synthetic trees with listed/unlisted sites, wrong line and a second unlisted load | Builder, now; red before implementation |
| WM-P1: no public consumer reaches the remaining war-room files; every original stay-set file is in `tools/collector/` | Fresh `split.py --root .` reports before and after relocation; compare each original stay path with its new path | Builder, after caller-supplied support and relocation |
| WM-P2: consumer behavior is retained | Existing stall-alarm, ci-overload, CI3, skills-eval, launch-fleet carried-copy and war-room proofs, changed only for paths | Builder scoped checks; CI full suites at exact head |
| The old publisher's no-publish preview still runs | Existing `tools/war-room/publish.py preview` command on synthetic local inputs with fake APIs; six output pages and privacy scan | Builder, after relocation; fixture evidence, no live claim |
| Move history is retained | `git log --follow` on a collector file reaches a pre-move commit | Builder, after committed `git mv` |
| Every open issue naming a moved file receives one notice | Complete paginated open-issue read, per-issue comment read before writing, and read-back of each notice | Builder, after exact mapping is known |
| No proof is weakened or lost | Full rename-aware diff; name the new location of each moved test; no assertion deletions | Builder and independent reviewer at exact head |
| Green hand-back | Required CI passes on the named head; independent review follows | CI/reviewer, pending ready PR |

Supporting edits use fleet.md's standing rule: kind 3, this ticket's evidence
under `docs/evidence/1058/`, to retain the red-first run and WM-P1/WM-P2 records;
kind 1, this ticket's own carriage-registry rows if needed for the new paths.
The checker/contract changes are covered by the replacement ruling, not by the
supporting-edit rule. Infra work needs no product changelog line.

The caller-supplied slice passes all 15 checker cases; its red log precedes
the implementation in commit `ac471bbb9793decc2623b57b342b7068f4356bf7`.
`before-move.txt` records the intermediate 307-stay/17-move report before the
executable-dependency ruling. It is not the relocation authority.

The read-only scout checked the pinned main: publisher entrypoint, chart
installation inputs, public consumers and preview commands. Its publisher,
package and shadow-import pointers were checked directly and used; no code
or test draft was supplied. The no-push audit recorded a hit for the fleet's
new delivery receipt, comment 6969038847. The original snapshot, saved window
and hit remain private and unchanged. Ruling
[6969174392](https://github.com/openwizdev/OpenWiz/issues/1058#issuecomment-6969174392),
with corrected delivery provenance, clears this specific legitimate fleet
write. The old mechanical result remains a hit, not a clean audit; future
checks remain required. The helper is archived.

## Executable-dependency slice

Ruling 6969174392 limits retention to executable dependencies. The owning
doc-link test now proves that prose does not retain its targets; its former
retention behavior was explicitly removed by that ruling. The synthetic-path
case catches test strings, comments and fixture logs retaining private code.
A Python-subprocess case keeps an actual invocation protected while textual
matches are removed. The loop fixture now contains an executable `argv`
instead of descriptive `reads` metadata. No other existing proof is removed.

`executable-red.txt` records the two intended failures before the filter
implementation (commit `7379572`). `executable-pass.txt` records all 17 cases
passing. `executable-report.txt` is the fresh result: 55 stay, 269 move.

Relocation stops under the ruling's explicit condition: the public overload
supplier imports `collect_ci`, which imports `gather` at lines 239 and 448.
`gather` imports `publish`, which imports `main` and `page`; `main` imports
`history`. These are actual executable imports, not textual mentions.
The factory collector also imports `gather` for privacy scanning. Resolving
that production coupling is not implemented by this checkpoint. No file has
moved, no publisher entrypoint or chart input has changed, and the granted
shadow.py import edit is not yet needed. This is not a green hand-back.

No new relocation test is planned: the existing consumer suites and the
contracted checker/preview boundaries already protect the behavior. The new
caller-supplied case catches a valid caller-selected harness input preventing a
split, or an unrelated dynamic load silently losing dependency protection.

## Shared runtime equivalence proof

[Ruling 6969452056](https://github.com/openwizdev/OpenWiz/issues/1058#issuecomment-6969452056)
authorizes extracting only the shared current-run reader, privacy scanner and
their required helpers/constants. `tools/collector/test_runtime.py` owns the
equivalence proof, using the pre-extraction definitions from public commit
`621e69c`, saved with their original source hashes in
`tools/collector/fixtures/runtime-baseline.json`. The baseline also preserves
the existing publisher privacy plants and one existing clean fixture.

The current-run claim compares the same synthetic reads, returned values,
read sequence, repeated enumeration, passthrough and refusal outcomes. The
privacy claim compares the same fixture bytes, every existing plant and its
escaped JSON form, binary/invalid-escape refusals and text-scan finding counts.
`runtime-red.txt` records the initial stubs reaching 22 intended assertion
failures before extraction. Both claims are fixture evidence, producible by
the builder now. Existing privacy tests will also run without assertion edits.
