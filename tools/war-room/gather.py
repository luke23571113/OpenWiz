#!/usr/bin/env python3
"""WR10: gather the real War room sources into one pinned WR2 selection. Reads only.

  python3 -I gather.py --remote URL --repo OWNER/REPO --run-url URL --out DIR [--data-remote URL]
      [--pool LABEL ...] [--journeys FILE --cohort FILE] [--answer-time FILE] [--stage DIR]

Before a publish: one source root and `DIR/selection.json` in WR2's
`sources.select` form, each artifact pinned by sha256, observed time and
evidence. The `board` branch is fetched, never pushed;
WR8's current CI/throughput and the merged cohort's journeys come from the
existing read-only `gh` readers. A source that cannot be read gives only its
own card a precise reason; a privacy hit anywhere in the root refuses the
whole gather, so nothing is selected and nothing is published. WRD1 adds the
three v2 health providers (main CI, CI queue, stage health) and the detailed
stage waits, from one pinned stage evidence set (contract.v2.md).
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import activity  # noqa: E402
import answer_time as wr5  # noqa: E402
import collect_factory  # noqa: E402
import cost  # noqa: E402
import health  # noqa: E402
import publish  # noqa: E402
import rework  # noqa: E402
import sources  # noqa: E402
import stage_waits  # noqa: E402
import suite  # noqa: E402

B, M, J = activity.B, activity.M, rework.J
POOLS = ('closedwiz-pc', 'ubuntu-24.04')
LITERAL = re.compile(r'"(?:[^"\\]|\\.)*"')  # one JSON string literal
COHORT_HOURS = 6  # the latest complete UTC hours searched for a merged cohort
ISSUE = 'https://github.com/%s/issues/2432'
LEVEL = ('A level at the board sample time (the latest sample of this fixed-PST day so far, the board\'s daily rule), '
         'not an aggregate over the window; board history completeness is unknown.')
COUNTS = (('open_approved', 'Open approved tickets'), ('can_start', 'Tickets that can start'),
          ('file_links', 'File links'), ('unlabelled_links', 'Unlabelled links'),
          ('ready_stock', 'Ready stock'), ('builders_running', 'Builders running'))
REASONS = {
    'board': 'Board history unavailable: history.jsonl on the board branch is missing, unreadable or invalid; '
             'prerequisite: the hourly board publish (.github/workflows/board.yml) writing a valid history row.',
    'credits': 'Credits unavailable: credits.jsonl on the board branch is missing, unreadable or invalid; '
               'prerequisite: the CloudRoom credit sampler appending valid samples (board.py sample).',
    'ci_bench': 'CI bench retired (#827): its daily publish no longer runs, so no point is read; '
                'PRs an hour against the baseline is drawn from a collector snapshot (charts/build.py --snapshot).',
    'activity': 'Current CI and throughput unavailable: the read-only gh reads of ci.yml runs/jobs and merged PRs failed; '
                'prerequisite: gh with actions, issues and pull-requests read access (WR8 activity.project).',
    'journey': 'Ticket journeys unavailable: journey.py collect over the merged cohort failed or found no cohort; '
               'prerequisite: read-only gh access and a merged PR closing a ticket in the latest complete UTC hours.',
    'rework': 'Rework unavailable: it needs the merged cohort\'s ticket journeys (journey.py collect), which are unavailable; '
              'prerequisite: read-only gh access and a merged PR closing a ticket in the latest complete UTC hours.',
    'answer_time': 'Answer time unavailable: the supplied answer_time projection is unreadable or invalid; '
                   'prerequisite: WR5 answer_time.project output over source-linked recorded requests.',
    'cost': 'Cost readiness unavailable: the journeys could not be read (WR4 cost.project); '
            'prerequisite: ticket journeys from journey.py collect.',
    'main_ci': 'Main CI unavailable: the read of the main head and its ci.yml push runs could not be selected; '
               'prerequisite: read-only gh access to the branch and its Actions runs (health.main_ci).',
    'ci_queue': 'CI queue unavailable: the current ci.yml run/job read could not be selected; '
                'prerequisite: read-only gh access to Actions runs and jobs (health.ci_queue).',
    'stage_waits': 'Stage waits unavailable: journey.py collect --stage-waits over the open approved and merged '
                   'tickets failed or found none, or its sidecar was refused; prerequisite: read-only gh access and '
                   "the board graph's open approved tickets (stage_waits.project).",
    'stage_health': 'Stage health unavailable: journey.py collect --stage-waits over the open approved and merged '
                    'tickets failed or found none, or its sidecar was refused; prerequisite: read-only gh access and '
                    "the board graph's open approved tickets (health.stage_health).",
    'stage_coverage': 'Stage evidence not collected: the board graph\'s open approved tickets or the merged PR pages '
                      'could not be read, so unfinished approved work cannot be enumerated and no partial stage cohort '
                      'is shown; prerequisite: a valid board-wide graph.json of this repository on the board branch '
                      '(source kind board) and complete PR pages.',
}
LIMITS = sources.ROOT / 'tools/war-room/limits.conf'  # TL1's one settings source


class Fail(Exception):
    pass


def utc(at):
    return suite._time(at).replace(tzinfo=timezone.utc)


def iso(value):
    return value.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def now():
    return iso(datetime.now(timezone.utc))


def git(work, *args):
    out = subprocess.run(['git', '-C', str(work), *args], capture_output=True)
    if out.returncode:
        # Never echo an auth-bearing remote URL or git's stderr.
        raise OSError('git %s failed' % args[0])
    return out.stdout


def branch(work, remote, name):
    """(files, commit, commit time) of one branch, fetched read-only; None if it is absent."""
    if subprocess.run(['git', '-C', str(work), 'fetch', '-q', '--depth=1', '--no-tags', remote,
                       'refs/heads/%s:refs/gather/%s' % (name, name)], capture_output=True).returncode:
        return None
    ref = 'refs/gather/' + name
    commit = git(work, 'rev-parse', ref).decode().strip()
    at = iso(datetime.fromtimestamp(int(git(work, 'log', '-1', '--format=%ct', ref).decode()), timezone.utc))
    names = [n for n in git(work, 'ls-tree', '-r', '-z', '--name-only', ref).decode().split('\0') if n]
    return {n: (lambda n=n: git(work, 'show', ref + ':' + n)) for n in names}, commit, at


class Root:
    """The gathered source root and its selection, one entry a slot."""

    def __init__(self, path, repo, run_url, at):
        self.path, self.repo, self.run_url, self.at = path, repo, run_url, at
        self.selection = []

    def write(self, rel, data):
        scan_bytes(data)  # before anything else reads it: a privacy hit refuses the whole gather
        target = self.path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    def select(self, kind, slot, rel, data, observed_at, evidence):
        entry = {'kind': kind, 'slot': slot, 'path': rel, 'sha256': self.write(rel, data),
                 'observed_at': observed_at, 'evidence': evidence}
        # The same reader the publish runs, per source: one that fails greys only its own card.
        try:
            failed = sources.select(self.path, [entry], self.at)[0] == sources._failed(slot, None, self.at)
        except ValueError:  # a selection entry WR2 refuses outright
            failed = True
        if failed:
            (self.path / rel).unlink()
            return self.missing(slot, REASONS[slot])
        self.selection.append(entry)
        return entry

    def projected(self, provider, observed_at=None):
        slot = provider['slot']
        metrics = provider.get('metrics') if type(provider.get('metrics')) is list else []
        times = [m['observed_at'] for m in metrics if type(m) is dict and type(m.get('observed_at')) is str]
        observed = observed_at or (max(times) if times else self.at)
        data = (json.dumps(provider, sort_keys=True, indent=1) + '\n').encode()
        return self.select('projected', slot, slot + '/provider.json', data, observed, [self.run_url])

    def missing(self, slot, reason):
        provider = {'slot': slot, 'state': 'unavailable', 'prerequisites': [reason],
                    'observations' if slot in sources.HEALTH_SLOTS else 'metrics': []}
        data = (json.dumps(provider, sort_keys=True) + '\n').encode()
        entry = {'kind': 'projected', 'slot': slot, 'path': 'missing/%s.json' % slot,
                 'sha256': self.write('missing/%s.json' % slot, data), 'observed_at': self.at,
                 'evidence': [ISSUE % self.repo]}
        self.selection.append(entry)
        return None


def board_provider(s, raw, graph_raw, graph_sha):
    """The latest board history row as partial counts, in the board's own daily window."""
    sources.board_history(s, raw)  # the row validator, first
    rows = [sources.board_strict(line) for line in raw.decode('utf-8').splitlines() if line.strip()]
    row = max(enumerate(rows), key=lambda pair: (pair[1]['at'], pair[0]))[1]
    since = utc(row['day'] + 'T08:00:00Z')
    until = min(utc(s['observed_at']), since + timedelta(days=1))
    suite.require(since <= utc(row['at']) < until, 'board sample outside its day')
    span = sources.window(iso(since), iso(until), 'PST-fixed-UTC-08:00')
    sample = ['board-sample-' + row['at'].lower()]
    items = [sources.metric(s, row['schema'], key.replace('_', '-'), 'board', label + ' (board sample ' + row['at'] + ')',
                            row[key], 'count', span, state='partial', prerequisites=[LEVEL], identities=sample,
                            statistic='count') for key, label in COUNTS]
    # The ratios need the ticket identities behind them: only a graph of the same read has them.
    tickets, gap = None, 'Ticket identities from graph.json on the board branch, read at ' + row['at'] + ', are required.'
    if graph_raw is not None:
        try:
            graph = suite._decode(graph_raw.decode('utf-8'))
            report = sources.board_check_links(graph)
            measures = sources.board_measures(graph, report)
            if graph['read_at'] == row['at'] and all(measures[k] == row[k] for k in sources.BOARD_MEASURE_KEYS):
                tickets = sources.board_open_approved(graph)
        except (ValueError, KeyError, TypeError, UnicodeError):
            pass
    for key, label, unit, statistic, rounding, num, den in (
            ('startable_percent', 'Startable percent', 'percent', 'proportion', 'half_up_0', 'can_start', None),
            ('fed_ratio', 'Fed ratio (ready stock per builder running)', 'ratio', 'ratio', 'half_up_1', 'ready_stock', 'building')):
        ids = None
        if tickets is not None:
            chosen = tickets if den is None else [t for t in tickets if sources.board_state(t) == den]
            ids = ['ticket-%d' % t['number'] for t in chosen]
        gaps = [LEVEL] + ([] if ids is not None else [gap])
        if ids is not None and not ids:
            gaps.append('No builders running at this sample: the source ratio is undefined, never zero.'
                        if den else 'No open approved tickets at this sample: the source percent is undefined.')
        value = row[key] if ids else None
        item = sources.metric(s, row['schema'], key.replace('_', '-'), 'board', label + ' (board sample ' + row['at'] + ')',
                              value, unit, span, state='partial', prerequisites=gaps, identities=ids or [],
                              statistic=statistic)
        item['rounding'] = rounding
        if ids:
            item['sample'].update(numerator=row[num], denominator=len(ids))
            if graph_sha:
                item['source'] = {'path': 'board/graph.json', 'schema': row['schema'], 'sha256': graph_sha}
        items.append(item)
    return sources.provider('board', items, [LEVEL])


