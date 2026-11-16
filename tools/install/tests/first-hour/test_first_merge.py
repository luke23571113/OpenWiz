#!/usr/bin/env python3
"""The 0.0.16 first-merge receipt on the installed journey and its bounded live kit (#637).

`Kit` proves first_merge_kit.py's offline rules on the synthetic fixtures in
tests/fixtures/first-hour/setup-onboard/ (shape only: their "live" class is a
label on invented values, never an observation). `Recording` runs the installed
first-hour journey (journey.py, #2204, joined in #636) with the user's App and
again with the explicit skip, and checks the recording receipt, fleet start,
action log and the key and brain faults it produces at the installed seams.
Every expected code and refusal below is written by hand from
contracts/setup-onboard.v1.md, contracts/first-hour.v1.md and
first-hour-live-kit.md. Nothing here is live, timed or on a real account.
"""
import copy
import hashlib
import importlib.util
import io
import json
import re
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FIXTURES = ROOT / 'tests/fixtures/first-hour/setup-onboard'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


kit = load('first_merge_kit_under_test', HERE / 'first_merge_kit.py')
START = 1700000000000


def fixture(name):
    return json.loads((FIXTURES / name).read_text())


class Bundle:
    """One synthetic run's documents, rebound after each edit as a real run would bind them."""

    def __init__(self):
        self.result, self.receipt = fixture('result.json'), fixture('receipt.json')
        self.fleet, self.binding, self.record = fixture('fleet.json'), fixture('binding.json'), fixture('eligibility.json')
        self.rebind = True

    def texts(self):
        result_text = json.dumps(self.result, indent=1) + '\n'
        if self.rebind:
            self.receipt['binding']['first_hour_result_sha256'] = hashlib.sha256(result_text.encode()).hexdigest()
        return json.dumps(self.receipt, indent=1), result_text

    def run(self):
        receipt_text, result_text = self.texts()
        return kit.validate(receipt_text, result_text, self.fleet, self.binding, self.record)

    def merge_at(self, ms):
        """The first merge at another time: GitHub's merge time ends both clocks, read back once."""
        self.receipt['binding']['merge']['merged_at_ms'] = ms
        self.receipt['clock']['ended_at_ms'] = {'known': ms}
        self.result['clock']['ended_at_ms'] = {'known': ms}
        next(s for s in self.result['stages'] if s['id'] == 'merge')['evidence'][0]['at_ms'] = ms

    def act(self, kind, stage, actor='owner', at=START + 60000):
        self.receipt['actions']['log'].append({'at_ms': at, 'kind': kind, 'actor': actor, 'stage': stage,
                                               'detail': 'Synthetic owner action.'})
        self.receipt['actions']['count'] = {'known': len(self.receipt['actions']['log'])}
        self.binding['recorded']['actions'] = len(self.receipt['actions']['log'])


CLEAN = {'problems': [], 'failures': [], 'unproven': []}


