#!/usr/bin/env bash
set -e

source venv/bin/activate

echo "========================================"
echo "  Running Test Suite"
echo "========================================"
echo

python -m pytest -v

echo
echo "  All tests passed."
