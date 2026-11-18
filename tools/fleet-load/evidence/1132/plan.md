# #1132 proof plan

Existing LoadProof exercises the complete 100-ticket/five-spec schedule,
200 starts, 100 verified merges, 200 archives, ownership, head-bound routing,
quiet-agent deadlines, pagination and both HTTP/GraphQL budgets. It already
rejects planted safety/accounting violations. Keep every case and assertion.

No new test: this change measures and resets only the harness execution
budget and registers the existing suite in CI. The red proof is the existing
load workload exhausting its cumulative deadline; the green proof is the
same workload followed by every existing LoadProof/test.py case, without
reducing the workload. A separate timing helper observes complete fake
processes, including expected nonzero 304 responses, and checks that their
GH count equals the proof's existing question count for each completed tick.

If measurement confirms cumulative timeout: name the 900-second workload
budget in load.py and propagate it to scale.identity's frozen workload
snapshot before execution. Keep the 60-second per-command/tick cap and all
other virtual-time, HTTP, concurrency and safety bounds. Record all measured
ticks, profiler precision and incomplete rows. No production fleet or fake
responses change.
