#!/usr/bin/env python3
"""The token service (GA2, #1841): mint one-hour openwiz[bot] installation tokens
on the owner's machine, under contracts/token-service.v1.md.

  token-service.py start   let agents mint (a fresh install is stopped)
  token-service.py stop    refuse every mint, like an unreachable service
  token-service.py mint    read one request on stdin, write one answer or
                           refusal as one JSON line on stdout

It listens on no port: agents run `mint` through the owner's machine pairing or
locally. Only this tool reads the App's key, <state>/service/app/private-key.pem,
and only to sign the App's JWT; the key and every token stay off the command
line, standard error and the mint log. The mint log is
<state>/service/token-service/mint-log.jsonl, owner-only, one line per request
and never a token. mint-token.py stays byte-identical to the copy WizSkills'
launch-fleet carries: this tool uses the same guards from app.py.
"""
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse

# The documented `python3 -I` drops this folder from sys.path: add exactly it.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import app  # noqa: E402

SCHEMA = "openwiz.token-service.v1"
REFUSALS = {
    "usage": (2, "the request is not one valid token-service request."),
    "one-owner": (2, "the repositories must share one owner."),
    "not-installed": (3, "a repository is not in the App's installation."),
    "permission": (5, "a permission is outside the App's."),
    "github": (5, "GitHub refused the exchange or granted a different scope."),
    "expiry": (5, "the minted token failed the expiry guards."),
    "unavailable": (1, "the service cannot read its App state or reach GitHub."),
}
LEVEL = {"read": 0, "write": 1}
REQUESTER = re.compile(r"[a-z][a-z0-9-]{0,63}")
PERMISSION = re.compile(r"[a-z][a-z_]*")
TOKEN = re.compile(r"[A-Za-z0-9._~+/-]+=*")
# A handed-over token has more than REFRESH and at most LONGEST seconds left (the pin).
REFRESH, LONGEST = 300, 3900
REQUEST_LIMIT = 64 * 1024
FOLDER, STARTED, LOG = "token-service", "started", "mint-log.jsonl"
STOPPED = "Token service stopped: the owner has not started it."


