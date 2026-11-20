Login: stays on your machine

# OpenClaw driver

A [driver v1](../../kernel/driver.v1.md) that runs builders on this machine through [`acpx`](https://github.com/openclaw/acpx), OpenClaw's own headless command-line client for the Agent Client Protocol (MIT). It never uses the OpenClaw gateway: the gateway refuses remote agent starts by default, and this driver never asks you to loosen that. One Python file, standard library only, Linux, built on [`adapters/template/`](../template/README.md). Runs are saved in `$OPENWIZ_OPENCLAW_STATE` (default `~/.local/state/openwiz-openclaw`), owner-only.

| Command | What it does with `acpx` |
| --- | --- |
| `start` | Makes the run's own empty folder, `work/<run>` in the state folder, and opens one named session there: `acpx --cwd <folder> --model <model> --auth-policy fail --permission-policy <policy> --non-interactive-permissions deny <harness> sessions new --name <run>`. Then it sends the first prompt, the ticket and skill, with `acpx ... --ttl 60 <harness> -s <run> --no-wait <prompt>`, and answers once that prompt has started. If the session can't be opened (a missing sign-in, say), nothing more starts and the error says where acpx's output is. |
| `wake` | While the last prompt still runs, nothing: that agent is awake and reads the ticket itself. Otherwise one follow-up prompt to the same session, so the same agent, with its memory, edits its own status note. A stopped run is never woken. |
| `stop` | `acpx <harness> cancel -s <run>`, then `acpx <harness> sessions close <run>`, then it ends every process the run's acpx calls started, acpx's queue owner included, so nothing is left. Stopping again answers again. The run's folder stays, in case it holds unpushed work; delete it when you are done. |

Each acpx call runs under its own supervisor (`driver --turn`, a Linux child subreaper, as in the template), so `stop` reaches every process the call started, whatever its session or environment. acpx's output goes only to the run's owner-only log, `<run>.log` in the state folder; an error never repeats it. A wake and a stop hold the run's lock throughout. The driver saves a run before it starts anything for it, and if a save fails after a prompt began, it ends that prompt and says the outcome is unknown, never to retry.

## Permissions

Unattended tool use goes through a permission policy, never `--approve-all`. The policy approves the tool kinds a builder needs (`read`, `search`, `edit`, `move`, `execute`, `think`, `fetch`), denies `delete` and `switch_mode`, and denies anything else; with `--non-interactive-permissions deny` acpx never waits on a question nobody can answer. Approving `execute` lets the agent run commands in its folder, as a builder must (git, tests); read the policy in `driver` (`POLICY`) before your first run.

## Before the first run (yours to do)

The driver never touches a login (driver v1, N1 to N3): it adds no key, token or password to any call, and every acpx call inherits your environment unchanged (plus `OPENWIZ_RUN`). With `--auth-policy fail`, a harness that isn't signed in fails the start instead of prompting.

1. Install Node.js 22.13 or later and `acpx` (`npm install -g acpx`).
2. Sign in to the harness yourself, on this machine: `claude` or `codex` as usual. acpx starts that harness's ACP adapter, which uses your own sign-in.
3. Sign in to `gh` yourself, and install the skills your agents use, as for any local builder.
4. `harness` is one of acpx's built-in agents: `claude`, `codex`, `copilot`, `cursor`, `droid`, `gemini` or `opencode`. Any other name is refused: acpx would run it as a raw command, and its `openclaw` agent goes through the gateway. `model` is passed to `--model` unchanged.

## The kit

```sh
python3 -I kernel/driver-kit/kit.py --driver adapters/openclaw/driver \
  --repo <owner>/<throwaway> --ticket <n> --harness claude --model <model>
python3 -I adapters/openclaw/test_driver.py   # the fixture tests, on a synthetic acpx
```

`fixtures/bin/acpx` is a synthetic `acpx`; its command shapes follow `acpx --help` of acpx 0.22.0, and `evidence/acpx-shapes.txt` shows the real acpx 0.22.0 parsing each call the driver makes. The tests run with a `PATH` that holds only the fake, `python3` and `sleep`, so no real harness or acpx ever runs. `schema.json` is byte for byte the kit's `kernel/driver-kit/schema.json`.
