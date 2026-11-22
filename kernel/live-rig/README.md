# Live-check rig

Runs the [driver v1 kit](../driver-kit/README.md) against real hosts, on a schedule, wherever a signed-in tool already exists on the machine. Each run of the kit leaves a run record; a host that can't run is skipped, and its record says why. The design is spec #2474. **Platforms:** Linux and macOS, Python 3.9 or later, standard library only.

## Hard limits

- It never signs in, installs anything, spends money or starts a paid run: a host whose tool is missing, isn't signed in, or whose run might cost money is skipped.
- It never reads, adds or prints an environment value, and never passes a key: each status command and the kit get the caller's environment unchanged.
- It writes nothing to GitHub. The kit only reads the throwaway ticket, through the signed-in `gh`.
- It keeps only the kit's stdout and exit code; the kit's stderr goes straight to the rig's. Status commands get no stdin and their output is discarded.

## Run it

From the root of a clean checkout (a run record names its commit, so uncommitted changes refuse):

```sh
python3 -I kernel/live-rig/rig.py --hosts kernel/live-rig/hosts --settings <file> --out <dir> [--host <name>]
python3 -I kernel/live-rig/test_rig.py      # its own tests, on fixtures only
```

- `--settings`: a local JSON file outside the repository, `{"repo": "<owner>/<name>", "ticket": <n>}`, naming the throwaway repository and ticket the kit uses ([the kit's throwaway ticket](../driver-kit/README.md#the-throwaway-ticket)).
- `--out`: a folder outside the checkout. It holds the lock (`rig.lock`), so two runs never overlap: a second one prints `rig.py: another run holds the lock` and exits 0.
- `--hosts`: only its `*.json` files are host configs; anything else there (a host's `test_<host>.py`) is ignored.

Per host, in order: every `needs` program, then every `signed_in` command, then `cost`, then one kit run per `runs` entry:
`python3 -I kernel/driver-kit/kit.py --driver <driver> --repo <repo> --ticket <n> --harness <h> --model <m> --wait <w>`.
It prints one line per entry, `ran <host> <harness>: <k> of 5` or `skipped <host> <harness>: <why>`, where `<why>` is `not installed: <program>`, `not signed in: <program>` or `cost`. Exit 0: every entry ran or was skipped. 1: a kit exited 1 or 2. 2: the rig could not run; it says why on stderr, `rig.py: <why>`.

[`schedule.json`](schedule.json) is the weekly run (Monday 03:00), with the exact command, run from the checkout's root with the settings and records in a sibling folder. It runs on the PC only, never in the cloud.

## Host config

`hosts/<host>.json`, one per host, with exactly the keys of spec #2474's Implementation Decisions:

```json
{"host": "boat.dev", "driver": "adapters/boat/driver", "needs": ["boat"], "signed_in": [["boat", "status"]],
 "cost": "none", "runs": [{"harness": "claude", "model": "Opus 5.5"}], "wait": 900}
```

`signed_in` commands are read-only (never one that signs in, opens a browser, prompts or prints a credential), each must exit 0 within 30 seconds, and a timeout counts as not signed in; each host's pull request cites its command's source. Only `cost: none` runs; `paid` and `unknown` are skipped, and changing a host to `none` needs Jake's recorded OK. `wait` is at most 900. The example above is a shape, not a real host's config.

## Run record

`<out>/<YYYY-MM-DD>/<host>-<harness>-<model>.json`, one per `runs` entry, with exactly: `host`, `harness`, `model`, `date` (UTC), `driver_commit` and `kit_commit` (the checkout's 40-hex `HEAD`), `outcome` (`ran` or `skipped`), `skipped` (the reason or `null`), `kit_exit` (integer or `null`), `stdout` (the kit's stdout, or `null`) and `seconds` (whole seconds). It holds no login or environment value; where the kit's stdout quotes the checkout's path or the settings' repository, those read `<checkout>` and `<repository>`. The receipt writer reads these records.

## Fixtures

- `fixtures/hosts/`: fixture host configs: one on `adapters/template/driver` that runs 5 of 5, one with a missing program, one whose status command fails, one with `cost: unknown`, one on a planted driver, and one whose driver quotes the checkout's path and the repository.
- `fixtures/rig/`: the tests' fakes. `gh` answers the kit's two GraphQL reads from the kit's fake harness's tracker file, so the kit runs with the rig's exact command line and never reaches GitHub; `fake-signed-in` and `fake-signed-out` are status commands; `planted-driver` becomes `adapters/planted/driver` in the tests' throwaway checkout, the kit's `wake-does-nothing` planted driver, and `quoting-driver` becomes `adapters/quoting/driver`, whose refused start quotes both. Every test puts refusing stubs for the agent CLIs first on `PATH`, so a fixture mistake can never start a real one.
