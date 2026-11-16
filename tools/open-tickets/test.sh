#!/bin/sh
# O15 synthetic CLI proofs only. Never contacts live GitHub or needs private literals.
# --list prints the parts, one a line; --only PART runs just that part, so
# CI's release shards (#743) can run each part exactly once. The one list
# below is both what --list prints and what a whole run runs.
set -eu
usage() { echo 'usage: sh tools/open-tickets/test.sh [--list | --only PART] [O3-check.py [O14-import.py]]' >&2; exit 2; }
tickets_parts='plan graph text move carriage proposal collect'
tickets_only=
case ${1:-} in
  --list) [ "$#" -eq 1 ] || usage; printf '%s\n' $tickets_parts; exit 0 ;;
  --only)
    [ "$#" -ge 2 ] || usage
    case " $tickets_parts " in *" $2 "*) tickets_only=$2 ;; *) echo "open-tickets: no part '$2'" >&2; exit 2 ;; esac
    shift 2 ;;
esac
[ "$#" -le 2 ] || usage
tickets_here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
tickets_checker=${1:-$tickets_here/../privacy-check/check.py}
[ -r "$tickets_checker" ] && [ -r "$(dirname -- "$tickets_checker")/workflow.py" ] || {
  echo 'open-tickets: required O3 checker or sibling is unavailable' >&2
  exit 2
}
tickets_importer=${2:-$tickets_here/../open-import/import.py}
[ -r "$tickets_importer" ] && [ -r "$(dirname -- "$tickets_importer")/paths.json" ] || {
  echo 'open-tickets: required reviewed O14 importer/list is unavailable' >&2
  exit 2
}
for tickets_part in $tickets_parts; do
  [ -z "$tickets_only" ] || [ "$tickets_only" = "$tickets_part" ] || continue
  case $tickets_part in
    plan | graph) set -- ;;
    text | move | collect) set -- --checker "$tickets_checker" ;;
    *) set -- --checker "$tickets_checker" --importer "$tickets_importer" ;;
  esac
  python3 -I "$tickets_here/test_$tickets_part.py" "$@"
done
