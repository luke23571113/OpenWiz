#!/usr/bin/env python3
"""CI3's tests moved to tools/war-room/test_ci3.py (#826). ci-bench.yml still runs this path,
so it runs the moved tests' Measure, Collect classes until MT8 (#827) repoints that workflow."""
from pathlib import Path
import subprocess
import sys

MOVED = Path(__file__).resolve().parents[1] / "war-room" / "test_ci3.py"
sys.exit(subprocess.run([sys.executable, "-I", str(MOVED), *(sys.argv[1:] or "Measure Collect".split())]).returncode)
