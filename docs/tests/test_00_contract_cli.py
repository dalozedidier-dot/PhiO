import pytest
from contract_warnings import ContractWarning, ContractInfoWarning
import os
import warnings
import tempfile

from .config import INSTRUMENT_PATH
from .contracts import run_help, parse_help_flags, detect_tau_agg_flag

def test_cli_help_has_core_contract():
    assert INSTRUMENT_PATH.exists(), f"Instrument introuvable: {INSTRUMENT_PATH}"
    help_text = run_help(str(INSTRUMENT_PATH))
    flags = parse_help_flags(help_text)

    # Contrat minimal CLI
    assert flags["has_new_template"], "CLI: sous-commande new-template absente de --help"
    assert flags["has_score"], "CLI: sous-commande score absente de --help"
    assert flags["mentions_input"], "CLI: option --input non visible dans --help"
    assert flags["mentions_outdir"], "CLI: option --outdir non visible dans --help"

def test_cli_tau_flag_contract_is_non_ambiguous():
    help_text = run_help(str(INSTRUMENT_PATH))
    tau_flag = detect_tau_agg_flag(help_text)

    # Contrat : si le CLI expose des options d'agrégation, il doit préciser la forme tau
    flags = parse_help_flags(help_text)
    if not flags["mentions_agg"]:
        pytest.skip("CLI ne documente pas d'options --agg_* dans --help")
    assert tau_flag in ("--agg_τ", "--agg_tau"), (
        "CLI: ni --agg_τ ni --agg_tau n'apparaît dans --help alors que des options d'agrégation existent"
    )

def test_cli_bottleneck_documented_if_supported():
    help_text = run_help(str(INSTRUMENT_PATH))
    flags = parse_help_flags(help_text)
    if flags["mentions_bottleneck"]:
        # ok: documented
        assert True
    else:
        # not documented -> we don't fail, but we mark as xfail if agg exists (contract gap)
        if flags["mentions_agg"]:
            pytest.xfail("Bottleneck non documenté dans --help alors que les flags d'agrégation existent")

@pytest.mark.contract
def test_tau_aliases(run_cli, help_text=None):
    """Test des alias tau - politique configurable."""
    if help_text is None:
        proc = run_cli(["--help"])
        assert proc.returncode == 0, f"--help failed: {proc.stderr}"
        help_text = proc.stdout or ""
    policy = os.environ.get("PHIO_TAU_POLICY", "AT_LEAST_ONE").upper()
    has_tau = "--agg_tau" in help_text
    has_tau_unicode = "--agg_τ" in help_text

    if policy == "BOTH_REQUIRED":
        assert has_tau and has_tau_unicode, "Both --agg_tau and --agg_τ must be documented"
    elif policy == "AT_LEAST_ONE":
        assert has_tau or has_tau_unicode, "At least one of --agg_tau or --agg_τ must be documented"
    elif policy == "EXPLICIT_CHOICE":
        expected = os.environ.get("PHIO_EXPECTED_TAU", "--agg_tau")
        if expected == "--agg_tau":
            assert has_tau, f"Expected tau alias missing: {expected}"
        else:
            assert has_tau_unicode, f"Expected tau alias missing: {expected}"
    elif policy == "DISABLED":
        return
    else:
        warnings.warn(
            f"Unknown PHIO_TAU_POLICY={policy}; defaulting to AT_LEAST_ONE.",
            ContractInfoWarning,
            stacklevel=2,
        )
        assert has_tau or has_tau_unicode, "At least one of --agg_tau or --agg_τ must be documented"


@pytest.mark.contract
def test_cli_accepts_arguments(run_cli):
    """Test comportemental: vérifie que le CLI *reconnaît* les flags, sans exiger que la validation métier passe."""
    # --input reconnu : on passe volontairement un JSON invalide pour la logique métier.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
        tmp.write('{"test": "data"}')
        tmp_path = tmp.name

    try:
        proc = run_cli(["score", "--input", tmp_path])
        err = (proc.stderr or "").lower()

        # argparse renvoie typiquement code 2 sur erreur de parsing
        if proc.returncode == 2 and ("unrecognized arguments" in err or "unrecognized argument" in err):
            pytest.fail(f"Flag --input not recognized by CLI: {proc.stderr}")

        # On accepte un échec métier, tant que ce n'est pas une erreur de parsing
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@pytest.mark.contract
def test_cli_required_flags_behavior(run_cli):
    """Test que --help marche pour chaque sous-commande (contrat d'interface)."""
    cases = [
        (["score", "--help"], "score --help must work"),
        (["new-template", "--help"], "new-template --help must work"),
    ]
    for args, desc in cases:
        proc = run_cli(args)
        assert proc.returncode == 0, f"{desc} failed: {proc.stderr}"
        out = (proc.stdout or "").lower()
        if "usage:" not in out and "help" not in out:
            warnings.warn(
                f"{desc} did not show the expected help format",
                ContractInfoWarning,
                stacklevel=2,
            )


@pytest.mark.contract
def test_cli_basic_contract_required_flags(run_cli):
    """Contrat minimal: sous-commandes + flags requis visibles dans --help."""
    proc = run_cli(["--help"])
    assert proc.returncode == 0, f"--help failed: {proc.stderr}"
    help_text = proc.stdout or ""

    for subcmd in ["new-template", "score"]:
        assert subcmd in help_text, f"Required subcommand missing: {subcmd}"

    for flag in ["--input", "--outdir"]:
        assert flag in help_text, f"Required flag missing: {flag}"

    # Politique d'alias tau
    test_tau_aliases(run_cli, help_text=help_text)
