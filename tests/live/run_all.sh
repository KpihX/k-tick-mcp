#!/usr/bin/env bash
# Lance tous les scripts live dans l'ordre.
# Arrête à la 1ère erreur si --stop-on-fail est passé.

set -euo pipefail
STOP=${1:-""}
PYTHON="/home/kpihx/.local/share/uv/tools/tick-mcp/bin/python3"
DIR="$(cd "$(dirname "$0")" && pwd)"

pass=0; fail=0

for script in "$DIR"/[01]*.py; do
    name=$(basename "$script")
    echo ""
    echo "════════════════════════════════════════════════════════"
    echo "  RUNNING: $name"
    echo "════════════════════════════════════════════════════════"
    if PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$DIR" "$PYTHON" "$script"; then
        pass=$((pass + 1))
    else
        fail=$((fail + 1))
        echo "  *** ECHEC dans $name ***"
        [[ "$STOP" == "--stop-on-fail" ]] && exit 1
    fi
done

echo ""
echo "════════════════════════════════════════════════════════"
echo "  TOTAL : $pass scripts OK  |  $fail scripts ECHEC"
echo "════════════════════════════════════════════════════════"
[[ $fail -eq 0 ]] && exit 0 || exit 1
