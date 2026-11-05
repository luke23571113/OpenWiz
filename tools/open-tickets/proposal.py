#!/usr/bin/env python3
"""Build move.py's private proposal from a completed, checked collect.py dry run.

Read-only except its new private output folder: it rereads the source once,
refuses any drift from the dry run, reads the destination milestones, and
prepares each moving PR's O14 patch handoff with `import.py patch`. It never
applies, publishes or contacts the target with a write.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from plan import Refusal, InventoryChanged, require, inventory, number, parse_json, migration_excluded, listed_entries, private_numbers  # noqa: E402
from graph import text  # noqa: E402
from source import pages  # noqa: E402
from collect import SnapshotChanged, check_saved, collect_source, digest, digest_string  # noqa: E402
from carriage import IMPORTER_SHA256, sha  # noqa: E402
from text import CHECKER  # noqa: E402


def load_dry_run(args):
    """The dry run must pass collect.py --check unchanged; returns its saved records."""
    check_saved(SimpleNamespace(out=args.dry_run, checker=args.checker, literals=args.literals))
    read = lambda name: parse_json((args.dry_run / name).read_text(encoding='utf-8'))  # noqa: E731
    inv, report, provenance = read('inventory.json'), read('report.json'), read('provenance.json')
    require(report['status'] == 'planned', 'dry-run: not a complete planned run')
    return inv, report, provenance


def fresh_source(args, inv, provenance):
    """One bound reread, through the collector's own helpers; any difference refuses."""
    records = {n: {k: v for k, v in proof.items() if k != 'state'} for n, proof in provenance['closures'].items()}
    try:
        current = inventory(args.gh, inv['target'], listed_entries(inv))
    except InventoryChanged as error:
        raise Refusal('drift: source inventory changing; numbers=' + json.dumps(error.numbers)) from None
    scope_drift(inv, current)
    try:
        source, merges, closures, approvals, exclusions = collect_source(args.gh, current, records)
    except SnapshotChanged as error:
        raise Refusal('drift: ' + json.dumps(error.changes)) from None
    scope_drift(inv, inventory(args.gh, inv['target'], listed_entries(inv)))
    saved = provenance['source_nodes']
    now = {str(n): digest(node) for n, node in source.nodes.items()}
    changed = sorted(int(n) for n in set(saved) | set(now) if saved.get(n) != now.get(n))
    sections = [name for name, value in [('merges', merges), ('closures', closures), ('approvals', approvals),
                ('excluded_targets', exclusions)] if value != provenance[name]]
    require(not changed and not sections, 'drift: source differs from the dry run; numbers=' +
            json.dumps(changed) + '; sections=' + json.dumps(sections))
    require(digest(source.nodes) == provenance['source_sha256'], 'drift: source digest differs from the dry run')
    return source


def scope_drift(saved, current):
    require(digest(current) == digest(saved), 'drift: open scope differs from the dry run; numbers=' + json.dumps(
        sorted({r['number'] for r in saved['scope']} ^ {r['number'] for r in current['scope']} |
               set(saved['remaining']) ^ set(current['remaining']) |
               private_numbers(saved) ^ private_numbers(current))))


def destination_milestones(args, target, titles):
    rows = pages(args.gh, f'repos/{target}/milestones?state=all&per_page=100')
    found = {}
    for row in rows:
        require(type(row) is dict and text(row.get('title')) and number(row.get('number')),
                'destination: invalid milestone')
        found.setdefault(row['title'], []).append(row['number'])
    result = []
    for title in sorted(titles):
        require(len(found.get(title, [])) == 1, 'destination: milestone missing or ambiguous: ' + json.dumps(title))
        result.append({'title': title, 'number': found[title][0]})
    return result


def graph(inv, source, provenance, milestones):
    moving = {row['number'] for row in inv['moves']}
    items = []
    for n in sorted(moving):
        item = dict(source.nodes[n]['item'])
        item['labels'] = sorted(item['labels'])
        items.append(item)
    # Closed prerequisites are state-bearing references only: their own links are not moved.
    states = {int(n): 'merged' for n in provenance['merges']}
    states.update({int(n): proof['state'] for n, proof in provenance['closures'].items()})
    for n in sorted(states):
        item = source.nodes[n]['item']
        items.append(dict(item, labels=sorted(item['labels']), parent=None, blockers=[], state=states[n]))
    # Excluded issues stay on ClosedWiz: references only, so a HELD blocker resolves to
    # its bound private original (move.py carries it as that link, never an edge).
    for n in migration_excluded(inv):  # stays-private PRs need no item: nothing links to them
        item = source.nodes[n]['item']
        items.append(dict(item, labels=sorted(item['labels']), parent=None, blockers=[]))
    return dict(items=sorted(items, key=lambda i: i['number']), milestones=milestones, exclude=inv['excluded'])


def git_main(repo):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    result = subprocess.run(['git', '-C', str(repo), 'rev-parse', '--verify', '-q', 'refs/heads/main^{commit}'],
                            capture_output=True, text=True, env=env)
    require(result.returncode == 0, 'destination: no local main')
    return result.stdout.strip()


def handoff(args, n, node, folder):
    rng = node['range']
    result = subprocess.run([sys.executable, '-I', str(args.importer), 'patch', '--source', str(args.source_repo),
                             '--source-base', rng['source_base'], '--commit', rng['source_head'],
                             '--destination', str(args.destination), '--checker', str(args.checker),
                             '--literals', str(args.literals), '--output', str(folder)],
                            capture_output=True, text=True)
    # Never echo O14's diagnostics: they may name private paths.
    require(result.returncode == 0, f'PR #{n}: O14 patch refused')
    value = parse_json(result.stdout)
    require(type(value) is dict and value.get('status') == 'checked' and
            value.get('destination_base') == args.destination_main and digest_string(value.get('binding_sha256')) and
            sha((folder / 'binding.json').read_bytes()) == value['binding_sha256'],
            f'PR #{n}: incomplete O14 patch read-back')
    return dict(source_base=rng['source_base'], observed_base=rng['observed_base'], source_head=rng['source_head'],
                destination=str(args.destination), patch_dir=str(folder), binding_sha256=value['binding_sha256'])


