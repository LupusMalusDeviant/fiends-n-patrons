#!/usr/bin/env bash
# Decides whether the engine checked out at the pinned tag already carries the asset compiler, and
# prints `ready=true` or `ready=false` for $GITHUB_OUTPUT (Plan 0002 WP9.3).
#
# Why this exists at all: `grimoire-ac` (engine Plan 0002 WP9.2) is younger than the engine tag this
# game pins. Until the pin reaches a tag that ships it, the gate has no compiler to run, and a
# permanently red main would teach everyone to ignore it. So exactly one tag — the one named in
# `.github/asset-gate-bootstrap` — may run without the gate, loudly and visibly.
#
# The exemption cannot rot:
#   * it counts only for the tag written in that file; any other pin is an error;
#   * the moment a pinned tag does carry the compiler, the file itself becomes an error and has to
#     go, which turns the gate on for good.
#
# That is what happened with the pin to v0.5.0: the file is gone and every tag from here on carries
# the compiler, so this script now only guards against a pin that reaches back behind it.
#
# Usage: asset-tools-ready.sh <pinned tag> [engine directory]
set -euo pipefail

# The decision goes to $GITHUB_OUTPUT (when there is one) and to the log; everything else is prose
# for the log only, so the output file never sees a line it cannot parse.
ready() {
  echo "ready=$1"
  if [ -n "${GITHUB_OUTPUT:-}" ]; then
    echo "ready=$1" >>"$GITHUB_OUTPUT"
  fi
}

tag=${1:?usage: asset-tools-ready.sh <pinned tag> [engine directory]}
engine=${2:-engine}
project="$engine/tools/src/Grimoire.AssetCompiler/Grimoire.AssetCompiler.csproj"
bootstrap=".github/asset-gate-bootstrap"

if [ -f "$project" ]; then
  if [ -f "$bootstrap" ]; then
    echo "::error title=Bootstrap-Ausnahme ist hinfaellig::Engine-Tag $tag bringt den Asset-Compiler mit. $bootstrap loeschen; das Gate laeuft ab jetzt bei jedem Push."
    exit 1
  fi
  echo "Asset-Compiler im Engine-Tag $tag vorhanden."
  ready true
  exit 0
fi

if [ ! -f "$bootstrap" ]; then
  echo "::error title=Asset-Compiler fehlt im Engine-Tag::Engine-Tag $tag hat kein $project. Pin auf einen Tag heben, der den Asset-Compiler mitbringt (CONTRIBUTING.md, Engine-Upgrade)."
  exit 1
fi

expected=$(grep -v '^#' "$bootstrap" | grep . | head -n 1 | tr -d '[:space:]')
if [ "$expected" != "$tag" ]; then
  echo "::error title=Bootstrap-Ausnahme passt nicht::$bootstrap gilt fuer $expected, gepinnt ist $tag. Entweder der Tag bringt den Asset-Compiler mit — dann die Datei loeschen — oder die Ausnahme ist falsch."
  exit 1
fi

echo "::warning title=Asset-Gate noch nicht aktiv::Engine-Tag $tag ist aelter als der Asset-Compiler; der Content wird in diesem Lauf nicht uebersetzt. Mit dem naechsten Engine-Pin faellt die Ausnahme weg ($bootstrap loeschen)."
{
  echo "### Asset-Gate noch nicht aktiv"
  echo
  echo "Engine-Tag \`$tag\` ist aelter als \`grimoire-ac\` (Engine-WP9.2). Sobald der Pin auf einen Tag"
  echo "mit Asset-Compiler steht, faellt \`$bootstrap\` weg und das Gate uebersetzt \`content/\` bei"
  echo "jedem Push."
} >>"${GITHUB_STEP_SUMMARY:-/dev/null}"
ready false
