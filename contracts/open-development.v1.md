# OpenWiz open development contract, version 1 (`openwiz.open-development.v1`)

OpenWiz is built in public, in **openwizdev/OpenWiz** (the **public repository**). The few things that must stay private stay in **jparker2006/ClosedWiz** (the **private repository**). This contract fixes what is private, where private records live, the public forms that point to them, the fleet's records without thread ids, what the privacy check (`tools/privacy-check/`) refuses, and what the importer (`tools/open-import/`) may carry.

**Examples.** Every example here is synthetic: the decider `Robin`, every issue, pull request and comment number, every date, id, path, email address and word. Only the two repositories' names and the public repository's two anchor commits are real. A block whose info string is `good` shows a form that is accepted; `bad` shows one that is refused, and the text before it says why. In this file only, the privacy check skips `bad` blocks (they are its planted cases); it scans everything else here, `good` blocks included.

## Words

| Word | Meaning here |
| --- | --- |
| **Decider** | The person whose words decide: Jake. The privacy check's decider list is exactly `Jake`; tests add the synthetic `Robin`. |
| **Exact words** | What a decider wrote or said, byte for byte. They are always private. |
| **Private record** | A comment on a private repository issue or pull request that holds a decider's exact words. |
| **Pointer** | The link from a public record to its private record (see "The pointer"). |
| **Public record** | Anything on the public repository: its files, commits, branches, issues, pull requests and their comments. |
| **Thread id** | A CloudRoom thread's id: `thr_`, a letter or digit, then letters, digits, `_` or `-` (T1). Always private. |
| **Private state** | What the fleet and the orchestrator keep outside public records: CloudRoom itself (its threads and loops) and `private/orchestration/` in the private repository. |

## Repository identity and discovery

Neither a directory basename nor the cwd's project title discovers a private
repository. A caller selects a private input explicitly and verifies its role;
no search for an adjacent folder named ClosedWiz is a source of identity. The
privacy check takes an explicit `--literals PATH --require-literals`; the hook
accepts that path directly or through `OPENWIZ_PRIVACY_LITERALS`, and an
explicit unreadable list refuses. Repository-qualified decision discovery uses
the optional private `decision_repositories` setting, as
[decisions v1](decisions.v1.md) says: `public` and `private`, each an exact
`{owner, name}`; a malformed, duplicate, unreadable or same-repository pair is
refused, never replaced by the cwd. A reader that can't tell which repository it
is on treats it as public.

```good
{"decision_repositories":{"public":{"owner":"synthetic-public","name":"work"},"private":{"owner":"synthetic-records","name":"archive"}}}
```

Bad: the two roles name the same repository under case folding.

```bad
{"decision_repositories":{"public":{"owner":"synthetic-owner","name":"work"},"private":{"owner":"SYNTHETIC-OWNER","name":"WORK"}}}
```

## What is private

Exactly these, and nothing more. Everything else is public: code, contracts, skills, tests, docs, ADRs, the glossary, the open tickets that move and every ticket and pull request made on the public repository.

**Files, by class** (each stays in the private repository):

| Class | Paths | Why |
| --- | --- | --- |
| Grills | `docs/grills/`, every file but `docs/grills/README.md` | Every reply is a decider's exact words |
| The private folder's own description | `private/README.md` | Part of the private record |
| Machine details | `private/machines.md`, `private/acceptance-lessons.md` | Machines, how agents reach them, the standing spike approval in exact words |
| Release reviews and approvals | `private/openwiz-*.md` | Exact words and real hosts |
| The orchestrator's HANDOFF and state | `private/orchestration/` | Private state, thread ids, exact words |
| Build and live evidence | `private/evidence/` | Live evidence with real identifiers and thread ids |
| Research | `private/research/` | Research notes in the private record |
| Design moodboard | `private/design/` | Third-party posts and images, not ours to publish |

So the whole `private/` folder is private, and so is `docs/grills/` except its README.

**Not files:**

