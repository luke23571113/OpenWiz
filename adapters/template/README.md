# Driver template

The smallest [driver v1](../../kernel/driver.v1.md): one Python file, standard library only, Linux. It passes the [kit](../../kernel/driver-kit/README.md). Each turn of a run is a local process: `start` runs the first turn, `wake` runs another once the last one has ended, and `stop` ends every process the run started. Runs are saved in `$OPENWIZ_TEMPLATE_STATE` (default `~/.local/state/openwiz-template`), each one before its first turn starts.

## Make your own in an hour

1. Copy this folder to `adapters/<host>/`. Rename `template` in `VERSION`, and the state folder's name.
2. **`command`**: the command line your harness runs a turn with, using its own signed-in login. It must never add a login or a token. The template calls the program named by `harness` with `--model` and `-p`; map your harness names here.
3. **`launch`, `running` and `end`**: how your host starts a turn, tells whether it still runs, and ends the run. For a remote host, call its own signed-in tool here, and return what `running` and `end` need. Keep the three rules they hold:
   - **`stop` ends everything.** The template's `end` finds every process carrying the run's `OPENWIZ_RUN` mark, the turn's children too, even after the turn itself has exited, and answers only once none is left.
   - **One agent at a time.** `wake` starts no turn while the last one runs: that agent is awake and reads the ticket itself.
   - **No run, no agent.** `start` saves the run before it launches anything. If the save fails after the launch, it ends the turn and says the outcome is unknown, never "retry".
4. Add `many-at-once` or `own-sandbox` to `can` only when your host does that.
5. Run the kit against it on a throwaway ticket, on its real host, and put the output on the pull request.

Keep `schema.json` byte for byte the kit's `kernel/driver-kit/schema.json`: the kit checks it.

Its own tests: `python3 -I adapters/template/test_driver.py`.

```sh
echo '{"repository":"example/site","ticket":7,"skill":"build-ticket","harness":"claude","model":"opus"}' \
  | adapters/template/driver start          # {"run": "run-0123456789ab"}
adapters/template/driver schema             # every command's JSON Schema
```
