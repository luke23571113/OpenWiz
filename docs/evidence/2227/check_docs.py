#!/usr/bin/env python3
import re
import sys
from pathlib import Path

FILES = ('README.md', 'docs/install.md')
REQUIRED = re.compile(r'(?i)\bneeds? \[?CloudRoom\b|\brequires? \[?CloudRoom\b|\bCloudRoom\]?(?:\([^)]*\))?(?:,? is)? required'
                      r'|\bYou need \[?CloudRoom|done only when CloudRoom|sets up through (?:it|CloudRoom)')
HOSTS = ('this computer', 'boat.dev', 'CloudRoom')


def paragraphs(text):
    return [p for p in re.split(r'\n\s*\n', text) if p.strip()]


def sentences(paragraph):
    return re.split(r'(?<=[.!?;])\s+', ' '.join(paragraph.split()))


def check(name, text):
    failures = []
    for number, line in enumerate(text.splitlines(), 1):
        if REQUIRED.search(line):
            failures.append(f'{name}:{number}: says CloudRoom is required: {REQUIRED.search(line).group(0)!r}')
        if 'cloudroom.py install' in line and 'only if you pick' not in line:
            failures.append(f'{name}:{number}: runs CloudRoom\'s install without "only if you pick" it')

    before = re.search(r'^## Before you start\n(.*?)^## ', text, re.M | re.S)
    for bullet in re.findall(r'^- .*$', before.group(1), re.M) if before else ():
        if re.match(r'- \*\*[^*]*CloudRoom', bullet) and 'optional' not in bullet:
            failures.append(f'{name}: "Before you start" lists CloudRoom without saying it is optional: {bullet[:60]!r}')

    def hosts_in_order(line):
        flat = ' '.join(line.split())
        at = [flat.find(host) for host in HOSTS]
        return -1 not in at and at == sorted(at) and 'CloudRoom is optional' in flat

    if not any(hosts_in_order(line) for line in text.splitlines()):
        failures.append(f'{name}: no line names this computer, boat.dev and CloudRoom in that order and says '
                        '"CloudRoom is optional"')
    said_010 = said_011 = False
    for paragraph in paragraphs(text):
        for sentence in sentences(paragraph):
            if 'automatic fleet' not in sentence:
                continue
            if '0.1.0' in sentence and 'CloudRoom' in sentence:
                said_010 = True
            if 'this computer' in sentence:
                if '0.1.1' in sentence:
                    said_011 = True
                else:
                    failures.append(f'{name}: puts the automatic fleet on this computer without naming 0.1.1: '
                                    f'{sentence!r}')
    if not said_010:
        failures.append(f'{name}: never says that on 0.1.0 the automatic fleet runs in CloudRoom')
    if not said_011:
        failures.append(f'{name}: never says that 0.1.1 adds the automatic fleet on this computer')
    return failures


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
    failures = []
    for name in FILES:
        failures += check(name, (root / name).read_text(encoding='utf-8'))
    for failure in failures:
        print('FAIL', failure)
    print('ok: README.md and docs/install.md say CloudRoom is optional' if not failures
          else f'{len(failures)} failures')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
