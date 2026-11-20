#!/usr/bin/env python3
"""GA3's proof (#1844): the agent helper, against a fake token service.

Synthetic values only. Run: python3 -I tools/github-app/test_agent_token.py.
No real room-cli, service, GitHub or token is touched: room-cli, python3 and gh
are fakes on PATH that record what they were given, never a token itself.
"""
import base64
import hashlib
import importlib.util
import json
import os
import shutil
import socketserver
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
HELPER = HERE / "agent-token.py"
FIXTURES = ROOT / "contracts" / "fixtures" / "token-service"
PIN = json.loads((ROOT / "contracts" / "token-service.v1.md").read_text()
                 .split("```json\n", 1)[1].split("\n```", 1)[0])
SERVICE = "/synthetic/openwiz/tools/github-app/token-service.py"
REPO = "synthetic-owner/work"
WRITE = {"metadata": "read", "contents": "write", "issues": "write",
         "pull_requests": "write", "checks": "read", "actions": "read"}
READ = {name: "read" for name in WRITE}
TOKEN, TOKEN2 = "synthetic-agent-token-1", "synthetic-agent-token-2"
REQ = ("--requester", "builder-1", "--repository", REPO)
NOTE = PIN["fallback"]["note"]
WITHHELD = "openwiz: openwiz[bot] token withheld from git"
URL = f"https://github.com/{REPO}"

# One fake for room-cli, python3 and gh. It logs its name, argv, standard input,
# whether its standard output is a pipe, and a hash of GH_TOKEN: never a token.
FAKE = r'''
import hashlib, json, os, stat, sys, time
name, args = sys.argv[1], sys.argv[2:]
stdin = sys.stdin.read() if name != "gh" else ""
token = os.environ.get("GH_TOKEN")
entry = {"name": name, "args": args, "stdin": stdin,
         "stdout_pipe": stat.S_ISFIFO(os.fstat(1).st_mode),
         "gh_token": hashlib.sha256(token.encode()).hexdigest() if token else None}
log = os.environ["FAKE_LOG"]
with open(log, "a") as f:
    f.write(json.dumps(entry) + "\n")
if name == "gh":
    sys.exit(0)
calls = [json.loads(line) for line in open(log) if json.loads(line)["name"] != "gh"]
answers = json.load(open(os.environ["FAKE_ANSWERS"]))
answer = answers[min(len(calls), len(answers)) - 1]
time.sleep(answer.get("sleep", 0))
sys.stdout.write(answer.get("stdout", ""))
sys.stderr.write(answer.get("stderr", ""))
sys.exit(answer["exit"])
'''


class FakeGitHub(socketserver.ThreadingTCPServer):
    """github.com behind a local HTTPS proxy, for git's real transport. It asks for Basic
    auth and keeps a hash of each credential it is sent. Its certificate is a throwaway."""
    daemon_threads = allow_reuse_address = True

    def __init__(self, folder):
        cert, key = folder / "cert.pem", folder / "key.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                        "-subj", "/CN=github.com", "-keyout", str(key), "-out", str(cert)],
                       check=True, capture_output=True)
        self.tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.tls.load_cert_chain(cert, key)
        self.seen = []
        super().__init__(("127.0.0.1", 0), Tunnel)
        threading.Thread(target=self.serve_forever, daemon=True).start()

    def git(self):
        return ["git", "-c", f"http.proxy=http://127.0.0.1:{self.server_address[1]}",
                "-c", "http.sslVerify=false", "ls-remote", URL]


