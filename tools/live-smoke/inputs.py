#!/usr/bin/env python3
"""Assemble the kit's owner-only inputs file on the PC, offline (#772).

Each --records file is an owner-only JSON object of named inputs that the Local
PC agent copied from the existing private records (never from Git). Records
merge; one name with two different values refuses. The kit's own loopback
port is chosen here at run time, a free one that is never 7370, unless a
record names it. The result is one new owner-only file outside any checkout,
for prepare.py. It prints only the port and counts, never a value.
"""
import argparse
import json
from pathlib import Path
import runpy
import socket

HERE = Path(__file__).resolve().parent
prepare = runpy.run_path(str(HERE / 'prepare.py'))
Refused = prepare['Refused']
RESERVED = prepare['smoke']['RESERVED_PORT']


def free_port():
    """One currently free loopback port, never the reserved one."""
    for _ in range(20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        if port != RESERVED:
            return str(port)
    raise Refused('no_port')


def assemble(records, out):
    prepare['private_output'](out)
    if out.exists() or out.is_symlink():
        raise Refused('exists')
    merged = {}
    for path in records:
        for name, value in prepare['read_private'](path, 'records_not_owner_only').items():
            if name in merged and merged[name] != value:
                raise Refused('conflicting_record')
            merged[name] = value
    if 'port' in merged:
        port = merged['port']
        if type(port) is str and port.isdigit() and int(port) == RESERVED:
            raise Refused('reserved_port')
    else:
        merged['port'] = free_port()
    with prepare['write_exclusive'](out, json.dumps(merged, indent=2, sort_keys=True) + '\n'):
        pass
    return {'assembled': True, 'port': merged['port'], 'names': len(merged), 'records': len(records)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--records', action='append', required=True, type=Path,
                        help='absolute owner-only records file (repeatable)')
    parser.add_argument('--out', required=True, type=Path, help='absolute new inputs file, outside any checkout')
    args = parser.parse_args()
    try:
        print(json.dumps(assemble(args.records, args.out)))
        return 0
    except Refused as error:
        print(json.dumps({'assembled': False, 'reason': error.doc['reason']}))
    except (OSError, ValueError, TypeError, prepare['smoke']['Refusal']):
        print(json.dumps({'assembled': False, 'reason': 'invalid_input'}))
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
