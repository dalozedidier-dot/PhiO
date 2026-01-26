import copy
import json
import random
from pathlib import Path

import pytest

from .config import ROBUSTNESS_MAX_ZONE_CHANGE_RATE, PERTURBATION_COUNT, ROBUSTNESS_INPUT


def _perturb_one(data):
    d = copy.deepcopy(data)
    items = d.get("items", [])
    if not items:
        return d
    idx = random.randrange(len(items))
    sc = items[idx].get("score", 0)
    try:
        sc_int = int(sc)
    except Exception:
        return d
    delta = random.choice([-1, +1])
    items[idx]["score"] = max(0, min(3, sc_int + delta))
    return d


def _load_case(path: str):
    p = Path(path)
    assert p.exists(), f"ROBUSTNESS_INPUT introuvable: {p}"
    return json.loads(p.read_text(encoding="utf-8"))


def test_zone_robustness(run_cli, template_json, load_results):
    """Robustesse de zone sous perturbation ±1.

    Par défaut, ce test est *optionnel* : il est exécuté seulement si
    PHIO_ROBUSTNESS_INPUT est fourni, afin d'éviter les faux échecs
    quand le template par défaut tombe près d'une frontière de zone.
    """
    if not ROBUSTNESS_INPUT:
        pytest.skip("PHIO_ROBUSTNESS_INPUT non fourni : test de robustesse optionnel")

    baseline = _load_case(ROBUSTNESS_INPUT)

    rp0, out0 = run_cli(["score"], input_json=baseline)
    assert rp0.returncode == 0, rp0.stderr or rp0.stdout
    r0 = load_results(out0)
    z0 = r0.get("zone")
    assert z0 is not None, "zone absente de results.json"

    changes = 0
    for _ in range(PERTURBATION_COUNT):
        v = _perturb_one(baseline)
        rp, out = run_cli(["score"], input_json=v)
        assert rp.returncode == 0, rp.stderr or rp.stdout
        r = load_results(out)
        if r.get("zone") != z0:
            changes += 1

    rate = changes / float(PERTURBATION_COUNT)
    assert rate <= ROBUSTNESS_MAX_ZONE_CHANGE_RATE, f"Taux de changement de zone trop élevé: {rate:.2f}"