def self_check(args, plan):
    """The proposal must pass move.py's own default dry mode (no effects, no state)."""
    from move import Mover
    Mover(SimpleNamespace(plan=plan, state_dir=args.out / 'unused-state', map_out=args.out / 'unused-map.tsv',
                          checker=args.checker, literals=args.literals, gh=args.gh, importer=args.importer,
                          git='git'), parse_json(plan.read_text(encoding='utf-8')))


def inside(path, root):
    path, root = path.resolve(), root.resolve()
    return path == root or root in path.parents


def in_work_tree(path):
    """Fail closed: true unless Git and a .git walk both say the nearest existing ancestor is in no repository."""
    path = path.absolute()
    existing = next(p for p in [path, *path.parents] if p.exists())
    if any((p / '.git').exists() or (p / '.git').is_symlink() for p in [existing.resolve(), *existing.resolve().parents]):
        return True
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(LC_ALL='C', GIT_DISCOVERY_ACROSS_FILESYSTEM='1')
    try:
        result = subprocess.run(['git', '-C', str(existing), 'rev-parse', '--git-dir'],
                                capture_output=True, text=True, env=env)
    except OSError:
        return True
    return not (result.returncode == 128 and 'not a git repository' in result.stderr)


def build(args):
    os.umask(0o077)
    require(not args.out.exists(), 'output already exists; use a new folder')
    require(not inside(args.out, args.destination) and not inside(args.out, args.source_repo) and
            not inside(args.out, Path(__file__).resolve().parents[2]) and not in_work_tree(args.out),
            'output: inside a repository or public tree')
    require(sha(args.importer.read_bytes()) == IMPORTER_SHA256, 'importer differs from reviewed O14 delivery')
    datetime.date.fromisoformat(args.date)
    inv, report, provenance = load_dry_run(args)
    require(git_main(args.destination) == args.destination_main, 'destination: main is not the imported main')
    source = fresh_source(args, inv, provenance)
    titles = {source.nodes[r['number']]['item']['milestone'] for r in inv['moves']} - {None}
    proposal = dict(graph=graph(inv, source, provenance, destination_milestones(args, inv['target'], titles)),
                    bodies={str(r['number']): source.nodes[r['number']]['body'] for r in inv['moves']},
                    target=inv['target'], date=args.date,
                    approvals={n: dict(comment=p['comment'], fingerprint=p['fingerprint'])
                               for n, p in provenance['approvals'].items()},
                    closures=provenance['closures'], merges=provenance['merges'],
                    excluded_targets=provenance['excluded_targets'], stays_private_prs=inv['listed_private_pulls'], pulls={})
    args.out.mkdir(mode=0o700, parents=True)
    try:
        (args.out / 'patches').mkdir(mode=0o700)
        for row in inv['moves']:
            if row['kind'] == 'pull_request':
                n = row['number']
                proposal['pulls'][str(n)] = handoff(args, n, source.nodes[n], args.out / 'patches' / str(n))
        plan = args.out / 'proposal.json'
        plan.write_text(json.dumps(proposal, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        os.chmod(plan, 0o600)
        self_check(args, plan)
    except BaseException:
        remove(args.out)
        raise
    return dict(status='proposal', proposal_sha256=sha(plan.read_bytes()), counts=inv['counts'],
                pulls=len(proposal['pulls']), dry_run_report_sha256=sha((args.dry_run / 'report.json').read_bytes()),
                target=inv['target'], applied=False,
                # Carried as the original approval; apply's currentness read still refuses these.
                stale_approvals=[row['closedwiz'] for row in report['stale_approvals']],
                held_prerequisites=[row['closedwiz'] for row in report['held_prerequisites']],
                private_pulls=sorted(p['number'] for p in inv['private_pulls'] + inv['listed_private_pulls']))


def remove(folder):
    # Only this run's new folder: no partial proposal is left to be mistaken for a reviewed one.
    for path in sorted(folder.rglob('*'), key=lambda p: len(p.parts), reverse=True):
        path.rmdir() if path.is_dir() and not path.is_symlink() else path.unlink()
    folder.rmdir()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dry-run', type=Path, required=True, help='completed collect.py --out folder (passes --check)')
    p.add_argument('--out', type=Path, required=True, help='new private folder, outside every repository')
    p.add_argument('--checker', type=Path, default=CHECKER)
    p.add_argument('--literals', type=Path, required=True)
    p.add_argument('--gh', default='gh')
    p.add_argument('--importer', type=Path, default=Path(__file__).resolve().parent.parent / 'open-import/import.py')
    p.add_argument('--source-repo', type=Path, required=True, help='local ClosedWiz clone holding every PR range')
    p.add_argument('--destination', type=Path, required=True, help='local OpenWiz clone at the imported main')
    p.add_argument('--destination-main', required=True, help='the imported main commit the clone must be at')
    p.add_argument('--date', default=datetime.datetime.now(datetime.timezone.utc).date().isoformat(),
                   help='ISO date for private-record comments (default: today, UTC)')
    args = p.parse_args()
    try:
        print(json.dumps(build(args)))
    except (Refusal, OSError, ValueError) as error:
        print('refused: ' + (str(error) if isinstance(error, Refusal) else 'unreadable or invalid input'),
              file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
