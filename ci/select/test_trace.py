#!/usr/bin/env python3
"""The tracer's and the map builder's own tests (#432, K15), on synthetic
strace lines and a synthetic repository; no test runs under strace here.

  python3 -I ci/select/test_trace.py
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import map as map_mod  # noqa: E402
import pick  # noqa: E402
import resolve  # noqa: E402
import trace  # noqa: E402

R = '/w/repo'


def parse(text, cwd=R):
    return trace.parse(text.strip('\n').splitlines(), cwd)


class Parse(unittest.TestCase):
    def test_opens_stats_and_probes_that_found_nothing_all_count(self):
        touched, _ = parse(f'''
10 openat(AT_FDCWD<{R}>, "crates/core/src/lib.rs", O_RDONLY|O_CLOEXEC) = 3<{R}/crates/core/src/lib.rs>
10 newfstatat(AT_FDCWD<{R}>, "tests/fixtures/maybe.json", 0x7ffd, 0) = -1 ENOENT (No such file or directory)
10 statx(AT_FDCWD<{R}/tools/war-room>, "test/support/x.js", AT_STATX_SYNC_AS_STAT, STATX_ALL, 0x1) = 0
10 access("{R}/skills/a/SKILL.md", R_OK) = 0
''')
        self.assertEqual(touched, {f'{R}/crates/core/src/lib.rs', f'{R}/tests/fixtures/maybe.json',
                                   f'{R}/tools/war-room/test/support/x.js', f'{R}/skills/a/SKILL.md'})

    def test_relative_paths_follow_each_process_s_folder(self):
        touched, _ = parse(f'''
10 chdir("tools/war-room") = 0
10 clone(child_stack=NULL, flags=CLONE_CHILD_CLEARTID|SIGCHLD) = 11
11 open("charts/app.js", O_RDONLY) = 3<{R}/tools/war-room/charts/app.js>
10 open("../../docs/x.md", O_RDONLY) = -1 ENOENT (No such file or directory)
11 fchdir(4<{R}/tests>) = 0
11 stat("fixtures/a.json", 0x1) = 0
''')
        self.assertEqual(touched, {f'{R}/tools/war-room/charts/app.js', f'{R}/docs/x.md', f'{R}/tools/war-room',
                                   f'{R}/tests/fixtures/a.json'})

    def test_a_call_split_across_two_lines_is_read_whole(self):
        touched, _ = parse(f'''
10 openat(AT_FDCWD<{R}>, "crates/a.rs", O_RDONLY <unfinished ...>
11 openat(AT_FDCWD<{R}>, "crates/b.rs", O_RDONLY) = 3<{R}/crates/b.rs>
10 <... openat resumed>) = 4<{R}/crates/a.rs>
''')
        self.assertEqual(touched, {f'{R}/crates/a.rs', f'{R}/crates/b.rs'})

    def test_the_fd_s_own_path_is_kept_too_through_a_symlink(self):
        touched, _ = parse(f'''
10 execve("/tmp/x/room-cli", ["room-cli"], 0x1 /* 3 vars */) = 0
10 openat(AT_FDCWD</tmp/x>, "/tmp/x/fake", O_RDONLY) = 3<{R}/target/debug/fake-room-cli>
''')
        self.assertIn(f'{R}/target/debug/fake-room-cli', touched)

    def test_cargo_s_own_reads_are_left_out_but_the_programs_it_runs_are_not(self):
        touched, _ = parse(f'''
10 execve("/home/synthetic/.cargo/bin/cargo", ["cargo", "test"], 0x1 /* 3 vars */) = 0
10 newfstatat(AT_FDCWD<{R}>, "crates/gadget/src/lib.rs", 0x1, 0) = 0
10 openat(AT_FDCWD<{R}>, "target/debug/.fingerprint/x", O_RDONLY) = 3<{R}/target/debug/.fingerprint/x>
10 clone3({{flags=CLONE_VM, exit_signal=SIGCHLD}}, 88) = 12
12 openat(AT_FDCWD<{R}>, "crates/gadget/Cargo.toml", O_RDONLY) = 3<{R}/crates/gadget/Cargo.toml>
12 execve("{R}/target/debug/deps/proof-0123456789abcdef", ["proof"], 0x1 /* 3 vars */) = 0
12 openat(AT_FDCWD<{R}/tests>, "fixtures/a.json", O_RDONLY) = 3<{R}/tests/fixtures/a.json>
''')
        self.assertEqual(touched, {f'{R}/target/debug/deps/proof-0123456789abcdef', f'{R}/tests/fixtures/a.json'})

    def test_listings_are_the_folders_read_with_getdents(self):
        _, listed = parse(f'''
10 openat(AT_FDCWD<{R}>, "tests/fixtures", O_RDONLY|O_DIRECTORY|O_CLOEXEC) = 3<{R}/tests/fixtures>
10 getdents64(3<{R}/tests/fixtures>, 0x55 /* 4 entries */, 32768) = 112
10 openat(AT_FDCWD<{R}>, "crates", O_RDONLY|O_DIRECTORY|O_PATH) = 4<{R}/crates>
''')
        self.assertEqual(listed, {f'{R}/tests/fixtures'})

    def test_escaped_paths_come_back_whole(self):
        touched, _ = parse(f'''
10 openat(AT_FDCWD<{R}>, "tests/a b\\"q\\\\\\n\\303\\251.json", O_RDONLY) = -1 ENOENT (No such file or directory)
''')
        self.assertEqual(touched, {f'{R}/tests/a b"q\\\né.json'})

    def test_an_empty_path_is_the_open_file_itself(self):
        touched, _ = parse(f'''
10 newfstatat(3<{R}/a.rs>, "", {{st_mode=S_IFREG}}, AT_EMPTY_PATH) = 0
''')
        self.assertEqual(touched, set())


class Repo(unittest.TestCase):
    """A synthetic repository with a target/ and dep-info, and a cargo
    metadata answer given directly."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        files = {
            'crates/core/Cargo.toml': '', 'crates/core/src/lib.rs': '',
            'crates/gadget/Cargo.toml': '', 'crates/gadget/src/lib.rs': '',
            'crates/widget/Cargo.toml': '', 'crates/widget/src/main.rs': '', 'crates/widget/src/parts.rs': '',
            'tests/Cargo.toml': '', 'tests/proof/main.rs': 'use openwiz_core::x; mod support;',
            'tests/proof/support.rs': 'fn f() { openwiz_widget::y(); }',
            'tools/war-room/node_modules/react/index.js': '', 'tools/war-room/package.json': '',
            'target/debug/deps/proof-0123456789abcdef': '',
            'target/debug/deps/proof-0123456789abcdef.d':
                f'{self.root}/target/debug/deps/proof-0123456789abcdef: tests/proof/main.rs tests/proof/support.rs\n',
            'target/debug/deps/openwiz_core-1111111111111111.d':
                f'{self.root}/target/debug/deps/libopenwiz_core-1111111111111111.rlib: crates/core/src/lib.rs\n',
            'target/debug/deps/openwiz_gadget-2222222222222222.d':
                f'{self.root}/target/debug/deps/libopenwiz_gadget-2222222222222222.rlib: crates/gadget/src/lib.rs\n',
            'target/debug/deps/openwiz_widget-3333333333333333.d':
                f'{self.root}/target/debug/deps/libopenwiz_widget-3333333333333333.rlib: '
                f'{self.root}/crates/widget/src/main.rs {self.root}/crates/widget/src/parts.rs\n',
            'target/debug/openwiz-widget': '',
            'target/debug/openwiz-widget.d':
                f'{self.root}/target/debug/openwiz-widget: {self.root}/crates/widget/src/main.rs '
                f'{self.root}/crates/widget/src/parts.rs {self.root}/crates/core/src/lib.rs\n',
            'target/debug/examples/openwiz-widget': '',
            'target/debug/examples/openwiz-widget.d':
                f'{self.root}/target/debug/examples/openwiz-widget: {self.root}/tests/fixture-entrypoints/widget.rs '
                f'{self.root}/crates/widget/src/parts.rs {self.root}/crates/core/src/lib.rs\n',
            'crates/widget/build.rs': '',
            'target/debug/mystery': '',
            'target/tmp/scratch.txt': '',
        }
        for rel, text in files.items():
            os.makedirs(os.path.dirname(os.path.join(self.root, rel)), exist_ok=True)
            with open(os.path.join(self.root, rel), 'w') as f:
                f.write(text)
        self.r = resolve.Resolver(self.root)
        self.r._meta = resolve.index(self.metadata(), os.path.realpath(self.root))

    def metadata(self, extra=()):
        """A `cargo metadata --no-deps` answer with this tree's collision
        (#1579 R5): a synthetic widget crate's library and an openwiz-tests
        example are both `openwiz-widget`, so both are the crate name
        `openwiz_widget`."""
        real = os.path.realpath(self.root)

        def pkg(name, folder, targets, deps=()):
            return {'name': name, 'manifest_path': f'{real}/{folder}/Cargo.toml',
                    'dependencies': [{'name': d, 'path': f'{real}/x'} for d in deps] + [{'name': 'serde'}],
                    'targets': [{'name': n, 'kind': k} for n, k in targets]}
        return {'packages': [
            pkg('openwiz-core', 'crates/core', [('openwiz_core', ['lib'])]),
            pkg('openwiz-gadget', 'crates/gadget', [('openwiz_gadget', ['lib'])], ['openwiz-core']),
            pkg('openwiz-widget', 'crates/widget', [('openwiz_widget', ['lib']), ('openwiz-widget', ['bin'])],
                ['openwiz-core']),
            pkg('openwiz-tests', 'tests', [('proof', ['test']), ('openwiz-widget', ['example']),
                                           ('fake-room-cli', ['bin'])],
                ['openwiz-core', 'openwiz-gadget', 'openwiz-widget']),
            *extra]}

    def at(self, *rels):
        return {os.path.join(self.root, r) for r in rels}

    def test_a_test_binary_becomes_its_sources_and_the_crates_they_name(self):
        files, dirs, why = self.r.resolve(self.at('target/debug/deps/proof-0123456789abcdef'), set())
        self.assertIsNone(why)
        self.assertEqual(files, ['crates/core/Cargo.toml', 'crates/core/src/lib.rs', 'crates/widget/Cargo.toml',
                                 'crates/widget/build.rs', 'crates/widget/src/main.rs', 'crates/widget/src/parts.rs',
                                 'tests/Cargo.toml', 'tests/proof/main.rs', 'tests/proof/support.rs'])

    def test_a_program_a_test_ran_becomes_its_uplifted_dep_info(self):
        files, _, why = self.r.resolve(self.at('target/debug/openwiz-widget'), set())
        self.assertIsNone(why)
        self.assertEqual(files, ['crates/core/Cargo.toml', 'crates/core/src/lib.rs', 'crates/widget/Cargo.toml',
                                 'crates/widget/build.rs', 'crates/widget/src/main.rs', 'crates/widget/src/parts.rs'])

    def test_a_test_naming_a_crate_whose_name_an_example_shares_keeps_that_crate(self):
        files, _, why = self.r.resolve(self.at('target/debug/deps/proof-0123456789abcdef'), set())
        self.assertIsNone(why)
        self.assertIn('crates/widget/src/parts.rs', files)
        self.assertIn('crates/widget/Cargo.toml', files)

    def test_an_uplifted_program_adds_its_package_s_manifests_and_build_scripts(self):
        files, _, why = self.r.resolve(self.at('target/debug/examples/openwiz-widget'), set())
        self.assertIsNone(why)
        for f in ('crates/widget/Cargo.toml', 'crates/widget/build.rs', 'crates/core/Cargo.toml', 'tests/Cargo.toml',
                  'crates/widget/src/parts.rs', 'tests/fixture-entrypoints/widget.rs'):
            self.assertIn(f, files)

    def test_a_crate_manifest_change_selects_the_proof_running_that_program(self):
        files, dirs, why = self.r.resolve(self.at('target/debug/examples/openwiz-widget'), set())
        mp = {'schema': pick.MAP_SCHEMA, 'commit': 'c' * 40,
              'units': {'rust:test:cli-agent': {'files': files, 'dirs': dirs}}}
        result = pick.select([('M', 'crates/widget/Cargo.toml')], mp, ['rust:test:cli-agent'],
                             lambda p: b'', lambda ps: set())
        self.assertEqual(result['tests'], ['rust:test:cli-agent'])

    def test_a_program_or_crate_name_two_packages_share_leaves_the_test_out(self):
        twin = {'name': 'openwiz-twin', 'manifest_path': f'{os.path.realpath(self.root)}/crates/twin/Cargo.toml',
                'dependencies': [], 'targets': [{'name': 'openwiz-widget', 'kind': ['bin']},
                                                {'name': 'openwiz_core', 'kind': ['lib']}]}
        r = resolve.Resolver(self.root)
        r._meta = resolve.index(self.metadata([twin]), os.path.realpath(self.root))
        self.assertIsNotNone(r.resolve(self.at('target/debug/openwiz-widget'), set())[2])
        self.assertIsNotNone(r.resolve(self.at('target/debug/deps/proof-0123456789abcdef'), set())[2])

    def test_cargo_s_bookkeeping_and_scratch_are_not_inputs(self):
        files, _, why = self.r.resolve(self.at('target/tmp/scratch.txt', 'target/debug/deps/proof-0123456789abcdef.d',
                                               'target/debug/.fingerprint/x', 'target/debug/build/x/out/y'), set())
        self.assertIsNone(why)
        self.assertEqual(files, [])

    def test_a_build_product_it_can_t_trace_leaves_the_test_out(self):
        files, dirs, why = self.r.resolve(self.at('target/debug/mystery', 'crates/core/src/lib.rs'), set())
        self.assertEqual((files, dirs), ([], []))
        self.assertIn('target/debug/mystery', why)

    def test_git_s_index_or_objects_leave_the_test_out(self):
        for rel in ('.git/index', '.git/objects/pack/p.pack'):
            with self.subTest(rel):
                self.assertIsNotNone(self.r.resolve({f'{self.root}/{rel}'}, set())[2])
        self.assertIsNone(self.r.resolve({f'{self.root}/.git/HEAD', f'{self.root}/.git/refs/heads/main'}, set())[2])

    def test_node_modules_and_missing_files(self):
        files, dirs, why = self.r.resolve(
            self.at('tools/war-room/node_modules/react/index.js', 'docs/missing.md', 'crates/core'),
            self.at('tests/fixtures', 'tools/war-room/node_modules/react', 'target/debug', '.'))
        self.assertIsNone(why)
        self.assertEqual(files, ['docs/missing.md', 'tools/war-room/package-lock.json', 'tools/war-room/package.json'])
        self.assertEqual(dirs, ['.', 'tests/fixtures'])


