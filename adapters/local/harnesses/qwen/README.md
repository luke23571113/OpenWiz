# qwen (Qwen Code)

Login: qwen's own login: Qwen OAuth in ~/.qwen/oauth_creds.json, or an API key provider in ~/.qwen/settings.json or ~/.qwen/.env, set up with /auth in an interactive qwen

Effort: none

The `qwen` row runs [Qwen Code](https://github.com/QwenLM/qwen-code) on the local driver. Every source below is the `v0.28.4` tag (commit `e8424c88ddd463c56602063efde57c328b917cd4`), the newest release when this row was written. Live check: #2526.

## Where the login lives

The driver never reads or passes a login. `qwen` finds its own: a Qwen OAuth sign-in saved in `~/.qwen/oauth_creds.json` ([sharedTokenManager.ts](https://github.com/QwenLM/qwen-code/blob/v0.28.4/packages/core/src/qwen/sharedTokenManager.ts#L26), under `Storage.getGlobalQwenDir()`), or an API key provider in `~/.qwen/settings.json` or `~/.qwen/.env` ([auth.md](https://github.com/QwenLM/qwen-code/blob/v0.28.4/docs/users/configuration/auth.md)). To sign in, run `qwen` and use `/auth`: the `qwen auth` subcommands were removed and now only print a notice ([auth.ts](https://github.com/QwenLM/qwen-code/blob/v0.28.4/packages/cli/src/commands/auth.ts#L36-L54)). Signed out, a headless run prints `No auth type is selected...` and exits 1 ([validateNonInterActiveAuth.ts](https://github.com/QwenLM/qwen-code/blob/v0.28.4/packages/cli/src/validateNonInterActiveAuth.ts#L26-L29)); with stream-json output that line is the JSON `result` with `is_error: true`. The row's `signed_out` matches it, and `start` then says the harness is not signed in and names `qwen, then /auth`.

## The commands

The driver chooses the session id (`{"chosen": "uuid"}`): `qwen` takes a new session's id with `--session-id`, and refuses one that is not a UUID ([config.ts](https://github.com/QwenLM/qwen-code/blob/v0.28.4/packages/cli/src/config/config.ts#L821-L838)).

- Start: `qwen --output-format stream-json --session-id <uuid> --model <model> --approval-mode <mode> <prompt>`
- Wake: `qwen --output-format stream-json --resume <uuid> --model <model> --approval-mode <mode> <prompt>`
- Stop: the driver's own stop, which ends the whole process tree.

`--session-id` and `--resume` can't be used together ([config.ts](https://github.com/QwenLM/qwen-code/blob/v0.28.4/packages/cli/src/config/config.ts#L821-L823)), so wake passes only `--resume`, as [headless.md](https://github.com/QwenLM/qwen-code/blob/v0.28.4/docs/users/features/headless.md) shows (`qwen --resume <id> -p ...`). The prompt is the one positional argument, which runs one-shot ([config.ts](https://github.com/QwenLM/qwen-code/blob/v0.28.4/packages/cli/src/config/config.ts#L972-L981)); the row doesn't use `-p`, which `--help` marks deprecated ("Use the positional prompt instead", [top-level-options.ts](https://github.com/QwenLM/qwen-code/blob/v0.28.4/packages/cli/src/config/top-level-options.ts#L175-L176)). `--output-format stream-json` is one of `text`, `json` and `stream-json` ([top-level-options.ts](https://github.com/QwenLM/qwen-code/blob/v0.28.4/packages/cli/src/config/top-level-options.ts#L359-L364)).

## The modes

`--approval-mode` takes exactly `plan`, `default`, `auto-edit`, `auto` and `yolo` ([top-level-options.ts](https://github.com/QwenLM/qwen-code/blob/v0.28.4/packages/cli/src/config/top-level-options.ts#L28-L34), [approval-mode.md](https://github.com/QwenLM/qwen-code/blob/v0.28.4/docs/users/features/approval-mode.md)). Each is a mode here, adding `--approval-mode <mode>`. `--yolo` is not used: `qwen` refuses it with `--approval-mode` ([config.ts](https://github.com/QwenLM/qwen-code/blob/v0.28.4/packages/cli/src/config/config.ts#L802-L804)).

| Mode | Edits | Shell commands |
| --- | --- | --- |
| `yolo` | auto-approved | auto-approved, with no sandbox |
| `auto-edit` | auto-approved | need approval |
| `auto` | a model classifier decides | a model classifier decides |
| `default` | need approval | need approval |
| `plan` | read-only | not run |

## The census check, resolved

**A plain run never starts `qwen serve`.** `serve` runs only as its own subcommand, `qwen serve` (listed in [cli.ts](https://github.com/QwenLM/qwen-code/blob/v0.28.4/packages/cli/src/cli.ts#L82-L85)), or from `qwen daemon start` (`handleStart`), the only caller of `buildDaemonStartArgs`, which puts `serve` on the child's command line ([daemon.ts](https://github.com/QwenLM/qwen-code/blob/v0.28.4/packages/cli/src/commands/daemon.ts#L607-L617), [daemon.ts](https://github.com/QwenLM/qwen-code/blob/v0.28.4/packages/cli/src/commands/daemon.ts#L856-L871)). The row's start and wake name no subcommand, and the fake refuses `serve`. The detached self-update a session may start is only in the interactive UI's post-render prefetch ([startup-prefetch.ts](https://github.com/QwenLM/qwen-code/blob/v0.28.4/packages/cli/src/startup/startup-prefetch.ts#L149-L163), called from [startInteractiveUI.tsx](https://github.com/QwenLM/qwen-code/blob/v0.28.4/packages/cli/src/ui/startInteractiveUI.tsx#L364)), never in a headless run. So `daemon` is `none`: the tools a turn runs (monitors included, which `qwen` starts in their own process group, [llm.tsx](https://github.com/QwenLM/qwen-code/blob/v0.28.4/packages/cli/src/llm.tsx#L276-L278)) are processes of the turn, and the driver's stop ends them with its tree.

**The approval-mode values** are the five above.

**Effort: none.** `qwen` 0.28.4 has no effort flag and no effort variable: the CLI's options list none ([top-level-options.ts](https://github.com/QwenLM/qwen-code/blob/v0.28.4/packages/cli/src/config/top-level-options.ts)). Its one effort setting is `model.reasoningEffort` in `settings.json` (`low`, `medium`, `high`, `xhigh`, `max`, set with `/effort`), and "each provider maps and clamps this to what the active model supports (e.g. Gemini caps at \"high\")" ([settingsSchema.ts](https://github.com/QwenLM/qwen-code/blob/v0.28.4/packages/cli/src/config/settingsSchema.ts#L1887-L1907), [modelConfigUtils.ts](https://github.com/QwenLM/qwen-code/blob/v0.28.4/packages/cli/src/utils/modelConfigUtils.ts#L462-L491)). The driver can't write the user's settings, and a value some models silently clamp is one the contract says a row must not claim. So `row.json` says `none`, and a start with an effort is refused, never run at a default.

## What the fake allows

`fake` accepts only the start and wake lines above, with one of the five modes and a UUID session, and exits 2 on anything else: `-p`, `--yolo` with `--approval-mode`, `--session-id` with `--resume`, a non-UUID id, text output, an effort flag, `serve` and `auth`. `test_row.py` proves each of those refusals and that each documented line is taken.

## Evidence

- `evidence/red.txt`: the runner on an empty row (`{}`), failing.
- `evidence/green.txt`: the runner on this row, passing.
