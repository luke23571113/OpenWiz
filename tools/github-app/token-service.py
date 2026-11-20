#!/usr/bin/env python3
"""Skeleton for the red run: start and stop only; every mint is unavailable."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import app  # noqa: E402


def main():
    parser = app.arguments(__doc__)
    parser.add_argument("command", choices=("mint", "start", "stop"))
    args = parser.parse_args()
    folder = app.state_path(args.state_dir) / "service/token-service"
    if args.command == "start":
        folder.mkdir(mode=0o700, exist_ok=True)
        (folder / "started").touch(mode=0o600)
        return 0
    if args.command == "stop":
        (folder / "started").unlink(missing_ok=True)
        return 0
    print(json.dumps({"schema": "openwiz.token-service.v1", "kind": "refusal", "refusal": "unavailable",
                      "message": "Token refused: the service cannot read its App state or reach GitHub."}))
    return 1


if __name__ == "__main__":
    sys.exit(main())
