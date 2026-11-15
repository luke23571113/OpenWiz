#!/usr/bin/env python3
"""#635: `openwiz init`'s packaged runtime, outside in, on a recording fake gh.

Each case runs tools/install/setup/init.py as the installed CLI does and counts
the provider writes the fake GitHub recorded, compares retained content, and
holds every result to the T1 contract checker (setup-onboard-contract/check.py).
Fixture proof only: no real GitHub repository is created or read here.
"""
import base64
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
INIT = ROOT / 'tools/install/setup/init.py'
spec = importlib.util.spec_from_file_location('setup_onboard_check',
                                              ROOT / 'tools/install/tests/setup-onboard-contract/check.py')
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)

CODE = 'synthetic-owner/synthetic-app'
COMPANION = 'synthetic-owner/synthetic-app-brain'
FILES = {'.openwiz/brain/README.md', '.openwiz/brain/settings.json',
         '.openwiz/brain/grills/README.md', '.openwiz/brain/decisions/README.md'}


def repository(full_name, visibility, **extra):
    owner = full_name.split('/')[0]
    value = {'full_name': full_name, 'private': visibility == 'private', 'visibility': visibility,
             'default_branch': 'main', 'permissions': {'push': True}, 'owner': {'login': owner, 'type': 'User'},
             'description': None, 'homepage': None, 'labels': [], 'pulls': [],
             'branches': {'main': {'README.md': 'Synthetic app.\n'}}}
    value.update(extra)
    return value


