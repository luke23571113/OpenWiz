#!/usr/bin/env python3
# The junie fake accepts only the start and wake the row sends, and exits 2 on anything else, so a
# driver that builds a wrong Junie command line fails the kit instead of passing on a lenient fake.
import json, os, subprocess, sys, tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
FAKE = os.path.join(HERE, 'fake')
LIB = os.path.join(HERE, '..', '..', 'fixtures')
BASE = ['--skip-update-check', '--output-format', 'json']
REFUSED = {
    'text output': ['--skip-update-check', '--output-format', 'text', '--model', 'm', '--task', 'p'],
    'no update-check skip': ['--output-format', 'json', '--model', 'm', '--task', 'p'],
    'no model': BASE + ['--task', 'p'],
    'empty task': BASE + ['--model', 'm', '--task', ''],
    'a bare --resume, which resumes the last session, not this run\'s': BASE + ['--resume', '--model', 'm', '--task', 'p'],
    'a session id without --resume': BASE + ['--session-id', 's-1', '--model', 'm', '--task', 'p'],
    'a session id that is not one': BASE + ['--session-id', 'a b', '--resume', '--model', 'm', '--task', 'p'],
    '--effort, which the row never sends': BASE + ['--model', 'm', '--effort', 'high', '--task', 'p'],
    '--brave, which is interactive only': BASE + ['--model', 'm', '--brave', '--task', 'p'],
    'a positional task': BASE + ['--model', 'm', 'p'],
}


def run(args, **env):
    return subprocess.run([FAKE] + args, capture_output=True, text=True, timeout=30,
                          env=dict(os.environ, FAKE_CLI_LIB=LIB, PYTHONDONTWRITEBYTECODE='1', **env))


def main():
    bad = []
    for why, args in REFUSED.items():
        p = run(args)
        if p.returncode != 2:
            bad.append('fake accepted %s (exit %d)' % (why, p.returncode))
    with tempfile.TemporaryDirectory() as d:
        p = run(BASE + ['--model', 'm', '--task', 'start with the build-ticket skill'], FAKE_JUNIE_SIGNED_OUT='1',
                FAKE_CLI_RECORD=os.path.join(d, 'rec'))
        out = [json.loads(line) for line in p.stdout.splitlines() if line.strip()]
        if p.returncode != 0 or len(out) != 1 or 'sessionId' in out[0] or not out[0].get('errors') or \
                os.path.exists(os.path.join(d, 'rec')):
            bad.append('fake signed out did not answer as Junie 26.9.7 does: one errors line, no sessionId, exit 0, '
                       'and no turn')
    for line in bad:
        print('fail ' + line)
    print('pass junie test_row.py: the fake refuses %d command lines the row never sends, and answers signed out '
          'as Junie does' % len(REFUSED) if not bad else 'fail junie test_row.py: %d problem(s)' % len(bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
