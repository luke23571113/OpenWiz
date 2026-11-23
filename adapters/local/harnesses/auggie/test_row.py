#!/usr/bin/env python3
import json, os, sys, tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..'))
import test_harnesses as th

ROWS = os.path.dirname(HERE)
FAKE = os.path.join(HERE, 'fake')
ID = '00000000-0000-4000-8000-0000000000a1'


def path_without_auggie(env):
    lone = os.path.join(env.folder, 'python-only')
    os.mkdir(lone)
    os.symlink(sys.executable, os.path.join(lone, 'python3'))
    os.remove(os.path.join(env.folder, 'stubs', 'auggie'))
    return os.pathsep.join([os.path.join(env.folder, 'bin'), os.path.join(env.folder, 'stubs'), lone])


def not_installed():
    with th.ThrowawayMachine(ROWS, 'auggie', mode='full-access') as env:
        return env.start_refused_starting_nothing(
            lambda out: 'auggie is not installed' in out['error'] and 'install auggie' in out['next'],
            PATH=path_without_auggie(env))


def not_signed_in():
    with th.ThrowawayMachine(ROWS, 'auggie', 'auggie', FAKE, 'full-access') as env:
        code, out = env.start(FAKE_CLI_SIGNED_OUT='1')
        return code == 1 and th.kit.invalid(out, th.ERROR) is None and 'not signed in' in out.get('error', '') \
            and 'auggie auth login' in out.get('next', '')


def first_json_line_names_the_session():
    with tempfile.TemporaryDirectory() as state:
        th.local.STATE = state
        with open(os.path.join(state, 'run-synthetic.log'), 'w') as f:
            f.write('\n'.join([
                json.dumps({'type': 'session', 'version': 3, 'id': ID, 'timestamp': '2026-11-22T00:00:00.000Z',
                            'cwd': '/tmp/synthetic-worktree'}),
                json.dumps({'type': 'message_start', 'id': 'msg-synthetic-2'}),
                json.dumps({'type': 'turn_end', 'id': 'turn-synthetic-3'})]) + '\n')
        with open(os.path.join(HERE, 'row.json')) as f:
            session = json.load(f)['session']
        return th.local.reported_session('run-synthetic', session, {'output_from': 0}) == ID


def main():
    checks = [('not installed: a D3 error whose next says to install auggie, starting nothing', not_installed),
              ('not signed in: a D3 error that says so, whose next names auggie auth login', not_signed_in),
              ('the session header: the driver reads the id from 1.2.2\'s first JSON line', first_json_line_names_the_session)]
    ok = True
    for what, check in checks:
        passed = check()
        print('%s auggie row: %s' % ('pass' if passed else 'fail', what))
        ok = ok and passed
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
