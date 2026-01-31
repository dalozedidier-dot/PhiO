#!/usr/bin/env bash
set -euo pipefail

echo "Running traceability checks..."
python3 scripts/validate_traceability.py traceability_cases.json
echo "OK"
