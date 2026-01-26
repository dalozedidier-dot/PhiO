#!/usr/bin/env bash
set -euo pipefail

echo "=== Validation des catégories de warnings ==="

# Test 1: ContractWarning doit être une erreur quand on le promeut en erreur
echo "Test 1: ContractWarning doit lever une exception (mode -W error)..."
python -W "error::contract_warnings.ContractWarning" - <<'PY'
import warnings
from contract_warnings import ContractWarning
try:
    warnings.warn("contract violation", ContractWarning)
    raise SystemExit("ÉCHEC: ContractWarning n'a pas levé d'exception")
except ContractWarning:
    print("✓ ContractWarning traité comme erreur")
PY

# Test 2: ContractInfoWarning ne doit PAS être une erreur par défaut
echo "Test 2: ContractInfoWarning ne doit pas lever d'exception (par défaut)..."
python - <<'PY'
import warnings
from contract_warnings import ContractInfoWarning
warnings.warn("info only", ContractInfoWarning)
print("✓ ContractInfoWarning émis sans exception")
PY

echo "=== OK ==="
