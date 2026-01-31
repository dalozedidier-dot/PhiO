#!/usr/bin/env bash
# tests/test_llm_collector_exhaustive.sh
#
# Règle structurante :
# - NE DOIT JAMAIS appeler run_collector_tests.sh (sinon récursion).
# - Doit exécuter directement : checks -> warnings -> collecteur -> tests éventuels.
# - validate_contract_warnings.sh est appelé via bash (pas besoin de +x).

set -Eeuo pipefail

if [[ "${TRACE:-0}" == "1" ]]; then
  set -x
fi

trap 'rc=$?;
  echo "❌ ERR rc=$rc file=${BASH_SOURCE[0]} line=$LINENO cmd=${BASH_COMMAND}" >&2;
  exit "$rc"
' ERR

log() { printf '%s\n' "$*" >&2; }

# Repo root
if command -v git >/dev/null 2>&1 && git rev-parse --show-toplevel >/dev/null 2>&1; then
  cd "$(git rev-parse --show-toplevel)"
else
  cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

# Logs
ART_DIR="${ART_DIR:-test-reports/collector}"
mkdir -p "$ART_DIR"
LOG_FILE="${LOG_FILE:-$ART_DIR/collector_exhaustive.log}"
exec > >(tee -a "$LOG_FILE") 2>&1

log "collector exhaustive start"
log "***"
log "bash=${BASH_VERSION}"
log "TRACE=${TRACE:-0}"
log "ART_DIR=${ART_DIR}"
log "LOG_FILE=${LOG_FILE}"
log "PWD=$(pwd)"

# Pré-checks
command -v python >/dev/null 2>&1 || { log "missing_cmd=python"; exit 1; }
[[ -f "contract_probe.py" ]] || { log "missing_file=contract_probe.py"; exit 1; }

# Compile rapide (fail-fast)
log "py_compile: start"
python -m py_compile contract_probe.py
log "py_compile: done"

# Baseline optionnelle (ne pas forcer en CI si tu veux un repo immuable)
if [[ "${GENERATE_BASELINE:-0}" == "1" ]]; then
  log "GENERATE_BASELINE=1"
  [[ -f "phi_otimes_o_instrument_v0_1.py" ]] || { log "missing_file=phi_otimes_o_instrument_v0_1.py"; exit 1; }
  mkdir -p .contract
  python contract_probe.py \
    --instrument ./phi_otimes_o_instrument_v0_1.py \
    --out .contract/contract_baseline.json
else
  log "GENERATE_BASELINE=0"
fi

# Contract warnings : via bash (ignore le bit +x)
if [[ -f "./validate_contract_warnings.sh" ]]; then
  log "validate_contract_warnings: start"
  bash ./validate_contract_warnings.sh
  log "validate_contract_warnings: done"
else
  log "validate_contract_warnings_skipped: missing_file"
fi

# Collecteur LLM : exécution directe
if [[ -f "scripts/phio_llm_collect.sh" ]]; then
  log "collector: scripts/phio_llm_collect.sh"
  bash scripts/phio_llm_collect.sh
else
  log "collector_missing: scripts/phio_llm_collect.sh"
  exit 1
fi

# Tests pytest collector si présents
if [[ -d "tests" ]] && ls tests/test_*collector*.py >/dev/null 2>&1; then
  log "pytest_collector: start"
  mkdir -p test-reports/test-results
  python -m pytest -q \
    tests/test_*collector*.py \
    --junitxml=test-reports/test-results/pytest-collector.xml
  log "pytest_collector: done"
else
  log "pytest_collector: none_detected"
fi

log "collector exhaustive end"
