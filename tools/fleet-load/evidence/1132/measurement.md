# #1132: execution-budget measurement

Scope: synthetic fixture proof, not live fleet performance. The ticket's
orchestrator ruling is OpenWiz #555, comment 6987416334, item 2.

## Method

Run alone on Linux with affinity restricted to four CPUs (`taskset -c 0-3`)
and cgroup `cpu.max` of `400000 100000` (four CPU-seconds per second).
Python 3.11.2, jq 1.6, Rust 1.99.1, aarch64. Build the fixture CLI first,
then measure the complete scaled workload, without changing its schedule.

`measure_load.py` wraps each fake command during ticks with GNU time, including expected
nonzero statuses such as 304. Constructor revision priming precedes profiling.
This includes interpreter startup, fixture
imports, JSON, logging and fake-internal children. Each tick separately
records its wall time and child CPU; child CPU minus fake CPU is the
remaining shell/nonfake-child work, including profiling-wrapper overhead.
GNU time has 0.01-second precision for each user/system value; the TSVs give
a conservative 0.02-second-per-process aggregate rounding bound. The child
CPU total uses Python's higher-precision `getrusage`. No fake wall-time sum
is subtracted: parallel fake processes overlap. Failed ticks are incomplete,
not evidence of a complete read or reliable CPU decomposition.

The baseline used a temporary prototype of the same GNU-time wrappers and
`getrusage` measurement, against commit
`779250eb49d2929f422989536dc084b20c4fb2e9`. A prototype parsing error on GNU
time's expected-nonzero diagnostics was corrected with `-q` before the
recorded baseline; that setup error is not claimed as a load-proof failure.
The checked-in helper also verifies each completed tick's fake-gh process count
against the existing proof's recorded question count. Measurement requires
GNU time only; the regular suite gains no dependency.

## Reproduce

```sh
cargo build --locked -p openwiz-tests --example openwiz -j 2
taskset -c 0-3 python3 -I tools/fleet-load/measure_load.py \
  --report /tmp/fleet-load-cost.json --trace /tmp/fleet-load-trace.json
# Exercise every existing test.py assertion from that exact completed trace:
taskset -c 0-3 python3 -I tools/fleet-load/test.py \
  --verify-report /tmp/fleet-load-trace.json
# CI always runs a fresh workload:
sh tools/fleet-load/ci.sh
```

## Baseline result

The unchanged proof failed at 600.497 seconds. It completed 46 ticks and
started a 47th. Completed tick wall sum: 532.178 seconds; maximum: 20.444
seconds, comfortably below the unchanged 60-second tick cap. The failed
spec-400 tick received only 3.942 seconds of remaining workload time.
`red.txt` preserves that timeout and the consequent temporary-directory
cleanup error. No recording children remained after the failed run.

Completed ticks used 1103.518 child CPU-seconds. The 6358 fake processes
accounted for approximately 141.680 CPU-seconds; conservative total rounding
uncertainty is 127.160 seconds. The remainder is approximately 961.838
CPU-seconds of shell/nonfake-child work, including profiler overhead. This
separates fake-process cost without pretending to measure live HTTP latency.
`baseline-ticks.tsv` preserves every completed tick and marks the partial one.

The earlier saved failures (`../2788-load-second.txt` and
`../2788-r1-batch-load-failed.txt`) likewise exhausted the cumulative bound:
1.929 and 6.445 seconds remained for their last command. Those values were
remaining time, not full-tick durations or seconds beyond the tick cap.

## Budget decision

Reset the cumulative workload budget from 600 to 900 seconds (50% headroom
over the expired bound). Keep the separate 60-second command/tick cap.
Record 900 in the frozen aggregate workload snapshot as well, so the report
cannot advertise the old 600-second bound. Preserve every case, count,
virtual-time bound, concurrency bound and safety/API-budget assertion.
No production reader or fake response changes. This ticket explicitly
allows an evidence-based budget reset; it claims no production speedup.

### Profiler consistency correction

The first candidate profile stopped at its new process-count cross-check.
A warm tick also invokes the fake `room-cli thread list` from `records.py`;
that is a real fake-process cost, but not one of the GitHub questions.
The profiler now labels each timed process by tool, retains both costs, and
checks the exact GH-only count against the proof's existing question count.
The incomplete candidate run is not a passing workload. The baseline's
all-fake CPU measurements remain valid; they included that room-cli cost.
