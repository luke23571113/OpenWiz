#!/usr/bin/env python3
"""The 0.0.16 live kit's offline dry run, eligibility check and receipt validator (#637).

  first_merge_kit.py dry-run [ELIGIBILITY [BINDING]]
      walk every step of first-hour-live-kit.md's 0.0.16 extension with a
      simulated clock and no effect, and say whether final execution is refused
      (exit 0 eligible, 5 refused)
  first_merge_kit.py eligibility ELIGIBILITY BINDING
      refuse final execution while producer proof, binding or authority is
      missing (exit 0 eligible, 5 refused)
  first_merge_kit.py validate RECEIPT --result RESULT --fleet FLEET --binding BINDING --eligibility ELIGIBILITY
      check one setup-onboard.v1 `first_merge_receipt` against the same
      attempt's first-hour.v1 result, its fleet start and the kit's binding
      (exit 0 valid, 5 refused)

This supplements the first-hour kit (kit.py beside this file), never replaces
it: the receipt's codes come from setup-onboard.v1's checks and the result's
from first-hour.v1's, each kept separately, so neither verdict decides the
other. Nothing here performs a live action; every command only reads its files.
A passing dry run or validation proves the kit's shape and rules, never a live
result, an elapsed time, a usable login or an upstream capability. Stdlib only.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
KIT = ROOT / 'tools/install/first-hour-live-kit.md'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


receipt_check = load('first_merge_receipt_check', ROOT / 'tools/install/tests/setup-onboard-contract/check.py')
result_check = load('first_merge_result_check', ROOT / 'tools/install/tests/first-hour-contract/check.py')
first_hour_kit = load('first_merge_first_hour_kit', HERE / 'kit.py')

SPEC = 625
PRODUCERS = (632, 633, 606, 634, 635, 636, 637)  # T1 to T7 of spec #625
SCOPES = ('live', 'machine', 'accounts', 'repository', 'app', 'companion', 'secret', 'agents', 'merges', 'spending',
          'cleanup')
COUNTS = ('fleet_threads', 'loops', 'builders', 'reviewers', 'merges', 'app_registrations', 'companions')
CLEANUP = {'test_threads': ('archive', 'stop'), 'test_loops': ('stop', 'delete'), 'throwaway_repository': ('delete',),
           'companion_repository': ('delete',), 'test_app': ('delete', 'revoke'), 'test_secret': ('delete', 'revoke'),
           'machine_account': ('delete',)}
ROUTES = {('personal_login', 'skipped', 'not_used'), ('app', 'created', 'agent_save'), ('app', 'created', 'protected_paste'),
          ('app', 'reused', 'agent_save'), ('app', 'reused', 'protected_paste'), ('app', 'reused', 'not_used')}
FLEET_KEYS = ('schema', 'proof_class', 'private_record', 'route', 'fleet_threads', 'loop', 'engine_activations',
              'tick_starts', 'builders', 'reviewers')
# The owner steps each route needs, one action entry each (kind, stage); never one entry for several.
DECISION_STEPS = (('confirmation', 'spec_confirmation'), ('approval', 'plan_approval'), ('spending_approval', 'launch'))
APP_STEPS = (('app_manifest', 'create_app'), ('app_manifest', 'install_app'))
PASTE_STEPS = (('key_step', 'open_app_settings'), ('key_step', 'generate_key'), ('key_step', 'encode_key'),
               ('protected_paste', 'paste_protected_prompt'), ('key_step', 'delete_download'))
LOOP_MINUTES = 10  # docs/agents/fleet.md: a spec's fleet thread checks its spec every 10 minutes
POINTER = first_hour_kit.POINTER
HEX40, HEX64, REPOSITORY = first_hour_kit.HEX40, first_hour_kit.HEX64, first_hour_kit.REPOSITORY
integer, exact, strings = first_hour_kit.integer, first_hour_kit.exact, first_hour_kit.strings


def steps():
    """The 0.0.16 steps from the kit's own table: (id, name, effect, the scopes it needs)."""
    rows = re.findall(r'^\| (F[0-9]+) \| ([a-z-]+) \| (read|write|spend) \| ([a-z ]+) \| .+ \|$', KIT.read_text(), re.M)
    return [(s, name, effect, tuple(needs.split())) for s, name, effect, needs in rows]


