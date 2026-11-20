#!/bin/sh
# A synthetic WizSkills release's installer for the boat driver's tests: `install.sh --version <v> --dest <dir>`
# puts this release's skills at <dir>; an existing <dir> is kept as it is, as the real one keeps a matching install.
set -eu
[ "$1" = --version ] && [ "$3" = --dest ] || exit 2
dest=$4
[ -e "$dest" ] && exit 0
mkdir "$dest"
cp -R "$(dirname "$0")/skills" "$dest/skills"
