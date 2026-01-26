#!/usr/bin/env bash
set -euo pipefail

echo "=== Validation finale du framework contractuel v1.5 ==="

# 1. Structure
test -f "contract_warnings.py" || { echo "✗ contract_warnings.py manquant"; exit 1; }
test -f "pytest.ini" || { echo "✗ pytest.ini manquant"; exit 1; }
echo "✓ Fichiers racine OK"

# 2. Warnings
echo "→ Test des catégories de warnings"
./validate_contract_warnings.sh

# 3. Tests contractuels
export PHIO_INSTRUMENT="${PHIO_INSTRUMENT:-./phi_otimes_o_instrument_v0_1.py}"
export PHIO_CONTRACT_POLICY="${PHIO_CONTRACT_POLICY:-HONEST}"
export PHIO_TAU_POLICY="${PHIO_TAU_POLICY:-AT_LEAST_ONE}"

echo "→ Tests contractuels CLI + zones"
python -m pytest tests/test_00_contract_cli.py -v --tb=short
python -m pytest tests/test_08_zone_thresholds.py -v --tb=short

# 4. Baseline
mkdir -p .contract
if [ ! -f ".contract/contract_baseline.json" ]; then
  echo "⚠️  Baseline manquante; pour la créer: PHIO_UPDATE_BASELINE=true pytest tests/test_99_contract_regression.py"
  exit 0
fi

echo "→ Test de non-régression"
python -m pytest tests/test_99_contract_regression.py -v --tb=short

echo "=== ✅ OK ==="
