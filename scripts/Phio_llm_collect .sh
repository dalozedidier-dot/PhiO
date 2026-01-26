#!/usr/bin/env bash
# scripts/phio_llm_collect.sh (v0.3.0)
# Collecte maximale de contexte (structure + fichiers clés + hashes + concat texte)
# Objectif : bundle lisible + traçable, sans secrets, sans modifier le repo.

set -euo pipefail

ROOT="${1:-.}"
ROOT="$(cd "$ROOT" && pwd)"
OUTDIR="${2:-"$ROOT/_llm_bundle"}"

# ---- Paramètres (overrides via env) ----
MAX_FILE_BYTES="${MAX_FILE_BYTES:-200000}"
MAX_FILE_LINES="${MAX_FILE_LINES:-1200}"
MAX_CONCAT_LINES="${MAX_CONCAT_LINES:-9000}"
INCLUDE_GIT="${INCLUDE_GIT:-1}"
INCLUDE_PIP_FREEZE="${INCLUDE_PIP_FREEZE:-0}"
INCLUDE_CONCAT="${INCLUDE_CONCAT:-1}"
INCLUDE_TEST_OUTPUTS="${INCLUDE_TEST_OUTPUTS:-0}"
STRICT="${STRICT:-0}"
QUIET="${QUIET:-0}"

log() { [ "$QUIET" = "1" ] || echo "$@"; }
safe_mkdir() { mkdir -p "$1"; }

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    echo "NO_SHA256_TOOL"
  fi
}

is_text_file() {
  if command -v file >/dev/null 2>&1; then
    file -b --mime-type "$1" | grep -Eq \
      '^text/|^application/(json|xml|yaml|x-yaml|toml|javascript|x-shellscript)$'
  else
    case "$1" in
      *.md|*.markdown|*.rst|*.txt|*.py|*.sh|*.yml|*.yaml|*.json|*.toml|*.ini|*.cfg|*.gitignore|*.sql|*.graphql|*.proto|*.avsc|*.ipynb)
        return 0 ;;
      *) return 1 ;;
    esac
  fi
}

# ---- Exclusions ----
EXCLUDE_DIRS=(
  "_llm_bundle"
  ".git"
  "__pycache__"
  ".pytest_cache"
  ".ruff_cache"
  "node_modules"
  "venv"
  ".venv"
  "dist"
  "build"
)

should_exclude_path() {
  local p="$1"
  for d in "${EXCLUDE_DIRS[@]}"; do
    case "$p" in
      "$d"/*|*/"$d"/*) return 0 ;;
    esac
  done
  return 1
}

# ---- Sorties ----
safe_mkdir "$OUTDIR"
BUNDLE="$OUTDIR/bundle"
safe_mkdir "$BUNDLE"

TREE="$OUTDIR/tree.txt"
META="$OUTDIR/meta.txt"
REPORT="$OUTDIR/missing_report.md"
MANIFEST="$OUTDIR/manifest.json"
CONCAT="$OUTDIR/all_text.txt"
ARCHIVE="$OUTDIR/phio_llm_bundle.tar.gz"

log "ROOT=$ROOT"
log "OUTDIR=$OUTDIR"

# ---- 1) Tree ----
log "-> tree.txt"
(
  cd "$ROOT"
  if [ -d ".git" ] && [ "$INCLUDE_GIT" = "1" ] && command -v git >/dev/null 2>&1; then
    git ls-files 2>/dev/null || true
  else
    find . -type f -print | sed 's|^\./||'
  fi
) | while IFS= read -r p; do
  should_exclude_path "$p" && continue
  echo "$p"
done | sort > "$TREE"

# ---- 2) Meta ----
log "-> meta.txt"
{
  echo "ROOT=$ROOT"
  date -Is 2>/dev/null || date
  echo "uname=$(uname -a 2>/dev/null || true)"
  echo "python=$(python3 -V 2>/dev/null || true)"
  echo "pip=$(python3 -m pip -V 2>/dev/null || true)"
  echo
  echo "[ENV names: PHIO_* redacted values]"
  (env | grep -E '^PHIO_' 2>/dev/null || true) | sed 's/=.*/=<REDACTED>/'
  echo
  if [ -d "$ROOT/.git" ] && [ "$INCLUDE_GIT" = "1" ] && command -v git >/dev/null 2>&1; then
    echo "[GIT]"
    (cd "$ROOT" && {
      echo "branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
      echo "head=$(git rev-parse HEAD 2>/dev/null || true)"
      echo "status:"
      git status --porcelain 2>/dev/null || true
    })
  fi
} > "$META"

