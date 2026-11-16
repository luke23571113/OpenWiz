#!/usr/bin/env python3
"""CI3 moved to tools/war-room/ci3.py (#826). This path runs it, as a command or a module,
until MT8 (#827) retires tools/ci-bench/ and repoints the last callers."""
from pathlib import Path
import runpy

globals().update(runpy.run_path(str(Path(__file__).resolve().parents[1] / "war-room" / "ci3.py"), run_name=__name__))