class Kit(unittest.TestCase):
    def outcome(self, bundle):
        refusals, outcome, codes = bundle.run()
        return refusals, outcome, codes

    def test_a_bound_synthetic_receipt_is_valid_and_its_verdict_is_the_contracts(self):
        # The fixtures' positive shape: catches a validator that refuses a consistent bundle.
        refusals, outcome, codes = self.outcome(Bundle())
        self.assertEqual(refusals, [])
        self.assertEqual(outcome, 'pass')
        self.assertEqual(codes, {'receipt': CLEAN, 'result': CLEAN})

    def test_the_version_boundaries_never_pass(self):
        # Catches a receipt that passes at exactly 30 minutes, at six actions, with prepared help,
        # seeded state or an init-only merge (contracts/setup-onboard.v1.md, the 0.0.16 receipt).
        b = Bundle(); b.merge_at(START + 1799999)
        self.assertEqual(self.outcome(b)[:2], ([], 'pass'), '1,799,999 ms can qualify')
        for edit, code in ((lambda b: b.merge_at(START + 1800000), 'thirty_minutes_missed'),
                           (lambda b: b.act('typed_choice', 'agents'), 'actions_exceeded')):
            b = Bundle(); edit(b)
            self.assertEqual(self.outcome(b)[:2], (["setup-onboard.v1's checks refuse the receipt: failure_not_reported"],
                                                   'refused'), 'a pass claimed past the limit is refused')
            b.receipt['verdict'] = 'fail'
            refusals, outcome, codes = self.outcome(b)
            self.assertEqual((refusals, outcome, codes['receipt']['failures']), ([], 'fail', [code]))
        for edit, code in ((lambda b: b.receipt['freshness'].update(seeded_openwiz_state=True), 'seeded_state'),
                           (lambda b: b.receipt['freshness'].update(machine='reused'), 'not_fresh:machine')):
            b = Bundle(); edit(b); b.receipt['verdict'] = 'unverified'
            refusals, outcome, codes = self.outcome(b)
            self.assertEqual((refusals, outcome, codes['receipt']['unproven']), ([], 'unverified', [code]))
        b = Bundle(); b.receipt['verdict'] = 'unverified'
        for doc in (b.receipt, b.result):
            doc['help'][0]['source'] = 'private_instruction'
        refusals, outcome, codes = self.outcome(b)
        self.assertEqual((refusals, outcome, codes['receipt']['unproven'], codes['result']['unproven']),
                         ([], 'unverified', ['prepared_help'], ['prepared_help']))
        b = Bundle(); b.receipt['binding']['merge']['change'] = 'init_only'; b.receipt['verdict'] = 'fail'
        refusals, outcome, codes = self.outcome(b)
        self.assertEqual((outcome, codes['receipt']['failures']), ('fail', ['init_only_merge']))

    def test_weak_merge_evidence_is_refused(self):
        # Catches a merge offered at a head nobody reviewed, or one the first-hour result never read back.
        b = Bundle(); b.receipt['binding']['merge']['reviewed_head'] = '7' * 40
        self.assertEqual(self.outcome(b)[:2], (["setup-onboard.v1's checks refuse the receipt: merge_weak_evidence"], 'refused'))
        b = Bundle()
        merge = next(s for s in b.result['stages'] if s['id'] == 'merge')
        merge.update(state='missing', evidence=[dict(merge['evidence'][0], basis='pr_closed')])
        self.assertIn('The first-hour result has no verified merge read back.', self.outcome(b)[0])
        b = Bundle(); b.receipt['binding']['merge']['head'] = b.receipt['binding']['merge']['reviewed_head'] = \
            b.receipt['binding']['merge']['ci_green_head'] = '8' * 40
        self.assertEqual(self.outcome(b)[0], ["The receipt's merged head is not the first-hour result's commit."])

    def test_omitted_actions_waits_or_help_are_refused(self):
        # Catches a receipt that drops a logged step, a wait or a help to look faster or simpler.
        b = Bundle()
        b.receipt['actions']['log'].pop(0)
        b.receipt['actions']['count'] = {'known': 4}
        self.assertIn('The receipt does not keep every action the run recorded.', self.outcome(b)[0])
        b = Bundle(); b.receipt['waits'].pop()
        self.assertEqual(self.outcome(b)[0], ["The receipt's waits and help are not the first-hour result's."])
        b = Bundle(); b.receipt['help'] = []
        self.assertEqual(self.outcome(b)[0], ["The receipt's waits and help are not the first-hour result's."])
        b = Bundle()
        for doc in (b.receipt, b.result):
            doc['help'] = []
        self.assertEqual(self.outcome(b)[0], ['The receipt does not keep every wait and help the run recorded.'])

    def test_fixture_or_recording_evidence_labelled_live_is_refused(self):
        # Catches a live-labelled receipt standing on a recording, and a recording offered as live.
        b = Bundle()
        b.result.update(proof_class='recording', synthetic_assumptions=['Synthetic recording.'], private_record=None)
        self.assertIn('A live receipt binds a recording first-hour result.', self.outcome(b)[0])
        b = Bundle(); b.fleet['proof_class'] = 'fixture'
        self.assertIn('A live receipt binds a fixture fleet record.', self.outcome(b)[0])
        b = Bundle()
        b.receipt.update(proof_class='recording', synthetic_assumptions=['Synthetic recording.'], private_record=None,
                         verdict='unverified')
        refusals, outcome, codes = self.outcome(b)
        self.assertEqual((refusals, outcome), (['A recording receipt is synthetic proof, not a live observation.'], 'refused'))
        self.assertEqual(codes['receipt']['unproven'], ['not_live'])

    def test_an_engine_activation_or_fleet_tick_start_is_refused(self):
        # J87 Q1: the first fleet is launch-fleet's one fleet thread and its per-spec loop.
        # Catches an engine or tick start, a second fleet thread or a fleet with no loop passing.
        cases = [({'route': 'engine'}, 'The fleet was started by the engine, not launch-fleet.'),
                 ({'route': 'fleet_tick'}, 'The fleet was started by a fleet tick, not launch-fleet.'),
                 ({'engine_activations': 1}, 'The run activated the engine.'),
                 ({'tick_starts': 1}, 'The run started work through a fleet tick.'),
                 ({'fleet_threads': 2}, 'The run did not start exactly one fleet thread.'),
                 ({'loop': None}, 'The fleet thread has no per-spec check loop.'),
                 ({'loop': {'spec': 9100, 'every_minutes': 30}}, 'The fleet thread has no per-spec check loop.')]
        for edit, expected in cases:
            with self.subTest(edit):
                b = Bundle(); b.fleet.update(edit)
                self.assertEqual(self.outcome(b)[:2], ([expected], 'refused'))
        b = Bundle()
        b.result['operations'].append({'operation_id': '9' * 32, 'kind': 'activate_engine', 'phase': 'applied',
                                       'effect_count': 1, 'attempts': 1, 'reconciliation': 'none'})
        self.assertEqual(self.outcome(b)[:2], (['The run activated the engine.'], 'refused'))

    def test_the_receipt_is_bound_to_its_result_candidate_repository_and_route(self):
        # Catches a receipt validated against another attempt, candidate, target, repository or route.
        b = Bundle(); b.rebind = False; b.result['findings'] = []
        self.assertEqual(self.outcome(b)[0], ['The receipt is not bound to this first-hour result.'])
        b = Bundle(); b.binding['candidate']['source'] = '6' * 40
        self.assertEqual(self.outcome(b)[0], ['The receipt is for another candidate than the bound one.'])
        b = Bundle(); b.receipt['binding']['repository'] = {'known': 'syn-owner/another'}
        self.assertEqual(self.outcome(b)[0], ['The receipt is for another repository than the bound one.'])
        b = Bundle(); b.binding['route']['secret_route'] = 'protected_paste'
        self.assertEqual(self.outcome(b)[0], ['The receipt reports another identity or secret route than the bound one.'])
        b = Bundle(); b.receipt['binding']['merge']['merged_at_ms'] -= 1000
        b.receipt['clock']['ended_at_ms'] = {'known': b.receipt['binding']['merge']['merged_at_ms']}
        self.assertEqual(self.outcome(b)[0], ["The receipt's merge time is not the first-hour result's merge read-back."])

    def test_every_owner_step_is_its_own_entry_and_a_stand_in_counts(self):
        # Catches collapsed taps, an uncounted stand-in and a missing key, paste or spending step.
        b = Bundle(); b.receipt['actions']['log'][1]['stage'] = 'create_app'
        self.assertEqual(self.outcome(b)[0], ['The owner step install_app has no action entry of its own.'])
        b = Bundle(); b.receipt['actions']['log'][4].update(kind='typed_choice')
        self.assertEqual(self.outcome(b)[0], ['The owner step launch has no action entry of its own.'])
        b = Bundle(); b.receipt['actions']['log'][0]['actor'] = 'agent_for_owner'
        self.assertEqual(self.outcome(b)[:2], ([], 'pass'), "an agent's stand-in counts like the owner's tap")
        b = Bundle(); b.receipt['actions']['log'].pop(0)
        refusals, outcome, codes = self.outcome(b)
        self.assertEqual(outcome, 'refused')
        self.assertIn('action_count_mismatch', codes['receipt']['problems'], 'a dropped entry under the same count')
        # The protected paste: each of the installed route's owner steps, never one entry for all.
        b = Bundle()
        b.binding['route']['secret_route'] = b.receipt['secret_route'] = 'protected_paste'
        b.record['upstream'] = {'state': 'not_shipped', 'evidence': None}
        for step in ('open_app_settings', 'generate_key', 'download_key', 'encode_key'):
            b.act('key_step', step)
        b.act('protected_paste', 'paste_protected_prompt')
        b.act('key_step', 'delete_download')
        b.receipt['verdict'] = 'fail'
        refusals, outcome, codes = self.outcome(b)
        self.assertEqual((refusals, outcome, codes['receipt']['failures']), ([], 'fail', ['actions_exceeded']),
                         'the paste route counts every key step: it can never fit five actions with a new App')
        b.receipt['actions']['log'] = [a for a in b.receipt['actions']['log'] if a['stage'] != 'delete_download']
        b.receipt['actions']['count'] = {'known': len(b.receipt['actions']['log'])}
        b.binding['recorded']['actions'] = len(b.receipt['actions']['log'])
        self.assertEqual(self.outcome(b)[0], ['The owner step delete_download has no action entry of its own.'])

    def test_the_one_hour_and_ten_minute_measures_stay_independent(self):
        # Catches either first-hour.v1 measure deciding the 0.0.16 verdict, or the reverse.
        b = Bundle(); b.result['ten_minute_fleet'] = {'owner': 1110, 'state': 'missed', 'elapsed_ms': 700000}
        refusals, outcome, codes = self.outcome(b)
        self.assertEqual((refusals, outcome, codes['result']), ([], 'pass', CLEAN))
        b = Bundle(); b.merge_at(START + 2400000); b.receipt['verdict'] = 'fail'
        refusals, outcome, codes = self.outcome(b)
        self.assertEqual((refusals, outcome, codes['receipt']['failures'], codes['result']), ([], 'fail', ['thirty_minutes_missed'], CLEAN))
        self.assertEqual(b.result['clock']['limit_ms'], 3600000, 'the hour keeps its own limit')

    def test_private_looking_values_are_refused(self):
        b = Bundle(); b.receipt['actions']['log'][0]['detail'] = 'Synthetic: signed in as someone@example.com.'
        self.assertEqual(self.outcome(b)[0], ['The receipt holds something that looks like an account, id, token, email or path.'])


