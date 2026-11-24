#!/usr/bin/env python3
"""The builder before and after #3084 list the same runtime/adapters and runtime/kernel files for one source
(usage: same_list.py BEFORE_COMMIT SOURCE_COMMIT). Reads git only; prints both lists' digests."""
import hashlib
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/release'))
import build_products

before, source = sys.argv[1:]
old = build_products.git(ROOT, 'show', f'{before}:tools/release/build_products.py').decode()
scope = {}
for name in ('DRIVERS', 'KEY_CHECK_FILES', 'KIT'):
    exec(re.search(rf'^{name} = .*?(?=^\S|\Z)', old, re.M | re.S).group(0), scope)
tracked = set(build_products.git(ROOT, 'ls-tree', '-r', '-z', '--name-only', source, '--', 'adapters', 'kernel')
              .decode().split('\0'))
was = [f'adapters/{host}/{name}' for host in scope['DRIVERS'] if f'adapters/{host}/driver' in tracked
       for name in ('driver', 'schema.json') + scope['KEY_CHECK_FILES'].get(host, ())] + scope['KIT']
now = build_products.drivers(ROOT, source) + build_products.KIT
for label, names in (('before', was), ('after', now)):
    text = ''.join(f'{name}\n' for name in sorted(names))
    print(label, len(names), hashlib.sha256(text.encode()).hexdigest())
print('missing after:', sorted(set(was) - set(now)))
print('new after:', sorted(set(now) - set(was)))
sys.exit(sorted(was) != sorted(now))
