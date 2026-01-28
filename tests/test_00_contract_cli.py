from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _candidate_clis() -> list[Path]:
    """
    Candidates ordered from most explicit to most heuristic.
    """
    # 1) explicit override (best)
    env_path = os.environ.get("PHIO_CLI", "").strip()
    if env_path:
        p = Path(env_path)
        if not p.is_absolute():
            p = (REPO_ROOT / p).resolve()
        return [p]

    # 2) common names in repo root / scripts
    candidates = [
        REPO_ROOT / "phio.py",
        REPO_ROOT / "cli.py",
        REPO_ROOT / "contract_probe.py",
        REPO_ROOT / "phi_otimes_o_instrument_v0_1.py",  # kept as LAST resort, not assumed to be "the CLI"
        REPO_ROOT / "scripts" / "phio.py",
        REPO_ROOT / "scripts" / "cli.py",
        REPO_ROOT / "scripts" / "contract_probe.py",
    ]
    return candidates


def _pick_cli() -> Path | None:
    for p in _candidate_clis():
        if p.exists() and p.is_file():
            return p
    return None


def _run_cli(cli: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """
    Runs the CLI in a way that does NOT require executable bit nor shebang.
    Uses the same interpreter as the test runner.
    """
    cmd = [sys.executable, str(cli), *args]
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
    )


def test_cli_help_runs():
    """
    Contract-level smoke: help should run without crashing.
    If no CLI is declared/found, we SKIP (not fail), because it's optional.
    """
    cli = _pick_cli()
    if cli is None:
        pytest.skip("No CLI entrypoint found. Set PHIO_CLI to enable this test.")

    res = _run_cli(cli, "--help")
    # accept 0 or 2 for argparse-style help exits depending on implementation
    assert res.returncode in (0, 2), f"CLI help failed.\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"


def test_cli_help_mentions_contract_wording():
    """
    Soft assertion: help output should mention contract-ish wording.
    Keep it tolerant to avoid false negatives.
    """
    cli = _pick_cli()
    if cli is None:
        pytest.skip("No CLI entrypoint found. Set PHIO_CLI to enable this test.")

    res = _run_cli(cli, "--help")
    out = (res.stdout + "\n" + res.stderr).lower()

    # very tolerant keywords
    keywords = ["contract", "manifest", "trace", "ddr", "e_report", "schema"]
    assert any(k in out for k in keywords), (
        "CLI help output does not look like a contract/trace tool.\n"
        f"Used CLI: {cli}\n"
        f"Output:\n{res.stdout}\n{res.stderr}"
    )