- **Exact words.** In public, a decision is written as the decision, its date and a pointer.
- **Thread ids.** No public record carries one, in any form.
- **Real identifiers and anything personal:** the shapes and the private list in "The privacy check", and personal facts (devices, accounts, allowances) however written.
- **ClosedWiz's history and closed work:** every ClosedWiz commit, every closed issue and every merged or closed pull request stay in the private repository as the private record. None is copied.
- **Private state:** CloudRoom's threads and loops (their prompts hold thread ids and exact words) and the PC's loop folders. They are never published.
- **The private repository's visibility.** It stays private for good.

**Public, though they name the private side:** the name ClosedWiz, the pointer, the two cross-links, and branch names of the form `room/<title>-<suffix>` (a branch name is not a thread id).

## Where private records live

All private records live in the private repository, and nowhere else.

- **Files** of the private classes above, at their paths.
- **Exact words** in a private record comment on a private repository issue or pull request:
  - when the decision is on a private repository issue or pull request, a comment there. Today's approval comments on ClosedWiz (`**Plan graph approved by <decider>, …:**` followed by the quoted words, and the others) already are private records, and pointers may name them;
  - when the decision is on a public repository issue or pull request `#<N>`, a comment on the private repository issue titled exactly `Private record: OpenWiz #<N>`, opened on first use;
  - when it has no issue or pull request (a standing approval given in the orchestrator's thread), a comment on the private repository issue titled exactly `Private record: standing approvals`.

  A new private record comment opens with `**Private record for <subject>, <YYYY-MM-DD>:**`, where `<subject>` is `OpenWiz #<N>`, `ClosedWiz #<N>` or `standing approvals`, then the exact words in double quotes, with what they answered. It is private, so the privacy check never reads it.
- **Private state** in CloudRoom and in `private/orchestration/`.

## The pointer

A pointer is exactly one URL to the comment that holds the exact words:

```text
https://github.com/jparker2006/ClosedWiz/issues/<N>#issuecomment-<C>
https://github.com/jparker2006/ClosedWiz/pull/<N>#issuecomment-<C>
```

`<N>` and `<C>` are positive decimal numbers without leading zeroes. `pull` is for a comment on a pull request's conversation, which GitHub's API also calls an issue comment and links that way; it widens the spec's "issue comment" only in its URL, so that a grill pull request's records can be pointed to. The comment must exist and hold the exact words; a link to anything else (a file, a commit, an issue without a comment, a public repository comment) is not a pointer. Only people with access to the private repository can open it, and that is the point: the decision is public, the words are not.

```good
https://github.com/jparker2006/ClosedWiz/issues/9001#issuecomment-9000000001
```

Bad: a link to a grill file, not to a comment.

```bad
https://github.com/jparker2006/ClosedWiz/blob/main/docs/grills/2030-01-02-synthetic.md
```

Bad: a comment on the public repository; it can't hold exact words.

```bad
https://github.com/openwizdev/OpenWiz/issues/4001#issuecomment-4000000001
```

## Public approval records

A spec confirmation, a plan approval and an approval on its own (including one under a standing approval) are comments on the public repository. Each records **the decision, the date and the pointer**, never the exact words.

**First line:** today's opening, so every reader still finds the latest record the way it does now, then the decision:

```text
**Spec confirmed by <decider>, <YYYY-MM-DD>:** <decision>
**Plan graph approved by <decider>, <YYYY-MM-DD>, revision <N>:** <decision>
**Approved on its own by <decider>, <YYYY-MM-DD>:** <decision>
**Approved on its own by huntr, <YYYY-MM-DD>, tier <t>, kind <k>:** <decision>
```

**Second line:** exactly `Private record: <pointer>`.

**The rest** is as today: a plan approval's "Changed since" line, table, `Fingerprint:` line and revision text; an approval on its own's link to the brief, owned paths and Relies on.

- `<decision>` is the orchestrator's own plain words for what was decided, on that one line. It contains no double quote mark (`"`, `“`, `”`) and is never the exact words: it says what was decided, not how the decider put it.
- **A standing approval** is recorded where it is used: the approval on its own names it in the decision (for example `under Robin's standing approval for fixes to a red main`, or huntr's `under Robin's standing approval (ADR 0014)`), and its pointer is the private record where the standing approval was given.
- The whole comment contains no double-quoted exact words, no blockquote of them and no thread id.

```good
**Plan graph approved by Robin, 2030-01-02, revision 2:** approved as proposed, with the import waiting for a separate go-ahead.
Private record: https://github.com/jparker2006/ClosedWiz/issues/9001#issuecomment-9000000002
```

```good
**Spec confirmed by Robin, 2030-01-02:** confirmed, with consistent history as a requirement.
Private record: https://github.com/jparker2006/ClosedWiz/issues/9002#issuecomment-9000000003
```

```good
**Approved on its own by Robin, 2030-01-03:** approved under Robin's standing approval for fixes to a red main.
Private record: https://github.com/jparker2006/ClosedWiz/issues/9003#issuecomment-9000000004
```

Bad: today's private record form, quoting the exact words in public.

```bad
**Plan graph approved by Robin, 2030-01-02, revision 2:** "approve, but keep the import for later"
```

Bad: no pointer line.

```bad
**Spec confirmed by Robin, 2030-01-02:** confirmed.
```

Bad: the opening changed, so readers looking for `**Plan graph approved by` miss it.

```bad
**Robin approved the plan graph, 2030-01-02, revision 2:** approved as proposed.
Private record: https://github.com/jparker2006/ClosedWiz/issues/9001#issuecomment-9000000002
```

## Decision sources in documents

A document line that gives a decision's source (fleet settings, ADRs, docs, skills) says who decided, when, the decision in plain words, and the pointer as a Markdown link with the text `private record`:

```text
<decider>, <YYYY-MM-DD>: <decision> ([private record](<pointer>)).
```

```good
Source: Robin, 2030-01-04: every Codex thread runs in fast mode ([private record](https://github.com/jparker2006/ClosedWiz/issues/9004#issuecomment-9000000005)).
```

Bad: the exact words, quoted, with no pointer.

```bad
Source: Robin, 2030-01-04, in the orchestrator's thread: "make the codex ones fast"
```

## Fleet records

The fleet's public records (comments starting `launch-fleet:`) carry **no thread id**. Each public form below replaces the legacy form, which only the private repository still accepts; every other record is unchanged.

| Today (private repository only) | Public form |
| --- | --- |
| `launch-fleet: started, thread <id>` | `launch-fleet: started` |
| `launch-fleet: start checked, thread <id>, branch <branch>` | `launch-fleet: start checked, branch <branch>` |
| `launch-fleet: builder fallback due, thread <id>, branch <branch>` | `launch-fleet: builder fallback due, branch <branch>` |
| `launch-fleet: resume starting <wait comment id> for #<B>, thread <id>` | `launch-fleet: resume starting <wait comment id> for #<B>` |
| `launch-fleet: review started <commit>, thread <id>` | `launch-fleet: review started <commit>` |
| `launch-fleet: re-check sent <commit>, thread <id>` | `launch-fleet: re-check sent <commit>` |
| `launch-fleet: review told again <commit>, thread <id>` | `launch-fleet: review told again <commit>` |
| `launch-fleet: review failed <commit>, thread <id>: <why>` | `launch-fleet: review given up <commit>: <why>` |
| `launch-fleet: nightly telling <run> attempt <attempt>, thread <id>` | `launch-fleet: nightly telling <run> attempt <attempt>` |

`review failed <commit>: <why>` still means no reviewer started; `review given up` means a quiet reviewer was given up on and archived, and it is never told again.

**Finding a thread from public facts.** A record says what happened to which ticket, pull request, commit and branch. The fleet finds the thread from those:

- **From private state first:** the start record kept for each agent started ([fleet tick v1](fleet-tick.v1.md#threads)), or a record-to-thread map in `private/orchestration/`. It is keyed by what the public record names: the ticket, or the pull request and commit. A re-check sent to an existing reviewer adds the key for its new commit to that same reviewer's thread. A give-up retires every key of that reviewer, at every commit.
- **Then from CloudRoom, by title,** for a thread whose starter titled it: the builder of ticket `#<N>` is a thread whose title starts exactly `#<N>: ` and, when the record names a branch, whose branch is that branch (a helper's `#<N> helper …` never matches); the reviewer of pull request `#<P>` is a thread titled `Review #<P> at <short start commit>`, where the start commit is the one its `review started <commit>` record names, and the short commit is a prefix of it. launch-fleet titles its threads so.
- **A reviewer's lineage.** A reviewer keeps its thread across re-checks, so a record for a later commit leads back to the reviewer started for an earlier one. On pull request `#<P>`, order the fleet's records by when each comment was created (an edit keeps its comment's place). Each `review started <A>` record opens a **reviewer span**, which runs until the next `review started` record on `#<P>`. Every `re-check sent <C>`, `review told again <C>` and `review given up <C>` record in a span belongs to that span's reviewer, whatever its commit `<C>`: the reviewer is the one found by its start commit `<A>`, by private state or by title.
  - **A give-up closes the whole span.** If any record in a span is `review given up <C>`, at `<A>` or at any later commit, that reviewer is given up. The quiet-reviewer flow writes a give-up by editing the claim it names in place, so a later `review told again <C>` in the same span can remain; it is still the given-up reviewer's, and it is never acted on. No record in a closed span resolves to its reviewer, so that reviewer is never told again. Work still due for the pull request needs a fresh `review started` (a new span), or else a `look`.
  - **No span:** a `re-check sent`, `review told again` or `review given up` record with no `review started` before it on `#<P>`, or a span whose start commit can't be read, gives a `look`.
- **Exactly one match** is the thread. **None,** or a source that can't be read, means the thread is gone or out of reach for that record. **Two or more, or private state and CloudRoom disagreeing:** a `launch-fleet: look: <reason>` record, never a guess. The reason names the ticket or pull request, never a thread.

The same rule holds for every public record, not just the fleet's: no issue, pull request, comment, commit message or file on the public repository carries a thread id. Other records name roles and comment ids instead: `wayfind: claimed` (the claim is that comment) and `wayfind: released <claim comment id>`; a builder's helper log names each helper by role.

```good
launch-fleet: start checked, branch room/4001-synthetic-ticket-ab12
launch-fleet: review started 0123456789abcdef0123456789abcdef01234567
launch-fleet: look: two threads match the builder of #4001
launch-fleet: review given up 0123456789abcdef0123456789abcdef01234567: no verdict 30 minutes after it was told again
launch-fleet: nightly telling 12345678 attempt 1
```

Bad: a thread id in a public record (synthetic here, and still refused).

```bad
launch-fleet: started, thread thr_synbuilder1
```

Bad: today's give-up record, which keeps the thread and the old word.

```bad
launch-fleet: review failed 0123456789abcdef0123456789abcdef01234567, thread thr_synreviewer1: no verdict
```

Bad: a `look` that names the threads it found.

```bad
launch-fleet: look: thr_synbuilder1 and thr_synbuilder2 both match #4001
```

## The privacy check

One tool, run by CI on the public repository, by the pre-push hook, and by the importer before it stages anything. On the private repository it runs only against a staged public tree. It is given a tree, a commit range and a pull request's title and body, and it refuses each of the following, one line per refusal, naming the rule, the place and the line, never echoing a matched secret beyond what the reader needs to find it. Anything it can't read is a refusal too.

### Text rules

Applied to every text file in the tree, every commit message in the range, and the pull request's title and body.

**T1, thread ids:** any token matching `thr_` followed by a letter or digit, then letters, digits, `_` or `-`, at a word start. Allowed only in the synthetic forms `thr_syn…` and `thr_web…`, which only tests and their fixtures use.

```good
The fixture's thread is thr_synreviewer1.
```

```bad
Started the builder, thread thr_planted0001.
```

**T2, quotes in the private record form:** a decider's exact words, written the way the project records them today. Any of:

- a bold lead naming a decider and ending `:**`, then optional spaces, then a double quote mark (`"`, `“` or `”`, with or without a backslash before it);
- a decider's name, then on the same line text with no double quote mark, a colon, optional spaces and a double quote mark (as in the second `bad` line below);
- a blockquote line (`>`) directly after a line that names a decider and ends with `:` (a grill's reply form).

The decider list is `Jake`. A name inside quotes (a heading such as `"Open for Robin"`) or a quote with no decider before it is not this form.

```good
Robin approved the plan graph on 2030-01-02 ([private record](https://github.com/jparker2006/ClosedWiz/issues/9001#issuecomment-9000000002)).
```

```bad
**Approved on its own by Robin, 2030-01-03:** "approve #4001"
Robin, 2030-01-04, in the orchestrator's thread: "make the codex ones fast"
```

**T3, real identifiers:** any token of these shapes, unless it is one of the allowed forms. The allowed forms are an allowlist (a guard fails closed): a token that merely contains a word such as `example` is not allowed for that.

| Shape | Allowed forms |
| --- | --- |
| CloudRoom ids: `proj_`, `prj_`, `mch_`, `usr_`, `acct_` or `auto_` followed by letters or digits; `cr_` followed by a UUID's first two groups | `<prefix>_syn…`, `<prefix>_web…` |
| Home folders: `/Users/<name>`, `/home/<name>` | `<name>` is `runner` (GitHub's runner), `cache`, `token`, `secret` or `someone`, or starts with `synthetic` or `example` |
| Email addresses | the domain is `example.com`, `example.org`, `example.net` or `example.invalid`, or ends in `.example`; `…@users.noreply.github.com`, `noreply@github.com`, `git@github.com`, `user@github.com`, `pass@github.com` |
| Named literals: machine and account names, which can't be written here without publishing them | none |

The named literals live in one private file, `private/evidence/open-development/privacy-check/literals.txt`, one per line. The importer refuses to run without it. The pre-push hook uses an explicitly configured literals path; it never guesses a private sibling directory. CI on the public repository has no access to it and runs every other rule; the check always says whether the list was used.

```good
The fake room-cli runs as /home/runner with project prj_synfleet1.
```

```bad
Copied from /home/plantedname/openwiz, written by robin@mail.invalid in project prj_planted42.
```

### Tree rules

**F1, private files by class:** any path under `private/`, or under `docs/grills/` other than `docs/grills/README.md`. A path, not its content, decides; a file there is refused even if empty.

```good
docs/grills/README.md
contracts/open-development.v1.md
```

```bad
private/machines.md
docs/grills/2030-01-02-synthetic.md
```

**F2, workflow jobs that can select a self-hosted runner.** In every `.github/workflows/*.yml` and `*.yaml`, each job's `runs-on` must be one of:

- a GitHub-hosted label from this list, written as a string or as a one-item list: `ubuntu-latest`, `ubuntu-24.04`, `ubuntu-slim`, `macos-15`, `macos-15-intel`;
- `${{ matrix.<key> }}`, when every value `<key>` takes in that job's matrix is a literal on the list (no expression in the matrix);
- `${{ vars.<NAME> || '<label>' }}`, when `<NAME>` is `CI_RUNS_ON` or `CI_RUST_RUNS_ON` and `<label>` is on the list. This legacy exception requires these runner variables to stay unset on the public repository.
- The following repository-guarded expression, with exactly one of the three private routes below in `<private-route>`. The fork arm is first and both hosted arms are the literal `ubuntu-24.04`. Only the permanent private repository can consult the private route; on every public copy, the result is hosted regardless of variable values. Parentheses and guard order are required. This proves the carried workflow bytes directly; the importer never rewrites them.

```text
${{ github.event_name == 'pull_request' && github.event.pull_request.head.repo.full_name != github.repository && 'ubuntu-24.04' || github.repository == 'jparker2006/ClosedWiz' && (<private-route> || 'namespace-profile-closedwiz-rust') || 'ubuntu-24.04' }}
```

The three private routes are exactly `vars.CI_RUST_RUNS_ON`, `vars.CI_WEB_RUNS_ON`, and `vars.CI_SMALL_RUNS_ON || vars.CI_WEB_RUNS_ON`. The private fallback is never an accepted standalone public runner label. F2 accepts no other composite runner expression.

**Variables:** `CI_RUNS_ON`, `CI_RUST_RUNS_ON`, `CI_WEB_RUNS_ON` and `CI_SMALL_RUNS_ON` stay unset in the repository and organization variables available to the public repository; the repository guard keeps public jobs hosted even if one is set.

Anything else is refused: the `self-hosted` label, any label not on the list, a `group:` or `labels:` mapping, any other expression, and a job that calls a reusable workflow from another repository (its runner can't be checked here; a local one is checked as its own file). Adding a label to the list is a change to this contract.

```good
    runs-on: ${{ vars.CI_RUNS_ON || 'ubuntu-24.04' }}
```

```bad
    runs-on: [self-hosted, Linux, X64]
    runs-on: ${{ vars.CI_RUST_RUNS_ON || 'planted-runner-profile' }}
```

### Commit rules

Applied to the range the check is given (a pull request's base to head, a push's remote to local, or the importer's one new commit).

**C1, ClosedWiz history as an ancestor:** the public repository has exactly one root commit, `f099f9e0cbd3fc2a8ce3edf981235c953ee2dec7`, and its `main` only moves forward from `5d069b025c6eacb4123ca8241ba21345f1eae9dd`. A head is refused unless every root commit reachable from it is that one root (`git rev-list --max-parents=0 <head>` prints exactly it) and `5d069b02…` is its ancestor. This refuses ClosedWiz history however it arrives, through a merge commit included, without naming a single ClosedWiz commit. Read with replace objects off (`GIT_NO_REPLACE_OBJECTS=1`) and no grafts; a shallow clone can't prove it and is refused.

```good
git rev-list --max-parents=0 HEAD   # prints only f099f9e0cbd3fc2a8ce3edf981235c953ee2dec7
```

```bad
git rev-list --max-parents=0 HEAD   # prints f099f9e0… and a second root, from a merged private branch
```

**C2, commit messages:** each message in the range, checked with T1 to T3.

```good
#4001: thread-free fleet records
```

```bad
#4001: fix from the review, thread thr_planted0001
```

**C3, author and committer addresses:** each commit in the range must have author and committer email addresses of GitHub's private forms: `<id>+<login>@users.noreply.github.com`, `<login>@users.noreply.github.com`, or `noreply@github.com` (GitHub's own merge commits). Any other address is a real identifier in every public commit.

```good
Author: Robin <1234567+robin-synthetic@users.noreply.github.com>
```

```bad
Author: Robin <robin@mail.invalid>
```

### What it does not refuse

The name ClosedWiz; the pointer; the cross-links; mentions of `private/` or a grill as words; branch names; GitHub-hosted runner labels; anything already in the public repository's history before `5d069b02…`. It reads no image, so text inside a binary file is a reviewer's to check. Issue comments are not its input: their writers are tested to write only these forms.

## What the importer carries

The importer builds the public tree from one ClosedWiz commit and makes **one ordinary commit** on top of the public repository's `main`, in a local clone, dry-run by default.

**May carry:** the content of public files at that commit that are on its reviewed list (`tools/open-import/paths.json`), and the public repository's own files that list keeps. The new commit's only parent is the public repository's `main`; its author and committer pass C3.

**May not carry:** any file in a private class; any path not on the reviewed list; any ClosedWiz commit, branch, tag, note or other ref, or any ClosedWiz object fetched into the public clone; anything the privacy check refuses (it runs on the staged tree and the new commit before anything is staged as final). Work in flight moves as a patch, never as commits. It never pushes: that one commit goes to a new branch and one pull request, which merges when CI, the privacy check included, is green.

A staged tree's paths, from a ClosedWiz commit:

```good
contracts/open-development.v1.md
crates/core/src/lib.rs
docs/grills/README.md
```

Bad: a private file staged.

```bad
private/evidence/synthetic/run.log
```

## Consistent history

- **ClosedWiz is never deleted, rewritten, force-pushed or made public.** It keeps every commit, issue and pull request number as the private record.
- **OpenWiz carries on from its own history:** its `main` only moves forward from `5d069b025c6eacb4123ca8241ba21345f1eae9dd`, by ordinary commits, never by a ClosedWiz commit, and is never force-pushed.
- **Any number leads to the other:** each moved issue and pull request ends with `was [ClosedWiz #N](<its URL>)`, its last line, and each original has one comment, `moved to [OpenWiz #M](<its URL>)`. Both are Markdown links, so GitHub never links a bare `#N` to the wrong repository.

## Gaps

- T2 finds exact words in the forms the project writes them. Words quoted without a decider's name before them, or unquoted ones, are found only by review and by the writers' own tests.
- The named literals are not checked in CI on the public repository.
- Text inside images is not read.
