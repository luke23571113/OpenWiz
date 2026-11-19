#!/usr/bin/env python3
"""Build the selector's map from one traced run's records (#432, K15).

  python3 -I ci/select/map.py OUT.json --commit SHA --root DIR RECORDS...

RECORDS are the folders trace.py wrote (the rust lane). The map (pick.py's
MAP_SCHEMA) holds, for each test traced cleanly, the files it read or looked
for and the folders it listed, and the commit they were traced at. A test that failed under strace, or touched something
resolve.py can't account for, is left out, so the selector always runs it.

It refuses (exit 1, no map) when a test listed at DIR (units.py) has no
record, or a record names a test that isn't listed: a map from a run that
didn't trace every test would hide them.
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pick  # noqa: E402
import units as units_mod  # noqa: E402


def build(records, commit, listed):
    units, left_out = {}, {}
    for uid in sorted(listed):
        if uid not in records:
            raise SystemExit(f'map: {uid} has no record: every test must be traced')
    for uid, rec in sorted(records.items()):
        if uid not in listed:
            raise SystemExit(f'map: a record for {uid}, which is not a test here')
        if not rec.get('traced'):
            left_out[uid] = rec.get('untraced', 'not traced')
            continue
        files, dirs = set(rec['files']), set(rec['dirs'])
        if not files:
            left_out[uid] = 'read no repository file'
            continue
        units[uid] = {'files': sorted(files), 'dirs': sorted(dirs), 'seconds': rec['seconds']}
    mp = {'schema': pick.MAP_SCHEMA, 'commit': commit, 'units': units}
    pick.check_map(mp)
    return mp, left_out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--commit', required=True)
    ap.add_argument('--root', default='.')
    ap.add_argument('records', nargs='+')
    args = ap.parse_args(argv)
    records = {}
    for folder in args.records:
        for path in sorted(glob.glob(os.path.join(folder, '*.json'))):
            with open(path) as f:
                rec = pick.strict_json(f.read())
            uid = rec.pop('test')
            if uid in records:
                raise SystemExit(f'map: two records for {uid}')
            records[uid] = rec
    mp, left_out = build(records, args.commit, set(units_mod.list_units(args.root)))
    with open(args.out, 'w') as f:
        json.dump(mp, f, indent=1, sort_keys=True)
        f.write('\n')
    print(f'map: {len(mp["units"])} tests mapped at {args.commit}, {len(left_out)} left out (always run)')
    for uid, why in sorted(left_out.items()):
        print(f'map: left out {uid}: {why}')


if __name__ == '__main__':
    main(sys.argv[1:])
