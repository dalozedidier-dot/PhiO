#!/usr/bin/env python3
"""Runner minimal pour la TestSuite Φ⊗O.

Objectif: exécution séquentielle + résumé, sans logique implicite.
Les skips/xfail sont laissés à pytest; ce runner ne remplace pas pytest.
"""

import subprocess
import sys
from pathlib import Path

TEST_FILES = [
    "tests/test_00_contract_cli.py",
    "tests/test_08_zone_thresholds.py",
    "tests/test_01_sanity.py",
    "tests/test_06_golden_formula.py",
    "tests/test_02_properties.py",
    "tests/test_04_aggregation.py",
    "tests/test_03_robustness.py",
    "tests/test_07_consistency.py",
    "tests/test_05_traceability.py",
]


def main():
    root = Path(__file__).parent.resolve()
    failures = 0
    for tf in TEST_FILES:
        p = root / tf
        if not p.exists():
            continue
        cmd = [sys.executable, "-m", "pytest", str(p), "-v", "--tb=short"]
        r = subprocess.run(cmd)
        if r.returncode not in (0,):  # pytest returns 0 on pass; xfail/skip still 0 unless strict
            failures += 1
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
