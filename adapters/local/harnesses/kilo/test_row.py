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


# Kilo's own signed-out output, in the shapes its source prints (Kilo CLI v7.8.32):
# provider/error.ts (a 401 through a gateway), kilocode/cloud/auth.ts (no saved login), and the gateway's codes
# that kilocode/kilo-errors.ts reads from a JSON error line's responseBody.
GATEWAY = '{"type":"error","timestamp":0,"sessionID":"fake-signed-out","error":{"name":"APIError","data":' \
          '{"message":"Payment Required","statusCode":402,"responseBody":"{\\"error\\":{\\"code\\":\\"%s\\"}}"}}}'
SIGNED_OUT = ['Error: Unauthorized: request was blocked by a gateway or proxy. Your authentication token may be '
              'missing or expired \u2014 try running `kilo auth login <your provider URL>` to re-authenticate.',
              'Error: Kilo credentials are required; run `kilo auth login`',
              GATEWAY % 'PAID_MODEL_AUTH_REQUIRED']
# Not signed out: the free-model limit ("You need to sign up to keep going ... Or come back later", kilo-errors.ts)
# clears with time too, so it must stay a plain failure, never a 'sign in with kilo auth login' next.
USAGE_LIMIT = GATEWAY % 'PROMOTION_MODEL_LIMIT_REACHED'


def not_signed_in():
    with h.ThrowawayMachine(ROWS, 'kilo', 'kilo', FAKE, 'default', ['KILO_NO_DAEMON']) as env:
        for line in SIGNED_OUT:
            code, out = env.start(FAKE_CLI_SIGNED_OUT='1', FAKE_KILO_SIGNED_OUT_LINE=line)
            if code == 0:
                env.driver('stop', out)
            if code != 1 or h.kit.invalid(out, h.ERROR) is not None or env.records() or \
                    'the harness is not signed in' not in out['error'] or 'kilo auth login' not in out['next']:
                return False
        code, out = env.start(FAKE_CLI_SIGNED_OUT='1', FAKE_KILO_SIGNED_OUT_LINE=USAGE_LIMIT)
        if code == 0:
            env.driver('stop', out)
        return code == 1 and 'the harness failed' in out.get('error', '') and \
            'kilo auth login' not in out.get('next', '')


failed = [name for name, check in (('not installed: a D3 error whose next says to install and sign in', not_installed),
                                    ('not signed in: each of Kilo\'s signed-out lines is a D3 error saying so, whose '
                                     'next names kilo auth login; its free-model limit is not',
                                     not_signed_in)) if not check()]
for name in failed:
    print('fail kilo test_row.py: ' + name)
sys.exit(1 if failed else 0)
