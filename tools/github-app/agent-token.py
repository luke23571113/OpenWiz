#!/usr/bin/env python3
"""The agent helper (GA3, #1844): an openwiz[bot] token for gh and git.

It follows contracts/token-service.v1.md. It asks the owner's token service for
an installation token, keeps it in a private file, hands it to gh as GH_TOKEN in
one child's environment and to git through a credential helper that reads that
file, refreshes it with 300 seconds or less left, and falls back to the owner's
GitHub login with one standard-error note. It never asks for, reads or holds the
App's key, and never prints, logs or passes a token as an argument.

    agent-token.py start --requester LABEL --repository OWNER/NAME... [--read]
    agent-token.py run -- COMMAND [ARG...]
    agent-token.py credential get        (git's credential helper; run sets it)

With OPENWIZ_TOKEN_SERVICE unset or empty, each command changes nothing and
prints nothing: run runs COMMAND exactly as today.
"""
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCHEMA = "openwiz.token-service.v1"
WRITE = {"metadata": "read", "contents": "write", "issues": "write",
         "pull_requests": "write", "checks": "read", "actions": "read"}
READ = {name: "read" for name in WRITE}
REFUSALS = {"usage": 2, "one-owner": 2, "not-installed": 3, "permission": 5,
            "github": 5, "expiry": 5, "unavailable": 1}
REFRESH_AT_S, MAX_LIFETIME_S, TIMEOUT_S = 300, 3900, 60
NOTE = "openwiz: no openwiz[bot] token ({}); using the owner's GitHub account\n"
REQUESTER = re.compile(r"[a-z][a-z0-9-]{0,63}")
REPOSITORY = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+")
TOKEN = re.compile(r"[A-Za-z0-9._~+/-]+=*")
GIT_HELPER_KEY = "credential.https://github.com.helper"


class Refused(Exception):
    """A local usage error: one line on stderr and exit 2, before any call."""


def needs_refresh(now, expires_at):
    """The contract's refresh rule: ask again at 300 seconds or less left."""
    return expires_at - now <= REFRESH_AT_S


def _no_repeats(pairs):
    if len({key for key, _ in pairs}) != len(pairs):
        raise ValueError("repeated key")
    return dict(pairs)


def _parse(raw):
    try:
        return json.loads(raw.decode("utf-8").strip(), object_pairs_hook=_no_repeats)
    except ValueError:
        return None


def ask(argv, request, env, timeout=TIMEOUT_S):
    """One service call: (None, answer) on exit 0, else (reason, None).

    The answer is read from a pipe and never echoed. The call's standard error
    is discarded, so no service or pairing text reaches the agent's terminal.
    """
    try:
        done = subprocess.run(argv, input=request, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, env=env, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return "unreachable", None
    message = _parse(done.stdout)
    if done.returncode == 0:
        return None, message
    if (isinstance(message, dict) and set(message) == {"schema", "kind", "refusal", "message"}
            and message["schema"] == SCHEMA and message["kind"] == "refusal"
            and isinstance(message["refusal"], str)
            and REFUSALS.get(message["refusal"]) == done.returncode
            and isinstance(message["message"], str)
            and message["message"].startswith("Token refused: ")):
        return message["refusal"], None
    return ("bad-answer" if isinstance(message, dict) else "unreachable"), None


def check_answer(message, wanted, now):
    """(token, expires_at), or None unless the answer is exactly the request's scope."""
    if not (isinstance(message, dict) and set(message) == {
            "schema", "kind", "token", "expires_at", "repositories", "permissions"}):
        return None
    expires_at = message["expires_at"]
    if (message["schema"] != SCHEMA or message["kind"] != "answer"
            or not isinstance(message["token"], str) or not TOKEN.fullmatch(message["token"])
            or type(expires_at) is not int
            or not REFRESH_AT_S < expires_at - now <= MAX_LIFETIME_S
            or message["repositories"] != wanted["repositories"]
            or message["permissions"] != wanted["permissions"]):
        return None
    return message["token"], expires_at


def route(env):
    """(None, argv) for the configured route, or (reason, None) when it is off or unusable."""
    service = env.get("OPENWIZ_TOKEN_SERVICE", "")
    if not service.startswith("/") or any(c in service for c in "'\n\r\0"):
        return "unreachable", None  # never run a path the quotes cannot hold
    if env.get("OPENWIZ_TOKEN_SERVICE_ROUTE") == "pairing":
        if env.get("OPENWIZ_TOKEN_SERVICE_READBACK") != "passed":
            return "pairing-off", None  # GA5's read-back gates the cloud route
        return None, ["room-cli", "mac", "run", "--stdin", f"python3 -I '{service}' mint"]
    if env.get("OPENWIZ_TOKEN_SERVICE_ROUTE") == "local":
        return None, ["python3", "-I", service, "mint"]
    return "unreachable", None


def mint(argv, wanted, env):
    """(None, token, expires_at) or (reason, None, None): one request, one checked answer."""
    request = json.dumps({"schema": SCHEMA, "kind": "request", **wanted}).encode() + b"\n"
    call_env = {k: v for k, v in env.items() if k != "GH_TOKEN"}
    now = int(time.time())
    reason, message = ask(argv, request, call_env)
    if reason:
        return reason, None, None
    got = check_answer(message, wanted, now)
    return ("bad-answer", None, None) if got is None else (None, *got)


def private_dir(env, create):
    """The 0700 directory outside every Git working tree that holds the token file."""
    raw = env.get("OPENWIZ_AGENT_TOKEN_DIR") or ""
    if not raw:
        runtime = env.get("XDG_RUNTIME_DIR", "")
        raw = (os.path.join(runtime, "openwiz-agent-token") if runtime.startswith("/")
               else os.path.join(str(Path.home()), ".cache", "openwiz-agent-token"))
    path = Path(raw)
    if not path.is_absolute():
        raise Refused("the private token directory must be an absolute path")
    for parent in (path, *path.parents):
        if (parent / ".git").exists():
            raise Refused("the private token directory must be outside every Git working tree")
    if create and not path.exists():
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.mkdir(mode=0o700)
    if path.exists():
        info = os.lstat(path)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077):
            raise Refused("the private token directory must be a 0700 directory you own")
    return path


