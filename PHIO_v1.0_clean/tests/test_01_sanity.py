import copy
import pytest

def _mutate_first_item(data, **kwargs):
    d = copy.deepcopy(data)
    if not d.get("items"):
        pytest.skip("Template sans items")
    d["items"][0].update(kwargs)
    return d

def test_help(run_cli):
    res, _ = run_cli(["--help"])
    assert res.returncode == 0

def test_new_template_and_score_ok(run_cli, template_json, load_results):
    # score the template file itself
    # write template to a temp file through runner (ensures encoding)
    res, outdir = run_cli(["score", "--input", "placeholder"], input_json=template_json)
    assert res.returncode == 0, res.stderr or res.stdout
    r = load_results(outdir)
    assert "T" in r, "clé T absente"
    assert "K_eff" in r, "clé K_eff absente"

@pytest.mark.parametrize("bad_score", [4, -1, 999])
def test_reject_score_out_of_range(run_cli, template_json, bad_score):
    invalid = _mutate_first_item(template_json, score=bad_score)
    res, _ = run_cli(["score", "--input", "placeholder"], input_json=invalid)
    assert res.returncode != 0, "Score hors-borne accepté (validation manquante)"

def test_reject_float_score(run_cli, template_json):
    invalid = _mutate_first_item(template_json, score=1.5)
    res, _ = run_cli(["score", "--input", "placeholder"], input_json=invalid)
    assert res.returncode != 0, "Score float accepté (v0.1 attend int-only)"

def test_reject_missing_dimension_key(run_cli, template_json):
    import copy
    invalid = copy.deepcopy(template_json)
    if not invalid.get("items"):
        pytest.skip("Template sans items")
    invalid["items"][0].pop("dimension", None)
    res, _ = run_cli(["score", "--input", "placeholder"], input_json=invalid)
    assert res.returncode != 0, "Clé manquante acceptée (validation manquante)"
