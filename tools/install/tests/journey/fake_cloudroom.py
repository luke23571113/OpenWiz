"""Test-only stand-in for the installed CloudRoom tool (runtime/cloudroom/cloudroom.py, #2201). Synthetic only.

The journey's synthetic release ships it at that runtime path, as it ships its
fixture `openwiz`. setup.py loads it and calls `status(Host(), state)`; it
answers the scenario's CloudRoom result ($SYNTHETIC_SCENARIO `cloudroom`:
`ok` is a current signed-in account) with the tool's own public codes, and
reads nothing on this computer. The real tool's install and sign-in proofs are
its own tests (tools/install/cloudroom/test_cloudroom.py).
"""
import json
import os


class Host:
    """No computer is read."""


def status(host, state_dir):
    with open(os.environ['SYNTHETIC_SCENARIO'], encoding='utf-8') as handle:
        scenario = json.load(handle)
    return {'code': 'cloudroom_login_verified' if scenario.get('cloudroom') == 'ok' else 'cloudroom_login_missing'}
