#!/usr/bin/env python3
"""Read-only inventory and dry-map validation for #1283; no migration yet.

Only counts, kinds and issue numbers are saved, plus each stays-private PR's
file count and path-list digest. Titles, bodies, comments and file names stay in
memory and are discarded. Public drafts, privacy checking, graph
mapping and resumable apply are still blocked; see README.md.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

SOURCE = 'jparker2006/ClosedWiz'
DEFAULT_TARGET = 'openwizdev/openwiz'
SPEC = 1257
SCHEMA = 'openwiz.ticket-move.inventory.v1'
HEADER = 'kind\tclosedwiz\topenwiz\n'
KINDS = {'issue', 'pull_request'}
IMPORTER = Path(__file__).resolve().parent.parent / 'open-import/import.py'
# The reviewed O14 delivery: carriage.py's PR handoffs and the stays-private classifier.
IMPORTER_SHA256 = '3b624db3ce0e38861245b106027eae4baa68002065e4fedeb79da62317267629'


class Refusal(Exception):
    pass


class InventoryChanged(Refusal):
    def __init__(self, numbers, counts=None):
        self.numbers = numbers
        self.counts = counts
        super().__init__('gh: inventory changed during read; numbers=' + json.dumps(numbers) +
                         '; counts=' + json.dumps(counts))


def require(condition, message):
    if not condition:
        raise Refusal(message)


def number(value):
    return type(value) is int and value > 0


def object_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'repeated JSON key')
        result[key] = value
    return result


def parse_json(text):
    return json.loads(text, object_pairs_hook=object_pairs)


def exact(value, keys, place):
    require(type(value) is dict and set(value) == set(keys), place + ': invalid object')


def records(value, place):
    require(type(value) is list, place + ': not a list')
    last = 0
    for row in value:
        exact(row, ['kind', 'number'], place)
        require(type(row['kind']) is str and row['kind'] in KINDS and number(row['number']),
                place + ': invalid kind or number')
        require(row['number'] > last, place + ': duplicate or unsorted number')
        last = row['number']


def counts(scope, moves):
    return {
        'open_issues': sum(r['kind'] == 'issue' for r in scope),
        'open_pull_requests': sum(r['kind'] == 'pull_request' for r in scope),
        'moving_issues': sum(r['kind'] == 'issue' for r in moves),
        'moving_pull_requests': sum(r['kind'] == 'pull_request' for r in moves),
    }


def classifier():
    """The importer's own private_or_retired, from the exact reviewed bytes (no copied rules)."""
    raw = IMPORTER.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == IMPORTER_SHA256,
            'importer differs from the reviewed O14 delivery')
    module = {'__name__': 'open_import', '__file__': str(IMPORTER)}
    exec(compile(raw, str(IMPORTER), 'exec'), module)
    return module['private_or_retired']


RULING = re.compile(r'https://github\.com/jparker2006/ClosedWiz/(issues|pull)/[1-9][0-9]*#issuecomment-[1-9][0-9]*')


def validate_listed(entries):
    """The reviewed stays-private list: PR number, reason and the ruling's comment URL each."""
    require(type(entries) is list, 'stays-private list: expected a list')
    seen = set()
    for entry in entries:
        exact(entry, ['number', 'reason', 'ruling'], 'stays-private list entry')
        require(number(entry['number']) and entry['number'] not in seen and type(entry['reason']) is str and
                entry['reason'].strip() and type(entry['ruling']) is str and RULING.fullmatch(entry['ruling']),
                'stays-private list: invalid or repeated entry')
        seen.add(entry['number'])
    return sorted(entries, key=lambda entry: entry['number'])


def private_pull(gh, n, is_private, listed):
    """A PR stays private when it is on the reviewed list, or when it has changed files and
    every one, renames' old names included, is private. Returns (kind, record) or (None, None)."""
    files = read(gh, f'/pulls/{n}/files?per_page=100', pages=True)
    names = set()
    for row in files:
        require(type(row) is dict and type(row.get('filename')) is str and row['filename'] and
                type(row.get('previous_filename', '')) is str, f'gh: PR #{n} invalid file list')
        names.update(v for v in [row['filename'], row.get('previous_filename')] if v)
    pull = read(gh, f'/pulls/{n}')
    require(pull.get('number') == n and type(pull.get('changed_files')) is int and
            pull['changed_files'] == len(files), f'gh: PR #{n} file list incomplete')
    listing = ''.join(name + '\n' for name in sorted(names)).encode()
    record = {'number': n, 'changed_files': len(files), 'files_sha256': hashlib.sha256(listing).hexdigest()}
    if n in listed:
        # A reviewed exception binds the reviewed revision too: same paths with new content differ.
        head = pull.get('head', {}).get('sha') if type(pull.get('head')) is dict else None
        require(type(head) is str and re.fullmatch('[0-9a-f]{40}', head), f'gh: PR #{n} invalid head')
        return 'listed', dict(record, head_sha=head, reason=listed[n]['reason'], ruling=listed[n]['ruling'])
    if files and all(is_private(name) for name in names):
        return 'all_private', record
    return None, None


