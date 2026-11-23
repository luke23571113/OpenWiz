# copilot (GitHub Copilot CLI)

Login: copilot's own login, saved by `copilot login` in the system credential store, or in plain text under ~/.copilot/ (or $COPILOT_HOME) when there is no store

Effort: `--reasoning-effort <low|medium|high|xhigh|max>` at start and at every wake

Live check: #2469

The `copilot` harness row on the local driver, under the [harness-row contract](../../harness-row.md). The driver never reads or passes this login: it lives only in copilot's own store, and the user signs in with `copilot login` on their own machine. Signed out, `copilot -p` prints `Error: No authentication information found.` and exits 1, so `start` fails with `the harness is not signed in` and names `copilot login`.

## Commands

The driver picks the session id (`{"chosen": "uuid"}`), saves it, and passes it at start and at every wake.

- **Start:** `copilot -p <prompt> --output-format json --session-id <uuid> --model <model> <mode> [--reasoning-effort <level>]`. A `--session-id` that matches no session and is a valid UUID creates a new session with that id.
- **Wake:** `copilot -p <prompt> --session-id <uuid> <mode> [--reasoning-effort <level>]`. The same `--session-id` resumes that session, which keeps its model.
- **Stop:** the driver's own stop, which ends the whole process tree.

## Modes

In a `-p` run copilot can't ask, so it denies any tool request that no allow rule approves. The owner approves one of these:

| Mode | Adds | What it allows |
| --- | --- | --- |
| `allow-all-tools` | `--allow-all-tools` | Every tool without asking; file access stays inside the clone and the system temp directory, and URLs keep their checks |
| `allow-all` | `--allow-all` | `--allow-all-tools --allow-all-paths --allow-all-urls` |

Deny rules, organization policy and `permissions.disableBypassPermissionsMode` still win over both.

## Effort (J318)

The row passes the user's effort as `--reasoning-effort <level>`, one of `low`, `medium`, `high`, `xhigh` or `max`, at start and at every wake (the flag is a top-level option, and resuming takes it too). Any other effort is refused before anything starts. Which levels a model offers depends on the model (`max` is for Anthropic models): copilot reports a level the selected model doesn't offer as a warning and leaves it unapplied, so it never ignores one silently, and the live check runs with a model that offers the level it uses.

## Background process

As a session shuts down, copilot v1.0.114 may start a detached `copilot --agent rem-agent -p … --yolo --silent` memory pass in the same folder, when its `COPILOT_SUBCONSCIOUS` experiment is on for the account. It leaves the turn's session and closes its output, so `stop` reaches it on Linux only (the local README's limit). The fake stands in for it with the library's hard-detached service, and this row claims only the platforms its live check runs on.

## The census check, resolved

The census needed nothing blocking (the driver picks the UUID), only the permission flags for `modes` and the effort setting. Resolved from GitHub Copilot CLI v1.0.114 (`@github/copilot` 1.0.114, build `780b7b25939`), read as files and never run:

- **Permission flags:** `--allow-all-tools` ("Allow all tools to run automatically without confirmation. Non-interactive mode cannot ask, so it denies tool requests that no allow rule … approves") and `--allow-all` / `--yolo` ("equal --allow-all-tools --allow-all-paths --allow-all-urls"), in v1.0.114's `copilot --help` and `copilot help permissions` text, and the [command reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference#command-line-options).
- **Effort:** `--effort=LEVEL`, `--reasoning-effort=LEVEL` ("Set the reasoning effort level (`low`, `medium`, `high`, `xhigh`, `max`)") in the [command reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference#command-line-options); added in 1.0.4, with `--effort` as its alias in 1.0.10; a level the model does not offer gets a warning, not silence: "The warning for an unsupported --reasoning-effort value is no longer lost when the session's model changes while the CLI is starting" (1.0.110), and "a level the selected model does not offer is reported and left unapplied" (1.0.88), all in the [changelog](https://github.com/github/copilot-cli/blob/main/changelog.md).
- **Session:** `--session-id ID` resumes a matching session, or "a new session is created only when the value is a valid UUID" ([command reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference#command-line-options); 1.0.51 in the [changelog](https://github.com/github/copilot-cli/blob/main/changelog.md)).
- **Output:** `--output-format json` gives JSONL, one record per line ([command reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference#command-line-options)).
- **Login:** "an authentication token is stored securely in the system credential store. If a credential store is not found, the token is stored in a plain text configuration file under `~/.copilot/` (or the directory specified by `COPILOT_HOME` if set)" ([command reference, `copilot login`](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference)).
- **Source:** [github/copilot-cli](https://github.com/github/copilot-cli), whose npm package is [`@github/copilot`](https://www.npmjs.com/package/@github/copilot/v/1.0.114).

`fake` accepts only the start and wake lines above, with those modes and levels, and exits 2 on anything else; `test_row.py` checks that.
