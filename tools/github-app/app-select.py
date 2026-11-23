#!/usr/bin/env python3
USAGE = """The pairing App selector (#2661): pick one App's state on the owner's machine and
hand the mint to the token service there, under contracts/token-service.v1.md.

  app-select.py mint   read one token-service request on stdin, choose one App
                       state directory, run `token-service.py mint --state-dir`
                       on it and pass its one JSON line and exit back unchanged

The owner points OPENWIZ_TOKEN_SERVICE at this file. Its owner-only (0600) config,
OPENWIZ_APP_SELECT_CONFIG or ~/.config/openwiz/app-select.json, holds exactly one of:

  {"state_dir": "/abs/state"}                named: that App, and only it
  {"candidates": ["/abs/a", "/abs/b"]}       resolved: the one App installed on
                                             every requested repository

A missing, unsafe or unclear config, or no App or more than one, is the contract's
refusal with one fixed sentence on stderr: no service call and no token. Resolving
asks each candidate App's own installation lookup with its JWT, signed by app.py
(the key goes to openssl as a file descriptor, never into this process). It never
calls the token endpoint and never touches the default state.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.parse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import app  # noqa: E402 -- the documented `python3 -I` drops this folder from sys.path

SERVICE = HERE / "token-service.py"
_spec = importlib.util.spec_from_file_location("token_service", SERVICE)
service = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(service)

CONFIG, CONFIG_LIMIT, BUDGET_S = "OPENWIZ_APP_SELECT_CONFIG", 4096, 55
SENTENCE = ("App selector refused: set OPENWIZ_APP_SELECT_CONFIG (default ~/.config/openwiz/app-select.json) "
            "to an owner-only (0600) file naming one App state as \"state_dir\", or listing \"candidates\" "
            "of which exactly one App is installed on every requested repository.")


def config_path():
    if os.environ.get(CONFIG):
        return Path(os.environ[CONFIG])
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", ""))
    return (xdg if xdg.is_absolute() else Path.home() / ".config") / "openwiz/app-select.json"


def app_state(value):
    app.require(isinstance(value, str))
    path = app.state_path(Path(value))
    os.close(app.app_directory(path))
    return path


def configured():
    path = config_path()
    app.require(path.is_absolute())
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        app.checked(fd)
        app.require(os.fstat(fd).st_size <= CONFIG_LIMIT)
        value = app.parse_json(os.read(fd, CONFIG_LIMIT + 1).decode("utf-8"))
    finally:
        os.close(fd)
    if set(value) == {"state_dir"}:
        return [app_state(value["state_dir"])], False
    app.require(set(value) == {"candidates"} and isinstance(value["candidates"], list) and value["candidates"])
    states = [app_state(item) for item in value["candidates"]]
    app.require(len(set(states)) == len(states))
    return states, True


def installed(state, repositories, base):
    directory = app.app_directory(state)
    try:
        config = app.parse_json(app.read_file(directory, "app.json", 1024))
        app.require(set(config) == {"app_id"})
        jwt = app.jwt(directory, config["app_id"])
    finally:
        os.close(directory)
    status, found = app.get(base, "/app", jwt)
    app.require(status == 200 and found.get("id") == config["app_id"])
    for name in repositories:
        status, held = app.get(base, "/repos/" + urllib.parse.quote(name, safe="/") + "/installation", jwt)
        app.require(status in (200, 404))
        if status == 404 or held.get("app_id") != config["app_id"]:
            return False
    return True


def refuse(code, sentence=True):
    if sentence:
        print(SENTENCE, file=sys.stderr)
    return service.answer(service.refusal(code), service.REFUSALS[code][0])


def main():
    started = time.monotonic()
    parser = argparse.ArgumentParser(description=USAGE, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("mint",))
    parser.add_argument("--api-base", default="https://api.github.com",
                        help="GitHub API; HTTP loopback accepted for synthetic tests only")
    args = parser.parse_args()
    base = app.api_base(args.api_base)
    data = sys.stdin.buffer.read(service.REQUEST_LIMIT + 1)
    try:
        states, resolve = configured()
    except Exception:
        return refuse("unavailable")
    if resolve:
        try:
            request = service.request_of(data)
        except service.Refused:
            return refuse("usage", sentence=False)
        repositories = request["repositories"]
        if len({name.split("/")[0].lower() for name in repositories}) != 1:
            return refuse("one-owner", sentence=False)
        try:
            states = [state for state in states if installed(state, repositories, base)]
        except Exception:
            return refuse("unavailable")
        if len(states) != 1:
            return refuse("not-installed" if not states else "unavailable")
    try:
        done = subprocess.run([sys.executable, "-I", str(SERVICE), "mint", "--state-dir", str(states[0]),
                               "--api-base", base], input=data, stdout=subprocess.PIPE,
                              timeout=max(1, BUDGET_S - (time.monotonic() - started)))
    except (OSError, subprocess.TimeoutExpired):
        return service.answer(service.refusal("unavailable"), 1)
    sys.stdout.buffer.write(done.stdout)
    sys.stdout.flush()
    return done.returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        # SECURITY: never a traceback: it could carry a request, a path or a provider body.
        sys.exit(service.answer(service.refusal("unavailable"), 1))
