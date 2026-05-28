#!/bin/bash
set -e
cd "$(dirname "$0")/../.."
echo "=== Running CLI Tool scenario (dry-run) ==="
python runner.py --goal "Build a CLI file organizer that sorts files by extension" --dry-run --max-iterations 10
echo "=== CLI Tool scenario completed ==="
