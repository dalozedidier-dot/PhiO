# tests/test_00_contract_cli.py

from __future__ import annotations

import subprocess


def _run_cli_help(instrument_path: str) -> str:
    """
    Execute the instrument CLI with --help and return combined stdout/stderr.
    """
    proc = subprocess.run(
        ["python3", instrument_path, "--help"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    return proc.stdout or ""


def test_cli_help_has_core_contract(instrument_path: str):
    """
    CLI contract test.

    - Le skip / fail en cas d'absence de l'instrument est déjà géré par la fixture
      instrument_path (mode dev vs mode strict).
    - Ici, on vérifie uniquement le contrat minimal du CLI.
    """
    out = _run_cli_help(instrument_path)

    # Marqueurs contractuels MINIMAUX et stables
    expected_markers = [
        "PhiO",
        "--help",
    ]

    missing = [m for m in expected_markers if m not in out]
    assert not missing, (
        "CLI help output is missing expected contract marker(s): "
        f"{missing}\n--- CLI output ---\n{out}"
    )
