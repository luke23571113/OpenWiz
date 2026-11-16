#!/bin/sh
# MT10 (#829) proof M4: nothing refers to the retired live-check toolkit.
# Usage: sh docs/evidence/829/search.sh [REV]   (default: the work tree)
# Exits 0 with no output when nothing refers to it, 1 listing each hit.
# The release words "live-checked" and the release kits in docs/live-checks/
# are not the toolkit and do not match. Excluded by exact path: this folder,
# and historical records that quote the old workflow as it was.
set -u
pattern='tools/live-check|live-check toolkit|live-check fixture|live-check-source|live-check-evidence|live-check failure|toolkit-nightly|prerequisite:toolkit|prerequisite-toolkit|CLASSIFY_STEP=toolkit|lt3-fixture-source|outputs\.toolkit'
set -- ${1:+"$1"} -- . \
  ':(exclude)docs/evidence/829/**' \
  ':(exclude)docs/evidence/ci2-batch-proof.md' \
  ':(exclude)docs/evidence/ci2-pr-cuts.md' \
  ':(exclude)ci/main-batch/fixtures/shadow/ci-before.sha256'
if git grep -n -I -E "$pattern" "$@"; then exit 1; fi
exit 0
