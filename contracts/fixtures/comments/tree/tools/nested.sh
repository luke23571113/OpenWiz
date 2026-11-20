#!/bin/sh
label="$(printf '%s' "a # not a comment")"
when="$(date "+%s" # SAFETY: the stamp is whole seconds, never a fraction
# SAFETY: the clock may step back, so callers never subtract stamps
)"
echo "$label $when"
