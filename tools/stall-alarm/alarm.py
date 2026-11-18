#!/usr/bin/env python3
"""#567: a bounded, read-only factory check; only local alarm state is written."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time


SHA = r"[0-9a-f]{40}"
# #824: the GitHub facts are the war-room collector's on-demand read
# (tools/collector/collector.v1.md): `open_prs`, and `merges` for the hour.
READ = "openwiz.war-room.collector.read.v1"
SENT = ("findings sent", "CI failure sent", "re-check sent")
# Only the pull-request and any-item rows of launch-fleet's Records table.
# Match the record prefix, as fleet.sh's kind() does; annotations may follow.
# Unknown or incomplete fleet text cannot prove an agent acted. The
# collector's open_prs read refuses any other record with this rule.
PR_RECORD = re.compile(
    rf"launch-fleet: (?:review (?:starting|withdrawn) {SHA}"
    rf"|(?:review started|review told again|re-check sent) {SHA}"
    # Public records omit the thread; a present legacy suffix must be complete.
    rf"(?:, thread [A-Za-z0-9_-]+|(?!,))"
    rf"|review given up {SHA}: .+"
    rf"|review (?:refused|failed) {SHA}(?:, thread [A-Za-z0-9_-]+)?: .+"
    rf"|(?:CI failure sent|findings sent) {SHA}"
    rf"|merge (?:queued|blocked) {SHA}: .+|look: .+)(?=\b|$)"
)


class ReadError(Exception):
    pass


def require(condition):
    if not condition:
        raise ReadError("unexpected response shape")


def integer(value):
    return type(value) is int and value >= 0


def no_repeats(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def invalid_constant(_):
    raise ReadError("non-JSON constant")


def decode(text):
    return json.loads(text, object_pairs_hook=no_repeats, parse_constant=invalid_constant)


def timestamp(value):
    require(isinstance(value, str))
    require(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", value) is not None)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class Reader:
    def __init__(self, seconds):
        self.end = time.monotonic() + seconds

    def read(self, args, whole=False):
        # Each command gets at most eight seconds; the collector's one read
        # (WHOLE) holds every GitHub read of the tick, so it gets the rest.
        remaining = self.end - time.monotonic()
        if remaining <= 0:
            raise ReadError("command failed")
        # A separate group lets a timed-out command and its own children be
        # stopped together, including a credential helper holding stdout open.
        try:
            proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                    start_new_session=True)
        except OSError:
            raise ReadError("command failed") from None
        try:
            out, _ = proc.communicate(timeout=remaining if whole else min(8, remaining))
        except BaseException as error:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
            if isinstance(error, subprocess.TimeoutExpired):
                raise ReadError("command failed") from None
            raise
        if proc.returncode != 0:
            raise ReadError("command failed")
        try:
            return decode(out.decode("utf-8"))
        except (ReadError, ValueError):
            raise ReadError("invalid JSON") from None


def loop_cadence(cron):
    # Fleet safety nets recur throughout every hour. Use the largest gap,
    # including the hour boundary, so offset/list schedules work too.
    require(isinstance(cron, str))
    fields = cron.split()
    require(len(fields) == 5 and fields[1:] == ["*"] * 4)
    minute = fields[0]
    if minute == "*":
        minutes = list(range(60))
    elif re.fullmatch(r"\*/[0-9]{1,2}", minute):
        step = int(minute[2:])
        require(1 <= step <= 60)
        minutes = list(range(0, 60, step))
    else:
        require(re.fullmatch(r"[0-9]{1,2}(?:,[0-9]{1,2})*", minute) is not None)
        minutes = sorted(set(map(int, minute.split(","))))
        require(all(0 <= value < 60 for value in minutes))
    return max(b - a for a, b in zip(minutes, minutes[1:] + [minutes[0] + 60])) * 60


def loop_stalls(reader, loop_id, now, started_at, grace):
    program = os.environ.get("STALL_ALARM_ROOM_CLI", "room-cli")
    require(program == "room-cli" or Path(program).is_absolute())
    answer = reader.read([program, "loop", "list", "--json"])
    require(isinstance(answer, dict) and isinstance(answer.get("automations"), list))
    loops = answer["automations"]
    require(all(isinstance(loop, dict) and isinstance(loop.get("id"), str) for loop in loops))
    found = [loop for loop in loops if loop["id"] == loop_id]
    if not found:
        raise ReadError("selected loop missing")
    require(len(found) == 1)
    loop = found[0]
    require("last_error" in loop and "last_run_at" in loop)
    require(loop["last_error"] is None or isinstance(loop["last_error"], str))
    require(type(loop.get("enabled")) is bool)
    try:
        max_age = loop_cadence(loop.get("cron")) + grace
    except ReadError:
        raise ReadError("unsupported cadence") from None
    last_run = timestamp(loop["last_run_at"]) if loop["last_run_at"] is not None else None
    # A run can start during the status read, after our clock snapshot.
    # Bound future skew by the configured grace and treat it as age zero.
    if last_run is not None and last_run > now + grace:
        raise ReadError("future timestamp")
    age = max(0, now - last_run) if last_run is not None else None
    if not loop["enabled"]:
        return {"loop/disabled": "fleet loop disabled"}
    if loop["last_error"]:
        # Never print scheduler error text: it can contain private prompts.
        return {"loop/error": "fleet loop last run errored"}
    if last_run is None and now - started_at > max_age:
        return {"loop/never": "fleet loop never ran after startup grace"}
    if age is not None and age > max_age:
        return {"loop/stale": "fleet loop last run overdue"}
    return {}


def collector():
    configured = os.environ.get("STALL_ALARM_COLLECTOR")
    if configured:
        require(Path(configured).is_absolute())
        return configured
    # An embedded script has no checkout of its own: it must name one.
    here = globals().get("__file__")
    require(isinstance(here, str) and Path(here).is_file())
    return str(Path(here).resolve().parents[1] / "collector" / "collect_factory.py")


def exact(value, *keys):
    """VALUE is an object with exactly KEYS (the contract's objects are closed)."""
    require(isinstance(value, dict) and set(value) == set(keys))
    return value


def known(facts, name):
    fact = exact(facts[name], "fact", "state", "read", "point", "window", "fresh_until", "freshness",
                 "source", "evidence", "prerequisites", "value")
    require(fact["fact"] == name and fact["state"] == "known")
    return fact["value"]


def inspect_pull(pull, now, base, checks):
    exact(pull, "number", "draft", "base", "head", "mergeable", "rollup", "checks", "verdict", "record")
    number, head = pull["number"], pull["head"]
    require(integer(number) and number > 0)
    require(type(pull["draft"]) is bool and isinstance(pull["base"], str))
    require(isinstance(head, str) and re.fullmatch(SHA, head) is not None)
    require(pull["mergeable"] in ("MERGEABLE", "CONFLICTING", "UNKNOWN"))
    # The latest of the PR's fleet record and its verdict, by last edit, then
    # comment ID: only a sent record at the current head can be idle.
    latest = []
    for kind, field in (("record", "kind"), ("verdict", "verdict")):
        item = pull[kind]
        if item is not None:
            exact(item, field, "head", "comment_id", "at")
            require(integer(item["comment_id"]) and isinstance(item[field], str))
            require(item["head"] is None or isinstance(item["head"], str))
            latest.append((timestamp(item["at"]), item["comment_id"], kind, item))
    idle = {}
    if latest:
        edited, ident, kind, item = max(latest, key=lambda entry: entry[:2])
        if kind == "record" and item["kind"] in SENT and item["head"] == head and now - edited >= 3600:
            idle[f"github/idle/{number}/{ident}/{iso(edited)}"] = f"idle #{number}: 60 minutes after {item['kind']}"
    rollup, results = pull["rollup"], pull["checks"]
    require(rollup in ("success", "failure", "pending", None) and isinstance(results, list))
    require(all(isinstance(exact(c, "name", "result")["name"], str) and isinstance(c["result"], str)
                for c in results))
    green = rollup == "success" and all(
        any(c["name"] == check and c["result"] == "success" for c in results) for check in checks)
    verdict = pull["verdict"]
    approved = verdict is not None and verdict["verdict"] == "APPROVE" and verdict["head"] == head
    eligible = (not pull["draft"] and pull["base"] == base
                and pull["mergeable"] == "MERGEABLE" and approved and green)
    return idle, eligible


def github_stalls(reader, args, now):
    since, until = iso(now - 3600), iso(now)
    command = [sys.executable, "-I", collector(), "read", "--repo", args.repo,
               "--fact", "merges", "--fact", "open_prs", "--since", since, "--until", until,
               "--base", args.base, *[part for check in args.check for part in ("--check", check)]]
    if args.now:
        command += ["--now", until]
    answer = reader.read(command, whole=True)
    exact(answer, "schema", "repository", "requested_at", "factory", "ci")
    require(answer["schema"] == READ and answer["repository"] == args.repo and answer["ci"] == {})
    facts = answer["factory"]
    exact(facts, "merges", "open_prs")
    merges, value = known(facts, "merges"), known(facts, "open_prs")
    require(facts["merges"]["window"] == {"since": since, "until": until, "timezone": "UTC"})
    require(isinstance(exact(merges, "pull_requests")["pull_requests"], list))
    recent_merge = False
    for merged in merges["pull_requests"]:
        exact(merged, "number", "merged_at", "base", "tickets", "direction")
        require(integer(merged["number"]) and isinstance(merged["base"], str))
        require(timestamp(since) <= timestamp(merged["merged_at"]) < timestamp(until))
        recent_merge = recent_merge or merged["base"] == args.base
    exact(value, "default_branch", "base", "checks", "pull_requests")
    require(value["default_branch"] == args.base)
    require(value["base"] == args.base and value["checks"] == args.check)
    require(isinstance(value["pull_requests"], list))
    stalls, eligible = {}, False
    for pull in value["pull_requests"]:
        idle, ready = inspect_pull(pull, now, args.base, args.check)
        stalls.update(idle)
        eligible = eligible or ready
    if eligible and not recent_merge:
        stalls["github/merges"] = "no merges for 60 minutes with an approved green conflict-free pull request"
    return stalls


def load_state(path, scope, now):
    if not path.exists():
        return {"version": 1, "scope": scope, "alarms": {}, "started_at": now}
    state = decode(path.read_text())
    require(isinstance(state, dict) and set(state) in (
        {"version", "scope", "alarms"}, {"version", "scope", "alarms", "started_at"}))
    # Upgrade existing state without losing deduplication/escalation timers.
    state.setdefault("started_at", now)
    require(type(state["started_at"]) in (int, float) and 0 <= state["started_at"] <= now)
    # X5 renames the default required checks. Only that exact upgrade for
    # this same repo/loop/base may reuse state; never rearm existing alarms.
    old_scope = {**scope, "checks": ["web-build", "rust", "web-test"]}
    if scope["checks"] == ["ci"] and state["scope"] == old_scope:
        state["scope"] = scope
    require(type(state["version"]) is int and state["version"] == 1 and state["scope"] == scope)
    require(isinstance(state["alarms"], dict))
    for key, alarm in state["alarms"].items():
        require(key.startswith(("loop/", "github/", "read/")))
        require(isinstance(alarm, dict) and set(alarm) == {"since", "escalated"})
        require(type(alarm["since"]) in (int, float) and alarm["since"] >= 0)
        require(type(alarm["escalated"]) is bool)
    return state


def save_state(path, state):
    descriptor, temporary = tempfile.mkstemp(prefix=".alarm-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as out:
            json.dump(state, out)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--fleet-loop", required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--base", default="main")
    parser.add_argument("--check", action="append", help="required CI check, repeatable; default: ci")
    parser.add_argument("--now", help="controlled UTC clock for fixture proofs")
    parser.add_argument("--fleet-grace", type=int, default=600,
                        help="seconds beyond the fleet cadence before overdue/never-run alarms (default: 600)")
    parser.add_argument("--deadline", type=float, default=40, help="whole external-read budget, at most 40 seconds")
    args = parser.parse_args()
    require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo) is not None)
    require(re.fullmatch(r"[A-Za-z0-9_./-]+", args.base) is not None)
    require(0 < args.deadline <= 40)
    require(args.fleet_grace >= 0)
    args.check = args.check or ["ci"]
    now = timestamp(args.now) if args.now else time.time()
    reader = Reader(args.deadline)
    scope = {"repo": args.repo, "loop": args.fleet_loop, "base": args.base, "checks": args.check}
    args.state.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = os.open(str(args.state) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = load_state(args.state, scope, now)
        alarms, lines = state["alarms"], []
        for source, read in (("loop", lambda: loop_stalls(reader, args.fleet_loop, now,
                                                        state["started_at"], args.fleet_grace)),
                             ("github", lambda: github_stalls(reader, args, now))):
            try:
                current = read()
            except (ReadError, ValueError, KeyError, TypeError, IndexError, OSError, subprocess.TimeoutExpired) as error:
                # Keep the last known alarms on a failed read. Unknown is not
                # recovery, and cannot reset a 30-minute escalation timer.
                current = {f"read/{source}": f"read failed: {source} status unavailable"}
                # Only fixed safe causes may reach output, never upstream text.
                if source == "loop" and str(error) in (
                        "command failed", "invalid JSON", "selected loop missing",
                        "unsupported cadence", "future timestamp"):
                    current[f"read/{source}"] += ": " + str(error)
            else:
                alarms.pop(f"read/{source}", None)
                for key in list(alarms):
                    if key.startswith(source + "/") and key not in current:
                        del alarms[key]
            for key, message in current.items():
                if key not in alarms:
                    alarms[key] = {"since": now, "escalated": False}
                    lines.append("ALARM: " + message)
                elif not alarms[key]["escalated"] and now - alarms[key]["since"] >= 1800:
                    alarms[key]["escalated"] = True
                    lines.append("JAKE: " + message + "; still open after 30 minutes")
        # Record before emitting, so subsequent ticks do not repeat an alarm.
        save_state(args.state, state)
        for line in lines:
            print(line)
        return 1 if lines else 0
    finally:
        os.close(lock)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ReadError, ValueError, KeyError, TypeError, OSError):
        print("ALARM: read failed: alarm configuration or local state unavailable")
        sys.exit(1)