class Init(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix='openwiz-init-test-'))
        os.chmod(self.base, 0o700)
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        shutil.copy(HERE / 'fake_gh.py', self.bin / 'gh')
        os.chmod(self.bin / 'gh', 0o700)
        self.world_file = self.base / 'world.json'
        self.state = self.base / 'state'
        self.world({CODE.lower(): repository(CODE, 'private')})

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def world(self, repos=None, faults=(), user='synthetic-owner'):
        if repos is None:
            world = self.read()
            world['faults'] = list(faults)
        else:
            world = {'user': {'login': user, 'type': 'User'}, 'repos': repos, 'faults': list(faults), 'log': []}
        self.world_file.write_text(json.dumps(world))

    def read(self):
        return json.loads(self.world_file.read_text())

    def edit(self, change):
        world = self.read()
        change(world)
        self.world_file.write_text(json.dumps(world))

    def init(self, *args, expect=0):
        env = {'PATH': f'{self.bin}:/usr/bin:/bin', 'HOME': str(self.base / 'home'),
               'OPENWIZ_STATE_DIR': str(self.state), 'FAKE_GH_WORLD': str(self.world_file)}
        result = subprocess.run([sys.executable, '-I', str(INIT), '--repository', CODE, '--json', *args],
                                env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, expect, result.stdout + result.stderr)
        self.assertEqual(result.stderr, '')
        document = json.loads(result.stdout)
        if document['schema'] == 'openwiz.setup-onboard.v1':
            report = contract.check(document)
            self.assertEqual(report.problems, [], document)
            self.assertEqual(report.failures, [], document)
        return document

    def writes(self):
        return [call for call in self.read()['log'] if call[0] != 'GET']

    def apply(self, preview, expect=0):
        return self.init('--yes', '--operation', preview['operation_id'], expect=expect)

    def files(self, name, branch='openwiz/brain'):
        return self.read()['repos'][name.lower()]['branches'].get(branch, {})

    def saved(self):
        return json.loads((self.state / 'setup/state.json').read_text())

    # Catches: a preview that writes, a private repository given a companion,
    # or a brain that carries runtime state, ids or other content.
    def test_private_code_keeps_the_brain_in_repository_through_one_visible_proposal(self):
        preview = self.init()
        self.assertEqual((preview['outcome'], preview['brain']['location']), ('proposed', 'in_repository'))
        self.assertEqual(self.writes(), [], 'a preview writes nothing on GitHub')
        self.assertIn(CODE, preview['report_line'])
        applied = self.apply(preview)
        self.assertEqual(applied['outcome'], 'applied')
        self.assertEqual([e['kind'] for e in applied['effects']], ['create_label', 'open_pull_request'])
        self.assertEqual(applied['pull_requests'], [{'repository': CODE, 'number': 1, 'visible': True,
                                                     'state': 'open'}])
        written = self.files(CODE)
        self.assertEqual(set(written) - {'README.md'}, FILES)
        content = ''.join(written[f] for f in FILES)
        for private in (str(self.state), str(self.base), preview['operation_id'], 'thr_', 'OPENWIZ_STATE_DIR'):
            self.assertNotIn(private, content)
        settings = json.loads(written['.openwiz/brain/settings.json'])
        self.assertEqual(settings['brain_location'], 'in_repository')
        self.assertEqual(self.read()['repos'][CODE.lower()]['branches']['main'],
                         {'README.md': 'Synthetic app.\n'}, 'only proposed, never pushed to main')
        self.assertEqual(self.saved()['brain'], applied['brain'])

    # Catches: private records written into public code, or a companion that is
    # public or unlinked.
    def test_public_code_gets_a_linked_private_companion_and_no_private_content(self):
        self.world({CODE.lower(): repository(CODE, 'public')})
        preview = self.init()
        self.assertEqual(preview['brain']['brain_repository'], COMPANION)
        self.assertEqual(self.writes(), [])
        applied = self.apply(preview)
        self.assertEqual([e['kind'] for e in applied['effects']],
                         ['create_companion', 'link_companion', 'create_label', 'open_pull_request'])
        companion = self.read()['repos'][COMPANION.lower()]
        self.assertEqual((companion['private'], companion['homepage']), (True, f'https://github.com/{CODE}'))
        self.assertEqual(set(self.files(COMPANION)), FILES)
        code = self.read()['repos'][CODE.lower()]
        self.assertEqual(code['branches'], {'main': {'README.md': 'Synthetic app.\n'}}, 'public code untouched')
        self.assertEqual(code['labels'], ['openwiz'])
        self.assertEqual(sum(1 for call in self.writes() if call[1].startswith(f'repos/{CODE}')), 1,
                         'only the label is written on public code')
        self.assertEqual(applied['private_content_written'], 'brain_repository')

    # Catches: visibility inferred from a missing, internal, contradictory,
    # unread or renamed read, and any write before it is positively known.
    def test_unknown_or_ambiguous_visibility_refuses_before_any_write(self):
        cases = {'internal': repository(CODE, 'internal'),
                 'contradictory': dict(repository(CODE, 'public'), private=True),
                 'missing': {k: v for k, v in repository(CODE, 'private').items() if k != 'visibility'},
                 'unreadable': dict(repository(CODE, 'private'), hidden=True),
                 'renamed': dict(repository(CODE, 'private'), full_name='synthetic-owner/other-name')}
        for name, repo in cases.items():
            with self.subTest(name):
                shutil.rmtree(self.state, ignore_errors=True)
                self.world({CODE.lower(): repo})
                refused = self.init(expect=5)
                self.assertEqual((refused['outcome'], refused['reason_code'], refused['brain']),
                                 ('refused', 'visibility_unknown', None))
                self.assertEqual(self.writes(), [])
        self.world({CODE.lower(): repository(CODE, 'private')}, faults=[{'method': 'GET', 'path': f'repos/{CODE}',
                                                                         'mode': 'drop', 'times': 1}])
        self.assertEqual(self.init(expect=5)['reason_code'], 'visibility_unknown')
        self.assertEqual(self.writes(), [])

    # Catches: reusing a foreign or public repository as the brain, a name GitHub
    # would truncate, or a companion created under another user's account.
    def test_unsafe_or_conflicting_companions_refuse_with_nothing_written(self):
        long = 'synthetic-owner/' + 'a' * 95
        cases = {
            'companion_conflict': ({CODE.lower(): repository(CODE, 'public'),
                                    COMPANION.lower(): repository(COMPANION, 'public')}, CODE, 'synthetic-owner'),
            'foreign': ({CODE.lower(): repository(CODE, 'public'),
                         COMPANION.lower(): repository(COMPANION, 'private', description='Someone else')},
                        CODE, 'synthetic-owner'),
            'companion_name_unsafe': ({long.lower(): repository(long, 'public')}, long, 'synthetic-owner'),
            'companion_owner_mismatch': ({CODE.lower(): repository(CODE, 'public')}, CODE, 'synthetic-helper'),
        }
        for name, (repos, target, login) in cases.items():
            with self.subTest(name):
                shutil.rmtree(self.state, ignore_errors=True)
                self.world(repos, user=login)
                before = copy.deepcopy(self.read()['repos'])
                env_repo = ['--repository', target] if target != CODE else []
                refused = self.init(*env_repo, expect=5)
                self.assertEqual(refused['reason_code'], 'companion_conflict' if name == 'foreign' else name)
                self.assertEqual(self.writes(), [])
                self.assertEqual(self.read()['repos'], before)

    # Catches: a denied companion creation reported as done, or followed by
    # writes that publish the brain somewhere else.
    def test_denied_companion_creation_stops_before_any_private_content(self):
        self.world({CODE.lower(): repository(CODE, 'public')},
                   faults=[{'method': 'POST', 'path': 'user/repos', 'mode': 403, 'times': 9}])
        preview = self.init()
        refused = self.apply(preview, expect=5)
        self.assertEqual((refused['reason_code'], refused['private_content_written']), ('companion_denied', 'none'))
        self.assertEqual(self.writes(), [['POST', 'user/repos']])
        self.assertNotIn(COMPANION.lower(), self.read()['repos'])
        self.assertNotIn('brain', self.saved())

    # Catches: a lost reply retried blindly (a duplicate repository, label,
    # file or pull request), or uncertainty erased by a later preview.
    def test_lost_replies_stay_uncertain_until_read_back_then_complete_once(self):
        steps = ['user/repos', f'repos/{COMPANION}', f'repos/{CODE}/labels', f'repos/{COMPANION}/contents/',
                 f'repos/{COMPANION}/pulls']
        methods = {'user/repos': 'POST', f'repos/{COMPANION}': 'PATCH', f'repos/{CODE}/labels': 'POST',
                   f'repos/{COMPANION}/contents/': 'PUT', f'repos/{COMPANION}/pulls': 'POST'}
        for mode in ('lose', 'drop'):
            for path in steps:
                with self.subTest(mode=mode, path=path):
                    shutil.rmtree(self.state, ignore_errors=True)
                    self.world({CODE.lower(): repository(CODE, 'public')},
                               faults=[{'method': methods[path], 'path': path, 'mode': mode, 'times': 1}])
                    preview = self.init()
                    uncertain = self.apply(preview, expect=6)
                    self.assertEqual(uncertain['outcome'], 'uncertain')
                    calls = len(self.writes())
                    again = self.init(expect=6)
                    self.assertEqual(again['operation_id'], preview['operation_id'])
                    self.assertEqual(len(self.writes()), calls, 'a preview never retries')
                    done = self.apply(preview)
                    self.assertEqual(done['outcome'], 'applied')
                    world = self.read()
                    self.assertEqual(sum(1 for c in world['log'] if c == ['POST', 'user/repos']),
                                     2 if (mode, path) == ('drop', 'user/repos') else 1)
                    self.assertEqual(len(world['repos'][COMPANION.lower()]['pulls']), 1)
                    self.assertEqual(world['repos'][CODE.lower()]['labels'], ['openwiz'])
                    self.assertEqual(set(world['repos'][COMPANION.lower()]['branches']['openwiz/brain']), FILES)
                    retried = [e for e in done['effects'] if e['attempts'] > 1]
                    self.assertTrue(all(e['reconciliation'] == 'provider_read_back' for e in retried))
                    self.assertTrue(all(e['effect_count'] == 1 for e in done['effects']))

    # Catches: repeat init duplicating a pull request, overwriting the owner's
    # edits, or ignoring the owner's closed proposal.
    def test_repeat_init_reconciles_existing_work_and_never_overwrites_it(self):
        first = self.apply(self.init())
        calls = len(self.writes())
        again = self.init()
        self.assertEqual((again['outcome'], again['operation_id']), ('applied', first['operation_id']))
        self.assertEqual(len(self.writes()), calls)
        # Lost local state, owner edits on the open proposal: reuse, write nothing.
        shutil.rmtree(self.state)
        self.edit(lambda w: w['repos'][CODE.lower()]['branches']['openwiz/brain'].update(
            {'.openwiz/brain/README.md': 'Owner edit.\n'}))
        fresh = self.init()
        self.assertEqual(fresh['effects'], [])
        self.assertEqual(self.apply(fresh)['pull_requests'][0]['number'], 1)
        self.assertEqual(len(self.writes()), calls)
        self.assertEqual(self.files(CODE)['.openwiz/brain/README.md'], 'Owner edit.\n')
        # Owner work on the branch without a proposal is never overwritten.
        shutil.rmtree(self.state)
        self.edit(lambda w: w['repos'][CODE.lower()].update(pulls=[]))
        conflict = self.apply(self.init(), expect=5)
        self.assertEqual(conflict['reason_code'], 'owner_work_conflict')
        self.assertEqual(self.files(CODE)['.openwiz/brain/README.md'], 'Owner edit.\n')
        # A proposal the owner closed is not reopened or replaced.
        shutil.rmtree(self.state)
        self.edit(lambda w: w['repos'][CODE.lower()].update(
            pulls=[{'number': 1, 'state': 'closed', 'head': 'openwiz/brain'}]))
        self.assertEqual(self.init(expect=5)['reason_code'], 'proposal_closed')

    # Catches: an apply that acts on an unknown operation or on a preview whose
    # GitHub facts changed since.
    def test_apply_acts_only_on_the_exact_current_preview(self):
        self.assertEqual(self.init('--yes', '--operation', '0' * 32, expect=8)['reason_code'], 'operation_stale')
        preview = self.init()
        self.edit(lambda w: w['repos'][CODE.lower()].update(private=False, visibility='public'))
        self.assertEqual(self.apply(preview, expect=8)['reason_code'], 'operation_stale')
        self.assertEqual(self.writes(), [])
        usage = self.init('--yes', expect=2)
        self.assertEqual((usage['schema'], usage['error']['kind']), ('openwiz.cli-error.v1', 'usage'))

    # Catches: a setting that cannot move the brain later, or a move that skips
    # the preview, authorization and visible proposal.
    def test_the_brain_location_setting_moves_through_the_same_proposal_rules(self):
        self.apply(self.init())
        self.edit(lambda w: w['repos'][CODE.lower()].update(private=False, visibility='public'))
        calls = len(self.writes())
        moved = self.init()
        self.assertEqual((moved['outcome'], moved['brain']['location']), ('proposed', 'companion'))
        self.assertEqual(len(self.writes()), calls)
        self.assertEqual(self.saved()['brain']['location'], 'in_repository', 'unchanged until applied')
        applied = self.apply(moved)
        self.assertEqual(self.saved()['brain'], applied['brain'])
        settings = json.loads(self.files(COMPANION)['.openwiz/brain/settings.json'])
        self.assertEqual((settings['brain_location'], settings['code_repository']), ('companion', CODE))


