#!/usr/bin/env python3
import json, os, re, subprocess, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..'))
import test_harnesses as runner

ROWS = os.path.dirname(HERE)
FAKE = os.path.join(HERE, 'fake')
UUID = r'[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}'
SID = '0b8f2c1e-5d4a-4c3b-9a2f-6e7d8c9b0a1f'
failures = []


def check(what, ok):
    print('%s goose row: %s' % ('pass' if ok else 'fail', what))
    if not ok:
        failures.append(what)


def fake_exit(args, mode='auto'):
    env = {'PATH': os.environ.get('PATH', ''), 'FAKE_CLI_LIB': runner.FIXTURES}
    if mode is not None:
        env['GOOSE_MODE'] = mode
    return subprocess.run([sys.executable, '-I', FAKE] + args, env=env, capture_output=True, timeout=30).returncode


START = 'Build the ticket: example/site#7, with the build-ticket skill.'
WAKE = 'You were woken: take up example/site#7 again, with the build-ticket skill.'
REFUSED = [
    ('a session id without --resume', ['run', '--session-id', SID, '--model', 'm', '--output-format', 'json', '-t', START]),
    ('--no-session with a name', ['run', '--no-session', '-n', SID, '--model', 'm', '--output-format', 'json', '-t', START]),
    ('an output format goose does not have', ['run', '-n', SID, '--model', 'm', '--output-format', 'yaml', '-t', START]),
    ('-t and an instructions file together', ['run', '-n', SID, '--model', 'm', '--output-format', 'json', '-i', 'x.md',
                                              '-t', START]),
    ('no text at all', ['run', '-n', SID, '--model', 'm', '--output-format', 'json']),
    ('an effort flag goose does not have', ['run', '-n', SID, '--model', 'm', '--output-format', 'json', '--effort',
                                            'high', '-t', START]),
    ('a name that is not the driver\'s uuid', ['run', '-n', 'project-x', '--model', 'm', '--output-format', 'json', '-t',
                                               START]),
    ('a wake prompt without --resume', ['run', '-n', SID, '--model', 'm', '--output-format', 'json', '-t', WAKE]),
    ('a start prompt with --resume', ['run', '-n', SID, '--resume', '--model', 'm', '--output-format', 'json', '-t',
                                      START]),
]
for what, args in REFUSED:
    check('the fake exits 2 on %s' % what, fake_exit(args) == 2)
good = ['run', '-n', SID, '--model', 'm', '--output-format', 'json', '-t', START]
check('the fake exits 2 on a documented line without GOOSE_MODE=auto', fake_exit(good, None) == 2 and
      fake_exit(good, 'approve') == 2)

row = runner.local.read_row(os.path.join(HERE, 'row.json'), 'goose')
with runner.ThrowawayMachine(ROWS, 'goose', 'goose', FAKE, 'auto', ['GOOSE_MODE']) as env:
    code, out = env.start(FAKE_CLI_RECORD_ONLY='1', GOOSE_MODE='approve')
    woke = env.driver('wake', out) if code == 0 else (1, {})
    env.driver('stop', out)
    turns = env.records()
    sid = turns[0]['session'] if turns else ''
    check('the driver chose a UUID session id and named the session with it at start and wake',
          code == 0 and woke[0] == 0 and len(turns) == 2 and re.fullmatch(UUID, sid) is not None and
          turns[1]['session'] == sid)
    check('a turn runs the documented goose run lines exactly',
          len(turns) == 2 and turns[0]['argv'][:-1] == ['run', '-n', sid, '--model', 'synthetic-1', '--output-format',
                                                        'json', '-t'] and
          turns[1]['argv'][:-1] == ['run', '-n', sid, '--resume', '--model', 'synthetic-1', '--output-format', 'json',
                                    '-t'] and turns[0]['argv'][-1].startswith('Build the ticket: example/site#7') and
          turns[1]['argv'][-1].startswith('You were woken'))
    check("the row's GOOSE_MODE=auto wins over the user's own GOOSE_MODE=approve",
          len(turns) == 2 and all(t['env'] == {'GOOSE_MODE': 'auto'} for t in turns))
    check('the row reads no login: no field names a key, a token or the keyring file',
          not re.search(r'(?i)api.?key|token|secrets\.yaml', json.dumps([row['start'], row['wake'], row['env'],
                                                                          row['modes']])))

sys.exit(1 if failures else 0)