def merged_cohort(prs, started):
    """The latest complete UTC hours (up to COHORT_HOURS) holding a merged PR that closes a ticket."""
    hour = utc(started).replace(minute=0, second=0)
    for k in range(1, COHORT_HOURS + 1):
        since = hour - timedelta(hours=k)
        merged = sorted(n for n, p in prs.items() if p['merged'] is not None
                        and since <= p['merged'].replace(tzinfo=timezone.utc) < hour)
        if any(prs[n]['tickets'] for n in merged):
            return {'cohort': 'merged-utc-%s-%dh' % (since.strftime('%Y%m%d%H'), k), 'merged_prs': merged,
                    'since': iso(since), 'until': iso(hour)}
    return None


ACTIVE = ('in_progress', 'queued', 'waiting', 'pending', 'requested')


def current_runs(repo, since, until, read):
    """WR8's run reader, bounded: ci.yml's whole run history (over the API's 1000-item limit here)
    is listed as its active runs, one status at a time, and the completed runs created in
    [since, until], the only runs WR8's current_activity uses. Each listing keeps bench.pages'
    total_count and limit checks; a run listed twice, or under a status it does not have,
    refuses the read. The union is answered in WR8's page shape, newest first, one fresh
    listing per enumeration, so WR8's own before/after comparison still sees any change."""
    listed = 'repos/%s/actions/workflows/%s/runs?' % (repo, B.WORKFLOW)
    whole = re.compile(re.escape(listed + 'per_page=%d&page=' % B.PAGE) + r'([1-9][0-9]*)')
    union = []

    def listing():
        runs = {}
        queries = [('status=%s' % s, s) for s in ACTIVE] + [('created=%s..%s&status=completed' % (since, until), 'completed')]
        for query, status in queries:
            for value, where in B.pages(listed + query + '&per_page=%d' % B.PAGE, 'workflow_runs', 'runs', read):
                rid = B.as_int(B.as_obj(value, where), 'id', where)
                if rid in runs or B.as_str(value, 'status', where) != status:
                    raise B.Fail('current runs: a run listed twice or under another status')
                if status == 'completed' and not since <= B.as_time(value, 'created_at', where) <= until:
                    raise B.Fail('current runs: a completed run outside its created window')
                runs[rid] = value
        return [runs[r] for r in sorted(runs, reverse=True)]

    def answer(path):
        found = whole.fullmatch(path)
        if found is None:
            return read(path)
        page = int(found.group(1))
        if page == 1:
            union[:] = listing()
        return {'total_count': len(union), 'workflow_runs': union[(page - 1) * B.PAGE:page * B.PAGE]}
    return answer


