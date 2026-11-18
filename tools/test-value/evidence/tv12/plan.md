# TV12 proof plan

Base OpenWiz: `aa09045873946bf512f7e2ad538ecc17384366d8`.
Base WizSkills: `c112b993d0ec582d2aae370cf8011810fde9aea2`.

- T1: review every `tests/checks/skills.rs` test in `ledger.md`, including
  exact keepers for executable checks and explicit retirement of wording-only
  test machinery. Keep OpenWiz harness/consumer/release integration checks here.
- T5: port `plan_graph_relies_on_form`, `research_worker_github_check` and the
  executable portion of `research_snapshot_path_survives_fresh_shells` to the
  owning skill's Python suites. Run their public scripts against the same
  synthetic cases, with no real GitHub calls. WizSkills CI at the companion
  PR's exact head must run them before claiming completion.
- Preserve the six Rust wrappers of OpenWiz install/setup suites: those tools
  remain in OpenWiz, and WizSkills currently has no replacements for them.
- Test rule: no new product behaviour. Each ported test names its existing bug;
  execute a bounded mutation to confirm the suite catches a broken public script.
- Coverage: #814 names T1/T5, rather than T2, as its proof. Inspect whether the
  base's skills group is green before attempting kit measurement; a red run is
  never presented as coverage evidence. CI alone supplies comparable run time.
- No release, dependency, workflow, lock or protected runtime guard edit is authorized.
  The exact WizSkills `SUITES` registration request is on #814; await it before
  editing `check/run.py`.

The base's 48 skills tests passed (`before-skills.txt`), and the kit's `checks`
baseline passed all 133 tests in an isolated base worktree (`before.json`). Compare only
coverage/count/size locally, never sandbox timing. All three portable test
mutations were killed (`port-mutations.txt`); each reached its behaviour assertion.
The replacement suites are tests of existing scripts, not a product fix, so
there is no production red/green implementation pair.

WizSkills `check/run.py` received only the three own suite entries, under J110
as explicitly confirmed in #814 comment 6990532152. No runner, inventory guard,
rule or workflow changes.

Helper: scout, behavioural keeper/runner mapping at base
`aa09045873946bf512f7e2ad538ecc17384366d8` (WizSkills
`c112b993d0ec582d2aae370cf8011810fde9aea2`), ISSUES. Used eight source-verified
items: three missing keepers, restricted PATH, six retained wrappers, explicit
registration, collection and runner boundary. Deferred its isolation parser
migration suggestion because that parser only validated the retired wording.
No wrong factual items found. Archived after reading.
No-push check: `clean #814: nothing changed but the writes you named (branches 0, comments 2)`.

Run-provenance correction: `cargo fmt --all` was invoked while the initial
48-test skills run was still executing. That violated fleet.md's one-Cargo-
command rule, although formatting neither built nor replaced a binary. The
independent base kit measure used the untouched detached worktree and passed
all 133 tests; the pruned 16-test run completed before scoped Clippy, and the
after kit measure has its own output. The base measurement, rather than the
initial run alone, supplies the source-bound baseline evidence.
