#!/usr/bin/env python3
"""#1027's controlled I/O-latency replay of current_activity: synthetic runs only, no live read.

    python3 -I replay.py <bench_reads.py> [--runs 259] [--scale 0.02]

Loads the given bench_reads.py (the parent's, written out with `git show`, or the head's), reads
one synthetic day of ci.yml runs through its current_activity and prints one JSON line: wall
seconds, request/run/job counts, the most reads in flight and the result's sha256. Each request
sleeps a latency fixed by its path and read number alone (0.35-1.15 s, the reported live range,
times --scale), so both versions wait for exactly the same requests whatever their order.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import threading
import time

WAR_ROOM = Path(__file__).resolve().parents[2]
REPO = 'synthetic-owner/work'
ROOT = 'repos/' + REPO
DAY, AT = '2030-01-02T00:00:00Z', '2030-01-02T12:30:00Z'


def world(count):
    """`count` runs, about four in five completed today with six jobs, the rest active with three."""
    runs, answers = [], {}
    for n in range(count):
        rid = 5000 + n
        done = n % 5 != 0
        run = {'id': rid, 'run_attempt': 1 + n % 3, 'status': 'completed' if done else 'in_progress',
               'conclusion': 'success' if done else None, 'created_at': '2030-01-02T%02d:%02d:00Z' % (n % 12, n % 60)}
        runs.append(run)
        jobs = []
        for k in range(6 if done else 3):
            labels = ['ubuntu-slim'] if k % 2 else ['ubuntu-24.04']
            job = {'id': rid * 10 + k, 'run_id': rid, 'run_attempt': run['run_attempt'], 'labels': labels,
                   'created_at': run['created_at'], 'status': 'completed' if done else ('queued', 'in_progress')[k % 2],
                   'runner_name': 'synthetic-runner' if done else None, 'steps': [],
                   'started_at': '2030-01-02T12:00:00Z' if done else None,
                   'completed_at': '2030-01-02T12:%02d:%02dZ' % (1 + k, n % 60) if done else None}
            jobs.append(job)
        answers[f'{ROOT}/actions/runs/{rid}/jobs?per_page=100&page=1'] = {'total_count': len(jobs), 'jobs': jobs}
        answers[f'{ROOT}/actions/runs/{rid}'] = run
    runs.sort(key=lambda r: -r['id'])  # newest first, as the API lists them
    for page in range(1, count // 100 + 2):
        answers[f'{ROOT}/actions/workflows/ci.yml/runs?per_page=100&page={page}'] = {
            'total_count': count, 'workflow_runs': runs[(page - 1) * 100:page * 100]}
    return answers


class Reader:
    def __init__(self, answers, scale):
        self.answers, self.scale, self.lock = answers, scale, threading.Lock()
        self.reads, self.now, self.most = {}, 0, 0

    def __call__(self, path):
        with self.lock:
            nth = self.reads[path] = self.reads.get(path, 0) + 1
            self.now += 1
            self.most = max(self.most, self.now)
        try:
            fraction = int.from_bytes(hashlib.sha256(f'{path}#{nth}'.encode()).digest()[:4], 'big') / 2 ** 32
            time.sleep((0.35 + 0.8 * fraction) * self.scale)
            return json.loads(json.dumps(self.answers[path]))
        finally:
            with self.lock:
                self.now -= 1


def main():
    args = argparse.ArgumentParser()
    args.add_argument('module')
    args.add_argument('--runs', type=int, default=259)
    args.add_argument('--scale', type=float, default=0.02)
    a = args.parse_args()
    spec = importlib.util.spec_from_file_location('bench_reads_under_test', a.module)
    B = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(B)
    B.HERE = WAR_ROOM  # the price table both versions read
    read = Reader(world(a.runs), a.scale)
    started = time.monotonic()
    seen = B.current_activity(DAY, AT, repo=REPO, read=read)
    seconds = time.monotonic() - started
    print(json.dumps({'seconds': round(seconds, 2), 'requests': sum(read.reads.values()),
                      'runs': len(seen['runs']), 'jobs': len(seen['jobs']), 'priced_jobs': len(seen['cost_jobs']),
                      'most_in_flight': read.most,
                      'result_sha256': hashlib.sha256(json.dumps(seen, sort_keys=True).encode()).hexdigest()}))


if __name__ == '__main__':
    main()
