#!/bin/bash
set -e
cd "$(dirname "$0")/../.."
echo "=== Running API Service scenario (dry-run) ==="
python runner.py --goal "Build a FastAPI microservice with JWT authentication" --dry-run --max-iterations 10
echo "=== API Service scenario completed ==="
