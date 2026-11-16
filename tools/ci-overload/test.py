#!/usr/bin/env python3
"""CS5 offline proofs through the observer's command boundary."""
import json
import fcntl
import contextlib
import importlib.util
import io
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
NOW = 1800000000
REPO = 'synthetic-owner/synthetic-repo'


def healthy():
    return dict(repository=REPO, observed_at=NOW, complete=True,
                queue=dict(complete=True, jobs=[]),
                budgets={pool: dict(remaining=1000, limit=1000, reset_at=NOW + 3600,
                                    retry_after=0) for pool in ('rest', 'graphql')})


class Alarm(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.state = self.folder / 'pause.json'

    def observe(self, value, action='merge-batch', now=NOW):
        source = self.folder / 'observation.json'
        source.write_text(json.dumps(value))
        result = subprocess.run([sys.executable, '-I', str(HERE / 'alarm.py'),
            '--repository', REPO, '--input', str(source), '--state', str(self.state),
            '--now', str(now), '--action', action], capture_output=True, text=True, timeout=2)
        self.assertIn(result.returncode, (0, 1), result.stderr)
        answer = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0 if answer['allowed'] else 1)
        return answer

    def test_queue_boundaries(self):
        # Running age must not count as waiting. Only required queued jobs do.
        for wait, level in ((299, 'healthy'), (300, 'alarm'), (301, 'alarm'),
                            (899, 'alarm'), (900, 'escalate'), (901, 'escalate')):
            with self.subTest(wait=wait):
                if self.state.exists():
                    self.state.unlink()
                value = healthy()
                value['queue']['jobs'] = [
                    dict(id='job-old-running', required=True, status='in_progress',
                         queued_at=NOW - 5000, started_at=NOW - 4900),
                    dict(id='job-optional', required=False, status='queued',
                         queued_at=NOW - 5000, started_at=None),
                    dict(id='job-required', required=True, status='queued',
                         queued_at=NOW - wait, started_at=None)]
                result = self.observe(value)
                self.assertEqual(result['level'], level)
                self.assertEqual(result['oldest_wait_seconds'], wait)
                self.assertEqual(result['paused'], wait >= 300)
                self.assertEqual(result['allowed'], wait < 300)

    def test_both_budget_boundaries_and_backoff(self):
        for pool in ('rest', 'graphql'):
            for remaining, level in ((101, 'healthy'), (100, 'healthy'), (99, 'alarm'),
                                     (1, 'alarm'), (0, 'escalate')):
                with self.subTest(pool=pool, remaining=remaining):
                    self.state.unlink(missing_ok=True)
                    value = healthy()
                    value['budgets'][pool]['remaining'] = remaining
                    result = self.observe(value)
                    self.assertEqual(result['level'], level)
                    self.assertEqual(result['paused'], remaining < 100)
            value = healthy()
            value['budgets'][pool]['retry_after'] = NOW + 30
            self.assertEqual(self.observe(value)['level'], 'alarm')
            value['budgets'][pool]['retry_after'] = NOW
            self.assertEqual(self.observe(value)['level'], 'healthy')

    def test_durable_pause_never_auto_resumes_and_work_continues(self):
        value = healthy()
        value['budgets']['rest']['remaining'] = 0
        first = self.observe(value)
        saved = json.loads(self.state.read_text())
        self.assertEqual(saved['causes'], ['rest_exhausted'])
        self.assertEqual(saved['observed_at'], NOW)
        self.assertEqual(saved['evidence_sha256'], first['evidence_sha256'])
        self.assertEqual(first['escalation'], 'due_not_sent')
        for action in ('merge-batch', 'automatic-refresh', 'nonessential-poll',
                       'completion', 'reconciliation'):
            result = self.observe(healthy(), action)
            self.assertEqual(result['level'], 'healthy')
            self.assertTrue(result['paused'])
            self.assertEqual(result['allowed'], action in ('completion', 'reconciliation'))
            self.assertEqual(json.loads(self.state.read_text())['causes'], ['rest_exhausted'])

    def test_incomplete_stale_and_invalid_inputs_never_admit(self):
        values = [None, [], {}, dict(healthy(), complete=False),
                  dict(healthy(), observed_at=NOW - 61), dict(healthy(), observed_at=NOW + 1),
                  dict(healthy(), repository='synthetic-other/repo')]
        for pool in ('rest', 'graphql'):
            for field, replacement in (('remaining', None), ('remaining', True), ('remaining', -1),
                                       ('limit', 0), ('reset_at', NOW)):
                value = healthy()
                value['budgets'][pool][field] = replacement
                values.append(value)
        value = healthy()
        value['queue']['complete'] = False
        values.append(value)
        value = healthy()
        value['queue']['jobs'] = [dict(id='', required=True, status='queued',
                                      queued_at=NOW - 400, started_at=None)]
        values.append(value)
        for value in values:
            with self.subTest(value=value):
                self.state.unlink(missing_ok=True)
                result = self.observe(value)
                self.assertEqual(result['level'], 'unknown')
                self.assertFalse(result['allowed'])
                self.assertTrue(result['paused'])

    def test_missing_duplicate_and_oversized_reads_keep_essential_work_available(self):
        source = self.folder / 'raw.json'
        for raw in (None, '{"complete":true,"complete":false}', ' ' * (2 * 1024 * 1024 + 1)):
            if raw is not None:
                source.write_text(raw)
            for action in ('merge-batch', 'completion', 'reconciliation'):
                result = subprocess.run([sys.executable, '-I', str(HERE / 'alarm.py'),
                    '--repository', REPO, '--input', str(source), '--state', str(self.state),
                    '--now', str(NOW), '--action', action], capture_output=True, text=True)
                self.assertEqual(result.returncode, 1 if action == 'merge-batch' else 0)
                answer = json.loads(result.stdout)
                self.assertEqual(answer['level'], 'unknown')
                self.assertTrue(answer['paused'])
                self.assertEqual(result.stderr, '')

    def test_decoder_recursion_preserves_essential_work_and_corrupt_evidence(self):
        # R2: deeply nested JSON bypasses the byte limit and used to
        # escape both read boundaries. Existing malformed cases do not recurse.
        nested = '[' * 100000 + '0' + ']' * 100000
        source = self.folder / 'raw.json'
        for boundary in ('input', 'state', 'pending'):
            for action in ('merge-batch', 'completion', 'reconciliation'):
                with self.subTest(boundary=boundary, action=action):
                    self.state.unlink(missing_ok=True)
                    source.write_text(nested if boundary == 'input' else json.dumps(healthy()))
                    corrupt = None
                    if boundary == 'state':
                        corrupt = self.state
                    elif boundary == 'pending':
                        pending = Path(str(self.state) + '.pending')
                        pending.mkdir(exist_ok=True)
                        corrupt = pending / 'synthetic-nested.json'
                    if corrupt is not None:
                        corrupt.write_text(nested)
                    result = subprocess.run([sys.executable, '-I', str(HERE / 'alarm.py'),
                        '--repository', REPO, '--input', str(source), '--state', str(self.state),
                        '--now', str(NOW), '--action', action], capture_output=True,
                        text=True, timeout=2)
                    self.assertEqual(result.returncode, 1 if action == 'merge-batch' else 0,
                                     result.stderr)
                    answer = json.loads(result.stdout)
                    self.assertEqual(answer['level'], 'unknown')
                    self.assertTrue(answer['paused'])
                    self.assertEqual(answer['allowed'], action != 'merge-batch')
                    self.assertEqual(result.stderr, '')
                    if corrupt is not None:
                        self.assertEqual(corrupt.read_text(), nested)

    def test_separate_processes_retain_the_same_pause(self):
        value = healthy()
        value['budgets']['rest']['remaining'] = 0
        self.observe(value)
        original = self.state.read_bytes()
        source = self.folder / 'healthy.json'
        source.write_text(json.dumps(healthy()))
        processes = [subprocess.Popen([sys.executable, '-I', str(HERE / 'alarm.py'),
            '--repository', REPO, '--input', str(source), '--state', str(self.state),
            '--now', str(NOW), '--action', 'merge-batch'], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True) for _ in range(3)]
        for process in processes:
            output, errors = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 1, errors)
            self.assertTrue(json.loads(output)['paused'])
        self.assertEqual(self.state.read_bytes(), original)
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o600)

    def test_contended_triggers_survive_healthy_reads_and_upgrade_existing_pause(self):
        # R1: refusal alone loses the trigger. Later independent healthy calls
        # must retain both the first pause and a contended severity upgrade.
        with Path(str(self.state) + '.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            value = healthy()
            value['budgets']['rest']['remaining'] = 99
            alarm = self.observe(value)
            self.assertFalse(alarm['allowed'])
            self.assertFalse(alarm['state_saved'])
        first = self.observe(healthy())
        self.assertTrue(first['paused'])
        self.assertFalse(first['allowed'])
        self.assertEqual(first['pause']['causes'], ['rest_below_ten_percent'])
        self.assertEqual(first['pause']['evidence_sha256'], alarm['evidence_sha256'])
        with Path(str(self.state) + '.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            value['budgets']['graphql']['remaining'] = 0
            exhausted = self.observe(value, 'completion', now=NOW + 1)
            self.assertTrue(exhausted['allowed'])
            self.assertFalse(exhausted['state_saved'])
        for action in ('merge-batch', 'automatic-refresh', 'nonessential-poll',
                       'completion', 'reconciliation'):
            result = self.observe(healthy(), action)
            self.assertTrue(result['paused'])
            self.assertEqual(result['allowed'], action in ('completion', 'reconciliation'))
            self.assertEqual(result['escalation'], 'due_not_sent')
            self.assertEqual(result['pause']['since'], NOW)
            self.assertEqual(result['pause']['level'], 'escalate')
            self.assertEqual(result['pause']['evidence_sha256'], exhausted['evidence_sha256'])

    def test_unwritable_or_corrupt_journal_refuses_but_preserves_essential_work(self):
        # R1: inability to persist or consume a pending trigger must never
        # silently admit; no existing case exercises this new durable boundary.
        pending = Path(str(self.state) + '.pending')
        pending.write_text('cannot publish here')
        exhausted = healthy()
        exhausted['budgets']['rest']['remaining'] = 0
        for action in ('merge-batch', 'completion', 'reconciliation'):
            result = self.observe(exhausted, action)
            self.assertFalse(result['state_saved'])
            self.assertTrue(result['paused'])
            self.assertEqual(result['allowed'], action != 'merge-batch')
        pending.unlink()
        pending.mkdir()
        corrupt = pending / 'synthetic-corrupt.json'
        corrupt.write_text('{"paused":true}')
        for action in ('merge-batch', 'completion', 'reconciliation'):
            result = self.observe(healthy(), action)
            self.assertEqual(result['level'], 'unknown')
            self.assertFalse(result['state_saved'])
            self.assertTrue(result['paused'])
            self.assertEqual(result['allowed'], action != 'merge-batch')
            self.assertEqual(corrupt.read_text(), '{"paused":true}')

    def test_recovery_keeps_journal_until_visible_pause_directory_sync_succeeds(self):
        # R4: a failed state-rename sync leaves a visible pause. Healthy
        # recovery must not consume its durable journal without that barrier.
        spec = importlib.util.spec_from_file_location('overload_r4', HERE / 'alarm.py')
        alarm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(alarm)
        source = self.folder / 'observation.json'
        pending = Path(str(self.state) + '.pending')
        real_sync = alarm.sync_directory
        fail_state_sync = True

        def sync(path):
            if path == self.state.parent and self.state.exists() and fail_state_sync:
                raise OSError('synthetic state-directory sync failure')
            real_sync(path)

        def call(value, action='merge-batch'):
            source.write_text(json.dumps(value))
            args = ['alarm.py', '--repository', REPO, '--input', str(source),
                    '--state', str(self.state), '--now', str(NOW), '--action', action]
            output = io.StringIO()
            with mock.patch.object(sys, 'argv', args), contextlib.redirect_stdout(output):
                code = alarm.main()
            result = json.loads(output.getvalue())
            self.assertEqual(code, 0 if result['allowed'] else 1)
            return result

        with mock.patch.object(alarm, 'sync_directory', sync):
            value = healthy()
            value['budgets']['rest']['remaining'] = 0
            first = call(value)
            self.assertFalse(first['state_saved'])
            self.assertFalse(first['allowed'])
            retained = {path.name: path.read_bytes() for path in pending.iterdir()}
            self.assertEqual(len(retained), 1)
            for action in ('merge-batch', 'completion', 'reconciliation'):
                with self.subTest(action=action):
                    result = call(healthy(), action)
                    self.assertFalse(result['state_saved'])
                    self.assertTrue(result['paused'])
                    self.assertEqual(result['allowed'], action != 'merge-batch')
                    self.assertEqual({path.name: path.read_bytes() for path in pending.iterdir()}, retained)
            fail_state_sync = False
            recovered = call(healthy())
            self.assertTrue(recovered['state_saved'])
            self.assertTrue(recovered['paused'])
            self.assertFalse(recovered['allowed'])
            self.assertEqual(recovered['pause']['evidence_sha256'], first['evidence_sha256'])
            self.assertEqual(list(pending.iterdir()), [])

    def test_nonregular_input_and_busy_state_lock_return_a_finite_refusal(self):
        source = self.folder / 'pipe'
        os.mkfifo(source)
        args = [sys.executable, '-I', str(HERE / 'alarm.py'), '--repository', REPO,
                '--state', str(self.state), '--now', str(NOW), '--action', 'merge-batch',
                '--input', str(source)]
        with self.subTest(case='nonregular input'):
            result = subprocess.run(args, capture_output=True, text=True, timeout=2)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(json.loads(result.stdout)['level'], 'unknown')
        with self.subTest(case='busy lock'):
            source = self.folder / 'healthy.json'
            source.write_text(json.dumps(healthy()))
            args[-1] = str(source)
            with Path(str(self.state) + '.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                result = subprocess.run(args, capture_output=True, text=True, timeout=2)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertFalse(json.loads(result.stdout)['state_saved'])

    def test_oldest_required_job_is_not_first_and_running_is_not_waiting(self):
        value = healthy()
        value['queue']['jobs'] = [
            dict(id='job-new', required=True, status='queued', queued_at=NOW - 4, started_at=None),
            dict(id='job-old', required=True, status='queued', queued_at=NOW - 900, started_at=None)]
        result = self.observe(value)
        self.assertEqual(result['level'], 'escalate')
        self.assertEqual(result['oldest_wait_seconds'], 900)

    def test_known_exhaustion_still_escalates_when_another_read_is_incomplete(self):
        value = healthy()
        value['queue']['complete'] = False
        value['budgets']['rest']['remaining'] = 0
        result = self.observe(value)
        self.assertEqual(result['level'], 'escalate')
        self.assertEqual(result['escalation'], 'due_not_sent')
        self.assertIn('observation_unknown', result['causes'])

    def test_corrupt_pause_refuses_admission_without_replacing_evidence(self):
        self.state.write_text('{"paused":true}')
        result = self.observe(healthy())
        self.assertEqual(result['level'], 'unknown')
        self.assertFalse(result['state_saved'])
        self.assertTrue(result['paused'])
        self.assertFalse(result['allowed'])
        self.assertEqual(self.state.read_text(), '{"paused":true}')


class Fleet(unittest.TestCase):
    def test_fleet_guard_blocks_new_work_but_allows_completion_without_api_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'observation.json'
            value = healthy()
            value['budgets']['graphql']['remaining'] = 0
            source.write_text(json.dumps(value))
            bin_dir = root / 'bin'
            bin_dir.mkdir()
            fake = bin_dir / 'gh'
            fake.write_text('#!/bin/sh\necho unexpected-API-call >&2\nexit 99\n')
            fake.chmod(0o755)
            env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ['PATH'],
                       GH_REPO=REPO, LAUNCH_FLEET_NOW=str(NOW),
                       LAUNCH_FLEET_OVERLOAD_INPUT=str(source),
                       LAUNCH_FLEET_OVERLOAD_STATE=str(root / 'pause.json'))
            for action in ('merge-batch', 'automatic-refresh', 'nonessential-poll',
                           'completion', 'reconciliation'):
                result = subprocess.run(['sh', str(HERE.parents[1] /
                    'skills/launch-fleet/scripts/fleet.sh'), 'overload', action],
                    env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0 if action in
                                 ('completion', 'reconciliation') else 1, result.stderr)
                answer = json.loads(result.stdout)
                self.assertTrue(answer['paused'])
                self.assertEqual(answer['escalation'], 'due_not_sent')
                self.assertEqual(result.stderr, '')


class Scheduled(unittest.TestCase):
    # R3: a scheduled run must refuse before refresh/poll effects. The fleet
    # action proof alone missed the loop's unconditional fetch/checkout path.
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.install = self.root / 'installed'
        repo = HERE.parents[1]
        for name in ('skills/launch-fleet/scripts/loop.sh',
                     'skills/launch-fleet/scripts/fleet.sh',
                     'skills/launch-fleet/scripts/records.py',
                     'skills/plan-graph/revision.sh', 'tools/ci-overload/alarm.py'):
            target = self.install / name.replace('tools/ci-overload/', 'skills/launch-fleet/scripts/carried/')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repo / name, target)
        self.loop = self.install / 'skills/launch-fleet/scripts/loop.sh'
        self.bundle = self.root / 'bundle.sh'
        generated = subprocess.run(['sh', str(self.loop), '--bundle', REPO],
                                   capture_output=True, text=True, timeout=2)
        self.assertEqual(generated.returncode, 0, generated.stderr)
        self.bundle.write_text(generated.stdout)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        for name, text in {
            'git': '#!/bin/sh\nprintf "git %s\\n" "$3" >> "$EFFECTS"\n'
                   'if [ "$3" = checkout ] && [ -n "${PAUSE_ON_CHECKOUT:-}" ]; then\n'
                   '  cp "$PAUSE_ON_CHECKOUT" "$LAUNCH_FLEET_OVERLOAD_STATE" || exit 98\nfi\n',
            'gh': '#!/bin/sh\nprintf "gh %s\\n" "$1" >> "$EFFECTS"\nexit 99\n',
        }.items():
            program = self.bin / name
            program.write_text(text)
            program.chmod(0o755)
        self.source = self.root / 'observation.json'
        self.source.write_text(json.dumps(healthy()))
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                        GH_REPO=REPO, LAUNCH_FLEET_NOW=str(NOW),
                        LAUNCH_FLEET_OVERLOAD_INPUT=str(self.source))
        self.env.pop('LAUNCH_FLEET_RUNTIME', None)
        self.env.pop('FLEET_SPEC', None)
        self.env.pop('PAUSE_ON_CHECKOUT', None)

    def prepare(self, mode, case, cloned=True):
        folder = self.root / (mode + '-' + case + '-' + str(cloned))
        folder.mkdir()
        consumer = folder / 'home' / REPO
        if cloned:
            (consumer / '.git').mkdir(parents=True)
            shutil.copytree(self.install / 'skills', consumer / 'skills')
        runtime = folder / 'runtime'
        runtime.mkdir()
        return folder, dict(self.env, LAUNCH_FLEET_HOME=str(folder / 'home'),
                            LAUNCH_FLEET_OVERLOAD_STATE=str(folder / 'pause.json'),
                            EFFECTS=str(folder / 'effects'), TMPDIR=str(runtime))

    def pause(self, path):
        value = healthy()
        value['budgets']['rest']['remaining'] = 0
        source = self.root / 'exhausted.json'
        source.write_text(json.dumps(value))
        result = subprocess.run([sys.executable, '-I', str(HERE / 'alarm.py'),
            '--repository', REPO, '--input', str(source), '--state', str(path),
            '--now', str(NOW), '--action', 'merge-batch'],
            capture_output=True, text=True, timeout=2)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertTrue(json.loads(result.stdout)['state_saved'])

    def run_loop(self, mode, folder, env):
        result = subprocess.run(['sh', str(self.loop if mode == 'source' else self.bundle)],
                                env=env, capture_output=True, text=True, timeout=2)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertEqual(list((folder / 'runtime').iterdir()), [])
        effects = folder / 'effects'
        return effects.read_text() if effects.exists() else ''

    def test_source_and_bundle_refuse_before_refresh_or_poll(self):
        for mode in ('source', 'bundle'):
            for cloned in (False, True):
                for case in ('retained', 'unknown', 'missing-state-path', 'healthy'):
                    with self.subTest(mode=mode, cloned=cloned, case=case):
                        folder, env = self.prepare(mode, case, cloned)
                        if case == 'retained':
                            self.pause(Path(env['LAUNCH_FLEET_OVERLOAD_STATE']))
                        elif case == 'unknown':
                            env['LAUNCH_FLEET_OVERLOAD_INPUT'] = str(folder / 'absent.json')
                        elif case == 'missing-state-path':
                            env.pop('LAUNCH_FLEET_OVERLOAD_STATE')
                        trace = self.run_loop(mode, folder, env)
                        expected = ('git fetch\ngit checkout\ngh api\n' if cloned
                                    else 'gh repo\n') if case == 'healthy' else ''
                        self.assertEqual(trace, expected)

    def test_bundle_survives_install_removal_and_rechecks_before_poll(self):
        seed = self.root / 'retained.json'
        self.pause(seed)
        # The checkout is present only to let the recording git finish. A
        # retained pause arriving during checkout must stop the later API read.
        for mode in ('source', 'bundle'):
            with self.subTest(mode=mode):
                folder, env = self.prepare(mode, 'pause-during-refresh')
                env['PAUSE_ON_CHECKOUT'] = str(seed)
                if mode == 'bundle':
                    shutil.rmtree(self.install)
                self.assertEqual(self.run_loop(mode, folder, env),
                                 'git fetch\ngit checkout\n')



