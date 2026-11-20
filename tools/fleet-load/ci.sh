#!/bin/sh
# WZ4 (#2634): ClosedWiz's fleet load checks, moved out of launch-fleet, in one
# command for CI (#1132 registers release:fleet-load). Run from the repository
# root; needs Python, sh, jq, cargo and node, as the load tests always did.
set -eu
cd "$(dirname "$0")/../.."
python3 -I tools/fleet-load/test_seams.py
python3 -I tools/fleet-load/test.py
