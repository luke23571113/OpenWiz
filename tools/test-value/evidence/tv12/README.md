# TV12: skills checks after WZ12

[Ledger](ledger.md): every one of the original 48 tests has a row.
[Proof plan and helper check](plan.md).

Three executable checks move to the owning WizSkills suites: the public
dependency declaration validator, the worker GitHub-write guard, and snapshot
commands executed in fresh shells. Their production scripts match byte-for-byte
between the installed pin and WizSkills. All three replacement suites ran green
in [WizSkills CI 44390693366](https://github.com/openwizdev/WizSkills/actions/runs/44390693366)
at `0564f5e3cb3c0e8a2461279ee1dcfbe7e69051b1` before the Rust originals were
removed. [wizskills-ci.json](wizskills-ci.json) records each explicit pass receipt.

The 32 retired tests compared sentence/heading/order/file inventories or private
Markdown parsers used only for those wording checks. Their wording-enforcement
behaviour is retired under #814; the instructions and supported runtime behaviour
remain. All 23 references to the three retired wording validators were inside
the original test file (`git grep` at the base). No production guard changed.

OpenWiz retains 13 integration checks: its harness-link checker and planted bad
links, local release contract checks, public install-prompt integration, and all
six wrappers of its install/setup suites. Those six have no green WizSkills
replacement; their required replacement scripts are named in the ledger.
These cross the installed package and OpenWiz-owned consumer files, so stay in
the shared target rather than a single Rust crate.

## Evidence

- `before.json`: the exact base, `aa09045873946bf512f7e2ad538ecc17384366d8`,
  measured in its own detached worktree; all 133 checks-target tests passed in
  instrumented and plain runs.
- `after.json` and `compare.txt`: final Rust source with the three portable
  originals removed, measured with the same kit and toolchain. Refreshed after
  the green replacement receipt, rather than relabelling the checkpoint report.
- `checkpoint-after.json`: the earlier 101-test checkpoint, still retaining
  the three originals pending that receipt. Its 16-test skills-only run is
  `after-skills.txt`; these are intermediate evidence, not final counts.
- `before-skills.txt`: the initial 48-test group run; the plan records its
  formatting-concurrency correction. The independent base measurement above
  provides the source-bound baseline.
- `port-mutations.txt`: all three ported suites fail at their behaviour
  assertions after a controlled break, in temporary copies only. Production
  scripts are unchanged. Reproduction: copy the affected skill and run its new
  suite after replacing `check-relies.sh` with `#!/bin/sh\nexit 0\n`, replacing
  `"$work/after"` with `"$work/before"` in `check-workers.sh`, or removing the
  single quotes around `<snapshot-path>` in the documented `check` command.

## Method and limits

Rust 1.99.1, cargo-llvm-cov 0.9.1, two build jobs and test threads. Each measured
checkout has its own target folder. Sandbox duration is omitted from the human
comparison; only CI job durations on the same lane support campaign speed
claims. Original kit JSON retains its required schema, including seconds, which
are not used as timing evidence. No speed claim is made here.

The existing `tools/test-value/evidence/**` import row covers all evidence:
no paths.json row added. No product changelog, dependency, contract, workflow,
pin, release, publication or live action changes. Full product suites run in CI.

## Final result

The checks target goes from **133 to 98 tests**; the skills group goes from
48 to 13 here, with three executable proofs running in WizSkills. The kit
reports 23 compiled Rust source files in each run. Final source size and per-crate
coverage are in [compare.txt](compare.txt): **200 covered product lines in each
run, unchanged in every crate; drops: none**. Both instrumented and plain runs
passed on final Rust blob `5bc91e467840f1a110df9f6d514b1ba99741e4c9`.
