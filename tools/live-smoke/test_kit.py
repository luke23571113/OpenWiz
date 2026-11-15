"""RL7 (#772): the public release smoke kit's own port, owner-only inputs,
read-only collectors and scratch App token route. Synthetic values only."""
import datetime
import hashlib
import http.server
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import threading
import unittest

HERE = Path(__file__).resolve().parent
FixtureCase = runpy.run_path(str(HERE / 'test_smoke.py'))['FixtureCase']
CLAIMS = runpy.run_path(str(HERE / 'test_smoke.py'))['CLAIMS']
PORT = '8123'
# A sentinel no output may ever print: it stands for a private input value.
PRIVATE = 'thr_synthetic_private_input'
SCOPE = {'targets': ['synthetic-target'], 'writes': {'fleet': 2, 'send': 1, 'new': 1},
         'app_permissions': ['contents:write', 'issues:write', 'metadata:read'], 'spending_cents': 0}


def canonical_sha(value):
    # The release-candidate contract's digest: canonical JSON, sorted keys.
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


def run(*argv, env=None, timeout=10):
    return subprocess.run([sys.executable, '-I', *map(str, argv)], capture_output=True,
                          text=True, timeout=timeout, env=env)


class Port(FixtureCase):
    """catches: a kit that reaches 7370 (the owner's my.openwiz.dev server) or a
    service on another port than the one the kit records, before any effect."""

    def setUp(self):
        super().setUp()
        self.kit['port'] = PORT
        service = next(s for s in self.kit['steps'] if s['claim'] == 'service')
        service['id'] = 'service_before'
        self.kit['steps'].remove(service)
        self.kit['steps'].insert(0, service)
        self.service_reply(PORT)
        self.replies['ui'] = {'exit': 0, 'out': json.dumps({'count': 1, 'known': True})}

    def service_reply(self, port):
        self.replies['service'] = {'exit': 0, 'out': json.dumps({
            'count': 1, 'known': True, 'schema': 'openwiz.service-status.v1',
            'server': {'port': int(port)}})}

    def pinned(self, name, text):
        path = self.root / name
        path.write_text(text)
        self.kit['artifacts'][str(path)] = self.sha(path)
        return str(path)

    def terminal(self, argv):
        step = next(s for s in self.kit['steps'] if s['claim'] == 'terminal')
        step['argv'] = argv

    def test_a_kit_that_asks_for_7370_refuses_before_any_effect(self):
        python = sys.executable
        self.kit['artifacts'][python] = self.sha(Path(python))
        http_probe = str(HERE / 'http.py')
        browser = str(HERE / 'browser.mjs')
        rows = {
            'kit port': lambda: self.kit.update(port='7370'),
            'legacy default port key': lambda: self.kit.update(default_terminal_port='7370'),
            'explicit ui port': lambda: self.terminal([self.kit['openwiz'], 'ui', '--port', '7370']),
            'no-argument ui': lambda: self.terminal([self.kit['openwiz'], 'ui']),
            'no-argument program through a driver': lambda: self.terminal(
                [str(self.fake), 'terminal', self.kit['openwiz']]),
            'http probe': lambda: (self.kit['artifacts'].update({http_probe: self.sha(Path(http_probe))}),
                                   self.terminal([python, '-I', http_probe, '7370', '/api/v1/loops'])),
            'browser origin': lambda: (self.kit['artifacts'].update({browser: self.sha(Path(browser))}),
                                       self.terminal([str(self.fake), browser, self.pinned(
                                           'browser.json', json.dumps({'origin': 'http://127.0.0.1:7370/'}))])),
        }
        clean = json.loads(json.dumps(self.kit))
        for name, change in rows.items():
            with self.subTest(name):
                self.kit = json.loads(json.dumps(clean))
                change()
                self.state = self.root / ('state-' + name.replace(' ', '-'))
                doc = self.report(self.invoke(), 2)
                self.assertEqual(doc['reason'], 'reserved_port')
                self.assertEqual(self.call_list(), [])
                self.assertFalse(self.state.exists())

    def test_every_port_use_is_the_kits_recorded_port(self):
        rows = {
            'ui port differs': lambda: self.terminal([self.kit['openwiz'], 'ui', '--port', '8124']),
            'ui port without a kit port': lambda: (self.kit.pop('port'),
                                                   self.terminal([self.kit['openwiz'], 'ui', '--port', PORT])),
        }
        clean = json.loads(json.dumps(self.kit))
        for name, change in rows.items():
            with self.subTest(name):
                self.kit = json.loads(json.dumps(clean))
                change()
                self.assertEqual(self.report(self.invoke(), 2)['reason'], 'port_mismatch')
                self.assertEqual(self.call_list(), [])

    def test_service_must_report_the_kits_port_before_the_first_write(self):
        self.terminal([self.kit['openwiz'], 'ui', '--port', PORT])
        self.service_reply('8124')
        doc = self.report(self.invoke(), 3)
        self.assertEqual(doc['reason'], 'port_mismatch')
        self.assertEqual([c[0] for c in self.call_list()], ['service'])
        self.service_reply(PORT)
        self.state = self.root / 'right-port'
        self.calls.unlink()
        self.assertEqual(self.report(self.invoke(), 0)['verdict'], 'pass')
        self.assertIn(['ui', '--port', PORT], self.call_list())


