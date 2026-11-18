# TV12: skills checks after WZ12

[Ledger](ledger.md): every one of the original 48 tests has a row.
[Proof plan and helper check](plan.md).

Three checks exercise an executable skill boundary rather than comparing
sentences: the public dependency declaration validator, the research worker
GitHub-write guard, and research snapshot commands executed in fresh shells.
Their scripts match byte-for-byte between the installed pin and WizSkills.
The companion ports preserve the executable cases and remove exact prose pins.

The 32 retired tests compared sentence inventories, heading/order/file inventories
or the private Markdown parsers used only for those wording checks. Their
wording-enforcement behaviour is retired by #814; the skill instructions,
approval rules and runtime guards remain. In particular the isolation parser
was not a shipped Markdown parser: every caller was a test in this one file.
All 23 references to the three retired wording validators are inside the
original test file (`git grep` at the base commit). No runtime allowlist,
privacy guard, contract, workflow or dependency changed.

OpenWiz keeps its harness-link checker and planted bad-link cases, local release
contract checks, public install-prompt integration check and all six wrappers
that execute its install/setup suites. These span the installed skills and the
OpenWiz consumer; none belongs to one Rust product crate, so they remain shared.

The portable originals remain too until the companion's exact-head CI receipt
runs their replacements green. The six other suite wrappers have no WizSkills
replacement and stay; see their named replacement requirements in the ledger.

## Proof and limits

- `before-skills.txt`: all 48 base skills tests passed.
- `port-mutations.txt`: all three ported tests fail after a controlled break of
  the behaviour they protect, in temporary copies only. Production scripts are
  unchanged; this migration is not a product bug fix.
  Reproduction: copy the affected skill to a temporary directory and run its
  new suite after (a) replacing `check-relies.sh` with `#!/bin/sh\nexit 0\n`,
  (b) replacing `"$work/after"` with `"$work/before"` throughout
  `check-workers.sh`, or (c) removing the single quotes around
  `<snapshot-path>` in the documented `check` command. Each suite must fail.
- The kit's before/after `checks` measurement runs in isolated worktrees with
  Rust 1.99.1 and cargo-llvm-cov 0.9.1, with two build jobs and test threads.
- Sandbox run times are deliberately omitted from human-facing logs and the
  comparison. Only CI job durations on the same lane can support a speed claim.
  The kit's original JSON results retain its required schema, including seconds;
  those local values are not a campaign timing claim.
- No live effect, publication, pin advance or release is proven or performed.

The existing `tools/test-value/evidence/**` import row covers this evidence:
no `tools/open-import/paths.json` row is added. No product changelog is needed.

## Measured checkpoint result

`before.json` is the exact base; `after.json` measures the unchanged Rust source
of checkpoint `0f797a784a290e3b5a483c8aafe4bf4fe24c6f67`. The following
commit adds only evidence. Both instrumented and plain target runs passed.

- Checks target: 133 to 101 tests; skills group: 48 to 16.
- Compiled test source: 23 files in each, 437,689 to 364,509 bytes, 12,019 to
  10,133 lines. This is the kit's compiled-source size, not evidence-file size.
- Coverage: 200 covered product lines before and after, unchanged in every
  crate; `drops: none`. Full comparison in [compare.txt](compare.txt).
- The three ported executable checks remain in Rust at this checkpoint because
  the companion CI receipt is pending. This is not the completed T5 hand-back.
  Remove those originals only on the named green receipt, and refresh the
  measurement if the source changes. The six suite wrappers still have no
  replacement and must remain.
