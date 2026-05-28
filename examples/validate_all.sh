#!/bin/bash
set -e
SCRIPT_DIR="$(dirname "$0")"
echo "=== Validating all examples ==="
echo ""
PASS=0
FAIL=0
TOTAL=0

for dir in "$SCRIPT_DIR"/*/; do
    if [ -f "$dir/run.sh" ]; then
        name=$(basename "$dir")
        TOTAL=$((TOTAL + 1))
        printf "  [%d] %-30s " "$TOTAL" "$name"
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
echo "=== Summary ==="
echo "  Total:  $TOTAL"
echo "  Passed: $PASS"
echo "  Failed: $FAIL"
echo ""
if [ $FAIL -eq 0 ]; then
    echo "All examples passed."
else
    echo "Some examples failed. Review output above."
    exit 1
fi