class Refused(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def check(condition, code):
    if not condition:
        raise Refused(code)


def request_of(data):
    """The one valid request in DATA, or a usage refusal. Nothing in it is trusted before this."""
    try:
        check(len(data) <= REQUEST_LIMIT, "usage")
        value = app.parse_json(data.decode("utf-8"))  # a repeated key at any depth is refused
    except (ValueError, RecursionError):
        raise Refused("usage") from None
    check(set(value) == {"schema", "kind", "requester", "repositories", "permissions"}, "usage")
    check(value["schema"] == SCHEMA and value["kind"] == "request", "usage")
    requester, repositories, permissions = value["requester"], value["repositories"], value["permissions"]
    check(isinstance(requester, str) and REQUESTER.fullmatch(requester) is not None, "usage")
    check(isinstance(repositories, list) and repositories, "usage")
    for name in repositories:
        check(isinstance(name, str) and app.REPOSITORY.fullmatch(name) is not None
              and name.split("/")[1] not in (".", ".."), "usage")
    check(len({name.lower() for name in repositories}) == len(repositories), "usage")
    check(isinstance(permissions, dict) and permissions, "usage")
    for name, level in permissions.items():
        check(PERMISSION.fullmatch(name) is not None and isinstance(level, str) and level in LEVEL, "usage")
    return value


def folder(state, create=False):
    """The service's own owner-only folder, <state>/service/token-service, as a descriptor."""
    fd = os.open(state, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        app.checked(fd, directory=True)
        for component in ("service", FOLDER):
            if create:
                try:
                    os.mkdir(component, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
            app.checked(fd, directory=True)
        return fd
    except Exception:
        os.close(fd)
        raise


def started(directory):
    try:
        fd = os.open(STARTED, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    except OSError:
        return False
    try:
        app.checked(fd)
        return True
    except ValueError:
        return False
    finally:
        os.close(fd)


def mint(api, request, now):
    """(token, expires_at) for exactly REQUEST, or a refusal, checked in the contract's order."""
    repositories, permissions = request["repositories"], request["permissions"]
    owners = {name.split("/")[0].lower() for name in repositories}
    check(len(owners) == 1, "one-owner")
    try:
        setting = app.mode()
        directory = app.app_directory(app.state_path(api["state"]))
        try:
            config = app.parse_json(app.read_file(directory, "app.json", 1024))
            app.require(set(config) == {"app_id"})
            jwt = app.jwt(directory, config["app_id"])  # the key reaches OpenSSL only by descriptor
        finally:
            os.close(directory)
    except Exception:
        raise Refused("unavailable") from None
    try:
        status, found = app.get(api["base"], "/app", jwt)
        check(status == 200 and found.get("id") == config["app_id"], "github")
        held = set()
        for name in repositories:
            path = "/repos/" + urllib.parse.quote(name, safe="/") + "/installation"
            status, installation = app.get(api["base"], path, jwt)
            check(status in (200, 404), "github")
            check(status == 200 and installation.get("app_id") == config["app_id"]
                  and installation.get("repository_selection") == "selected"
                  and type(installation.get("id")) is int and installation["id"] > 0, "not-installed")
            check(app.bound(setting, (found.get("owner") or {}).get("login"),
                            (installation.get("account") or {}).get("login"), [name]), "not-installed")
            held.add(installation["id"])
        check(len(held) == 1, "not-installed")
        for name, level in permissions.items():
            check(name in app.SERVICE and LEVEL[level] <= LEVEL[app.SERVICE[name]], "permission")
        result = app.post(api["base"], f"/app/installations/{held.pop()}/access_tokens",
                          {"repositories": [name.split("/")[1] for name in repositories],
                           "permissions": permissions}, jwt)
    except Refused:
        raise
    except urllib.error.HTTPError:
        raise Refused("github") from None
    except OSError:
        raise Refused("unavailable") from None
    except Exception:
        raise Refused("github") from None
    # Exactly the request: never a wider, narrower or other grant.
    token, listed = result.get("token"), result.get("repositories")
    check(result.get("permissions") == permissions and result.get("repository_selection") == "selected", "github")
    check(isinstance(listed, list) and all(isinstance(r, dict) and isinstance(r.get("full_name"), str)
                                           for r in listed), "github")
    check(sorted(r["full_name"].lower() for r in listed) == sorted(n.lower() for n in repositories), "github")
    check(isinstance(token, str) and TOKEN.fullmatch(token) is not None, "github")
    try:
        expires_at = int(datetime.fromisoformat(result["expires_at"].replace("Z", "+00:00")).timestamp())
    except Exception:
        raise Refused("github") from None
    check(REFRESH < expires_at - now <= LONGEST, "expiry")
    return token, expires_at


def serve(api, log, data):
    """(message, exit) for one request; the log line is written before any token is handed over."""
    now = time.time()
    line = {"schema": SCHEMA, "kind": "mint-log", "at": int(now), "requester": "-"}
    try:
        request = request_of(data)
        line.update(requester=request["requester"], repositories=request["repositories"])
        token, expires_at = mint(api, request, now)
        line.update(permissions=request["permissions"], outcome="minted", expires_at=expires_at)
        message = {"schema": SCHEMA, "kind": "answer", "token": token, "expires_at": expires_at,
                   "repositories": request["repositories"], "permissions": request["permissions"]}
    except Refused as refused:
        line["outcome"] = refused.code
        message = refusal(refused.code)
    except Exception:
        # Anything unforeseen is unavailable, and still logged.
        line["outcome"] = "unavailable"
        message = refusal("unavailable")
    entry = (json.dumps(line) + "\n").encode()
    app.require(os.write(log, entry) == len(entry))
    os.fsync(log)
    return message, REFUSALS[message["refusal"]][0] if message["kind"] == "refusal" else 0


def refusal(code):
    return {"schema": SCHEMA, "kind": "refusal", "refusal": code, "message": "Token refused: " + REFUSALS[code][1]}


def main():
    parser = app.arguments(__doc__)
    parser.add_argument("command", choices=("mint", "start", "stop"))
    args = parser.parse_args()
    if args.command != "mint":
        directory = folder(app.state_path(args.state_dir), create=True)
        try:
            if args.command == "start":
                fd = os.open(STARTED, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=directory)
                try:
                    app.checked(fd)
                finally:
                    os.close(fd)
            else:
                try:
                    os.unlink(STARTED, dir_fd=directory)
                except FileNotFoundError:
                    pass
        finally:
            os.close(directory)
        print("Token service started." if args.command == "start" else "Token service stopped.")
        return 0
    try:
        directory = folder(app.state_path(args.state_dir))
    except FileNotFoundError:
        directory = None
    except Exception:
        return answer(refusal("unavailable"), 1)
    try:
        if directory is None or not started(directory):
            print(STOPPED, file=sys.stderr)
            return 1
        try:
            log = os.open(LOG, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        except OSError:
            return answer(refusal("unavailable"), 1)
        try:
            app.checked(log)
            api = {"state": args.state_dir, "base": app.api_base(args.api_base)}
            return answer(*serve(api, log, sys.stdin.buffer.read(REQUEST_LIMIT + 1)))
        finally:
            os.close(log)
    finally:
        if directory is not None:
            os.close(directory)


def answer(message, code):
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        # Never a traceback: it could carry a request, a path or a provider body.
        sys.exit(answer(refusal("unavailable"), 1))
