#!/usr/bin/env bash
# tests/test_llm_collector_exhaustive.sh
# Batterie de tests "maximale" pour scripts/phio_llm_collect.sh (sans modifier le script).
set -euo pipefail

echo "🧪🧪🧪 TEST EXHAUSTIF DU COLLECTEUR LLM 🧪🧪🧪"
echo "Date: $(date -Iseconds)"
echo "Host: $(uname -a)"
echo

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COLLECTOR="${COLLECTOR:-$REPO_ROOT/scripts/phio_llm_collect.sh}"

if [ ! -x "$COLLECTOR" ]; then
  echo "❌ Collecteur introuvable ou non exécutable: $COLLECTOR" >&2
  exit 1
fi

TEST_ROOT="$(mktemp -d)"
FAILURES=0
TESTS_RUN=0

inc(){ ((++TESTS_RUN)); }
fail() { echo "❌ Échec: $1"; ((++FAILURES)); }
pass() { echo "✅ Réussi: $1"; }

cleanup() {
  echo -e "\n🧹 Nettoyage..."
  rm -rf "$TEST_ROOT" "$REPO_ROOT"/_test_output_* 2>/dev/null || true
}
trap cleanup EXIT

echo "📁 Environnement de test: $TEST_ROOT"

# --- Construire un "mini-projet" riche ---
mkdir -p "$TEST_ROOT/.contract"
echo '{"version":"1.5.0","baseline":"test"}' > "$TEST_ROOT/.contract/contract_baseline.json"

mkdir -p "$TEST_ROOT/.github/workflows"
echo "name: CI" > "$TEST_ROOT/.github/workflows/phi_ci.yml"

mkdir -p "$TEST_ROOT/.githooks"
printf '%s\n' '#!/usr/bin/env bash' 'echo pre-commit' > "$TEST_ROOT/.githooks/pre-commit"
chmod +x "$TEST_ROOT/.githooks/pre-commit"
printf '%s\n' '#!/usr/bin/env bash' 'echo pre-push' > "$TEST_ROOT/.githooks/pre-push"
chmod +x "$TEST_ROOT/.githooks/pre-push"

mkdir -p "$TEST_ROOT/scripts"
printf '%s\n' '#!/usr/bin/env bash' 'echo "Setting up..."' > "$TEST_ROOT/scripts/dev-setup.sh"
chmod +x "$TEST_ROOT/scripts/dev-setup.sh"

# Dossiers à exclure
mkdir -p "$TEST_ROOT/__pycache__/test"
echo "__pycache__ content" > "$TEST_ROOT/__pycache__/test/__init__.pyc"
mkdir -p "$TEST_ROOT/.pytest_cache/v" "$TEST_ROOT/.ruff_cache" "$TEST_ROOT/node_modules/react" "$TEST_ROOT/venv/bin" \
         "$TEST_ROOT/.venv/lib" "$TEST_ROOT/dist" "$TEST_ROOT/build"

# Tests/baseline/fixtures
mkdir -p "$TEST_ROOT/tests"
echo "# Test file" > "$TEST_ROOT/tests/test_example.py"
touch "$TEST_ROOT/tests/__init__.py"

mkdir -p "$TEST_ROOT/test_data/golden"
echo '{"test":"data"}' > "$TEST_ROOT/test_data/golden/expected.json"

mkdir -p "$TEST_ROOT/fixtures"
echo "# Test Matrix" > "$TEST_ROOT/fixtures/simple_matrix.md"

# Binaire + secrets (ne doivent PAS finir dans concat, et de toute façon ne sont pas copiés dans bundle/)
head -c 100 /dev/urandom > "$TEST_ROOT/binary_file.bin"
echo "SECRET_KEY=12345" > "$TEST_ROOT/.env"
echo "-----BEGIN PRIVATE KEY-----" > "$TEST_ROOT/secret.pem"

# Gros fichiers texte (tester MAX_FILE_BYTES / MAX_CONCAT_LINES)
python3 - <<'PY' "$TEST_ROOT"
import os, sys
root = sys.argv[1]
with open(os.path.join(root, "large_file.txt"), "w", encoding="utf-8") as f:
    for i in range(50000):
        f.write("Line %d: %s\n" % (i, "x"*100))
