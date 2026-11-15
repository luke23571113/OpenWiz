#!/usr/bin/env python3
"""Offline kit gate and result validator for #2190's bounded acceptance kit (OB8).

python3 -I tools/ops-live/acceptance.py kit <kit.json>
python3 -I tools/ops-live/acceptance.py results <kit.json> <results.json>

Exit 0: consistent; 1: refused (every refusal on stderr); 2: usage or an
unreadable file. Reads only the named files: no network, GitHub, room-cli,
thread or write. A pass is never permission and never a live result: a live
claim still needs its observed evidence read back and independently reviewed.
The kit's controls are checked by #2219's controls/kit.py, unchanged.
"""
import hashlib
import importlib.util
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True

_SPEC = importlib.util.spec_from_file_location(
    "controls_kit", Path(__file__).resolve().parent / "controls" / "kit.py")
controls = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(controls)
Refused = controls.Refused
read = controls.read
POINTER = controls.POINTER
MISSING = object()

KIT_FORMAT = "ops-live-kit/1"
RESULTS_FORMAT = "ops-live-results/1"
CLAIMS = ("P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8")
# #2244's PC discovery findings (kit section discovery_2244). While any is
# unknown or its record is missing, the claims below cannot pass and the live
# gate stays closed. "documented" is help-only: the live run must observe it.
DISCOVERY = ("lost_start_lookup", "negative_execution", "independent_wakes", "reviewer_own_output")
FINDINGS = ("unknown", "documented", "observed", "absent")
DISCOVERY_AFFECTS = ("P3", "P4", "P5", "P7")
# J55: a lost start may be re-spawned once with the same request id, counted.
SPAWNS = ("builder_start", "review_start")
# J56: a verdict counts only when it matches its reviewer thread's own output read by id.
VERDICTS = ("APPROVE", "CHANGES")
# Never a throwaway: the real repositories under test.
REAL_REPOSITORIES = ("jparker2006/closedwiz", "openwizdev/openwiz")
REPOSITORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+")
MEASURES = ("grant_wait_ms", "review_start_delay_ms", "oldest_pending_message_age_ms",
            "release_delay_ms", "recovery_time_ms", "duplicate_starts",
            "incorrect_grants", "incorrect_releases")
# ops-dispatch v1 intent actions and completion states.
ACTIONS = ("builder_start", "review_start", "delivery", "hold_release", "merge", "grant", "audit")
COMPLETIONS = ("completed", "superseded", "uncertain", "reconciled_not_executed",
               "disabled", "refused")
ROUTED = ("builder_start", "review_start", "delivery")  # completion needs the recipient's ACK
EVIDENCE_CLASSES = ("fixture", "observation", "review")
KIT_TOP = ("format", "status", "discovery_2244", "start_after", "test_repository",
           "cloud_threads", "controls", "read_back", "host_roles", "cloud_exposure",
           "permitted_effects", "claims", "measures")
RESULTS_TOP = ("format", "kit", "live", "repository", "window", "threads", "operations",
               "respawns", "fencing", "reviewer_output", "verdicts", "cleanup", "claims",
               "measures", "gaps")


def _text(value):
    return isinstance(value, str) and controls._printable(value)