def ci_facts(repo, *, since, until):
    """MT3 (#822): a snapshot's five CI facts (collector.v1.md), read now through the collector."""
    import collect_ci  # it imports gather for current_runs and the privacy scan: import it only here
    return collect_ci.read(repo, collect_ci.FACTS, since=since, until=until)['ci']


def scan_bytes(data):
    """The existing privacy checker and credential/thread-id guard (publish.text_scan) over one artifact."""
    base = sources.native('tools/privacy-check/check.py')

    class Quiet(base.Checker):
        def refuse(self, *args, **kwargs):
            self.findings += 1
    checker = Quiet()
    try:
        text = data.decode('utf-8')
        publish.text_scan(text, checker)
        # JSON escapes (\u0067, \/) hide a value from the bytes but not from a reader:
        # every JSON string literal, keys included, is scanned again as it decodes.
        publish.text_scan('\n'.join(json.loads(s) for s in LITERAL.findall(text)), checker)
    except (UnicodeError, ValueError):
        raise Fail('the privacy scan refused a gathered binary or an undecodable string')
    if checker.findings:
        raise Fail('the privacy scan refused a gathered source')


def scan(root):
    """Every gathered file, again, as it will be selected."""
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise Fail('the privacy scan refused a gathered link')
        if path.is_file():
            scan_bytes(path.read_bytes())