def _read(path):
    try:
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid():
            return None
        return _parse(path.read_bytes())
    except OSError:
        return None


def _write(path, value):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")  # 0600 from mkstemp
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(value, handle)
        os.replace(name, path)
    except BaseException:
        os.unlink(name)
        raise


def held_token(directory, wanted, now):
    """The private file's token, while it covers exactly this request and is not due."""
    held = _read(directory / "token.json")
    if not isinstance(held, dict) or not isinstance(held.get("token"), str):
        return None
    if (type(held.get("expires_at")) is not int or needs_refresh(now, held["expires_at"])
            or held.get("repositories") != wanted["repositories"]
            or held.get("permissions") != wanted["permissions"]):
        return None
    return held["token"]


def token_for_run(directory, wanted, env):
    """The token to hand over, or None after the run's one fallback note."""
    reason, argv = route(env)
    if not reason:
        token = held_token(directory, wanted, int(time.time()))
        if token:
            return token
        reason, token, expires_at = mint(argv, wanted, env)
    if reason:
        (directory / "token.json").unlink(missing_ok=True)
        sys.stderr.write(NOTE.format(reason))
        return None
    _write(directory / "token.json", {"token": token, "expires_at": expires_at, **wanted})
    return token


def configured(env):
    return bool(env.get("OPENWIZ_TOKEN_SERVICE"))


def start(args, env):
    """Record the request and get the first token (or fall back)."""
    wanted = {"requester": None, "repositories": [], "permissions": WRITE}
    while args:
        flag = args.pop(0)
        if flag == "--read":
            wanted["permissions"] = READ
        elif flag in ("--requester", "--repository") and args:
            value = args.pop(0)
            if flag == "--requester":
                wanted["requester"] = value
            else:
                wanted["repositories"].append(value)
        else:
            raise Refused("usage: start --requester LABEL --repository OWNER/NAME... [--read]")
    if not (wanted["requester"] and REQUESTER.fullmatch(wanted["requester"])):
        raise Refused("--requester is a short lowercase label, such as builder-1844")
    repositories = wanted["repositories"]
    if (not repositories or len(set(map(str.lower, repositories))) != len(repositories)
            or not all(REPOSITORY.fullmatch(r) for r in repositories)
            or len({r.split("/")[0].lower() for r in repositories}) != 1):
        raise Refused("--repository is OWNER/NAME, at least one, each once, all of one owner")
    if not configured(env):
        return 0
    directory = private_dir(env, create=True)
    _write(directory / "request.json", wanted)
    token_for_run(directory, wanted, env)
    return 0


def run(args, env):
    """Run COMMAND with the token in its own environment, or as the owner after the note."""
    if args[:1] == ["--"]:
        args = args[1:]
    if not args:
        raise Refused("usage: run -- COMMAND [ARG...]")
    child = dict(env)
    if configured(env):
        directory = private_dir(env, create=False)
        wanted = _read(directory / "request.json")
        if not isinstance(wanted, dict) or set(wanted) != {"requester", "repositories", "permissions"}:
            raise Refused("no request recorded: run start first")
        old = _read(directory / "token.json")
        token = token_for_run(directory, wanted, env)
        if token:
            child["GH_TOKEN"] = token
            helper = f"!{shlex.quote(sys.executable)} -I {shlex.quote(os.path.abspath(__file__))} credential"
            count = int(child.get("GIT_CONFIG_COUNT", "0") or "0")
            for offset, value in enumerate(("", helper)):  # "" resets git's helper list first
                child[f"GIT_CONFIG_KEY_{count + offset}"] = GIT_HELPER_KEY
                child[f"GIT_CONFIG_VALUE_{count + offset}"] = value
            child["GIT_CONFIG_COUNT"] = str(count + 2)
        elif isinstance(old, dict) and child.get("GH_TOKEN") == old.get("token"):
            del child["GH_TOKEN"]  # never hand on the App token a failed refresh replaced
    try:
        os.execvpe(args[0], args, child)
    except OSError:
        raise Refused("cannot run the command")


def credential(args, env):
    """git's credential helper: answer `get` for https://github.com from the private file."""
    if args != ["get"] or not configured(env):
        return 0
    fields = dict(line.split("=", 1) for line in sys.stdin.read().splitlines() if "=" in line)
    if fields.get("protocol") != "https" or fields.get("host") != "github.com":
        return 0
    held = _read(private_dir(env, create=False) / "token.json")
    if (isinstance(held, dict) and isinstance(held.get("token"), str)
            and TOKEN.fullmatch(held["token"]) and type(held.get("expires_at")) is int
            and held["expires_at"] > time.time()):
        sys.stdout.write(f"username=x-access-token\npassword={held['token']}\n")
    return 0


def main(argv):
    commands = {"start": start, "run": run, "credential": credential}
    try:
        if not argv or argv[0] not in commands:
            raise Refused("usage: agent-token.py start|run|credential ...")
        return commands[argv[0]](list(argv[1:]), dict(os.environ))
    except Refused as error:
        sys.stderr.write(f"openwiz: agent-token: {error}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
