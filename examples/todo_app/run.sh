#!/bin/bash
set -e
cd "$(dirname "$0")/../.."
echo "=== Running Todo App scenario (dry-run) ==="
python runner.py --goal "Build a Python Flask todo app with REST API and SQLite" --dry-run --max-iterations 10
echo "=== Todo App scenario completed ==="
