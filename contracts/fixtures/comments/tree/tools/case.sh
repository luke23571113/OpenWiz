#!/bin/sh
kind="$(case "$1" in
  value) printf '%s' ok ;;
esac
# SAFETY: the kind is empty for any other argument
# SAFETY: callers treat an empty kind as unknown
)"
echo "$kind"