def open_approved(graph_raw, repo):
    """Open approved ticket numbers on the board graph (unfinished work), or None.

    Only the configured repository's own board-wide read enumerates its unfinished work:
    a spec graph covers one spec, and another repository's numbers are other issues."""
    if graph_raw is None:
        return None
    try:
        graph = suite._decode(graph_raw.decode('utf-8'))
        if type(graph) is not dict or graph.get('repo') != repo or graph.get('source') != {'kind': 'board'}:
            return None
        sources.board_check_links(graph)
        return sorted(t['number'] for t in sources.board_open_approved(graph))
    except (ValueError, KeyError, TypeError, UnicodeError):
        return None


def stage_evidence(repo, tickets, clock):
    """TL2's journeys and stage sidecar over `tickets`, read once, or None."""
    if not tickets:
        return None
    stages = {}
    try:
        doc = J.collect(repo, sorted(tickets), [], stage_export=stages, read_at=clock())
        J.validate(json.loads(json.dumps(doc)))
        J.validate_stage_waits(json.loads(json.dumps(stages)), json.loads(json.dumps(doc)))
    except (J.ReadError, M.ReadError, OSError, ValueError, TypeError, KeyError, StopIteration):
        return None
    return ((json.dumps(doc, indent=2) + '\n').encode(), (json.dumps(stages, indent=2) + '\n').encode())


