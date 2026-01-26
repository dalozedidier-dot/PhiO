#!/usr/bin/env bash
set -euo pipefail

echo "== Validate ContractWarning escalation =="

# Force ContractWarning to be treated as an error (exception)
export PYTHONWARNINGS="error::contract_warnings.ContractWarning"

python - <<'PY'
import warnings
from contract_warnings import ContractWarning

# This MUST raise (because PYTHONWARNINGS=error::contract_warnings.ContractWarning)
warnings.warn("contract violation", ContractWarning)
PY

echo "OK: ContractWarning escalated to exception"
