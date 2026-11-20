Login: stays on your machine

# Hermes driver

A [driver v1](../../kernel/driver.v1.md) that runs each builder in [Hermes](https://hermes-agent.nousresearch.com) (Nous Research's `hermes-agent`) on this machine, through your own `hermes` CLI. One Python file, standard library only, Linux (it keeps each turn's processes with `/proc` and a subreaper). Built from [`adapters/template/`](../template/README.md). Runs are saved in `$OPENWIZ_HERMES_STATE` (default `~/.local/state/openwiz-hermes`), owner-only.

| Command | What it does in Hermes |
| --- | --- |
| `start` | `hermes chat --oneshot --format stream-json --source tool` with the ticket and skill as its query, under the driver's own supervisor. It answers once Hermes' first `system` `init` line names the session, and saves that `session_id` with the run. If no session is reported within 60 seconds, or the turn ends without one, it ends the turn and refuses. |
| `wake` | While the last turn still runs, nothing: that agent is awake and reads the ticket itself. Otherwise the same command with `--resume <session_id>`: the same Hermes session and transcript, so the agent edits its own status note. A wake after `stop` is refused. |
| `stop` | Sends the turn's processes SIGINT, Hermes' Ctrl-C, so the turn is interrupted and settles cancelled (its `result` ends `exit_code: 130`). Whatever still runs after 10 seconds it ends with SIGTERM and then SIGKILL, every process the run's turns started, through the template's supervisor. Then it deletes the turns' output logs. |

The driver uses Hermes' CLI, not its API server. The API server needs `API_SERVER_KEY` on every request, and a driver never reads a credential (driver v1, N2). The choice is recorded on #1988.

## How `harness` and `model` map

Hermes is its own agent. It reaches Claude Code and Codex only through its bundled skills, which shell out to those CLIs.

| `harness` | What the driver passes |
| --- | --- |
| `claude` | `-s claude-code`, and the query asks Hermes to run the `claude` CLI with `model` and have it run `skill` |
| `codex` | `-s codex`, and the query asks Hermes to run the `codex` CLI with `model` and have it run `skill` |
| `hermes` | `-m <model>`: Hermes itself is the agent, on that model |

Any other `harness` is refused. What this can't control:

- For `claude` and `codex`, `model` and `skill` reach the inner CLI only as words in Hermes' prompt. Hermes runs on its own configured model, and the inner CLI's flags, effort and permissions are whatever Hermes' skill chooses.
- `stop` interrupts and ends what runs on this machine under the turn. If your Hermes setup hands a turn to its gateway or to a remote terminal backend, ending it there is Hermes' job, and the live check shows whether it does.
- The driver adds no `--yolo`. Hermes' own approval settings decide whether the agent may run commands without asking, and a turn with no terminal can't answer a prompt.

## Before the first run (yours to do)

The driver never touches a login (driver v1, N1 to N3). It runs `hermes` with your environment unchanged, and passes no key, token or password anywhere. It never reads `~/.hermes`.

1. Install Hermes and set up its model and provider yourself (`hermes setup`).
2. For `claude` or `codex`, install and sign in to that CLI yourself, and enable Hermes' bundled `claude-code` or `codex` skill.
3. Sign in to `gh` yourself, so the agent can post its status note.

## The kit

```sh
python3 -I kernel/driver-kit/kit.py --driver adapters/hermes/driver \
  --repo <owner>/<throwaway> --ticket <n> --harness claude --model <model>
python3 -I adapters/hermes/test_driver.py      # the fixture tests, on a synthetic hermes CLI
```

`fixtures/bin/hermes` is a synthetic `hermes` CLI. Its arguments and JSON lines follow Hermes' CLI reference. They were not observed on a live install. `evidence/red*.txt` are the failing-first runs and `evidence/green.txt` is the passing run.