# ---- 3) Copie fichiers/dossiers clés ----
log "-> bundle/ (copy key artifacts)"

KEY_FILES=(
  "README.md"
  "README_CONTRACT.md"
  "requirements.txt"
  "pyproject.toml"
  "pytest.ini"
  "run_tests.py"
  "run_all_tests.sh"
  "final_validation.sh"
  "validate_contract_warnings.sh"
  "contract_probe.py"
  "contract_warnings.py"
  "diagnostic.py"
  "extract_conventions.py"
  ".github/workflows/phi_ci.yml"
  ".githooks/pre-commit"
  ".githooks/pre-push"
  "scripts/dev-setup.sh"
  "scripts/phio_llm_collect.sh"
)

BASELINE_ARTIFACTS=(
  ".contract/contract_baseline.json"
  "baseline"
  "baselines"
  "testdata/golden"
  "test_data/golden"
  "fixtures"
)

copy_file_if_exists() {
  local rel="$1"
  local src="$ROOT/$rel"
  local dst="$BUNDLE/$rel"
  if [ -f "$src" ]; then
    safe_mkdir "$(dirname "$dst")"
    cp -p "$src" "$dst" 2>/dev/null || true
    return 0
  fi
  return 1
}

copy_dir_if_exists() {
  local rel="$1"
  local src="$ROOT/$rel"
  if [ -d "$src" ]; then
    safe_mkdir "$BUNDLE/$(dirname "$rel")"
    (cd "$ROOT" && tar -cf - "$rel" 2>/dev/null) | (cd "$BUNDLE" && tar -xf - 2>/dev/null)
    return 0
  fi
  return 1
}

MISSING=()

for p in "${KEY_FILES[@]}"; do
  copy_file_if_exists "$p" || MISSING+=("$p")
done

for p in "${BASELINE_ARTIFACTS[@]}"; do
  if [ -f "$ROOT/$p" ]; then
    copy_file_if_exists "$p" || true
  elif [ -d "$ROOT/$p" ]; then
    copy_dir_if_exists "$p" || true
  else
    MISSING+=("$p")
  fi
done

if [ -d "$ROOT/tests" ]; then
  copy_dir_if_exists "tests" || true
else
  MISSING+=("tests/ (directory)")
fi

[ -d "$ROOT/test_data" ] && copy_dir_if_exists "test_data" || true
[ -d "$ROOT/testdata" ] && copy_dir_if_exists "testdata" || true

if [ "$INCLUDE_TEST_OUTPUTS" = "1" ]; then
  for d in out test-results reports report; do
    [ -d "$ROOT/$d" ] && copy_dir_if_exists "$d" || true
  done
  for f in junit.xml pytest.xml results.xml results.json report.json; do
    [ -f "$ROOT/$f" ] && copy_file_if_exists "$f" || true
  done
fi

# ---- 4) Missing report ----
log "-> missing_report.md"

has_baseline="0"
[ -f "$ROOT/.contract/contract_baseline.json" ] && has_baseline="1"
{ [ -d "$ROOT/baseline" ] || [ -d "$ROOT/baselines" ]; } && has_baseline="1"
{ [ -d "$ROOT/testdata/golden" ] || [ -d "$ROOT/test_data/golden" ]; } && has_baseline="1"

tests_init_missing="0"
if [ -d "$ROOT/tests" ] && [ ! -f "$ROOT/tests/__init__.py" ]; then
  tests_init_missing="1"
fi

{
  echo "# Missing report"
  echo
  echo "ROOT: \`$ROOT\`"
  echo "Generated: $(date -Is 2>/dev/null || date)"
  echo
  echo "## Expected but missing"
  if [ "${#MISSING[@]}" -eq 0 ]; then
    echo "- (none)"
  else
    printf "%s\n" "${MISSING[@]}" | sort -u | sed 's/^/- /'
  fi
  echo
  echo "## Structural checks"
  if [ "$has_baseline" = "0" ]; then
    echo "- CRITICAL: no baseline/golden detected"
  else
    echo "- baseline/golden: detected"
  fi
  if [ "$tests_init_missing" = "1" ]; then
    echo "- tests package marker: MISSING (tests/__init__.py)"
  else
    echo "- tests package marker: ok"
  fi
  if [ -f "$ROOT/.github/workflows/phi_ci.yml" ]; then
    echo "- workflow: present"
  else
    echo "- workflow: missing"
  fi
} > "$REPORT"

