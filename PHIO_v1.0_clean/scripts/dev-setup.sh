#!/bin/sh
set -e

echo "=== dev-setup: PhiO contract framework ==="

# Activate versioned hooks (idempotent)
if [ -d ".githooks" ]; then
  git config core.hooksPath .githooks
  echo "✅ core.hooksPath=.githooks"
else
  echo "❌ .githooks directory not found. Run from repo root."
  exit 1
fi

# Verify
HOOKS_PATH=$(git config --get core.hooksPath || true)
if [ "$HOOKS_PATH" != ".githooks" ]; then
  echo "❌ hooksPath misconfigured: $HOOKS_PATH"
  exit 1
fi
echo "✅ hooksPath verified"

# Quick hint about instrument path (non-blocking)
if [ -n "${PHIO_INSTRUMENT:-}" ] && [ -f "$PHIO_INSTRUMENT" ]; then
  echo "✅ PHIO_INSTRUMENT=$PHIO_INSTRUMENT"
else
  echo "ℹ️  Define PHIO_INSTRUMENT to point to your instrument file, e.g.:"
  echo "   export PHIO_INSTRUMENT=../phi_otimes_o_instrument_v0_1.py"
fi

echo "OK"
