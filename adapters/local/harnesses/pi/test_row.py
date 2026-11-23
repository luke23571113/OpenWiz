#!/usr/bin/env python3
import os, subprocess, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
FAKE = os.path.join(HERE, 'fake')
LIB = os.path.join(HERE, '..', '..', 'fixtures')
ID = '0b6f3c2e-5a7d-4e1f-9c3b-2d8a6e4f1a07'
START = 'Build the ticket: example/site#7, with the build-ticket skill. Keep one status note there.'
WAKE = 'You were woken: take up example/site#7 again, with the build-ticket skill. Edit your own status note there; ' \
       'post no second one.'
REFUSED = {
    'a --session-id that starts with a dot': ['-p', '--mode', 'json', '--session-id', '.' + ID, '--model', 'm', '--', START],
    'a --session-id with a slash': ['-p', '--mode', 'json', '--session-id', 'a/b', '--model', 'm', '--', START],
    '--session-id with --continue': ['-c', '--session-id', ID, '-p', '--model', 'm', '--', WAKE],
    'an unknown --mode': ['-p', '--mode', 'yaml', '--session-id', ID, '--model', 'm', '--', START],
    'a prompt that starts with @, which pi reads as a file': ['-p', '--mode', 'json', '--session-id', ID, '--model', 'm',
                                                             '--', '@' + START],
    'an unknown short option': ['-p', '-x', '--mode', 'json', '--session-id', ID, '--model', 'm', '--', START],
    'a start with no prompt': ['-p', '--mode', 'json', '--session-id', ID, '--model', 'm', '--'],
    'a wake with no session id': ['-p', '--model', 'm', '--', WAKE],
    'a wake prompt on a start line': ['-p', '--mode', 'json', '--session-id', ID, '--model', 'm', '--', WAKE],
    'a start prompt on a wake line': ['--session-id', ID, '-p', '--model', 'm', '--', START],
}
failures = []


def check(what, ok):
    print('%s pi row: %s' % ('pass' if ok else 'fail', what))
    if not ok:
        failures.append(what)


env = dict(os.environ, FAKE_CLI_LIB=LIB)
for what, argv in sorted(REFUSED.items()):
    p = subprocess.run([sys.executable, FAKE] + argv, env=env, capture_output=True, text=True, timeout=30)
    check('the fake exits 2 on ' + what, p.returncode == 2)
sys.exit(1 if failures else 0)
