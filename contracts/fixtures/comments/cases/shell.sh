#!/bin/sh
# Copyright 2030 Synthetic Example
set -eu

# Make the folder first.
mkdir -p "$out"   # make it
echo "# not a comment" '# nor this'
count=$#
echo "${#count}"
cat <<EOT
# a heredoc line, not a comment
EOT
# shellcheck disable=SC2086
echo $count
# shellcheck disable=SC2086 -- word splitting is wanted here
echo $count
# External: the synthetic CLI exits 3 on success, https://example.com/cli/issues/12
synthetic-cli || [ $? -eq 3 ]
# comment-ok: the synthetic runner reads this line as its job name
echo done