def private_pulls(gh, scope, listed=()):
    is_private = classifier()
    listed = {entry['number']: entry for entry in validate_listed(list(listed))}
    kinds = {r['number']: r['kind'] for r in scope}
    for n in listed:
        require(kinds.get(n) == 'pull_request', f'stays-private list: #{n} is not an open PR')
    pulls = [r['number'] for r in scope if r['kind'] == 'pull_request']
    with ThreadPoolExecutor(max_workers=4) as pool:
        found = list(pool.map(lambda n: private_pull(gh, n, is_private, listed), pulls))
    return ([r for kind, r in found if kind == 'all_private'], [r for kind, r in found if kind == 'listed'])


def private_numbers(inv):
    return {p['number'] for p in inv['private_pulls'] + inv['listed_private_pulls']}


def read_listed(path):
    return [] if path is None else validate_listed(parse_json(path.read_text(encoding='utf-8')))


def listed_entries(inv):
    return [{k: p[k] for k in ['number', 'reason', 'ruling']} for p in inv['listed_private_pulls']]


def migration_excluded(inv):
    """The migration spec and its remaining tickets: the exclusions with excluded-target bindings."""
    return sorted({r['number'] for r in inv['scope']} & ({SPEC} | set(inv['remaining'])))


def validate_inventory(inv):
    exact(inv, ['schema', 'source', 'target', 'migration_spec', 'remaining', 'scope',
                'excluded', 'private_pulls', 'listed_private_pulls', 'counts', 'moves', 'status'], 'inventory')
    require(inv['schema'] == SCHEMA and inv['source'] == SOURCE and
            type(inv['migration_spec']) is int and inv['migration_spec'] == SPEC and
            inv['status'] == 'inventory_only', 'inventory: unsupported contract')
    target(inv['target'])
    for key in ['remaining', 'excluded']:
        seq = inv[key]
        require(type(seq) is list and all(number(n) for n in seq) and
                seq == sorted(set(seq)), 'inventory: invalid ' + key)
    records(inv['scope'], 'inventory scope')
    records(inv['moves'], 'inventory moves')
    kinds = {r['number']: r['kind'] for r in inv['scope']}
    for key, extra in [('private_pulls', []), ('listed_private_pulls', ['head_sha', 'reason', 'ruling'])]:
        private = inv[key]
        require(type(private) is list and [p.get('number') if type(p) is dict else None for p in private] ==
                sorted({p['number'] for p in private}), 'inventory: invalid stays-private PRs')
        for record in private:
            exact(record, ['number', 'changed_files', 'files_sha256', *extra], 'inventory stays-private PR')
            require(kinds.get(record['number']) == 'pull_request' and type(record['changed_files']) is int and
                    record['changed_files'] >= (1 if key == 'private_pulls' else 0) and
                    type(record['files_sha256']) is str and re.fullmatch('[0-9a-f]{64}', record['files_sha256']),
                    'inventory: invalid stays-private PRs')
            require(key == 'private_pulls' or type(record['head_sha']) is str and
                    re.fullmatch('[0-9a-f]{40}', record['head_sha']), 'inventory: invalid stays-private PRs')
    validate_listed(listed_entries(inv))
    require(not {p['number'] for p in inv['private_pulls']} & {p['number'] for p in inv['listed_private_pulls']},
            'inventory: invalid stays-private PRs')
    excluded = sorted(set(migration_excluded(inv)) | private_numbers(inv))
    require(inv['excluded'] == excluded, 'inventory: wrong exclusions')
    moves = [r for r in inv['scope'] if r['number'] not in excluded]
    require(inv['moves'] == moves, 'inventory: incomplete move set')
    expected = counts(inv['scope'], moves)
    exact(inv['counts'], expected, 'inventory counts')
    require(all(type(v) is int for v in inv['counts'].values()) and inv['counts'] == expected,
            'inventory: counts differ')


def target(value):
    require(type(value) is str and re.fullmatch(r'[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+', value)
            and value.lower() != SOURCE.lower(), 'target: expected another OWNER/REPO')


def read(gh, endpoint, pages=False):
    args = [gh, 'api', '--method', 'GET']
    if pages:
        args += ['--paginate', '--slurp']
    args.append('repos/' + SOURCE + endpoint)
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    # Diagnostics may contain private response text; do not echo them.
    require(result.returncode == 0, 'gh: read failed for ' + endpoint.split('?')[0])
    value = parse_json(result.stdout)
    if not pages:
        require(type(value) is dict, 'gh: expected an object')
        return value
    require(type(value) is list and len(value) > 0 and all(type(p) is list for p in value),
            'gh: incomplete paginated read')
    return [row for page in value for row in page]


