# First-hour live kit: install instruction to the first verified merge

The bounded extension of the [0.0.13 live kit](live-kit.md) that #2207 runs for spec #2194's first hour (PR1, and PR2, PR4, PR5 and PR7's live parts). **Preparing it performs nothing live.** This file grants no live, account, feedback-send, spending, cut-over, ship or publishing authority by being merged. The 0.0.13 kit, its steps and its ten-minute target stay as they are; this kit adds its own steps and reuses that kit's timer only through its own record.

The kit's offline dry run, eligibility check and result validator are `tests/first-hour/kit.py` beside this file:

```sh
python3 -I tools/install/tests/first-hour/kit.py dry-run [<eligibility.json>]
python3 -I tools/install/tests/first-hour/kit.py eligibility <eligibility.json>
python3 -I tools/install/tests/first-hour/kit.py validate <result.json> --binding <binding.json> --eligibility <eligibility.json>
```

A passing dry run or validation proves the kit's shape and its rules, never a live result, an elapsed time or a usable login. The installed recording journey (`tests/first-hour/test_journey.py`) is synthetic proof of the same path; it is never a live observation.

## Eligibility

Final execution is refused until `kit.py eligibility` passes on a record of the current state. It refuses, naming each reason:

- **The graph:** the approved #2194 revision and its fingerprint, with the private-record pointer of its approval. A missing or unreadable approval refuses.
- **Every gate's producers:** each of the three first-hour gates (`cloudroom_setup` #2201, `paid_offer` #2202, `feedback` #2203) needs its exact producer tickets in the approved graph and each producer's verified merge (pull request, merge commit and approved head read back as merged), never a closed issue. Today `paid_offer` has #2293 and `feedback` has #2292; `cloudroom_setup` has no producer in the graph, so **this kit is ineligible** until its producer ticket is added under plan-graph's change control and merged. The kit never stands in for it.
- **Authority:** a private-record pointer for each scope the run uses: `live` (the run on the installed candidate), `account` (the owner-authorized repository, App and test-owned threads), `feedback_send` (one synthetic issue on the agreed destination) and `spending` (Cloud Credits within the bound). A missing scope refuses; standing authority must be checked against these exact steps and counts.
- **The candidate:** one checked candidate, bound below, with its green fixture integration and this kit's passing dry run read back first.

The record is one `openwiz.first-hour-kit-eligibility.v1` JSON object: `graph` (`revision`, `fingerprint`, `approval` pointer), `gates` (for each of the three gates, its producers, each `ticket`, `pr`, `merge_commit`, `approved_head` and `merged_at_head`) and `authority` (a pointer for each of `live`, `account`, `feedback_send` and `spending`).

## Binding

One `openwiz.first-hour-kit-binding.v1` JSON object, written before step H1 and never edited after:

