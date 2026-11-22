#!/usr/bin/env python3
"""The kilo row's own checks, run by test_harnesses.py after the contract and kit checks."""
import os, sys
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..'))
import test_harnesses as h

ROWS = os.path.dirname(HERE)
FAKE = os.path.join(HERE, 'fake')


def without_any_agent_cli(env):
    # SAFETY: only the machine's own bin folder and PATH folders that hold no agent CLI, real or stub.
    keep = [d for d in os.environ.get('PATH', '').split(os.pathsep)
            if d and not any(os.path.exists(os.path.join(d, c)) for c in h.STUBS)]
    return os.pathsep.join([os.path.join(env.folder, 'bin')] + keep)


def not_installed():
    with h.ThrowawayMachine(ROWS, 'kilo', mode='default') as env:
        says = lambda out: out['error'] == 'harness kilo is not installed here' and \
            out['next'] == 'install kilo on this machine and sign in to it yourself, then start again'
        return env.start_refused_starting_nothing(says, PATH=without_any_agent_cli(env))


def not_signed_in():
    with h.ThrowawayMachine(ROWS, 'kilo', 'kilo', FAKE, 'default', ['KILO_NO_DAEMON']) as env:
        code, out = env.start(FAKE_KILO_SIGNED_OUT='1')
        if code == 0:
            env.driver('stop', out)
        if code != 1 or h.kit.invalid(out, h.ERROR) is not None or env.records():
            return False
        log = out['next'].partition('read ')[2].partition(', fix what it says there')[0]
        try:
            with open(log) as f:
                said = f.read()
        except OSError:
            return False
        return 'the first turn ended at once' in out['error'] and 'kilo auth login' in said


failed = [name for name, check in (('not installed: a D3 error whose next says to install and sign in', not_installed),
                                    ('not signed in: a D3 error whose next points at the log naming kilo auth login',
                                     not_signed_in)) if not check()]
for name in failed:
    print('fail kilo test_row.py: ' + name)
sys.exit(1 if failed else 0)