def binding_errors(b):
    """Every reason the binding leaves the run unbound or unsafe."""
    keys = ('schema', 'candidate', 'host', 'scope', 'route', 'counts', 'credit_bound', 'recorded', 'cleanup', 'graph')
    if not exact(b, keys) or b['schema'] != 'openwiz.first-merge-kit-binding.v1':
        return ['The binding must be openwiz.first-merge-kit-binding.v1 with exactly its fields.']
    out = []
    c = b['candidate']
    if not (exact(c, ('version', 'source', 'target', 'manifest_sha256')) and isinstance(c['version'], str)
            and re.fullmatch(r'0\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', c['version'])
            and isinstance(c['source'], str) and HEX40.fullmatch(c['source']) and c['target'] in first_hour_kit.TARGETS
            and isinstance(c['manifest_sha256'], str) and HEX64.fullmatch(c['manifest_sha256'])):
        out.append('The bound candidate is malformed.')
    h = b['host']
    if not (exact(h, ('target', 'fresh_machine', 'seeded_openwiz_state')) and h['fresh_machine'] is True
            and h['seeded_openwiz_state'] is False and isinstance(c, dict) and h['target'] == c.get('target')):
        out.append("The host must be a fresh machine on the candidate's target with no seeded OpenWiz state.")
    s = b['scope']
    if not (exact(s, ('repository', 'app_repositories', 'companion_repository')) and isinstance(s['repository'], str)
            and REPOSITORY.fullmatch(s['repository']) and s['app_repositories'] == [s['repository']]):
        out.append('The scope must be one throwaway repository, with the App on it only.')
    elif s['companion_repository'] is not None and not (
            isinstance(s['companion_repository'], str) and REPOSITORY.fullmatch(s['companion_repository'])
            and s['companion_repository'].lower() != s['repository'].lower()):
        out.append('The companion must be a different repository.')
    r = b['route']
    if not (exact(r, ('identity', 'app_registration', 'secret_route'))
            and (r['identity'], r['app_registration'], r['secret_route']) in ROUTES):
        out.append('The route is inconsistent: the skip is personal_login, skipped, not_used.')
    n = b['counts']
    if not (exact(n, COUNTS) and all(integer(n[k]) for k in COUNTS) and n['fleet_threads'] == 1 and n['loops'] == 1
            and n['app_registrations'] <= 1 and n['companions'] <= 1):
        out.append('The counts are unbound: one fleet thread, one loop, at most one App registration and one companion.')
    elif isinstance(r, dict) and r.get('app_registration') == 'created' and n['app_registrations'] < 1:
        out.append('The binding allows no App registration for its created App.')
    if not integer(b['credit_bound'], 1):
        out.append('The credit bound must be a positive number of Cloud Credits.')
    rec = b['recorded']
    if not (exact(rec, ('actions', 'waits', 'help')) and all(integer(rec[k]) for k in rec)):
        out.append('The recorded action, wait and help counts are malformed.')
    items = b['cleanup']
    safe = isinstance(items, list) and all(
        exact(i, ('resource', 'action')) and i['resource'] in CLEANUP and i['action'] in CLEANUP[i['resource']]
        for i in items)
    if not (safe and {'test_threads', 'test_loops'} <= {i['resource'] for i in items}):
        out.append('Unsafe cleanup: only bound test-owned resources, with test threads and loops stopped.')
    g = b['graph']
    if not (exact(g, ('spec', 'revision', 'fingerprint')) and g['spec'] == SPEC and integer(g['revision'], 1)
            and isinstance(g['fingerprint'], str) and HEX64.fullmatch(g['fingerprint'])):
        out.append('The bound graph is malformed.')
    return out


