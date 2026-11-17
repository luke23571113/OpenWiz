#!/bin/sh
# MT8 (#827), M4's repository search: the tools' paths, ci-bench.yml and ci-benchmarks.
# The slot names ci_bench and factory_metrics are not searched (immutable saved names).
# Excluded by exact path: the named gaps (#819 revision 4; #827 ruling, items 9 and 11).
# Excluded by exact string: the saved owner label tools/factory-metrics/limits.conf (item 10).
set -eu
cd "$(git rev-parse --show-toplevel)"
hits="$(git grep -n -I -E 'tools/ci-bench/|tools/factory-metrics/|ci-bench\.yml|ci-benchmarks' -- . \
  ':!docs/evidence/ci2-pr-cuts.md' \
  ':!ci/main-batch/fixtures/shadow/red-r1-benchmark.log' \
  ':!docs/evidence/823/ci-bench-parity.log' \
  ':!tools/war-room/collector.v1.md' \
  ':!tools/war-room/fixtures/collector-ci/green-move.log' \
  ':!tools/war-room/fixtures/collector-ci/green-move-merged.log' \
  ':!tools/war-room/fixtures/rework/green.log' \
  ':!tools/war-room/fixtures/rework/green-ci-registration.log' \
  ':!docs/evidence/827/search.sh' \
  | sed 's|tools/factory-metrics/limits\.conf||g' \
  | grep -E 'tools/ci-bench/|tools/factory-metrics/|ci-bench\.yml|ci-benchmarks' || true)"
if [ -n "$hits" ]; then printf '%s\n' "$hits"; echo "search: references remain"; exit 1; fi
echo "search: no reference to either tool outside the named gaps"
