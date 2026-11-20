# The local driver

The default host: a [driver v1](../../kernel/driver.v1.md) that runs builders on the machine it runs on, your computer or a VPS, with the harnesses you have already signed into. One Python file, standard library only, Linux (it finds a run's processes through `/proc`).

```sh
echo '{"repository":"example/site","ticket":7,"skill":"build-ticket","harness":"claude","model":"claude-opus-5-5"}' \
  | adapters/local/driver start             # {"run": "run-0123456789ab"}
echo '{"run":"run-0123456789ab"}' | adapters/local/driver wake
echo '{"run":"run-0123456789ab"}' | adapters/local/driver stop
adapters/local/driver version               # {"driver": "local", ..., "can": [..., "many-at-once"]}
```

- **Harnesses:** `claude` runs `claude -p <prompt> --model <model> --permission-mode <mode>`; `codex` runs `codex exec --model <model> --sandbox <mode> <prompt>`. Each is found on `PATH` when the run starts. A harness that isn't installed, or isn't one of these, is a JSON error whose `next` says what to do.
- **Permission mode:** the owner chooses it once, during setup, for the repository, and saves it in that repository's `docs/agents/fleet.md` as one row: `| Harness permission mode | `<mode>` |`. Use a `claude --permission-mode` value or a `codex --sandbox` value, for the harness that repository's builders use. The driver reads the row from the run's fresh clone and passes the value unchanged as that harness's own option. It never chooses, adds or widens a permission. With no such row (or more than one, or a value that isn't one plain word), `start` refuses before anything runs, and its `next` says to save the row. Without a mode, a stock harness in `-p`/`exec` refuses every tool and the builder can do nothing.
- **Logins:** none. The driver adds no login or token. Each turn, and the clone, inherit the environment of whoever runs the driver, unchanged (the turn also gets `OPENWIZ_RUN`); the harness's and `gh`'s own sign-ins decide what they may reach.
- **Workspaces:** each run gets its own fresh clone of the request's repository (`gh repo clone`, the person's own signed-in GitHub CLI), in `$OPENWIZ_LOCAL_STATE/work/<run>`. Every turn of that run works there, and two runs never share a checkout. A workspace stays after `stop`, in case it holds unpushed work; delete it when you are done.
- **First turn:** `start` watches the first turn for `$OPENWIZ_LOCAL_SETTLE` seconds (default 30) before it answers. A first turn that has already ended (a harness refusing its tools ends at once, posting nothing) fails `start`, and the error shows the turn's last log line, unless that line looks like a credential, and where the full log is.
- **Runs:** `start` saves the run, then runs its first turn. A run whose first turn began but couldn't be saved is ended, and its error says the outcome is unknown and what to check; it never says retry. `wake` runs another turn on the same ticket, in which the agent edits its own status note. While the run's last turn is still running, `wake` answers `woke: true` and starts no second turn, so one ticket never has two agents. `stop` ends every process the run's turns started, whatever their session or environment: a polite signal, then a kill after 10 seconds. Each turn runs under a small supervisor (`driver --turn`) that keeps every process it starts, so a worker in its own session or with a clean environment is still stopped. A wake and a stop on one run take turns under its lock. Several runs at once are independent.
- **State:** each run's request, its workspace and each turn's output log, owner-only, in `$OPENWIZ_LOCAL_STATE` (default `~/.local/state/openwiz-local`).
- **On a VPS:** sign in to the harness and to `gh` there, and run the driver there, for example over `ssh`.

`schema.json` is byte for byte the kit's `kernel/driver-kit/schema.json`.

## Tests

```sh
python3 -I adapters/local/test_driver.py    # the kit's five checks and every rule above, with a synthetic claude, codex and gh
```

The real-host run is the kit's, on a throwaway ticket, with a real signed-in harness and `gh`. The throwaway repository's `docs/agents/fleet.md` needs its `Record authors` row and its `Harness permission mode` row:

```sh
python3 -I kernel/driver-kit/kit.py --driver adapters/local/driver --repo <owner>/<throwaway> --ticket <n> \
  --harness claude --model <model>
```