def eligibility(record, binding):
    """Every reason final execution is refused; empty means eligible."""
    out = binding_errors(binding) if binding is not None else ['No binding was given.']
    if record is None:
        return ['No eligibility record was given.'] + out
    if not exact(record, ('schema', 'graph', 'producers', 'authority', 'upstream')) \
            or record['schema'] != 'openwiz.first-merge-kit-eligibility.v1':
        return ['The eligibility record must be openwiz.first-merge-kit-eligibility.v1 with exactly its fields.'] + out
    g = record['graph']
    if not (exact(g, ('spec', 'revision', 'fingerprint', 'approval')) and g['spec'] == SPEC and integer(g['revision'], 1)
            and isinstance(g['fingerprint'], str) and HEX64.fullmatch(g['fingerprint'])
            and isinstance(g['approval'], str) and POINTER.fullmatch(g['approval'])):
        out.append("Spec #625's approved graph revision, fingerprint and approval pointer are missing or malformed.")
    elif isinstance(binding, dict) and isinstance(binding.get('graph'), dict) and (
            binding['graph'].get('revision'), binding['graph'].get('fingerprint')) != (g['revision'], g['fingerprint']):
        out.append('The binding names another graph revision than the eligibility record.')
    producers = record['producers'] if isinstance(record['producers'], list) else []
    for ticket in PRODUCERS:
        found = [p for p in producers if isinstance(p, dict) and p.get('ticket') == ticket]
        p = found[0] if len(found) == 1 else None
        if p is None:
            out.append('Producer #%d has no verified merge in the record.' % ticket)
        elif not (exact(p, ('ticket', 'pr', 'merge_commit', 'approved_head', 'merged_at_head')) and integer(p['pr'], 1)
                  and all(isinstance(p[k], str) and HEX40.fullmatch(p[k]) for k in ('merge_commit', 'approved_head'))):
            out.append('Producer #%d is malformed.' % ticket)
        elif p['merged_at_head'] is not True:
            out.append('Producer #%d has no verified merge at its approved head (a closed issue is not one).' % ticket)
    auth = record['authority']
    if not exact(auth, SCOPES):
        out.append('The record must name exactly the authority scopes %s.' % ', '.join(SCOPES))
    else:
        for scope in SCOPES:
            if not (isinstance(auth[scope], str) and POINTER.fullmatch(auth[scope])):
                out.append('No recorded %s authority for these exact steps and counts.' % scope)
    u = record['upstream']
    observed = exact(u, ('state', 'evidence')) and u['state'] == 'observed_supported' \
        and isinstance(u['evidence'], str) and POINTER.fullmatch(u['evidence']) is not None
    if isinstance(binding, dict) and isinstance(binding.get('route'), dict) \
            and binding['route'].get('secret_route') == 'agent_save' and not observed:
        out.append('The no-paste route needs the observed CloudRoom agent-side save-secret contribution; it stays Unverified.')
    return out


def dry_run(record=None, binding=None, out=sys.stdout):
    """Every step in order, with a simulated clock and no effect; then final execution's refusals."""
    refusals = eligibility(record, binding)
    auth = record.get('authority') if isinstance(record, dict) and isinstance(record.get('authority'), dict) else {}
    clock = 0
    for step, name, effect, needs in steps():
        clock += 60000
        missing = [s for s in needs if not (isinstance(auth.get(s), str) and POINTER.fullmatch(auth[s]))]
        status = ('refused: no recorded %s authority' % ', '.join(missing)) if missing else \
            'would run within the recorded authority'
        print('%s %s (%s) at +%d ms: %s; no effect in a dry run' % (step, name, effect, clock, status), file=out)
    print('The dry run sets no elapsed time and observes nothing live.', file=out)
    for line in refusals:
        print('Final execution refused: ' + line, file=out)
    if not refusals:
        print('Final execution eligible within the recorded authority.', file=out)
    return 5 if refusals else 0


def lists(report):
    return {'problems': report.problems, 'failures': report.failures, 'unproven': report.unproven}


