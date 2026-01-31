#!/usr/bin/env python3
"""Génère un script shell d'exports à partir de diagnostic_report.json"""

import argparse, json
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default="diagnostic_report.json")
    ap.add_argument("--out", default="phio_env_suggestions.sh")
    args = ap.parse_args()

    rep = Path(args.report)
    if not rep.exists():
        raise SystemExit(f"report absent: {rep}")

    data = json.loads(rep.read_text(encoding="utf-8"))
    conv = data.get("conventions", {})
    dims = conv.get("dimensions", ["Cx","K","τ","G","D"])

    # DIM_SIGN selon formule fournie (si dims connus)
    dimsign = []
    for d in dims:
        if d in ("Cx","τ","tau","G","D"):
            dimsign.append(f"{d}:1")
        elif d == "K":
            dimsign.append("K:-1")

    lines = [
        "# exports Phi⊗O (auto)",
        f'export PHIO_INSTRUMENT="{data.get("instrument","phi_otimes_o_instrument_v0_1.py")}"',
        f'export PHIO_DIMS="{",".join(dims)}"',
    ]
    if dimsign:
        lines.append(f'export PHIO_DIMSIGN="{",".join(dimsign)}"')
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.out)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
