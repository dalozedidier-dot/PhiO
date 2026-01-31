import pytest

from .config import INSTRUMENT_PATH
from .contracts import extract_zone_thresholds_ast

def test_zone_thresholds_extractable_or_explicitly_absent():
    """Contrat: si le zonage existe, il doit être extractible (ou déclaré non-stable).

    Ce test est volontairement conservateur:
    - PASS si on extrait un objet seuils/mapping plausible
    - XFAIL si rien n'est détecté (signal de non-contractualisation)
    """
    info = extract_zone_thresholds_ast(str(INSTRUMENT_PATH))
    if info is None:
        pytest.xfail("Seuils de zone non extractibles via heuristique AST (contrat non explicité).")
    # Minimal structure check
    assert isinstance(info, dict)
    assert "pattern" in info
    assert any(k in info for k in ("thresholds", "mapping"))
