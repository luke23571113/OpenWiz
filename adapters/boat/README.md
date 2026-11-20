# boat.dev driver

A [driver v1](../../kernel/driver.v1.md) that runs each builder in its own [boat.dev](https://boat.dev) cloud sandbox, through your own signed-in `boat` CLI. One Python file, standard library only, Linux (it keeps each turn's processes with `/proc` and a subreaper). Runs are saved in `$OPENWIZ_BOAT_STATE` (default `~/.local/state/openwiz-boat`), owner-only.

| Command | What it does on boat.dev |
| --- | --- |
| `start` | `boat new --name openwiz-<run>`, then `boat prompt <sandbox> --new --provider <harness> --model <model>` with the ticket and skill. It answers once boat has queued the agent's turn. If the prompt fails, it stops the new sandbox before refusing. |
| `wake` | While the last turn's `boat prompt` still runs, nothing: that agent is awake and reads the ticket itself. Otherwise, if boat stopped the sandbox (it auto-stops after an hour without a running prompt), `boat resume` it, then `boat prompt <sandbox> --resume <conversation>`: the same agent, with its memory, edits its own status note. |
| `stop` | Ends every local process the turns started, `boat interrupt`s the agent and `boat stop`s the sandbox. The disk stays for at least 14 days at no compute cost; `boat delete <sandbox>` removes it for good. |

Each turn is a local `boat prompt` under its own supervisor (a subreaper), so the driver can answer at once, and `stop` reaches every process the turn started, whatever its session or environment. The turn's output goes to an owner-only log beside the run's state, deleted on `stop`.

**Never two agents, never one left running.** A wake and a stop hold the run's lock throughout, so they take turns. The driver saves a run before it starts anything for it. A run stays `starting` until its first turn is saved: a wake refuses it, and a stop still reaches its sandbox. If a save fails after a turn began, the driver ends that turn (and, for a start, stops the sandbox) and says the outcome is unknown, never to do it again. A stop that can't save still ends everything, then says so.

`version` adds `many-at-once` and `own-sandbox` to `can`: every run gets its own sandbox, and a boat plan runs many at once.

## Before the first run (yours to do)

The driver never touches a login (driver v1, N1 to N3): it calls `boat` with your environment unchanged, and passes no key, token or password anywhere.

1. Install the `boat` CLI (`curl -fsSL https://boat.dev/install | sh`) and sign in to it yourself.
2. In boat's dashboard, connect GitHub (so the agent's `gh` and `git push` work in the sandbox, as your agents' account) and the key or subscription for each harness you use (Agents & Proxying).
3. `harness` is one of boat's providers: `claude`, `codex`, `pi`, `opencode`, `prime`, `kimi` or `mistral`. `model` is passed to `--model` unchanged.

boat bills per second while a sandbox runs, against your plan.

## The kit

```sh
python3 -I kernel/driver-kit/kit.py --driver adapters/boat/driver \
  --repo <owner>/<throwaway> --ticket <n> --harness claude --model <model>
python3 -I adapters/boat/test_driver.py      # the fixture tests, on a synthetic boat CLI
```

`fixtures/bin/boat` is a synthetic `boat` CLI. Its JSON Lines follow boat's CLI reference; they were not observed on a live account, and the `state` field of `boat info --json` is assumed. The live kit run checks them.