class Tunnel(socketserver.StreamRequestHandler):
    def handle(self):
        if not self.rfile.readline().startswith(b"CONNECT github.com:443 "):
            return
        while self.rfile.readline() not in (b"\r\n", b""):
            pass
        self.wfile.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
        stream = self.server.tls.wrap_socket(self.request, server_side=True).makefile("rwb")
        while stream.readline():
            auth = ""
            while (line := stream.readline()) not in (b"\r\n", b""):
                key, _, value = line.decode().partition(":")
                auth = value.strip() if key.lower() == "authorization" else auth
            if auth.startswith("Basic "):
                self.server.seen.append(sha(base64.b64decode(auth[6:]).decode()))
                stream.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 0\r\n\r\n")
            else:
                stream.write(b'HTTP/1.1 401 Unauthorized\r\nWWW-Authenticate: Basic realm="x"\r\n'
                             b"Content-Length: 0\r\n\r\n")
            stream.flush()


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def answer(token=TOKEN, left=3600, repositories=(REPO,), permissions=None):
    body = {"schema": "openwiz.token-service.v1", "kind": "answer", "token": token,
            "expires_at": int(time.time()) + left, "repositories": list(repositories),
            "permissions": permissions or WRITE}
    return {"exit": 0, "stdout": json.dumps(body) + "\n"}


def refusal(code):
    body = {"schema": "openwiz.token-service.v1", "kind": "refusal", "refusal": code,
            "message": PIN["refusals"][code]["message"]}
    return {"exit": PIN["refusals"][code]["exit"], "stdout": json.dumps(body) + "\n"}


