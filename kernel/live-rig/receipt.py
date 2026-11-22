#!/usr/bin/env python3
import argparse
import importlib.machinery
import importlib.util
import json
import os
import re
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.join(HERE, '..', 'driver-kit', 'kit.py')
LISTINGS = os.path.join(HERE, 'listings.json')
REPO = 'openwizdev/OpenWiz'
KEYS = {'host', 'harness', 'model', 'date', 'driver_commit', 'kit_commit', 'outcome', 'skipped', 'kit_exit',
        'stdout', 'seconds'}
CHECKS = ('version', 'start', 'wake', 'stop', 'token')
NOTE = {'start': 'pass start: the run posted builder status note ',
        'wake': 'pass wake: the run edited builder status note '}
TOKEN_LINE = 'pass token: no login or token passed through the driver'
HEX40 = re.compile(r'[0-9a-f]{40}\Z')
DATE = re.compile(r'\d{4}-\d{2}-\d{2}\Z')
LISTING_ID = re.compile(r'[a-z0-9-]{2,40}\Z')
LOGIN = re.compile(r'[A-Za-z0-9](?:-?[A-Za-z0-9]){0,38}\Z')
ONE_LINE = re.compile(r'[^\x00-\x1f\x7f]+\Z')
MACHINE_PATH = re.compile(r'/(?:home|Users|root|private|var/folders)/|\b[A-Za-z]:\\')


class Refused(Exception):
    pass


def kit():
    spec = importlib.util.spec_from_loader('kit', importlib.machinery.SourceFileLoader('kit', KIT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def checked(rec):
    if not isinstance(rec, dict) or set(rec) != KEYS:
        raise Refused('the run record does not have exactly the run record keys')
    if rec['outcome'] == 'skipped':
        raise Refused('the run was skipped: %s' % rec['skipped'])
    if rec['outcome'] != 'ran':
        raise Refused('the run record outcome is not ran')
    if rec['kit_exit'] != 0:
        raise Refused('kit.py exited %s, not 0' % rec['kit_exit'])
    for key in ('host', 'harness', 'model'):
        if not isinstance(rec[key], str) or not ONE_LINE.match(rec[key]):
            raise Refused('the run record %s is not one line' % key)
    for key in ('driver_commit', 'kit_commit'):
        if not isinstance(rec[key], str) or not HEX40.match(rec[key]):
            raise Refused('the run record %s is not a 40-hex lowercase commit' % key)
    if not isinstance(rec['date'], str) or not DATE.match(rec['date']):
        raise Refused('the run record date is not YYYY-MM-DD')
    if not isinstance(rec['stdout'], str):
        raise Refused('the run record has no kit stdout')
    return rec


def kit_lines(stdout):
    lines = stdout.split('\n')
    if lines[-1] != '':
        raise Refused("kit.py's stdout does not end in a newline")
    lines = lines[:-1]
    if len(lines) != 5:
        raise Refused("kit.py's stdout has %d lines, not its five" % len(lines))
    names = [re.match(r'(?:pass|fail) (\w+): ', l) for l in lines]
    if None in names:
        raise Refused("kit.py's stdout holds a line that is not a check line")
    if sorted(m.group(1) for m in names) != sorted(CHECKS):
        raise Refused("kit.py's stdout does not name its five checks once each")
    if tuple(m.group(1) for m in names) != CHECKS:
        raise Refused("kit.py's lines are out of order; the order is %s" % ', '.join(CHECKS))
    passed = sum(l.startswith('pass ') for l in lines)
    if passed != 5:
        raise Refused('the run is %d of 5 pass, not 5 of 5' % passed)
    out = []
    for name, line in zip(CHECKS, lines):
        if name in NOTE:
            if not re.fullmatch(re.escape(NOTE[name]) + r'[0-9]+', line):
                raise Refused("the %s line is not kit.py's, ending in its status note's id" % name)
            line = NOTE[name] + '<note>'
        if name == 'token' and line != TOKEN_LINE:
            raise Refused("the token line is not kit.py's only passing token line")
        out.append(line)
    return out


def listing_for(rec, listing):
    with open(LISTINGS) as f:
        listings = json.load(f)
    if rec['host'] not in listings:
        raise Refused('host %s is not in listings.json' % rec['host'])
    if listing == listings[rec['host']]:
        return listing
    harness = '%s/%s' % (rec['host'], rec['harness'])
    if harness not in listings:
        raise Refused('%s is not %s\'s driver listing, and harness %s is not in listings.json'
                      % (listing, rec['host'], harness))
    if listing != listings[harness]:
        raise Refused('%s is neither %s nor %s in listings.json' % (listing, listings[rec['host']], listings[harness]))
    return listing


def contract_format_line(n, line):
    return n == 13 and line == TOKEN_LINE


def receipt(rec, listing, run_by):
    if not LISTING_ID.match(listing):
        raise Refused('--listing %s is not a listing id' % listing)
    if not LOGIN.match(run_by):
        raise Refused('--run-by is not a GitHub login')
    rec = checked(rec)
    body = kit_lines(rec['stdout'])
    listing = listing_for(rec, listing)
    lines = ['# listing: ' + listing, '# host: ' + rec['host'],
             '# driver: %s@%s' % (REPO, rec['driver_commit']), '# kit: %s@%s' % (REPO, rec['kit_commit']),
             '# harness: ' + rec['harness'], '# model: ' + rec['model'], '# date: ' + rec['date'],
             '# run by: ' + run_by] + body + ['Result: 5 of 5 pass']
    k = kit()
    for n, line in enumerate(lines, 1):
        if MACHINE_PATH.search(line):
            raise Refused('line %d holds a machine path' % n)
        if not contract_format_line(n, line) and k.holds_credential(line):
            raise Refused('line %d holds a credential shape' % n)
    path = os.path.join('receipts', listing, '%s-%s.txt' % (rec['date'], rec['driver_commit'][:12]))
    return path, ''.join(l + '\n' for l in lines)


def main(argv):
    ap = argparse.ArgumentParser(prog='receipt.py')
    ap.add_argument('record')
    ap.add_argument('--listing', required=True)
    ap.add_argument('--run-by', required=True)
    ap.add_argument('-o', dest='out', required=True)
    a = ap.parse_args(argv)
    try:
        try:
            with open(a.record) as f:
                rec = json.load(f)
        except (OSError, ValueError):
            raise Refused('the run record is not readable JSON')
        rel, text = receipt(rec, a.listing, a.run_by)
        path = os.path.join(a.out, rel)
        if os.path.lexists(path):
            raise Refused('a receipt is already at %s; the first one is kept' % rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            raise Refused('a receipt is already at %s; the first one is kept' % rel)
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
    except Refused as e:
        print('receipt.py: %s' % e, file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