class Eligibility(unittest.TestCase):
    def test_the_dry_run_has_no_effect_and_refuses_without_proof_binding_and_authority(self):
        # Catches a dry run that says eligible with nothing recorded, or a step that claims an effect.
        out = io.StringIO()
        self.assertEqual(kit.dry_run(None, None, out), 5)
        lines = out.getvalue().splitlines()
        steps = [l for l in lines if re.match(r'F[0-9]+ ', l)]
        self.assertEqual([l.split()[0] for l in steps], ['F%d' % i for i in range(1, 18)])
        self.assertTrue(all(l.endswith('; no effect in a dry run') for l in steps), steps)
        self.assertIn('F11 fleet (spend) at +660000 ms: refused: no recorded agents, spending authority; no effect in a dry run', lines)
        self.assertIn('Final execution refused: No eligibility record was given.', lines)
        self.assertIn('Final execution refused: No binding was given.', lines)
        out = io.StringIO()
        self.assertEqual(kit.dry_run(fixture('eligibility.json'), fixture('binding.json'), out), 0)
        self.assertIn('F11 fleet (spend) at +660000 ms: would run within the recorded authority; no effect in a dry run',
                      out.getvalue().splitlines())
        self.assertIn('Final execution eligible within the recorded authority.', out.getvalue())

    def test_missing_producer_proof_authority_or_upstream_refuses(self):
        # Catches a closed producer, a missing ticket, missing authority or an unobserved no-paste route.
        binding = fixture('binding.json')
        r = fixture('eligibility.json'); r['producers'][5]['merged_at_head'] = False
        self.assertEqual(kit.eligibility(r, binding), ['Producer #636 has no verified merge at its approved head (a closed issue is not one).'])
        r = fixture('eligibility.json'); r['producers'] = [p for p in r['producers'] if p['ticket'] != 637]
        self.assertEqual(kit.eligibility(r, binding), ['Producer #637 has no verified merge in the record.'])
        for scope in ('spending', 'secret', 'cleanup', 'companion'):
            r = fixture('eligibility.json'); r['authority'][scope] = None
            self.assertEqual(kit.eligibility(r, binding), ['No recorded %s authority for these exact steps and counts.' % scope])
        r = fixture('eligibility.json'); r['upstream'] = {'state': 'not_shipped', 'evidence': None}
        self.assertEqual(kit.eligibility(r, binding), ['The no-paste route needs the observed CloudRoom agent-side save-secret '
                                                       'contribution; it stays Unverified.'])
        paste = fixture('binding.json'); paste['route']['secret_route'] = 'protected_paste'
        self.assertEqual(kit.eligibility(r, paste), [])
        r = fixture('eligibility.json'); r['graph']['fingerprint'] = '4' * 64
        self.assertEqual(kit.eligibility(r, binding), ['The binding names another graph revision than the eligibility record.'])

    def test_an_unbound_or_unsafe_binding_refuses(self):
        # Catches an unbound candidate, scope or count, a seeded or reused host and an unsafe cleanup.
        record = fixture('eligibility.json')
        cases = [(lambda b: b['candidate'].pop('manifest_sha256'), 'The bound candidate is malformed.'),
                 (lambda b: b['host'].update(fresh_machine=False), 'The host must be a fresh machine on the candidate\'s target with no seeded OpenWiz state.'),
                 (lambda b: b['host'].update(seeded_openwiz_state=True), 'The host must be a fresh machine on the candidate\'s target with no seeded OpenWiz state.'),
                 (lambda b: b['scope']['app_repositories'].append('syn-owner/other'), 'The scope must be one throwaway repository, with the App on it only.'),
                 (lambda b: b['scope'].update(companion_repository=b['scope']['repository']), 'The companion must be a different repository.'),
                 (lambda b: b['counts'].update(fleet_threads=2), 'The counts are unbound: one fleet thread, one loop, at most one App registration and one companion.'),
                 (lambda b: b['counts'].update(app_registrations=2), 'The counts are unbound: one fleet thread, one loop, at most one App registration and one companion.'),
                 (lambda b: b['counts'].pop('builders'), 'The counts are unbound: one fleet thread, one loop, at most one App registration and one companion.'),
                 (lambda b: b.update(credit_bound=0), 'The credit bound must be a positive number of Cloud Credits.'),
                 (lambda b: b['route'].update(identity='personal_login'), 'The route is inconsistent: the skip is personal_login, skipped, not_used.'),
                 (lambda b: b['cleanup'].append({'resource': 'all_repositories', 'action': 'delete'}), 'Unsafe cleanup: only bound test-owned resources, with test threads and loops stopped.'),
                 (lambda b: b['cleanup'].append({'resource': 'raw_evidence', 'action': 'delete'}), 'Unsafe cleanup: only bound test-owned resources, with test threads and loops stopped.'),
                 (lambda b: b.update(cleanup=[c for c in b['cleanup'] if c['resource'] != 'test_loops']), 'Unsafe cleanup: only bound test-owned resources, with test threads and loops stopped.')]
        for edit, expected in cases:
            with self.subTest(expected):
                b = fixture('binding.json'); edit(b)
                self.assertEqual(kit.eligibility(record, b), [expected])
        out = io.StringIO()
        bad = fixture('binding.json'); bad['cleanup'] = []
        self.assertEqual(kit.dry_run(record, bad, out), 5)
        self.assertIn('Final execution refused: Unsafe cleanup: only bound test-owned resources, with test threads and loops stopped.',
                      out.getvalue())


if __name__ == '__main__':
    unittest.main()