def collector_fake(folder):
    """MT3's synthetic gh and its answers (tools/war-room's collector-ci fixture), unchanged."""
    spec = importlib.util.spec_from_file_location(
        'test_collect_ci', HERE.parents[1] / 'tools/war-room/test_collect_ci.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Fake(folder), module.R


class Supplier(unittest.TestCase):
    """MT6 (#825): `fleet.sh overload` with the supplier reads the collector's queue on demand."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.fake, self.r = collector_fake(self.root)
        self.input = self.root / 'observation.json'  # the caller's own input, used only without a supplier

    def env(self, fake=None, supplier=HERE / 'supply.py', now=None, state='pause.json', **extra):
        env = (fake or self.fake).env(GH_REPO=REPO, LAUNCH_FLEET_OVERLOAD_INPUT=str(self.input),
                                      LAUNCH_FLEET_OVERLOAD_STATE=str(self.root / state), **extra)
        for name in ('LAUNCH_FLEET_NOW', 'LAUNCH_FLEET_OVERLOAD_SUPPLY'):
            env.pop(name, None)
        if supplier is not None:
            env['LAUNCH_FLEET_OVERLOAD_SUPPLY'] = str(supplier)
        if now is not None:
            env['LAUNCH_FLEET_NOW'] = str(now)
        return env

    def admit(self, action, **options):
        """One `fleet.sh overload <action>`, with the supplier unless `supplier=None`."""
        asked = len(self.fake.asked())
        result = subprocess.run(['sh', str(HERE.parents[1] / 'skills/launch-fleet/scripts/fleet.sh'),
                                 'overload', action], env=self.env(**options), capture_output=True, text=True,
                                timeout=60)
        self.assertIn(result.returncode, (0, 1), result.stderr)
        answer = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0 if answer['allowed'] else 1)
        return answer, self.fake.asked()[asked:]

    def supply(self):
        """The supplier on its own, writing the caller's input; returns the observation."""
        result = subprocess.run([sys.executable, '-I', str(HERE / 'supply.py'), '--repository', REPO,
                                 '--output', str(self.input)], env=self.env(supplier=None),
                                capture_output=True, text=True, timeout=60)
        self.assertEqual((result.returncode, result.stdout), (0, ''), result.stderr)
        return json.loads(self.input.read_text())

    def without_queued_jobs(self, fake=None):
        fake = fake or self.fake
        jobs = fake.answer(self.r + '/actions/runs/7101/jobs?')
        jobs['jobs'] = [j for j in jobs['jobs'] if j['status'] != 'queued']
        jobs['total_count'] = len(jobs['jobs'])
        fake.drop(self.r + '/actions/workflows/privacy.yml/runs?status=queued&')

    def test_the_guard_decides_on_the_collector_s_queue_read_now(self):
        # catches: a supplier that never reads the collector (the guard keeps refusing every run on
        # a missing input) or reads it without the required queued jobs.
        # job-8101 has queued since 12:03:20 on 2026-01-05 (the fixture's README): the guard escalates.
        answer, asked = self.admit('merge-batch')
        self.assertIn('rate_limit', asked)
        self.assertEqual((answer['level'], answer['allowed'], answer['escalation']),
                         ('escalate', False, 'due_not_sent'))
        self.assertEqual(answer['oldest_wait_seconds'], answer['pause']['observed_at'] - 1767614600)

    def test_an_observation_older_than_the_bound_still_refuses(self):
        # catches: the supplier's observation stamped with the guard's clock or the file's write time,
        # or a looser bound on the supplied path, so the guard admits on an observation past 60 s.
        self.without_queued_jobs()
        before = int(time.time())
        answer, _ = self.admit('merge-batch', now=before + 120, state='late.json')  # 2 min after the read began
        self.assertEqual((answer['level'], answer['allowed']), ('unknown', False))
        answer, _ = self.admit('merge-batch')
        self.assertEqual((answer['level'], answer['allowed']), ('healthy', True))
        before = int(time.time())
        observed = self.supply()['observed_at']
        self.assertTrue(before <= observed <= int(time.time()))
        for age, allowed in ((60, True), (61, False)):
            with self.subTest(age=age):
                answer, asked = self.admit('merge-batch', supplier=None, now=observed + age,
                                           state='age-%d.json' % age)
                self.assertEqual(asked, [])
                self.assertEqual(answer['allowed'], allowed)
                self.assertEqual(answer['level'], 'healthy' if allowed else 'unknown')

    def test_a_failed_supply_never_admits_on_an_older_observation(self):
        # catches (R1): a supplier that can't start, can't import the collector or reads nothing, while
        # the caller's earlier healthy observation (under 60 s old) is still there: the guard admits on it.
        self.without_queued_jobs()
        self.supply()
        lone = self.root / 'lone'  # a copy of the supplier without the war room beside it
        lone.mkdir()
        shutil.copyfile(HERE / 'supply.py', lone / 'supply.py')
        for case, supplier in (('missing', self.root / 'missing-checkout/supply.py'),
                               ('no collector', lone / 'supply.py'), ('read fails', HERE / 'supply.py')):
            if case == 'read fails':
                self.fake.drop('rate_limit')
            for action in ('merge-batch', 'automatic-refresh', 'nonessential-poll'):
                with self.subTest(case=case, action=action):
                    state = '%s-%s.json' % (case.replace(' ', '-'), action)
                    answer, _ = self.admit(action, supplier=supplier, state=state)
                    self.assertEqual((answer['level'], answer['allowed'], answer['state_saved']),
                                     ('unknown', False, True))
                    self.assertEqual(json.loads((self.root / state).read_text())['level'], 'unknown')

    def test_an_observed_escalation_is_kept_when_another_admission_reads_healthy_first(self):
        # catches (R2): two admissions sharing one observation path, so a later healthy read replaces an
        # earlier escalating one before its guard opens it: both admit and no pause is kept.
        (self.root / 'b').mkdir()
        recovered, _ = collector_fake(self.root / 'b')
        self.without_queued_jobs(recovered)
        ready, release = self.root / 'ready', self.root / 'release'
        os.mkfifo(ready)
        os.mkfifo(release)
        held = self.root / 'held.py'  # the real supplier, then a hold before fleet.sh's guard runs
        held.write_text('import os, subprocess, sys\n'
                        "rc = subprocess.run([sys.executable, '-I', os.environ['REAL_SUPPLY'], *sys.argv[1:]]).returncode\n"
                        "with open(os.environ['HOLD_READY'], 'w') as f: f.write(str(rc))\n"
                        "with open(os.environ['HOLD_RELEASE']) as f: f.read()\n"
                        'sys.exit(rc)\n')
        fleet = ['sh', str(HERE.parents[1] / 'skills/launch-fleet/scripts/fleet.sh'), 'overload', 'merge-batch']
        first = subprocess.Popen(fleet, env=self.env(supplier=held, REAL_SUPPLY=str(HERE / 'supply.py'),
                                                     HOLD_READY=str(ready), HOLD_RELEASE=str(release)),
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            with open(ready) as f:
                self.assertEqual(f.read(), '0')
            second = subprocess.run(fleet, env=self.env(fake=recovered), capture_output=True, text=True,
                                    timeout=60)
            self.assertEqual((second.returncode, json.loads(second.stdout)['level']), (0, 'healthy'))
        finally:
            with open(release, 'w') as f:
                f.write('go')
            out, err = first.communicate(timeout=60)
        answer = json.loads(out)
        self.assertEqual((first.returncode, answer['level'], answer['allowed']), (1, 'escalate', False), err)
        self.assertEqual(json.loads((self.root / 'pause.json').read_text())['level'], 'escalate')

    def test_a_partial_read_still_hands_the_guard_its_known_exhaustion(self):
        # catches: a supplier that drops an incomplete observation, losing the exhausted pool the
        # collector did read: the guard then pauses as unknown and never says escalation is due.
        self.without_queued_jobs()
        self.fake.drop(self.r + '/actions/runs/7103/jobs?')
        self.fake.answer('rate_limit')['resources']['core']['remaining'] = 0
        answer, _ = self.admit('merge-batch')
        self.assertEqual((answer['level'], answer['allowed'], answer['escalation']),
                         ('escalate', False, 'due_not_sent'))
        self.assertEqual(sorted(answer['causes']), ['observation_unknown', 'rest_exhausted'])

    def test_completion_and_reconciliation_spend_no_read_and_stay_allowed(self):
        # catches: essential actions made to wait on, or spend API reads for, a fresh collector read
        # while the pools may be exhausted; they must finish whatever the observation says.
        for action in ('completion', 'reconciliation'):
            with self.subTest(action=action):
                answer, asked = self.admit(action, state=action + '.json')
                self.assertEqual(asked, [])
                self.assertEqual(answer['allowed'], True)

if __name__ == '__main__':
    unittest.main()
