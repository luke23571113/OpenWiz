#!/usr/bin/env python3
"""Measure the real fleet reader on recording fakes, with no live endpoint.

The HTTP counts are the existing transport model's response pages, not observed
live traffic. Every fake gh invocation starts Python; its cost is reported
separately from those pages. Run this alone for comparable wall/CPU timings.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('probe_load', HERE / 'load.py')
load = importlib.util.module_from_spec(spec)
spec.loader.exec_module(load)


def measure(fleet):
    with tempfile.TemporaryDirectory(prefix='fleet-probes-') as directory:
        world = load.Workload(directory, fleet)
        world.env.update(GH_TOKEN='synthetic-measurement-token', OPENWIZ_STATE_DIR=str(world.root / 'state'),
                         LOAD_FLEET='thr_synfleet100')
        rows = []
        for name, verb, offset in [('spec-cold', 'spec', 0), ('spec-prime', 'spec', 60),
                                   ('spec-warm', 'spec', 120), ('spec-changed', 'spec', 180),
                                   ('spec-after-change', 'spec', 240), ('spec-expired', 'spec', 2040),
                                   ('spec-after-expiry', 'spec', 2100), ('check-cold', 'check', 2160),
                                   ('check-warm', 'check', 2220)]:
            if name == 'check-cold':
                # Make all five specs the project check's responsibility so
                # this is a populated full check, rather than owned-fleet skips.
                for number in load.SPECS:
                    world.item(number)['comments'] = [c for c in world.item(number)['comments']
                                                      if not c['body'].startswith('launch-fleet: fleet active')]
                world.save()
            if name == 'spec-changed':
                world.item(1001)['comments'].append(dict(id=90001, at=load.stamp(load.START + 179),
                                                       body='Synthetic measurement update'))
                world.save()
            world.env['LAUNCH_FLEET_NOW'] = str(load.START + offset)
            # Separate full-check caches so its cold/warm boundary is explicit.
            world.env['LAUNCH_FLEET_CACHE'] = str(world.root / ('check-cache' if verb == 'check' else 'cache'))
            before = len(world.read_events())
            cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
            started = time.monotonic()
            result = subprocess.run(['sh', str(fleet)] + (['spec', '100'] if verb == 'spec' else ['check']),
                                    env=world.env, text=True, capture_output=True, timeout=120)
            wall = time.monotonic() - started
            after_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
            if result.returncode:
                raise RuntimeError(f'{name}: {result.stderr}')
            calls = world.read_events()[before:]
            assert all(c['tool'] == 'gh' and c['kind'] == 'command' for c in calls), 'measurement wrote an effect'
            http = [h for c in calls for h in c['http']]
            row = dict(run=name, wall_s=round(wall, 3),
                       children_cpu_s=round(after_cpu.ru_utime + after_cpu.ru_stime - cpu.ru_utime - cpu.ru_stime, 3),
                       fake_gh_processes=len(calls),
                       graphql_commands=sum(c['args'][:2] == ['api', 'graphql'] for c in calls),
                       modeled_graphql_requests=sum(h['api'] == 'graphql' for h in http),
                       modeled_graphql_points=sum(h['cost'] for h in http if h['api'] == 'graphql'),
                       modeled_rest_pages=sum(h['api'] == 'rest' for h in http),
                       cached_304s=sum(c.get('http_status') == 304 for c in calls),
                       due_lines=len(result.stdout.splitlines()),
                       due_sha256=hashlib.sha256(result.stdout.encode()).hexdigest(),
                       points=result.stderr.strip())
            rows.append(row)
            print(json.dumps(row), file=sys.stderr, flush=True)
        # Isolate the fake interpreter/world/response/logging cost. No network
        # time is present; do not subtract this from a hypothetical live tick.
        count = 20
        bytecode = world.env.pop('LOAD_BYTECODE')
        samples, outputs, traces = [], [], []
        for mode in ('source-compilation', 'checked-bytecode'):
            if mode == 'checked-bytecode':
                world.env['LOAD_BYTECODE'] = bytecode
            first = len(world.read_events())
            cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
            started = time.monotonic()
            responses = []
            for _ in range(count):
                result = subprocess.run(['gh', 'api', '--include', '-H', 'Accept: application/vnd.github+json',
                                         'repos/synthetic-owner/synthetic-repo'], env=world.env,
                                        check=True, text=True, capture_output=True, timeout=10)
                responses.append((result.stdout, result.stderr))
            end = resource.getrusage(resource.RUSAGE_CHILDREN)
            samples.append(dict(mode=mode, count=count, wall_s=round(time.monotonic() - started, 3),
                                cpu_s=round(end.ru_utime + end.ru_stime - cpu.ru_utime - cpu.ru_stime, 3)))
            outputs.append(responses)
            traces.append(world.read_events()[first:])
        assert outputs[0] == outputs[1] and traces[0] == traces[1], 'bytecode changed fake responses/events'
        return dict(evidence='synthetic fixture; live HTTP and latency unverified',
                    candidate_sha256=hashlib.sha256(fleet.read_bytes()).hexdigest(),
                    workload='existing FA3 100 tickets, five specs; spec 100 has 20 tickets',
                    ticks=rows, fake_process_sample=dict(samples=samples, responses_and_events='20 exact matches'))


def compare(main, candidate):
    """R1: equal output and no GraphQL regression on any tick, including recovery."""
    expected = ['spec-cold', 'spec-prime', 'spec-warm', 'spec-changed', 'spec-after-change',
                'spec-expired', 'spec-after-expiry', 'check-cold', 'check-warm']
    assert [r['run'] for r in main['ticks']] == expected, 'incomplete main sequence'
    assert [r['run'] for r in candidate['ticks']] == expected, 'incomplete candidate sequence'
    assert main['workload'] == candidate['workload'], 'different workloads'
    errors, rows = [], []
    for before, after in zip(main['ticks'], candidate['ticks']):
        name = before['run']
        if before['due_sha256'] != after['due_sha256']:
            errors.append(name + ': due output differs')
        row = dict(run=name, due_output_equal=before['due_sha256'] == after['due_sha256'])
        for field in ('graphql_commands', 'modeled_graphql_requests', 'modeled_graphql_points'):
            row[field] = dict(main=before[field], candidate=after[field])
            if after[field] > before[field]:
                errors.append(f"{name}: {field} {after[field]} > main {before[field]}")
        if name in ('spec-after-change', 'spec-after-expiry'):
            assert before['graphql_commands'] == before['modeled_graphql_requests'] == 0, 'main did not replay ' + name
        rows.append(row)
    return dict(main_sha256=main['candidate_sha256'], ticks=rows, errors=errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fleet', type=Path, default=(load.SCRIPTS / 'fleet.sh').resolve())
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, help='main reader; compare every tick and fail on any GraphQL increase')
    parser.add_argument('--baseline-report', type=Path, help='save main observations separately')
    args = parser.parse_args()
    if args.baseline_report and not args.baseline:
        parser.error('--baseline-report requires --baseline')
    main = measure(args.baseline.resolve()) if args.baseline else None
    if main is not None:
        baseline_report = args.baseline_report or args.report.with_name(args.report.stem + '-main.json')
        assert baseline_report.resolve() != args.report.resolve(), 'reports must have distinct paths'
        baseline_report.write_text(json.dumps(main, indent=2) + '\n')
    report = measure(args.fleet.resolve())
    if main is not None:
        report['comparison'] = compare(main, report)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    if main is not None:
        assert not report['comparison']['errors'], 'R1 GraphQL budget regression: ' + '; '.join(report['comparison']['errors'])


if __name__ == '__main__':
    main()