def fleet_errors(fleet, binding):
    if not exact(fleet, FLEET_KEYS) or fleet['schema'] != 'openwiz.first-merge-kit-fleet.v1' \
            or fleet['proof_class'] not in ('fixture', 'recording', 'live') \
            or not all(integer(fleet[k]) for k in ('fleet_threads', 'engine_activations', 'tick_starts', 'builders', 'reviewers')):
        return ['The fleet start must be openwiz.first-merge-kit-fleet.v1 with exactly its fields.']
    out = []
    if fleet['route'] != 'launch_fleet':
        out.append({'engine': 'The fleet was started by the engine, not launch-fleet.',
                    'fleet_tick': 'The fleet was started by a fleet tick, not launch-fleet.'}.get(
            fleet['route'], 'The fleet was not started by launch-fleet.'))
    if fleet['engine_activations']:
        out.append('The run activated the engine.')
    if fleet['tick_starts']:
        out.append('The run started work through a fleet tick.')
    if fleet['fleet_threads'] != 1:
        out.append('The run did not start exactly one fleet thread.')
    loop = fleet['loop']
    if not (exact(loop, ('spec', 'every_minutes')) and integer(loop['spec'], 1) and loop['every_minutes'] == LOOP_MINUTES):
        out.append('The fleet thread has no per-spec check loop.')
    counts = binding['counts']
    if fleet['builders'] > counts['builders'] or fleet['reviewers'] > counts['reviewers']:
        out.append('The run started more builders or reviewers than bound.')
    return out


