#!/usr/bin/env bash
set -euo pipefail

# Validation contractuelle: la catégorie ContractWarning doit pouvoir être escaladée en exception.
# Le test est *positif* si une exception ContractWarning est levée quand on force le filtre.
python3 - <<'PY'
import warnings
from contract_warnings import ContractWarning

warnings.simplefilter("error", ContractWarning)

try:
    warnings.warn("contract violation", ContractWarning)
    raise SystemExit("❌ ContractWarning n'a PAS été escaladée en exception")
except ContractWarning:
    print("✅ OK: ContractWarning escaladée en exception")
PY
