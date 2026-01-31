#!/usr/bin/env bash
set -euo pipefail

echo "=== Validation finale du framework contractuel v1.5 (patched) ==="

# 1) Structure minimale requise
test -f "contract_warnings.py" || { echo "ERROR: contract_warnings.py manquant"; exit 1; }
test -f "pytest.ini" || { echo "ERROR: pytest.ini manquant"; exit 1; }

# validate_contract_warnings.sh est attendu par ton workflow
test -f "validate_contract_warnings.sh" || { echo "ERROR: validate_contract_warnings.sh manquant"; exit 1; }
chmod +x validate_contract_warnings.sh || true

echo "OK: fichiers racine présents"

# 2) Warnings (escalade / policy)
echo "== Test des catégories de warnings =="
./validate_contract_warnings.sh

# 3) Tests contractuels
export PHIO_INSTRUMENT="${PHIO_INSTRUMENT:-./phi_otimes_o_instrument_v0_1.py}"
export PHIO_CONTRACT_POLICY="${PHIO_CONTRACT_POLICY:-HONEST}"
export PHIO_TAU_POLICY="${PHIO_TAU_POLICY:-AT_LEAST_ONE}"

echo "== Tests contractuels CLI + zones =="
PYTHONPATH=. python -m pytest tests/test_00_contract_cli.py -v --tb=short
PYTHONPATH=. python -m pytest tests/test_08_zone_thresholds.py -v --tb=short

# 4) Baseline / non-régression
mkdir -p .contract
BASELINE_PATH=".contract/contract_baseline.json"
REGRESSION_TEST="tests/test_99_contract_regression.py"

# Si la baseline n'existe pas, on indique quoi faire.
# On ne casse pas forcément, car la stratégie dépend de ton environnement.
if [ ! -f "${BASELINE_PATH}" ]; then
  echo "WARN: baseline absente (${BASELINE_PATH})"
  if [ "${PHIO_UPDATE_BASELINE:-false}" = "true" ]; then
    if [ -f "${REGRESSION_TEST}" ]; then
      echo "INFO: génération baseline via ${REGRESSION_TEST} (PHIO_UPDATE_BASELINE=true)"
      PYTHONPATH=. python -m pytest "${REGRESSION_TEST}" -v --tb=short
    else
      echo "ERROR: PHIO_UPDATE_BASELINE=true mais ${REGRESSION_TEST} absent"
      exit 1
    fi
  else
    echo "INFO: PHIO_UPDATE_BASELINE=false -> non-régression ignorée (baseline absente)"
    exit 0
  fi
fi

# Baseline présente => on tente la non-régression, mais seulement si le test existe
echo "== Test de non-régression =="
if [ -f "${REGRESSION_TEST}" ]; then
  PYTHONPATH=. python -m pytest "${REGRESSION_TEST}" -v --tb=short
else
  echo "WARN: ${REGRESSION_TEST} absent -> non-régression ignorée"
fi

echo "=== OK ==="
