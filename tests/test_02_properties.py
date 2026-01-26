import copy
import pytest

# Convention dérivée des formules (si stables)
DIM_SIGN = {"Cx": +1, "K": -1, "τ": +1, "tau": +1, "G": +1, "D": +1}

def _bump_item(data, dim_label, delta):
    d = copy.deepcopy(data)
    for it in d.get("items", []):
        if it.get("dimension") == dim_label:
            it["score"] = max(0, min(3, int(it["score"]) + delta))
    return d

def _extract_T(res_json):
    return float(res_json["T"])

def test_monotonicity_local(run_cli, template_json, infer_dimensions, load_results):
    # baseline
    r0_proc, out0 = run_cli(["score", "--input", "placeholder"], input_json=template_json)
    assert r0_proc.returncode == 0, r0_proc.stderr or r0_proc.stdout
    base = load_results(out0)
    T0 = _extract_T(base)

    for dim in infer_dimensions:
        sign = DIM_SIGN.get(dim, 0)
        if sign == 0:
            continue
        variant = _bump_item(template_json, dim, +1)
        rp, out = run_cli(["score", "--input", "placeholder"], input_json=variant)
        assert rp.returncode == 0, rp.stderr or rp.stdout
        r = load_results(out)
        T1 = _extract_T(r)
        if sign > 0:
            assert T1 >= T0, f"{dim} +1 devrait augmenter (ou laisser) T"
        else:
            assert T1 <= T0, f"{dim} +1 devrait diminuer (ou laisser) T"
