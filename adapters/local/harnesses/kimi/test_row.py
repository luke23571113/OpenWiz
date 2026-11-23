#!/usr/bin/env python3
import json, os, subprocess, sys, tempfile
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
FAKE = os.path.join(HERE, 'fake')
LIB = os.path.join(HERE, '..', '..', 'fixtures')
PROMPT = 'Work on the ticket with the build-ticket skill.'
WOKEN = 'You were woken. Carry on with the build-ticket skill.'
START = ['-p', PROMPT, '--output-format', 'stream-json', '-m', 'kimi-code/kimi-for-coding']

# External: kimi refuses -p with --yolo, --auto or --plan, and --output-format without -p,
# https://github.com/MoonshotAI/kimi-code/blob/56145f849caa305d42acd09b67fb65d11146f887/apps/kimi-code/src/cli/options.ts
REFUSED = [START + ['--yolo'], START + ['-y'], START + ['--yes'], START + ['--auto-approve'], START + ['--auto'],
           START + ['--plan'], START[2:], START + ['-p', PROMPT], ['-p', ' '] + START[2:],
           ['-p', PROMPT, '--output-format', 'json', '-m', 'm'], ['-p', PROMPT, '-m', 'm'],
           ['-p', PROMPT, '--output-format', 'stream-json'], ['--continue'] + START, START + ['extra'],
           ['-S', '', '-p', WOKEN], ['-S', 'fake-1', '-p', WOKEN, '--yolo'], ['-S', 'fake-1'], ['--prompt=' + PROMPT]]
ALLOWED = [(START, None), (['--model', 'm', '--output-format', 'stream-json', '--prompt', PROMPT], None),
           (['-S', 'fake-1', '-p', WOKEN], 'fake-1'), (['--resume', 'fake-2', '--prompt', WOKEN, '-m', 'm'], 'fake-2')]


def run(argv, folder):
    env = dict(PATH=os.environ.get('PATH', ''), FAKE_CLI_LIB=LIB, FAKE_CLI_RECORD=os.path.join(folder, 'record'),
               FAKE_CLI_RECORD_ONLY='1', KIMI_CODE_NO_AUTO_UPDATE='1')
    return subprocess.run([sys.executable, '-I', FAKE] + argv, env=env, capture_output=True, text=True, timeout=60)


def main():
    bad = []
    with tempfile.TemporaryDirectory() as folder:
        for argv in REFUSED:
            p = run(argv, folder)
            if p.returncode != 2 or p.stdout:
                bad.append('allowed %r (exit %d)' % (argv, p.returncode))
        for argv, session in ALLOWED:
            p = run(argv, folder)
            lines = [json.loads(x) for x in p.stdout.splitlines()]
            hint = [x for x in lines if x.get('type') == 'session.resume_hint']
            if p.returncode != 0 or (session is None) != (len(hint) == 1) or \
                    (hint and hint[0]['command'] != 'kimi -r ' + hint[0]['session_id']):
                bad.append('refused or misreported %r (exit %d)' % (argv, p.returncode))
        if not bad:
            with open(os.path.join(folder, 'record')) as f:
                sessions = [json.loads(x)['session'] for x in f]
            if sessions[2:] != ['fake-1', 'fake-2']:
                bad.append('the woken turns got %r' % sessions[2:])
    for line in bad:
        print('fail: the fake ' + line)
    print('fail' if bad else 'pass: the fake takes only the documented kimi command lines')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
