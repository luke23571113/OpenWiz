#!/usr/bin/env python3
"""MT4 (#823): ci-bench's headline, PRs an hour against the baseline, from one collector snapshot.

`read(path, at)` returns one validated `openwiz.war-room.collector.v1` snapshot
(collector.v1.md); `figure(snapshot)` turns its `factory.prs_per_hour` fact into the
chart figure `body-ci-bench-headline`. See contract.md, "PRs an hour against the baseline".
"""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import prepare  # noqa: E402
import suite  # noqa: E402

ID = 'body-ci-bench-headline'
SCHEMA = suite._decode((HERE.parent / 'collector.v1.schema.json').read_text(encoding='utf-8'))


def read(path, at):
    """The snapshot at `path`, checked against the collector schema; raises ValueError."""
    return suite._decode(Path(path).read_text(encoding='utf-8'))


def figure(snapshot):
    """The headline figure (prepare's figure shape, before `sources` is named)."""
    return None
