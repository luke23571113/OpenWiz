"""Review regressions. Only synthetic endpoints/processes and local Git."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import runpy
import signal
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FixtureCase = runpy.run_path(str(HERE / 'test_smoke.py'))['FixtureCase']


class Review(FixtureCase):
    def test_r2_live_tick_is_restricted_to_the_audited_plan(self):
        source = self.root / 'source'
        subprocess.run(['git', 'init', '-q', str(source)], check=True)
        subprocess.run(['git', '-C', str(source), '-c', 'user.name=Synthetic',
                        '-c', 'user.email=synthetic@example.invalid',
                        'commit', '--allow-empty', '-qm', 'synthetic source'], check=True)
        head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
        marker = self.root / 'effect'
        text = self.fake.read_text().replace("case = sys.argv[1]", "case = sys.argv[1]\nif sys.argv[1:3] == ['fleet', 'tick'] and '--dry-run' not in sys.argv:\n    (root / 'effect').write_text('tick dispatched')")
        self.fake.write_text(text)
        self.kit['artifacts'][str(self.fake)] = self.sha(self.fake)
        self.kit['artifacts'][str(HERE / 'smoke.py')] = self.sha(HERE / 'smoke.py')
        self.kit.update(mode='live', source={'checkout': str(source), 'head': head})
        plan = self.restricted_tick(self.kit['steps'][0])

        def approved():
            return hashlib.sha256(json.dumps(self.kit, sort_keys=True, ensure_ascii=True,
                separators=(',', ':')).encode()).hexdigest()
        # The restriction module is code the live run executes: it must be pinned.
        self.assertEqual(self.report(self.run_tool('--execute', approved()), 2)['reason'], 'invalid_kit')
        self.kit['artifacts'][str(HERE / 'restriction.py')] = self.sha(HERE / 'restriction.py')
        # The preview the tick would execute names the never-started ticket.
        self.replies['fleet tick --dry-run'] = {'exit': 0, 'out': json.dumps(
            dict(plan, actions=[dict(plan['actions'][0], ticket=9004)]))}
        doc = self.report(self.run_tool('--execute', approved()), 3)
        self.assertEqual(doc['reason'], 'out_of_scope')
        self.assertEqual(self.ticks(), [])
        self.assertFalse(marker.exists())
        # With the audited preview, the live tick runs once, pinned to it.
        self.restricted_tick(self.kit['steps'][0])
        self.report(self.run_tool('--execute', approved()), 0)
        self.assertEqual(self.ticks(), [['fleet', 'tick', '--expect-plan',
                                         str(self.state / 'fleet-expected-plan.json'), '--json']])
        self.assertTrue(marker.exists())

    def test_r6_timeout_reaps_the_real_pty_drivers_new_session(self):
        # Adopt a leaking baseline child so this regression can clean it up
        # even before the fix. Only descendants of this test can be adopted.
        libc = ctypes.CDLL(None, use_errno=True)
        self.assertEqual(libc.prctl(36, 1, 0, 0, 0), 0)
        pid_file = self.root / 'child-pid'
        child = self.root / 'synthetic-terminal.py'
        child.write_text('import os, pathlib, signal\n'
                         f'pathlib.Path({str(pid_file)!r}).write_text(str(os.getpid()))\n'
                         'print("Synthetic child started", flush=True)\nsignal.pause()\n')
        driver = ROOT / 'tests/terminal/pty_drive.py'
        python = str(Path(sys.executable).resolve())
        self.kit['artifacts'].update({python: self.sha(Path(python)), str(driver): self.sha(driver), str(child): self.sha(child)})
        step = self.kit['steps'][0]
        step['kind'] = 'read'
        step['argv'] = [python, '-I', str(driver), '80', '24',
                        json.dumps([{'wait': 'Never printed', 'timeout': 30}]), python, '-I', str(child)]
        # Keep the fixture's required fleet write separate from the timed probe.
        self.kit['steps'].append({'id': 'fleet_write', 'claim': 'fleet', 'kind': 'write',
            'argv': [str(self.fake), 'fleet'], 'exit': 0,
            'checks': [{'path': '/count', 'equals': 1}]})
        result = self.invoke()
        self.assertTrue(pid_file.exists(), 'the child actually ran in the PTY')
        pid = int(pid_file.read_text())
        try:
            self.assertEqual(self.report(result, 3)['reason'], 'timeout')
            self.assertFalse(Path(f'/proc/{pid}').exists(), 'the terminal child must be gone and reaped')
        finally:
            if Path(f'/proc/{pid}').exists():
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    os.waitpid(pid, 0)
                except ChildProcessError:
                    pass


    def test_r8_cleanup_readback_is_bounded_and_never_repeats_write(self):
        helper = HERE / 'cleanup.py'
        python = str(Path(sys.executable).resolve())
        gh = self.root / 'synthetic-gh'
        gh.write_text(r'''#!/usr/bin/env python3
import json, pathlib, sys
root = pathlib.Path(__file__).parent
if sys.argv[1:3] == ['issue', 'edit']:
    with (root / 'cleanup-writes').open('a') as stream:
        stream.write('write\n')
    print('{}')
else:
    mode = (root / 'readback-mode').read_text()
    if mode == 'stderr':
        sys.stderr.write('synthetic noisy stderr ' * 1024)
    labels = [{'name': 'X' * 16384}] if mode == 'stdout' else []
    print(json.dumps({'number': 9004, 'state': 'OPEN', 'labels': labels}))
''')
        gh.chmod(0o700)
        wrapper = self.root / 'small-limit-runner.py'
        wrapper.write_text('import runpy\n'
            f'module=runpy.run_path({str(HERE / "smoke.py")!r})\n'
            "module['command'].__globals__['LIMIT']=4096\n"
            "raise SystemExit(module['main']())\n")
        self.kit['artifacts'].update({python: self.sha(Path(python)),
            str(helper): self.sha(helper), str(gh): self.sha(gh)})
        self.kit['steps'][0] = {'id': 'cleanup_write', 'claim': 'fleet', 'kind': 'write',
            'argv': [python, '-I', str(helper), '--gh', str(gh), '--repo',
                     'synthetic-owner/synthetic-repo', '--ticket', '9004', '--action', 'unlabel'],
            'exit': 0, 'checks': [{'path': '/state', 'equals': 'OPEN'},
                                 {'path': '/needs_info', 'equals': False}]}
        self.kit_path.write_text(json.dumps(self.kit))
        (self.root / 'replies.json').write_text(json.dumps(self.replies))
        writes = self.root / 'cleanup-writes'
        for mode in ('stdout', 'stderr', 'normal'):
            with self.subTest(mode=mode):
                if writes.exists():
                    writes.unlink()
                self.state = self.root / ('cleanup-' + mode)
                (self.root / 'readback-mode').write_text(mode)
                argv = [python, '-I', str(wrapper), '--kit', str(self.kit_path),
                        '--state', str(self.state), '--fixture']
                code = 3 if mode == 'stdout' else 0
                result = subprocess.run(argv, capture_output=True, text=True, timeout=10)
                doc = self.report(result, code)
                self.assertEqual(doc['reason'], 'uncertain_write' if mode == 'stdout' else 'none')
                self.assertEqual(writes.read_text().splitlines(), ['write'])
                before = self.call_list()
                result = subprocess.run(argv, capture_output=True, text=True, timeout=10)
                self.report(result, code)
                self.assertEqual(writes.read_text().splitlines(), ['write'])
                if mode == 'stdout':
                    # Resume may recheck the bundle but cannot dispatch a later
                    # step or repeat this unknown cleanup write/readback.
                    self.assertNotIn(['send'], self.call_list())
                    self.assertEqual(self.call_list(), before + [['ls', '--json']])


if __name__ == '__main__':
    unittest.main()