class Inputs(unittest.TestCase):
    """The PC-side owner-only inputs file and prepare.py's handling of it."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.fake = self.root / 'program'
        self.fake.write_text('#!/bin/sh\nexit 0\n')
        self.fake.chmod(0o700)
        self.run_dir = self.root / 'run'
        self.run_dir.mkdir(mode=0o700)

    def sha(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def standard_records(self):
        """Every name the standard sheet binds except the run-time port."""
        names = set()

        def collect(value):
            if isinstance(value, dict):
                [collect(v) for v in value.values()]
            elif isinstance(value, list):
                [collect(v) for v in value]
            elif isinstance(value, str) and value.startswith('@'):
                names.add(value[1:])
        collect(json.loads((HERE / 'combined.template.json').read_text()))
        records = {}
        for name in names:
            if name == 'release':
                records[name] = {'scope': SCOPE, 'products': [], 'coverage': [], 'risk': {}, 'gaps': []}
            elif name.endswith('_checks'):
                records[name] = [{'path': '/count', 'equals': 1}]
            elif name.endswith('_argv'):
                records[name] = [str(self.fake), 'readback']
            else:
                records[name] = str(self.fake)
        records.update(mode='fixture', scratch_checkout=str(self.root), env={},
                       control_thread=PRIVATE,
                       artifacts={str(self.fake): self.sha(self.fake)},
                       source={'checkout': str(self.root), 'head': '0' * 40},
                       fleet_scope={'specs': [9001], 'tickets': [9002, 9003, 9004],
                                    'rules': ['frontier', 'adr_0008'], 'never_start': [9004]})
        records.pop('port')
        return records

    def write(self, path, value, mode=0o600):
        path.write_text(json.dumps(value))
        path.chmod(mode)
        return path

    def assemble(self, *records, out=None):
        out = out or self.run_dir / 'inputs.json'
        args = [HERE / 'inputs.py', '--out', out]
        for path in records:
            args += ['--records', path]
        return run(*args), out

    def test_records_assemble_one_owner_only_file_with_a_run_time_port(self):
        """catches: a world-readable inputs file, a reused or reserved port, or
        conflicting record values silently resolved by whichever comes last."""
        records = self.standard_records()
        first = dict(list(records.items())[:20])
        second = dict(list(records.items())[20:])
        result, out = self.assemble(self.write(self.root / 'a.json', first),
                                    self.write(self.root / 'b.json', second))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn(PRIVATE, result.stdout + result.stderr)
        self.assertEqual(out.stat().st_mode & 0o777, 0o600)
        inputs = json.loads(out.read_text())
        self.assertEqual(json.loads(result.stdout)['port'], inputs['port'])
        self.assertRegex(inputs['port'], '^[1-9][0-9]{3,4}$')
        self.assertNotEqual(inputs['port'], '7370')
        self.assertEqual(dict(inputs, port=None), dict(records, port=None))
        refusals = {
            'shared records': ([self.write(self.root / 'shared.json', records, 0o644)], 'records_not_owner_only'),
            'conflict': ([self.write(self.root / 'c1.json', {'project': 'prj_syn_0001'}),
                          self.write(self.root / 'c2.json', {'project': 'prj_syn_0002'})], 'conflicting_record'),
            'reserved port': ([self.write(self.root / 'p.json', dict(records, port='7370'))], 'reserved_port'),
        }
        for name, (paths, reason) in refusals.items():
            with self.subTest(name):
                result, target = self.assemble(*paths, out=self.run_dir / (name.replace(' ', '-') + '.json'))
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stdout), {'assembled': False, 'reason': reason})
                self.assertFalse(target.exists())
        result, _ = self.assemble(self.root / 'a.json', out=out)
        self.assertEqual(json.loads(result.stdout)['reason'], 'exists')
        self.assertEqual(json.loads(out.read_text()), inputs)

    def test_prepare_prints_kit_and_scope_digests_and_refuses_unsafe_inputs(self):
        """catches: prepare accepting a shared or committed inputs file, a stale
        or misspelt input name, or a token in the inputs; and the scope digest
        the candidate must carry never being printed."""
        inputs = dict(self.standard_records(), port=PORT)
        good = self.write(self.run_dir / 'inputs.json', inputs)
        out = self.run_dir / 'kit.json'
        result = run(HERE / 'prepare.py', '--inputs', good, '--out', out)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn(PRIVATE, result.stdout + result.stderr)
        kit = json.loads(out.read_text())
        self.assertEqual(json.loads(result.stdout), {
            'prepared': True, 'kit_sha256': hashlib.sha256(json.dumps(
                kit, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode()).hexdigest(),
            'scope_sha256': canonical_sha(SCOPE), 'port': PORT})
        self.assertEqual(kit['port'], PORT)
        self.assertNotIn('default_terminal_port', kit)
        checkout = self.root / 'checkout'
        subprocess.run(['git', 'init', '-q', str(checkout)], check=True)
        (checkout / 'private').mkdir()
        rows = {
            'shared inputs': (self.write(self.run_dir / 'shared.json', inputs, 0o640), out, 'inputs_not_owner_only'),
            'inputs in a checkout': (self.write(checkout / 'private' / 'inputs.json', inputs), out, 'inside_checkout'),
            'kit in a checkout': (good, checkout / 'kit.json', 'inside_checkout'),
            'stale input': (self.write(self.run_dir / 'stale.json', dict(inputs, default_steps='[]')), out, 'unused_input'),
            'missing input': (self.write(self.run_dir / 'missing.json', {k: v for k, v in inputs.items() if k != 'gh'}),
                              out, 'missing_input'),
            'token value': (self.write(self.run_dir / 'token.json', dict(inputs, send_op='ghs_' + 'A' * 36)),
                            out, 'credential_in_inputs'),
        }
        for name, (source, target, reason) in rows.items():
            with self.subTest(name):
                fresh = target if target != out else self.run_dir / (name.replace(' ', '-') + '-kit.json')
                result = run(HERE / 'prepare.py', '--inputs', source, '--out', fresh)
                self.assertEqual(result.returncode, 2)
                doc = json.loads(result.stdout)
                self.assertEqual((doc['prepared'], doc['reason']), (False, reason))
                self.assertNotIn(PRIVATE, result.stdout)
                self.assertFalse(fresh.exists())
        self.assertEqual(json.loads(run(HERE / 'prepare.py', '--inputs', rows['missing input'][0],
                                        '--out', self.run_dir / 'm.json').stdout)['missing'], ['gh'])

    def test_dry_run_binds_a_synthetic_candidate_and_runs_nothing(self):
        """catches: a PC dry run that cannot tell its kit is not the one the
        candidate carries until the live run starts."""
        inputs = dict(self.standard_records(), port=PORT)
        source = self.write(self.run_dir / 'inputs.json', inputs)
        kit_path = self.run_dir / 'kit.json'
        prepared = json.loads(run(HERE / 'prepare.py', '--inputs', source, '--out', kit_path).stdout)
        body = {'kit': {'sha256': prepared['kit_sha256'], 'scope_sha256': prepared['scope_sha256']}}
        candidate = self.write(self.run_dir / 'candidate.json', {
            'schema': 'openwiz.release-candidate.v1', 'candidate': body, 'candidate_sha256': canonical_sha(body)})
        state = self.run_dir / 'checkpoint'
        result = run(HERE / 'smoke.py', '--kit', kit_path, '--state', state, '--dry-run', '--candidate', candidate)
        self.assertEqual(result.returncode, 0, result.stdout)
        doc = json.loads(result.stdout)
        self.assertEqual((doc['verdict'], doc['reason']), ('not_run', 'dry_run'))
        self.assertEqual(doc['claims'], {c: 'not_run' for c in CLAIMS})
        self.assertFalse(state.exists())
        other = dict(body, kit=dict(body['kit'], scope_sha256='0' * 64))
        wrong = self.write(self.run_dir / 'other.json', {
            'schema': 'openwiz.release-candidate.v1', 'candidate': other, 'candidate_sha256': canonical_sha(other)})
        result = run(HERE / 'smoke.py', '--kit', kit_path, '--state', state, '--dry-run', '--candidate', wrong)
        self.assertEqual((result.returncode, json.loads(result.stdout)['reason']), (2, 'candidate_mismatch'))
        self.assertFalse(state.exists())


class FakeGitHub(http.server.BaseHTTPRequestHandler):
    """A loopback stand-in for the installation token route only."""
    granted = None
    requests = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        FakeGitHub.requests.append({'path': self.path, 'body': body})
        expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        doc = {'token': 'ghs_' + 'S' * 36, 'expires_at': expiry.strftime('%Y-%m-%dT%H:%M:%SZ'),
               'permissions': FakeGitHub.granted or body['permissions'],
               'repository_selection': 'selected',
               'repositories': [{'full_name': 'synthetic-owner/' + n} for n in body['repositories']]}
        raw = json.dumps(doc).encode()
        self.send_response(201)
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


class AppToken(unittest.TestCase):
    """catches: the scratch App steps running with a token wider than the
    kit's recorded App scope, a permission the App was never granted, or the
    token reaching argv, output or the kit."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        state = self.root / 'state'
        app_dir = state / 'github-app'
        app_dir.mkdir(parents=True, mode=0o700)
        state.chmod(0o700)
        subprocess.run(['openssl', 'genrsa', '-out', str(app_dir / 'private-key.pem'), '2048'],
                       check=True, capture_output=True)
        (app_dir / 'private-key.pem').chmod(0o600)
        (app_dir / 'app.json').write_text('{"app_id": 1001}')
        (app_dir / 'app.json').chmod(0o600)
        self.state = state
        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), FakeGitHub)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        FakeGitHub.granted, FakeGitHub.requests = None, []
        self.kit = self.root / 'kit.json'
        self.child = self.root / 'child.py'
        self.child.write_text('import json, os, sys\n'
                              'print(json.dumps({"argv": sys.argv[1:], '
                              '"token": os.environ.get("OPENWIZ_SMOKE_APP_TOKEN")}))\n')

    def mint(self, permissions):
        self.kit.write_text(json.dumps({'release': {'scope': dict(SCOPE, app_permissions=permissions)}}))
        self.kit.chmod(0o600)
        return run(HERE / 'app_token.py', '--kit', self.kit, '--state-dir', self.state,
                   '--installation-id', '2002', '--repository', 'synthetic-owner/synthetic-scratch',
                   '--api-base', f'http://127.0.0.1:{self.server.server_port}',
                   '--', sys.executable, '-I', self.child, 'synthetic-arg')

    def test_token_is_exactly_the_kits_app_scope_and_reaches_only_the_childs_environment(self):
        result = self.mint(SCOPE['app_permissions'])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(FakeGitHub.requests, [{
            'path': '/app/installations/2002/access_tokens',
            'body': {'permissions': {'contents': 'write', 'issues': 'write', 'metadata': 'read'},
                     'repositories': ['synthetic-scratch']}}])
        child = json.loads(result.stdout)
        self.assertEqual(child, {'argv': ['synthetic-arg'], 'token': 'ghs_' + 'S' * 36})
        self.assertNotIn('ghs_', result.stderr)

    def test_a_permission_the_app_lacks_or_a_wider_grant_refuses_without_running(self):
        for name, permissions, granted in (
                ('new permission', ['administration:write'], None),
                ('write the App only reads', ['checks:write'], None),
                ('wider grant', ['issues:write'], {'issues': 'write', 'contents': 'write'})):
            with self.subTest(name):
                FakeGitHub.granted, FakeGitHub.requests = granted, []
                result = self.mint(permissions)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertNotIn('ghs_', result.stdout + result.stderr)
                self.assertNotIn('synthetic-arg', result.stdout)
                if granted is None:
                    self.assertEqual(FakeGitHub.requests, [])


