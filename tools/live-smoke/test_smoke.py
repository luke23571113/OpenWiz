"""Command-boundary proofs. All executable responses and identifiers are synthetic."""
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RUNNER = Path(__file__).with_name('smoke.py')
# The runner's own journal/replay code, loaded by path (this folder's http.py
# must not shadow the standard library), to set state as an interruption would.
import importlib.util
_SPEC = importlib.util.spec_from_file_location('live_smoke_runner_for_tests', RUNNER.resolve())
SMOKE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(SMOKE)
CLAIMS = ['fleet', 'swarms', 'service', 'loops', 'cockpit', 'decisions',
          'json', 'send', 'new', 'app', 'read_safety']


class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.calls = self.root / 'calls'
        self.fake = self.root / 'fake-room-cli'
        self.fake.write_text('''#!/usr/bin/env python3
import json, pathlib, sys
root = pathlib.Path(__file__).parent
with (root / 'calls').open('a') as log:
    log.write(json.dumps(sys.argv[1:]) + '\\n')
case = sys.argv[1]
replies = json.loads((root / 'replies.json').read_text())
key = ' '.join(sys.argv[1:4])
reply = replies[key] if key in replies else replies[case]
print(reply['out'])
print('SENSITIVE_DIAGNOSTIC', file=sys.stderr)
sys.exit(reply['exit'])
''')
        self.fake.chmod(0o700)
        self.replies = {'ls': {'exit': 0, 'out': json.dumps({
            'schema': 'openwiz.inventory.v1', 'coverage': {'state': 'complete'},
            'gaps': [], 'data': {'sessions': []}})}}
        steps = []
        for claim in CLAIMS:
            self.replies[claim] = {'exit': 0, 'out': json.dumps({
                'count': 1, 'id': 'thr_synthetic_private', 'known': True})}
            steps.append({'id': claim, 'claim': claim,
                          'kind': 'write' if claim in ('fleet', 'send', 'new') else 'read',
                          'argv': [str(self.fake), claim], 'exit': 0,
                          'checks': [{'path': '/count', 'equals': 1},
                                     {'path': '/known', 'equals': True}]})
        self.kit = {'schema': 'openwiz.live-smoke-kit.v1', 'mode': 'fixture',
                    'cwd': str(self.root), 'openwiz': str(self.fake),
                    'artifacts': {str(self.fake): self.sha(self.fake)},
                    'env': {}, 'timeout_seconds': 2, 'steps': steps}
        self.base_kit = json.loads(json.dumps(self.kit))
        self.kit_path = self.root / 'kit.json'
        self.state = self.root / 'state'

    @staticmethod
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def run_tool(self, *args):
        self.kit_path.write_text(json.dumps(self.kit))
        (self.root / 'replies.json').write_text(json.dumps(self.replies))
        return subprocess.run([sys.executable, '-I', str(RUNNER),
                               '--kit', str(self.kit_path), '--state', str(self.state),
                               *args], capture_output=True, text=True, timeout=10)

    def invoke(self):
        return self.run_tool('--fixture')

    def fleet_block(self):
        """The fleet claim as launch-fleet leaves it to the runner: a CLI read,
        an event (launch-fleet acts between sittings) and a readback that
        repeats the block until the fleet's merges show."""
        self.kit['steps'][0].update(kind='read', argv=[str(self.fake), 'fleet', '9001', '--json'])
        wait = {'id': 'fleet_done', 'claim': 'fleet', 'kind': 'await',
                'argv': [str(self.fake), 'done'], 'exit': 0,
                'checks': [{'path': '/safe', 'equals': True}],
                'until': [{'path': '/merged', 'equals': 2}], 'again_from': 'fleet'}
        self.replies['fleet 9001 --json'] = {'exit': 0, 'out': '{"count":1,"known":true}'}
        self.replies['done'] = {'exit': 0, 'out': '{"merged":0,"safe":true}'}
        self.kit['steps'][1:1] = [{'id': 'fleet_event', 'claim': 'fleet', 'kind': 'event'}, wait]

    def fleet_reads(self):
        return self.call_list().count(['fleet', '9001', '--json'])

    def rewrite_journal(self, edit, events=None):
        """Rewrite the journal's events (re-chained) and save their replay as the
        checkpoint: a consistent synthetic state, never a bare checkpoint edit."""
        if events is None:
            _, events = SMOKE.read_journal(self.state)
        events = [edit(dict(e)) for e in events]
        prev, lines = '0' * 64, []
        for seq, event in enumerate(events):
            line = SMOKE.canonical({'seq': seq, 'prev': prev, 'event': event})
            lines.append(line + b'\n')
            prev = hashlib.sha256(line).hexdigest()
        (self.state / 'journal.jsonl').write_bytes(b''.join(lines))
        SMOKE.save(self.state, SMOKE.replay(json.loads(self.kit_path.read_text()), events))

    def call_list(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def report(self, result, code):
        self.assertEqual(result.returncode, code, result.stderr + result.stdout)
        self.assertNotIn('SENSITIVE_DIAGNOSTIC', result.stdout + result.stderr)
        self.assertNotIn('thr_synthetic_private', result.stdout + result.stderr)
        return json.loads(result.stdout)


class Smoke(FixtureCase):
    def test_complete_then_resume_never_repeats_effects(self):
        doc = self.report(self.invoke(), 0)
        self.assertEqual(doc['verdict'], 'pass')
        self.assertEqual(doc['evidence'], 'fixture')
        self.assertEqual(doc['claims'], {c: 'pass' for c in CLAIMS})
        self.assertEqual(self.call_list(), [['ls', '--json']] + [[c] for c in CLAIMS])
        self.report(self.invoke(), 0)
        self.assertEqual(self.call_list().count(['send']), 1)
        self.assertNotIn('thr_synthetic_private', (self.state / 'checkpoint.json').read_text())

    def test_bundle_refusal_has_no_effect_and_can_start_when_fixed(self):
        self.replies['ls'] = {'exit': 1, 'out': '{"schema":"openwiz.cli-error.v1"}'}
        self.assertEqual(self.report(self.invoke(), 3)['reason'], 'bundle_preflight')
        self.assertEqual(self.call_list(), [['ls', '--json']])
        self.replies['ls'] = {'exit': 0, 'out': json.dumps({
            'schema': 'openwiz.inventory.v1', 'coverage': {'state': 'complete'},
            'gaps': [], 'data': {'sessions': []}})}
        self.report(self.invoke(), 0)

    def test_dry_run_executes_nothing_and_creates_no_state(self):
        doc = self.report(self.run_tool('--dry-run'), 0)
        self.assertEqual(doc['verdict'], 'not_run')
        self.assertEqual(doc['claims'], {c: 'not_run' for c in CLAIMS})
        self.assertEqual(self.call_list(), [])
        self.assertFalse(self.state.exists())

    def test_every_promise_required_before_any_execution(self):
        for claim in CLAIMS:
            with self.subTest(claim=claim):
                original = self.kit['steps']
                self.kit['steps'] = [s for s in original if s['claim'] != claim]
                self.report(self.invoke(), 2)
                self.assertEqual(self.call_list(), [])
                self.kit['steps'] = original

    def test_wrong_fact_is_fail_and_not_retried(self):
        self.replies['send']['out'] = '{"count":2,"known":true}'
        doc = self.report(self.invoke(), 1)
        self.assertEqual(doc['claims']['send'], 'fail')
        self.assertEqual(doc['reason'], 'comparison')
        self.report(self.invoke(), 1)
        self.assertEqual(self.call_list().count(['send']), 1)
        self.assertNotIn(['new'], self.call_list())

    def test_missing_or_duplicate_or_wrong_type_fact_is_never_pass(self):
        for raw in ('{}', '{"count":1,"count":1,"known":true}',
                    '{"count":true,"known":true}', '[]', 'not-json',
                    '{"count":1,"known":true} trailing'):
            with self.subTest(raw=raw):
                self.state = self.root / ('state-' + hashlib.sha256(raw.encode()).hexdigest())
                self.replies['swarms']['out'] = raw
                self.assertNotEqual(self.report(self.invoke(), 3 if raw in ('{}', '[]', 'not-json', '{"count":1,"count":1,"known":true}', '{"count":1,"known":true} trailing') else 1)['verdict'], 'pass')

    def test_failed_write_stays_uncertain_on_resume(self):
        self.replies['send'] = {'exit': 9, 'out': '{}'}
        doc = self.report(self.invoke(), 3)
        self.assertEqual(doc['reason'], 'uncertain_write')
        self.report(self.invoke(), 3)
        self.assertEqual(self.call_list().count(['send']), 1)

    def test_event_ends_and_resume_does_not_repeat_completed_steps(self):
        self.kit['steps'].insert(1, {'id': 'next_event', 'claim': 'fleet', 'kind': 'event'})
        self.assertEqual(self.report(self.invoke(), 3)['reason'], 'next_event')
        self.assertEqual(self.call_list(), [['ls', '--json'], ['fleet']])
        self.report(self.invoke(), 0)
        self.assertEqual(self.call_list().count(['fleet']), 1)

    def test_independent_read_comparison(self):
        step = self.kit['steps'][1]
        step['checks'].append({'path': '/id', 'same_as': {'step': 'fleet', 'path': '/id'}})
        self.report(self.invoke(), 0)
        # A fresh run with mismatched independent values must fail.
        self.state = self.root / 'other-state'
        self.replies['swarms']['out'] = '{"count":1,"known":true,"id":"different"}'
        self.report(self.invoke(), 1)

    def test_unpinned_command_and_unknown_claim_refuse(self):
        self.kit['steps'][0]['argv'][0] = '/not/pinned'
        self.report(self.invoke(), 2)
        self.assertEqual(self.call_list(), [])
        self.kit['steps'][0]['argv'][0] = str(self.fake)
        self.kit['steps'][0]['claim'] = 'unknown'
        self.report(self.invoke(), 2)
        self.assertEqual(self.call_list(), [])

    def test_changed_kit_or_artifact_refuses_resume(self):
        self.report(self.invoke(), 0)
        self.kit['timeout_seconds'] = 3
        self.report(self.invoke(), 2)
        self.kit['timeout_seconds'] = 2
        self.fake.write_text(self.fake.read_text() + '\n# changed\n')
        self.report(self.invoke(), 2)

    def test_live_kit_cannot_use_fixture_mode_or_unapproved_digest(self):
        self.kit['mode'] = 'live'
        self.report(self.invoke(), 2)
        self.report(self.run_tool('--execute', '0' * 64), 2)
        self.assertEqual(self.call_list(), [])


    def test_retired_engine_commands_refuse_before_any_step(self):
        """catches: a kit that still runs `openwiz fleet tick` (any form, the
        reviewed-plan one included) or `openwiz engine`, which the engine
        retirement removes: the runner must refuse it before any step runs."""
        forms = {'tick': ['fleet', 'tick', '--json'],
                 'pinned tick': ['fleet', 'tick', '--expect-plan', '/synthetic/plan.json', '--json'],
                 'tick preview': ['fleet', 'tick', '--dry-run', '--json'],
                 'engine status': ['engine', 'status', '--json'],
                 'engine activate': ['engine', 'activate']}
        for name, args in forms.items():
            for kind in ('write', 'read'):
                with self.subTest(form=name, kind=kind):
                    self.state = self.root / ('retired-' + name.replace(' ', '-') + '-' + kind)
                    self.kit['steps'][0].update(kind=kind, argv=[str(self.fake), *args])
                    self.assertEqual(self.report(self.invoke(), 2)['reason'], 'retired_command')
                    self.assertEqual(self.report(self.run_tool('--dry-run'), 2)['reason'], 'retired_command')
                    self.assertEqual(self.call_list(), [])

    def test_retired_commands_refuse_through_any_alias_of_the_pinned_program(self):
        """catches (review R2): a symlink, hardlink or pinned copy of the pinned
        `openwiz` running `fleet tick` or `engine` as a block read or as the
        terminating await, repeating a retired write with no attempt record."""
        aliases = {'symlink': lambda a: a.symlink_to(self.fake),
                   'hardlink': lambda a: os.link(self.fake, a),
                   'copy': lambda a: (a.write_bytes(self.fake.read_bytes()), a.chmod(0o700))}
        forms = {'tick': ['fleet', 'tick', '--json'], 'engine': ['engine', 'activate']}
        for name, make in aliases.items():
            alias = self.root / ('alias-' + name)
            make(alias)
            for form, args in forms.items():
                for place in ('block read', 'await'):
                    with self.subTest(alias=name, form=form, place=place):
                        self.kit = json.loads(json.dumps(self.base_kit))
                        self.fleet_block()
                        self.kit['artifacts'][str(alias)] = self.sha(self.fake)
                        index = 0 if place == 'block read' else 2
                        self.kit['steps'][index]['argv'] = [str(alias), *args]
                        self.state = self.root / ('alias-%s-%s-%s' % (name, form, place.replace(' ', '-')))
                        self.assertEqual(self.report(self.invoke(), 2)['reason'], 'retired_command')
                        self.assertEqual(self.call_list(), [])
        # An identity that cannot be read is refused as the same program.
        self.kit = json.loads(json.dumps(self.base_kit))
        missing = str(self.root / 'missing-program')
        self.kit['artifacts'][missing] = '0' * 64
        self.kit['steps'][0]['argv'] = [missing, 'fleet', 'tick', '--json']
        self.state = self.root / 'alias-unreadable'
        self.assertEqual(self.report(self.invoke(), 2)['reason'], 'retired_command')
        self.assertEqual(self.call_list(), [])

    def test_fleet_block_rereads_once_per_event_until_readback(self):
        """catches: the fleet claim needing a runner write to progress, or a
        block re-running anything but its reads between launch-fleet's events."""
        self.fleet_block()
        self.assertEqual(self.report(self.invoke(), 3)['reason'], 'next_event')
        self.assertEqual(self.report(self.invoke(), 3)['reason'], 'pending')
        self.assertEqual(self.report(self.invoke(), 3)['reason'], 'next_event')
        self.assertEqual(self.fleet_reads(), 2)
        self.replies['done']['out'] = '{"merged":2,"safe":true}'
        doc = self.report(self.invoke(), 0)
        self.assertEqual(doc['claims']['fleet'], 'pass')
        self.assertEqual(self.fleet_reads(), 2)
        self.assertEqual(self.call_list().count(['send']), 1)
        self.assertFalse(any(c[:2] == ['fleet', 'tick'] for c in self.call_list()))

    def test_no_write_can_be_repeated(self):
        """catches: a repeat block that would re-send a message or re-run a
        fleet write (a cleanup, a reply) on a later event."""
        self.kit['steps'].append({'id': 'repeat_send', 'claim': 'send', 'kind': 'await',
                                 'argv': [str(self.fake), 'send'], 'exit': 0,
                                 'checks': [{'path': '/count', 'equals': 2}],
                                 'again_from': 'send'})
        self.report(self.invoke(), 2)
        self.assertEqual(self.call_list(), [])
        self.kit['steps'].pop()
        self.fleet_block()
        self.kit['steps'][0]['kind'] = 'write'
        self.assertEqual(self.report(self.invoke(), 2)['reason'], 'invalid_kit')
        self.assertEqual(self.call_list(), [])

    def test_attempting_checkpoint_refuses_without_any_execution(self):
        self.kit['steps'].insert(0, {'id': 'event', 'claim': 'fleet', 'kind': 'event'})
        self.report(self.invoke(), 3)
        # Interrupted after the fsynced attempt, before anything else was saved.
        SMOKE.journal(self.state, {'kind': 'attempt', 'id': 'fleet', 'claim': 'fleet'})
        before = self.call_list()
        self.assertEqual(self.report(self.invoke(), 3)['reason'], 'uncertain_write')
        self.assertEqual(self.report(self.invoke(), 3)['reason'], 'uncertain_write')
        self.assertEqual(self.call_list(), before)
        # A checkpoint edited without its journal is refused, not trusted.
        checkpoint = self.state / 'checkpoint.json'
        state = json.loads(checkpoint.read_text())
        state['steps'][1]['state'] = 'pass'
        checkpoint.write_text(json.dumps(state))
        self.assertEqual(self.report(self.invoke(), 2)['reason'], 'invalid_state')
        self.assertEqual(self.call_list(), before)

    def test_lock_contention_refuses_without_execution(self):
        import fcntl
        self.state.mkdir(mode=0o700)
        with (self.state / 'lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.report(self.invoke(), 2)['reason'], 'runner_busy')
        self.assertEqual(self.call_list(), [])

    def test_timeout_write_cannot_be_replayed(self):
        text = self.fake.read_text().replace("case = sys.argv[1]", "case = sys.argv[1]\nif case == 'send':\n    import signal\n    signal.pause()")
        self.fake.write_text(text)
        self.kit['artifacts'][str(self.fake)] = self.sha(self.fake)
        self.kit['timeout_seconds'] = 1
        self.assertEqual(self.report(self.invoke(), 3)['reason'], 'uncertain_write')
        self.report(self.invoke(), 3)
        self.assertEqual(self.call_list().count(['send']), 1)

    def test_wrong_await_invariant_is_failure_not_pending(self):
        self.kit['steps'].insert(1, {'id': 'safe_readback', 'claim': 'fleet',
            'kind': 'await', 'argv': [str(self.fake), 'safety'], 'exit': 0,
            'checks': [{'path': '/safe', 'equals': True}]})
        self.replies['safety'] = {'exit': 0, 'out': '{"safe":false}'}
        self.assertEqual(self.report(self.invoke(), 1)['reason'], 'comparison')
        self.assertNotIn(['send'], self.call_list())

    def test_http_probe_preserves_duplicate_keys_for_the_strict_reader(self):
        import http.server
        import threading
        body = b'{"count":1,"count":2}'
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass
        with http.server.HTTPServer(('127.0.0.1', 0), Handler) as server:
            server.timeout = 3
            thread = threading.Thread(target=server.handle_request)
            thread.start()
            try:
                result = subprocess.run([sys.executable, '-I', str(RUNNER.with_name('http.py')),
                    str(server.server_port), '/api/v1/loops'], capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, body)
            finally:
                thread.join(timeout=5)
                self.assertFalse(thread.is_alive())

    def test_fleet_sitting_and_time_caps_allow_no_more_sittings(self):
        """catches: a fleet block re-reading past AC6's 60 sittings or three
        hours, or a final readback accepted after the cap expired."""
        self.fleet_block()
        for field in ('sittings', 'started'):
            with self.subTest(field=field):
                self.state = self.root / ('capped-' + field)
                for reason in ('next_event', 'pending', 'next_event'):
                    self.assertEqual(self.report(self.invoke(), 3)['reason'], reason)
                if field == 'sittings':
                    # Journal 58 more real sittings: readback, repeat, read, event.
                    self.rewrite_journal(lambda e: e)
                    _, events = SMOKE.read_journal(self.state)
                    events = events + events[3:7] * 58
                    self.rewrite_journal(lambda e: e, events)
                    state = json.loads((self.state / 'checkpoint.json').read_text())
                    self.assertEqual(state['fleet']['sittings'], 60)
                else:
                    self.rewrite_journal(lambda e: dict(e, at=1) if e.get('id') == 'fleet_event' else e)
                before = self.fleet_reads()
                if field == 'sittings':
                    # The sixtieth sitting's own readback still runs; no repeat follows it.
                    self.assertEqual(self.report(self.invoke(), 3)['reason'], 'pending')
                self.assertEqual(self.report(self.invoke(), 3)['reason'], 'fleet_limit')
                self.assertEqual(self.report(self.invoke(), 3)['reason'], 'fleet_limit')
                self.assertEqual(self.fleet_reads(), before)

        # Expiry also bounds the final observation, not only the next sitting.
        self.state = self.root / 'expired-but-merged'
        self.report(self.invoke(), 3)
        self.rewrite_journal(lambda e: dict(e, at=1) if e.get('id') == 'fleet_event' else e)
        self.replies['done']['out'] = '{"merged":2,"safe":true}'
        self.assertEqual(self.report(self.invoke(), 3)['reason'], 'fleet_limit')

        # A journal claiming a 61st sitting is not one the runner could write.
        self.state = self.root / 'capped-sittings'
        _, events = SMOKE.read_journal(self.state)
        with self.assertRaises(SMOKE.Refusal):
            SMOKE.replay(json.loads(self.kit_path.read_text()), events + events[3:7])

    def test_app_step_selects_installation_token_without_owner_fallback(self):
        text = self.fake.read_text().replace("print(reply['out'])", "if case == 'app':\n    import os\n    reply['out'] = json.dumps({'selected': os.environ.get('GH_TOKEN'), 'fallback': 'GITHUB_TOKEN' in os.environ})\nprint(reply['out'])")
        self.fake.write_text(text)
        self.kit['artifacts'][str(self.fake)] = self.sha(self.fake)
        step = next(s for s in self.kit['steps'] if s['claim'] == 'app')
        step['token_env'] = 'OPENWIZ_SMOKE_APP_TOKEN'
        step['checks'] = [{'path': '/selected', 'equals': 'synthetic-installation-token'},
                          {'path': '/fallback', 'equals': False}]
        from unittest.mock import patch
        with patch.dict(os.environ, {'OPENWIZ_SMOKE_APP_TOKEN': 'synthetic-installation-token',
                                     'GH_TOKEN': 'synthetic-owner-token',
                                     'GITHUB_TOKEN': 'synthetic-other-token'}):
            result = self.invoke()
            self.report(result, 0)
            self.assertNotIn('synthetic-installation-token', result.stdout + result.stderr)
        self.state = self.root / 'missing-app-token'
        with patch.dict(os.environ, {'GH_TOKEN': 'synthetic-owner-token'}):
            os.environ.pop('OPENWIZ_SMOKE_APP_TOKEN', None)
            self.assertEqual(self.report(self.invoke(), 3)['reason'], 'missing_credential')


class ShippedCommands(unittest.TestCase):
    """#776: a kit step that runs a command the CLI no longer ships passes
    every fixture test (the fake answers anything) and fails only live."""

    def test_every_openwiz_step_in_the_template_is_a_shipped_command(self):
        root = RUNNER.resolve().parents[2]
        catalogue = json.loads((root / 'crates/cli/src/agent-catalogue.json').read_text())
        shipped = [c['argv'] for c in catalogue['commands']]
        template = json.loads(RUNNER.with_name('combined.template.json').read_text())
        for step in template['steps']:
            argv = step.get('argv')
            if not isinstance(argv, list):
                continue
            self.assertNotIn('@pty_driver', argv, step['id'])
            if argv[0] != '@openwiz':
                continue
            words = [a for a in argv[1:] if not a.startswith(('-', '@'))]
            self.assertTrue(any(words[:len(c)] == c for c in shipped),
                            f"{step['id']}: openwiz {' '.join(argv[1:])} is not a shipped command")


# The 0.1.0 sheet's synthetic programs (#1727). The driver is a stand-in for
# KN4's Cloudroom driver at its contract (kernel/driver.v1.md): JSON in on stdin,
# one JSON answer out, its runs kept in OPENWIZ_CLOUDROOM_STATE, and a thread
# that only room-cli can read back.
FAKE_DRIVER = """#!/usr/bin/env python3
import json, os, pathlib, sys
root = pathlib.Path(__file__).parent
state = pathlib.Path(os.environ['OPENWIZ_CLOUDROOM_STATE'])
cmd = sys.argv[1]
body = sys.stdin.read()
with (root / 'driver-calls').open('a') as log:
    log.write(json.dumps([cmd, json.loads(body) if body else None]) + '\\n')
if cmd == 'version':
    out = {'driver': 'cloudroom', 'records': ['openwiz:records v1'], 'can': ['start', 'wake', 'stop']}
elif cmd == 'start':
    req = json.loads(body)
    assert type(req['ticket']) is int and os.environ['ROOM_PROJECT_ID'] == 'proj_synthetic'
    state.mkdir(exist_ok=True)
    (state / 'run-0123456789ab.json').write_text(json.dumps({'thread': 'thr_synthetic_private', 'request': req}))
    (root / 'room-state').write_text(json.dumps({'projectId': 'proj_synthetic', 'archived': False}))
    out = {'run': 'run-0123456789ab'}
elif cmd == 'wake':
    out = {'run': json.loads(body)['run'], 'woke': True}
elif cmd == 'stop':
    (root / 'room-state').write_text(json.dumps({'projectId': 'proj_synthetic', 'archived': True}))
    out = {'run': json.loads(body)['run'], 'stopped': True}
print(json.dumps(out))
"""
FAKE_ROOM = """#!/usr/bin/env python3
import json, pathlib, sys
root = pathlib.Path(__file__).parent
assert sys.argv[1:] == ['thread', 'show', 'thr_synthetic_private'], sys.argv
print(json.dumps(dict(json.loads((root / 'room-state').read_text()), id='thr_synthetic_private', parent='thr_synthetic_private')))
"""
FAKE_CLI = """#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
if args[:1] == ['status']:
    out = {'schema': 'openwiz.install-status.v1', 'outcome': 'installed', 'channel': 'packaged', 'version': '0.1.0',
           'source': 'synthetic-source', 'target': 'synthetic-target', 'build': 'synthetic-build'}
elif args == ['help', '--agent']:
    out = {'schema': 'openwiz.cli.v1', 'kind': 'catalogue', 'commands': ['synthetic']}
elif args == ['ls', '--json']:
    out = {'schema': 'openwiz.inventory.v1', 'coverage': {'state': 'complete'}, 'gaps': [], 'data': {'sessions': []}}
elif args[:1] == ['show']:
    out = {'schema': 'openwiz.inventory.v1', 'data': {'session': {'id': args[1]}}}
elif args == ['api', '/installation/repositories']:
    out = {'total_count': 1, 'repositories': [{'full_name': 'example/throwaway'}]}
print(json.dumps(out))
"""
DRIVER_STEPS = {'new_once': 'start', 'send_once': 'wake', 'driver_stop': 'stop'}


def template():
    return json.loads(RUNNER.with_name('combined.template.json').read_text())


class Sheet(unittest.TestCase):
    """#1727: the 0.1.0 kit sheet, its driver steps and its release section."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def program(self, name, text):
        path = self.root / name
        path.write_text(text)
        path.chmod(0o700)
        return str(path)

    def bound(self):
        """The template bound to synthetic inputs, as prepare.py would."""
        cli = self.program('openwiz', FAKE_CLI)
        programs = {'openwiz': cli, 'gh': cli, 'install_entry': cli,
                    'driver': self.program('driver', FAKE_DRIVER), 'room_cli': self.program('room-cli', FAKE_ROOM)}
        (self.root / 'state').mkdir()
        inputs = dict(programs, mode='fixture', cwd=str(self.root), python=sys.executable,
                      artifacts={p: FixtureCase.sha(Path(p)) for p in set(programs.values()) | {sys.executable}},
                      source={'checkout': str(self.root), 'head': '0' * 40},
                      env={'OPENWIZ_CLOUDROOM_STATE': str(self.root / 'state'), 'ROOM_PROJECT_ID': 'proj_synthetic'},
                      install_root='/synthetic/root', install_state='/synthetic/state', install_build='synthetic-build',
                      release_version='0.1.0', release_source='synthetic-source', release_target='synthetic-target',
                      release_targets=['x86_64-unknown-linux-gnu'],
                      release_products=[{'product': 'cli', 'target': 'x86_64-unknown-linux-gnu'}],
                      release_gaps=['synthetic gap'], promise_install='synthetic_install',
                      promise_drivers='synthetic_drivers', promise_app='synthetic_app',
                      expected_catalogue_commands=['synthetic'], send_thread='thr_synthetic_show',
                      project='proj_synthetic', driver_repository='example/throwaway', driver_ticket='7',
                      driver_skill='synthetic-skill', harness='claude', model='synthetic-model',
                      app_repository='example/throwaway')
        prepare = runpy_path('prepare.py')
        return prepare['bind'](template(), inputs)

    def test_bound_sheet_loads_and_its_release_section_is_accepted(self):
        """catches: a 0.1.0 sheet the runner or the receipt refuses only when the
        PC prepares it on the candidate's hashes (Saturday), not here."""
        kit = self.bound()
        path = self.root / 'kit.json'
        path.write_text(json.dumps(kit))
        SMOKE.load_kit(path)
        receipt = runpy_path('receipt.py')
        section = receipt['release_section'](kit)
        self.assertEqual(section['scope']['writes'], {'send': 1, 'new': 1})
        self.assertEqual(section['scope']['spending_cents'], 0)

    def test_driver_steps_start_wake_and_stop_one_run_through_the_runner(self):
        """catches: a driver step the runner can't feed (the driver reads its
        request on stdin; the runner gives none), a wake or stop that doesn't
        reach the run start made, a second start, or a sheet that leaves the
        run's thread unarchived."""
        kit = self.bound()
        path = self.root / 'kit.json'
        path.write_text(json.dumps(kit))
        result = subprocess.run([sys.executable, '-I', str(RUNNER), '--kit', str(path),
                                 '--state', str(self.root / 'checkpoint'), '--fixture'],
                                capture_output=True, text=True, timeout=30,
                                env=dict(os.environ, OPENWIZ_SMOKE_APP_TOKEN='synthetic-installation-token'))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('thr_synthetic_private', result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['claims'], {c: 'pass' for c in kit['claims']})
        calls = [json.loads(line) for line in (self.root / 'driver-calls').read_text().splitlines()]
        self.assertEqual([c for c, _ in calls], ['version', 'start', 'wake', 'stop'])
        self.assertEqual(calls[1][1], {'repository': 'example/throwaway', 'ticket': 7, 'skill': 'synthetic-skill',
                                       'harness': 'claude', 'model': 'synthetic-model'})
        self.assertEqual(calls[2][1], {'run': 'run-0123456789ab'})
        self.assertEqual(calls[3][1], {'run': 'run-0123456789ab'})
        self.assertTrue(json.loads((self.root / 'room-state').read_text())['archived'])

    def test_driver_steps_call_only_driver_v1_commands_on_the_pinned_driver(self):
        """catches: a driver step naming a command the driver contract doesn't
        have, a driver write run outside the pinned `@driver`, or a stop missing
        so the throwaway's agent is left running."""
        contract = (RUNNER.resolve().parents[2] / 'kernel/driver.v1.md').read_text()
        commands = set(re.findall(r'^\| `([a-z]+)` \|', contract, re.M))
        self.assertTrue({'start', 'wake', 'stop'} <= commands, commands)
        steps = {s['id']: s for s in template()['steps']}
        for step in steps.values():
            if '@driver' in step['argv']:
                at = step['argv'].index('@driver')
                self.assertEqual(step['argv'][:at], ['@python', '-I', '-c', step['argv'][3]], step['id'])
                self.assertIn(step['argv'][at + 1], commands, step['id'])
        self.assertEqual({i: steps[i]['argv'][5] for i in DRIVER_STEPS}, DRIVER_STEPS)
        writes = sorted(s['id'] for s in steps.values() if s['kind'] == 'write')
        self.assertEqual(writes, ['new_once', 'send_once'])

    def test_every_risk_step_has_a_coverage_row(self):
        """catches: 0.0.17's blocker, a risk step in no `release.coverage` row,
        so the risk receipt's expected coverage is empty and the gate refuses
        `coverage_mismatch` only after the live run."""
        release = template()['release']
        covered = {step for row in release['coverage'] for step in row['steps']}
        for category in ('send', 'new', 'app_permissions'):
            self.assertTrue(release['risk'][category], category)
            self.assertLessEqual(set(release['risk'][category]), covered, category)
        self.assertEqual(release['risk']['spending'], [])


def runpy_path(name):
    import runpy
    return runpy.run_path(str(RUNNER.with_name(name)))


if __name__ == '__main__':
    unittest.main()
