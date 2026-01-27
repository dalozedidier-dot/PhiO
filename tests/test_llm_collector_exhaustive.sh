#!/usr/bin/env bash
# tests/test_llm_collector_exhaustive.sh
#
# IMPORTANT:
# - NE DOIT PAS appeler run_collector_tests.sh (sinon boucle).
# - Doit exécuter directement le collecteur (ex: scripts/phio_llm_collect.sh) et/ou des tests.

set -Eeuo pipefail

if [[ "${TRACE:-0}" == "1" ]]; then
  set -x
fi

trap 'rc=$?;
  echo "❌ ERR rc=$rc file=${BASH_SOURCE[0]} line=$LINENO cmd=${BASH_COMMAND}" >&2;
  exit "$rc"
' ERR

log() { printf '%s\n' "$*" >&2; }

# repo root
if command -v git >/dev/null 2>&1 && git rev-parse --show-toplevel >/dev/null 2>&1; then
  cd "$(git rev-parse --show-toplevel)"
else
  cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

# logs
ART_DIR="${ART_DIR:-test-reports/collector}"
mkdir -p "$ART_DIR"
LOG_FILE="${LOG_FILE:-$ART_DIR/collector_exhaustive.log}"
exec > >(tee -a "$LOG_FILE") 2>&1

log "collector exhaustive start"
log "***"
log "bash=${BASH_VERSION}"
log "trace=${TRACE:-0}"
log "art_dir=${ART_DIR}"
log "log_file=${LOG_FILE}"

# prérequis minimaux
command -v python >/dev/null 2>&1

# compile rapide (fail-fast)
log "py_compile: start"
python -m py_compile contract_probe.py
log "py_compile: done"

# baseline optionnelle (ne change rien si GENERATE_BASELINE=0)
if [[ "${GENERATE_BASELINE:-0}" == "1" ]]; then
  log "generate_baseline=1"
  mkdir -p .contract
  python contract_probe.py \
    --instrument ./scripts/phi_otimes_o_instrument_v0_1.py \
    --out .contract/contract_baseline.json
else
  log "generate_baseline=0"
fi

# warnings: on exécute VIA bash même si le bit +x manque
if [[ -f "./validate_contract_warnings.sh" ]]; then
  log "validate_contract_warnings: start"
  bash ./validate_contract_warnings.sh
  log "validate_contract_warnings: done"
else
  log "validate_contract_warnings_skipped: missing_file"
fi

# ---- EXÉCUTION COLLECTEUR (directe, sans wrapper) ----
# Ici on suppose que le collecteur est scripts/phio_llm_collect.sh (vu dans ton log).
# Si ce script requiert des args, tu peux les passer via env (INPUT/OUTDIR etc.)
if [[ -f "scripts/phio_llm_collect.sh" ]]; then
  log "collector_script: scripts/phio_llm_collect.sh"
  bash scripts/phio_llm_collect.sh
else
  log "collector_script_missing"
  exit 1
fi

# Option: tests pytest collector si présents
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
