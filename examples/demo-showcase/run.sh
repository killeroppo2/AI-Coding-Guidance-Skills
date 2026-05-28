#!/bin/bash
set -e
cd "$(dirname "$0")/../.."
echo "=== Running Demo Showcase scenario (dry-run) ==="
python runner.py --goal "Build a URL shortener CLI with SQLite backend" --dry-run --verbose --max-iterations 15
echo "=== Demo Showcase scenario completed ==="
