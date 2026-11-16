#!/usr/bin/env python3
"""CI3's loop every 3 days (#784): skeleton for the red run; no behaviour yet."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
from bench import Fail  # noqa: E402,F401


def check(now, read=None, record=None, authors=None):
    return ""


def read_before(path):
    return {"result": {}}


def main(argv=None):
    return 0


if __name__ == "__main__":
    sys.exit(main())
