#!/bin/sh
set -u
bin=$1
tmp=$(mktemp -d)
sh -c 'mkdir -m 700 "$1/openwiz-loop-index-$$" && echo synthetic > "$1/openwiz-loop-index-$$/kept.txt" && echo "$1/openwiz-loop-index-$$" > "$1/planted" && TMPDIR="$1" exec "$2" --exact state::loops::storage::tests::an_indexed_run_without_its_record_is_refused_never_an_empty_history -q' sh "$tmp" "$bin" >/dev/null 2>&1
code=$?
planted=$(cat "$tmp/planted")
if [ -f "$planted/kept.txt" ]; then kept=yes; else kept=no; fi
echo "test exit=$code; pre-existing file kept=$kept"
rm -rf "$tmp"
[ "$code" = 0 ] && [ "$kept" = yes ]
