# Cloudroom driver

A [driver v1](../../kernel/driver.v1.md) for [Cloudroom](https://cloudroom.dev): each run is one Cloudroom thread. One Python file, standard library only. Run it inside a Cloudroom thread of the project the repository belongs to, where `room-cli` is already signed in and `ROOM_PROJECT_ID` is set; the threads it starts are that thread's children, each in its own sandbox.

| Command | What it runs |
| --- | --- |
| `start` | `room-cli thread spawn --parent-self --project $ROOM_PROJECT_ID --provider <harness> --model <model> --title "#<ticket>: <repository> builder" --prompt <the skill's one-line brief>`. The harness `claude` is Cloudroom's `claude-code`; other names pass as they are. The run exists only once Cloudroom's answer names a thread of this project |
| `wake` | `room-cli thread tell <thread> --mode queue --message-file <file>`: "You were woken for `<repository>#<ticket>`: read the ticket again, edit your own status note, and carry on". It answers `woke` only when `room-cli` accepts the message; a refusal is an error that leaves the run for the next wake |
| `stop` | `room-cli thread archive <thread>`, which stops the thread and archives it. A refusal leaves the run live |

Runs (run id, thread id, request) are kept privately in `$OPENWIZ_CLOUDROOM_STATE` (default `~/.local/state/openwiz-cloudroom`, owner-only). A run id never shows its thread.

**Logins.** The driver never reads, adds or passes a login: `room-cli` runs with the caller's environment unchanged, and inputs carry no credential (D1, N1 to N3).

## Waking on GitHub's events

GitHub's events reach a fleet through launch-fleet's route (#1329's FF2): the repository's webhook runs the project's wake loop, its tick runs `fleet.sh wake` on the numbers the events name, and for a spec with a fleet loop that runs the loop. The fleet wake then delivers to the ticket's builder with `room-cli thread tell <id> --mode queue --message-file <file>`, counting it only on `tell`'s own acceptance. `wake` is exactly that delivery, so a fleet that keeps a run id calls `driver wake` there instead, with the same rules.

## Tests and the kit

```sh
python3 -I adapters/cloudroom/test_driver.py   # the kit's five checks and the wake route, on a synthetic room-cli
python3 -I kernel/driver-kit/kit.py --driver adapters/cloudroom/driver \
  --repo <owner>/<throwaway> --ticket <n> --harness claude --model claude-opus-5-5   # the real host
```

`fixtures/room-cli` is a synthetic `room-cli`: it never reaches Cloudroom, and runs each thread's turns as local processes of the kit's fake harness. The kit sees only processes on its own machine, so on the real host its stop and token checks see `room-cli` itself, not the remote thread; that thread ends when Cloudroom archives it.
