#!/usr/bin/env python3
"""The agent helper (GA3, #1844): an openwiz[bot] token for gh and git.

It follows contracts/token-service.v1.md. It asks the owner's token service for
an installation token, keeps it in a private file, hands it to gh as GH_TOKEN in
one child's environment and to git through a credential helper that reads that
file, refreshes it with 300 seconds or less left, and falls back to the owner's
GitHub login with one standard-error note. It never asks for, reads or holds the
App's key, and never prints, logs or passes a token as an argument.

    agent-token.py start REQUEST
    agent-token.py run REQUEST -- COMMAND [ARG...]
    REQUEST: --requester LABEL --repository OWNER/NAME... [--read]

Each request has its own cache file, so agents on one account never share or
replace each other's tokens. Each run copies its token into a snapshot file
that lives only while COMMAND runs; gh gets it as GH_TOKEN and git through
`credential --snapshot`, which answers only git's own credential exchange.

With OPENWIZ_TOKEN_SERVICE unset or empty, each command changes nothing and
prints nothing: run runs COMMAND exactly as today.
"""
import hashlib
import json
import os
import re
import secrets
import shlex
import signal
import stat
import subprocess
import sys
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
REFUSAL_MESSAGE = re.compile(r"Token refused: [^\n]+\.")
GIT_HELPER_KEY = "credential.https://github.com.helper"
RUN_MARK, GIT_MARK = "OPENWIZ_AGENT_TOKEN_RUN", "OPENWIZ_AGENT_TOKEN_GIT_AT"
USAGE = ("agent-token.py start REQUEST | run REQUEST -- COMMAND [ARG...]; "
         "REQUEST is --requester LABEL --repository OWNER/NAME... [--read]")


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


def ask(argv, request, env):
    """One service call: (None, answer) on exit 0, else (reason, None).

    The answer is read from a pipe and never echoed. The call's standard error
    is discarded, so no service or pairing text reaches the agent's terminal.
    """
    try:
        done = subprocess.run(argv, input=request, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, env=env, timeout=TIMEOUT_S)
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
            and REFUSAL_MESSAGE.fullmatch(message["message"])):
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


class Private:
    """The 0700 directory, outside every Git working tree, that holds token files.

    Its path may not pass through a symlink, and every file operation goes
    through one descriptor opened on it, so no path swap can redirect a write.
    """

    def __init__(self, env, create):
        raw = env.get("OPENWIZ_AGENT_TOKEN_DIR") or ""
        if not raw:
            runtime = env.get("XDG_RUNTIME_DIR", "")
            raw = (os.path.join(runtime, "openwiz-agent-token") if runtime.startswith("/")
                   else os.path.join(str(Path.home()), ".cache", "openwiz-agent-token"))
        if not os.path.isabs(raw):
            raise Refused("the private token directory must be an absolute path")
        self.path = os.path.normpath(raw)
        parent = os.path.dirname(self.path)
        if os.path.realpath(parent) != parent or os.path.islink(self.path):
            raise Refused("the private token directory must not pass through a symlink")
        for above in (self.path, *Path(self.path).parents):
            if os.path.lexists(os.path.join(above, ".git")):
                raise Refused("the private token directory must be outside every Git working tree")
        if create:
            os.makedirs(parent, mode=0o700, exist_ok=True)
            try:
                os.mkdir(self.path, 0o700)
            except FileExistsError:
                pass
        try:
            self.fd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        except OSError:
            raise Refused("the private token directory must be a 0700 directory you own")
        info = os.fstat(self.fd)
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise Refused("the private token directory must be a 0700 directory you own")

    def read(self, name):
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=self.fd)
        except OSError:
            return None
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid():
                return None
            return _parse(handle.read())

    def write(self, name, value):
        temporary = f".tmp-{secrets.token_hex(8)}"
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,
                     dir_fd=self.fd)
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(value, handle)
            os.replace(temporary, name, src_dir_fd=self.fd, dst_dir_fd=self.fd)
        except BaseException:
            self.unlink(temporary)
            raise

    def unlink(self, name):
        try:
            os.unlink(name, dir_fd=self.fd)
        except FileNotFoundError:
            pass


