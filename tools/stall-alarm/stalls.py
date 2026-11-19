#!/usr/bin/env python3
"""FM3 (#1171): one stall rule over the collector's `flow` progress facts.

A claimed, unmerged ticket with no progress (commit, record, CI result or
verdict) for 30 minutes is a stall, tagged with one cause. Reads one collector
snapshot or read envelope (tools/collector/collector.v1.md); reads nothing else.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys

SCHEMA = "openwiz.stall-alarm.stalls.v1"
DOCUMENTS = ("openwiz.war-room.collector.v1", "openwiz.war-room.collector.read.v1")
STALL = timedelta(minutes=30)
CAUSES = ("ci", "jake", "limit", "stuck", "unknown")
# launch-fleet's Records table: the kinds that hand a ticket to a person, or to a usage limit.
JAKE = ("asked the orchestrator", "told the user", "parked", "needs approval")
LIMIT = ("builder fallback due",)
TIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ")


class Invalid(Exception):
    pass


def require(condition, why):
    if not condition:
        raise Invalid(why)


def when(text):
    require(isinstance(text, str) and TIME.fullmatch(text), "invalid time")
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def stamp(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def maybe(text):
    return None if text is None else when(text)


def cause(progress):
    """One cause from the fixed list. A fact the snapshot lacks leaves it unknown."""
    if progress["ci_pending"] is True:
        return "ci"
    if "last_record" not in progress:  # a flow fact written before the record kind existed
        return "unknown"
    record = progress["last_record"]
    if record in JAKE:
        return "jake"
    if record in LIMIT:
        return "limit"
    return "stuck" if progress["ci_pending"] is False else "unknown"


def gaps(progress):
    """The ticket's dated past stalls, or None when its history is unknown."""
    items = progress.get("gaps")
    if items is None:
        return None
    require(isinstance(items, list), "invalid gaps")
    out = []
    for gap in items:
        require(isinstance(gap, dict) and set(gap) == {"from", "until"}, "invalid gap")
        start, end = when(gap["from"]), when(gap["until"])
        require(end - start >= STALL, "a gap shorter than a stall")
        out.append(start)
    return out


def stall_list(doc):
    """The stall list and the daily count at the flow fact's read point."""
    require(isinstance(doc, dict) and doc.get("schema") in DOCUMENTS, "not a collector document")
    fact = (doc.get("factory") or {}).get("flow")
    out = {"schema": SCHEMA, "repository": doc.get("repository"), "at": None,
           "stalls": None, "unknown": None, "daily": {"date": None, "count": None}}
    if fact is None or fact.get("value") is None:
        return out  # no flow fact, or an unavailable one: the whole list is unknown, never empty
    at = when(fact["point"])
    day = at.replace(hour=0, minute=0, second=0)
    out["at"], out["daily"]["date"] = stamp(at), at.date().isoformat()
    stalls, unknown, starts, history = [], [], [], True
    for row in fact["value"]["tickets"]:
        progress = row["progress"]
        claimed, merged = maybe(row["claimed_at"]), maybe(row["merged_at"])
        if claimed is None or (merged is not None and merged < day):
            continue  # never started, or finished before the day
        past = gaps(progress) if progress["complete"] else None
        if past is None:
            history = False
        else:
            starts += [start + STALL for start in past]
        if row["state"] != "open" or merged is not None:
            if row["state"] == "unknown":
                unknown.append({"ticket": row["ticket"], "spec": row["spec"], "reason": "state"})
            continue
        last = maybe(progress["last_observed_at"])
        if last is not None and at - last < STALL:
            continue  # progress inside 30 minutes is never a stall, even on a partial history
        if last is None or not progress["complete"]:
            unknown.append({"ticket": row["ticket"], "spec": row["spec"], "reason": "progress"})
            continue
        starts.append(last + STALL)
        stalls.append({"ticket": row["ticket"], "spec": row["spec"], "pull_requests": row["pull_requests"],
                       "since": stamp(last), "minutes": int((at - last).total_seconds() // 60),
                       "cause": cause(progress)})
    stalls.sort(key=lambda s: (-s["minutes"], s["ticket"]))
    out["stalls"], out["unknown"] = stalls, unknown
    if history and not unknown:
        out["daily"]["count"] = sum(day <= start <= at for start in starts)
    return out


def main(argv):
    parser = argparse.ArgumentParser(description="The stall list and daily count from a collector document.")
    parser.add_argument("--input", required=True, type=Path, help="a collector snapshot or read envelope holding flow")
    args = parser.parse_args(argv)
    try:
        doc = json.loads(args.input.read_text(encoding="utf-8"))
        result = stall_list(doc)
    except (OSError, ValueError, Invalid, KeyError, TypeError, AttributeError) as e:
        print("stalls: invalid collector document (%s)" % (e if isinstance(e, Invalid) else type(e).__name__),
              file=sys.stderr)
        return 1
    print(json.dumps(result, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
