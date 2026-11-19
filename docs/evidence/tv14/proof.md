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
| `test_committed_diff` | Reading dirty working-tree contents instead of the requested commits | Available locally |

The PR-only step's execution and pass require this PR's CI record; non-PR
skipping is checked by inspecting the single step's event condition and CI
records when available. Documentation and scope are independent review claims.
No deletions of existing tests; no downstream ticket needs a new seam.

Supporting edits: this folder records acceptance proofs for `budget.py` and
`test_budget.py` under J110; its wildcard carriage row registers only this
folder. The two exact script rows use spec #787's narrow registry grant.
No product changelog: this is infrastructure only.
