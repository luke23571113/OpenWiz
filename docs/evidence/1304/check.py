"""DS6 (#1304) proof: the contracts' links, cited sections and machine-read parts.

Run from the repository root: python3 -I docs/evidence/1304/check.py <base commit>
Prints one line per problem and exits 1, or prints `ok` and exits 0.
"""
import re, subprocess, sys, posixpath
from pathlib import Path

BASE = sys.argv[1]
problems = []


def at_base(path):
    return subprocess.run(['git', 'show', f'{BASE}:{path}'], capture_output=True, text=True, check=True).stdout


def slug(heading):
    s = re.sub(r'[^\w\- ]', '', heading.strip().lower())
    return s.replace(' ', '-')


def anchors(path):
    return {slug(m) for m in re.findall(r'^#+ (.*)$', Path(path).read_text(), re.M)}


# 1. Links from every contract resolve, with their anchors, and none lands on a file the docs table moves or deletes.
table = Path('docs/cleanup/docs-table.md').read_text()
gone = {p for p, a in re.findall(r'^\| `([^`]+\.md)` \| \d+ \| (\w+) \|', table, re.M) if a in ('move', 'delete')}
gone |= {'STATUS.md'}
PINNED = {'contracts/wizloops-loop.v1.md', 'contracts/wizloops-cloudroom.v1.md'}  # WizLoops copies, hash-pinned
for md in sorted(Path('contracts').glob('*.md')):
    if str(md) in PINNED:
        continue
    for n, line in enumerate(md.read_text().splitlines(), 1):
        for url in re.findall(r'\]\(([^)\s]+)\)', line):
            if re.match(r'[a-z]+:', url) or url.startswith('<'):
                continue  # a web link, or a template's placeholder
            target, _, anchor = url.partition('#')
            path = posixpath.normpath(posixpath.join('contracts', target)) if target else str(md)
            if path in gone:
                problems.append(f'{md}:{n}: links to {path}, which the docs table moves or deletes')
            elif not Path(path).exists():
                problems.append(f'{md}:{n}: broken link {url}')
            elif anchor and path.endswith('.md') and anchor not in anchors(path):
                problems.append(f'{md}:{n}: no heading for #{anchor} in {path}')

# 2. Links from elsewhere into a contract's heading still land.
for src, url in [('contracts/plan.v1.md', 'fleet.v1.md#ticket-states'),
                 ('tools/release/README.md', 'open-development.v1.md#the-privacy-check'),
                 ('docs/github-app.md', 'service.v1.md#the-state-directory')]:
    target, anchor = url.split('#')
    if anchor not in anchors('contracts/' + target):
        problems.append(f'{src}: links to contracts/{url}, which has no such heading')

# 3. Sections code comments cite by name are still headings.
CITED = {
    'fleet.v1.md': ['Reads: where every fact is', 'The rule', "A ticket's agents: the verified chain", 'Needs you',
                    'Unplaced', 'Ticket states', 'Where each field comes from', 'Examples'],
    'review-loops.v2.md': ['The check'],
}
for name, headings in CITED.items():
    have = set(re.findall(r'^#+ (.*)$', Path('contracts/' + name).read_text(), re.M))
    problems += [f'contracts/{name}: code cites "{h}", which is no longer a heading' for h in headings if h not in have]

if '| `## GitHub identity` |' not in Path('contracts/fleet-tick.v1.md').read_text():
    problems.append('contracts/fleet-tick.v1.md: code cites its `## GitHub identity` row, which is gone')

# 4. Machine-read parts stay byte for byte.
def fences(text, lang):
    return re.findall(rf'```{lang}\n(.*?)\n *```', text, re.S)


def config_line(text):
    return [l for l in text.splitlines() if '"openwiz.service-config.v1"' in l and l.startswith('{')]


def next_rows(text):
    return re.findall(r'^\| `[a-z]+` \|[^|]*\| `Next: [^`]*` \|$', text, re.M)


READ = {
    'fleet.v1.md': lambda t: (fences(t, 'json'), t.split('\n## Examples\n')[1:2] and fences(t.split('\n## Examples\n')[1], 'json')),
    'service.v1.md': config_line,
    'review-loops.v1.md': lambda t: (fences(t, 'json'), fences(t, 'md'), next_rows(t)),
    'review-loops.v2.md': lambda t: (fences(t, 'md'), next_rows(t)),
}
for name, part in READ.items():
    path = 'contracts/' + name
    if part(Path(path).read_text()) != part(at_base(path)):
        problems.append(f'{path}: a part the tests read changed')

# 5. Rejected patterns: 2 + 1 review or correction counts.
for md in sorted(Path('contracts').glob('*.md')):
    for n, line in enumerate(md.read_text().splitlines(), 1):
        if re.search(r'\b2 \+ 1\b', line):
            problems.append(f'{md}:{n}: teaches 2 + 1')

print('\n'.join(problems) or 'ok')
sys.exit(1 if problems else 0)
