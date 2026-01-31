#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Baseline regression test for PhiO contract.

Policy:
- Baseline stored at .contract/contract_baseline.json
- If PHIO_UPDATE_BASELINE=true, the test regenerates baseline via contract_probe.py and overwrites it.
- Otherwise, the test compares a canonicalized version of the baseline against a freshly generated one,
  ignoring volatile fields (timestamps, paths).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict

import pytest


BASELINE_PATH = Path(".contract") / "contract_baseline.json"
PROBE = Path("contract_probe.py")


VOLATILE_TOPLEVEL_KEYS = {
    "validation_timestamp",
    "instrument_path",
    "instrument_hash",
    "_probe_forensics",
}


def _canonicalize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _canonicalize(obj[k]) for k in sorted(obj.keys(), key=lambda x: str(x))}
    if isinstance(obj, list):
        return [_canonicalize(x) for x in obj]
    return obj


def _strip_volatile(b: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in b.items() if k not in VOLATILE_TOPLEVEL_KEYS}


def _run_probe(tmp_out: Path) -> None:
    if not PROBE.exists():
        raise RuntimeError(f"Missing {PROBE}")
    cmd = [os.environ.get("PYTHON", "python"), str(PROBE), "--out", str(tmp_out)]
    subprocess.run(cmd, check=True)


@pytest.mark.contract
def test_contract_baseline_regression(tmp_path: Path) -> None:
    update = os.environ.get("PHIO_UPDATE_BASELINE", "false").lower() == "true"
    tmp_out = tmp_path / "contract_baseline.current.json"

    # generate current baseline
    _run_probe(tmp_out)
    current = json.loads(tmp_out.read_text(encoding="utf-8"))

    # ensure baseline directory exists
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)

    if update or not BASELINE_PATH.exists():
        BASELINE_PATH.write_text(json.dumps(_canonicalize(current), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                                 encoding="utf-8")
        # If we're updating, this is considered success.
        return

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    c = _canonicalize(_strip_volatile(current))
    b = _canonicalize(_strip_volatile(baseline))

    assert b == c, (
        "Contract baseline drift detected.\n"
        "If the change is intentional, run with PHIO_UPDATE_BASELINE=true to update baseline."
    )
