#!/usr/bin/env python3
"""K16 step requirements from the same trusted map and diff as test selection.

The web export and its build went with the web view (#1264), so no step
builds or reads it. Non-plain runs and errors use FULL in job.py.
"""
import os
import subprocess

from skills import SUITES

FLAGS = ('lint-rust', 'build-site', 'image-skills')


def plan(tests, changes, known, root, classify=True):
    paths = [p for _, p in changes]
    folders = {p.split('/')[1] for p in paths if p.startswith('skills/') and len(p.split('/')) > 2}
    skill_tests = sorted(folders & set(SUITES))

    rust_lint = any(p.endswith('.rs') or p.startswith('crates/') or p in ('Cargo.toml', 'Cargo.lock', 'tests/Cargo.toml')
                    for p in paths)
    if classify:
        proc = subprocess.run(['sh', os.path.join(root, '.github/actions/docs-only/classify.sh')],
                              input='\n'.join(paths) + '\n', capture_output=True, text=True, check=True,
                              env=dict(os.environ, CLASSIFY_STEP='site'))
        if proc.stdout.strip() not in ('none', 'web-build', 'web-build web-test'):
            raise ValueError('no site decision from classify.sh')
        site_build = 'web-test' in proc.stdout.split()
    else:
        site_build = any(p.startswith('tools/release/') for p in paths)
    values = (rust_lint, site_build, 'image' in skill_tests)
    return {**{k: 'true' if v else 'false' for k, v in zip(FLAGS, values)},
            'skill-tests': ' '.join(skill_tests) if skill_tests else 'none'}
