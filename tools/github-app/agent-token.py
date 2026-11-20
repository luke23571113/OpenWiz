#!/usr/bin/env python3
"""GA3 (#1844) stub: the red run's helper. Does nothing yet."""
import os
import sys


def needs_refresh(now, expires_at):
    return False


def ask(argv, request, env, timeout=60):
    return ("ok", None)


if __name__ == "__main__":
    if sys.argv[1:2] == ["run"]:
        os.execvp(sys.argv[3], sys.argv[3:])