class BrainReference(unittest.TestCase):
    """The store's optional `brain` field and setup's project check of it."""

    def setUp(self):
        sys.path.insert(0, str(ROOT / 'tools/install/setup'))
        import store
        self.store = store
        self.base = Path(tempfile.mkdtemp(prefix='openwiz-brain-test-'))

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def brain(self, **change):
        value = {'location': 'companion', 'code_repository': CODE, 'code_visibility': 'public',
                 'brain_repository': COMPANION, 'brain_visibility': {'known': 'private'},
                 'visibility_basis': 'github_repository_read', 'folder': '.openwiz/brain',
                 'setting': 'brain_location',
                 'decision_repositories': {'public': {'owner': 'synthetic-owner', 'name': 'synthetic-app'},
                                           'private': {'owner': 'synthetic-owner',
                                                       'name': 'synthetic-app-brain'}}}
        value.update(change)
        return value

    # Catches: an existing project refused, or an unsafe reference (a companion
    # that is the code itself, a mismatched pair, a public brain) accepted.
    def test_existing_projects_and_valid_references_pass_unsafe_ones_refuse(self):
        state = self.store.empty()
        self.store.validate(state)
        self.store.validate(dict(state, brain=None))
        self.store.validate(dict(state, brain=self.brain()))
        self.store.validate(dict(state, brain=self.brain(
            location='in_repository', code_visibility='private', brain_repository=CODE,
            decision_repositories=None)))
        for bad in (self.brain(brain_repository=CODE.upper()),
                    self.brain(brain_visibility={'known': 'public'}),
                    self.brain(code_visibility='private'),
                    self.brain(decision_repositories=None),
                    self.brain(location='in_repository', code_visibility='private', decision_repositories=None),
                    dict(self.brain(), token='synthetic')):
            with self.subTest(bad=bad):
                with self.assertRaises(self.store.Refused):
                    self.store.validate(dict(state, brain=bad))

    # Catches: the project check passing on a brain that is public, missing or
    # only proposed, or failing an existing project that has no brain.
    def test_the_project_check_resolves_the_brain_reference(self):
        spec = importlib.util.spec_from_file_location('openwiz_setup', ROOT / 'tools/install/setup/setup.py')
        setup = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(setup)
        bin_dir = self.base / 'bin'
        bin_dir.mkdir()
        shutil.copy(HERE / 'fake_gh.py', bin_dir / 'gh')
        os.chmod(bin_dir / 'gh', 0o700)
        world = self.base / 'world.json'
        record = json.dumps({'schema': 'openwiz.brain-settings.v1', 'brain_location': 'companion',
                             'code_repository': CODE, 'brain_repository': COMPANION})

        def resolve(companion):
            world.write_text(json.dumps({'user': {'login': 'synthetic-owner', 'type': 'User'}, 'faults': [],
                                         'log': [], 'repos': {COMPANION.lower(): companion}}))
            saved = dict(os.environ)
            os.environ.update(PATH=f'{bin_dir}:/usr/bin:/bin', FAKE_GH_WORLD=str(world))
            try:
                return setup.check_brain(self.brain())
            finally:
                os.environ.clear()
                os.environ.update(saved)
        merged = repository(COMPANION, 'private', branches={'main': {'.openwiz/brain/settings.json': record}})
        self.assertEqual(setup.check_brain(None), 'project_verified')
        self.assertEqual(resolve(merged), 'project_verified')
        self.assertEqual(resolve(dict(merged, private=False, visibility='public')), 'project_settings_missing')
        self.assertEqual(resolve(repository(COMPANION, 'private', branches={
            'main': {}, 'openwiz/brain': {'.openwiz/brain/settings.json': record}})), 'project_settings_missing')
        self.assertEqual(resolve(dict(merged, hidden=True)), 'project_settings_missing')


if __name__ == '__main__':
    unittest.main()