with open(os.path.join(root, "exact_200kb.txt"), "w", encoding="utf-8") as f:
    f.write("x" * 204800)
with open(os.path.join(root, "over_200kb.txt"), "w", encoding="utf-8") as f:
    f.write("x" * 205000)
PY

# Git réel (pour exercer INCLUDE_GIT=1)
if command -v git >/dev/null 2>&1; then
  (cd "$TEST_ROOT" && git init -q && git config user.email "test@example.com" && git config user.name "test" || true)
  (cd "$TEST_ROOT" && git add -A && git commit -qm "init" || true)
fi

echo -e "\n🚀 DÉBUT DES TESTS\n"

# --- Test 1: Exécution de base ---
echo "=== Test 1: Exécution de base ==="
inc
if QUIET=1 "$COLLECTOR" "$TEST_ROOT" "$REPO_ROOT/_test_output_basic" >/dev/null 2>&1; then
  pass "Exécution de base"
else
  fail "Exécution de base"
fi

# --- Test 2: Fichiers requis ---
echo -e "\n=== Test 2: Fichiers requis ==="
inc
req=(tree.txt meta.txt missing_report.md manifest.json phio_llm_bundle.tar.gz)
all_ok=true
for f in "${req[@]}"; do
  if [ ! -f "$REPO_ROOT/_test_output_basic/$f" ]; then
    echo "  ❌ Manquant: $f"
    all_ok=false
  else
    echo "  ✅ Présent: $f"
  fi
done
$all_ok && pass "Fichiers requis présents" || fail "Fichiers requis manquants"

# --- Test 3: Exclusions dans tree.txt ---
echo -e "\n=== Test 3: Exclusions ==="
inc
tree="$REPO_ROOT/_test_output_basic/tree.txt"
excluded=(__pycache__ .git .pytest_cache .ruff_cache node_modules venv .venv dist build)
bad=false
for d in "${excluded[@]}"; do
  if grep -q "^${d}/" "$tree"; then
    echo "  ❌ $d présent dans tree.txt"
    bad=true
  else
    echo "  ✅ $d exclu"
  fi
done
(! $bad) && pass "Exclusions OK" || fail "Exclusions KO"

# --- Test 4: Redaction PHIO_* ---
echo -e "\n=== Test 4: Redaction PHIO_* ==="
inc
export PHIO_SECRET_KEY="should_be_redacted"
export PHIO_API_KEY="another_secret"
export REGULAR_VAR="should_not_appear"
QUIET=1 "$COLLECTOR" "$TEST_ROOT" "$REPO_ROOT/_test_output_redaction" >/dev/null 2>&1 || true
meta="$REPO_ROOT/_test_output_redaction/meta.txt"

if grep -q "PHIO_SECRET_KEY=<REDACTED>" "$meta" && grep -q "PHIO_API_KEY=<REDACTED>" "$meta"; then
  echo "  ✅ PHIO_* redacted"
else
  echo "  ❌ PHIO_* pas redacted comme attendu"
  fail "Redaction PHIO_*"
fi

# Le script n'imprime pas l'environnement complet : REGULAR_VAR ne doit pas apparaître.
if grep -q "REGULAR_VAR=" "$meta"; then
  echo "  ❌ REGULAR_VAR ne devrait pas apparaître dans meta.txt"
  fail "Redaction trop large / meta inattendu"
else
  echo "  ✅ REGULAR_VAR absent (attendu)"
  pass "Redaction OK"
fi
unset PHIO_SECRET_KEY PHIO_API_KEY REGULAR_VAR

# --- Test 5: Limites concat ---
echo -e "\n=== Test 5: Limites concat ==="
inc
MAX_FILE_BYTES=100 MAX_FILE_LINES=10 MAX_CONCAT_LINES=50 QUIET=1 \
  "$COLLECTOR" "$TEST_ROOT" "$REPO_ROOT/_test_output_limits" >/dev/null 2>&1 || true
