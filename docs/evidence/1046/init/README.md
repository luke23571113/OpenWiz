# Init lost-reply proof: disk-journal stall

The existing keeper `Init.test_lost_replies_stay_uncertain_until_read_back_then_complete_once`
protects against a duplicate repository, label, file or pull request after a
lost reply, and against a preview clearing uncertainty. No new test: keep and
strengthen its fixture isolation; all ten lost/drop rows and assertions remain.

The original foreground push ran 148 checks successfully and failed only
`setup_onboard_init_passes`: the final apply of the lost-label row exceeded
its 60-second subprocess bound. A measured run of the same ten-row test made
648 real fsync calls. A controlled probe inserts one disk-journal stall in
that final apply; the unchanged proof then reaches the same 60-second timeout
(`red.log`, committed before the fixture edit). The measured ordinary run is
`measurement.log`; a pass there does not erase the original failure.

The fixture now puts only its disposable state on Linux `/dev/shm`. That
removes unrelated disk-journal queues while retaining real fsync, file locks,
atomic replacement and separate-process reloads. Executable fixtures stay on
the ordinary temporary volume, since `/dev/shm` may be mounted noexec. Other
platforms retain their ordinary temporary volume. No production file, sleep,
retry or timeout changed. This is a provider-reconciliation proof, not a
power-loss test; tmpfs holds no data across a host restart.

`python3 -B docs/evidence/1046/init/probe.py` now passes the same disk-stall
probe (`green-stall.log`). `python3 -I tools/install/tests/init/test_init.py -v`
passes all 13 existing proofs (`green-suite.log`). The probe is diagnostic
instrumentation, not a new product test. It uses Linux `/proc` to identify the
backing file; the suite itself stays portable.

Scope: the manager's public grant on #1046 includes
`tools/install/tests/init/test_init.py` and its test-only helpers. This evidence
folder uses the standing own-evidence-folder supporting rule. No production
scope is requested or used.
