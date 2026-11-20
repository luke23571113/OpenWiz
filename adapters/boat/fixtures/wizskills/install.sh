#!/bin/sh
# A synthetic WizSkills release's installer for the boat driver's tests. Like the real one, `install.sh --version
# <v> --dest <dir>` fetches the tag v<v> again from https://github.com/openwizdev/WizSkills.git (any
# url.<x>.insteadOf rewrite applies) and puts that checkout at <dir>; an existing <dir> is kept as it is.
set -eu
[ "$1" = --version ] && [ "$3" = --dest ] || exit 2
[ -e "$4" ] && exit 0
git clone --quiet --depth 1 --branch "v$2" https://github.com/openwizdev/WizSkills.git "$4"
