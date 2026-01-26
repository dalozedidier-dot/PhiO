import copy
import pytest
import math

def _make_singleton_case(dim_labels):
    # one item per dimension, score fixed to known values
    # choose scores within [0,3]
    scores = {
        "Cx": 2,
        "K": 3,
        "τ": 1,
        "tau": 1,
        "G": 2,
        "D": 0,
    }
    items=[]
    for d in dim_labels:
        if d in ("τ","tau","Cx","K","G","D"):
            items.append({"dimension": d, "score": scores[d], "weight": 1.0, "justification":"golden"})
    return {"system": {"name":"Golden", "description":"golden", "context":"test"}, "items": items}

def _expected(scores, tau_label):
    Cx = scores["Cx"]
    K = scores["K"]
    tau = scores[tau_label]
    G = scores["G"]
    D = scores["D"]
    K_eff = K / (1 + tau + G + D + Cx)
    T = Cx + tau + G + D - K_eff
    return T, K_eff

def test_golden_formula_if_singletons(run_cli, infer_dimensions, load_results):
    # require all core dims present in template
    dims=set(infer_dimensions)
    has_tau = "τ" in dims or "tau" in dims
    if not {"Cx","K","G","D"}.issubset(dims) or not has_tau:
        pytest.skip("dimensions nécessaires absentes pour golden test")
    tau_label = "τ" if "τ" in dims else "tau"
    case = _make_singleton_case(["Cx","K",tau_label,"G","D"])
    rp, out = run_cli(["score","--input","placeholder"], input_json=case)
    assert rp.returncode==0, rp.stderr or rp.stdout
    res = load_results(out)
    # compute expectation
    scores={"Cx":2,"K":3,tau_label:1,"G":2,"D":0}
    Texp, Keexp = _expected(scores, tau_label)
    # tolérance flottante
    assert math.isclose(float(res["K_eff"]), Keexp, rel_tol=1e-5, abs_tol=1e-8)
    assert math.isclose(float(res["T"]), Texp, rel_tol=1e-5, abs_tol=1e-8)
