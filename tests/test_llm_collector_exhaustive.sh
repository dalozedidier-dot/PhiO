#!/usr/bin/env bash
# tests/test_llm_collector_exhaustive.sh
#
# Objectif :
# - Exécuter une batterie "exhaustive" du collecteur LLM avec observabilité maximale.
# - Échouer de façon explicite (ligne + commande) au premier défaut (mode strict).
# - Produire un log exploitable (stdout/stderr) et un exit code non ambigu.
#
# Hypothèses minimales :
# - Bash disponible
# - Python disponible si des tests Python existent
# - Le script est lancé depuis n'importe où (il se recale sur le repo root)

set -Eeuo pipefail

# --- Observabilité ---
# Active xtrace si TRACE=1
if [[ "${TRACE:-0}" == "1" ]]; then
  set -x
fi

# Trap d'erreur : ligne + commande
trap 'rc=$?;
  echo "ERROR: rc=$rc file=${BASH_SOURCE[0]} line=$LINENO cmd=${BASH_COMMAND}" >&2;
  exit "$rc"
' ERR

log() { printf '%s\n' "$*" >&2; }

# --- Détermination du repo root ---
resolve_repo_root() {
  if command -v git >/dev/null 2>&1 && git rev-parse --show-toplevel >/dev/null 2>&1; then
    git rev-parse --show-toplevel
    return 0
  fi
  # Fallback : parent du dossier tests/
  local here
  here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  (cd "$here/.." && pwd)
}

REPO_ROOT="$(resolve_repo_root)"
cd "$REPO_ROOT"

# --- Logs / artefacts ---
ART_DIR="${ART_DIR:-test-reports/collector}"
mkdir -p "$ART_DIR"
LOG_FILE="${LOG_FILE:-$ART_DIR/collector_exhaustive.log}"

# Redirection globale vers log + console
exec > >(tee -a "$LOG_FILE") 2>&1

log "collector exhaustive start"
log "pwd=$(pwd)"
log "bash=${BASH_VERSION}"
log "trace=${TRACE:-0}"
log "art_dir=$ART_DIR"
log "log_file=$LOG_FILE"

# --- Pré-checks stricts (échoue si prérequis manquants) ---
require_file() {
  local p="$1"
  if [[ ! -f "$p" ]]; then
    log "missing_file=$p"
    return 1
  fi
}

require_cmd() {
  local c="$1"
  if ! command -v "$c" >/dev/null 2>&1; then
    log "missing_cmd=$c"
    return 1
  fi
}

# Ajuste la liste selon ton repo réel.
# Ici on met des prérequis "collecteur" typiques, et on échoue si absents.
REQUIRED_FILES=(
  "contract_probe.py"
  "validate_contract_warnings.sh"
)

for f in "${REQUIRED_FILES[@]}"; do
  require_file "$f"
done

require_cmd bash
require_cmd python

# --- (Option) Installation deps si le script est utilisé en local ---
# En CI, préférer une step dédiée.
if [[ "${AUTO_PIP_INSTALL:-0}" == "1" ]]; then
  log "auto_pip_install=1"
  python -m pip install --upgrade pip
  if [[ -f requirements.txt ]]; then
    python -m pip install -r requirements.txt
  fi
fi

# --- Compilation rapide (fail fast) ---
log "py_compile: start"
python -m py_compile contract_probe.py

# Compile des modules collecteur si présents (sinon n'échoue pas)
for maybe in \
  "phi_otimes_o_instrument_v0_1.py" \
  "contract_warnings.py" \
  "diagnostic.py" \
  "extract_conventions.py"
do
  if [[ -f "$maybe" ]]; then
    python -m py_compile "$maybe"
  else
    log "py_optional_missing=$maybe"
  fi
done
log "py_compile: done"

# --- Génération baseline (optionnelle) ---
# Si tu veux rendre le test indépendant d'un état repo, active GENERATE_BASELINE=1
if [[ "${GENERATE_BASELINE:-0}" == "1" ]]; then
  log "generate_baseline=1"
  require_file "phi_otimes_o_instrument_v0_1.py"
  mkdir -p .contract
  python contract_probe.py \
    --instrument ./phi_otimes_o_instrument_v0_1.py \
    --out .contract/contract_baseline.json

  # Vérification minimale
  python - <<'PY'
import json
p = ".contract/contract_baseline.json"
with open(p, "r", encoding="utf-8") as f:
    d = json.load(f)
if not isinstance(d, dict) or len(d) == 0:
    raise SystemExit("baseline_invalid_or_empty")
required = ["contract_version", "compliance", "cli", "zones", "formula"]
missing = [k for k in required if k not in d]
if missing:
    raise SystemExit(f"baseline_missing_keys={missing}")
print("baseline_ok")
PY
else
  log "generate_baseline=0"
fi

# --- Validation contract warnings (si script + module dispo) ---
# Ici : on exécute, mais on rend l’échec explicite si ImportError sur contract_warnings.py.
if [[ -x "./validate_contract_warnings.sh" ]]; then
  log "validate_contract_warnings: start"
  ./validate_contract_warnings.sh
  log "validate_contract_warnings: done"
else
  log "validate_contract_warnings_skipped: not_executable"
fi

# --- Tests collecteur : stratégie adaptive ---
# 1) Si un script dédié existe : run_collector_tests.sh
# 2) Sinon : pytest sur un pattern collector si présent
# 3) Sinon : échoue explicitement (exhaustive == pas de test == erreur)
EXIT_CODE=0

if [[ -x "./run_collector_tests.sh" ]]; then
  log "run_collector_tests.sh: start"
  ./run_collector_tests.sh
  log "run_collector_tests.sh: done"
elif [[ -d "tests" ]]; then
  # Détection simple : un fichier test contenant "collector" dans son nom
  if ls tests/test_*collector*.py >/dev/null 2>&1; then
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
else
  log "tests_dir_missing"
  EXIT_CODE=1
fi

# --- Post-state minimal ---
log "post_state: git_status_porcelain"
git status --porcelain || true

log "collector exhaustive end rc=$EXIT_CODE"
exit "$EXIT_CODE"
