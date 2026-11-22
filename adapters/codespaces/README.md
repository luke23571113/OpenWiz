# GitHub Codespaces driver
Login: held by GitHub

A [driver v1](../../kernel/driver.v1.md) that runs each builder in its own [GitHub Codespaces](https://docs.github.com/en/codespaces) codespace, on your own GitHub account, through your own signed-in `gh` CLI. One Python file, standard library only. **Platforms:** Linux and macOS, Python 3.9 or later. Runs are saved in `$OPENWIZ_CODESPACES_STATE` (default `~/.local/state/openwiz-codespaces`), owner-only. A run's id is the driver's own: `cs-` and a random hex id.

| Command | What it does in Codespaces |
| --- | --- |
| `start` | First the pre-checks, before anything is created: `gh auth status` must show the `codespace` scope, and `gh api /user/codespaces/secrets` must list one of the harness's secret names (below), with `repository` in that secret's repository list. Only secret names and repository lists are read, never a value. If either check fails, `start` refuses with one line naming the fix, and creates nothing. Then `gh codespace create -R <repository> --default-permissions --display-name openwiz-<ticket> --idle-timeout 240m --retention-period 72h`, with `-m "$OPENWIZ_CODESPACES_MACHINE"` when that is set; the codespace name it prints is saved with the run. One `gh codespace ssh -c <name> -- <command>` installs the WizSkills release OpenWiz pins (`wizskills.lock`) and the harness in the codespace, the way the boat driver installs the pinned release. Then the first turn: a local `gh codespace ssh -c <name> -- <harness command>`, with `claude -p --session-id <uuid>` for `claude` or `codex exec --json` for `codex`, whose thread id is saved. |
| `wake` | Refused after a driver `stop`, and for an unknown run (driver v1, D5). While the last turn still runs, nothing: that agent is awake and reads the ticket itself. Otherwise a new local `gh codespace ssh` turn with `claude -p --resume <uuid>` or `codex exec resume <id>`: the same agent, with its memory. `gh codespace ssh` starts a codespace that GitHub stopped for idleness, and the codespace's home folder (with `~/.claude` and `~/.codex`) survives a stop. A rebuild of the codespace loses that folder, and with it the harness's session: the wake then refuses with one line, and the run needs a new `start`. |
| `stop` | Ends every local process the turns started, then `gh codespace stop -c <name>`, so the codespace stops billing compute. Stopping a run that is already stopped answers again (driver v1, D6). The stopped codespace's disk stays until GitHub deletes it, 72 hours after it stopped (the retention period); `gh codespace delete -c <name>` deletes it sooner. |

GitHub stops a codespace after 240 minutes without activity (the idle timeout set at `start`). Each turn is a local `gh codespace ssh` under the driver's own supervisor, so the driver answers at once and `stop` reaches every process the turn started. Locking, saving a run before starting anything for it, and the supervisor follow the [boat driver](../boat/README.md): a wake and a stop take turns, and no run is left with two agents or with one left running.

**No key in, no diagnostic out.** The driver never reads, passes or prints a key (driver v1, N1 to N3). The harness's login reaches the codespace as a Codespaces user secret that GitHub puts in the codespace's environment, where the harness reads it. No command the driver sends into the codespace names that secret with `$`, `${`, `env`, `printenv` or `set`. A failed `gh` command answers fixed words that name the failure and its fix; `gh`'s own text never reaches the driver's answer.

`version` adds `many-at-once` and `own-sandbox` to `can`: every run gets its own codespace.

## Before the first run (yours to do)

1. Install the [`gh` CLI](https://cli.github.com) and sign in to it yourself (`gh auth login`).
2. Give `gh` the `codespace` scope: `gh auth refresh -h github.com -s codespace`. `start` checks it.
3. **Set the harness's login as a Codespaces secret, by name,** for each repository you build. You type the value into `gh` yourself, at its prompt:
   - for `claude`: `gh secret set CLAUDE_CODE_OAUTH_TOKEN --user --repos <owner/name>` (or `ANTHROPIC_API_KEY` in its place, for an API key);
   - for `codex`: `gh secret set CODEX_API_KEY --user --repos <owner/name>`.

   `--user` makes it a Codespaces secret of your own account, and `--repos` is the list of repositories whose codespaces get it: name every repository you build, comma-separated (`--repos owner/one,owner/two`). Leave out `--body`, so the value is typed at the prompt and never lands in your shell's history. The driver reads only the secret's name and its repository list, never its value. Deleting the secret (`gh secret delete <NAME> --user`) revokes it.

`harness` is `claude` or `codex`, the two whose secrets are named above.

**Machine:** `$OPENWIZ_CODESPACES_MACHINE` is passed to `gh codespace create -m` unchanged; when it is unset, no `-m` is passed. `gh api /repos/<owner/name>/codespaces/machines` lists the machine types a repository can use.

**Costs:** Codespaces bills compute, while a codespace runs, and storage, while it exists (stopped included), to your own GitHub account, or takes them from its monthly free quota. `stop` ends the compute; the storage lasts until the codespace is deleted, by the 72-hour retention period or by `gh codespace delete -c <name>`.

**Effort:** runs use the host's default effort. Driver v1's `start` has no effort field, so whatever effort a fleet configures isn't applied, and each prompt tells the agent to write its status note's model as `<model> default effort`. Passing an effort needs a driver v2 field, a separate decision.

**Not yet checked live:** whether the codespace's own `GITHUB_TOKEN` lets the agent post its status note and push its branch, and whether an open `gh codespace ssh` turn keeps the codespace from idling out. The live check answers both.

## The kit

```sh
python3 -I kernel/driver-kit/kit.py --driver adapters/codespaces/driver \
  --repo <owner>/<throwaway> --ticket <n> --harness claude --model <model>
python3 -I adapters/codespaces/test_driver.py      # the fixture tests, on a synthetic gh CLI
```

The kit run creates a real codespace on your account, which costs money; `gh codespace delete -c <name>` it afterwards. `fixtures/bin/gh` is a synthetic `gh` CLI (`auth status`, `api /user/codespaces/secrets`, `codespace create`, `ssh`, `stop` and `list`), whose `ssh` runs a synthetic harness locally.
