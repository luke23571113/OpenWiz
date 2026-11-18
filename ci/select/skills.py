#!/usr/bin/env python3
"""Run CI's selected skill suites (#433). Unknown or empty selection runs all.

python3 -I ci/select/skills.py 'triage where-are-we'   # or all / none
The order of the full run is the existing CI order. No shell interpolation.
"""
import subprocess
import sys

SUITES = {
    # #555: the skills' own suites run in WizSkills (check/run.py). ClosedWiz
    # keeps one lane for its own checks over the installed launch-fleet.
    'launch-fleet': [['python3', '-I', 'tools/review-relay/test_inbox.py']],
}
# #743: suites CI runs as their own job, split across members by
# ci/shard/lanes.py; the skills job's matrix runs the rest.
SHARDED = ('launch-fleet',)


def valid(value):
    if value in ('all', 'none'):
        return True
    names = value.split(' ')
    return bool(names) and len(set(names)) == len(names) and all(n in SUITES for n in names)


def selected(value):
    if not valid(value) or value == 'all':
        return list(SUITES)
    return [] if value == 'none' else [n for n in SUITES if n in value.split(' ')]


def run(value):
    names = selected(value)
    print('skill selection: ' + (' '.join(names) if names else 'none'), flush=True)
    for name in names:
        for command in SUITES[name]:
            code = subprocess.run(command).returncode
            if code:
                return code if code > 0 else 1
    return 0


if __name__ == '__main__':
    sys.exit(run(sys.argv[1] if len(sys.argv) == 2 else 'all'))
