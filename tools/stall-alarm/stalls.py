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


def stall_list(doc):
    """The stall list and the daily count at the flow fact's read point. Not built yet: nothing is known."""
    return {"schema": SCHEMA, "repository": None, "at": None, "stalls": None, "unknown": None,
            "daily": {"date": None, "count": None}}


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
