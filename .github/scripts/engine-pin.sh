#!/usr/bin/env bash
# Prints the engine pin from Cargo.lock as `tag=<tag>` and `rev=<commit>` — the two lines a workflow
# appends to $GITHUB_OUTPUT.
#
# The pin lives in Cargo.lock, never in a workflow: cargo resolves every `grimoire*` crate from the
# same `git+…?tag=…#<commit>` source (ADR-0009, ADR-0013), so a `cargo update -p grimoire` moves the
# asset gate with the rest of the build and nothing has to be edited twice. Two different engine
# sources in one lock file would make "the pinned tag" ambiguous, so that is an error here.
#
# Usage: engine-pin.sh [Cargo.lock]
set -euo pipefail

lock=${1:-Cargo.lock}
test -f "$lock" || { echo "engine-pin: $lock fehlt." >&2; exit 1; }

sources=$(grep -oE 'git\+https://github\.com/LupusMalusDeviant/grimoire\?tag=[^"#]+#[0-9a-f]{40}' "$lock" | sort -u)
count=$(printf '%s\n' "$sources" | grep -c . || true)
if [ "$count" -ne 1 ]; then
  echo "engine-pin: $lock nennt $count Engine-Quellen, erwartet genau eine:" >&2
  printf '%s\n' "$sources" >&2
  exit 1
fi

tag=${sources#*\?tag=}
tag=${tag%%#*}
rev=${sources#*#}

printf 'tag=%s\n' "$tag"
printf 'rev=%s\n' "$rev"
