#!/usr/bin/env python3
"""Profile the unchanged FA3 schedule on Linux, including failed ticks.

GNU time measures complete fake-command processes (Python startup, fixture
responses, logging and any children). Child CPU minus fake CPU measures the
remaining fleet.sh work. Fake wall times overlap and MUST NOT be subtracted
from tick wall time. GNU time's per-process CPU precision is 0.01 seconds.
Run alone, with four CPUs, after building the fixture CLI.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import resource
import platform
import shlex
import subprocess
import sys
import time
from unittest import mock

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('profile_load', HERE / 'load.py')
load = importlib.util.module_from_spec(spec)
spec.loader.exec_module(load)
REAL_RUN = subprocess.run


def measure(fleet, report_path, trace_path=None):
    rows = []
    report = dict(evidence='synthetic fixture; live HTTP and latency unverified',
                  affinity_cpus=len(os.sched_getaffinity(0)), python=platform.python_version(), arch=platform.machine(),
                  cpu_quota=Path('/sys/fs/cgroup/cpu.max').read_text().strip(),
                  cpu_precision_s=0.01, workload_budget_s=getattr(load, 'MAX_WALL_S', 600), tick_budget_s=60,
                  note='Fake wall durations overlap; subtract CPU only. Nonfake CPU includes time wrapper overhead.',
                  ticks=rows, state='incomplete')
    started = time.monotonic()

    class Measured(load.Workload):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.profile = self.root / 'fake-times.jsonl'
            for name in ('gh', 'room-cli'):
                wrapper = self.root / 'bin' / name
                # -q preserves expected nonzero fake statuses (notably 304)
                # without mixing GNU time's diagnostic text into the JSONL.
                prefix = shlex.join(['/usr/bin/time', '-q', '-a', '-o', str(self.profile), '-f',
                                     '{"wall_s":%e,"user_s":%U,"system_s":%S}'])
                wrapper.write_text(wrapper.read_text().replace('exec ', 'exec ' + prefix + ' ', 1))

        def tick(self, spec, low=False):
            def timed(args, **kwargs):
                if args != ['sh', self.fleet, 'spec', str(spec)]:
                    return REAL_RUN(args, **kwargs)
                first = len(self.profile.read_text().splitlines()) if self.profile.exists() else 0
                before = resource.getrusage(resource.RUSAGE_CHILDREN)
                began = time.monotonic()
                error = None
                try:
                    return REAL_RUN(args, **kwargs)
                except Exception as failure:
                    error = type(failure).__name__
                    raise
                finally:
                    wall = time.monotonic() - began
                    after = resource.getrusage(resource.RUSAGE_CHILDREN)
                    samples = [json.loads(line) for line in self.profile.read_text().splitlines()[first:]]
                    fake_cpu = sum(s['user_s'] + s['system_s'] for s in samples)
                    cpu = after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime
                    row = dict(spec=spec, offset_s=self.now - load.START, low=low,
                               wall_s=round(wall, 6), children_cpu_s=round(cpu, 6),
                               fake_processes=len(samples), fake_cpu_s=round(fake_cpu, 6),
                               fake_summed_wall_s=round(sum(s['wall_s'] for s in samples), 6),
                               nonfake_cpu_s=round(cpu - fake_cpu, 6),
                               fake_cpu_rounding_bound_s=round(0.02 * len(samples), 6), error=error)
                    rows.append(row)
                    report_path.write_text(json.dumps(report, indent=2) + '\n')
                    print(json.dumps(row), flush=True)
            with mock.patch.object(load.subprocess, 'run', side_effect=timed):
                super().tick(spec, low=low)
            assert rows[-1]['fake_processes'] == self.ticks[-1]['questions'], 'missing fake process measurements'

    try:
        with mock.patch.object(load, 'Workload', Measured):
            trace = load.run(fleet=fleet, scaled=True)
        if trace_path:
            trace_path.write_text(json.dumps(trace) + '\n')
        load.verify(trace)
        load.extension('scale').report(trace)
        report['state'] = 'complete'
    finally:
        report['wall_s'] = round(time.monotonic() - started, 6)
        report_path.write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fleet', type=Path, default=(load.SCRIPTS / 'fleet.sh').resolve())
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--trace', type=Path, help='Optional full synthetic trace for test.py --verify-report')
    args = parser.parse_args()
    if not Path('/usr/bin/time').is_file():
        parser.error('requires GNU time at /usr/bin/time')
    if len(os.sched_getaffinity(0)) != 4:
        parser.error('run with exactly four CPUs, e.g. taskset -c 0-3')
    quota, period = Path('/sys/fs/cgroup/cpu.max').read_text().split()
    if quota != 'max' and int(quota) < 4 * int(period):
        parser.error('requires a CPU quota of at least four CPUs')
    measure(args.fleet.resolve(), args.report, args.trace)


if __name__ == '__main__':
    main()