if [ "$STRICT" = "1" ]; then
  if [ "$has_baseline" = "0" ] || [ ! -d "$ROOT/tests" ]; then
    log "STRICT=1 -> critical missing detected -> exit 1"
    exit 1
  fi
fi

# ---- 5) Manifest ----
log "-> manifest.json"

python3 - << 'PY' "$ROOT" "$OUTDIR" "$BUNDLE"
import os, sys, json, hashlib, datetime
ROOT, OUTDIR, BUNDLE = sys.argv[1:]

def sha256(path):
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return "ERROR"

entries = []

for fn in ("tree.txt", "meta.txt", "missing_report.md"):
    p = os.path.join(OUTDIR, fn)
    if os.path.exists(p):
        entries.append({"path": fn, "sha256": sha256(p), "bytes": os.path.getsize(p)})

for dirpath, _, filenames in os.walk(BUNDLE):
    for fn in filenames:
        p = os.path.join(dirpath, fn)
        rel = os.path.relpath(p, OUTDIR).replace("\\", "/")
        entries.append({"path": rel, "sha256": sha256(p), "bytes": os.path.getsize(p)})

manifest = {
    "root": ROOT,
    "generated": datetime.datetime.now().isoformat(),
    "count": len(entries),
    "entries": sorted(entries, key=lambda x: x["path"])
}

with open(os.path.join(OUTDIR, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
PY

# ---- 6) Concat texte ----
if [ "$INCLUDE_CONCAT" = "1" ]; then
  log "-> all_text.txt (concat text, bounded)"
  : > "$CONCAT"

  {
    echo "### CONCAT CONTEXT"
    echo "ROOT=$ROOT"
    echo "Generated=$(date -Is 2>/dev/null || date)"
    echo
    echo "===== FILE: meta.txt ====="
    sed -n "1,500p" "$META"
    echo
    echo "===== FILE: missing_report.md ====="
    sed -n "1,800p" "$REPORT"
    echo
  } >> "$CONCAT"

  while IFS= read -r rel; do
    src="$BUNDLE/$rel"
    [ -f "$src" ] || continue

    case "$rel" in
      *.pem|*.key|*.p12|*.pfx|*.env|*secrets*|*token*) continue ;;
    esac

    if is_text_file "$src"; then
      echo >> "$CONCAT"
      echo "===== FILE: $rel =====" >> "$CONCAT"

      bytes=$(wc -c < "$src" 2>/dev/null | tr -d ' ' || echo "0")
      if [ "$bytes" -gt "$MAX_FILE_BYTES" ] && [ "$bytes" -ne "0" ]; then
        echo "(skipped: $bytes bytes > MAX_FILE_BYTES=$MAX_FILE_BYTES)" >> "$CONCAT"
      else
        head -n "$MAX_FILE_LINES" "$src" 2>/dev/null >> "$CONCAT" || true
      fi
    fi
  done < <(cd "$BUNDLE" && find . -type f -print 2>/dev/null | sed 's|^\./||' | sort)

  tmp="$OUTDIR/.concat.tmp"
  head -n "$MAX_CONCAT_LINES" "$CONCAT" 2>/dev/null > "$tmp" || true
  mv "$tmp" "$CONCAT" 2>/dev/null || true
fi

# ---- 7) pip freeze ----
if [ "$INCLUDE_PIP_FREEZE" = "1" ]; then
  log "-> pip_freeze.txt"
  python3 -m pip freeze > "$OUTDIR/pip_freeze.txt" 2>/dev/null || true
fi

# ---- 8) Archive ----
log "-> archive"

tar -C "$OUTDIR" -czf "$ARCHIVE" \
  tree.txt meta.txt missing_report.md manifest.json \
  $( [ -f "$CONCAT" ] && echo "all_text.txt" ) \
  $( [ -f "$OUTDIR/pip_freeze.txt" ] && echo "pip_freeze.txt" ) \
  bundle

log "OK: $ARCHIVE"
log "OUTDIR: $OUTDIR"
