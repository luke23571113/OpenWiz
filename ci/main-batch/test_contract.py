#!/usr/bin/env python3
"""Offline reference reader/proofs for C6. Never calls GitHub or admits work.

Claim CS3: only exact, complete combined work covers the stated batch.
The old plan gate checks lane results, but does not bind batch membership,
current attempts, external checks or a candidate's complete work inventory.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/actions/docs-only'))
import gate

FIXTURES = Path(__file__).resolve().parent / 'fixtures/contract'


def coverage_refusals(raw, context):
    """Offline reference seam for #2314/#2319, never evidence authenticity.

    Context is independently observed, complete and current at the candidate;
    deriving it from this document defeats the contract. No I/O except the
    checked-in schemas is performed here.
    """
    try:
        schema = gate.escapes.strict_json((ROOT / 'contracts/ci-main-batch.v1.schema.json').read_text())
        errors = gate.escapes.lint(schema)
        if errors:
            return errors
        document = gate.escapes.strict_json(raw)
        errors = gate.escapes.errors_of(schema, schema, document, '$')
        errors += gate.escapes.errors_of(schema, schema['$defs']['context'], context, '$context')
        if errors:
            return errors
        batch, execution = document['batch'], document['execution']
        if batch != context['batch'] or execution != context['execution']:
            return ['batch or current execution differs from independently observed context']
        if context['previous_head'] != batch['base']:
            return ['batch overlaps or leaves a gap after the covered checkpoint']
        parent = batch['base']
        for member in batch['members']:
            if member['parent'] != parent or member['merge'] == parent:
                return ['membership is not a contiguous ordered main range']
            parent = member['merge']
        if parent != batch['head'] or batch['base'] == batch['head']:
            return ['membership does not end at the combined head']
        for key in ('pull_request', 'head', 'merge'):
            if len({m[key] for m in batch['members']}) != len(batch['members']):
                return ['ambiguous duplicate member ' + key]
        if any(sha == '0'*40 for sha in [batch['base'], batch['head'],
               *[m[k] for m in batch['members'] for k in ('head', 'merge', 'parent')]]):
            return ['zero commit is not an immutable identity']
        boundaries = {batch['base'], *[m['merge'] for m in batch['members'][:-1]]}
        if execution['event_base'] not in boundaries:
            return ['execution event base is not a batch boundary before the tested head']
        errors = gate.escapes.refusals(document['plan'])
        if errors:
            return errors
        plan = gate.escapes.strict_json(document['plan'])
        run = plan['run']
        if (plan['selection']['mode'] != 'full' or run['base_branch'] != 'main'
                or any(run[k] != execution[k] for k in ('id', 'attempt', 'event'))
                or run['base'] != execution['event_base'] or run['head'] != batch['head']):
            return ['plan is not full work for the exact combined main execution']
        lanes = plan['lanes']
        inventory = [t for lane in [lanes[k] for k in ('always','rust','web','site')]
                     + lanes['skills'] for t in lane['tests']]
        if sorted(inventory) != sorted(context['inventory']):
            return ['full plan omits or adds work against the independent candidate inventory']
        expected = {k: lanes[k]['tests'] for k in ('always','rust','web')}
        for kind in ('site','release'):
            tests = [t for t in lanes['site']['tests'] if t.startswith(kind+':')]
            if tests:
                expected[kind] = tests
        expected.update({'skill:'+s['skill']: s['tests'] for s in lanes['skills']})
        expected.update({'build:web_export': []})
        digest = hashlib.sha256(document['plan'].encode('utf-8')).hexdigest()
        wanted = {k: dict(lane=k, tests=v, plan_sha256=digest, run=run) for k,v in expected.items()}
        receipts = document['receipts']
        if len(receipts) != len(wanted) or {r['lane'] for r in receipts} != set(wanted):
            return ['missing, duplicate or foreign full-work receipt']
        for receipt in receipts:
            actual = dict(receipt, tests=sorted(receipt['tests']))
            if actual != dict(wanted[receipt['lane']], tests=sorted(wanted[receipt['lane']]['tests'])):
                return ['receipt does not bind exact plan, run, attempt and tests']
        outcomes = document['outcomes']
        if (len(outcomes) != len(expected)+1 or {o['name'] for o in outcomes} != {'changes', *expected}
                or any(o['result'] != 'success' for o in outcomes)):
            return ['missing, duplicate, non-success or foreign combined-work result']
        checks = document['checks']
        check_ids = {c['name']: c for c in context['required_checks']}
        if (len(check_ids) != len(context['required_checks']) or 'ci' not in check_ids
                or len(checks) != len(context['required_checks'])
                or {c['name'] for c in checks} != set(check_ids)
                or any(c['result'] != 'success' or c['head'] != batch['head'] for c in checks)):
            return ['missing, duplicate, non-success or foreign required check']
        if any(any(c[k] != check_ids[c['name']][k] for k in ('id', 'attempt')) for c in checks):
            return ['required check does not bind its independently observed current run/attempt']
        ci = next(c for c in checks if c['name'] == 'ci')
        if any(ci[k] != execution[k] for k in ('id', 'attempt')):
            return ['required ci is not the exact current combined execution']
        return []
    except (OSError, ValueError, TypeError, KeyError, RecursionError, gate.escapes.Fail) as error:
        return ['unreadable coverage: ' + str(error)]


class Contract(unittest.TestCase):
    def setUp(self):
        self.record = json.loads((FIXTURES / 'complete.json').read_text())
        self.context = json.loads((FIXTURES / 'expected.json').read_text())

    def refusals(self, document=None, context=None):
        return coverage_refusals(json.dumps(self.record if document is None else document),
                                 self.context if context is None else context)

    def refused(self, document, clue):
        self.assertTrue(self.refusals(document), clue)

    def test_untrusted_shapes_and_claimed_switch_authority_refuse(self):
        for field, value in [('schema','future'), ('switch_authorized', True), ('mode','active')]:
            d = copy.deepcopy(self.record); d[field]=value
            self.refused(d, 'schema is closed; fixtures grant no activation')
        raw = json.dumps(self.record)
        for bad in (raw.replace('"attempt": 1', '"attempt": true', 1),
                    raw[:-1]+', "schema": "openwiz.ci-main-batch.v1"}', 'null', '{'):
            self.assertTrue(coverage_refusals(bad, self.context))


if __name__ == '__main__':
    unittest.main()
