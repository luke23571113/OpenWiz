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
No runtime allowlist, privacy guard, contract, workflow or dependency changed.

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
- The kit's before/after `checks` measurement runs in isolated worktrees with
  Rust 1.99.1 and cargo-llvm-cov 0.9.1, with two build jobs and test threads.
- Sandbox run times are deliberately omitted from human-facing logs and the
  comparison. Only CI job durations on the same lane can support a speed claim.
  The kit's original JSON results retain its required schema, including seconds;
  those local values are not a campaign timing claim.
- No live effect, publication, pin advance or release is proven or performed.

The existing `tools/test-value/evidence/**` import row covers this evidence:
no `tools/open-import/paths.json` row is added. No product changelog is needed.
