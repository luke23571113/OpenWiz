# The VPS session: sign in, then one command

For Jake, once, on the VPS. Spec #2474 ("VPS session files"). Everything below is yours to run: no agent signs in, exports a key or passes `--allow-cost` for you. This page holds names only, never a value.

## The session, in order

1. **Bootstrap** the free tools into `~/.local` (#2580): first `kernel/live-rig/vps/bootstrap.sh --dry-run` to read the plan, then `kernel/live-rig/vps/bootstrap.sh`. It never signs in or spends.
2. **Sign in**, yourself: `gh auth login` first (every host needs it; [GitHub CLI manual](https://cli.github.com/manual/gh_auth_login)), then each host's row below. Export each key name in the shell you run step 3 from.
3. **Run the five checks**, from the root of a clean checkout of `main`. `<file>` is a local settings file outside the repository, `{"repo": "<owner>/<throwaway>", "ticket": <n>}`; `<dir>` is a folder outside the checkout. Every host config says `cost: paid`, so a host runs only when you name it, by its host name, with `--allow-cost`:

   ```sh
   python3 -I kernel/live-rig/heads.py --tickets kernel/live-rig/vps/live-tickets.json --hosts kernel/live-rig/vps/hosts --settings <file> --out <dir> --allow-cost Hermes --allow-cost Pane --allow-cost Factory --allow-cost Conductor --allow-cost Cursor
   ```

   Read what it would post, then run the same command again with `--post` added (#2582).

A host you skip signing in to is skipped by the command, `skipped <host> <harness>: <why>`; the rest still run.

## One row per host

Each row starts with the host name its config gives (`hosts/<file>.json`, cited in Sources). "Status check" is what the rig runs before a run: read-only, output discarded, never a sign-in. "Bills" is whether one live turn bills beyond a plan you already have.

| Host | Sign in (yours) | Names you export | Status check | Bills | Sources |
| --- | --- | --- | --- | --- | --- |
| `Hermes` | `hermes setup`: pick Hermes' model and provider (or `hermes setup --portal` for Nous Portal). The run's harness is `claude`, so also sign in to `claude` yourself (run `claude`, then `/login`) and enable Hermes' bundled `claude-code` skill. | none | `gh auth status`. Hermes has no status command whose exit code shows a sign-in: `hermes auth status <provider>` and `hermes doctor` both exit 0 when logged out, so read `hermes status` yourself before step 3. | unknown | `hosts/hermes.json`; `adapters/hermes/README.md` (#2017): "real model turns that cost money", on whatever provider Hermes runs; [Hermes CLI reference](https://hermes-agent.nousresearch.com/docs/reference/cli-commands); [`hermes auth status`](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/auth_commands.py) prints "logged out" and returns; [Claude Code quickstart](https://code.claude.com/docs/en/quickstart) for `/login` |
| `Pane` | Install Pane and open the app, or `runpane install daemon`. Save the throwaway repository's checkout: `runpane repos add --path <checkout>`. Sign in to `claude` yourself (run `claude`, then `/login`). | none | `runpane repos list --json` (fails unless the Pane app or daemon is running), then `gh auth status` | no | `hosts/pane.json`; `adapters/pane/README.md` (#2029): a run "uses that agent's paid model usage or subscription allowance", so on your Claude plan it is the plan's allowance; on a Claude API key it bills; [runpane CLI reference](https://runpane.com/docs/runpane-cli); [Claude Code quickstart](https://code.claude.com/docs/en/quickstart) |
| `Factory` | Run `droid` once and finish Factory's browser device pairing. Make an API key on [Factory's settings page](https://app.factory.ai/settings/api-keys). | `FACTORY_API_KEY` | that the name `FACTORY_API_KEY` is in the environment (never its value; as the drivers check it), then `gh auth status`. A missing name reads `not signed in: python3`. | unknown | `hosts/factory.json`; `adapters/factory/README.md` (#2022): "Factory bills each turn against your Factory plan", so `no` only if you already have one; [Droid exec docs](https://docs.factory.com/droid-exec/overview) for the key and `FACTORY_API_KEY` |
| `Conductor` | Dashboard: a Conductor Pro account with Conductor Cloud, its GitHub App on the throwaway repository, that repository added to your organization's Cloud Computer, and your Claude subscription added in Settings, Agents. Make a user API key on Conductor's API keys page, which the [Conductor API docs](https://www.conductor.build/docs/api) link. | `CONDUCTOR_API_KEY` | that the name `CONDUCTOR_API_KEY` is in the environment (never its value), then `gh auth status`. A missing name reads `not signed in: python3`. | unknown | `hosts/conductor.json`; `adapters/conductor/README.md` (#2020): "Conductor bills nothing for model usage: each agent's own account does", but cloud workspaces need Conductor Pro; [Conductor API docs](https://www.conductor.build/docs/api); [Cloud FAQ](https://www.conductor.build/docs/cloud/faq) |
| `Cursor` | Dashboard: a Cursor plan with cloud agents, GitHub connected to Cursor, and a user API key at cursor.com/dashboard (API Keys). | `CURSOR_API_KEY` | that the name `CURSOR_API_KEY` is in the environment (never its value), then `gh auth status`. A missing name reads `not signed in: python3`. | unknown | `hosts/cursor.json`; `adapters/cursor/README.md` (#2021): "Cursor bills cloud agents at its model rates, against your plan"; [Cloud Agents billing](https://cursor.com/docs/cloud-agent#billing); the run's `composer-2.5` draws from the paid plans' weekly pool, then bills ([Composer 2.5](https://cursor.com/docs/models/cursor-composer-2-5)) |

The two API hosts (Conductor, Cursor) need `curl` 8.3 or later, which the bootstrap installs: their drivers have curl read the key from your environment itself. Each host's harness and model is in its config's `runs`; change one there before step 3 if your plan lists another model.
