# First-review R1: ordinary JavaScript false refusals

Report: [#1098, comment 6965602444](https://github.com/openwizdev/OpenWiz/pull/1098#issuecomment-6965602444),
authored by the configured record author, at `736da8fcbb36a58256c2ed465ad18539851cb0fe`.
This is #1093/#1098's single first-review fix round, followed by the same
reviewer's one re-check. WM1 #1056/#1079 remains complete and separate.
Only blocker R1 is addressed. R2/R3/R4 remain polish #1100/#1101/#1102.

## Cause, closure and proof plan (before the fix)

The lexer models only a number as a division operand and only a small list of
punctuators as regex starts. It also reads a shebang as code and loses the
context of a closing parenthesis. This rejects ordinary public consumers
before their resolvable dependency loads. All affected paths reach the same
`js_code` lexer for `.js`, `.mjs`, `.cjs` and `.ts`; no consumer edits are needed.

| Claim | Evidence, owner and readiness |
| --- | --- |
| Reproduce the real-tree regression | Builder; available now. `r1-real-tree-base.txt` and `r1-real-tree-before.txt`: both checkers on the same clean reviewed tree. Baseline has 2 pre-existing dynamic refusals; reviewed checker adds 39 ordinary-JavaScript slash refusals. |
| Ordinary syntax retains following direct/multiline loads | Builder; synthetic CLI table `test_javascript_ordinary_syntax_keeps_following_loads`, with each consumer run in Node and tree digests checked. Red on the reviewed implementation, then green with the fix. Covers shebang, `!`, arrow/`>`, identifier/bracket/string/template/postfix/regex division and matched control/call/group parentheses. |
| Real loads in division operands remain visible | Same table: one collector is loaded as a division operand and again afterward; its first reference must remain line 1. |
| Truly ambiguous syntax still refuses with location and no sets | Existing uncertainty test, replacing the wrongly classified `if (...) /regex/` negative with a closing-brace ambiguity. The original valid `if` consumer moves to the new retaining table as its keeper; its behavior is corrected as R1 requires. No test method is deleted. |
| Closure on the actual public tree | Builder; available after fix. `python3 -I ci/wizroom/split.py --root .` must emit zero `ambiguous JavaScript slash` refusals, keeping the two baseline dynamic refusals and no sets. This is a read-only local-tree observation, not live migration. |
| R11 and prior controls stay intact | Existing full split suite, including original regex backtick direct/multiline Node proofs, comments/templates, dynamic refusal and tree digests. |

No contract, workflow, dependency, consumer or other ticket's logic changes.
Only owned checker/test/evidence paths change in this round. The evidence folder
is already covered by the PR's standing-rule registry row; no new supporting edit.

Added test: `test_javascript_ordinary_syntax_keeps_following_loads` catches:
valid ordinary JavaScript refuses the entire split, preventing WM2 from obtaining
a move report despite resolvable collector loads. The existing tests miss this
because their division examples use only numbers, and their regex starts use `=`.

The closing-brace ambiguity remains deliberately refused; this round does not
add a complete JavaScript grammar. No live services, writes or delete APIs are
used. Exact-head required CI remains the hand-back gate.