def usable(held, now):
    """A token file's token, unless it is malformed or due for refresh."""
    if (isinstance(held, dict) and isinstance(held.get("token"), str)
            and TOKEN.fullmatch(held["token"]) and type(held.get("expires_at")) is int
            and not needs_refresh(now, held["expires_at"])):
        return held["token"]
    return None


def cache_name(wanted):
    """One cache file per requester and scope, so agents never share or replace each other's."""
    digest = hashlib.sha256(json.dumps(wanted, sort_keys=True).encode()).hexdigest()
    return f"token-{digest[:32]}.json"


def token_for(private, wanted, env):
    """(token, expires_at) to hand over, or (None, None) after the run's one fallback note."""
    name = cache_name(wanted)
    reason, argv = route(env)
    if not reason:
        held = private.read(name)
        if (usable(held, int(time.time())) and held.get("repositories") == wanted["repositories"]
                and held.get("permissions") == wanted["permissions"]):
            return held["token"], held["expires_at"]
        reason, token, expires_at = mint(argv, wanted, env)
    if reason:
        private.unlink(name)
        sys.stderr.write(NOTE.format(reason))
        return None, None
    private.write(name, {"token": token, "expires_at": expires_at, **wanted})
    return token, expires_at


def configured(env):
    return bool(env.get("OPENWIZ_TOKEN_SERVICE"))


def parse_request(args):
    """The request from --requester, --repository... and --read; the rest after `--`."""
    wanted = {"requester": None, "repositories": [], "permissions": WRITE}
    args = list(args)
    while args and args[0] != "--":
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
            raise Refused(f"usage: {USAGE}")
    if not (wanted["requester"] and REQUESTER.fullmatch(wanted["requester"])):
        raise Refused("--requester is a short lowercase label, such as builder-1844")
    repositories = wanted["repositories"]
    if (not repositories or len(set(map(str.lower, repositories))) != len(repositories)
            or not all(REPOSITORY.fullmatch(r) for r in repositories)
            or len({r.split("/")[0].lower() for r in repositories}) != 1):
        raise Refused("--repository is OWNER/NAME, at least one, each once, all of one owner")
    return wanted, args[1:] if args else None


def start(args, env):
    """Get the request's first token (or fall back), so the agent's first use is quick."""
    wanted, rest = parse_request(args)
    if rest is not None:
        raise Refused(f"usage: {USAGE}")
    if configured(env):
        token_for(Private(env, create=True), wanted, env)
    return 0


def without_inherited(env):
    """The environment with any App credential an outer run handed down removed."""
    child = dict(env)
    if RUN_MARK not in child:
        return child
    child.pop(RUN_MARK)
    child.pop("GH_TOKEN", None)
    first = child.pop(GIT_MARK, "")
    count = child.get("GIT_CONFIG_COUNT", "0")
    if first.isdigit() and count.isdigit():
        pairs = [(child.pop(f"GIT_CONFIG_KEY_{i}", ""), child.pop(f"GIT_CONFIG_VALUE_{i}", ""))
                 for i in range(int(count))]
        del pairs[int(first):int(first) + 2]
        for i, (key, value) in enumerate(pairs):
            child[f"GIT_CONFIG_KEY_{i}"], child[f"GIT_CONFIG_VALUE_{i}"] = key, value
        child["GIT_CONFIG_COUNT"] = str(len(pairs))
    return child


def git_helper(snapshot):
    """The one credential helper `run` gives git: it reads this run's snapshot only."""
    return (f"!exec {shlex.quote(sys.executable)} -I {shlex.quote(os.path.abspath(__file__))}"
            f" credential --snapshot {shlex.quote(snapshot)}")