class Collectors(unittest.TestCase):
    """The exported read-only AC6 collectors, over a synthetic gh/room-cli."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.program = self.root / 'program'
        self.program.write_text('#!/usr/bin/env python3\n'
                                'import json, pathlib, sys\n'
                                'root = pathlib.Path(__file__).parent\n'
                                'with (root / "calls").open("a") as log:\n'
                                '    log.write(json.dumps(sys.argv[1:]) + "\\n")\n'
                                'replies = json.loads((root / "replies.json").read_text())\n'
                                'reply = replies[" ".join(sys.argv[1:])]\n'
                                'print(reply["out"])\n'
                                'sys.exit(reply["exit"])\n')
        self.program.chmod(0o700)
        self.replies = {}

    def reply(self, argv, doc, code=0):
        self.replies[' '.join(argv)] = {'out': doc if isinstance(doc, str) else json.dumps(doc), 'exit': code}

    def collect(self, *args):
        (self.root / 'replies.json').write_text(json.dumps(self.replies))
        return run(HERE / 'collect.py', *args)

    def calls(self):
        path = self.root / 'calls'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def issue(self, number, state, labels=(), prs=(), repository='synthetic-scratch'):
        self.reply(['issue', 'view', str(number), '--repo', 'synthetic-owner/synthetic-scratch', '--json',
                    'number,state,stateReason,labels,closedByPullRequestsReferences'],
                   {'number': number, 'state': state, 'stateReason': 'COMPLETED' if state == 'CLOSED' else '',
                    'labels': [{'name': n} for n in labels],
                    'closedByPullRequestsReferences': [
                        {'number': p, 'repository': {'name': repository, 'owner': {'login': 'synthetic-owner'}}}
                        for p in prs]})

    def pr(self, number, state, base='scratch', merge='a' * 40):
        self.reply(['pr', 'view', str(number), '--repo', 'synthetic-owner/synthetic-scratch', '--json',
                    'number,state,baseRefName,headRefOid,mergeCommit'],
                   {'number': number, 'state': state, 'baseRefName': base, 'headRefOid': 'b' * 40,
                    'mergeCommit': {'oid': merge} if state == 'MERGED' else None})

    def fleet(self):
        return self.collect('fleet', '--gh', self.program, '--repo', 'synthetic-owner/synthetic-scratch',
                            '--branch', 'scratch', '--spec', '9001', '--ticket', '9002', '--ticket', '9003',
                            '--ticket', '9004')

    def test_fleet_collector_reports_strict_merges_and_never_passes_a_failed_read(self):
        """catches: a ticket counted as merged from its closed state alone, from
        a PR into another branch or repository, or a collector that prints a
        document after a failed or malformed read, so a readback could pass
        on no evidence."""
        self.issue(9001, 'OPEN')
        self.issue(9002, 'CLOSED', prs=[7001])
        self.pr(7001, 'MERGED')
        self.issue(9003, 'CLOSED', prs=[7002, 7003])
        self.pr(7002, 'MERGED', base='other')
        self.pr(7003, 'CLOSED')
        self.issue(9004, 'OPEN', labels=['needs-info', 'ready-for-agent'], prs=[7004], repository='elsewhere')
        result = self.fleet()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            'schema': 'openwiz.live-smoke-fleet.v1', 'branch': 'scratch',
            'spec': {'number': 9001, 'state': 'OPEN', 'state_reason': ''},
            'tickets': [
                {'number': 9002, 'state': 'CLOSED', 'state_reason': 'COMPLETED', 'needs_info': False,
                 'merged': [{'number': 7001, 'head': 'b' * 40, 'merge_commit': 'a' * 40}]},
                {'number': 9003, 'state': 'CLOSED', 'state_reason': 'COMPLETED', 'needs_info': False, 'merged': []},
                {'number': 9004, 'state': 'OPEN', 'state_reason': '', 'needs_info': True, 'merged': []}],
            'merged_tickets': 1})
        self.assertTrue(all(c[0] in ('issue', 'pr') and c[1] == 'view' for c in self.calls()))
        for name, change in (('gh fails', lambda: self.reply(self.replies_key(9003), {}, 1)),
                             ('not JSON', lambda: self.reply(self.replies_key(9003), 'not json')),
                             ('duplicate key', lambda: self.reply(self.replies_key(9003),
                                                                  '{"number": 9003, "number": 9003}')),
                             ('wrong type', lambda: self.issue(9003, 'CLOSED', prs=['7002']))):
            with self.subTest(name):
                self.issue(9003, 'CLOSED', prs=[7002, 7003])
                change()
                result = self.fleet()
                self.assertEqual((result.returncode, result.stdout), (2, ''))

    def replies_key(self, number):
        return ['issue', 'view', str(number), '--repo', 'synthetic-owner/synthetic-scratch', '--json',
                'number,state,stateReason,labels,closedByPullRequestsReferences']

    def log(self, after, rows):
        argv = ['thread', 'log', 'thr_syn_0101', '--json', '--limit', '100']
        if after is not None:
            argv[4:4] = ['--after-seq', str(after)]
        self.reply(argv, rows)

    def test_delivery_collector_counts_exact_text_after_the_recorded_boundary(self):
        """catches: a delivery counted from text sent before the run, from a
        message that only contains the text, or across a log page boundary."""
        text = 'AC6: ok, continue.'
        page = [{'seq': n, 'type': 'syn-other', 'data': {}} for n in range(11, 111)]
        page[5] = {'seq': 16, 'type': 'syn-user-message', 'data': {'input': text}}
        page[6] = {'seq': 17, 'type': 'syn-user-message', 'data': {'input': 'quoted: ' + text}}
        self.log(10, page)
        self.log(110, [{'seq': 111, 'type': 'syn-agent-message', 'data': {'text': text}}])
        argv = ['delivery', '--room-cli', self.program, '--thread', 'thr_syn_0101', '--after-seq', '10',
                '--text', text]
        result = self.collect(*argv)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            'schema': 'openwiz.live-smoke-delivery.v1', 'events': 101, 'exact': 2, 'wrapped': 1,
            'exact_types': 2, 'max_exact_per_type': 1})
        self.assertNotIn(text, result.stdout)
        self.assertNotIn('thr_syn_0101', result.stdout)
        for name, rows in (('seq goes back', [{'seq': 9, 'type': 't', 'data': {}}]),
                           ('no seq', [{'type': 't', 'data': {}}]),
                           ('not a list', {'events': []})):
            with self.subTest(name):
                self.log(110, rows)
                result = self.collect(*argv)
                self.assertEqual((result.returncode, result.stdout), (2, ''))


if __name__ == '__main__':
    unittest.main()
