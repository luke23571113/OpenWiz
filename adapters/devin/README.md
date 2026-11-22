# Devin driver

Login: held by Devin

- The key is your own `DEVIN_API_KEY`, or the keychain entry `openwiz-devin` when that variable is unset.
- OpenWiz never stores it. Remove it from your environment or keychain to revoke it.

A [driver v1](../../kernel/driver.v1.md) for [Devin](https://devin.ai): each run is one Devin session, and its run id is Devin's session id (`devin-...`). One Python file, standard library only. **Platforms:** Linux and macOS, Python 3.9 or later.

Every Devin call goes through the kit's key helper, [`hostkey.py`](../../kernel/driver-kit/hostkey.py), for host `devin` (driver v1 N4). The driver sends it only a method, a path and a body. The helper alone reads the key and sends it to Devin's registered address. The driver never reads, names or passes the key, and never builds a URL.

| Command | Devin call (v3 sessions API) |
| --- | --- |
| `start` | `POST /v3/organizations/<org>/sessions` with `prompt` (the skill's one-line brief, as the template's) and, unless `model` is `default`, `devin_mode`. It saves the session before it answers. If it can't save it, it terminates the session and says the outcome is unknown |
| `wake` | `POST /v3/organizations/<org>/sessions/<run>/messages` with `message` ("You were woken: read the ticket again and carry on"). Devin resumes a suspended session for it. A stopped run takes no wake |
| `stop` | Marks the run stopped, then `DELETE /v3/organizations/<org>/sessions/<run>`, which terminates the session. If Devin refuses, the run stays stopping: no wake, and the next `stop` sends the terminate again. Once Devin has terminated it (or answers 404 or 410), a later `stop` answers without a call |

- **Organization.** `<org>` is your `DEVIN_ORG_ID` (`org-...`, in Devin's settings). It is not a credential. `start` refuses without it, and a run keeps the organization it started in.
- **`harness` and `model`.** `harness` is always `devin`. Devin picks its own model, so `model` names a Devin mode: `default` (your organization's default; no `devin_mode` is sent), or one of `normal`, `fast`, `fusion`, `lite`, `ultra`, `fast-ultra`, `swe-2-medium`, `swe-2-high` and `swe-2-max`. Anything else is refused before any call.
- **The key** needs Devin's session permission (`UseDevinSessions`). A 401 or 403 is an error that says so, and never shows Devin's answer.
- **State.** Runs (session id, organization, request) are kept in `$OPENWIZ_DEVIN_STATE` (default `~/.local/state/openwiz-devin`, owner-only). A wake or a stop holds the run's lock (`<run>.lock`).

## Tests and the kit

```sh
python3 -I adapters/devin/test_driver.py      # the kit's five checks, key check included, on a synthetic Devin
python3 -I kernel/driver-kit/kit.py --driver adapters/devin/driver \
  --repo <owner>/<throwaway> --ticket <n> --harness devin --model default   # the real host
```

`fixtures/fake-devin` is a synthetic Devin on `127.0.0.1`, reached through the helper's loopback test override (`OPENWIZ_HOSTKEY_TEST_ORIGIN`, with a synthetic `OPENWIZ_HOSTKEY_TEST_KEY`). It never reaches Devin, and plays each session's agent by posting and editing the builder status note in the kit's local tracker. `fixtures/kit-host.json` is what the kit's own fake host answers during the key check. The kit sees only processes on its own machine: here, the driver and the helper. The session runs on Devin, and ends when Devin terminates it.
