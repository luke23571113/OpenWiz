#!/usr/bin/env python3
"""GA3's proof (#1844): the agent helper, against a fake token service.

Synthetic values only. Run: python3 -I tools/github-app/test_agent_token.py.
No real room-cli, service, GitHub or token is touched: room-cli, python3 and gh
are fakes on PATH that record what they were given, never a token itself.
"""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

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
TOKEN, TOKEN2, OLD = "synthetic-agent-token-1", "synthetic-agent-token-2", "synthetic-old-token"
NOTE = PIN["fallback"]["note"]

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
        return self.private / "token.json"

    def assert_never_exposed(self, *results, tokens=(TOKEN, TOKEN2)):
        """No token in any output, argument list or file outside the private token file."""
        for result in results:
            for token in tokens:
                self.assertNotIn(token, result.stdout + result.stderr)
        for call in self.calls():
            for token in tokens:
                self.assertNotIn(token, " ".join(call["args"]) + call["stdin"])
        for path in self.root.rglob("*"):
            if path.is_file() and path != self.token_file() and path.name != "answers.json":
                for token in tokens:
                    self.assertNotIn(token.encode(), path.read_bytes(), path)

    def assert_fallback(self, result, reason):
        self.assertEqual(result.stderr, NOTE.replace("<reason>", reason) + "\n")
        self.assertFalse(self.token_file().exists())


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
        ran = self.helper("run", "--", "gh", "issue", "view", "1")
        self.assertEqual((ran.returncode, ran.stderr), (0, ""))
        self.assertEqual(self.calls("gh")[-1]["gh_token"], sha(TOKEN))
        git = self.helper("run", "--", "git", "credential", "fill", stdin="protocol=https\nhost=github.com\n\n")
        self.assertEqual(git.returncode, 0, git.stderr)
        self.assertIn(f"password={TOKEN}\n", git.stdout)  # git's own pipe back to its caller
        self.assertEqual(len(self.service_calls()), 1, "a fresh token is reused, not minted again")
        self.assert_never_exposed(started, ran)

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
        ran = self.helper("run", "--", "gh", "pr", "list")
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
                self.log.unlink()
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


class Fallback(Helper):
    def test_unreachable_service_falls_back_with_one_note(self):
        # catches: no note, two notes (start then run), or a silent switch of identity.
        self.answers({"exit": 1, "stdout": "", "stderr": "synthetic: owner's machine unavailable"})
        started = self.start()
        self.assertEqual(started.returncode, 0)
        self.assert_fallback(started, "unreachable")
        ran = self.helper("run", "--", "gh", "issue", "view", "1", GH_TOKEN="synthetic-owner-login")
        self.assertEqual(ran.returncode, 0)
        self.assert_fallback(ran, "unreachable")
        self.assertEqual(self.calls("gh")[-1]["gh_token"], sha("synthetic-owner-login"))
        self.assertNotIn("synthetic: owner", started.stderr, "service text never reaches the agent's stderr")

    def test_a_failed_refresh_leaves_no_service_credential(self):
        # catches: gh and git split between the App and the owner after a failed refresh.
        self.private.mkdir(mode=0o700)
        self.token_file().write_text(json.dumps({"token": OLD, "expires_at": int(time.time()) + 100,
                                                 "repositories": [REPO], "permissions": WRITE}))
        self.token_file().chmod(0o600)
        (self.private / "request.json").write_text(json.dumps(
            {"requester": "builder-1", "repositories": [REPO], "permissions": WRITE}))
        self.answers({"exit": 1, "stdout": ""})
        ran = self.helper("run", "--", "gh", "pr", "list", GH_TOKEN=OLD)
        self.assert_fallback(ran, "unreachable")
        self.assertIsNone(self.calls("gh")[-1]["gh_token"], "the held App token is not handed on")
        git = self.helper("run", "--", "git", "credential", "fill",
                          stdin="protocol=https\nhost=github.com\n\n")
        self.assertNotIn(OLD, git.stdout)

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
        for reason, item in [*cases.items(), ("bad-answer", wider), ("bad-answer", short),
                             ("bad-answer", long), ("bad-answer", twice), ("bad-answer", bad_exit),
                             ("bad-answer", injected)]:
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
        started = time.monotonic()
        reason = helper.ask([str(self.bin / "room-cli"), "x"], b"{}", self.env, timeout=1)[0]
        self.assertEqual(reason, "unreachable")
        self.assertLess(time.monotonic() - started, 4)

    def test_no_service_configured_is_exactly_as_today(self):
        # catches: a note, a call or a changed environment when no service is set.
        result = self.start(OPENWIZ_TOKEN_SERVICE=None)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        ran = self.helper("run", "--", "gh", "api", "user", OPENWIZ_TOKEN_SERVICE=None,
                          GH_TOKEN="synthetic-owner-login")
        self.assertEqual((ran.returncode, ran.stderr), (0, ""))
        self.assertEqual(self.service_calls(), [])
        self.assertEqual(self.calls("gh")[-1]["gh_token"], sha("synthetic-owner-login"))
        self.assertFalse(self.private.exists())


if __name__ == "__main__":
    unittest.main()
