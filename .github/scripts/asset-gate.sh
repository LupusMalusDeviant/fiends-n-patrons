#!/usr/bin/env bash
# Runs the asset compiler over one directory and decides the job (Plan 0002 WP9.3).
#
#   asset-gate.sh <content-dir> <out-dir> pass
#   asset-gate.sh <content-dir> <out-dir> fail <expected-codes file>
#
# `pass` demands a clean run: exit code 0, every source compiled, a pack written. Every diagnostic
# fails the run — the gate never writes a pack that does not match its sources.
# `fail` is the negative proof: the run must end with a non-zero exit code and report every code in
# the expectation file. Without it a green gate would also be green with no compiler at all.
#
# Needs GRIMOIRE_AC and GRIMOIRE_SIGILC (the tools built from the pinned engine tag). A
# `behaviors.json` beside the content is passed on when it is there (docs/formats/sigil.md §13.3).
set -euo pipefail

dir=${1:?usage: asset-gate.sh <content-dir> <out-dir> pass|fail [expected-codes]}
out=${2:?usage: asset-gate.sh <content-dir> <out-dir> pass|fail [expected-codes]}
expect=${3:?usage: asset-gate.sh <content-dir> <out-dir> pass|fail [expected-codes]}
expected_codes=${4:-}

: "${GRIMOIRE_AC:?GRIMOIRE_AC fehlt (Pfad zu grimoire-ac)}"
: "${GRIMOIRE_SIGILC:?GRIMOIRE_SIGILC fehlt (Pfad zu sigilc)}"

arguments=("build" "$dir" "--out" "$out" "--sigilc" "$GRIMOIRE_SIGILC" "--timings")
if [ -f "$dir/behaviors.json" ]; then
  arguments+=("--behaviors" "$dir/behaviors.json")
fi

log=$(mktemp)
trap 'rm -f "$log"' EXIT
echo "grimoire-ac ${arguments[*]}"
set +e
"$GRIMOIRE_AC" "${arguments[@]}" 2>&1 | tee "$log"
status=${PIPESTATUS[0]}
set -e
echo "Exit-Code: $status"

case "$expect" in
  pass)
    if [ "$status" -ne 0 ]; then
      echo "::error title=Asset-Gate rot::\`$dir\` hat Diagnosen (Exit-Code $status); kein Pack geschrieben. Die Meldungen oben nennen Datei, Zeile, Ursache und Fix."
      exit 1
    fi
    ;;
  fail)
    test -n "$expected_codes" || { echo "asset-gate: fail braucht eine Erwartungsdatei." >&2; exit 2; }
    if [ "$status" -eq 0 ]; then
      echo "::error title=Negativnachweis gescheitert::\`$dir\` wurde angenommen, obwohl es abgelehnt werden muss. Entweder lief der Compiler nicht, oder er erkennt den Fehler nicht mehr."
      exit 1
    fi
    missing=0
    while read -r code; do
      case "$code" in ''|\#*) continue ;; esac
      if ! grep -q "error\[$code\]" "$log"; then
        echo "::error title=Diagnose fehlt::\`$dir\` wurde abgelehnt, aber ohne $code. Erwartet nach $expected_codes."
        missing=1
      else
        echo "Erwartete Diagnose gemeldet: $code"
      fi
    done <"$expected_codes"
    [ "$missing" -eq 0 ] || exit 1
    if [ -d "$out" ] && find "$out" -name '*.grimpack' -print -quit | grep -q .; then
      echo "::error title=Pack trotz Diagnose::Zu \`$dir\` wurde ein Pack geschrieben, obwohl der Lauf Diagnosen hat."
      exit 1
    fi
    ;;
  *)
    echo "asset-gate: unbekannte Erwartung \`$expect\` (pass oder fail)." >&2
    exit 2
    ;;
esac
