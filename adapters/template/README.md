# Driver template

The smallest [driver v1](../../kernel/driver.v1.md): one Python file, standard library only, Linux. It passes the [kit](../../kernel/driver-kit/README.md). Each turn of a run is a local process: `start` runs the first turn, `wake` runs another, `stop` ends them all. Runs are saved in `$OPENWIZ_TEMPLATE_STATE` (default `~/.local/state/openwiz-template`).

## Make your own in an hour

1. Copy this folder to `adapters/<host>/`. Rename `template` in `VERSION`, and the state folder's name.
2. **`command`**: the command line your harness runs a turn with, using its own signed-in login. It must never add a login or a token. The template calls the program named by `harness` with `--model` and `-p`; map your harness names here.
3. **`launch` and `end`**: how your host starts a turn and ends one. For a remote host, call its own signed-in tool here, and return what `end` needs.
4. Add `many-at-once` or `own-sandbox` to `can` only when your host does that.
5. Run the kit against it on a throwaway ticket, on its real host, and put the output on the pull request.

Keep `schema.json` byte for byte the kit's `kernel/driver-kit/schema.json`: the kit checks it.

```sh
echo '{"repository":"example/site","ticket":7,"skill":"build-ticket","harness":"claude","model":"opus"}' \
  | adapters/template/driver start          # {"run": "run-0123456789ab"}
adapters/template/driver schema             # every command's JSON Schema
```
