# phi_otimes_o_instrument_v0_1.py
# Instrument "PhiO-times-O" — v0.1 (spec minimale structurée)
# Remarque: base contractuelle (existence + structure), pas une implémentation métier complète.

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Tuple


__instrument_id__ = "phi_otimes_o"
__version__ = "0.1"


# --- Data model (min) ---------------------------------------------------------


@dataclass(frozen=True)
class Dimension:
    key: str
    label: str
    weight: float = 1.0
    description: str = ""


@dataclass(frozen=True)
class InstrumentSpec:
    instrument_id: str
    version: str
    dimensions: Tuple[Dimension, ...]
    features: Tuple[str, ...] = ()
    aggregation: Dict[str, Any] | None = None
    traceability: Dict[str, Any] | None = None
    golden_formula: Dict[str, Any] | None = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["dimensions"] = [asdict(x) for x in self.dimensions]
        d["features"] = list(self.features)
        return d


# --- Spec (min) ---------------------------------------------------------------

_DIMENSIONS: Tuple[Dimension, ...] = (
    Dimension(key="phi", label="Phi", weight=1.0, description="Dimension Phi"),
    Dimension(key="o_times", label="O×", weight=1.0, description="Dimension O-times"),
    Dimension(key="o", label="O", weight=1.0, description="Dimension O"),
)

_FEATURES: Tuple[str, ...] = (
    "aggregation",
    "traceability",
    "golden_formula",
    "consistency",
)

_AGGREGATION: Dict[str, Any] = {
    "method": "weighted_mean",
    "bottleneck_dominance": False,
}

_TRACEABILITY: Dict[str, Any] = {
    "cases_optional": True,
    "schema": "minimal",
}

_GOLDEN_FORMULA: Dict[str, Any] = {
    "method": "weighted_sum",
    "normalization": "none",
}

SPEC = InstrumentSpec(
    instrument_id=__instrument_id__,
    version=__version__,
    dimensions=_DIMENSIONS,
    features=_FEATURES,
    aggregation=_AGGREGATION,
    traceability=_TRACEABILITY,
    golden_formula=_GOLDEN_FORMULA,
)


# --- API utilitaire (min) -----------------------------------------------------


def get_spec() -> Dict[str, Any]:
    """Retourne la spec instrument sous forme dict sérialisable."""
    return SPEC.to_dict()


def supports(feature: str) -> bool:
    """Indique si une capacité est déclarée comme supportée."""
    return feature in set(SPEC.features)


def list_dimensions() -> List[str]:
    return [d.key for d in SPEC.dimensions]


def weights() -> Dict[str, float]:
    return {d.key: float(d.weight) for d in SPEC.dimensions}


def score_singleton(values: Dict[str, float]) -> float:
    """Score minimal: moyenne pondérée des dimensions présentes."""
    w = weights()
    total_w = 0.0
    total = 0.0
    for k, v in values.items():
        if k in w:
            total += float(v) * w[k]
            total_w += w[k]
    return total if total_w == 0.0 else total / total_w


def aggregate(scores: List[Dict[str, float]]) -> Dict[str, Any]:
    """Agrégation minimale sur une liste de scores dimensionnels."""
    if not scores:
        return {"by_dim": {}, "global": 0.0}

    dims = list_dimensions()
    by_dim: Dict[str, float] = {}
    for d in dims:
        vals = [float(s[d]) for s in scores if d in s]
        by_dim[d] = sum(vals) / len(vals) if vals else 0.0

    global_score = score_singleton(by_dim)
    return {"by_dim": by_dim, "global": global_score}