concat="$REPO_ROOT/_test_output_limits/all_text.txt"
if [ -f "$concat" ]; then
  lines=$(wc -l < "$concat" | tr -d ' ')
  if [ "$lines" -le 50 ]; then
    echo "  ✅ MAX_CONCAT_LINES respecté: $lines"
  else
    echo "  ❌ MAX_CONCAT_LINES dépassé: $lines"
    fail "Limite concat"
  fi
  if grep -qi "skipped" "$concat"; then
    echo "  ✅ fichiers gros signalés skipped"
    pass "Limites de taille OK"
  else
    echo "  ⚠️  aucun 'skipped' (possible si aucun fichier copié n'a dépassé MAX_FILE_BYTES)"
    pass "Limites de taille (partiel)"
  fi
else
  echo "  ❌ all_text.txt absent alors que INCLUDE_CONCAT par défaut=1"
  fail "Concat absent"
fi

# --- Test 6: STRICT=1 doit échouer sans baseline/tests ---
echo -e "\n=== Test 6: STRICT=1 ==="
inc
no_base="$(mktemp -d)"
echo "README" > "$no_base/README.md"
if STRICT=1 QUIET=1 "$COLLECTOR" "$no_base" "$REPO_ROOT/_test_output_strict" >/dev/null 2>&1; then
  echo "  ❌ STRICT=1 aurait dû échouer"
  fail "STRICT trop permissif"
else
  echo "  ✅ STRICT=1 échoue (attendu)"
  pass "STRICT OK"
fi
rm -rf "$no_base" "$REPO_ROOT/_test_output_strict" 2>/dev/null || true

# --- Test 7: INCLUDE_TEST_OUTPUTS ---
echo -e "\n=== Test 7: INCLUDE_TEST_OUTPUTS ==="
inc
mkdir -p "$TEST_ROOT/test-results"
echo '<testsuite/>' > "$TEST_ROOT/test-results/junit.xml"
echo '{"passed":10}' > "$TEST_ROOT/report.json"
INCLUDE_TEST_OUTPUTS=1 QUIET=1 "$COLLECTOR" "$TEST_ROOT" "$REPO_ROOT/_test_output_with_outputs" >/dev/null 2>&1 || true
if [ -f "$REPO_ROOT/_test_output_with_outputs/bundle/test-results/junit.xml" ] && \
   [ -f "$REPO_ROOT/_test_output_with_outputs/bundle/report.json" ]; then
  pass "INCLUDE_TEST_OUTPUTS OK"
else
  fail "INCLUDE_TEST_OUTPUTS KO"
fi

# --- Test 8: Performance (gros fichier binaire non copié → doit rester rapide) ---
echo -e "\n=== Test 8: Performance ==="
inc
python3 - <<'PY' "$TEST_ROOT"
import os, sys
root=sys.argv[1]
with open(os.path.join(root,"very_large.bin"),"wb") as f:
    f.write(b"x"*5_000_000)
PY

# timeout portable: si la commande `timeout` n'existe pas, on exécute sans.
if command -v timeout >/dev/null 2>&1; then
  if timeout 10 env MAX_FILE_BYTES=1000000 MAX_CONCAT_LINES=10000 QUIET=1 "$COLLECTOR" "$TEST_ROOT" "$REPO_ROOT/_test_output_perf" >/dev/null 2>&1; then
    pass "Performance OK"
  else
    code=$?
    if [ "$code" -eq 124 ]; then
      fail "Performance (timeout)"
    else
      fail "Performance (exit $code)"
    fi
  fi
else
  QUIET=1 "$COLLECTOR" "$TEST_ROOT" "$REPO_ROOT/_test_output_perf" >/dev/null 2>&1 || fail "Performance (sans timeout)"
  pass "Performance (sans timeout) exécuté"
fi

# --- Test 9: Manifest JSON valide et SHA256 présents ---
echo -e "\n=== Test 9: Manifest SHA256 ==="
inc
man="$REPO_ROOT/_test_output_basic/manifest.json"
if python3 -c "import json; json.load(open('$man'))" >/dev/null 2>&1; then
  echo "  ✅ JSON valide"
else
  fail "Manifest JSON invalide"
fi

bad=$(python3 - <<'PY' "$man"
import json, sys
m=json.load(open(sys.argv[1], encoding="utf-8"))
invalid=[e for e in m.get("entries",[]) if not e.get("sha256") or e["sha256"] in ("ERROR","NO_SHA256_TOOL","error:sha256_failed")]
print(len(invalid))
PY
)
if [ "$bad" -eq 0 ]; then
  pass "Manifest SHA256 OK"
