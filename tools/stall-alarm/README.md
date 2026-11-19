# Stall alarm (#567)

A small check for the confirmed bottlenecks grill, BN2. It reads the war
room collector's factory facts (#824) and the selected fleet loop, writes
only its own local alarm state, and
prints one line per new stall. Quiet ticks print nothing and start no agent.
An alarm still confirmed 30 minutes after its first detection prints one
additional `JAKE:` line, once. Recovery is silent and rearms the alarm.

```sh
python3 tools/stall-alarm/test.py
python3 tools/stall-alarm/alarm.py --repo example-owner/example-repo \
  --fleet-loop loop_fixture --state /tmp/stall-alarm-example.json
```

Needs Python 3 (standard library only), a checkout holding
`tools/collector/collect_factory.py` with an authenticated `gh` for it, and
the full managed local `room-cli loop list --json` on the PC. No package or
crate is added.
The second command is a real read; the tests use isolated fakes only.

The [runtime ruling on #567](https://github.com/jparker2006/ClosedWiz/issues/567#issuecomment-6575288221)
selects a **Local, script-only check on the PC**. The generated script
selects the running Linux app's bundled CLI. An absolute
`STALL_ALARM_ROOM_CLI` can select another verified managed launcher; the
orchestrator verifies it before installation. Direct CLI invocations use
`room-cli` on PATH unless this variable is set. Cloud check sandboxes are
not a supported deployment. Installation, activation and delivery remain
pending; the builder proves the command boundary with fakes.

## The ticket stall rule (FM3, #1171)

`stalls.py` reads one collector snapshot or flow read (the `flow` fact of
[collector v1](../collector/collector.v1.md)) and prints the stall list and
the daily count. It reads nothing else and writes nothing.

```sh
python3 -I tools/stall-alarm/stalls.py --input snapshot.json
```

- **The rule:** a claimed, unmerged, open ticket whose `last_observed_at`
  (its latest commit, record, CI result or verdict) is 30 minutes or more
  before the flow fact's read point is a stall. Progress inside 30 minutes is
  never a stall, even on a partial history. With 30 minutes or more and an
  incomplete history, the ticket is listed under `unknown`, never stall-free.
- **One cause,** from a fixed list, first match: `ci` (a pending workflow
  attempt), `jake` (the latest factory record is `asked the orchestrator`,
  `told the user`, `parked` or `needs approval`), `limit` (`builder fallback
  due`), `stuck` (CI is not pending and the latest record names no outside
  wait), else `unknown`. A flow fact without `last_record` leaves every cause
  but `ci` unknown.
- **The daily count** is the number of stalls that began (30 minutes after
  their last progress) on the read point's UTC day, up to the read point: the
  ticket's dated `gaps` plus the open stalls. It is null when any ticket active
  that day has an unknown history.
- An unavailable or absent flow fact gives null `stalls`, `unknown` and
  count, never an empty list or zero.

Fixture proof: `python3 -B -I tools/stall-alarm/test.py FlowStalls`, over
[`fixtures/flow-read.json`](fixtures/flow-read.json) (synthetic). Red runs:
[`evidence/1171-red-first.log`](evidence/1171-red-first.log) and
[`evidence/1171-red-unknown.log`](evidence/1171-red-unknown.log).

## What fires

| Alarm | Evidence read at this tick | Clears when |
| --- | --- | --- |
| Fleet loop | Selected `automations[].id` is disabled, has nonempty `last_error`, has an overdue `last_run_at`, or never ran before startup grace expired | That loop is enabled, error-free and running within its cadence and grace |
| No merges | `merges` holds no PR merged to the default base during the last 60 minutes, and in `open_prs` at least one open, non-draft PR has its latest verdict `APPROVE` at the current head, a `success` rollup with each required check `success`, and `MERGEABLE` | A recent merge exists or no PR meets those conditions |
| Idle agent | In `open_prs`, the later of a PR's latest fleet record and latest verdict is a `findings sent`, `CI failure sent` or `re-check sent` record that names its current head, and is at least 60 minutes old | New head, newer record/verdict, or PR closes |
| Failed read | A source failed, timed out, returned malformed/partial JSON or lacked the selected loop; for GitHub, the collector failed or either fact is not `known` | That source can be read completely again |

Loop read failures retain `read failed: loop status unavailable` and append
one fixed safe cause when known: `command failed`, `invalid JSON`,
`selected loop missing`, `unsupported cadence`, or `future timestamp`.
Other malformed loop data retains the generic message; GitHub read messages
are unchanged. Command output, exception details, loop IDs and scheduler
error text never supply diagnostic text. A cause change remains the same
`read/loop` episode, with its original deduplication and escalation timer;
an escalation names the cause observed at that tick.

## The collector read (#824)

The alarm makes no GitHub read of its own. Each tick it runs the war room
collector once, `python3 -I tools/collector/collect_factory.py read --repo
OWNER/NAME --fact merges --fact open_prs --since <tick - 60 min> --until
<tick> --base <base> --check <check> ...`, and reads the one
`openwiz.war-room.collector.read.v1` envelope it prints, as the
[collector contract](../collector/collector.v1.md) says for the stall alarm:
on demand, inside the tick's read budget, never from a snapshot. Only the
CloudRoom loop status stays the alarm's own read.

The collector is `tools/collector/collect_factory.py` beside this folder, or
the absolute path in `STALL_ALARM_COLLECTOR`. A copy of the alarm with no
checkout beside it (the embedded script below) must name one, or its GitHub
read fails. The envelope must be for this repository, hold exactly `merges`
and `open_prs`, both `known`, with the requested hour, base and checks;
anything else, an exit other than 0 or invalid JSON is a failed read, never
a quiet tick. `merges` counts every base, so only merges into `--base`
clear the no-merge alarm.

The collector applies the record rules: a fleet record is its first
nonblank line and matches a pull-request or any-item prefix of the fleet
skill's Records table (`PR_RECORD` here, which the collector imports).
Annotations after a recognized prefix are allowed, including on sent
records. Unknown kinds and incomplete record prefixes make `open_prs`
unavailable. A record's last edit is its action time; the latest record uses
that time, then comment ID. A verdict must start the comment body; the latest
verdict is by comment ID, matching the fleet. Plain discussion does not prove
an agent acted. No thread content is read. `UNKNOWN` mergeability does not
count as conflict-free. More than 100 comments or 100 checks on a PR, a
GraphQL error, a repeated JSON key, or a PR whose head and last commit
disagree make `open_prs` unavailable. Required checks default to `ci`;
`--check NAME` repeats to select another exact set. `--base` defaults to
`main` and must match the repository's default branch.

Two edges differ from the alarm's former own query. The hour is the
collector's half-open window `[tick - 60 min, tick)`, where the former search
counted merges strictly after the cutoff. A PR whose head moved during the
read now fails that tick's read instead of counting as not eligible. Search
freshness and live timing have not been measured. Loop list is a latest
snapshot: this cannot detect errors that arise and clear between ten-minute
ticks.

Fixture proof: `python3 -B -I tools/stall-alarm/test.py`. `Alarm` runs the
former cases through the real collector over synthetic GitHub answers;
`CollectorFixtures` reads the contract's
[`read-stall.json`](../collector/fixtures/collector/read-stall.json) and its
variants through a fake collector, and checks that no `gh` runs. The red
run, against the unchanged alarm, is
[`evidence/824-red-first.log`](evidence/824-red-first.log); the green run
is [`evidence/824-green.log`](evidence/824-green.log). CI runs this suite in
`war-room.yml`'s test step, on every pull request that touches this folder,
the war room (including the collector) or that workflow.

Fleet liveness uses the selected loop's configured `cron`: minute `*`,
`*/N`, a single minute, or comma-separated minutes, with `*` in the other
four fields. The largest gap (including the hour boundary) is its cadence.
The bounded [scheduler discovery](../../private/evidence/infra-stall-alarm/1466-skipped-tick.md)
found that the installed native scheduler advances its attempt timestamp and
counter when claiming a tick, before executing a script or dispatching an
agent. Empty successful script output is classified as `skipped` afterward;
skipping an agent wake therefore does not make that scheduler's attempt clock
stale. This is code-level discovery, not an observed live skipped tick; the
evidence records the status-read compatibility gap and deployment limits.
Other schedules or missing/malformed liveness fields fail the read visibly.
A run is overdue once its age exceeds that cadence plus `--fleet-grace`
seconds (default 600). A never-run loop gets the same allowance from the
alarm's first invocation with its persistent state, then alarms. The startup
time survives subsequent invocations and upgrades from the old state format.
Disabled loops alarm immediately. All use the existing once-per-episode,
30-minute escalation and silent recovery policy.
Run timestamps up to `--fleet-grace` seconds ahead of the check's clock
snapshot count as age zero, allowing runs that start during the status read
and bounded clock skew. Timestamps beyond that allowance fail the read.

## Failing-first proof for safe read causes (#1896)

Fixture evidence only; no live read or deployment. Before the implementation,
the issue's seven-row reproducer kept both quiet controls quiet and ended:

```text
AssertionError: proposed safe diagnostic context absent: nonzero-exit,invalid-json,missing-loop,invalid-cadence,future-over-boundary
```

The committed regression proof was run before the fix with:

```sh
python3 -B -I tools/stall-alarm/test.py Alarm.test_invalid_loop_liveness_fields_fail_loudly Alarm.test_loop_malformed_duplicate_and_missing_fields_fail_loudly Alarm.test_nonzero_read_recovers_and_rearms Alarm.test_run_during_read_or_within_future_grace_is_quiet Alarm.test_loop_cause_changes_preserve_stalls_dedup_and_escalation
```

Red output excerpt (the expected cause was absent):

```text
- ['ALARM: read failed: loop status unavailable']
+ ['ALARM: read failed: loop status unavailable: invalid JSON']
Ran 5 tests in 2.461s
FAILED (failures=12)
```

After the fix, the same command passes. The complete stall-alarm fixture
suite also passes (32 tests), covering refusal, quiet boundaries, private
upstream-output exclusion, both sources, recovery and escalation. This suite
is run locally; it is not currently invoked by the repository's CI workflow.

## State and time

Use a private persistent state path, outside the checkout, unique to the
repository, base, checks and fleet-loop ID. State is locked and atomically
replaced before lines are printed. A failed source preserves its previous
alarms and timers while the other source continues. An error's text changing
does not create a second stall. Recovery followed by recurrence does.
An edited sent record identifies a new action and gets a fresh escalation
timer, even if checks missed the interval when it was under 60 minutes old.

Each command gets at most eight seconds inside a shared 40-second read
budget, except the collector's read, which holds all of the tick's GitHub
reads and gets the rest of the budget; a timed-out command and its children
are stopped together. No clone,
fetch or build runs during a tick. Local state work follows that budget.
`--deadline` may lower the budget; `--now` supplies a controlled UTC clock
for proofs. The test runner measures complete fake invocations, including
process startup and persistence.

State loss rearms alarms and loses their escalation age. Unreadable or
unwritable state prints a failure; persistence cannot deduplicate its own
storage failure. Saving before printing also leaves a small crash window
between saving and output delivery. This is a local deduplication check,
not a durable delivery ledger. Keep its state when updating the script.

## How the orchestrator creates the loop

**Setup instructions for the orchestrator; installation and activation are
pending.** Run from a Local thread on the PC after merge. Use its
existing GitHub login and the full managed local CLI. No private endpoint
or new credential is needed. Substitute the repository, project and fleet
loop IDs in these examples, and set `PC_HOST` to the PC's CloudRoom host;
example IDs are synthetic.

First build the script from the reviewed checkout's root. It embeds the
alarm, keeps its state on the PC outside the checkout, and selects the
bundled CLI each tick so an app restart's changed mount path can be found.
If the app is unavailable, its status read fails visibly instead of using an
ambient CLI. It names that checkout's collector (#824), so the checkout must
stay on the PC at that path, updated only to reviewed commits; a missing
collector fails each tick's GitHub read visibly.

```sh
cat > /tmp/stall-alarm-check.sh <<'SH'
#!/bin/sh
if [ -z "${STALL_ALARM_ROOM_CLI:-}" ]; then
  for STALL_ALARM_ROOM_CLI in /tmp/.mount_*/resources/app.asar.unpacked/node_modules/bb-app/host-daemon/dist/room-cli; do
    [ -x "$STALL_ALARM_ROOM_CLI" ] && break
  done
fi
export STALL_ALARM_ROOM_CLI
SH
printf ': "${STALL_ALARM_COLLECTOR:=%s}"\nexport STALL_ALARM_COLLECTOR\n' \
  "$PWD/tools/collector/collect_factory.py" >> /tmp/stall-alarm-check.sh
cat >> /tmp/stall-alarm-check.sh <<'SH'
exec python3 - --repo example-owner/example-repo --fleet-loop loop_fixture \
  --state "${STALL_ALARM_STATE:-$HOME/.local/state/stall-alarm/example-owner-example-repo.json}" <<'PY'
SH
cat tools/stall-alarm/alarm.py >> /tmp/stall-alarm-check.sh
printf '\nPY\n' >> /tmp/stall-alarm-check.sh
```

Then, when installation is authorized, create the Local script-only loop
with the full managed CLI. These are the Local creation flags observed in
the bundled CLI's read-only help; no loop was created during this build.
Schedule this alarm independently of the fleet loop it monitors; never
invoke it only from that fleet loop, since a stopped fleet cannot check itself.

```sh
for STALL_INSTALL_CLI in /tmp/.mount_*/resources/app.asar.unpacked/node_modules/bb-app/host-daemon/dist/room-cli; do
  [ -x "$STALL_INSTALL_CLI" ] && break
done
"$STALL_INSTALL_CLI" loop create --project project_fixture \
  --name 'stall alarm example-owner/example-repo' --host "$PC_HOST" \
  --cron '*/10 * * * *' --timezone UTC --script-file /tmp/stall-alarm-check.sh
```

This Local creation uses the script-only mode, with no agent prompt or
Cloud execution flags. Exit 0 with no output is quiet; exit 1 means alarm
lines were emitted. Output is available for the orchestrator to route;
`JAKE:` lines identify the escalations for Jake. The script itself starts
no agent and sends no message. Setup must verify how Local run status,
retries and alarm delivery are handled. No live delivery is claimed.

The PC and its CloudRoom app must stay running. The detector retains its
40-second read budget and is measured against the ticket's 60-second target;
this does not assert a Cloud sandbox or Local scheduler timeout. Rebuild
and update the loop's stored script after an upgrade, retaining its state.
On the first successful check with the new default `ci`, the loader migrates
only the exact former default `web-build`, `rust`, `web-test` scope for the
same repository, fleet loop and base. It retains alarm ages, escalation flags
and the startup timestamp; older state without a startup timestamp gets one
as before. Every other scope mismatch is refused. Rebuild the stored script
to apply this migration; the repository change does not update a live loop.

**Switching repository** (#1279): the repository is only `--repo`. Rebuild
the script above with the new `--repo` and a state file named for it (the
default path already is), and replace the loop's stored script. A state file
kept for another repository is refused (`read failed`), so never reuse it.
