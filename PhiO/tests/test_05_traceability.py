import json
from pathlib import Path
import pytest

DATA = Path(__file__).parent.parent / "test_data" / "traceability_cases.json"

def test_traceability_cases_optional(run_cli, load_results):
    if not DATA.exists():
        pytest.skip("traceability_cases.json absent")
    cases = json.loads(DATA.read_text(encoding="utf-8"))
    if not cases:
        pytest.skip("aucun cas de traçabilité fourni")
    for case in cases:
        rp, out = run_cli(["score", "--input", "placeholder"], input_json=case["input"])
        assert rp.returncode == 0, rp.stderr or rp.stdout
        res = load_results(out)
        # assertions minimales (non-contradiction) : présence des clés
        assert "T" in res and "K_eff" in res and "zone" in res
