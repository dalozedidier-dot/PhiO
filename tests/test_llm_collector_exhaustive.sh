#!/usr/bin/env bash
# tests/test_llm_collector_exhaustive.sh
#
# But:
# - Exécuter une suite "collector exhaustive" sans recursion.
# - Observabilité: trace optionnelle + trap ERR (ligne/commande).
# - Bornage: timeout global optionnel.
#
# IMPORTANT:
# - Ce script NE DOIT JAMAIS appeler run_collector_tests.sh (sinon boucle).
# - Le wrapper (run_collector_tests.sh) peut appeler CE script, pas l'inverse.

set -Eeuo pipefail

# Trace si TRACE=1
if [[ "${TRACE:-0}" == "1" ]]; then
  set -x
fi

trap 'rc=$?;
  echo "❌ ERR rc=$rc file=${BASH_SOURCE[0]} line=$LINENO cmd=${BASH_COMMAND}" >&2;
  exit "$rc"
' ERR

log() { printf '%s\n' "$*" >&2; }

# --- Repo root ---
resolve_repo_root() {
  if command -v git >/dev/null 2>&1 && git rev-parse --show-toplevel >/dev/null 2>&1; then
    git rev-parse --show-toplevel
    return 0
  fi
  local here
  here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  (cd "$here/.." && pwd)
}

REPO_ROOT="$(resolve_repo_root)"
cd "$REPO_ROOT"

# --- Artefacts/logs ---
ART_DIR="${ART_DIR:-test-reports/collector}"
mkdir -p "$ART_DIR"
LOG_FILE="${LOG_FILE:-$ART_DIR/collector_exhaustive.log}"

# Log vers console + fichier
exec > >(tee -a "$LOG_FILE") 2>&1

log "=== collector exhaustive start ==="
log "pwd=$(pwd)"
log "bash_version=${BASH_VERSION}"
log "TRACE=${TRACE:-0}"
log "ART_DIR=$ART_DIR"
log "LOG_FILE=$LOG_FILE"

# --- Pré-checks ---
require_cmd() { command -v "$1" >/dev/null 2>&1 || { log "missing_cmd=$1"; return 1; }; }
require_file() { [[ -f "$1" ]] || { log "missing_file=$1"; return 1; }; }

require_cmd bash
require_cmd python

# Ces fichiers doivent exister pour ce script (ajuste si besoin)
require_file "contract_probe.py"

# --- Compilation rapide (fail-fast) ---
log "py_compile: start"
python -m py_compile contract_probe.py

# Optionnels
for maybe in \
  "phi_otimes_o_instrument_v0_1.py" \
  "contract_warnings.py" \
  "diagnostic.py" \
  "extract_conventions.py"
do
  if [[ -f "$maybe" ]]; then
    python -m py_compile "$maybe"
    log "py_compile_optional_ok=$maybe"
  else
    log "py_optional_missing=$maybe"
  fi
done
log "py_compile: done"

# --- (Option) baseline ---
if [[ "${GENERATE_BASELINE:-0}" == "1" ]]; then
  log "GENERATE_BASELINE=1"
  require_file "phi_otimes_o_instrument_v0_1.py"
  mkdir -p .contract
  python contract_probe.py \
    --instrument ./phi_otimes_o_instrument_v0_1.py \
    --out .contract/contract_baseline.json

  python - <<'PY'
import json
p = ".contract/contract_baseline.json"
d = json.load(open(p, "r", encoding="utf-8"))
if not isinstance(d, dict) or len(d) == 0:
    raise SystemExit("baseline_invalid_or_empty")
required = ["contract_version", "compliance", "cli", "zones", "formula"]
missing = [k for k in required if k not in d]
if missing:
    raise SystemExit(f"baseline_missing_keys={missing}")
print("baseline_ok")
PY
else
  log "GENERATE_BASELINE=0"
fi

# --- Validation contract warnings ---
# IMPORTANT: on ne dépend pas du bit +x ; on exécute via bash si le fichier existe.
if [[ -f "./validate_contract_warnings.sh" ]]; then
  log "validate_contract_warnings: start"
  bash ./validate_contract_warnings.sh
  log "validate_contract_warnings: done"
else
  log "validate_contract_warnings: skipped (missing file)"
fi

# --- Exécution des tests collector ---
# Règle: ce script exécute DIRECTEMENT des tests (pytest ou script dédié),
# sans jamais appeler run_collector_tests.sh.
EXIT_CODE=0

if [[ -x "./tests/run_llm_collector_exhaustive_internal.sh" ]]; then
  # Si tu as un script interne dédié, appelle-le ici (nom explicite pour éviter la récursion).
  log "internal_collector_script: start"
  ./tests/run_llm_collector_exhaustive_internal.sh
  log "internal_collector_script: done"
elif [[ -d "tests" ]] && ls tests/test_*collector*.py >/dev/null 2>&1; then
  log "pytest_collector: start"
  mkdir -p test-reports/test-results
  python -m pytest -q \
    tests/test_*collector*.py \
    --junitxml=test-reports/test-results/pytest-collector.xml
  log "pytest_collector: done"
else
  log "no_collector_tests_detected"
  EXIT_CODE=1
fi

log "post_state: git_status_porcelain"
git status --porcelain || true

log "=== collector exhaustive end rc=$EXIT_CODE ==="
exit "$EXIT_CODE"
