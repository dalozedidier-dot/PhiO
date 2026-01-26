import re
import pytest

def _supports_bottleneck(help_text: str) -> bool:
    return "bottleneck" in help_text.lower() or "--agg" in help_text

def test_bottleneck_dominance_if_supported(run_cli, template_json, load_results):
    help_res, _ = run_cli(["--help"])
    assert help_res.returncode == 0
    if not _supports_bottleneck(help_res.stdout + help_res.stderr):
        pytest.skip("bottleneck non détecté dans --help")

    # median (default)
    rp_m, out_m = run_cli(["score", "--input", "placeholder"], input_json=template_json)
    assert rp_m.returncode == 0, rp_m.stderr or rp_m.stdout
    m = load_results(out_m)

    # bottleneck flags with both tau labels; if one fails we try the other
    flags_tau = ["--agg_τ", "bottleneck"]
    flags_tau_ascii = ["--agg_tau", "bottleneck"]
    base_flags = ["--agg_Cx", "bottleneck", "--agg_K", "bottleneck", "--agg_G", "bottleneck", "--agg_D", "bottleneck"]
    # try unicode tau
    rp_b, out_b = run_cli(["score", "--input", "placeholder"] + base_flags + flags_tau, input_json=template_json)
    if rp_b.returncode != 0:
        rp_b, out_b = run_cli(["score", "--input", "placeholder"] + base_flags + flags_tau_ascii, input_json=template_json)
    assert rp_b.returncode == 0, rp_b.stderr or rp_b.stdout
    b = load_results(out_b)

    assert float(b["T"]) >= float(m["T"]), "bottleneck devrait être >= median sur T"
    assert float(b["K_eff"]) <= float(m["K_eff"]), "bottleneck devrait être <= median sur K_eff"
