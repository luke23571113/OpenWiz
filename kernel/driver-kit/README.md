# Driver v1 test kit

Runs the five checks of [driver v1](../driver.v1.md) against one driver, on one throwaway ticket. **Platforms:** Linux and macOS, Python 3.9 or later, standard library only (it watches `/proc` on Linux, and `ps` on macOS). It never writes to GitHub: the agent the driver starts writes its own status note.

```sh
python3 -I kernel/driver-kit/kit.py --driver adapters/<host>/driver \
  --repo <owner>/<throwaway> --ticket <n> --harness <h> --model <m> [--skill build-ticket] [--wait 900]
python3 -I kernel/driver-kit/test_kit.py     # the kit's own tests: the template passes, each planted driver fails
python3 -I kernel/driver-kit/test_hostkey.py # the key helper's own tests: every refusal, and the key never leaks
```

It prints one line per check, in the order version, start, wake, stop, token: `pass <check>: <what>` or `fail <check>: <why>`. Exit 0: all five pass. 1: a check failed. 2: the kit could not run; it says why on stderr, `kit.py: <why>`. Wake and stop run only after start passes.

## Key hosts

A host driven only through an API that takes the user's key is reached only through the key helper, [`hostkey.py`](hostkey.py) (driver v1 N4). The driver runs `python3 -I kernel/driver-kit/hostkey.py` with exactly `host`, `method` (`GET`, `POST` or `DELETE`), `path` and an optional `body` on stdin, and reads back exactly `status` and `body`, or a D3 error. The helper alone reads the key (16 to 4096 letters, digits or `._~+/=-`): from the host's variable in [`hosts.json`](hosts.json), or else its keychain entry through `/usr/bin/security` or `/usr/bin/secret-tool`. It sends the key only in an `Authorization: Bearer` header, over HTTPS with the system's TLS defaults (it clears `OPENSSL_*` and `SSL_*` variables first), to the registered origin. It refuses an unregistered host, an escaping path or a request that holds the key before any network call, follows no redirect, and never prints or stores the key. Adding a host is one reviewed entry in `hosts.json`. Under the kit's loopback override, `OPENWIZ_HOSTKEY_TEST_ORIGIN` (honoured only as `http://127.0.0.1:<port>`), the helper reads only the synthetic `OPENWIZ_HOSTKEY_TEST_KEY`, never the host's variable or the keychain.

When a driver's `README.md` names a registered host, the token check runs the key check. It plants a canary key in the host's variable and in `OPENWIZ_HOSTKEY_TEST_KEY`, points the helper at a loopback fake host, and runs start, wake and stop, sampling the processes every few milliseconds while each runs. It passes only when start, wake and stop each reached the fake host from the helper's own process (`python3 -I` and the kit's `hostkey.py`), with the canary in its `Authorization` header and nowhere else. The canary must never appear in the driver's output, on a command line or in another variable. No file of the driver's folder, and no script its processes run outside it, may name the host's variable or call `security` or `secret-tool`; in `README.md`, only a line naming both the variable and the keychain entry may name them. The fake host answers `200 {}`, or what the driver's `fixtures/kit-host.json` says: exactly `answers`, each exactly `method`, `path` (a pattern), `status` and `body`. A README whose login line is `Login: stays on your machine` needs no registry; any other README needs the helper and its registry, or the kit exits 2. Sampling can miss a process that lives less than a few milliseconds, and a module a driver imports without running it is not scanned: the driver's review covers both.

## The throwaway ticket

Make a throwaway repository with a `docs/agents/fleet.md` whose `Record authors` row names the account your agents post as, and one open ticket in it. The kit reads the ticket's comments through a signed-in `gh` (GraphQL only), every 10 seconds, for up to `--wait` seconds per step. Close the ticket when you're done; the kit leaves it as it is.

`--tracker <file>` reads the ticket from a local file instead of GitHub, for the kit's own tests: a JSON object with exactly `record_authors` (logins) and `comments` (each exactly `id`, `author`, `updated_at` and `body`).

## What it doesn't see

It knows a credential by the status contract's credential rules or as the value of a secret in its own environment. It never shows a driver answer that holds one, in its text or once decoded: that answer fails with a fixed diagnostic.

It sees the processes a driver starts on this machine (each carries the kit's `OPENWIZ_KIT_RUN` mark in its environment), not what a remote host runs. A driver that clears its children's environment hides them from the token and stop checks: its review must check that by reading its code.

On macOS, with no `/proc`, the kit lists processes with `ps -A`, and reads each one's environment with `ps -E`. Where `ps` shows a process's environment, the mark finds it as on Linux. Where it shows none, the kit finds the run's processes by process group instead: a process belongs to the run when it is in a group where the kit has seen a marked process, never the kit's own group. On macOS a process's environment is what `ps -E` prints after its command line. The token check drops each variable the kit gave the driver unchanged, then splits the rest only where a new `NAME=` begins, so a value with spaces stays whole. First the kit checks that `ps -E` shows the environment of a process it starts itself. Where it doesn't, stop and token fail, because the kit can't tell which processes the driver started: `ps shows no process's environment here, so the kit cannot tell which processes the driver started`. Seeing the probe is not enough: stop and token pass only once `ps -E` has shown at least one of the run's own processes, carrying the mark. Where it never has, both fail as unverified, whatever the probe showed: `ps -E never showed a process of this run, so the kit cannot tell which processes the driver started`. So on macOS, a driver whose processes all run on another machine cannot pass stop and token here.

## Fixtures

- `fixtures/no-proc/`: runs Python as on macOS, on Linux: no `/proc`, no `prctl` and no pidfd, `sys.platform` `darwin`, and a `ps` that takes macOS's `-E` (with `NO_PROC_HIDE_ENV` set, it shows no environment at all; with `NO_PROC_PROBE_ONLY` set, only the kit's own probe's). The drivers' and the kit's tests put it first on `PATH` to run the macOS path (#2010).
- `fixtures/fake-harness`: a synthetic harness. It posts one builder note into the tracker named by `KIT_TRACKER`, edits it when woken, then waits to be stopped.
- `fixtures/planted/<name>`: the template with one planted break each. `test_kit.py` names the exact lines each must print.
- `fixtures/key-host/`: a fake key-host driver, the template sending each start, wake and stop to host `devin` through the helper. `fixtures/planted/key-*/` are it with one key break each: it reads the key itself (in the driver, in a `test_*` file it imports, or in a script it runs, `fixtures/runtime-reader`), names the variable in its README, passes the key in an argument, in another variable, in a variable's name, in a short-lived child or in a request body, prints it, sends it to the host itself, asks for an unregistered host or for a path with a host in it, calls the keychain tool, or meets a fake host whose `fixtures/kit-host.json` refuses start. `test_kit.py` also runs it against a fake host that answers a redirect: start fails, and the redirect's target gets no request.
- `evidence/`: the red run and the green run; `red-1586.txt`, `red-1586-r1.txt` and `green-1586.txt` are those of the credential fixes. `red-2039.txt` and `green-2039.txt` are those of the run-seen rule on macOS. `red-2379-*.txt` and `green-2379.txt` are those of the key helper and the key check; `red-2379-review-*.txt` and `green-2379-review.txt` are those of its review round.