def validate(receipt_text, result_text, fleet, binding, record):
    """(refusals, outcome, codes): outcome is `refused`, or the receipt's own verdict when nothing refuses."""
    out = eligibility(record, binding)
    receipt_report, result_report = receipt_check.check_text(receipt_text), result_check.check_text(result_text)
    codes = {'receipt': lists(receipt_report), 'result': lists(result_report)}
    if receipt_report.problems:
        out.append("setup-onboard.v1's checks refuse the receipt: " + ', '.join(receipt_report.problems))
    if result_report.problems:
        out.append("first-hour.v1's checks refuse the result: " + ', '.join(result_report.problems))
    unread = {'schema', 'not_strict_json'}
    if unread & set(receipt_report.problems) or unread & set(result_report.problems) or binding_errors(binding):
        return out, 'refused', codes
    receipt, result = json.loads(receipt_text), json.loads(result_text)
    if receipt['kind'] != 'first_merge_receipt' or result['kind'] != 'result':
        return out + ['A kit receipt is a first_merge_receipt bound to a first-hour result.'], 'refused', codes
    out += fleet_errors(fleet, binding)
    bound = receipt['binding']
    if bound['first_hour_result_sha256'] != hashlib.sha256(result_text.encode('utf-8')).hexdigest():
        out.append('The receipt is not bound to this first-hour result.')
    live = receipt['proof_class'] == 'live'
    if not live:
        out.append('A %s receipt is synthetic proof, not a live observation.' % receipt['proof_class'])
    else:
        for name, doc in (('first-hour result', result), ('fleet record', fleet)):
            if isinstance(doc, dict) and doc.get('proof_class') != 'live':
                out.append('A live receipt binds a %s %s.' % (doc.get('proof_class'), name))
    candidate = binding['candidate']
    if bound['candidate'].get('known') != candidate or result['candidate'].get('known') != candidate:
        out.append('The receipt is for another candidate than the bound one.')
    repository = binding['scope']['repository']
    if bound['repository'].get('known') != repository or result['repository'].get('known', {}).get('full_name') != repository:
        out.append('The receipt is for another repository than the bound one.')
    route = binding['route']
    if (receipt['identity'], receipt['app_registration'], receipt['secret_route']) != (
            route['identity'], route['app_registration'], route['secret_route']):
        out.append('The receipt reports another identity or secret route than the bound one.')
    # Both clocks start when the same public instruction is opened: one start, read once, or none at all.
    if receipt['clock']['started_at_ms'].get('known') != result['clock']['started_at_ms'].get('known'):
        out.append("The receipt's start is not the first-hour result's instruction-open start.")
    # The merge: the first-hour result's own read-back, at the receipt's head and time.
    merge = bound['merge']
    stage = next(s for s in result['stages'] if s['id'] == 'merge')
    read_back = [e for e in stage['evidence'] if e['basis'] == 'merge_read_back'] if stage['state'] == 'verified' else []
    if not read_back:
        out.append('The first-hour result has no verified merge read back.')
    else:
        if not any(w['kind'] == 'commit' and w['id'] == merge['head'] for w in result['retained_work']):
            out.append("The receipt's merged head is not the first-hour result's commit.")
        ended = result['clock']['ended_at_ms'].get('known')
        # GitHub's merge time ends both clocks; the read-back that observed it comes at or after it.
        if merge['merged_at_ms'] > max(e['at_ms'] for e in read_back) or ended not in (None, merge['merged_at_ms']):
            out.append("The receipt's merge time is not the first-hour result's merge read-back.")
    if any(o['kind'] == 'activate_engine' for o in result['operations']) and 'The run activated the engine.' not in out:
        out.append('The run activated the engine.')
    kinds = [o['kind'] for o in result['operations']]
    counts = binding['counts']
    if kinds.count('start_agent') > counts['builders'] + counts['reviewers'] or kinds.count('merge') > counts['merges']:
        out.append('The run started or merged more than the bound counts.')
    # Every wait, help and action the run recorded, the same in both documents.
    waits = lambda doc: sorted((w['kind'], w['started_at_ms'], w['ended_at_ms']) for w in doc['waits'])
    helps = lambda doc: sorted((h['at_ms'], h['source']) for h in doc['help'])
    if waits(receipt) != waits(result) or helps(receipt) != helps(result):
        out.append("The receipt's waits and help are not the first-hour result's.")
    elif (len(receipt['waits']), len(receipt['help'])) != (binding['recorded']['waits'], binding['recorded']['help']):
        out.append('The receipt does not keep every wait and help the run recorded.')
    log = receipt['actions']['log']
    if len(log) != binding['recorded']['actions']:
        out.append('The receipt does not keep every action the run recorded.')
    required = list(DECISION_STEPS)
    if receipt['app_registration'] == 'created':
        required += APP_STEPS
    if receipt['secret_route'] == 'protected_paste':
        required += PASTE_STEPS
    for kind, step in required:
        if not any(a['kind'] == kind and a['stage'] == step for a in log):
            out.append('The owner step %s has no action entry of its own.' % step)
    if any(first_hour_kit.PRIVATE.search(s) for doc in (receipt, result, fleet) for s in strings(doc)):
        out.append('The receipt holds something that looks like an account, id, token, email or path.')
    return out, 'refused' if out else receipt['verdict'], codes


def main(argv):
    try:
        return run(argv)
    except (OSError, ValueError) as error:
        print('Refused: a file is unreadable or not strict JSON (%s).' % type(error).__name__)
        return 5


def run(argv):
    read = lambda path: receipt_check.strict_json(Path(path).read_text())  # duplicate keys and fractions refused
    if argv[:1] == ['dry-run'] and len(argv) <= 3:
        return dry_run(*(read(p) for p in argv[1:]))
    if len(argv) == 3 and argv[0] == 'eligibility':
        refusals = eligibility(read(argv[1]), read(argv[2]))
        for line in refusals or ['Eligible: the kit may run within its recorded authority.']:
            print(line)
        return 5 if refusals else 0
    if len(argv) == 10 and argv[0] == 'validate' and argv[2::2] == ['--result', '--fleet', '--binding', '--eligibility']:
        refusals, outcome, codes = validate(Path(argv[1]).read_text(), Path(argv[3]).read_text(), read(argv[5]),
                                            read(argv[7]), read(argv[9]))
        print(json.dumps({'refusals': refusals, 'outcome': outcome, 'codes': codes}, indent=1))
        return 5 if refusals else 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