- `candidate`: `version`, `source`, `target`, `manifest_sha256`, exactly first-hour.v1's candidate;
- `host`: `target` (one declared target, equal to the candidate's) and `fresh_account: true` (a disposable user account or machine with no prior OpenWiz state);
- `scope`: `repository` (`owner/name`, the owner-authorized repository, chosen by the owner, never the installer's demo) and `app_repositories` (exactly that repository);
- `counts`: the most of each effect the run may make: `builders`, `reviewers`, `merges`, `feedback_issues`, `shares` (each a nonnegative integer; `feedback_issues` and `shares` at most 1);
- `recorded`: `waits` and `help`, how many of each the run's log holds, so the result keeps every one;
- `graph`: `revision` and `fingerprint` of the approved #2194 graph.

The validator refuses a malformed binding, and a result for any other candidate, target or repository.

## Steps

Each step is bounded. `read` steps change nothing; `write` steps act only on the bound repository and test-owned resources; `spend` steps may use Cloud Credits within the bound. Stop at the first step whose bound would be exceeded, or whose producer is missing, and record a gap. A step that needs a gate is ineligible until that gate's producers are in the approved graph with verified merges (#2201's `cloudroom_setup` has none yet; #2202's `paid_offer` names #2293; #2203's `feedback` names #2292); the kit never implements it.

| Step | Name | Effect | Needs | Bound |
| --- | --- | --- | --- | --- |
| H1 | discovery | read | none | Read-only discovery of the host, the candidate's release, CloudRoom and the bound repository; record what exists |
| H2 | instruction | read | none | Open the public install instruction once on the fresh account; the first-hour clock starts here |
| H3 | install | write | none | Install the bound candidate once through the public instruction; no prior OpenWiz state |
| H4 | cloudroom | write | cloudroom_setup | CloudRoom's bundled install or reuse and its one sign-in screen; ineligible until its producer merges |
| H5 | connections | write | none | Connect the App to the bound repository only; record each component's setup.v1 evidence; a listed harness is not a usable login |
| H6 | refused-connection | read | none | One refused connection (a repository outside the App's selection), its message and that nothing took effect |
| H7 | idea | write | none | One genuinely fresh small idea on the bound repository: no prepared plan, no private operator steps |
| H8 | confirmations | write | none | The spec confirmation and the exact-plan approval, each saved separately and read back |
| H9 | fleet | spend | none | The approved frontier only, at most `counts.builders` builders, with the harness, model, effort and location the owner chose |
| H10 | interruption | write | none | One interruption and resumption on the run's own work (a reload, a lost reply or a restart); compare drafts, identities, branch and commit content and pending records before and after |
| H11 | review-and-ci | spend | none | One independent other-family review and the required CI on the first pull request's exact head; at most `counts.reviewers` reviewers |
| H12 | merge | write | none | The first merge through the standing merge rules, read back from GitHub at the approved head; the first-hour clock stops here; at most `counts.merges` |
| H13 | free-only | read | paid_offer | The installed copy says OpenWiz is free now and paid plans come later, with no paid offer or payment code |
| H14 | feedback-and-share | write | feedback | One explicitly approved synthetic feedback issue through the user's own login after its exact preview, and one share of public content only; at most `counts.feedback_issues` and `counts.shares` |
| H15 | cleanup | write | none | Stop only the kit's own threads and disposable resources; keep the evidence |

## Timing

Two independent targets, recorded separately; neither is derived from the other, and a second attempt never replaces the first:

- **The first hour (PR1):** first-hour.v1's clock, from H2 (the public instruction opened) to H12 (GitHub's merge time of the first verified merge, read back). Everything between counts; waits and help are recorded, never subtracted. Over `3600000` ms is a missed hour.
- **The first running fleet (#1110's target):** [live-kit.md](live-kit.md)'s definition, unchanged, recorded as the result's `ten_minute_fleet` (`owner: 1110`): `met`, `missed` or `unmeasured`. It never decides the hour.

## Result

One first-hour.v1 `result` document (`proof_class: live`, no synthetic assumptions, a private-record pointer to the raw evidence), checked against the binding:

- #2200's checks give its codes: any problem refuses it; any failure makes it a `fail`, reported as one.
- A `fixture` or `recording` document is refused as a live observation: it is synthetic proof, labelled as such.
- Its candidate, target and repository match the binding; its operations stay within `counts` (each effect at most once); its `waits` and `help` hold exactly the counts the binding recorded; and each gate's state and producers match the eligibility record's verified producers.
- Values are sanitized technical text only: no account names, thread or project ids, tokens, emails, machine paths or transcripts. The validator refuses anything that looks like one. Raw evidence stays private, reached by the pointer.

## The 0.0.16 extension: one install instruction to the first merged implementation (#637)

The bounded extension that T8 #638 asks Jake to authorize and T9 #639 runs for spec #625 (P1 to P7's live parts). **Preparing it performs nothing live.** Merging this section, the spec's graph approval or any standing approval grants no live, machine, account, App, companion, secret, agent, merge, spending, cleanup or publication authority: each scope below needs its own exact private-record pointer, recorded for these steps and counts. Everything above stays as it is: the first-hour result, its one-hour limit (`3600000`) and the ten-minute measure keep their own meaning and verdicts, and this extension never relabels them a 30-minute proof.

The offline dry run, eligibility check and receipt validator are `tests/first-hour/first_merge_kit.py` beside this file:

```sh
python3 -I tools/install/tests/first-hour/first_merge_kit.py dry-run [<eligibility.json> [<binding.json>]]
python3 -I tools/install/tests/first-hour/first_merge_kit.py eligibility <eligibility.json> <binding.json>
python3 -I tools/install/tests/first-hour/first_merge_kit.py validate <receipt.json> --result <result.json> --fleet <fleet.json> --binding <binding.json> --eligibility <eligibility.json>
```

Each exits 0 only when nothing refuses (5 refused, 2 usage). A dry run or a valid synthetic receipt proves the kit's shape and rules only, never elapsed time, a real account, a usable login, an upstream capability or a live result. The installed recording journey (`tests/first-hour/test_first_merge.py`) produces a `recording` receipt on the same path; it is never a live observation.

### What execution needs (sign-off material for #638)

Final execution is refused until `first_merge_kit.py eligibility` passes on one `openwiz.first-merge-kit-eligibility.v1` record and the run's binding. It names each refusal:

- **The graph:** spec #625's approved revision, its fingerprint and the private-record pointer of that approval.
- **Producer proof:** each implementation ticket of the spec, #632, #633, #606, #634, #635, #636 and #637, with its pull request, merge commit and approved head read back as merged at that head (`merged_at_head: true`). A closed issue is not a merge. The kit never stands in for a missing producer.
- **Authority:** one private-record pointer for each scope the run uses, checked against these exact steps and counts:

| Scope | What it permits |
| --- | --- |
| `live` | Running the bound installed candidate from the public install instruction |
| `machine` | The one fresh disposable supported machine or clean machine account, and its initial-state record |
| `accounts` | The test owner's GitHub, CloudRoom and harness sign-ins on that machine, each an owner action |
| `repository` | The fresh throwaway repository, created and controlled by the test owner, as the only selected repository |
| `app` | Registering and installing the test owner's own private App on that repository only (Create, then Install) |
| `companion` | The separate public-code check's one private companion repository and its link |
| `secret` | The bound secret route: the protected paste (GitHub's replacement key, its owner download, encoding, paste and deletion) or the agent-side save |
| `agents` | One fleet thread, its per-spec check loop, and at most the bound builders and reviewers |
| `merges` | At most the bound merges, through the standing merge rules |
| `spending` | Cloud Credits up to the bound credit limit |
| `cleanup` | Stopping, archiving or deleting only the bound test-owned resources |

- **The no-paste route:** a binding with `secret_route: agent_save` also needs `upstream.state: observed_supported` with a private-record pointer to the observed real save and later delivery of the CloudRoom agent-side save-secret contribution. Until that exists the route is refused, and its live status stays Unverified.

### Binding

One `openwiz.first-merge-kit-binding.v1` JSON object, written before step F1 and never edited after:

- `candidate`: `version`, `source`, `target`, `manifest_sha256`, exactly the first-hour result's and the receipt's candidate;
- `host`: `target` (the candidate's), `fresh_machine: true`, `seeded_openwiz_state: false`;
- `scope`: `repository` (`owner/name`, the fresh throwaway repository), `app_repositories` (exactly that repository) and `companion_repository` (`null`, or for the separate public-code check the one private companion `<owner>/<name>-brain`);
- `route`: `identity` (`app` or `personal_login`), `app_registration` (`created`, `reused` or `skipped`) and `secret_route` (`agent_save`, `protected_paste` or `not_used`), as the receipt must report them; the skip-App continuation is `personal_login`, `skipped`, `not_used`;
- `counts`: `fleet_threads` (exactly `1`), `loops` (exactly `1`), `builders`, `reviewers`, `merges`, `app_registrations` (at most `1`) and `companions` (at most `1`);
- `credit_bound`: the Cloud Credits the run may spend, a positive integer;
- `recorded`: `actions`, `waits` and `help`, how many of each the run's private raw log holds, so the receipt keeps every one;
- `cleanup`: each test-owned resource to stop or remove, each `{"resource", "action"}` with `resource` one of `test_threads`, `test_loops`, `throwaway_repository`, `companion_repository`, `test_app`, `test_secret`, `machine_account` and `action` one of `archive`, `delete`, `revoke`, `stop`; `test_threads` and `test_loops` are always stopped, and raw evidence is never a cleanup target;
- `graph`: spec #625's `revision` and `fingerprint`.

### Steps

Each step is bounded and needs every scope it names. `read` steps change nothing; `write` steps act only on the bound repository and test-owned resources; `spend` steps may use Cloud Credits within the bound. Stop at the first step whose bound would be exceeded or whose authority is missing, and record a gap. The primary timed run (F1 to F13) has no planted fault; F14 to F16 are separate, bounded checks after it, never inside its clock.

| Step | Name | Effect | Authority | Bound |
| --- | --- | --- | --- | --- |
| F1 | discovery | read | live machine | Record the machine's initial tools, account sessions and provider logins, and that no OpenWiz state, App, brain, plan or private instruction is seeded |
| F2 | instruction | read | live | Open the public install instruction once; the clock starts here |
| F3 | install | write | live machine | Install the bound candidate through the instruction; nothing compiled |
| F4 | cloudroom | write | accounts | CloudRoom's bundled install or reuse and its sign-in; every screen is an owner action |
| F5 | github-sign-in | write | accounts | GitHub's own browser sign-in through `gh`; no pasted token; every screen is an owner action |
| F6 | app | write | app repository | The owner's own private App: Create, then Install on the bound repository only; at most `counts.app_registrations` |
| F7 | key | write | secret | The bound secret route only; every key, download, encoding, paste and cleanup step is an owner action |
| F8 | init | write | repository | `openwiz init` on the bound repository, its visible brain pull request and the owner's merge of it |
| F9 | idea | write | repository | One genuinely fresh small idea; its text is kept in the receipt |
| F10 | confirmations | write | repository | The spec confirmation and the exact-plan approval, each saved separately and read back |
| F11 | fleet | spend | agents spending | Launch-fleet's start: exactly one fleet thread and its per-spec check loop, which start only the approved frontier; no engine activation and no `fleet tick` start |
| F12 | review-and-ci | spend | agents spending | One independent other-family review and the required CI on the first implementation pull request's exact head |
| F13 | merge | write | merges | The first implementation merge through the standing rules, read back with its commit; the clock stops at its merge time |
| F14 | public-companion | write | repository companion | Separate bounded check: init on test-owned public code makes and links one private companion; read back both visibilities and the link |
| F15 | skip-app | write | accounts repository | Separate bounded check: the explicit App skip continues under the verified personal login; read back the acting identity |
| F16 | recovery | write | repository | Separate bounded check: the existing fault kit's refusal and interruption cases, never inserted into F1 to F13 |
| F17 | cleanup | write | cleanup | Stop and remove only the bound test-owned resources; keep the raw evidence privately |

### Timing and actions

The receipt's clock runs from F2 to F13's GitHub merge time, strictly below `1800000` ms: 1,799,999 ms can qualify; 1,800,000 ms fails. Nothing is paused or subtracted: downloads, sign-ins, setup, decisions, queue, review, CI and every wait and help count. The first-hour result's one-hour limit and the ten-minute-to-running-fleet measure are recorded beside it and decided separately; neither verdict decides another.

Every owner interaction is one action-log entry: each sign-in screen, navigation, App Create and Install, key generation, download, encoding, paste and download deletion, typed choice and its submission, confirmation, consent, approval and spending approval, and the owner's merge of the brain pull request. An agent's stand-in for one logs `agent_for_owner` and counts exactly like it; several taps are never one entry. More than five fails.

### Fleet start

One `openwiz.first-merge-kit-fleet.v1` record, read back from CloudRoom and the spec's own fleet record: `route` (`launch_fleet`; `engine` or `fleet_tick` is refused), `fleet_threads` (exactly `1`), `loop` (`{"spec", "every_minutes"}`: the fleet thread's own per-spec check, every `10` minutes; `null` is refused), `engine_activations` and `tick_starts` (each `0`), and `builders` and `reviewers` started.

### Receipt validation

`validate` refuses the receipt (exit 5) when any of these holds, one plain line each: setup-onboard.v1's or first-hour.v1's checks refuse a document; the receipt is not bound to the SHA-256 of that exact first-hour result; a `live` receipt binds a `fixture` or `recording` result or fleet record (fixtures labelled live), or a non-`live` receipt is offered as a live observation; the candidate, target, repository, identity, App registration or secret route differ from the binding; the first-hour result shows no verified merge, or one at another pull request, head or time; the waits and help differ from the first-hour result's or the binding's recorded counts, or the action log from the binding's count (omitted entries); a required owner step has no entry of its own (the App's Create and Install, each of the protected-paste route's key steps and its paste, the spec confirmation, the plan approval and the launch's spending approval); the fleet start shows an engine activation, a `fleet tick` start, other than one fleet thread or no per-spec loop, or any count exceeds the binding; or anything looks like an account, id, token, email or path. Otherwise its outcome is setup-onboard.v1's verdict: `pass` only for a live receipt with no failure and nothing unproven.
