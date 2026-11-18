# WM1R / WM-P1: JavaScript regex dependency retention

Scope: #1093, approved spec #979 revision 2, approval comment 6963194629,
fingerprint `8de30c79c914606daae1564750fdd21abd2ddc44c90d5732c86df621c9c42932`.
WM1 is complete; R11 is a separate ticket and does not reopen its review round.

## Proof plan (before the fix)

All proofs are owned by this builder, available now, and run at the checker CLI
on synthetic trees. Nothing here claims live migration or service behaviour.

| Claim / acceptance | Evidence and inputs |
| --- | --- |
| Exact R11 is a working consumer broken by the old move (AC1) | `reproduction.txt`: reviewer head 3786297, exact two-line Node consumer, marker collector; run before and after moving only the temporary collector. |
| Regression is red before code changes, including multiline (AC2) | `python3 -I ci/wizroom/test_split.py`; committed tests and `red.txt` before changing `split.py`. The parent checker is WM1's verified merge e52db337. |
| Direct/multiline loads after regex retain their collector (AC3) | `test_javascript_regex_does_not_hide_following_loads`; each consumer independently runs in Node and is checked through the CLI. Covers quotes, escapes, character-class slash and comment-like regex text. |
| Unknown loads and ambiguous regex syntax refuse with location and no sets (AC3) | `test_javascript_regex_uncertainty_refuses_without_sets`; computed load after regex, ambiguous slash and unterminated regex. |
| Ordinary regex, division, comments, quoted and template text behave correctly (AC4) | `test_javascript_regex_comment_and_template_controls`, plus all ten original split proofs unchanged. |
| The checker stays read-only (AC5) | Every old and new CLI invocation compares the synthetic tree digest before and after. Only the reproduction runner moves a temporary collector. No API or live-service tests. |
| Reviewable tests and exact-head checks (AC6) | PR lists `catches:` per added test; no deletions. Affected suite locally and required CI at the pushed head. CI remains pending until observed. |

Existing tests cover multiline loads, comments and dynamic refusal, but none puts
a backtick inside a regex before a load. The plausible break is the lexer
mistaking that backtick for a template opener and then hiding executable code.
The control matrix also protects against solving this by ignoring real templates
or treating every slash as a regex (which could swallow a division operand load).

Supporting edit: standing rule kind 1, own registry row
`tools/open-import/paths.json` adds `docs/evidence/1093/**`, required so the
public import/privacy inventory accepts this ticket's owned evidence folder.
No other registry row changes. Infra checker/tests/evidence: no product changelog.

Tests added (also listed in the PR):

- `test_javascript_regex_does_not_hide_following_loads` catches: a successful
  split moves a collector that a working Node consumer still loads after a regex.
- `test_javascript_regex_comment_and_template_controls` catches: non-code text
  retains an unused collector, or an ordinary regex/division hides a real load.
- `test_javascript_regex_uncertainty_refuses_without_sets` catches: uncertain
  JavaScript yields unsafe move sets instead of a located refusal.

No tests removed or weakened. No new dependency. No future seam is needed:
WM2 (#1058) consumes the unchanged split-checker CLI and its stay/move contract.