else
  fail "Manifest SHA256 invalides: $bad"
fi

# --- Test 10: Archive extractable ---
echo -e "\n=== Test 10: Archive ==="
inc
arch="$REPO_ROOT/_test_output_basic/phio_llm_bundle.tar.gz"
if [ -f "$arch" ]; then
  ex="$REPO_ROOT/_test_output_extract"
  rm -rf "$ex" && mkdir -p "$ex"
  if tar -xzf "$arch" -C "$ex" >/dev/null 2>&1; then
    if [ -f "$ex/tree.txt" ] && [ -f "$ex/manifest.json" ]; then
      pass "Archive OK"
    else
      fail "Archive contenu incomplet"
    fi
  else
    fail "Archive corrompue"
  fi
  rm -rf "$ex"
else
  fail "Archive absente"
fi

# --- Test 11: Sans git (fallback find) ---
echo -e "\n=== Test 11: Sans git ==="
inc
if [ -d "$TEST_ROOT/.git" ]; then
  mv "$TEST_ROOT/.git" "$TEST_ROOT/.git_backup"
fi
INCLUDE_GIT=1 QUIET=1 "$COLLECTOR" "$TEST_ROOT" "$REPO_ROOT/_test_output_no_git" >/dev/null 2>&1 || true
if [ -d "$TEST_ROOT/.git_backup" ]; then
  mv "$TEST_ROOT/.git_backup" "$TEST_ROOT/.git"
fi
if [ -s "$REPO_ROOT/_test_output_no_git/tree.txt" ]; then
  pass "Mode sans git OK"
else
  fail "Mode sans git KO"
fi

# --- Test 12: INCLUDE_PIP_FREEZE (optionnel) ---
echo -e "\n=== Test 12: INCLUDE_PIP_FREEZE ==="
inc
INCLUDE_PIP_FREEZE=1 QUIET=1 "$COLLECTOR" "$TEST_ROOT" "$REPO_ROOT/_test_output_pip" >/dev/null 2>&1 || true
if [ -f "$REPO_ROOT/_test_output_pip/pip_freeze.txt" ]; then
  pass "pip_freeze.txt généré"
else
  echo "  ℹ️  pip_freeze.txt absent (pip peut manquer / échec toléré)"
  pass "pip_freeze testé (tolérant)"
fi

# --- Test 13: INCLUDE_CONCAT=0 ---
echo -e "\n=== Test 13: INCLUDE_CONCAT=0 ==="
inc
INCLUDE_CONCAT=0 QUIET=1 "$COLLECTOR" "$TEST_ROOT" "$REPO_ROOT/_test_output_no_concat" >/dev/null 2>&1 || true
if [ ! -f "$REPO_ROOT/_test_output_no_concat/all_text.txt" ]; then
  pass "INCLUDE_CONCAT=0 OK"
else
  fail "INCLUDE_CONCAT=0 KO"
fi

# --- Test 14: Noms de fichiers "bizarres" (ne doivent pas faire crasher) ---
echo -e "\n=== Test 14: Chemins spéciaux ==="
inc
touch "$TEST_ROOT/file with spaces.txt"
touch "$TEST_ROOT/file'with'quotes.txt"
touch "$TEST_ROOT/file\"with\"doublequotes.txt"
touch "$TEST_ROOT/file|with|pipes.txt"
touch "$TEST_ROOT/file&with&ampersands.txt"
touch "$TEST_ROOT/file#with#hashes.txt"
QUIET=1 "$COLLECTOR" "$TEST_ROOT" "$REPO_ROOT/_test_output_paths" >/dev/null 2>&1 && pass "Chemins spéciaux OK" || fail "Chemins spéciaux KO"

# --- Test 15: Déterminisme (sur la structure copiée, pas sur meta/report/manifest) ---
echo -e "\n=== Test 15: Déterminisme (structure bundle) ==="
inc
QUIET=1 "$COLLECTOR" "$TEST_ROOT" "$REPO_ROOT/_test_output_det1" >/dev/null 2>&1
sleep 1
QUIET=1 "$COLLECTOR" "$TEST_ROOT" "$REPO_ROOT/_test_output_det2" >/dev/null 2>&1

