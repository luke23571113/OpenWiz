# OpenWiz checkpoints contract, version 1 (`openwiz.checkpoints.v1`)

Each spec answers two questions when it is planned, and the answers decide the owner's checkpoints. This contract fixes the two answers' lines on a spec body, how a spec without them is read, the evidence ask a fleet posts before a user-visible spec's final merge, the owner's late-look record, and how that record releases the held merge.

**Contract only** (#1829, RC1 of spec #1828). It changes no code. RC2 (#1830) makes plan-graph write the answers and the approval check refuse a new spec without them; RC3 (#1831) makes launch-fleet hold a user-visible spec's final merge. Each proves its own part at its own seam, against the fixtures in [`fixtures/checkpoints/`](fixtures/checkpoints/).

Authority: spec #1828 and its confirmed grill, J239 R1 to R3, a private record. It relies on the [open development contract](open-development.v1.md) for the decider, the pointer and the public record forms.

**Examples.** Every example and fixture is synthetic: the decider `Robin`, every issue, pull request and comment number, commit, date, login, link and word. Only the private repository's name is real, because the pointer form needs it.

## Words

| Word | Meaning here |
| --- | --- |
| **Owner** | The decider of the open development contract: Jake. |
| **Early say** | The owner decides the spec in its grill, before it is planned (as today). |
| **Late look** | The owner looks at evidence of the change working before the spec's final merge: a preview link, screenshots or a short video, never code. |
| **Final merge** | The merge of the spec's last open planned ticket: the one after which no planned ticket of the spec is open. |
| **Record author** | A login in the `Record authors` row of `docs/agents/fleet.md`'s `## GitHub identity` table. |

## The two answers

A spec body carries one section, written by plan-graph's to-spec when the spec is planned and confirmed with it:

```text
## Checkpoints

- One-way door: <yes|no>
- User-visible: <yes|yes, a release|no>
```

- The heading is exactly `## Checkpoints`, once in the body. The section runs to the next line starting `## ` or the end of the body. Any other heading line that names checkpoints (`## Checkpoint answers`, `### checkpoints`) makes the body invalid, never absent.
- Its non-blank lines are exactly these two, in this order, each value exactly as shown. The reason for an answer goes in the spec's other sections, never on these lines.
- **One-way door: yes** gives the owner the early say. **User-visible: yes** gives the late look too.
- **A release counts as user-visible.** A spec that publishes a release (a tag, a package or a published version) answers `User-visible: yes, a release`. A release is never `no`.
- **Neither:** both `no` (refactors, docs, internal tooling) means no checkpoint: the spec merges on the agents' checks.

How a spec body reads:

| Body | Reading | Early say | Late look |
| --- | --- | --- | --- |
| Both lines valid | `answered`, with each answer | when one-way door is `yes` | when user-visible is `yes` or `yes, a release` |
| No heading that names checkpoints | `absent`: a spec planned before this contract | yes | no |
| Anything else | `invalid`, with a code below | yes | yes |

- **Absent is early only.** A spec approved before this contract, or any spec without the section, keeps today's behaviour: its merges flow. Whether a new spec may be absent is the approval check's rule (RC2): it refuses a new spec without both answers.
- **Invalid is read as both yes.** The approval check refuses it. A fleet that finds one on an approved spec never guesses `no`: it holds the final merge for a late look like any user-visible spec.
- Invalid codes: `section-heading` (a heading that names checkpoints but isn't exactly `## Checkpoints`), `section-repeated` (two `## Checkpoints` headings), `answer-missing` (fewer than two non-blank lines), `answer-line` (any other line, value, order or a repeated answer).

## The evidence ask

When a user-visible spec's final merge has an approved, green, mergeable head, the fleet holds it and posts one evidence ask as a comment on the spec, from a record author:

```text
launch-fleet: late look asked #<P> at <commit>

Evidence: <preview|screenshots|video> <https link>
Look for: <what the owner should see working, in plain words>
```

- `#<P>` is the held pull request and `<commit>` its approved head, the full 40-character lowercase commit.
- One or more `Evidence:` lines, then exactly one `Look for:` line, and nothing else: no code block, no diff, no other line. Blank lines don't count.
- **Never code.** An evidence link to code is refused, whatever the letter case of its host: a GitHub pull request, commit, file, tree, compare, raw or blame page, a raw file host or a gist. Screenshot uploads (`https://github.com/user-attachments/…`) are evidence.
- It carries no thread id and no exact words, like every public record.
- **One ask per head.** The fleet posts none while a valid ask for that pull request and commit exists. A new head needs a new ask.
- Invalid codes: `ask-opening` (the first line), `evidence-missing` (no `Evidence:` line), `evidence-code` (a link to code), `ask-line` (any other line).

## The late-look record

The owner's look is recorded as a comment on the spec, from a record author, in the open development contract's public form for a decision: the decision, its date and the pointer, never the exact words.

```text
**Late look by <decider>, <YYYY-MM-DD>, #<P> at <commit>:** <approved|changes asked>: <decision>
Private record: <pointer>
```

- `<decider>` is the owner, by the name the open development contract's decider list has (`Jake`; tests add the synthetic `Robin`). A record naming anyone else releases nothing.
- `<YYYY-MM-DD>` is a real calendar date.
- `#<P> at <commit>` names the pull request and commit of the evidence ask it answers.
- `<decision>` is the recorder's own plain words for what the owner decided, on that one line, with no double quote mark (`"`, `“`, `”`). The exact words stay in the private record.
- The second line is exactly `Private record: <pointer>`, where `<pointer>` is the open development contract's pointer to the comment holding the exact words. A link to anything else is refused.
- Exactly these two non-blank lines. Who records the look, and how the owner is reached, is the orchestrator's routing, unchanged.
- Invalid codes: `record-opening` (the first line, a date that isn't real, its commit or outcome), `quoted-words` (a quote mark in the decision), `pointer-missing` (no `Private record:` line), `pointer-not-private` (a link that is not a pointer), `record-line` (any other line).

```good
**Late look by Robin, 2030-01-05, #4012 at 1111111111111111111111111111111111111111:** approved: the settings page works as the evidence shows.
Private record: https://github.com/jparker2006/ClosedWiz/issues/9001#issuecomment-9000000011
```

## Releasing the held merge

Only the final merge of a spec whose late look is `yes` (answered user-visible, a release or invalid) is held. Every other merge, and every merge of a spec whose answer is `no` or absent, flows as today.

The fleet reads the spec's comments in creation order, keeping only valid asks and records from record authors that name the held pull request and its current approved head, and records whose decider is the owner:

| Comments for the head | The merge |
| --- | --- |
| No valid ask | held, `ask-due`: the fleet posts the ask |
| An ask, and no record after it | held, `look-due` |
| The newest record after the first ask says `changes asked` | held, `changes-asked` |
| The newest record after the first ask says `approved` | released: it merges as the standing merge rules say |

- A record before the ask, for another commit, from anyone but a record author, naming a decider who is not the owner, or invalid never releases a merge.
- A new head (after changes, or after `main` is merged in) starts over: the earlier look covered other evidence.
- `changes asked` keeps the hold; the changes go through the ticket's normal review, and their new head gets a new ask.

## The forms, for readers

The line forms as regular expressions, each matched against a whole line. Readers (RC2's approval check, RC3's merge helper and the fixtures' reader) read this block rather than copying it.

```checkpoints-v1
{
  "section": "## Checkpoints",
  "section_like": "(?i)#+ *checkpoint.*",
  "one_way_door": "- One-way door: (yes|no)",
  "user_visible": "- User-visible: (yes|yes, a release|no)",
  "ask_opening": "launch-fleet: late look asked #([1-9][0-9]*) at ([0-9a-f]{40})",
  "ask_evidence": "Evidence: (preview|screenshots|video) (https://\\S+)",
  "ask_look_for": "Look for: (\\S.*)",
  "code_link": "(?i)https://(www\\.)?(github\\.com/[^/]+/[^/]+/(pull|commit|commits|blob|tree|compare|raw|blame)([/?#]|$)|raw\\.githubusercontent\\.com/|gist\\.github\\.com/)",
  "record_opening": "\\*\\*Late look by ([A-Z][A-Za-z-]*), ([0-9]{4}-[0-9]{2}-[0-9]{2}), #([1-9][0-9]*) at ([0-9a-f]{40}):\\*\\* (approved|changes asked): (\\S.*)",
  "record_pointer": "Private record: (https://github\\.com/jparker2006/ClosedWiz/(issues|pull)/[1-9][0-9]*#issuecomment-[1-9][0-9]*)"
}
```

`code_link` is matched at the start of an evidence link; the others match a whole line. `section_like` finds a near-miss heading: a line it matches that is not exactly `section` is `section-heading`.

## Fixtures

[`fixtures/checkpoints/`](fixtures/checkpoints/) holds one file per case and [`expected.json`](fixtures/checkpoints/expected.json), each file's reading. `python3 -I contracts/fixtures/checkpoints/check.py` reads them all as this contract says and fails on any difference.

| Folder | Cases |
| --- | --- |
| `spec/` | both answers yes, both no, each alone, a release, absent, and each invalid code |
| `ask/` | a valid ask, a second head's ask, a code link, a code link in capitals, no evidence, a code block, a short commit |
| `record/` | approved, changes asked, a second head's record, quoted words, no pointer, a public link, a changed opening, an unknown outcome, an extra line, a date that isn't real, another decider |
| `release/` | a fleet state (spec, whether the merge is final, head, record authors, the deciders list, comments in order) for every row of "Releasing the held merge", a release spec, and each case that flows |

## WizSkills copy

WizSkills carries this file byte-identical at `contracts/checkpoints.v1.md`, for RC2 and RC3. Any change here changes both, in the same version.
