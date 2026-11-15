#!/usr/bin/env python3
"""#803 red stub: the naive versions the tests are written against."""
import re

SCHEMA = "openwiz.test-value.measure.v1"


class MeasureError(Exception):
    pass


def coverage_by_crate(report, packages):
    out = {}
    for entry in report["data"][0]["files"]:
        for name, root in packages:
            if entry["filename"].startswith(root + "/"):
                lines = entry["summary"]["lines"]
                got = out.setdefault(name, [0, 0])
                got[0] += lines["covered"]
                got[1] += lines["count"]
    return out


def parse_counts(text):
    m = re.search(r"test result: \w+\. (\d+) passed; (\d+) failed; (\d+) ignored", text)
    return {"passed": int(m.group(1)), "ignored": int(m.group(3))}


def compare(before, after):
    b = sum(c for c, _ in before["coverage"].values())
    a = sum(c for c, _ in after["coverage"].values())
    return ["drops: none" if a >= b else "drops: total"]
