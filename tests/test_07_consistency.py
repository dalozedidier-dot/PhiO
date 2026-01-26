import pytest
import math

def _get_item_score(case_json, dim):
    for it in case_json.get("items", []):
        if it.get("dimension") == dim:
            return float(it.get("score"))
    raise KeyError(dim)

def test_dimension_scores_consistency_singletons(run_cli, infer_dimensions, load_results):
    """
    Sur un cas singleton (1 item par dimension), l'agrégation median et bottleneck
    devraient produire des scores dimensionnels égaux au score d'entrée.
    Ce test est conditionné à la présence de 'dimension_scores' dans results.json.
    """
    dims = list(infer_dimensions)
    # Construire un cas "un item par dimension" en reprenant les labels détectés.
    # On fixe un score constant 2 (dans [0,3]) pour toutes les dimensions.
    case = {
        "system": {"name": "ConsistencySingleton", "description": "singleton per dim", "context": "test"},
        "items": [{"dimension": d, "score": 2, "weight": 1.0, "justification": "singleton"} for d in dims],
    }

    # Score baseline (médiane / défaut)
    rp0, out0 = run_cli(["score", "--input", "placeholder"], input_json=case)
    assert rp0.returncode == 0, rp0.stderr or rp0.stdout
    r0 = load_results(out0)

    if "dimension_scores" not in r0:
        pytest.xfail("results.json ne contient pas 'dimension_scores' : impossible de tester la cohérence d'agrégation")
    ds0 = r0["dimension_scores"]

    # Vérifier cohérence sur défaut
    for d in dims:
        if d not in ds0:
            pytest.xfail(f"dimension_scores ne contient pas la clé {d}")
        assert math.isclose(float(ds0[d]), 2.0, rel_tol=0.0, abs_tol=1e-12), f"{d} median != score entrée"

    # Score bottleneck si supporté (détection via --help + tentative de flags)
    help_proc, _ = run_cli(["--help"])
    help_txt = (help_proc.stdout or "") + (help_proc.stderr or "")
    if "bottleneck" not in help_txt.lower():
        pytest.skip("bottleneck non annoncé dans --help")

    # Construire flags d'agrégation : on tente d'abord --agg_<dim> pour chaque dim;
    # pour τ on tente aussi alias ascii.
    args = ["score", "--input", "placeholder"]
    for d in dims:
        if d == "τ":
            # tentative unicode
            args += ["--agg_τ", "bottleneck"]
        elif d == "tau":
            args += ["--agg_tau", "bottleneck"]
        else:
            args += [f"--agg_{d}", "bottleneck"]

    rp1, out1 = run_cli(args, input_json=case)
    if rp1.returncode != 0:
        # fallback τ -> tau si nécessaire
        if "τ" in dims:
            args2 = ["score", "--input", "placeholder"]
            for d in dims:
                if d == "τ":
                    args2 += ["--agg_tau", "bottleneck"]
                else:
                    args2 += [f"--agg_{d}", "bottleneck"]
            rp1, out1 = run_cli(args2, input_json=case)
    assert rp1.returncode == 0, rp1.stderr or rp1.stdout
    r1 = load_results(out1)

    if "dimension_scores" not in r1:
        pytest.xfail("results.json ne contient pas 'dimension_scores' en mode bottleneck")
    ds1 = r1["dimension_scores"]

    for d in dims:
        if d not in ds1:
            pytest.xfail(f"dimension_scores (bottleneck) ne contient pas la clé {d}")
        assert math.isclose(float(ds1[d]), 2.0, rel_tol=0.0, abs_tol=1e-12), f"{d} bottleneck != score entrée"
        assert math.isclose(float(ds0[d]), float(ds1[d]), rel_tol=0.0, abs_tol=1e-12), f"{d} median != bottleneck sur singleton"
