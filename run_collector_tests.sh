#!/usr/bin/env bash
# run_collector_tests.sh
set -euo pipefail

echo "🚀 LANCEMENT DES TESTS DU COLLECTEUR"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

tests=(
  "tests/test_llm_collector_exhaustive.sh"
  "tests/test_llm_collector_stress.sh"
  "tests/test_cross_validation.sh"
)

passed=0
failed=0

for t in "${tests[@]}"; do
  echo -e "\n📋 $t"
  chmod +x "$REPO_ROOT/$t" 2>/dev/null || true
  if command -v timeout >/dev/null 2>&1; then
    timeout 300 bash "$REPO_ROOT/$t" && ok=1 || ok=0
  else
    bash "$REPO_ROOT/$t" && ok=1 || ok=0
  fi
  if [ "$ok" -eq 1 ]; then
    echo "✅ OK: $t"
    ((++passed))
  else
    echo "❌ KO: $t"
    ((++failed))
  fi
done

echo -e "\n🎯 Smoke test"
if QUIET=1 "$REPO_ROOT/scripts/phio_llm_collect.sh" "$REPO_ROOT" "$REPO_ROOT/_final_test" >/dev/null 2>&1; then
  echo "✅ Smoke OK"
  ((++passed))
else
  echo "❌ Smoke KO"
  ((++failed))
fi

echo -e "\n📊 Résumé: pass=$passed fail=$failed"
[ "$failed" -eq 0 ]
