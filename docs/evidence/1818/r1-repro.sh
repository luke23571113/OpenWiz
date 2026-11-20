#!/bin/sh
set -u
bin=$1
tmp=$(mktemp -d)
sh -c 'for d in "$1/openwiz-loop-index-$$" "$1/openwiz-loop-index-$$-0"; do mkdir -m 700 "$d" && echo synthetic > "$d/kept.txt" && echo "$d" >> "$1/planted"; done && TMPDIR="$1" exec "$2" --exact state::loops::storage::tests::an_indexed_run_without_its_record_is_refused_never_an_empty_history -q' sh "$tmp" "$bin" >/dev/null 2>&1
code=$?
kept=yes
for d in $(cat "$tmp/planted"); do [ -f "$d/kept.txt" ] || kept=no; done
echo "planted $(wc -l < "$tmp/planted") folders; test exit=$code; pre-existing files kept=$kept"
rm -rf "$tmp"
[ "$code" = 0 ] && [ "$kept" = yes ]