def run(args, env):
    """Run COMMAND with this run's token in its own environment, or as the owner after the note."""
    wanted, command = parse_request(args)
    if not command:
        raise Refused(f"usage: {USAGE}")
    if not configured(env):
        return execute(command, env)
    private = Private(env, create=True)
    token, expires_at = token_for(private, wanted, env)
    child = without_inherited(env)
    if not token:
        return execute(command, child)
    name = f"run-{secrets.token_hex(16)}.json"
    snapshot = os.path.join(private.path, name)
    private.write(name, {"token": token, "expires_at": expires_at})
    try:
        count = child.get("GIT_CONFIG_COUNT", "0") or "0"
        if not count.isdigit():
            raise Refused("GIT_CONFIG_COUNT must be a number")
        count = int(count)
        for offset, value in enumerate(("", git_helper(snapshot))):  # "" resets the list
            child[f"GIT_CONFIG_KEY_{count + offset}"] = GIT_HELPER_KEY
            child[f"GIT_CONFIG_VALUE_{count + offset}"] = value
        child.update({"GIT_CONFIG_COUNT": str(count + 2), "GH_TOKEN": token,
                      RUN_MARK: snapshot, GIT_MARK: str(count)})
        return execute(command, child, wait=True)
    finally:
        private.unlink(name)


def execute(command, env, wait=False):
    """Run COMMAND; with wait, stay to remove this run's snapshot after it ends."""
    try:
        if not wait:
            os.execvpe(command[0], command, env)
        child = subprocess.Popen(command, env=env)
    except OSError:
        raise Refused("cannot run the command")
    signal.signal(signal.SIGTERM, lambda number, frame: child.send_signal(number))
    while True:
        try:
            code = child.wait()
            return 128 - code if code < 0 else code
        except KeyboardInterrupt:
            continue  # the terminal's interrupt reached the command too


def only_git_asks(snapshot, env):
    """True only inside git's own exchange, with this run's helper the last one git uses."""
    try:
        parent = subprocess.run(["ps", "-o", "comm=", "-p", str(os.getppid())],
                                capture_output=True, text=True, timeout=10).stdout.strip()
        listed = subprocess.run(["git", "config", "--list", "-z"], capture_output=True,
                                env=env, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    if not os.path.basename(parent).startswith("git") or listed.returncode != 0:
        return False
    helpers = []
    for item in listed.stdout.split(b"\0"):
        key, _, value = item.decode("utf-8", "replace").partition("\n")
        if key.lower().startswith("credential.") and key.lower().endswith(".helper"):
            helpers.append((key, value))
    return helpers[-2:] == [(GIT_HELPER_KEY, ""), (GIT_HELPER_KEY, git_helper(snapshot))]


def credential(args, env):
    """git's credential helper: answer `get` for https://github.com from this run's snapshot."""
    if len(args) != 3 or args[0] != "--snapshot" or args[2] != "get" or not configured(env):
        return 0
    snapshot = args[1]
    private = Private(env, create=False)
    name = os.path.basename(snapshot)
    if (snapshot != env.get(RUN_MARK) or os.path.dirname(snapshot) != private.path
            or not re.fullmatch(r"run-[0-9a-f]{32}\.json", name)):
        return 0
    fields = dict(line.split("=", 1) for line in sys.stdin.read().splitlines() if "=" in line)
    if fields.get("protocol") != "https" or fields.get("host") != "github.com":
        return 0
    if not only_git_asks(snapshot, env):
        return 0
    held = private.read(name)
    if (isinstance(held, dict) and isinstance(held.get("token"), str)
            and TOKEN.fullmatch(held["token"]) and type(held.get("expires_at")) is int
            and held["expires_at"] > time.time()):
        sys.stdout.write(f"username=x-access-token\npassword={held['token']}\n")
    return 0


def main(argv):
    commands = {"start": start, "run": run, "credential": credential}
    try:
        if not argv or argv[0] not in commands:
            raise Refused(f"usage: {USAGE}")
        return commands[argv[0]](list(argv[1:]), dict(os.environ))
    except Refused as error:
        sys.stderr.write(f"openwiz: agent-token: {error}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
