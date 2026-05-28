#!/bin/bash
set -e
SCRIPT_DIR="$(dirname "$0")"
echo "=== Validating all examples ==="
PASS=0
FAIL=0

for dir in "$SCRIPT_DIR"/*/; do
    if [ -f "$dir/run.sh" ]; then
        name=$(basename "$dir")
        echo -n "  $name: "
        if bash "$dir/run.sh" > /dev/null 2>&1; then
            echo "PASS"
            PASS=$((PASS + 1))
        else
            echo "FAIL"
            FAIL=$((FAIL + 1))
        fi
    fi
done

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ] || exit 1
