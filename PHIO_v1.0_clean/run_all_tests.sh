#!/bin/sh
set -e

echo "🚀 PhiO – run_all_tests (contract v1.5)"

: "${PHIO_INSTRUMENT:=../phi_otimes_o_instrument_v0_1.py}"
export PHIO_INSTRUMENT

: "${PHIO_CONTRACT_POLICY:=HONEST}"
: "${PHIO_TAU_POLICY:=AT_LEAST_ONE}"
: "${PHIO_ALLOW_EXEC_EXTRACTION:=false}"
export PHIO_CONTRACT_POLICY PHIO_TAU_POLICY PHIO_ALLOW_EXEC_EXTRACTION

mkdir -p test-results || true

echo "=== 1) Contract validation (includes baseline check) ==="
chmod +x final_validation.sh validate_contract_warnings.sh
./final_validation.sh

echo "=== 2) Full pytest (includes contract + functional if present) ==="
python -m pytest tests/ -v --tb=short

echo "✅ Done"