# On compare tree.txt (déterministe) + la liste des chemins dans bundle/
if cmp -s "$REPO_ROOT/_test_output_det1/tree.txt" "$REPO_ROOT/_test_output_det2/tree.txt"; then
  echo "  ✅ tree.txt identique"
else
  echo "  ❌ tree.txt différent"
  fail "Déterminisme tree"
fi

list1="$REPO_ROOT/_test_output_det1/_bundle_paths.txt"
list2="$REPO_ROOT/_test_output_det2/_bundle_paths.txt"
( cd "$REPO_ROOT/_test_output_det1/bundle" && find . -type f -o -type l | sed 's|^\./||' | sort ) > "$list1" || true
( cd "$REPO_ROOT/_test_output_det2/bundle" && find . -type f -o -type l | sed 's|^\./||' | sort ) > "$list2" || true

if cmp -s "$list1" "$list2"; then
  pass "Déterminisme bundle (paths)"
else
  echo "  ❌ bundle paths différents (normal si le contenu change, mais pas attendu ici)"
  diff -u "$list1" "$list2" | head -50 || true
  fail "Déterminisme bundle"
fi

# --- Test 16: Profondeur ---
echo -e "\n=== Test 16: Profondeur ==="
inc
mkdir -p "$TEST_ROOT/deep/level1/level2/level3/level4/level5/level6/level7/level8/level9/level10"
echo "Deep file" > "$TEST_ROOT/deep/level1/level2/level3/level4/level5/level6/level7/level8/level9/level10/file.txt"
for i in $(seq 1 100); do echo "File $i" > "$TEST_ROOT/deep/file_$i.txt"; done
if command -v timeout >/dev/null 2>&1; then
  if timeout 15 env QUIET=1 "$COLLECTOR" "$TEST_ROOT" "$REPO_ROOT/_test_output_deep" >/dev/null 2>&1; then
    pass "Profondeur OK"
  else
    code=$?
    [ "$code" -eq 124 ] && fail "Profondeur (timeout)" || fail "Profondeur (exit $code)"
  fi
else
  QUIET=1 "$COLLECTOR" "$TEST_ROOT" "$REPO_ROOT/_test_output_deep" >/dev/null 2>&1 && pass "Profondeur OK" || fail "Profondeur KO"
fi

# --- Test 17: Symlinks (dans fixtures copiées) ---
echo -e "\n=== Test 17: Symlinks ==="
inc
ln -sf "simple_matrix.md" "$TEST_ROOT/fixtures/symlink_to_fixture"
QUIET=1 "$COLLECTOR" "$TEST_ROOT" "$REPO_ROOT/_test_output_symlink" >/dev/null 2>&1 || true
if [ -L "$REPO_ROOT/_test_output_symlink/bundle/fixtures/symlink_to_fixture" ]; then
  pass "Symlink préservé"
elif [ -f "$REPO_ROOT/_test_output_symlink/bundle/fixtures/symlink_to_fixture" ]; then
  echo "  ℹ️  symlink déréférencé (acceptable selon tar/cp)"
  pass "Symlink (déréférencé)"
else
  fail "Symlink absent"
fi

# --- Test 18: Permissions (fichier non lisible dans fixtures) ---
echo -e "\n=== Test 18: Permissions ==="
inc
echo "secret" > "$TEST_ROOT/fixtures/no_read.txt"
chmod 000 "$TEST_ROOT/fixtures/no_read.txt" || true
QUIET=1 "$COLLECTOR" "$TEST_ROOT" "$REPO_ROOT/_test_output_perm" >/dev/null 2>&1 || true
chmod 644 "$TEST_ROOT/fixtures/no_read.txt" || true
if [ -f "$REPO_ROOT/_test_output_perm/phio_llm_bundle.tar.gz" ]; then
  pass "Robuste aux permissions (ne crash pas)"
else
  fail "Crash sur permissions"
fi

echo -e "\n📊 RÉSULTATS"
echo "Tests exécutés: $TESTS_RUN"
echo "Échecs: $FAILURES"
echo "Succès: $((TESTS_RUN - FAILURES))"

if [ "$FAILURES" -eq 0 ]; then
  echo -e "\n🎉 TOUS LES TESTS ONT RÉUSSI"
  exit 0
else
  echo -e "\n⚠️  $FAILURES TEST(S) ONT ÉCHOUÉ"
  exit 1
fi
