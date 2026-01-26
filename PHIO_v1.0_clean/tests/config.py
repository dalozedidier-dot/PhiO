import os
from pathlib import Path

# Instrument
PHIO_INSTRUMENT = os.environ.get("PHIO_INSTRUMENT", "phi_otimes_o_instrument_v0_1.py")
INSTRUMENT_PATH = Path(PHIO_INSTRUMENT).resolve()

# Robustesse
ROBUSTNESS_MAX_ZONE_CHANGE_RATE = float(os.environ.get("PHIO_ROBUSTNESS_RATE", "0.30"))
PERTURBATION_COUNT = int(os.environ.get("PHIO_PERTURB_N", "20"))

# Unicode τ : par défaut on suit le template réel; si besoin on force un alias ASCII.
FORCE_ASCII_TAU = os.environ.get("PHIO_FORCE_ASCII_TAU", "0") == "1"

# Attendus (si formule stable et exportée dans results.json)
# T = Cx + tau + G + D - K_eff
# K_eff = K / (1 + tau + G + D + Cx)
FORMULA_EXPECTED = True

# Optionnel: fichier JSON explicite pour robustesse (évite la flakiness près des seuils)
ROBUSTNESS_INPUT = os.environ.get("PHIO_ROBUSTNESS_INPUT", "").strip() or None
