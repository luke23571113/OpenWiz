# gemini: Gemini CLI on the local driver

Login: Gemini CLI's own login: the cached Google sign-in under ~/.gemini, or the GEMINI_API_KEY the user set; the driver never reads or passes it

Effort: none

Live check: #2513

The `gemini` harness row, under the [harness-row contract](../../harness-row.md). Every fact below is from Gemini CLI **v0.70.0**, tag commit [`8468962e`](https://github.com/google-gemini/gemini-cli/tree/8468962efadfbcdfd988a8fd04af4110a68c886e), its latest release when this row was written.

**Who can use it.** Gemini CLI is now for enterprise users only: Gemini Code Assist Standard or Enterprise, or Code Assist for GitHub, on Google Cloud, plus legacy paid API or Vertex keys. Free individual access and Google AI Pro or Ultra moved to Antigravity CLI on June 18, 2026 ([README at v0.70.0](https://github.com/google-gemini/gemini-cli/blob/v0.70.0/README.md)).

## Commands

The driver chooses the session id, a UUID (`{"chosen": "uuid"}`), and runs every turn in the run's clone:

| Turn | Command |
| --- | --- |
| Start | `gemini -p <prompt> -o stream-json --session-id <uuid> -m <model> <mode>` |
| Wake | `gemini -p <prompt> -o stream-json --resume <uuid> -m <model> <mode>` |
| Stop | none of its own: the driver's stop ends the whole process tree |

- `-p` (`--prompt`) runs headless; `-o stream-json` prints JSONL events ([headless](https://github.com/google-gemini/gemini-cli/blob/v0.70.0/docs/cli/headless.md)).
- `--session-id` "Start[s] a new session with a manually provided UUID"; it refuses an id that already exists ([`config.ts`](https://github.com/google-gemini/gemini-cli/blob/v0.70.0/packages/cli/src/config/config.ts), [`gemini.tsx` `resolveSessionId`](https://github.com/google-gemini/gemini-cli/blob/v0.70.0/packages/cli/src/gemini.tsx)). `--resume`, `--session-id` and `--session-file` are mutually exclusive, so start and wake each take one.
- Sessions are saved per project folder ([sessions](https://github.com/google-gemini/gemini-cli/blob/v0.70.0/docs/cli/session-management.md)), so a wake must run in the same clone, which the driver does.
- `daemon: none`: the CLI starts no background service of its own. MCP servers it starts are children of the turn, inside the tree stop ends.

## Modes

| Mode | Arguments | What it allows |
| --- | --- | --- |
| `yolo` | `--approval-mode yolo --skip-trust` | Every tool runs without asking. `--skip-trust` trusts the run's clone for this session, because with folder trust on a headless run in an untrusted folder exits with `FatalUntrustedWorkspaceError` ([trusted folders](https://github.com/google-gemini/gemini-cli/blob/v0.70.0/docs/cli/trusted-folders.md)) |

Only `yolo` is offered. Headless, any tool that would ask is denied ([policy engine](https://github.com/google-gemini/gemini-cli/blob/v0.70.0/docs/reference/policy-engine.md)), so `default`, which asks before tools, and Gemini's auto-edit mode, which asks before shell commands, can't post a builder's status note unless the user's own policy allows them. `plan` is read-only. The auto-edit mode's value is also left out because OpenWiz's privacy check reads its `auto_`-prefixed name as a private identifier.

## The census check, resolved

**Is `--resume <uuid>` accepted together with `-p`? Yes.** At v0.70.0:

1. The `--resume` option takes a full session UUID, the string `latest` or an index; `findSession` matches the UUID first ([`config.ts`](https://github.com/google-gemini/gemini-cli/blob/v0.70.0/packages/cli/src/config/config.ts), [`sessionUtils.ts`](https://github.com/google-gemini/gemini-cli/blob/v0.70.0/packages/cli/src/utils/sessionUtils.ts)). The [sessions doc](https://github.com/google-gemini/gemini-cli/blob/v0.70.0/docs/cli/session-management.md) shows `gemini --resume <uuid>`.
2. The argument check refuses `-p` only with a positional prompt or `-i`, and `--resume` only with `--session-id` or `--session-file` ([`config.ts`](https://github.com/google-gemini/gemini-cli/blob/v0.70.0/packages/cli/src/config/config.ts)), so `-p` with `--resume` passes.
3. In `main`, the resumed session from `resolveSessionId` goes into `runNonInteractive` as `resumedSessionData`, so the headless turn continues that session ([`gemini.tsx`](https://github.com/google-gemini/gemini-cli/blob/v0.70.0/packages/cli/src/gemini.tsx)). The [CLI reference](https://github.com/google-gemini/gemini-cli/blob/v0.70.0/docs/cli/cli-reference.md) documents `gemini -r "<session-id>" "query"` with a positional prompt.

The census start line holds as given. The census wake line puts `--resume` first, which is the same command: yargs takes options in any order.

## Effort

**Effort: none. This host can't set effort.** At v0.70.0 Gemini CLI has no effort or thinking flag and no environment setting for it. Thinking is set only in `settings.json` under `modelConfigs`, as `thinkingConfig` (`thinkingBudget` for Gemini 2.5 models, `thinkingLevel` for Gemini 3) ([generation settings](https://github.com/google-gemini/gemini-cli/blob/v0.70.0/docs/cli/generation-settings.md), [`defaultModelConfigs.ts`](https://github.com/google-gemini/gemini-cli/blob/v0.70.0/packages/core/src/config/defaultModelConfigs.ts), the options in [`config.ts`](https://github.com/google-gemini/gemini-cli/blob/v0.70.0/packages/cli/src/config/config.ts)). A row passes only fixed arguments and settings, and editing the user's settings file is not one. A start with an effort is refused, and the runner checks that refusal.

## Signed out

When there is no sign-in, a headless turn prints `Please set an Auth method in your ~/.gemini/settings.json or specify one of the following environment variables before running: ...` and exits 41 ([`validateNonInterActiveAuth.ts`](https://github.com/google-gemini/gemini-cli/blob/v0.70.0/packages/cli/src/validateNonInterActiveAuth.ts)). The row's `signed_out` matches it, and `start` then names `gemini` as the sign-in command: run it, then choose Sign in with Google or set your own `GEMINI_API_KEY` ([README](https://github.com/google-gemini/gemini-cli/blob/v0.70.0/README.md)).

## The fake

`fake` is the only CLI here. It allows only the command lines in its `HELP` text, after the v0.70.0 options above, and exits 2 on anything else. `test_row.py` checks the refusals. No real `gemini` ran for this row: the runner puts refusing stubs for 31 agent CLIs on `PATH`, with only this fake ahead of them. The live run is #2513.
