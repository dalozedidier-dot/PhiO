from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[1]

# -----------------------------------------------------------------------------
# Instrument path
# -----------------------------------------------------------------------------
DEFAULT_INSTRUMENT = REPO_ROOT / "scripts" / "phi_otimes_o_instrument_v0_1.py"
_env = os.environ.get("INSTRUMENT_PATH", "").strip()

if _env:
    p = Path(_env)
    INSTRUMENT_PATH = p if p.is_absolute() else (REPO_ROOT / p).resolve()
else:
    INSTRUMENT_PATH = DEFAULT_INSTRUMENT.resolve()

# -----------------------------------------------------------------------------
# Robustness test parameters (expected by tests/test_03_robustness.py)
# -----------------------------------------------------------------------------
# Valeurs par défaut "neutres". Ajuste si les tests imposent un domaine spécifique.
ROBUSTNESS_MAX_ZONE_CHANGE_RATE: float = float(os.environ.get("ROBUSTNESS_MAX_ZONE_CHANGE_RATE", "0.25"))
PERTURBATION_COUNT: int = int(os.environ.get("PERTURBATION_COUNT", "10"))

# Structure d'entrée robuste générique.
# Si les tests attendent des clés précises, il faudra aligner ce dict sur leurs attentes.
ROBUSTNESS_INPUT: Dict[str, Any] = {
    "mode": os.environ.get("ROBUSTNESS_MODE", "default"),
    "seed": int(os.environ.get("ROBUSTNESS_SEED", "0")),
    "notes": "default robustness input (override via env if needed)",
}