class Map(unittest.TestCase):
    LISTED = {'rust:test:proof', 'rust:test:fleet', 'rust:test:loops'}

    def records(self):
        return {
            'rust:test:proof': {'files': ['tests/proof/main.rs'], 'dirs': [], 'seconds': 2.0, 'exit': 0, 'traced': True},
            'rust:test:fleet': {'files': ['tests/fleet/main.rs', 'crates/core/src/lib.rs'], 'dirs': ['tests/fleet'],
                                'seconds': 9.0, 'exit': 0, 'traced': True},
            'rust:test:loops': {'files': [], 'dirs': [], 'seconds': 1.0, 'exit': 0, 'traced': False,
                                'untraced': 'failed under strace'},
        }

    def test_untraced_tests_are_left_out(self):
        mp, left = map_mod.build(self.records(), 'c' * 40, self.LISTED)
        self.assertEqual(mp['schema'], pick.MAP_SCHEMA)
        self.assertEqual(mp['units']['rust:test:fleet'],
                         {'files': ['crates/core/src/lib.rs', 'tests/fleet/main.rs'],
                          'dirs': ['tests/fleet'], 'seconds': 9.0})
        self.assertNotIn('rust:test:loops', mp['units'])
        self.assertEqual(left, {'rust:test:loops': 'failed under strace'})

    def test_a_test_without_a_record_refuses_the_map(self):
        recs = self.records()
        del recs['rust:test:proof']
        with self.assertRaises(SystemExit):
            map_mod.build(recs, 'c' * 40, self.LISTED)

    def test_a_record_for_a_test_not_here_refuses_the_map(self):
        with self.assertRaises(SystemExit):
            map_mod.build(self.records(), 'c' * 40, self.LISTED - {'rust:test:loops'})

    def test_the_selector_reads_the_map_it_builds(self):
        mp, _ = map_mod.build(self.records(), 'c' * 40, self.LISTED)
        result = pick.select([('M', 'crates/core/src/lib.rs')], json.loads(json.dumps(mp)), sorted(self.LISTED),
                             lambda p: b'', lambda ps: set())
        self.assertEqual(result['tests'], ['rust:test:fleet', 'rust:test:loops'])