def _hex64(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _pointer(value, nullable=False):
    return (nullable and value is None) or (isinstance(value, str) and POINTER.fullmatch(value) is not None)


def _positive(value):
    return type(value) is int and 0 < value <= 9007199254740991


def _keys(doc, keys, path, out):
    if not isinstance(doc, dict):
        out.append(f"{path}: not an object")
        return False
    for key in doc:
        if key not in keys:
            out.append(f"{(path + '.') if path else ''}{key}: unknown key")
    for key in keys:
        if key not in doc:
            out.append(f"{(path + '.') if path else ''}{key}: missing")
    return True


# ---- the kit ---------------------------------------------------------------

def check_kit(doc):
    """Every refusal of a prepared or authorized kit; empty is a pass."""
    out = []
    if not _keys(doc, KIT_TOP, "", out):
        return ["kit: not an object"]
    if doc.get("format", MISSING) is not MISSING and doc["format"] != KIT_FORMAT:
        out.append(f"format: not {KIT_FORMAT}")
    if "controls" in doc:
        out += [f"controls.{r}" for r in controls.check(doc["controls"])]
    if "discovery_2244" in doc:
        _discovery(doc["discovery_2244"], out)
    if "start_after" in doc:
        _start_after(doc["start_after"], out)
    if "test_repository" in doc:
        repository = doc["test_repository"]
        heads = doc.get("controls", {}).get("candidates", {}).get("heads", []) \
            if isinstance(doc.get("controls"), dict) else []
        real = {r.lower() for r in REAL_REPOSITORIES} | {h["repository"].lower() for h in heads if isinstance(h, dict)
                                        and isinstance(h.get("repository"), str)} \
            if isinstance(heads, list) else {r.lower() for r in REAL_REPOSITORIES}
        if not (isinstance(repository, str) and REPOSITORY.fullmatch(repository)) \
                or repository.lower() in real:
            out.append("test_repository: not a throwaway owner/name repository")
    if "cloud_threads" in doc:
        _cloud_threads(doc, out)
    if "read_back" in doc and _keys(doc["read_back"], controls.CLASSES, "read_back", out):
        for name, value in doc["read_back"].items():
            if value is not None and not _hex64(value):
                out.append(f"read_back.{name}: not null or a sha256 digest")
    if "host_roles" in doc and _keys(doc["host_roles"], ("primary", "standby", "builder", "reviewer"),
                                     "host_roles", out):
        for name, value in doc["host_roles"].items():
            if not _text(value):
                out.append(f"host_roles.{name}: not a non-empty printable ASCII string")
    if "cloud_exposure" in doc and not _text(doc["cloud_exposure"]):
        out.append("cloud_exposure: not a non-empty printable ASCII string")
    effects = doc.get("permitted_effects")
    if "permitted_effects" in doc:
        if not isinstance(effects, list) or not effects:
            out.append("permitted_effects: not a non-empty list")
        else:
            for i, effect in enumerate(effects):
                if not _text(effect) or effect.split()[0] not in ACTIONS:
                    out.append(f"permitted_effects[{i}]: not a contract action")
            if "merge" in _permitted(doc) and not _granted(doc, "merge"):
                out.append("permitted_effects: merge without a merge grant")
            if not any(_text(e) and "(J55)" in e for e in effects):
                out.append("permitted_effects: no counted at-most-once J55 re-spawn")
    if "claims" in doc and doc["claims"] != list(CLAIMS):
        out.append("claims: not exactly P1-P8")
    if "measures" in doc and doc["measures"] != list(MEASURES):
        out.append("measures: not exactly the eight measures")
    status = doc.get("status")
    if status not in ("prepared", "authorized") and "status" in doc:
        out.append("status: not prepared or authorized")
    if status == "authorized" and not out:
        out += [f"status: authorized but live gate closed: {r}" for r in live_gate(doc)]
    return out


def _discovery(discovery, out):
    if not _keys(discovery, ("record", "decisions", "affects", "J55", "J56") + DISCOVERY,
                 "discovery_2244", out):
        return
    if not _pointer(discovery.get("record"), nullable=True):
        out.append("discovery_2244.record: not a private-record comment pointer")
    if "decisions" in discovery and not _pointer(discovery["decisions"]):
        out.append("discovery_2244.decisions: not a private-record comment pointer")
    for name in DISCOVERY:
        if discovery.get(name, "unknown") not in FINDINGS:
            out.append(f"discovery_2244.{name}: not unknown, documented, observed or absent")
    if "affects" in discovery and discovery["affects"] != list(DISCOVERY_AFFECTS):
        out.append("discovery_2244.affects: not exactly " + ", ".join(DISCOVERY_AFFECTS))
    j55 = discovery.get("J55")
    if "J55" in discovery and _keys(j55, ("spawn", "actions", "max_per_lost_start",
                                          "never_executed"), "discovery_2244.J55", out):
        if not _text(j55.get("spawn")):
            out.append("discovery_2244.J55.spawn: not a non-empty printable ASCII string")
        if j55.get("actions") != list(SPAWNS):
            out.append("discovery_2244.J55.actions: not exactly " + ", ".join(SPAWNS))
        if type(j55.get("max_per_lost_start")) is not int or j55["max_per_lost_start"] != 1:
            out.append("discovery_2244.J55.max_per_lost_start: not exactly 1")
        if j55.get("never_executed") != "unprovable":
            out.append("discovery_2244.J55.never_executed: not unprovable")
    j56 = discovery.get("J56")
    if "J56" in discovery and _keys(j56, ("verdict_source", "github_comment_alone"),
                                    "discovery_2244.J56", out):
        if j56.get("verdict_source") != "thread_output_by_id":
            out.append("discovery_2244.J56.verdict_source: not thread_output_by_id")
        if j56.get("github_comment_alone") != "never":
            out.append("discovery_2244.J56.github_comment_alone: not never")


def _start_after(entries, out):
    """Runs that must finish, with their evidence posted, before this one starts."""
    if not isinstance(entries, list):
        out.append("start_after: not a list")
        return
    for i, entry in enumerate(entries):
        p = f"start_after[{i}]"
        if not _keys(entry, ("ticket", "condition", "record"), p, out):
            continue
        if not _positive(entry.get("ticket")):
            out.append(f"{p}.ticket: not a positive integer")
        if not _text(entry.get("condition")):
            out.append(f"{p}.condition: not a non-empty printable ASCII string")
        if not _pointer(entry.get("record"), nullable=True):
            out.append(f"{p}.record: not a private-record comment pointer")
    if not any(isinstance(e, dict) and e.get("ticket") == 1110 for e in entries):
        out.append("start_after: not exactly #1110's posted evidence")


def _cloud_threads(doc, out):
    """The recorded Cloud-thread grant; J60's record, once set, replaces it, only in
    its throwaway repository and only after its named run."""
    grant, roles = doc["cloud_threads"], doc.get("host_roles")
    if not _keys(grant, ("record", "granted", "roles", "J60"), "cloud_threads", out):
        return
    if not _pointer(grant.get("record")):
        out.append("cloud_threads.record: not a private-record comment pointer")
    if not _positive(grant.get("granted")):
        out.append("cloud_threads.granted: not a positive integer")
    names = grant.get("roles")
    if not (isinstance(names, list) and names and isinstance(roles, dict)
            and all(isinstance(r, str) and r in roles for r in names)
            and len(set(names)) == len(names)):
        out.append("cloud_threads.roles: not kit host roles")
    j60 = grant.get("J60")
    if _keys(j60, ("record", "active", "total", "repository", "after"), "cloud_threads.J60", out):
        if not _pointer(j60.get("record"), nullable=True):
            out.append("cloud_threads.J60.record: not a private-record comment pointer")
        for name in ("active", "total"):
            if not _positive(j60.get(name)):
                out.append(f"cloud_threads.J60.{name}: not a positive integer")
        if j60.get("repository") != doc.get("test_repository"):
            out.append("cloud_threads.J60.repository: not the kit's test_repository")
        after = doc.get("start_after")
        if not (_positive(j60.get("after")) and isinstance(after, list) and any(
                isinstance(e, dict) and e.get("ticket") == j60["after"] for e in after)):
            out.append("cloud_threads.J60.after: not a start_after ticket")


def _thread_grant(kit):
    """(active, total, wording) of the Cloud threads the recorded grant allows."""
    grant = kit["cloud_threads"]
    if grant["J60"]["record"] is None:
        n = grant["granted"]
        return n, n, f"{n} Cloud threads granted (J60 not recorded)"
    j60 = grant["J60"]
    return j60["active"], j60["total"], f"{j60['active']} active, {j60['total']} total Cloud threads granted (J60)"


def _granted(kit, name):
    controls_doc = kit.get("controls")
    permissions = controls_doc.get("permissions") if isinstance(controls_doc, dict) else None
    entry = permissions.get(name) if isinstance(permissions, dict) else None
    return isinstance(entry, dict) and entry.get("granted") is True


def _permitted(kit):
    effects = kit.get("permitted_effects")
    return {e.split()[0] for e in effects if _text(e)} if isinstance(effects, list) else set()


def live_gate(doc):
    """Why no live, machine, write, activation, spending or merge step may start.

    Offline only: a digest in read_back says an agent read the record back; this
    function cannot read it again. Empty means the gate is open on paper.
    """
    reasons = []
    for name in controls.CLASSES:
        entry = doc["controls"]["permissions"][name]
        if not entry["needed"]:
            continue
        if not entry["granted"]:
            reasons.append(f"permission {name}: not granted")
        elif doc["read_back"][name] is None:
            reasons.append(f"permission {name}: record not read back")
    discovery = doc["discovery_2244"]
    if discovery["record"] is None:
        reasons.append("discovery_2244: #2244 findings not recorded")
    for name in DISCOVERY:
        if discovery[name] == "unknown":
            reasons.append(f"discovery_2244.{name}: unknown")
    reasons += _unmet(doc)
    active, total, wording = _thread_grant(doc)
    limits = doc["controls"]["limits"]["threads"]
    if limits["active"] > active or limits["total"] > total:
        reasons.append(f"cloud_threads: kit limits {limits['active']} active, {limits['total']} "
                       f"total exceed the {wording}")
    return reasons


def _unmet(kit):
    return [f"start_after #{e['ticket']}: not met: {e['condition']}"
            for e in kit["start_after"] if e["record"] is None]


def _unknown_2244(kit):
    d = kit["discovery_2244"]
    return d["record"] is None or any(d[name] == "unknown" for name in DISCOVERY)


# ---- the results -----------------------------------------------------------

def _evidence(entry, path, out):
    if not _keys(entry, ("evidence_class", "source", "digest"), path, out):
        return None
    if entry.get("evidence_class") not in EVIDENCE_CLASSES:
        out.append(f"{path}.evidence_class: not fixture, observation or review")
    if not _hex64(entry.get("digest")):
        out.append(f"{path}.digest: not a sha256 digest")
    source = entry.get("source")
    if entry.get("evidence_class") == "fixture":
        if not (_text(source) and source.startswith("fixture:")):
            out.append(f"{path}: fixture without a fixture: source")
    elif not (isinstance(source, str) and POINTER.fullmatch(source)):
        out.append(f"{path}: {entry.get('evidence_class')} without a private-record pointer")
    return entry


def _evidence_list(parent, path, out):
    value = parent.get("evidence", [])
    if not isinstance(value, list):
        out.append(f"{path}.evidence: not a list")
        return []
    return [e for i, e in enumerate(value) if _evidence(e, f"{path}.evidence[{i}]", out)]


def _observed(entries):
    return any(e.get("evidence_class") == "observation" and isinstance(e.get("source"), str)
               and POINTER.fullmatch(e["source"]) for e in entries)


def _time(value):
    return type(value) is int and 0 <= value <= 9007199254740991


def _intervals(items, path, window, out, alias=None):
    """Valid (start, end) spans, refusing impossible or out-of-window times."""
    spans, seen = [], set()
    for i, item in enumerate(items):
        p = f"{path}[{i}]"
        if alias:
            name = item.get(alias)
            if not _text(name):
                out.append(f"{p}.{alias}: not a non-empty printable ASCII string")
            elif name in seen:
                out.append(f"{p}: duplicate alias")
            else:
                seen.add(name)
        start, end = item.get("start"), item.get("end")
        if not _time(start):
            out.append(f"{p}.start: not a time in milliseconds")
            continue
        if end is None:
            out.append(f"{p}: never ended")
            end = window[1] if window else start
        elif not _time(end):
            out.append(f"{p}.end: not a time in milliseconds")
            continue
        elif end < start:
            out.append(f"{p}: ends before it starts")
            continue
        if window and (start < window[0] or end > window[1]):
            out.append(f"{p}: outside the run window")
        spans.append((start, end))
    return spans


def _peak(spans):
    events = sorted([(s, 1) for s, _ in spans] + [(e, -1) for _, e in spans],
                    key=lambda ev: (ev[0], ev[1]))  # an end at t frees before a start at t
    peak = active = 0
    for _, step in events:
        active += step
        peak = max(peak, active)
    return peak


def _bounds(spans, count, bound, path, out):
    peak = _peak(spans)
    if peak > bound["active"]:
        out.append(f"{path}: {peak} active at once exceeds {bound['active']}")
    if count > bound["total"]:
        out.append(f"{path}: {count} exceeds total {bound['total']}")


def check_results(kit_text, doc):
    """Every refusal of a results document against its kit; empty is a pass."""
    try:
        kit = read(kit_text)
    except Refused as refused:
        return [f"kit: {refused}"]
    kit_out = check_kit(kit)
    if kit_out:
        return [f"kit: {r}" for r in kit_out]
    out = []
    if not _keys(doc, RESULTS_TOP, "", out):
        return ["results: not an object"]
    if doc.get("format") != RESULTS_FORMAT:
        out.append(f"format: not {RESULTS_FORMAT}")
    if doc.get("kit") != hashlib.sha256(kit_text.encode()).hexdigest():
        out.append("kit: digest does not match the kit")
    live = doc.get("live")
    if type(live) is not bool:
        out.append("live: not true or false")
    elif live and kit["status"] != "authorized":
        out.append("live: kit is not authorized")
    if live is True:
        out += [f"live: start_after #{e['ticket']} not met" for e in kit["start_after"]
                if e["record"] is None]
    if doc.get("repository") != kit["test_repository"]:
        out.append("repository: not the kit's throwaway repository")
    limits = kit["controls"]["limits"]

    window = None
    w = doc.get("window")
    if _keys(w, ("start", "end"), "window", out):
        if not (_time(w.get("start")) and _time(w.get("end"))) or w["end"] < w["start"]:
            out.append("window: not a start and end in milliseconds")
        else:
            window = (w["start"], w["end"])
            if w["end"] - w["start"] > limits["duration_minutes"] * 60_000:
                out.append(f"window: longer than {limits['duration_minutes']} minutes")

    threads = doc.get("threads")
    if not isinstance(threads, list):
        out.append("threads: not a list")
        threads = []
    for i, t in enumerate(threads):
        if _keys(t, ("alias", "role", "start", "end"), f"threads[{i}]", out) and \
                not (_text(t.get("role")) and t["role"] in kit["host_roles"]):
            out.append(f"threads[{i}].role: not a kit host role")
    threads = [t for t in threads if isinstance(t, dict)]
    _bounds(_intervals(threads, "threads", window, out, alias="alias"), len(threads),
            limits["threads"], "threads", out)
    roles = kit["cloud_threads"]["roles"]
    cloud = [t for t in threads if isinstance(t.get("role"), str) and t["role"] in roles]
    active, total, _ = _thread_grant(kit)
    peak = _peak(_intervals(cloud, "threads", window, []))
    if peak > active:
        out.append(f"threads: {peak} Cloud threads active at once exceed the {active} granted")
    if len(cloud) > total:
        out.append(f"threads: {len(cloud)} Cloud threads exceed the {total} granted")

    operations = doc.get("operations")
    if not isinstance(operations, list):
        out.append("operations: not a list")
        operations = []
    ops = []
    bound = {}  # intent_id -> operation_key: one immutable intent, one stable key
    starts, respawned = {}, {}  # J55: operation_key -> first spawn; -> repeat count
    for i, op in enumerate(operations):
        p = f"operations[{i}]"
        if not _keys(op, ("operation_key", "intent_id", "action", "request_id", "respawn",
                          "start", "end", "completion", "ack"), p, out):
            continue
        ops.append((i, op))
        intent, key = op.get("intent_id"), op.get("operation_key")
        if _text(intent) and _hex64(key):
            if bound.setdefault(intent, key) != key:
                out.append(f"{p}: intent {intent} bound to another operation key")
        if not _hex64(op.get("operation_key")):
            out.append(f"{p}.operation_key: not a sha256 digest")
        if not _text(op.get("intent_id")):
            out.append(f"{p}.intent_id: not a non-empty printable ASCII string")
        action, completion = op.get("action"), op.get("completion")
        if action not in ACTIONS:
            out.append(f"{p}.action: not a contract action")
        if completion not in COMPLETIONS:
            out.append(f"{p}.completion: not a contract completion state")
        _respawn(kit, i, op, starts, respawned, out)
        ack = op.get("ack")
        if ack is not None and _keys(ack, ("operation_key", "intent_id", "recipient", "evidence"),
                                     f"{p}.ack", out):
            if (ack.get("operation_key"), ack.get("intent_id")) != \
                    (op.get("operation_key"), op.get("intent_id")):
                out.append(f"{p}.ack: names another operation")
            if not _text(ack.get("recipient")):
                out.append(f"{p}.ack.recipient: not a non-empty printable ASCII string")
            entry = _evidence(ack.get("evidence"), f"{p}.ack.evidence", out)
            if entry is not None and not _observed([entry]):
                out.append(f"{p}.ack: not observed")
        if completion != "completed":
            continue
        if action in ACTIONS and action not in _permitted(kit):
            out.append(f"{p}: {action} is not a permitted effect")
        if action in ROUTED and ack is None:
            out.append(f"{p}: completed {action} without an acknowledgement")
    _bounds(_intervals([op for _, op in ops], "operations", window, out), len(ops),
            limits["operations"], "operations", out)
    recorded = sum(respawned.values())
    respawns = doc.get("respawns", MISSING)
    if respawns is not MISSING:
        if type(respawns) is not int or respawns < 0:
            out.append("respawns: not a non-negative integer")
        elif respawns != recorded:
            out.append(f"respawns: {respawns} but {recorded} re-spawns recorded")
    completed = {}
    for _, op in ops:
        if op.get("completion") == "completed" and _hex64(op.get("operation_key")):
            completed.setdefault(op.get("operation_key"), []).append(op)
    duplicates = [k for k, v in completed.items() if len(v) > 1]
    for key in duplicates:
        out.append(f"operations: duplicate completed effect {key}")
    duplicate_starts = sum(len(v) - 1 for v in completed.values()
                           if v[0].get("action") == "builder_start")

    fencing = doc.get("fencing")
    boundary = None
    if _keys(fencing, ("boundary", "evidence"), "fencing", out):
        boundary = fencing.get("boundary")
        if boundary not in ("effect", "advisory", "unknown"):
            out.append("fencing.boundary: not effect, advisory or unknown")
        if boundary == "effect" and not _observed(_evidence_list(fencing, "fencing", out)):
            out.append("fencing: effect boundary not observed")
    reviewer = doc.get("reviewer_output")
    access = None
    if _keys(reviewer, ("access", "evidence"), "reviewer_output", out):
        access = reviewer.get("access")
        if access not in ("verified", "absent", "unknown"):
            out.append("reviewer_output.access: not verified, absent or unknown")
        if access == "verified" and not _observed(_evidence_list(reviewer, "reviewer_output", out)):
            out.append("reviewer_output: access not observed")
            access = "unobserved"
    authenticated, unauthenticated = _verdicts(doc, threads, out)
    for i, op in ops:
        if op.get("action") == "merge" and op.get("completion") == "completed":
            if access != "verified":
                out.append(f"operations[{i}]: merge without verified reviewer-output access")
            if "APPROVE" not in authenticated:
                out.append(f"operations[{i}]: merge without an authenticated APPROVE verdict")

    steps = kit["controls"]["restoration"] + kit["controls"]["cleanup"]
    cleanup = doc.get("cleanup")
    if not isinstance(cleanup, list):
        out.append("cleanup: not a list")
        cleanup = []
    accounted = set()
    for i, item in enumerate(cleanup):
        p = f"cleanup[{i}]"
        if not _keys(item, ("step", "state", "evidence"), p, out):
            continue
        step = item.get("step")
        if not _text(step) or step not in steps:
            out.append(f"{p}: not a kit restoration or cleanup step")
        elif step in accounted:
            out.append(f"{p}: duplicate step")
        else:
            accounted.add(step)
        if item.get("state") not in ("done", "accounted"):
            out.append(f"{p}: not done or accounted for")
        if not _evidence_list(item, p, out):
            out.append(f"{p}: no evidence")
    for step in steps:
        if step not in accounted:
            out.append(f"cleanup: missing {step}")

    claims = doc.get("claims")
    if not isinstance(claims, list) or [c.get("claim") if isinstance(c, dict) else None
                                        for c in claims] != list(CLAIMS):
        out.append("claims: not exactly P1-P8 in order")
        claims = [c for c in claims if isinstance(c, dict)] if isinstance(claims, list) else []
    acked_delivery = any(op.get("action") == "delivery" and op.get("completion") == "completed"
                         and op.get("ack") is not None for _, op in ops)
    for i, claim in enumerate(claims):
        if not _keys(claim, ("claim", "status", "evidence"), f"claims[{i}]", out):
            continue
        name, status = claim.get("claim"), claim.get("status")
        evidence = _evidence_list(claim, f"claims[{i}]", out)
        if status not in ("pass", "fail", "partial", "unverified"):
            out.append(f"claims[{i}].status: not pass, fail, partial or unverified")
        if status != "pass":
            continue
        if live is not True:
            out.append(f"claims {name}: pass without a live run")
        if not _observed(evidence):
            out.append(f"claims {name}: pass without observed live evidence")
        if name in DISCOVERY_AFFECTS and _unknown_2244(kit):
            out.append(f"claims {name}: pass while #2244 findings are unknown")
        if name == "P4" and not acked_delivery:
            out.append("claims P4: pass without an acknowledged delivery")
        if name == "P5":
            if boundary != "effect":
                out.append(f"claims P5: pass with {boundary} fencing")
            if duplicates:
                out.append("claims P5: pass with a duplicate effect")
        if name == "P7":
            if access != "verified":
                out.append(f"claims P7: pass with {access} reviewer-output access")
            if not authenticated and not unauthenticated:
                out.append("claims P7: pass without an authenticated verdict")
            out += [f"claims P7: pass with verdicts[{i}] not authenticated by its reviewer's "
                    "thread output" for i in unauthenticated]
        if name == "P8" and any(t.get("end") is None for t in threads):
            out.append("claims P8: pass with a thread that never ended")

    gaps = doc.get("gaps")
    if not isinstance(gaps, list) or not all(_text(g) for g in gaps):
        out.append("gaps: not a list of printable ASCII strings")
        gaps = []
    measures = doc.get("measures")
    if _keys(measures, MEASURES, "measures", out):
        for name in MEASURES:
            m = measures.get(name)
            p = f"measures.{name}"
            if not _keys(m, ("value", "denominator"), p, out):
                continue
            value, denominator = m.get("value"), m.get("denominator")
            if value is None:
                if not any(name in g for g in gaps):
                    out.append(f"{p}: unmeasured but not in gaps")
                continue
            if not _time(value):
                out.append(f"{p}.value: not a non-negative integer")
            if not _time(denominator) or denominator < 1:
                out.append(f"{p}: value without a positive denominator")
            if name == "duplicate_starts" and value != duplicate_starts:
                out.append(f"{p}: {value} but {duplicate_starts} duplicate builder start recorded")
    return out


def _respawn(kit, i, op, starts, respawned, out):
    """J55: one counted re-spawn of a lost start, same request id; never executed is unprovable."""
    p = f"operations[{i}]"
    action, key, request = op.get("action"), op.get("operation_key"), op.get("request_id")
    if action in SPAWNS:
        if not _text(request):
            out.append(f"{p}.request_id: not a non-empty printable ASCII string")
    elif request is not None:
        out.append(f"{p}.request_id: not null for {action}")
    flag = op.get("respawn")
    if type(flag) is not bool:
        out.append(f"{p}.respawn: not true or false")
    if action in SPAWNS and op.get("completion") == "reconciled_not_executed" and \
            kit["discovery_2244"]["negative_execution"] != "observed":
        out.append(f"{p}: {action} recorded as never executed, which #2244 found unprovable")
    j55 = kit["discovery_2244"]["J55"]
    if action not in j55["actions"]:
        if flag is True:
            out.append(f"{p}: {action} is not a J55 re-spawn")
        return
    if not isinstance(key, str):
        return
    # Track attempts before inspecting their caller-supplied classification.
    # The first attempt binds the action and request id for this stable key;
    # changing either cannot turn a repeat into a fresh start.
    origin = starts.setdefault(key, op)
    if origin is op:
        if flag is True:
            out.append(f"{p}: re-spawn without a lost start of {op.get('intent_id')}")
        return
    respawned[key] = respawned.get(key, 0) + 1
    if flag is not True:
        out.append(f"{p}: repeated spawn must set respawn true")
    if respawned[key] > j55["max_per_lost_start"]:
        out.append(f"{p}: second re-spawn of {op.get('intent_id')}")
    if origin.get("completion") != "uncertain" or origin.get("action") != action:
        out.append(f"{p}: re-spawn without a lost start of {op.get('intent_id')}")
    if request != origin.get("request_id"):
        out.append(f"{p}: re-spawn with another request id")
    if op.get("intent_id") != origin.get("intent_id"):
        out.append(f"{p}: re-spawn with another intent id")
    start, original_end = op.get("start"), origin.get("end")
    if _time(start) and _time(original_end) and start < original_end:
        out.append(f"{p}: re-spawn before the original attempt ended")


def _verdicts(doc, threads, out):
    """J56: (authenticated verdict values, indexes of unauthenticated verdicts)."""
    verdicts = doc.get("verdicts")
    if not isinstance(verdicts, list):
        out.append("verdicts: not a list")
        return set(), []
    reviewers = {t["alias"] for t in threads if t.get("role") == "reviewer" and _text(t.get("alias"))}
    authenticated, unauthenticated = set(), []
    for i, v in enumerate(verdicts):
        p = f"verdicts[{i}]"
        if not _keys(v, ("reviewer", "verdict", "comment", "thread_output", "matches"), p, out):
            unauthenticated.append(i)
            continue
        ok = True
        if not (_text(v.get("reviewer")) and v["reviewer"] in reviewers):
            out.append(f"{p}.reviewer: not a reviewer thread")
            ok = False
        if v.get("verdict") not in VERDICTS:
            out.append(f"{p}.verdict: not APPROVE or CHANGES")
            ok = False
        _evidence(v.get("comment"), f"{p}.comment", out)
        output = v.get("thread_output")
        if output is None:
            ok = False
        elif _evidence(output, f"{p}.thread_output", out) is None or not _observed([output]):
            out.append(f"{p}.thread_output: not observed")
            ok = False
        matches = v.get("matches")
        if type(matches) is not bool:
            out.append(f"{p}.matches: not true or false")
            ok = False
        elif matches and output is None:
            out.append(f"{p}: matches without its thread output read by id")
        if ok and matches is True:
            authenticated.add(v["verdict"])
        else:
            unauthenticated.append(i)
    return authenticated, unauthenticated


def summary(doc):
    lines = [f"{c['claim']}: {c['status']}" for c in doc["claims"]]
    return lines + ["consistent results (offline only): every pass still needs its "
                    "observed evidence read back and independent evidence review"]


# ---- the command -----------------------------------------------------------

USAGE = "usage: acceptance.py kit <kit.json> | results <kit.json> <results.json>"


def _load(path):
    return Path(path).read_bytes().decode("utf-8")


def main(argv):
    if not argv or (argv[0], len(argv)) not in (("kit", 2), ("results", 3)):
        print(USAGE, file=sys.stderr)
        return 2
    try:
        texts = [_load(p) for p in argv[1:]]
    except (OSError, UnicodeDecodeError):
        print("error: cannot read a named file as UTF-8", file=sys.stderr)
        return 2
    lines = []
    try:
        if argv[0] == "kit":
            kit = read(texts[0])
            refusals = check_kit(kit)
            if not refusals:
                gate = live_gate(kit)
                lines = [f"pass: kit {kit['status']} (offline only; no live claim)",
                         "live gate: " + ("open on paper; re-read every record before any step"
                                          if not gate else "closed")]
                lines += [f"  {r}" for r in gate]
        else:
            doc = read(texts[1])
            refusals = check_results(texts[0], doc)
            if not refusals:
                lines = summary(doc)
    except Refused as refused:
        refusals = [str(refused)]
    for refusal in refusals:
        print(f"refused: {refusal}", file=sys.stderr)
    if refusals:
        return 1
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