def chart_snapshot(repo):
    """MT13: only the chart's fact; other facts are explicitly not read here."""
    doc = {'schema': collect_factory.SNAPSHOT, 'repository': repo, 'collected_at': now()}
    for group in ('factory', 'ci'):
        doc[group] = {name: collect_factory.unavailable(name, 'Not read for the published PRs-an-hour chart.')
                      for name in collect_factory.SCHEMA['x-facts'][group]}
    doc['factory']['prs_per_hour'] = collect_factory.unavailable(
        'prs_per_hour', 'PRs an hour unavailable: the collector read failed or exceeded 60 seconds.')
    started = time.monotonic()
    try:
        with subprocess.Popen([sys.executable, '-I', str(HERE / 'collect_factory.py'), 'read', '--repo', repo,
                               '--fact', 'prs_per_hour'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              start_new_session=True) as read:
            raw, _ = read.communicate()
            suite.require(read.returncode == 0, 'chart read failed')
        answer = suite._decode(raw.decode('utf-8'))
        suite._shape(answer, collect_factory.SCHEMA['$defs']['read_envelope'], collect_factory.SCHEMA)
        suite.require(answer['repository'] == repo, 'chart read repository differs')
        fact = answer['factory']['prs_per_hour']
        collect_factory.validate(fact)
        doc['factory']['prs_per_hour'] = fact
    except (OSError, ValueError, KeyError, UnicodeError):
        pass  # An unread chart must not stall the remaining publish or become zero.
    finally:
        print('war-room PRs-per-hour read: %.3f seconds' % (time.monotonic() - started), file=sys.stderr)
    doc['collected_at'] = max([now(), *([fact['read']['ended_at']] if
                              (fact := doc['factory']['prs_per_hour'])['read'] else [])])
    scan_bytes(json.dumps(doc).encode())
    return doc


def gather(out, *, remote, repo, run_url, clock=now, pools=POOLS, journeys=None, cohort=None, answer_time=None,
           stage=None, data_remote=None):
    """Write out/root and out/selection.json, or raise Fail and select nothing.

    `data_remote` (WRD4) is the repository holding the board data branch, when it
    is not on `remote`; its commit evidence then links it.

    `stage` is an existing directory holding TL2's journeys.json and stage-waits.json;
    without it they are collected for the open approved and merged cohort tickets."""
    out = Path(out)
    suite.require(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo) is not None, 'invalid repository')
    suite.require(sources.LINK.fullmatch(run_url) is not None, 'invalid run link')
    suite.require((journeys is None) == (cohort is None), '--journeys and --cohort go together')
    started = clock()
    data_repo = repo
    if data_remote is not None:
        hosted = re.fullmatch(r'https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?', data_remote)
        data_repo = hosted.group(1) if hosted else repo
    commit_link = 'https://github.com/%s/commit/%%s' % data_repo
    with tempfile.TemporaryDirectory(prefix='war-room-gather-') as tmp:
        work = Path(tmp) / 'git'
        git(Path(tmp), 'init', '-q', '--bare', str(work))
        board = branch(work, data_remote or remote, 'board')

        # Current CI and throughput (WR8), and the merged cohort's journeys, through the existing gh readers.
        prs = None
        try:
            prs = M.collect_prs(repo)
        except (M.ReadError, OSError, ValueError, TypeError, KeyError):
            pass

        def pr_read(_repo):
            if prs is None:
                raise M.ReadError('merged PR pages unavailable')
            return prs
        wr8 = None
        journey_doc = None
        if journeys is not None:
            journey_wire = Path(journeys).read_bytes()
            chosen = suite._decode(Path(cohort).read_text(encoding='utf-8'))
            suite.require(type(chosen) is dict and set(chosen) == {'cohort', 'merged_prs', 'since', 'until', 'observed_at'},
                          'invalid cohort fields')
            journey_observed = chosen.pop('observed_at')
        else:
            journey_wire, chosen = None, merged_cohort(prs, started) if prs is not None else None
            if chosen is not None:
                tickets = sorted({t for n in chosen['merged_prs'] for t in prs[n]['tickets']})
                try:
                    journey_doc = J.collect(repo, tickets, [])
                    J.validate(json.loads(json.dumps(journey_doc)))
                    journey_wire = (json.dumps(journey_doc, indent=2) + '\n').encode()
                except (J.ReadError, M.ReadError, OSError, ValueError, TypeError, KeyError):
                    journey_wire = None
        # WRD1 health: main CI, and one stage evidence set covering unfinished approved work.
        main = health.main_ci(repo, B.gh, clock)
        stage_gap = None
        if stage is not None:
            stage_wires = tuple(Path(stage, name).read_bytes() for name in ('journeys.json', 'stage-waits.json'))
        else:
            # Both enumerations must succeed: a cohort missing the unfinished work is never collected.
            approved = open_approved(board[0]['graph.json']() if board and 'graph.json' in board[0] else None, repo)
            if approved is None or prs is None:
                stage_wires, stage_gap = None, REASONS['stage_coverage']
            else:
                tickets = set(approved)
                if chosen is not None:
                    tickets |= {t for n in chosen['merged_prs'] if n in prs for t in prs[n]['tickets']}
                stage_wires = stage_evidence(repo, tickets, clock)
        settings_raw, settings_read_at = LIMITS.read_bytes(), clock()
        ended = clock()
        if utc(ended) <= utc(started):
            time.sleep(1)  # WR8 needs a nonempty read interval: [started, ended)
            ended = clock()
        ci_read, raw_jobs = health.capture(current_runs(repo, iso(utc(ended).replace(hour=0, minute=0, second=0)),
                                                        ended, B.gh))
        try:
            wr8 = activity.project(ended, repo=repo, read_started_at=started, source_path='activity/observation.json',
                                   pools=tuple(pools), ci_read=ci_read, pr_read=pr_read, ticket_read=M.graphql)
        except (ValueError, TypeError, KeyError, OSError):
            wr8 = None
        # The queue is WR8's same checked read, projected again: no second API read. Its reads
        # happen inside activity.project, so its read bounds close only now (WR8 keeps `ended`).
        queue_end = clock()
        queue = health.ci_queue(repo, tuple(pools), json.loads(wr8[1])['ci'] if wr8 else None, raw_jobs,
                                started, queue_end)
        if journeys is None:
            journey_observed = ended

        if out.exists():
            raise Fail('the output directory already exists')
        staging = Path(tmp) / 'root'
        staging.mkdir(mode=0o700)
        root = Root(staging, repo, run_url, queue_end)  # the selection's tick: after every read

        # Board history and credits, from the board branch at its commit.
        files = board[0] if board else {}
        if board and 'history.jsonl' in files:
            raw = files['history.jsonl']()
            s = {'path': 'board/history.jsonl', 'sha256': root.write('board/history.jsonl', raw),
                 'observed_at': board[2], 'evidence': [commit_link % board[1]]}
            graph = files['graph.json']() if 'graph.json' in files else None
            try:
                root.projected(board_provider(s, raw, graph, graph and hashlib.sha256(graph).hexdigest()), board[2])
            except Exception as error:
                if not isinstance(error, (ValueError, KeyError, TypeError, UnicodeError)) and \
                        type(error).__name__ not in ('Fail', 'ReadError'):
                    raise
                (staging / 'board/history.jsonl').unlink()
                root.missing('board', REASONS['board'])
        else:
            root.missing('board', REASONS['board'])
        if board and 'credits.jsonl' in files:
            root.select('credits', 'credits', 'board/credits.jsonl', files['credits.jsonl'](), board[2],
                        [commit_link % board[1]])
        else:
            root.missing('credits', REASONS['credits'])

        # The CI bench retired (#827): its slot is an explained gap, never a stale point.
        root.missing('ci_bench', REASONS['ci_bench'])

        if wr8 is not None:
            provider, wire = wr8
            root.write('activity/observation.json', wire)
            root.projected(provider, ended)
        else:
            root.missing('activity', REASONS['activity'])

        # The v2 health providers, each pinned to its own retained observation bytes.
        for slot, (provider, wire), observed in (('main_ci', main, max(o['read']['ended_at'] for o in main[0]['observations'])),
                                                 ('ci_queue', queue, queue_end)):
            root.write('health/%s.json' % slot.replace('_', '-'), wire)
            if root.projected(provider, observed) is None:
                (staging / 'health' / ('%s.json' % slot.replace('_', '-'))).unlink()
        if stage_wires is not None:
            root.write('stage/journeys.json', stage_wires[0])
            root.write('stage/stage-waits.json', stage_wires[1])
            root.write('stage/limits.conf', settings_raw)
            files = dict(root=staging, journey='stage/journeys.json', sidecar='stage/stage-waits.json',
                         settings='stage/limits.conf')
            sample = iso(utc(ended).replace(minute=utc(ended).minute // 5 * 5, second=0))
            # Each producer's own refusal is an explained unavailable provider, never a miss or zero.
            root.projected(stage_waits.project(sample, **files, settings_evidence=[run_url], assembled_at=ended,
                                               settings_read_at=settings_read_at), ended)
            root.projected(health.stage_health(**files, settings_read_at=settings_read_at,
                                               read={'started_at': started, 'ended_at': ended}, evidence=[run_url]), ended)
        else:
            root.missing('stage_waits', stage_gap or REASONS['stage_waits'])
            root.missing('stage_health', stage_gap or REASONS['stage_health'])

        # Journeys, rework (WR6) and cost readiness (WR4) over one merged cohort.
        journey = None
        if journey_wire is not None and chosen is not None:
            journey = root.select('journey', 'journey', 'journey/journeys.json', journey_wire, journey_observed, [run_url])
        else:
            root.missing('journey', REASONS['journey'])
        if journey is not None:
            try:
                root.projected(rework.project(journey_wire, source_path='journey/journeys.json',
                                              observed_at=journey_observed, **chosen), journey_observed)
            except ValueError:
                root.missing('rework', REASONS['rework'])
        else:
            root.missing('rework', REASONS['rework'])
        selections = {}
        for key, entry in (('journey', journey),):
            if entry is not None:
                selections[key] = {'path': str(staging / entry['path']), 'source_path': entry['path'],
                                   'observed_at': entry['observed_at'], 'evidence': entry['evidence']}
        if selections:
            sample = utc(ended).replace(minute=utc(ended).minute // 5 * 5, second=0)
            try:
                root.projected(cost.project(iso(sample), assembled_at=ended, **selections))
            except ValueError:
                root.missing('cost', REASONS['cost'])
        else:
            root.missing('cost', REASONS['cost'])

        # Answer time (WR5): its own projection when one is supplied, otherwise its precise readiness.
        supplied = None
        if answer_time is not None:
            try:
                supplied = suite._decode(Path(answer_time).read_text(encoding='utf-8'))
                suite.require(type(supplied) is dict and supplied.get('slot') == 'answer_time', 'not an answer_time provider')
            except (OSError, ValueError, UnicodeError):
                supplied = None
                root.missing('answer_time', REASONS['answer_time'])
        if supplied is not None:
            root.projected(supplied)
        elif answer_time is None:
            root.projected(wr5.unavailable(), ended)

        scan(staging)
        chart_wire = (json.dumps(chart_snapshot(repo), indent=1) + '\n').encode()
        out.mkdir(parents=True)
        shutil.copytree(staging, out / 'root')
        (out / 'selection.json').write_text(json.dumps(root.selection, indent=1) + '\n', encoding='utf-8')
        (out / 'snapshot.json').write_bytes(chart_wire)
    return root.selection



# The collector snapshot (collector.v1.md): every fact once, composed from both groups' reads.
def snapshot(repository, *, clock=now, **reads):
    """One `openwiz.war-room.collector.v1` snapshot, or raise Fail on a privacy hit (nothing kept).

    `reads` are collect_factory.read's keywords (window, usage, robots, tickets, base, checks);
    the CI group is read over the same window."""
    # One window for both groups, resolved before either reads (the default: the last whole UTC day).
    reads['since'], reads['until'] = collect_factory.window(reads.get('since'), reads.get('until'), clock())
    factory = collect_factory.read(repository, collect_factory.FACTS, clock=clock, **reads)['factory']  # MT2's call
    ci = ci_facts(repository, since=reads['since'], until=reads['until'])  # MT3's call
    # The collection's end: at or after every fact's read, whichever clock each reader used.
    ends = [f['read']['ended_at'] for group in (factory, ci) for f in group.values() if f['read']]
    doc = {'schema': collect_factory.SNAPSHOT, 'repository': repository, 'collected_at': max([clock(), *ends]),
           'factory': factory, 'ci': ci}
    scan_bytes(json.dumps(doc, sort_keys=True).encode())
    return doc


def main(argv):
    parser = argparse.ArgumentParser(description='Gather the War room sources (WR10). Reads only.')
    parser.add_argument('--remote', required=True, help='the repository to fetch board from')
    parser.add_argument('--data-remote', help='the repository holding the board data branch; '
                        'default: --remote. A https://github.com/OWNER/REPO[.git] value also names its evidence links')
    parser.add_argument('--repo', required=True, help='OWNER/REPO for the read-only gh reads and links')
    parser.add_argument('--run-url', required=True, help='the GitHub run performing the reads (evidence)')
    parser.add_argument('--out', required=True, type=Path, help='a new directory')
    parser.add_argument('--pool', action='append', help='an exact CI pool label (repeat); default: %s' % ', '.join(POOLS))
    parser.add_argument('--journeys', type=Path, help='an existing journeys.json instead of collecting one')
    parser.add_argument('--cohort', type=Path, help="the journeys' merged cohort (cohort, merged_prs, since, until, observed_at)")
    parser.add_argument('--answer-time', type=Path, help="WR5's projected answer_time provider")
    parser.add_argument('--stage', type=Path, help="an existing directory with TL2's journeys.json and stage-waits.json")
    a = parser.parse_args(argv)
    try:
        selection = gather(a.out, remote=a.remote, repo=a.repo, run_url=a.run_url, pools=tuple(a.pool or POOLS),
                           journeys=a.journeys, cohort=a.cohort, answer_time=a.answer_time, stage=a.stage,
                           data_remote=a.data_remote)
    except (Fail, ValueError, OSError, UnicodeError, RecursionError) as e:
        # Only the reason class: a source error can carry a private value.
        print('war-room gather: %s; nothing selected' % (e if isinstance(e, Fail) else type(e).__name__), file=sys.stderr)
        return 1
    for entry in selection:
        print('%s: %s' % (entry['slot'], 'missing, with its reason' if entry['path'].startswith('missing/') else entry['path']))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
