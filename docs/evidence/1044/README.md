# #1044 / #1060: stage the service without a parent writer

Synthetic fixtures only. Published logs replace scratch paths and process ids.

## Current implementation

Under owner decision J146 (private record), the only new updater command is:

```text
/bin/cp -- <root>/service/builds/<commit>/source/target/release/openwiz-service <root>/service/builds/<commit>/openwiz-service
```

Both paths are absolute, under the same build directory, and use the same typed
commit, also checked against the immutable runner call's commit. No other flags
or copier forms are accepted. The existing runner supplies environment clearing,
process-group isolation, null stdio, cancellation and descendant cleanup. The
p08a runner inventory is unchanged. The adapter allowlist is unchanged.

The source is checked with `symlink_metadata`. The build directory is created
new at 0700 in this attempt; staging also refuses any planted destination before
copying. After copying, the parent sets mode 0700 by path, verifies `private()`
(owned, regular, no symlink, one link), fsyncs a read-only file handle and the
build directory, and executes the existing identity check. The parent never
opens a writable descriptor for the candidate. Web copying remains unchanged.

## Red first

- `red-80dd129.md` preserves the strongest original proof and its ten failing
  runs from `80dd129`, including the observed ETXTBSY identity exec.
- `red-etxtbsy-j146.log` reruns that proof here with only `stage_program`
  temporarily restored to `copy_file(source, destination, 0o700)`. It fails at
  the staging assertion with an inherited writer retained. The temporary
  mutation was restored before committing.
- `red-allowlist-j146.log` runs the extended command table before the allowlist
  fix: it fails because the approved copier form is refused.

The proof and both red logs were committed before the runner fix. The earlier
`red.log` and `green*.log` describe PR #1084's original direct-copier attempt,
not the current head. `inherited-writer.c` is the earlier #1046 scheduling probe.

## Owning tests

- `a_concurrent_fork_cannot_keep_the_staged_program_busy` (preserved from
  `80dd129`): catches #1060/#1044 when parent-side staging leaves a writer that
  a concurrent fork can retain, making the identity exec fail with ETXTBSY.
  Git and identity exec are real; build gates are synthetic. A 64 MiB padded
  candidate gives the watcher a window to retain any parent writer until the
  attempt ends. Existing tests did not arrange that scheduling hazard.
- Extended `only_the_complete_fixed_gate_can_run`: catches #1060 if copier
  authorization accepts relative paths/programs, extra or missing flags,
  mismatched or invalid commits, another destination or another build root.
  Its existing table had no copier rows.
- `staging_refuses_a_planted_target_a_symlinked_program_or_another_identity`:
  catches #1060 if staging overwrites a planted path, follows a symlinked build
  output, or queues another compiled identity. Its fake now sends copier calls
  through the real System runner.
- Keeper `a_passing_main_merge_is_staged_but_not_reported_as_running` still
  compiles and stages a real service and verifies the complete gate and queued
  result. It is also run under the earlier retained-writer preload probe.
  The dedicated proof replaces its former `fixture::Inheritor` watcher.
- No new test for fsync: crash durability is retained by explicit file and
  directory sync calls and reviewed, not claimed from a fixture run.

## Supporting edits

`tools/open-import/paths.json` adds only this ticket's evidence-folder row under
fleet.md's standing supporting-edit rule, kind 1. It supports the owned staging
proof/evidence paths and the failing-first/CI acceptance criteria: the old CI
refused these unclassified added evidence files before product tests could run.
No import policy or guard logic changes. `changes/1060.md` is the owned product
changelog line. There are no new dependencies or live-update claims.

## Current scoped results

- `green-allowlist-j146.log`: the fixed-form table passes, including every
  negative copier row.
- `green-etxtbsy-j146.log`: the preserved concurrent-writer proof stages and
  queues the candidate with no parent writer observed.
- `green-safeguards-j146.log`: all three refusal rows pass.
- `green-probe-j146.log`: the real release-build keeper passes under
  `OW_UPDATE_KEEP_WRITER=1` and `LD_PRELOAD` of `inherited-writer.c`; the
  retained-writer hook does not fire because staging opens no parent writer.
- `green-checks-j146.log`: formatting, `cargo clippy -p openwiz-service
  --all-targets -- -D warnings`, and the existing p08a source-contract suite
  pass, including the unchanged updater-runner inventory and planted violations.
