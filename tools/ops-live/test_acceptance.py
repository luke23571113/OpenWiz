#!/usr/bin/env python3
"""Red/green proofs for the offline result validator (#2190, OB8).

python3 -I tools/ops-live/test_acceptance.py

Every case is synthetic. The prepared kit is the real tools/ops-live/kit.json;
an "authorized" kit is a synthetic copy whose pointers name no real comment.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("acceptance", HERE / "acceptance.py")
acceptance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acceptance)

KIT_TEXT = (HERE / "kit.json").read_text()
POINTER = "https://github.com/jparker2006/ClosedWiz/issues/4001#issuecomment-{}"
DIGEST = "ab" * 32
MINUTE = 60_000
START = 1_800_000_000_000


def observed(n=1):
    return {"evidence_class": "observation", "source": POINTER.format(9000 + n),
            "digest": DIGEST}


def fixture():
    return {"evidence_class": "fixture", "source": "fixture:synthetic", "digest": DIGEST}


def authorized_kit():
    """The real kit (#2244's findings, J55/J56, the recorded grants including J60)
    with its one open precondition, #1110's posted evidence, met under a synthetic pointer."""
    kit = json.loads(KIT_TEXT)
    kit["status"] = "authorized"
    for n, (name, entry) in enumerate(kit["controls"]["permissions"].items()):
        if entry["needed"]:
            entry["granted"] = True
            entry["record"] = POINTER.format(100 + n)
            kit["read_back"][name] = DIGEST
    for entry in kit["start_after"]:
        entry["record"] = POINTER.format(210)
    return kit


def text(doc):
    return json.dumps(doc, indent=2)


def digest(kit_text):
    return hashlib.sha256(kit_text.encode()).hexdigest()


def op(n, action, ack=True, at=None):
    key = f"{n:064x}"
    at = n if at is None else at
    return {"operation_key": key, "intent_id": f"intent-{n}", "action": action,
            "request_id": f"req-{n}" if action in ("builder_start", "review_start") else None,
            "respawn": False,
            "start": START + at * MINUTE, "end": START + at * MINUTE + 30_000,
            "completion": "completed",
            "ack": {"operation_key": key, "intent_id": f"intent-{n}",
                    "recipient": "builder-span", "evidence": observed(n)} if ack else None}


def with_respawn(kit_text):
    """A lost builder start recovered by one counted J55 re-spawn of the same request."""
    doc = live_results(kit_text)
    lost = op(11, "builder_start", ack=False)
    lost["completion"] = "uncertain"
    again = op(11, "builder_start", at=13)
    again["respawn"] = True
    doc["operations"] += [lost, again]
    doc["respawns"] = 1
    return doc


def live_results(kit_text):
    """A consistent, fully passing synthetic live result for an authorized kit."""
    kit = json.loads(kit_text)
    steps = kit["controls"]["restoration"] + kit["controls"]["cleanup"]

    return {
        "format": "ops-live-results/1",
        "kit": digest(kit_text),
        "live": True,
        "repository": "openwizdev/livecheck-throwaway-1110",
        "window": {"start": START, "end": START + 60 * MINUTE},
        "threads": [
            {"alias": "builder-a", "role": "builder", "start": START, "end": START + 50 * MINUTE},
            {"alias": "reviewer-a", "role": "reviewer", "start": START + 5 * MINUTE,
             "end": START + 40 * MINUTE},
            {"alias": "standby-a", "role": "standby", "start": START + 10 * MINUTE,
             "end": START + 20 * MINUTE},
        ],
        "operations": [op(1, "builder_start"), op(3, "delivery"), op(5, "review_start"),
                       op(7, "grant", ack=False), op(9, "hold_release", ack=False)],
        "fencing": {"boundary": "effect", "evidence": [observed(20)]},
        "reviewer_output": {"access": "verified", "evidence": [observed(21)]},
        "verdicts": [{"reviewer": "reviewer-a", "verdict": "APPROVE", "comment": observed(50),
                      "thread_output": observed(51), "matches": True}],
        "respawns": 0,
        "cleanup": [{"step": s, "state": "done", "evidence": [observed(30 + i)]}
                    for i, s in enumerate(steps)],
        "claims": [{"claim": c, "status": "pass", "evidence": [observed(40 + i)]}
                   for i, c in enumerate(kit["claims"])],
        "measures": {m: {"value": 1, "denominator": 1} for m in kit["measures"]}
                    | {"duplicate_starts": {"value": 0, "denominator": 1}},
        "gaps": [],
    }


def prepared_results():
    """What an honest run against the prepared kit can say: nothing is proven."""
    doc = live_results(KIT_TEXT)
    doc["live"] = False
    doc["threads"], doc["operations"] = [], []
    doc["fencing"] = {"boundary": "unknown", "evidence": []}
    doc["reviewer_output"] = {"access": "unknown", "evidence": []}
    doc["verdicts"] = []
    doc["cleanup"] = [dict(c, state="accounted") for c in doc["cleanup"]]
    for claim in doc["claims"]:
        claim.update(status="unverified", evidence=[])
    doc["measures"] = {m: {"value": None, "denominator": None} for m in doc["measures"]}
    doc["gaps"] = ["no live run: every measure is unmeasured"] + [
        f"{m} unmeasured" for m in doc["measures"]]
    return doc


def refusals(kit_text, doc):
    return acceptance.check_results(kit_text, acceptance.read(text(doc)))


class Kit(unittest.TestCase):
    """AC1: absent authority leaves only a prepared kit."""

    def test_prepared_kit_passes_and_its_live_gate_is_closed(self):
        kit = acceptance.read(KIT_TEXT)
        self.assertEqual(acceptance.check_kit(kit), [])
        # The permissions are recorded and read back, #2244's findings, J55/J56 and
        # J60's thread grant are in: only #1110's run keeps the gate closed.
        self.assertEqual(acceptance.live_gate(kit), [
            "start_after #1110: not met: 0.0.13's timed live run has finished and its "
            "evidence is posted on #1110"])
        self.assertEqual(kit["cloud_threads"]["J60"], {
            "record": "https://github.com/jparker2006/ClosedWiz/issues/325#issuecomment-6874553811",
            "active": 3, "total": 6, "repository": "openwizdev/livecheck-throwaway-1110",
            "after": 1110})
        grant = "https://github.com/jparker2006/ClosedWiz/issues/325#issuecomment-6868136156"
        for name, entry in kit["controls"]["permissions"].items():
            with self.subTest(name):
                if name == "merge":
                    self.assertEqual(entry, {"needed": False, "granted": False, "record": None})
                else:
                    self.assertEqual(entry, {"needed": True, "granted": True, "record": grant})
        self.assertEqual(kit["cloud_threads"]["record"], grant)
        self.assertEqual(kit["test_repository"], "openwizdev/livecheck-throwaway-1110")
        found = kit["discovery_2244"]
        self.assertEqual(found["record"],
                         "https://github.com/jparker2006/ClosedWiz/issues/2244#issuecomment-6846689726")
        self.assertEqual([found[k] for k in ("lost_start_lookup", "negative_execution",
                                             "independent_wakes", "reviewer_own_output")],
                         ["absent", "absent", "documented", "absent"])

    def test_authorized_kit_without_authority_is_refused(self):
        cases = []
        kit = authorized_kit()
        kit["controls"]["permissions"]["live"].update(granted=False, record=None)
        cases.append(("no grants", kit, "permission live: not granted"))
        kit = json.loads(KIT_TEXT)
        kit["status"] = "authorized"
        cases.append(("#1110 still running", kit, "start_after #1110: not met: 0.0.13's timed "
                      "live run has finished and its evidence is posted on #1110"))
        kit = authorized_kit()
        kit["cloud_threads"]["J60"]["record"] = None
        cases.append(("J60 unanswered", kit, "cloud_threads: kit limits 3 active, 6 total exceed "
                      "the 2 Cloud threads granted (J60 not recorded)"))
        kit = authorized_kit()
        kit["cloud_threads"]["J60"]["total"] = 5
        cases.append(("J60 granted less", kit, "cloud_threads: kit limits 3 active, 6 total exceed "
                      "the 3 active, 5 total Cloud threads granted (J60)"))
        kit = authorized_kit()
        kit["read_back"]["write"] = None
        cases.append(("no read-back", kit, "permission write: record not read back"))
        kit = authorized_kit()
        kit["discovery_2244"]["reviewer_own_output"] = "unknown"
        cases.append(("#2244 unknown", kit, "discovery_2244.reviewer_own_output: unknown"))
        kit = authorized_kit()
        kit["discovery_2244"]["record"] = None
        cases.append(("#2244 unrecorded", kit, "discovery_2244: #2244 findings not recorded"))
        for name, kit, reason in cases:
            with self.subTest(name):
                self.assertIn(f"status: authorized but live gate closed: {reason}",
                              acceptance.check_kit(kit))
        self.assertEqual(acceptance.check_kit(authorized_kit()), [])
        self.assertEqual(acceptance.live_gate(authorized_kit()), [])

    def test_kit_shape_is_strict(self):
        cases = []
        for key in ("controls", "discovery_2244", "claims", "measures", "read_back"):
            kit = json.loads(KIT_TEXT)
            del kit[key]
            cases.append((f"no {key}", kit, f"{key}: missing"))
        kit = json.loads(KIT_TEXT)
        kit["controls"]["limits"]["threads"]["active"] = 0
        cases.append(("controls refused", kit, "controls.limits.threads.active: not a positive integer"))
        kit = json.loads(KIT_TEXT)
        kit["claims"] = ["P1", "P2"]
        cases.append(("claims", kit, "claims: not exactly P1-P8"))
        kit = json.loads(KIT_TEXT)
        kit["discovery_2244"]["affects"] = ["P3", "P4"]
        cases.append(("assumption narrowed", kit, "discovery_2244.affects: not exactly P3, P4, P5, P7"))
        kit = json.loads(KIT_TEXT)
        kit["permitted_effects"].append("merge on a test-owned pull request")
        cases.append(("merge without grant", kit, "permitted_effects: merge without a merge grant"))
        kit = json.loads(KIT_TEXT)
        kit["permitted_effects"].append("deploy to production")
        cases.append(("unknown effect", kit, "permitted_effects[7]: not a contract action"))
        kit = json.loads(KIT_TEXT)
        kit["surprise"] = 1
        cases.append(("unknown key", kit, "surprise: unknown key"))
        kit = json.loads(KIT_TEXT)
        kit["discovery_2244"]["independent_wakes"] = "maybe"
        cases.append(("finding vocabulary", kit,
                      "discovery_2244.independent_wakes: not unknown, documented, observed or absent"))
        kit = json.loads(KIT_TEXT)
        kit["discovery_2244"]["decisions"] = "J55 and J56"
        cases.append(("decisions pointer", kit,
                      "discovery_2244.decisions: not a private-record comment pointer"))
        for key in ("J55", "J56", "negative_execution", "decisions"):
            kit = json.loads(KIT_TEXT)
            del kit["discovery_2244"][key]
            cases.append((f"no {key}", kit, f"discovery_2244.{key}: missing"))
        for bound in (2, 0, True, None):
            kit = json.loads(KIT_TEXT)
            kit["discovery_2244"]["J55"]["max_per_lost_start"] = bound
            cases.append((f"J55 bound {bound!r}", kit,
                          "discovery_2244.J55.max_per_lost_start: not exactly 1"))
        kit = json.loads(KIT_TEXT)
        kit["discovery_2244"]["J55"]["actions"] = ["builder_start", "review_start", "delivery"]
        cases.append(("J55 widened", kit,
                      "discovery_2244.J55.actions: not exactly builder_start, review_start"))
        kit = json.loads(KIT_TEXT)
        kit["discovery_2244"]["J55"]["never_executed"] = "provable"
        cases.append(("J55 never executed", kit, "discovery_2244.J55.never_executed: not unprovable"))
        kit = json.loads(KIT_TEXT)
        kit["discovery_2244"]["J56"]["github_comment_alone"] = "sometimes"
        cases.append(("J56 comment alone", kit, "discovery_2244.J56.github_comment_alone: not never"))
        kit = json.loads(KIT_TEXT)
        kit["discovery_2244"]["J56"]["verdict_source"] = "github_comment"
        cases.append(("J56 source", kit,
                      "discovery_2244.J56.verdict_source: not thread_output_by_id"))
        for repository in ("jparker2006/ClosedWiz", "openwizdev/openwiz", "not a repository"):
            kit = json.loads(KIT_TEXT)
            kit["test_repository"] = repository
            cases.append((f"test repository {repository}", kit,
                          "test_repository: not a throwaway owner/name repository"))
        kit = json.loads(KIT_TEXT)
        kit["start_after"] = []
        cases.append(("no #1110 precondition", kit, "start_after: not exactly #1110's posted evidence"))
        kit = json.loads(KIT_TEXT)
        kit["start_after"][0]["record"] = "posted"
        cases.append(("#1110 record", kit, "start_after[0].record: not a private-record comment pointer"))
        kit = json.loads(KIT_TEXT)
        kit["cloud_threads"]["granted"] = 0
        cases.append(("no grant", kit, "cloud_threads.granted: not a positive integer"))
        kit = json.loads(KIT_TEXT)
        kit["cloud_threads"]["roles"] = ["builder", "pilot"]
        cases.append(("unknown role", kit, "cloud_threads.roles: not kit host roles"))
        kit = json.loads(KIT_TEXT)
        kit["cloud_threads"]["J60"]["record"] = "yes"
        cases.append(("J60 record", kit, "cloud_threads.J60.record: not a private-record comment pointer"))
        kit = json.loads(KIT_TEXT)
        kit["cloud_threads"]["J60"]["repository"] = "jparker2006/ClosedWiz"
        cases.append(("J60 elsewhere", kit, "cloud_threads.J60.repository: not the kit's test_repository"))
        kit = json.loads(KIT_TEXT)
        kit["cloud_threads"]["J60"]["after"] = 1111
        cases.append(("J60 unordered", kit, "cloud_threads.J60.after: not a start_after ticket"))
        kit = json.loads(KIT_TEXT)
        kit["start_after"] = []
        cases.append(("#1110 ordering dropped under J60", kit,
                      "cloud_threads.J60.after: not a start_after ticket"))
        kit = json.loads(KIT_TEXT)
        kit["permitted_effects"] = [e for e in kit["permitted_effects"] if "J55" not in e]
        cases.append(("re-spawn not a permitted effect", kit,
                      "permitted_effects: no counted at-most-once J55 re-spawn"))
        for name, kit, reason in cases:
            with self.subTest(name):
                self.assertIn(reason, acceptance.check_kit(kit))
        with self.assertRaises(acceptance.Refused):
            acceptance.read('{"format": 1, "format": 2}')


class Results(unittest.TestCase):
    """AC2: offline red-first result validation."""

    def setUp(self):
        self.kit_text = text(authorized_kit())

    def test_consistent_results_pass(self):
        self.assertEqual(refusals(self.kit_text, live_results(self.kit_text)), [])
        self.assertEqual(refusals(KIT_TEXT, prepared_results()), [])

    def test_fabricated_concurrency(self):
        cases = []
        doc = live_results(self.kit_text)
        doc["threads"].append({"alias": "builder-b", "role": "builder",
                               "start": START + 12 * MINUTE, "end": START + 15 * MINUTE})
        cases.append(("four active threads", doc, "threads: 4 active at once exceeds 3"))
        doc = live_results(self.kit_text)
        doc["threads"] += [{"alias": f"t-{i}", "role": "builder", "start": START + (51 + i) * MINUTE,
                            "end": START + (51 + i) * MINUTE + 1} for i in range(4)]
        cases.append(("seven threads", doc, "threads: 7 exceeds total 6"))
        doc = live_results(self.kit_text)
        doc["operations"][1]["start"] = doc["operations"][0]["start"] + 1
        doc["operations"][2]["start"] = doc["operations"][0]["start"] + 2
        cases.append(("three active operations", doc, "operations: 3 active at once exceeds 2"))
        doc = live_results(self.kit_text)
        doc["threads"][0]["start"] = START - 1
        cases.append(("before the window", doc, "threads[0]: outside the run window"))
        doc = live_results(self.kit_text)
        doc["threads"][1]["end"] = doc["threads"][1]["start"] - 1
        cases.append(("ends before it starts", doc, "threads[1]: ends before it starts"))
        doc = live_results(self.kit_text)
        doc["window"]["end"] = START + 181 * MINUTE
        cases.append(("too long", doc, "window: longer than 180 minutes"))
        doc = live_results(self.kit_text)
        doc["threads"][2]["alias"] = "builder-a"
        cases.append(("one thread counted twice", doc, "threads[2]: duplicate alias"))
        for name, doc, reason in cases:
            with self.subTest(name):
                self.assertIn(reason, refusals(self.kit_text, doc))

    def test_missing_acknowledgements(self):
        cases = []
        doc = live_results(self.kit_text)
        doc["operations"][1]["ack"] = None
        cases.append(("no ack", doc, "operations[1]: completed delivery without an acknowledgement"))
        doc = live_results(self.kit_text)
        doc["operations"][1]["ack"]["operation_key"] = "f" * 64
        cases.append(("another key", doc, "operations[1].ack: names another operation"))
        doc = live_results(self.kit_text)
        doc["operations"][2]["ack"]["intent_id"] = "intent-99"
        cases.append(("another intent", doc, "operations[2].ack: names another operation"))
        doc = live_results(self.kit_text)
        doc["operations"][1]["ack"]["evidence"] = fixture()
        cases.append(("fixture ack", doc, "operations[1].ack: not observed"))
        doc = live_results(self.kit_text)
        doc["operations"] = [o for o in doc["operations"] if o["action"] != "delivery"]
        cases.append(("P4 with no delivery", doc, "claims P4: pass without an acknowledged delivery"))
        for name, doc, reason in cases:
            with self.subTest(name):
                self.assertIn(reason, refusals(self.kit_text, doc))

    def test_advisory_only_fencing(self):
        for boundary in ("advisory", "unknown"):
            doc = live_results(self.kit_text)
            doc["fencing"]["boundary"] = boundary
            with self.subTest(boundary):
                self.assertIn(f"claims P5: pass with {boundary} fencing", refusals(self.kit_text, doc))
        doc = live_results(self.kit_text)
        doc["fencing"]["evidence"] = [fixture()]
        self.assertIn("fencing: effect boundary not observed", refusals(self.kit_text, doc))
        doc = live_results(self.kit_text)
        doc["operations"].append(dict(doc["operations"][0], start=START + 55 * MINUTE,
                                      end=START + 56 * MINUTE))
        self.assertIn("operations: duplicate completed effect " + doc["operations"][0]["operation_key"],
                      refusals(self.kit_text, doc))

    def test_one_intent_bound_to_two_operation_keys(self):
        # R1: a second completed start of the same immutable intent under a
        # changed key must not dodge duplicate accounting (ops-dispatch v1).
        doc = live_results(self.kit_text)
        again = copy.deepcopy(doc["operations"][0])
        again["operation_key"] = again["ack"]["operation_key"] = "f" * 64
        again.update(start=START + 55 * MINUTE, end=START + 56 * MINUTE)
        doc["operations"].append(again)
        self.assertIn("operations[5]: intent intent-1 bound to another operation key",
                      refusals(self.kit_text, doc))
        # Distinct intents with distinct keys stay consistent.
        doc = live_results(self.kit_text)
        other = copy.deepcopy(doc["operations"][0])
        other.update(intent_id="intent-11", start=START + 55 * MINUTE, end=START + 56 * MINUTE)
        other["operation_key"] = "f" * 64
        other["ack"].update(operation_key="f" * 64, intent_id="intent-11")
        doc["operations"].append(other)
        self.assertEqual(refusals(self.kit_text, doc), [])

    def test_absent_reviewer_output_access(self):
        for access in ("absent", "unknown"):
            doc = live_results(self.kit_text)
            doc["reviewer_output"]["access"] = access
            with self.subTest(access):
                self.assertIn(f"claims P7: pass with {access} reviewer-output access",
                              refusals(self.kit_text, doc))
        kit = authorized_kit()
        kit["controls"]["permissions"]["merge"].update(needed=True, granted=True, record=POINTER.format(300))
        kit["read_back"]["merge"] = DIGEST
        kit["permitted_effects"].append("merge of a test-owned pull request")
        kit_text = text(kit)
        doc = live_results(kit_text)
        doc["operations"].append({"operation_key": "e" * 64, "intent_id": "intent-m", "action": "merge",
                                  "request_id": None, "respawn": False, "start": START + 55 * MINUTE, "end": START + 56 * MINUTE,
                                  "completion": "completed", "ack": None})
        self.assertEqual(refusals(kit_text, doc), [])
        unauthenticated = copy.deepcopy(doc)
        unauthenticated["verdicts"][0].update(thread_output=None, matches=False)
        self.assertIn("operations[5]: merge without an authenticated APPROVE verdict",
                      refusals(kit_text, unauthenticated))
        changes = copy.deepcopy(doc)
        changes["verdicts"][0]["verdict"] = "CHANGES"
        self.assertIn("operations[5]: merge without an authenticated APPROVE verdict",
                      refusals(kit_text, changes))
        doc["reviewer_output"] = {"access": "verified", "evidence": [fixture()]}
        self.assertIn("reviewer_output: access not observed", refusals(kit_text, doc))
        doc["reviewer_output"]["access"] = "absent"
        self.assertIn("operations[5]: merge without verified reviewer-output access",
                      refusals(kit_text, doc))

    def test_j55_counted_at_most_once_respawn(self):
        self.assertEqual(refusals(self.kit_text, with_respawn(self.kit_text)), [])
        reviewer = with_respawn(self.kit_text)
        for operation in reviewer["operations"][5:]:
            operation["action"] = "review_start"
        self.assertEqual(refusals(self.kit_text, reviewer), [])
        adjacent = with_respawn(self.kit_text)
        adjacent["operations"][6].update(start=START + 11 * MINUTE + 30_000,
                                         end=START + 12 * MINUTE)
        self.assertEqual(refusals(self.kit_text, adjacent), [])
        cases = []
        doc = with_respawn(self.kit_text)
        second = copy.deepcopy(doc["operations"][6])
        second.update(start=START + 15 * MINUTE, end=START + 15 * MINUTE + 30_000,
                      completion="uncertain", ack=None)
        doc["operations"].append(second)
        doc["respawns"] = 2
        cases.append(("second re-spawn", doc, "operations[7]: second re-spawn of intent-11"))
        # #2975: the issue's second attempt is uncertain and unflagged, so
        # neither completed-effect accounting nor flag counting catches it.
        doc = with_respawn(self.kit_text)
        second = copy.deepcopy(doc["operations"][6])
        second.update(completion="uncertain", ack=None, respawn=False,
                      start=START + 15 * MINUTE, end=START + 15 * MINUTE + 30_000)
        doc["operations"].append(second)
        cases.append(("unflagged second re-spawn", doc,
                      "operations[7]: second re-spawn of intent-11"))
        cases.append(("unflagged second still counted", doc,
                      "respawns: 1 but 2 re-spawns recorded"))
        counted = copy.deepcopy(doc)
        counted["respawns"] = 2
        cases.append(("count alone cannot classify recovery", counted,
                      "operations[7]: repeated spawn must set respawn true"))
        doc = with_respawn(self.kit_text)
        doc["operations"][6]["respawn"] = False
        doc["respawns"] = 0
        cases.append(("unflagged first recovery", doc,
                      "operations[6]: repeated spawn must set respawn true"))
        cases.append(("unflagged first still counted", doc,
                      "respawns: 0 but 1 re-spawns recorded"))
        for completion in ("completed", "refused"):
            doc = with_respawn(self.kit_text)
            doc["operations"][5]["completion"] = completion
            cases.append((f"original {completion}", doc,
                          "operations[6]: re-spawn without a lost start of intent-11"))
        # #2975: even a matching recovery ACK cannot change the original intent.
        for action in ("builder_start", "review_start"):
            doc = with_respawn(self.kit_text)
            for operation in doc["operations"][5:]:
                operation["action"] = action
            doc["operations"][6]["intent_id"] = "intent-99"
            doc["operations"][6]["ack"]["intent_id"] = "intent-99"
            cases.append((f"changed {action} origin intent", doc,
                          "operations[6]: re-spawn with another intent id"))
        # #2975: individually valid spans still contradict recovery order.
        # The first row is the issue's minute 10/10.5 reproduction; the
        # others straddle the uncertain original's end at minute 11.5.
        for name, start, end in (("before original", 10 * MINUTE, 10 * MINUTE + 30_000),
                                 ("overlapping original", 11 * MINUTE + 1, 12 * MINUTE),
                                 ("one millisecond early", 11 * MINUTE + 29_999, 12 * MINUTE)):
            doc = with_respawn(self.kit_text)
            doc["operations"][6].update(start=START + start, end=START + end)
            cases.append((name, doc,
                          "operations[6]: re-spawn before the original attempt ended"))
        doc = with_respawn(self.kit_text)
        del doc["respawns"]
        cases.append(("missing count", doc, "respawns: missing"))
        doc = with_respawn(self.kit_text)
        doc["respawns"] = 0
        cases.append(("under-counted", doc, "respawns: 0 but 1 re-spawns recorded"))
        doc = live_results(self.kit_text)
        doc["respawns"] = 1
        cases.append(("counted, none recorded", doc, "respawns: 1 but 0 re-spawns recorded"))
        doc = with_respawn(self.kit_text)
        doc["operations"].pop(5)
        cases.append(("no lost start", doc, "operations[5]: re-spawn without a lost start of intent-11"))
        doc = with_respawn(self.kit_text)
        doc["operations"][6]["request_id"] = "req-99"
        cases.append(("another request id", doc, "operations[6]: re-spawn with another request id"))
        doc = with_respawn(self.kit_text)
        doc["operations"][5]["completion"] = "reconciled_not_executed"
        cases.append(("never executed claimed", doc,
                      "operations[5]: builder_start recorded as never executed, which #2244 found unprovable"))
        doc = live_results(self.kit_text)
        doc["operations"][1]["respawn"] = True
        doc["respawns"] = 1
        cases.append(("re-spawned delivery", doc, "operations[1]: delivery is not a J55 re-spawn"))
        doc = live_results(self.kit_text)
        doc["operations"][1]["request_id"] = "req-x"
        cases.append(("request id on a delivery", doc, "operations[1].request_id: not null for delivery"))
        doc = live_results(self.kit_text)
        doc["operations"][0]["request_id"] = None
        cases.append(("spawn without a request id", doc,
                      "operations[0].request_id: not a non-empty printable ASCII string"))
        for name, doc, reason in cases:
            with self.subTest(name):
                self.assertIn(reason, refusals(self.kit_text, doc))

    def test_cloud_threads_within_the_recorded_grant(self):
        kit = authorized_kit()
        kit["cloud_threads"]["J60"]["record"] = None
        kit["status"] = "prepared"
        kit_text = text(kit)
        doc = live_results(kit_text)
        doc["live"] = False
        found = refusals(kit_text, doc)
        self.assertIn("threads: 3 Cloud threads active at once exceed the 2 granted", found)
        self.assertIn("threads: 3 Cloud threads exceed the 2 granted", found)
        doc["threads"].pop()
        self.assertEqual([r for r in refusals(kit_text, doc) if "Cloud threads" in r], [])
        kit["cloud_threads"]["roles"] = ["builder"]
        doc = live_results(text(kit))
        self.assertEqual([r for r in refusals(text(kit), doc) if "Cloud threads" in r], [])

    def test_run_only_on_the_throwaway_repository_after_1110(self):
        doc = live_results(self.kit_text)
        doc["repository"] = "jparker2006/ClosedWiz"
        self.assertIn("repository: not the kit's throwaway repository",
                      refusals(self.kit_text, doc))
        # J60's threads are granted, but a run before #1110's posted evidence is refused.
        kit = authorized_kit()
        kit["start_after"][0]["record"] = None
        self.assertIn("status: authorized but live gate closed: start_after #1110: not met: 0.0.13's "
                      "timed live run has finished and its evidence is posted on #1110",
                      acceptance.check_kit(kit))
        kit["status"] = "prepared"
        kit_text = text(kit)
        found = refusals(kit_text, live_results(kit_text))
        self.assertIn("live: start_after #1110 not met", found)
        self.assertEqual([r for r in found if "Cloud threads" in r], [])

    def test_j56_verdict_read_by_id(self):
        cases = []
        doc = live_results(self.kit_text)
        doc["verdicts"][0].update(thread_output=None, matches=False)
        cases.append(("GitHub comment alone", doc,
                      "claims P7: pass with verdicts[0] not authenticated by its reviewer's thread output"))
        doc = live_results(self.kit_text)
        doc["verdicts"][0]["matches"] = False
        cases.append(("mismatch", doc,
                      "claims P7: pass with verdicts[0] not authenticated by its reviewer's thread output"))
        doc = live_results(self.kit_text)
        doc["verdicts"][0]["thread_output"] = None
        cases.append(("matches without a read", doc,
                      "verdicts[0]: matches without its thread output read by id"))
        doc = live_results(self.kit_text)
        doc["verdicts"][0]["thread_output"] = fixture()
        cases.append(("fixture thread output", doc, "verdicts[0].thread_output: not observed"))
        doc = live_results(self.kit_text)
        doc["verdicts"][0]["reviewer"] = "builder-a"
        cases.append(("not a reviewer", doc, "verdicts[0].reviewer: not a reviewer thread"))
        doc = live_results(self.kit_text)
        doc["verdicts"][0]["verdict"] = "LGTM"
        cases.append(("verdict vocabulary", doc, "verdicts[0].verdict: not APPROVE or CHANGES"))
        doc = live_results(self.kit_text)
        doc["verdicts"] = []
        cases.append(("no verdict", doc, "claims P7: pass without an authenticated verdict"))
        for name, doc, reason in cases:
            with self.subTest(name):
                self.assertIn(reason, refusals(self.kit_text, doc))

    def test_unpermitted_effects(self):
        doc = live_results(self.kit_text)
        doc["operations"].append({"operation_key": "e" * 64, "intent_id": "intent-m", "action": "merge",
                                  "request_id": None, "respawn": False, "start": START + 55 * MINUTE, "end": START + 56 * MINUTE,
                                  "completion": "completed", "ack": None})
        self.assertIn("operations[5]: merge is not a permitted effect", refusals(self.kit_text, doc))

    def test_incomplete_cleanup(self):
        cases = []
        doc = live_results(self.kit_text)
        doc["cleanup"][0]["state"] = "pending"
        cases.append(("pending", doc, "cleanup[0]: not done or accounted for"))
        doc = live_results(self.kit_text)
        doc["cleanup"].pop()
        cases.append(("missing step", doc,
                      "cleanup: missing account for every test-owned branch and claim ref; refs are never deleted or reused"))
        doc = live_results(self.kit_text)
        doc["cleanup"][1]["evidence"] = []
        cases.append(("no evidence", doc, "cleanup[1]: no evidence"))
        doc = live_results(self.kit_text)
        doc["cleanup"].append(dict(doc["cleanup"][0]))
        cases.append(("twice", doc, "cleanup[6]: duplicate step"))
        doc = live_results(self.kit_text)
        doc["cleanup"][2]["step"] = "something else"
        cases.append(("unknown step", doc, "cleanup[2]: not a kit restoration or cleanup step"))
        doc = live_results(self.kit_text)
        doc["threads"][2]["end"] = None
        cases.append(("thread never ended", doc, "threads[2]: never ended"))
        for name, doc, reason in cases:
            with self.subTest(name):
                self.assertIn(reason, refusals(self.kit_text, doc))

    def test_false_live_passes(self):
        cases = []
        doc = prepared_results()
        doc["claims"][0].update(status="pass", evidence=[observed()])
        cases.append(("pass without a live run", KIT_TEXT, doc, "claims P1: pass without a live run"))
        doc = prepared_results()
        doc["live"] = True
        cases.append(("live under a prepared kit", KIT_TEXT, doc, "live: kit is not authorized"))
        doc = live_results(self.kit_text)
        doc["claims"][0]["evidence"] = [fixture()]
        cases.append(("fixture-only pass", self.kit_text, doc, "claims P1: pass without observed live evidence"))
        doc = live_results(self.kit_text)
        doc["claims"][5]["evidence"] = [dict(observed(), evidence_class="review")]
        cases.append(("review-only pass", self.kit_text, doc, "claims P6: pass without observed live evidence"))
        doc = live_results(self.kit_text)
        doc["claims"][1]["evidence"] = [dict(observed(), source="fixture:looks-live")]
        cases.append(("observation from a fixture", self.kit_text, doc,
                      "claims[1].evidence[0]: observation without a private-record pointer"))
        kit = authorized_kit()
        kit["discovery_2244"]["independent_wakes"] = "unknown"
        kit["status"] = "prepared"
        kit_text = text(kit)
        doc = live_results(kit_text)
        doc["live"] = False
        cases.append(("#2244 still unknown", kit_text, doc, "claims P3: pass while #2244 findings are unknown"))
        doc = live_results(self.kit_text)
        doc["kit"] = "0" * 64
        cases.append(("another kit", self.kit_text, doc, "kit: digest does not match the kit"))
        doc = live_results(self.kit_text)
        doc["claims"] = doc["claims"][:7]
        cases.append(("claim dropped", self.kit_text, doc, "claims: not exactly P1-P8 in order"))
        doc = live_results(self.kit_text)
        doc["measures"]["recovery_time_ms"] = {"value": 5, "denominator": None}
        cases.append(("no denominator", self.kit_text, doc,
                      "measures.recovery_time_ms: value without a positive denominator"))
        doc = live_results(self.kit_text)
        doc["measures"]["release_delay_ms"] = {"value": None, "denominator": None}
        cases.append(("silent gap", self.kit_text, doc, "measures.release_delay_ms: unmeasured but not in gaps"))
        doc = live_results(self.kit_text)
        doc["operations"].append(dict(doc["operations"][0], start=START + 55 * MINUTE,
                                      end=START + 56 * MINUTE))
        cases.append(("duplicates under-reported", self.kit_text, doc,
                      "measures.duplicate_starts: 0 but 1 duplicate builder start recorded"))
        for name, kit_text, doc, reason in cases:
            with self.subTest(name):
                self.assertIn(reason, refusals(kit_text, doc))

    def test_results_shape_is_strict(self):
        doc = live_results(self.kit_text)
        doc["effects_enabled"] = True
        self.assertIn("effects_enabled: unknown key", refusals(self.kit_text, doc))
        doc = live_results(self.kit_text)
        doc["live"] = 1
        self.assertIn("live: not true or false", refusals(self.kit_text, doc))
        doc = live_results(self.kit_text)
        doc["operations"][0]["completion"] = "done"
        self.assertIn("operations[0].completion: not a contract completion state",
                      refusals(self.kit_text, doc))


class WrongTypes(unittest.TestCase):
    """A wrong-typed value anywhere is refused, never a crash or a pass."""

    def test_every_node_replaced(self):
        kit_text = text(authorized_kit())

        def paths(node, here=()):
            yield here
            items = node.items() if isinstance(node, dict) else \
                enumerate(node) if isinstance(node, list) else ()
            for key, child in items:
                yield from paths(child, here + (key,))

        for base in (live_results(kit_text), with_respawn(kit_text)):
            self.replace_every_node(kit_text, base, paths)

    def replace_every_node(self, kit_text, base, paths):
        for path in list(paths(base))[1:]:
            for value in (None, [], {}, [1], 1.5, True):
                doc = copy.deepcopy(base)
                parent = doc
                for key in path[:-1]:
                    parent = parent[key]
                if type(parent[path[-1]]) is type(value) and parent[path[-1]] == value:
                    continue
                parent[path[-1]] = value
                with self.subTest(path=path, value=value):
                    result = refusals(kit_text, doc)
                    if value != [] or path[-1] not in ("gaps", "evidence", "threads", "operations"):
                        self.assertNotEqual(result, [])


class Command(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-I", str(HERE / "acceptance.py"), *args],
                              capture_output=True, text=True)

    def test_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = Path(tmp, "results.json")
            results.write_text(text(prepared_results()))
            ok = self.run_cli("kit", str(HERE / "kit.json"))
            self.assertEqual(ok.returncode, 0, ok.stderr)
            self.assertIn("live gate: closed", ok.stdout)
            ok = self.run_cli("results", str(HERE / "kit.json"), str(results))
            self.assertEqual(ok.returncode, 0, ok.stderr)
            self.assertIn("P5: unverified", ok.stdout)
            bad = prepared_results()
            bad["claims"][4]["status"] = "pass"
            results.write_text(text(bad))
            refused = self.run_cli("results", str(HERE / "kit.json"), str(results))
            self.assertEqual(refused.returncode, 1)
            self.assertIn("refused: claims P5: pass without a live run", refused.stderr)
            self.assertEqual(self.run_cli("kit").returncode, 2)
            self.assertEqual(self.run_cli("kit", str(Path(tmp, "absent.json"))).returncode, 2)


if __name__ == "__main__":
    unittest.main()
