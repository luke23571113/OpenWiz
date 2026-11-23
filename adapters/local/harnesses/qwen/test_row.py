import importlib.machinery, importlib.util, json, os, re, signal, subprocess, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
FAKE = os.path.join(HERE, 'fake')
LIB = os.environ.get('FAKE_CLI_LIB') or os.path.join(HERE, '..', '..', 'fixtures')
SID = '123e4567-e89b-12d3-a456-426614174000'
FIRST = 'Take up example/site#7 with the build-ticket skill.'
WOKEN = 'You were woken: take up example/site#7 again, with the build-ticket skill.'
START = ['--output-format', 'stream-json', '--session-id', SID, '--model', 'synthetic-1', '--approval-mode', 'yolo',
         FIRST]
WAKE = ['--output-format', 'stream-json', '--resume', SID, '--model', 'synthetic-1', '--approval-mode', 'yolo', WOKEN]
GOOD = [START, WAKE] + [START[:7] + [m, FIRST] for m in ('plan', 'default', 'auto-edit', 'auto')]
BAD = {
    'the deprecated -p prompt flag': START[:8] + ['-p', FIRST],
    'no prompt': START[:8],
    'two prompts': START + ['again'],
    'an approval mode qwen does not have': START[:7] + ['never', FIRST],
    '--yolo with --approval-mode': START[:8] + ['--yolo', FIRST],
    '--session-id with --resume': WAKE[:4] + ['--session-id', SID] + WAKE[4:],
    'a session id that is not a UUID': START[:3] + ['fake-0123456789ab'] + START[4:],
    'text output': ['--output-format', 'text'] + START[2:],
    'an effort flag qwen does not have': START[:8] + ['--reasoning-effort', 'high', FIRST],
    'the start prompt on a resume': WAKE[:8] + [FIRST],
    'a wake prompt on a new session': START[:8] + [WOKEN],
    'the serve subcommand': ['serve'],
    'the removed auth subcommand': ['auth', 'qwen-oauth'],
    'no --model': START[:4] + START[6:],
}
SIGNED_OUT = ('none', 'qwen-oauth', 'openai', 'openai-env-key', 'provider-key', 'provider-env-key', 'enforced-type',
              'subscription-expired')


def run(argv, **env):
    return subprocess.run([sys.executable, FAKE] + argv, capture_output=True, text=True, timeout=30,
                          env=dict(os.environ, FAKE_CLI_LIB=LIB, **env))


def supervisor_shape():
    if not os.path.isdir('/proc/self'):
        return ['this row holds on Linux only: its detached StopFailure hook supervisor needs the Linux subreaper']
    os.environ['FAKE_CLI_LIB'] = LIB
    loader = importlib.machinery.SourceFileLoader('qwen_fake', FAKE)
    fake = importlib.util.module_from_spec(importlib.util.spec_from_loader('qwen_fake', loader))
    loader.exec_module(fake)
    pid, _ = fake.stop_failure_hook_supervisor('stop-failure-hook')
    try:
        fds = {fd: os.readlink('/proc/%d/fd/%d' % (pid, fd)) for fd in (0, 1, 2, 3)}
        shape = (os.getsid(pid), os.getpgid(pid), fds[0], fds[1], fds[2], fds[3].startswith('pipe:'))
        if shape != (pid, pid, os.devnull, os.devnull, os.devnull, True) or os.getsid(0) == pid:
            return ["the fake's StopFailure hook supervisor is not qwen's detached shape: %r" % (shape,)]
        return []
    finally:
        os.killpg(pid, signal.SIGKILL)
        os.waitpid(pid, 0)


def main():
    with open(os.path.join(HERE, 'row.json')) as f:
        row = json.load(f)
    failures = []
    for name, argv in BAD.items():
        p = run(argv, FAKE_CLI_SIGNED_OUT='1')
        if p.returncode != 2 or p.stdout:
            failures.append('the fake took %s (exit %d)' % (name, p.returncode))
    for argv in GOOD:
        p = run(argv, FAKE_CLI_SIGNED_OUT='1')
        lines = p.stdout.splitlines()
        if p.returncode != 1 or len(lines) != 1 or json.loads(lines[0])['type'] != 'result' or \
                not any(re.search(s, lines[0], re.I) for s in row['signed_out']):
            failures.append('the fake refused a documented line %r (exit %d)' % (argv[:8], p.returncode))
    failures += supervisor_shape()
    seen = set()
    for auth in SIGNED_OUT:
        p = run(START, FAKE_CLI_SIGNED_OUT='1', FAKE_QWEN_AUTH=auth)
        lines = p.stdout.splitlines()
        if p.returncode != 1 or len(lines) != 1 or lines[0] in seen or \
                not any(re.search(s, lines[0], re.I) for s in row['signed_out']):
            failures.append("the row's signed_out misses qwen's %s refusal (exit %d)" % (auth, p.returncode))
        seen.add(lines[0] if lines else '')
    p = run(WAKE, FAKE_QWEN_CHAT_RECORDING='false')
    if p.returncode != 1 or p.stdout or p.stderr != 'No saved session found with ID %s. Run `qwen --resume` without an ' \
            'ID to choose from existing sessions.\n' % SID or any(re.search(s, p.stderr, re.I) for s in row['signed_out']):
        failures.append('a wake with chat recording off is not qwen\'s missing-session exit, or reads as signed out')
    with open(os.path.join(HERE, 'README.md')) as f:
        commands = f.read().partition('## The commands')[2].partition('\n## ')[0]
    if not re.search(r'- Start: .*\n- Wake: .*\n(.*\n)?.*`general\.chatRecording`', commands):
        failures.append('the README does not name the general.chatRecording prerequisite beside start and wake')
    if 'subscription_credentials.json' not in row['login'] or 'oauth_creds.json' in row['login']:
        failures.append("the row's login does not name the Qwen subscription sign-in, subscription_credentials.json")
    if sorted(row['modes']) != sorted(['plan', 'default', 'auto-edit', 'auto', 'yolo']) or \
            any(v != ['--approval-mode', k] for k, v in row['modes'].items()):
        failures.append("the row's modes are not qwen's five --approval-mode values")
    for line in failures:
        print('fail: ' + line)
    print('test_row.py: %d bad lines refused, %d documented lines taken, %d sign-in refusals checked, modes checked: %s'
          % (len(BAD), len(GOOD), len(SIGNED_OUT), 'fail' if failures else 'ok'))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
