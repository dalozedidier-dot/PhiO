#!/usr/bin/env bash
# tests/test_cross_validation.sh
# Validation croisée : mêmes inputs → même structure tree/bundle.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COLLECTOR="${COLLECTOR:-$REPO_ROOT/scripts/phio_llm_collect.sh}"

echo "🔄 VALIDATION CROISÉE"

TEST_DIR="$(mktemp -d)"
trap 'rm -rf "$TEST_DIR" "$REPO_ROOT/_cross1" "$REPO_ROOT/_cross2" "$REPO_ROOT/_cross3" 2>/dev/null || true' EXIT

mkdir -p "$TEST_DIR/.contract"
echo '{"baseline":true}' > "$TEST_DIR/.contract/contract_baseline.json"
mkdir -p "$TEST_DIR/tests"
touch "$TEST_DIR/tests/__init__.py"
echo "README" > "$TEST_DIR/README.md"

echo "Run 1: defaults"
QUIET=1 "$COLLECTOR" "$TEST_DIR" "$REPO_ROOT/_cross1" >/dev/null 2>&1

echo "Run 2: modified limits"
env MAX_FILE_BYTES=1000 MAX_CONCAT_LINES=100 INCLUDE_PIP_FREEZE=0 QUIET=1 \
  "$COLLECTOR" "$TEST_DIR" "$REPO_ROOT/_cross2" >/dev/null 2>&1

echo "Run 3: no concat"
env INCLUDE_CONCAT=0 QUIET=1 "$COLLECTOR" "$TEST_DIR" "$REPO_ROOT/_cross3" >/dev/null 2>&1

echo "Compare tree.txt"
cmp -s "$REPO_ROOT/_cross1/tree.txt" "$REPO_ROOT/_cross2/tree.txt" || { echo "❌ tree.txt différent"; exit 1; }

echo "Compare bundle paths"
for d in _cross1 _cross2; do
  (cd "$REPO_ROOT/$d/bundle" && find . -type f -o -type l | sed 's|^\./||' | sort) > "$REPO_ROOT/$d/_paths.txt"
done
cmp -s "$REPO_ROOT/_cross1/_paths.txt" "$REPO_ROOT/_cross2/_paths.txt" || { echo "❌ bundle paths différents"; exit 1; }

for d in _cross1 _cross2 _cross3; do
  test -f "$REPO_ROOT/$d/phio_llm_bundle.tar.gz" || { echo "❌ Archive manquante dans $d"; exit 1; }
done

echo "🎉 Validation croisée réussie"
