# TV14 proof plan

All inputs are synthetic; these are fixture proofs, not live observations.
The command is `python3 -I tools/test-value/test_budget.py`. Each case invokes
`budget.py` as a process in a private temporary Git repository with real commits
and a PR event description. No existing test exercises this new CLI boundary.

| Claim / owning test | Catches | Readiness |
| --- | --- | --- |
| `test_boundary_and_offsets` | Off-by-one ceiling, gross instead of net counting, and ignoring deletion offsets | Available locally |
| `test_allowance` | Passing an insufficient allowance or rejecting a sufficient recorded allowance | Available locally |
| `test_test_paths_only` | Missing a supported test path or charging product/evidence lines outside those paths | Available locally |
| `test_renames_and_unusual_names` | Rename heuristics or quoted filenames hiding test growth | Available locally |
| `test_unreadable_revisions` | A missing base/head or failed comparison silently passing | Available locally |
| `test_unreadable_description` | Missing, malformed or non-string descriptions silently passing | Available locally |
| `test_malformed_allowance` | Accepting malformed, unjustified or duplicate allowances | Available locally |
| `test_binary_test_file` | Uncountable test changes silently treated as zero | Available locally |
| `test_committed_diff` | Reading dirty working-tree contents or borrowing deletion credit from newer main-only tests | Available locally |

The PR-only step's execution and pass require this PR's CI record; non-PR
skipping is checked by inspecting the single step's event condition and CI
records when available. Documentation and scope are independent review claims.
No deletions of existing tests; no downstream ticket needs a new seam.

Supporting edits: this folder records acceptance proofs for `budget.py` and
`test_budget.py` under J110; its wildcard carriage row registers only this
folder. The two exact script rows use spec #787's narrow registry grant.
No product changelog: this is infrastructure only.

Results: all nine CLI proofs pass after enforcement. The initial red run is
`red.txt`; `red-advanced-base.txt` additionally proves that a direct base/head
diff incorrectly grants 600 deleted lines of credit when main advances.
`passing.txt` records the complete passing fixture suite. No campaign speed
claim is made from these local logs; timing comparisons require CI lanes.

## R1: the budget step must be classified by the collector

Claim: the approved budget step has exactly one CI measurement category,
so the workflow coverage check and CI benchmark can read PR runs containing it.
Existing owning proof:
`tools/collector/test_ci3.py::Steps::test_check_steps_covers_ci_and_refuses_a_step_with_no_row`.
Catches: a new CI step missing from the collector table, or a checker that
accepts an unknown step. Available locally through `ci3.py check-steps` and
`test_ci3.py`; no new test is needed because this existing test fails for R1.
`red-r1.txt` records both the checker refusal and this test's assertion failure.
J110 kind 1 covers this ticket's one exact `build` row in
`tools/collector/steps.tsv`, beside the carriage guard; it supports the owned
PR workflow step without changing that workflow or the collector's logic.
R2 (#1162) and R3 (#1163) remain separate polish work.
