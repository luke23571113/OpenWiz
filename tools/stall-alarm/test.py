#!/usr/bin/env python3
"""#567, #824: public CLI proofs, synthetic gh/loop/collector snapshots and private state.

`CollectorFixtures` feeds the alarm the collector contract's own read
envelopes (tools/war-room/fixtures/collector/) through a fake collector and
checks that the alarm itself never runs `gh`.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

HERE = Path(__file__).resolve().parent
SCRIPT = Path(os.environ.get("STALL_ALARM_SCRIPT", HERE / "alarm.py")).resolve()
FIXTURES = HERE.parent / "collector" / "fixtures" / "collector"
NOW = 1793620800  # 2026-11-02T12:00:00Z


def stamp(seconds):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat().replace("+00:00", "Z")


def connection(nodes):
    return {"nodes": nodes, "pageInfo": {"hasNextPage": False, "endCursor": None}}


def world():
    return {"data": {"repository": {"defaultBranchRef": {"name": "main"},
                      "pullRequests": connection([])}, "search": {"issueCount": 0}}}


class Harness(unittest.TestCase):
    def setUp(self):
        self.now = NOW
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        # The fake is deliberately strict about every external call.
        for name in ("gh", "room-cli"):
            target = self.bin / name
            target.write_text("#!/usr/bin/env python3\n" +
                "import json, os, pathlib, sys, time\n"
                "root = pathlib.Path(os.environ['FAKE_ROOT'])\n"
                "name = pathlib.Path(sys.argv[0]).name\n"
                "with (root / 'calls').open('a') as f: f.write(json.dumps([name, *sys.argv[1:]]) + '\\n')\n"
                "assert (name == 'gh' and sys.argv[1:3] == ['api', 'graphql']) or "
                "(name == 'room-cli' and sys.argv[1:] == ['loop', 'list', '--json']), sys.argv\n"
                "mode = (root / (name + '.mode')).read_text()\n"
                "if mode == 'hang': time.sleep(120)\n"
                "if mode == 'fail': print('synthetic private stdout'); "
                "print('synthetic private stderr', file=sys.stderr); sys.exit(1)\n"
                "query = next((a for a in sys.argv if a.startswith('query=')), '')\n"
                # The collector's PR inventory (#824): the world's recent-merge
                # count, as that many PRs merged into main a minute before the tick.
                "if name == 'gh' and 'mergedAt' in query:\n"
                "    try: count = json.loads((root / 'gh.json').read_text())['data']['search']['issueCount']\n"
                "    except Exception: count = 0\n"
                "    at = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(int((root / 'tick').read_text()) - 60))\n"
                "    end = {'hasNextPage': False, 'endCursor': None}\n"
                "    nodes = [{'number': 9000 + i, 'baseRefName': 'main', 'mergedAt': at, 'closedAt': at,\n"
                "              'closingIssuesReferences': {'nodes': [], 'pageInfo': end}} for i in range(count)]\n"
                "    print(json.dumps({'data': {'repository': {'pullRequests': {'nodes': nodes, 'pageInfo': end}}}}))\n"
                "    sys.exit(0)\n"
                "if name == 'gh' and 'cursor=next' in sys.argv:\n"
                "    sys.stdout.write((root / 'gh.next.json').read_text()); sys.exit(0)\n"
                "sys.stdout.write((root / (name + '.json')).read_text())\n")
            target.chmod(0o755)
            (self.root / (name + ".mode")).write_text("ok")
        self.github = world()
        # Synthetic repeating fleet. Installed scheduler code advances attempt
        # timestamps even for skipped script output; see 1466-skipped-tick.md.
        self.fleet = {"id": "loop_fixture", "enabled": True, "cron": "*/10 * * * *",
                      "last_error": None, "last_run_at": stamp(NOW - 60)}
        self.fleet_running = True
        self.loops = {"automations": [self.fleet]}
        self.env = {}
        self.answer = None

    def run_alarm(self, offset=0, deadline=4, repo="example-owner/example-repo", grace=None,
                  checks=None):
        if self.fleet_running:
            self.fleet["last_run_at"] = stamp(self.now + offset - 60)
        for name, data in (("gh", self.github), ("room-cli", self.loops), ("collector", self.answer)):
            (self.root / (name + ".json")).write_text(
                data if isinstance(data, str) else json.dumps(data))
        (self.root / "tick").write_text(str(self.now + offset))
        env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}", FAKE_ROOT=str(self.root))
        env.pop("STALL_ALARM_COLLECTOR", None)
        env.update(self.env)
        began = time.monotonic()
        proc = subprocess.run([sys.executable, str(SCRIPT), "--repo", repo,
            "--fleet-loop", "loop_fixture", "--state", str(self.root / "state.json"),
            "--now", stamp(self.now + offset), "--deadline", str(deadline),
            *[arg for check in checks or [] for arg in ("--check", check)],
            *([] if grace is None else ["--fleet-grace", str(grace)])],
            env=env, capture_output=True, text=True, timeout=deadline + 3)
        self.assertIn(proc.returncode, (0, 1), proc.stderr)
        self.assertEqual(proc.stderr, "")
        self.assertEqual(proc.returncode, 1 if proc.stdout else 0)
        return proc.stdout.splitlines(), time.monotonic() - began


    def calls(self):
        return [json.loads(line) for line in (self.root / "calls").read_text().splitlines()]


TICK = 1898597040  # 2030-03-01T12:04:00Z, read-stall.json's tick
CONTRACT_REPO = "synthetic-owner/synthetic-repo"
QUIET_LINES = ["ALARM: idle #4211: 60 minutes after findings sent",
               "ALARM: idle #4213: 60 minutes after findings sent",
               "ALARM: no merges for 60 minutes with an approved green conflict-free pull request"]


class CollectorFixtures(Harness):
    """#824: the alarm's GitHub facts are the collector's on-demand read (collector.v1.md)."""

    def setUp(self):
        super().setUp()
        self.now = TICK
        collector = self.bin / "collector"
        collector.write_text("#!/usr/bin/env python3\n"
            "import json, os, pathlib, sys, time\n"
            "root = pathlib.Path(os.environ['FAKE_ROOT'])\n"
            "with (root / 'calls').open('a') as f: f.write(json.dumps(['collector', *sys.argv[1:]]) + '\\n')\n"
            "assert sys.flags.isolated, 'the collector runs isolated (-I)'\n"
            "mode = (root / 'collector.mode').read_text()\n"
            "if mode == 'hang': time.sleep(120)\n"
            "if mode == 'fail': print('synthetic private stdout'); sys.exit(1)\n"
            "sys.stdout.write((root / 'collector.json').read_text())\n")
        (self.root / "collector.mode").write_text("ok")
        self.env = {"STALL_ALARM_COLLECTOR": str(collector)}
        self.answer = json.loads((FIXTURES / "read-stall.json").read_text())

    def read(self, offset=0):
        return self.run_alarm(offset, repo=CONTRACT_REPO)[0]

    # catches: the alarm still reading GitHub itself, asking the collector for the
    # wrong facts, hour, base or checks, or misreading the contract's worked read
    # (a draft counted, a null rollup made eligible, a verdict newer than a record
    # ignored). The expected alarms are the fixture README's own.
    def test_contract_read_fires_its_worked_alarms_without_gh(self):
        self.assertEqual(self.read(), QUIET_LINES)
        self.assertEqual([c for c in self.calls() if c[0] != "room-cli"], [[
            "collector", "read", "--repo", CONTRACT_REPO, "--fact", "merges", "--fact", "open_prs",
            "--since", "2030-03-01T11:04:00Z", "--until", "2030-03-01T12:04:00Z",
            "--base", "main", "--check", "ci", "--now", "2030-03-01T12:04:00Z"]])

    # catches: the collector's all-bases merges hiding a stalled base, or a merge
    # into the base failing to clear the alarm.
    def test_only_a_merge_into_the_base_clears_no_merges(self):
        merges = self.answer["factory"]["merges"]
        for base, expected in (("release-0.0.9", QUIET_LINES), ("main", QUIET_LINES[:2])):
            with self.subTest(base=base):
                (self.root / "state.json").unlink(missing_ok=True)
                merges["value"]["pull_requests"] = [{"number": 4209, "merged_at": "2030-03-01T11:30:00Z",
                                                     "base": base, "tickets": [], "direction": "unknown"}]
                merges["evidence"] = ["https://github.com/synthetic-owner/synthetic-repo/pull/4209"]
                self.assertEqual(self.read(), expected)

    # catches: a fact the collector could not read, or an answer for another
    # repository, base, check set or hour, taken as a quiet factory. Unknown is
    # never "no stall".
    def test_unread_or_mismatched_answers_fail_the_read(self):
        good = copy.deepcopy(self.answer)

        def edit(change):
            answer = copy.deepcopy(good)
            change(answer, answer["factory"]["merges"], answer["factory"]["open_prs"])
            return answer

        def unread(fact, state="unavailable"):
            fact.update(state=state, prerequisites=["synthetic prerequisite"])
            if state == "unavailable":
                fact["value"] = None
        cases = {
            "open_prs unavailable": edit(lambda a, m, o: unread(o)),
            "merges unavailable": edit(lambda a, m, o: unread(m)),
            "merges partial": edit(lambda a, m, o: unread(m, "partial")),
            "another repository": edit(lambda a, m, o: a.update(repository="synthetic-owner/other-repo")),
            "a snapshot, not a read": edit(lambda a, m, o: a.update(schema="openwiz.war-room.collector.v1")),
            "merges missing": edit(lambda a, m, o: a["factory"].pop("merges")),
            "a CI fact instead": edit(lambda a, m, o: a.update(ci={"queue": {}})),
            "another default branch": edit(lambda a, m, o: o["value"].update(default_branch="trunk")),
            "other checks judged": edit(lambda a, m, o: o["value"].update(checks=["ci", "privacy"])),
            "another hour": edit(lambda a, m, o: m["window"].update(since="2030-03-01T10:04:00Z")),
            "a merge outside the hour": edit(lambda a, m, o: m["value"]["pull_requests"].append(
                {"number": 4209, "merged_at": "2030-03-01T11:03:59Z", "base": "main", "tickets": [],
                 "direction": "unknown"})),
            "a PR without its record": edit(lambda a, m, o: o["value"]["pull_requests"][0].pop("record")),
            "a PR with an unknown field": edit(lambda a, m, o: o["value"]["pull_requests"][0].update(body="x")),
            "a record with an unknown field": edit(lambda a, m, o: o["value"]["pull_requests"][1]["record"].update(
                thread="thr_syn_fixture")),
            "a fact with an unknown field": edit(lambda a, m, o: o.update(stale=True)),
            "not JSON": "synthetic private invalid JSON",
            "a repeated key": '{"schema":"openwiz.war-room.collector.read.v1","schema":"x"}',
        }
        for label, answer in cases.items():
            with self.subTest(label):
                (self.root / "state.json").unlink(missing_ok=True)
                self.answer = answer
                self.assertEqual(self.read(), ["ALARM: read failed: github status unavailable"])
        (self.root / "state.json").unlink(missing_ok=True)
        self.answer = good
        (self.root / "collector.mode").write_text("fail")
        self.assertEqual(self.read(), ["ALARM: read failed: github status unavailable"])
        self.assertNotIn("gh", [c[0] for c in self.calls()])


if __name__ == "__main__":
    unittest.main(verbosity=2)
