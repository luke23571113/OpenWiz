#!/bin/sh
stamp="$(echo `date +%s` # a backtick makes this substitution unsure, so this is not read
)"
kind="$(if case "$1" in v) echo "a # b" ;; esac; then echo v; fi)" # unsure line, not read
echo "$stamp $kind"