def load_helper():
    spec = importlib.util.spec_from_file_location("agent_token", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Helper(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="agent-token-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        (self.root / "fake.py").write_text(FAKE)
        for name in ("room-cli", "python3", "gh"):
            shim = self.bin / name
            shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" -I "{self.root}/fake.py" {name} "$@"\n')
            shim.chmod(0o755)
        self.log = self.root / "calls.log"
        self.private = self.root / "private"
        self.home = self.root / "home"
        self.home.mkdir()
        self.env = {"PATH": f"{self.bin}:/usr/bin:/bin", "HOME": str(self.home),
                    "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
                    "FAKE_LOG": str(self.log), "FAKE_ANSWERS": str(self.root / "answers.json"),
                    "OPENWIZ_AGENT_TOKEN_DIR": str(self.private),
                    "OPENWIZ_TOKEN_SERVICE": SERVICE, "OPENWIZ_TOKEN_SERVICE_ROUTE": "pairing",
                    "OPENWIZ_TOKEN_SERVICE_READBACK": "passed"}

    def answers(self, *items):
        (self.root / "answers.json").write_text(json.dumps(list(items)))

    def helper(self, *args, stdin="", **env):
        full = dict(self.env)
        full.update(env)
        for key in [k for k, v in full.items() if v is None]:
            del full[key]
        return subprocess.run([sys.executable, "-I", str(HELPER), *args], input=stdin,
                              capture_output=True, text=True, env=full, timeout=30)

    def start(self, *extra, **env):
        return self.helper("start", "--requester", "builder-1", "--repository", REPO, *extra, **env)

    def calls(self, name=None):
        if not self.log.exists():
            return []
        rows = [json.loads(line) for line in self.log.read_text().splitlines()]
        return [r for r in rows if name is None or r["name"] == name]

    def service_calls(self):
        return [c for c in self.calls() if c["name"] != "gh"]

    def one_call(self):
        calls = self.service_calls()
        self.assertEqual(len(calls), 1, "exactly one service call")
        return calls[0]

    def held(self):
        self.assertTrue(self.token_file().is_file(), "the private token file holds the token")
        return json.loads(self.token_file().read_text())

    def token_file(self):
        """The one request's cache file (the helper names it per requester and scope)."""
        files = sorted(self.private.glob("token-*.json")) if self.private.is_dir() else []
        self.assertLessEqual(len(files), 1, "one request, one cache file")
        return files[0] if files else self.private / "token-none.json"

    def assert_never_exposed(self, *results, tokens=(TOKEN, TOKEN2)):
        """No token in any output, argument list or file outside the private token file."""
        for result in results:
            for token in tokens:
                self.assertNotIn(token, result.stdout + result.stderr)
        for call in self.calls():
            for token in tokens:
                self.assertNotIn(token, " ".join(call["args"]) + call["stdin"])
        for path in self.root.rglob("*"):
            private = path.parent == self.private and path.name.startswith("token-")
            if path.is_file() and not private and path.name != "answers.json":
                for token in tokens:
                    self.assertNotIn(token.encode(), path.read_bytes(), path)

    def github(self):
        server = FakeGitHub(self.root)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    def assert_fallback(self, result, reason):
        self.assertEqual(result.stderr, NOTE.replace("<reason>", reason) + "\n")
        self.assertFalse(self.token_file().exists())
        self.assertEqual(list(self.private.glob("run-*")) if self.private.is_dir() else [], [])


class Refresh(unittest.TestCase):
    def test_the_contract_refresh_boundary(self):
        # catches: a refresh at under 300 seconds only, or never, so a token expires mid-work.
        helper = load_helper()
        for case in json.loads((FIXTURES / "refresh.json").read_text())["cases"]:
            with self.subTest(case["name"]):
                self.assertEqual(helper.needs_refresh(case["now"], case["expires_at"]), case["refresh"])


class MintedToken(Helper):
    def test_gh_and_git_use_the_minted_token(self):
        # catches: gh or git not getting the App's token, or getting it through an argument or file in a tree.
        self.answers(answer())
        started = self.start()
        self.assertEqual((started.returncode, started.stdout, started.stderr), (0, "", ""))
        self.assertEqual(self.held()["token"], TOKEN)
        self.assertEqual(self.token_file().stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.private.stat().st_mode & 0o777, 0o700)
        ran = self.helper("run", *REQ, "--", "gh", "issue", "view", "1")
        self.assertEqual((ran.returncode, ran.stderr), (0, ""))
        self.assertEqual(self.calls("gh")[-1]["gh_token"], sha(TOKEN))
        # git's own HTTPS transport gets it; the owner's store helper never does (run resets the list).
        (self.home / ".gitconfig").write_text("[credential]\n\thelper = store\n")
        github = self.github()
        git = self.helper("run", *REQ, "--", *github.git())
        self.assertEqual(git.returncode, 0, git.stderr)
        self.assertEqual(set(github.seen), {sha(f"x-access-token:{TOKEN}")})
        self.assertFalse((self.home / ".git-credentials").exists())
        self.assertEqual(len(self.service_calls()), 1, "a fresh token is reused, not minted again")
        self.assertEqual(list(self.private.glob("run-*")), [], "each run removes its snapshot")
        self.assertEqual(list(self.private.glob("exec-*")), [], "and its git exec folder")
        self.assert_never_exposed(started, ran, git)

    def test_the_request_names_repositories_and_permissions_only(self):
        # catches: a request that is not the contract's, names the key, or asks for more than the App's.
        self.answers(answer(permissions=READ))
        self.start("--read")
        request = json.loads(self.one_call()["stdin"])
        self.assertEqual(request, {"schema": "openwiz.token-service.v1", "kind": "request",
                                   "requester": "builder-1", "repositories": [REPO], "permissions": READ})

    def test_refreshes_with_five_minutes_left_before_the_next_use(self):
        # catches: a held token used with 300 seconds or less left, or an expired one.
        self.answers(answer(), answer(token=TOKEN2))
        self.start()
        held = self.held()
        held["expires_at"] = int(time.time()) + 200
        self.token_file().write_text(json.dumps(held))
        ran = self.helper("run", *REQ, "--", "gh", "pr", "list")
        self.assertEqual((ran.returncode, ran.stderr), (0, ""))
        self.assertEqual(len(self.service_calls()), 2)
        self.assertEqual(self.calls("gh")[-1]["gh_token"], sha(TOKEN2))
        self.assert_never_exposed(ran)

    def test_token_crosses_the_pairing_only_as_piped_stdout_of_one_call(self):
        # catches: the token route (#1839, option 1) broken: a token on a command line, a terminal or a
        # second call, or a pairing call made before GA5's read-back passed.
        self.answers(answer())
        started = self.start()
        call = self.one_call()
        self.assertEqual([call["name"], *call["args"]], PIN["reach"]["routes"]["pairing"][:4]
                         + [f"python3 -I '{SERVICE}' mint"])
        self.assertTrue(call["stdout_pipe"], "the answer is read from a pipe, never a terminal")
        self.assertIsNone(call["gh_token"], "the pairing call's environment holds no token")
        self.assert_never_exposed(started)
        for readback in (None, "", "inconclusive", "failed", "Passed"):
            with self.subTest(readback=readback):
                self.log.unlink(missing_ok=True)
                off = self.start(OPENWIZ_TOKEN_SERVICE_READBACK=readback)
                self.assertEqual(self.calls(), [], "no pairing call while the read-back has not passed")
                self.assert_fallback(off, "pairing-off")

    def test_a_local_thread_runs_the_service_itself(self):
        # catches: the local route sent over the pairing, or held back by the pairing's read-back.
        self.answers(answer())
        self.start(OPENWIZ_TOKEN_SERVICE_ROUTE="local", OPENWIZ_TOKEN_SERVICE_READBACK=None)
        call = self.one_call()
        self.assertEqual([call["name"], *call["args"]], ["python3", "-I", SERVICE, "mint"])
        self.assertTrue(call["stdout_pipe"])

    def test_a_private_place_inside_a_git_tree_is_refused(self):
        # catches: the token file written where a commit could pick it up.
        self.answers(answer())
        tree = self.root / "work"
        (tree / ".git").mkdir(parents=True)
        refused = self.start(OPENWIZ_AGENT_TOKEN_DIR=str(tree / "private"))
        self.assertEqual(refused.returncode, 2)
        self.assertEqual(self.calls(), [])
        self.assertFalse((tree / "private" / "token.json").exists())
        self.private.mkdir(mode=0o755)
        self.private.chmod(0o755)
        loose = self.start()
        self.assertEqual((loose.returncode, self.calls()), (2, []), "a directory others can read is refused")


class Fallback(Helper):
    def test_unreachable_service_falls_back_with_one_note(self):
        # catches: no note, two notes (start then run), or a silent switch of identity.
        self.answers({"exit": 1, "stdout": "", "stderr": "synthetic: owner's machine unavailable"})
        started = self.start()
        self.assertEqual(started.returncode, 0)
        self.assert_fallback(started, "unreachable")
        ran = self.helper("run", *REQ, "--", "gh", "issue", "view", "1", GH_TOKEN="synthetic-owner-login")
        self.assertEqual(ran.returncode, 0)
        self.assert_fallback(ran, "unreachable")
        self.assertEqual(self.calls("gh")[-1]["gh_token"], sha("synthetic-owner-login"))
        self.assertNotIn("synthetic: owner", started.stderr, "service text never reaches the agent's stderr")

    def test_a_failed_refresh_leaves_no_service_credential(self):
        # catches: gh and git split between the App and the owner after a failed refresh.
        self.answers(answer(), {"exit": 1, "stdout": ""})
        self.start()
        held = self.held()
        held["expires_at"] = int(time.time()) + 100
        self.token_file().write_text(json.dumps(held))
        outer = str(self.private / ("run-" + "0" * 32 + ".json"))  # as an outer run marks its child
        ran = self.helper("run", *REQ, "--", "gh", "pr", "list", GH_TOKEN=TOKEN,
                          OPENWIZ_AGENT_TOKEN_RUN=outer)
        self.assert_fallback(ran, "unreachable")
        self.assertIsNone(self.calls("gh")[-1]["gh_token"], "the held App token is not handed on")
        self.assertIsNone(self.service_calls()[-1]["gh_token"], "nor passed to the service call")
        git = self.helper("run", *REQ, "--", "git", "credential", "fill",
                          stdin="protocol=https\nhost=github.com\n\n")
        self.assertNotIn(TOKEN, git.stdout)

    def test_each_fixture_fallback_reason(self):
        # catches: a refusal, a bad or wider answer, or an expiring answer used as a token.
        cases = {
            "not-installed": refusal("not-installed"),
            "unavailable": refusal("unavailable"),
            "permission": refusal("permission"),
            "bad-answer": {"exit": 0, "stdout": "garbled"},
        }
        wider = answer(repositories=(REPO, "synthetic-owner/other"))
        short = answer(left=200)
        long = answer(left=4000)
        twice = {"exit": 0, "stdout": answer()["stdout"].replace('"kind"', '"token": "x", "kind"')}
        bad_exit = dict(refusal("permission"), exit=0)
        injected = answer(token="synthetic\nusername=x")
        failed_answer = dict(answer(), exit=5)
        for reason, item in [*cases.items(), ("bad-answer", wider), ("bad-answer", short),
                             ("bad-answer", long), ("bad-answer", twice), ("bad-answer", bad_exit),
                             ("bad-answer", injected), ("bad-answer", failed_answer)]:
            with self.subTest(reason=reason, item=item["stdout"][:60]):
                self.log.unlink(missing_ok=True)
                self.answers(item)
                result = self.start()
                self.assertEqual(result.returncode, 0)
                self.assert_fallback(result, reason)
                self.assert_never_exposed(result)
        reasons = {c["reason"] for c in json.loads((FIXTURES / "fallback.json").read_text())["cases"]
                   if "reason" in c}
        self.assertLessEqual(reasons, set(PIN["fallback"]["reasons"]))

    def test_a_path_that_cannot_be_quoted_is_never_run(self):
        # catches: a service path breaking out of the pairing command's single quotes.
        for path in ("/synthetic/it's.py", "/synthetic/a\nb.py", "relative/token-service.py"):
            with self.subTest(path=path):
                result = self.start(OPENWIZ_TOKEN_SERVICE=path)
                self.assertEqual(self.calls(), [])
                self.assert_fallback(result, "unreachable")

    def test_a_service_that_does_not_answer_in_time(self):
        # catches: an agent hanging on a pairing call that never returns.
        helper = load_helper()
        self.answers({"exit": 0, "stdout": "", "sleep": 5})
        helper.TIMEOUT_S = 1  # the contract's 60 seconds, shortened for the test
        started = time.monotonic()
        reason = helper.ask([str(self.bin / "room-cli"), "x"], b"{}", self.env)[0]
        self.assertEqual(reason, "unreachable")
        self.assertLess(time.monotonic() - started, 4)

    def test_no_service_configured_is_exactly_as_today(self):
        # catches: a note, a call or a changed environment when no service is set.
        result = self.start(OPENWIZ_TOKEN_SERVICE=None)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        ran = self.helper("run", *REQ, "--", "gh", "api", "user", OPENWIZ_TOKEN_SERVICE=None,
                          GH_TOKEN="synthetic-owner-login")
        self.assertEqual((ran.returncode, ran.stderr), (0, ""))
        self.assertEqual(self.service_calls(), [])
        self.assertEqual(self.calls("gh")[-1]["gh_token"], sha("synthetic-owner-login"))
        self.assertFalse(self.private.exists())


class Review(Helper):
    """The review's findings R1, R2, R3, R4, R6, R7 and R8 on #1916, each red first."""
    REQ = REQ

    def shell(self, script, *extra, **env):
        env = dict({"PY": sys.executable, "H": str(HELPER)}, **env)
        return self.helper("run", *self.REQ, "--", "sh", "-c", script, *extra, **env)

    def test_r1_credential_answers_only_inside_git_exchange(self):
        # catches: the credential subcommand printing the token when run by hand.
        self.answers(answer())
        self.start()
        direct = self.helper("credential", "get", stdin="protocol=https\nhost=github.com\n\n")
        self.assertEqual((direct.stdout, direct.stderr), ("", ""))
        by_hand = self.shell('printf "protocol=https\\nhost=github.com\\n\\n" | '
                             '"$PY" -I "$H" credential --snapshot "$OPENWIZ_AGENT_TOKEN_RUN" get | cat')
        self.assertNotIn(TOKEN, by_hand.stdout + by_hand.stderr)

    def test_r2_a_symlinked_ancestor_into_a_git_tree_is_refused(self):
        # catches: the lexical Git-tree guard followed through a symlink into a working tree.
        self.answers(answer())
        tree = self.root / "work"
        (tree / ".git").mkdir(parents=True)
        (tree / "sub").mkdir()
        (self.root / "link").symlink_to(tree / "sub")
        refused = self.start(OPENWIZ_AGENT_TOKEN_DIR=str(self.root / "link" / "private"))
        self.assertEqual((refused.returncode, self.calls()), (2, []))
        self.assertFalse((tree / "sub" / "private").exists())

    def test_r1_a_git_credential_command_never_prints_the_token(self):
        # catches: `git credential fill` inside a run printing the App token to its caller's stdout.
        self.answers(answer())
        self.start()
        fill = self.helper("run", *self.REQ, "--", "git", "credential", "fill",
                           stdin="protocol=https\nhost=github.com\n\n")
        piped = self.shell('printf "protocol=https\nhost=github.com\n\n" | git credential fill | cat')
        self.assert_never_exposed(fill, piped)
        self.assertNotEqual(fill.returncode, 0)
        self.assertEqual(fill.stderr.count(WITHHELD), 1, "one note")

    def test_r2_an_ancestor_swapped_before_the_open_never_redirects_the_token(self):
        # catches: the directory checked by path, then reopened by path after an ancestor became a
        # symlink into a Git tree, so the token is written inside the tree.
        helper = load_helper()
        tree = self.root / "work"
        (tree / ".git").mkdir(parents=True)
        (tree / "private").mkdir(mode=0o700)
        safe = self.root / "safe"
        (safe / "private").mkdir(parents=True, mode=0o700)
        safe.chmod(0o700)  # under any umask, so only the swap can redirect it
        real_open = os.open

        def swap_then_open(path, *args, **kwargs):
            if os.path.basename(path) == "private" and not safe.is_symlink():
                safe.rename(self.root / "moved")
                safe.symlink_to(tree)
            return real_open(path, *args, **kwargs)

        with mock.patch.object(helper.os, "open", swap_then_open):
            try:
                private = helper.Private(dict(self.env, OPENWIZ_AGENT_TOKEN_DIR=str(safe / "private")), True)
                private.write("token-x.json", {"token": TOKEN})
            except helper.Refused:
                pass
        self.assertTrue(safe.is_symlink(), "the swap happened")
        self.assertEqual(list((tree / "private").iterdir()), [])

    def test_r2_an_ancestor_others_can_change_is_refused(self):
        # catches: a private directory under a folder anyone can write, who could swap it later.
        self.answers(answer())
        shared = self.root / "shared"
        shared.mkdir()
        shared.chmod(0o777)
        refused = self.start(OPENWIZ_AGENT_TOKEN_DIR=str(shared / "private"))
        self.assertEqual((refused.returncode, self.calls()), (2, []))
        self.assertFalse((shared / "private").exists())

    def test_r2_an_ancestor_its_group_can_change_is_refused(self):
        # catches: a non-sticky folder writable by the caller's own group, whose other members
        # could move the private directory into a Git tree.
        self.answers(answer())
        shared = self.root / "group"
        shared.mkdir()
        shared.chmod(0o770)
        os.chown(shared, -1, os.getgid())
        refused = self.start(OPENWIZ_AGENT_TOKEN_DIR=str(shared / "private"))
        self.assertEqual((refused.returncode, self.calls()), (2, []))
        self.assertFalse((shared / "private").exists())

    def test_r7_a_replaced_helper_list_or_header_never_authenticates_git(self):
        # catches: higher-priority git config replacing the helper list, so the App helper is never
        # asked and git signs in with the owner's helper or an owner's Authorization header.
        self.answers(answer())
        self.start()
        owner = "!f() { echo username=synthetic-owner; echo password=synthetic-owner-login; }; f"
        header = "Authorization: Basic " + base64.b64encode(b"synthetic-owner:synthetic-owner-login").decode()
        for config in (("credential.helper=", f"credential.helper={owner}"),
                       ("credential.https://github.com.helper=", f"credential.https://github.com.helper={owner}"),
                       (f"http.extraHeader={header}",)):
            with self.subTest(config=config[-1][:40]):
                github = self.github()
                options = [arg for item in config for arg in ("-c", item)]
                ran = self.helper("run", *self.REQ, "--", "git", *options, *github.git()[1:])
                self.assertEqual(github.seen, [], "git signs in as no one: not the owner, not the App")
                self.assertNotEqual(ran.returncode, 0)
                self.assertEqual(ran.stderr.count(WITHHELD), 1, "one note")

    def test_r8_git_http_tracing_never_shows_the_token(self):
        # catches: inherited GIT_TRACE_CURL, GIT_CURL_VERBOSE or GIT_TRACE_REDACT=0 logging the App
        # credential's Authorization header to the terminal or a trace file.
        self.answers(answer())
        self.start()
        github = self.github()
        trace = self.root / "curl-trace.txt"
        ran = self.helper("run", *self.REQ, "--", *github.git(), GIT_TRACE_CURL=str(trace),
                          GIT_CURL_VERBOSE="1", GIT_TRACE_REDACT="0")
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual(set(github.seen), {sha(f"x-access-token:{TOKEN}")})
        encoded = base64.b64encode(f"x-access-token:{TOKEN}".encode()).decode()
        self.assert_never_exposed(ran, tokens=(TOKEN, encoded))

    def test_r7_a_later_owner_helper_never_authenticates_git(self):
        # catches: the helper declining for a later helper, so git silently signs in as the owner.
        self.answers(answer())
        self.start()
        github = self.github()
        owner = "!f() { echo username=synthetic-owner; echo password=synthetic-owner-login; }; f"
        ran = self.helper("run", *self.REQ, "--", "git", "-c", f"credential.helper={owner}", *github.git()[1:])
        self.assertEqual(github.seen, [], "git signs in as no one: not the owner, not the App")
        self.assertNotEqual(ran.returncode, 0)
        self.assertEqual(ran.stderr.count(WITHHELD), 1, "one note")
        self.assert_never_exposed(ran)

    def test_r3_two_agents_on_one_account_keep_their_own_scopes(self):
        # catches: a second agent's start replacing the first's request, so one gets the other's token.
        self.answers(answer(), answer(token=TOKEN2, permissions=READ))
        self.start()
        self.helper("start", "--requester", "reviewer-2", "--repository", REPO, "--read")
        first = self.helper("run", *self.REQ, "--", "gh", "pr", "list")
        second = self.helper("run", "--requester", "reviewer-2", "--repository", REPO, "--read",
                             "--", "gh", "pr", "view", "1")
        self.assertEqual([c["gh_token"] for c in self.calls("gh")], [sha(TOKEN), sha(TOKEN2)])
        self.assertEqual(len(self.service_calls()), 2)
        self.assert_never_exposed(first, second)

    def test_r4_a_command_scope_helper_never_gets_the_token(self):
        # catches: `git -c credential.helper=store` adding a persisting helper after the reset.
        self.answers(answer())
        self.start()
        fill = self.helper("run", *self.REQ, "--", "git", "-c", "credential.helper=store",
                           "credential", "fill", stdin="protocol=https\nhost=github.com\n\n")
        self.helper("run", *self.REQ, "--", "git", "-c", "credential.helper=store",
                    "credential", "approve", stdin=fill.stdout + "\n")
        self.assertNotIn(TOKEN, fill.stdout)
        self.assertFalse((self.home / ".git-credentials").exists())

    def test_r6_a_failed_start_inside_a_run_hands_no_app_token_on(self):
        # catches: a fallback forwarding an inherited App token because the cache was already cleared.
        self.answers(answer())
        req = " ".join(self.REQ)
        ran = self.shell(f'OPENWIZ_TOKEN_SERVICE_READBACK=failed "$PY" -I "$H" start {req}; '
                         f'OPENWIZ_TOKEN_SERVICE_READBACK=failed "$PY" -I "$H" run {req} -- gh pr list')
        self.assertEqual([c["gh_token"] for c in self.calls("gh")], [None])
        self.assertEqual(ran.stderr, (NOTE.replace("<reason>", "pairing-off") + "\n") * 2)


if __name__ == "__main__":
    unittest.main()