ROOT = os.path.dirname(os.path.dirname(HERE))
PRIVACY = os.path.join(ROOT, 'tools/privacy-check/check.py')
# The selector's committed files the public tree carries (#2298): the measured
# map and this file's synthetic strace fixtures.
PUBLISHED = ('ci/select/map.json', 'ci/select/test_trace.py')


class Privacy(unittest.TestCase):
    """The open-development privacy check (T3: home-shaped paths) passes the
    committed map and fixtures, and still refuses a planted home row."""

    def check(self, edit=None):
        with tempfile.TemporaryDirectory() as tree:
            for rel in PUBLISHED:
                os.makedirs(os.path.join(tree, os.path.dirname(rel)), exist_ok=True)
                with open(os.path.join(ROOT, rel)) as f:
                    text = f.read()
                with open(os.path.join(tree, rel), 'w') as f:
                    f.write(edit(rel, text) if edit else text)
            import subprocess
            r = subprocess.run([sys.executable, '-I', PRIVACY, '--tree', tree], capture_output=True, text=True)
        return r.returncode, [ln for ln in r.stdout.splitlines() if ln.startswith(('T', 'F', 'READ'))]

    def test_the_committed_map_and_fixtures_have_no_finding(self):
        rc, findings = self.check()
        self.assertEqual((len(findings), findings[:5]), (0, []))
        self.assertEqual(rc, 0)

    def test_a_planted_home_row_is_still_refused(self):
        # Split so this source line is not itself a home-shaped path.
        planted = '"tools/war-room/' + 'home' + '/package.json",'

        def plant(rel, text):
            if rel != 'ci/select/map.json':
                return text
            at = text.index('"files": [') + len('"files": [')
            return text[:at] + '\n    ' + planted + text[at:]
        rc, findings = self.check(plant)
        self.assertEqual(len(findings), 1, findings)
        self.assertTrue(findings[0].startswith('T3 staged:"ci/select/map.json"'), findings)
        self.assertNotEqual(rc, 0)


if __name__ == '__main__':
    unittest.main()
