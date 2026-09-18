#!/usr/bin/env bash
# Golden master of the engine's reference patterns (Plan 0002 WP7.5).
#
# The game does not own these patterns — they live in the engine and the engine gates their unit
# bytes itself. What the game owns is the claim that *the tag it pins* still turns them into the
# same units and the same simulation: that is what this master freezes, and it is exactly what
# breaks loudly when the pin moves to an engine whose compiler or interpreter changed.
#
#   reference-masters.sh check <engine dir> [master file]
#   reference-masters.sh renew <engine dir> [master file]
#
# `check` compares, `renew` rewrites (its own commit, with a reason — CONTRIBUTING). The engine
# directory is a checkout of the pinned tag with `sigilc` built in release, which the asset gate
# already provides.
set -euo pipefail

mode=${1:?usage: reference-masters.sh check|renew <engine dir> [master file]}
engine=${2:?usage: reference-masters.sh check|renew <engine dir> [master file]}
master=${3:-tests/golden/reference_patterns.json}

sigilc="$engine/target/release/sigilc"
if [ ! -x "$sigilc" ] && [ -x "$sigilc.exe" ]; then
  sigilc="$sigilc.exe"
fi
test -x "$sigilc" || { echo "reference-masters: kein sigilc unter $sigilc" >&2; exit 2; }
reference="$engine/crates/grimoire_sigilc/tests/reference"
test -d "$reference" || { echo "reference-masters: kein $reference" >&2; exit 2; }

# Settings of the run. They belong to the master: a different tick count is a different master.
TICKS=600
SEED=0
CAPACITY=16384
BOUNDS="-13.5,-13.5,13.5,13.5"
TARGET="0,-7.5"

field() { # <document> <key>
  printf '%s' "$1" | grep -o "\"$2\":\"[0-9a-f]*\"" | head -n 1 | cut -d'"' -f4
}

lines=""
status=0
for source in "$reference"/*.sigil; do
  name=$(basename "$source")
  document=$("$sigilc" simulate --json \
    --root "$reference" \
    --behaviors "$reference/behaviors.json" \
    --ticks "$TICKS" --seed "$SEED" --capacity "$CAPACITY" \
    --bounds "$BOUNDS" --target "$TARGET" \
    -- "$source")
  unit=$(field "$document" unit_id)
  content=$(field "$document" content_hash)
  final=$(field "$document" final_state_hash)
  if [ -z "$unit" ] || [ -z "$content" ] || [ -z "$final" ]; then
    echo "::error title=Referenz-Pattern nicht simulierbar::$name lieferte kein vollstaendiges Dokument." >&2
    exit 1
  fi
  line="  { \"pattern\": \"$name\", \"unit_id\": \"$unit\", \"content_hash\": \"$content\", \"final_state_hash\": \"$final\" }"
  lines="${lines}${line},"$'\n'

  if [ "$mode" = "check" ]; then
    expected=$(grep -F "\"pattern\": \"$name\"" "$master" || true)
    if [ -z "$expected" ]; then
      echo "::error title=Referenz-Pattern fehlt im Master::$name steht nicht in $master."
      status=1
      continue
    fi
    if [ "$(printf '%s' "$expected" | tr -d ' ,')" != "$(printf '%s' "$line" | tr -d ' ,')" ]; then
      echo "::error title=Referenz-Pattern weicht ab::$name"
      echo "  Master: $(printf '%s' "$expected" | sed 's/^ *//')"
      echo "  Lauf:   $(printf '%s' "$line" | sed 's/^ *//')"
      status=1
    fi
  fi
done

if [ "$mode" = "check" ]; then
  if [ "$status" -eq 0 ]; then
    echo "Alle Referenz-Patterns stimmen mit $master ueberein."
  else
    echo "Erneuern ist eine Entscheidung, keine Reparatur (CONTRIBUTING, \"Golden-Master und Referenzwerte\")." >&2
  fi
  exit "$status"
fi

if [ "$mode" != "renew" ]; then
  echo "reference-masters: unbekannter Modus \`$mode\` (check oder renew)" >&2
  exit 2
fi

tag=$(bash .github/scripts/engine-pin.sh | sed -n 's/^tag=//p')
mkdir -p "$(dirname "$master")"
{
  echo "{"
  echo "  \"schema\": \"grimoire.fnp.golden.reference\","
  echo "  \"schema_version\": 1,"
  echo "  \"engine_tag\": \"$tag\","
  echo "  \"settings\": { \"ticks\": $TICKS, \"seed\": $SEED, \"capacity\": $CAPACITY, \"bounds\": \"$BOUNDS\", \"target\": \"$TARGET\" },"
  echo "  \"patterns\": ["
  printf '%s' "$lines" | sed '$ s/,$//'
  echo "  ]"
  echo "}"
} >"$master"
echo "Master $master aus Engine-Tag $tag erneuert."
