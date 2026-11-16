#!/usr/bin/env python3
"""Red-first stand-in (#637): only the two existing contract cores, no kit rules yet."""
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


receipt_check = load('first_merge_receipt_check', ROOT / 'tools/install/tests/setup-onboard-contract/check.py')
result_check = load('first_merge_result_check', ROOT / 'tools/install/tests/first-hour-contract/check.py')


def lists(report):
    return {'problems': report.problems, 'failures': report.failures, 'unproven': report.unproven}


def validate(receipt_text, result_text, fleet, binding, record):
    receipt, result = receipt_check.check_text(receipt_text), result_check.check_text(result_text)
    codes = {'receipt': lists(receipt), 'result': lists(result)}
    refusals = []
    if receipt.problems:
        refusals.append("setup-onboard.v1's checks refuse the receipt: " + ', '.join(receipt.problems))
    if result.problems:
        refusals.append("first-hour.v1's checks refuse the result: " + ', '.join(result.problems))
    verdict = json.loads(receipt_text).get('verdict') if not receipt.problems else None
    return refusals, 'refused' if refusals else verdict, codes


def eligibility(record, binding):
    return []


def dry_run(record, binding, out=sys.stdout):
    return 0
