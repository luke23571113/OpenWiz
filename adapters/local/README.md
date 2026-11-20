# The local driver

The default host: a [driver v1](../../kernel/driver.v1.md) that runs builders on the machine it runs on, your computer or a VPS, with the harnesses you have already signed into. One Python file, standard library only, Linux (it finds a run's processes through `/proc`).

```sh
echo '{"repository":"example/site","ticket":7,"skill":"build-ticket","harness":"claude","model":"claude-opus-5-5"}' \
  | adapters/local/driver start             # {"run": "run-0123456789ab"}
echo '{"run":"run-0123456789ab"}' | adapters/local/driver wake
echo '{"run":"run-0123456789ab"}' | adapters/local/driver stop
adapters/local/driver version               # {"driver": "local", ..., "can": [..., "many-at-once"]}
```

- **Harnesses:** `claude` runs `claude -p <prompt> --model <model>`; `codex` runs `codex exec --model <model> <prompt>`. Each is found on `PATH` when the run starts. A harness that isn't installed, or isn't one of these, is a JSON error whose `next` says what to do.
- **Logins:** none. The driver adds no login, token or permission flag. Each turn inherits the environment of whoever runs the driver, unchanged, plus `OPENWIZ_RUN`; the harness's own sign-in and settings decide what its agent may do.
- **Runs:** `start` saves the run, then runs its first turn. A run whose first turn began but couldn't be saved is ended, and its error says the outcome is unknown and what to check; it never says retry. `wake` runs another turn on the same ticket, in which the agent edits its own status note. While the run's last turn is still running, `wake` answers `woke: true` and starts no second turn, so one ticket never has two agents. `stop` ends every process the run's turns started, whatever their session or environment: a polite signal, then a kill after 10 seconds. Each turn runs under a small supervisor (`driver --turn`) that keeps every process it starts, so a worker in its own session or with a clean environment is still stopped. A wake and a stop on one run take turns under its lock. Several runs at once are independent.
- **State:** each run's request and each turn's output log, owner-only, in `$OPENWIZ_LOCAL_STATE` (default `~/.local/state/openwiz-local`).
- **On a VPS:** sign in to the harness there, and run the driver there, for example over `ssh`.

`schema.json` is byte for byte the kit's `kernel/driver-kit/schema.json`.

## Tests

```sh
python3 -I adapters/local/test_driver.py    # the kit's five checks with a synthetic claude and codex, several runs at once, a missing harness
```

The real-host run is the kit's, on a throwaway ticket, with a real signed-in harness:

```sh
python3 -I kernel/driver-kit/kit.py --driver adapters/local/driver --repo <owner>/<throwaway> --ticket <n> \
  --harness claude --model <model>
```