def read_once(gh):
    repo = read(gh, '')
    issue = read(gh, '/issues/' + str(SPEC))
    expected = repo.get('open_issues_count')
    summary = issue.get('sub_issues_summary')
    require(type(expected) is int and expected >= 0 and type(summary) is dict,
            'gh: missing independent inventory count')
    total = summary.get('total')
    require(type(total) is int and total >= 0, 'gh: missing sub-issue count')
    items = read(gh, '/issues?state=open&per_page=100', pages=True)
    children = read(gh, '/issues/' + str(SPEC) + '/sub_issues?per_page=100', pages=True)
    scope = []
    for item in items:
        require(type(item) is dict and number(item.get('number')), 'gh: invalid issue number')
        scope.append({'kind': 'pull_request' if 'pull_request' in item else 'issue',
                      'number': item['number']})
    scope.sort(key=lambda row: row['number'])
    records(scope, 'gh inventory')
    if len(scope) != expected:
        raise InventoryChanged([], dict(expected=expected, observed=len(scope)))
    remaining = []
    for child in children:
        require(type(child) is dict and number(child.get('number')), 'gh: invalid sub-issue number')
        remaining.append(child['number'])
    require(len(set(remaining)) == len(remaining) == total, 'gh: partial or duplicate sub-issue read')
    return scope, sorted(remaining)


def inventory(gh, public, listed=()):
    target(public)
    scope, remaining = read_once(gh)
    again_scope, again_remaining = read_once(gh)
    if (scope, remaining) != (again_scope, again_remaining):
        before = {r['number']: r['kind'] for r in scope}
        after = {r['number']: r['kind'] for r in again_scope}
        changed = {n for n in set(before) | set(after) if before.get(n) != after.get(n)}
        changed.update(set(remaining) ^ set(again_remaining))
        raise InventoryChanged(sorted(changed))
    private, listed = private_pulls(gh, scope, listed)
    excluded = sorted(({row['number'] for row in scope} & ({SPEC} | set(remaining))) |
                      {p['number'] for p in private + listed})
    moves = [row for row in scope if row['number'] not in excluded]
    result = {'schema': SCHEMA, 'source': SOURCE, 'target': public, 'migration_spec': SPEC,
              'remaining': remaining, 'scope': scope, 'excluded': excluded, 'private_pulls': private,
              'listed_private_pulls': listed,
              'counts': counts(scope, moves), 'moves': moves, 'status': 'inventory_only'}
    validate_inventory(result)
    return result


def planned_map(inv):
    return HEADER + ''.join(f'{r["kind"]}\t{r["number"]}\tplanned\n' for r in inv['moves'])


def check_map(data, inv):
    validate_inventory(inv)
    require(b'\r' not in data and data.endswith(b'\n'), 'map: expected LF and final newline')
    text = data.decode('utf-8')
    require(text.startswith(HEADER), 'map: invalid header')
    rows = []
    for line in text[len(HEADER):].splitlines():
        cells = line.split('\t')
        require(len(cells) == 3 and cells[0] in KINDS and
                re.fullmatch(r'[1-9][0-9]*', cells[1]) and cells[2] == 'planned',
                'map: invalid dry-run row')
        rows.append({'kind': cells[0], 'number': int(cells[1])})
    records(rows, 'map: rows')
    require(rows == inv['moves'], 'map: missing, unexpected or wrong-kind row')
    require(text == planned_map(inv), 'map: noncanonical encoding')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gh', default='gh', help='gh executable (fake in tests)')
    parser.add_argument('--target', help='intended target; no target is contacted')
    parser.add_argument('--out', type=Path, help='new private output folder')
    parser.add_argument('--check-map', type=Path, help='validate an inventory-only dry map')
    parser.add_argument('--inventory', type=Path, help='inventory.json for --check-map')
    parser.add_argument('--stays-private-prs', type=Path, help='reviewed stays-private PR list (JSON)')
    args = parser.parse_args()
    try:
        if args.check_map:
            require(args.inventory and not args.out and not args.target,
                    '--check-map requires only --inventory')
            check_map(args.check_map.read_bytes(), parse_json(args.inventory.read_text()))
            print('pass: inventory-only dry map complete; planned links and public drafts unverified')
        else:
            require(args.out and not args.inventory, '--out is required')
            require(not args.out.exists(), 'output already exists; use a new folder')
            inv = inventory(args.gh, args.target or DEFAULT_TARGET, read_listed(args.stays_private_prs))
            data = planned_map(inv).encode()
            check_map(data, inv)
            args.out.mkdir(parents=True)
            (args.out / 'inventory.json').write_text(json.dumps(inv, indent=2) + '\n', encoding='utf-8')
            (args.out / 'map.dry-run.tsv').write_bytes(data)
            print(json.dumps({'status': inv['status'], 'counts': inv['counts'],
                              'excluded': inv['excluded'], 'public_drafts': 'unverified'}))
    except (Refusal, OSError, ValueError) as error:
        # Do not print an input's contents, gh's response, or file paths.
        message = str(error) if isinstance(error, Refusal) else 'unreadable or invalid input'
        print('refused: ' + message, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
