#!/usr/bin/env python3
# phi_otimes_o_instrument_v0_1.py
# PhiO instrument reference implementation (contract-driven minimal).
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Tuple

__instrument_id__ = "phi_otimes_o"
__version__ = "0.1"

# Explicit zone thresholds for AST extractor + test_08_zone_thresholds.py
# Intervals: (-inf, t0] (t0,t1] (t1,t2] (t2,+inf)
ZONE_THRESHOLDS = [0.5, 1.5, 2.5]
ZONE_LABELS = ["Z0", "Z1", "Z2", "Z3"]

SCORE_MIN = 0
SCORE_MAX = 3


def _tau_label() -> str:
    # prefer unicode tau unless forced to ASCII
    force_ascii = os.environ.get("PHIO_FORCE_ASCII_TAU", "0") == "1"
    return "tau" if force_ascii else "τ"


def build_template(name: str = "Template", description: str = "pytest template") -> Dict[str, Any]:
    tau = _tau_label()
    dims = ["Cx", "K", tau, "G", "D"]
    items = []
    for d in dims:
        items.append(
            {
                "dimension": d,
                "score": 0,
                "weight": 1.0,
                "justification": "template",
            }
        )
    return {
        "system": {"name": name, "description": description, "context": "template"},
        "items": items,
    }


def _is_int_strict(x: Any) -> bool:
    # reject bools (bool is subclass of int)
    return isinstance(x, int) and not isinstance(x, bool)


def validate_input(data: Dict[str, Any]) -> None:
    items = data.get("items", None)
    if not isinstance(items, list) or not items:
        raise ValueError("input.items absent ou vide")
    for idx, it in enumerate(items):
        if not isinstance(it, dict):
            raise ValueError(f"item[{idx}] doit être un objet")
        if "dimension" not in it:
            raise ValueError(f"item[{idx}] clé 'dimension' manquante")
        dim = it.get("dimension")
        if not isinstance(dim, str) or not dim.strip():
            raise ValueError(f"item[{idx}].dimension invalide")
        if "score" not in it:
            raise ValueError(f"item[{idx}] clé 'score' manquante")
        sc = it.get("score")
        if not _is_int_strict(sc):
            raise ValueError(f"item[{idx}].score doit être int-only (reçu: {type(sc).__name__})")
        if sc < SCORE_MIN or sc > SCORE_MAX:
            raise ValueError(f"item[{idx}].score hors borne [{SCORE_MIN},{SCORE_MAX}]: {sc}")


def _agg(values: List[float], mode: str) -> float:
    if not values:
        return 0.0
    m = (mode or "median").strip().lower()
    if m == "bottleneck":
        return float(min(values))
    # default median
    return float(median(values))


def _normalize_tau_label(dim: str) -> str:
    if dim == "τ":
        return "tau"
    if dim == "tau":
        return "τ"
    return dim


def aggregate_dimension_scores(data: Dict[str, Any], agg_modes: Dict[str, str]) -> Dict[str, float]:
    buckets: Dict[str, List[float]] = {}
    for it in data.get("items", []) or []:
        dim = it.get("dimension")
        if not dim:
            continue
        sc = float(it.get("score", 0))
        buckets.setdefault(str(dim), []).append(sc)

    out: Dict[str, float] = {}
    for dim, vals in buckets.items():
        mode = agg_modes.get(dim) or agg_modes.get(_normalize_tau_label(dim)) or "median"
        out[dim] = _agg(vals, mode)
    return out


def compute_metrics(dims: Dict[str, float]) -> Tuple[float, float]:
    tau_val = float(dims.get("τ", dims.get("tau", 0.0)))
    Cx = float(dims.get("Cx", 0.0))
    K = float(dims.get("K", 0.0))
    G = float(dims.get("G", 0.0))
    D = float(dims.get("D", 0.0))

    denom = 1.0 + tau_val + G + D + Cx
    K_eff = K / denom if denom != 0 else 0.0
    T = Cx + tau_val + G + D - K_eff
    return T, K_eff


def assign_zone(T: float) -> str:
    t0, t1, t2 = ZONE_THRESHOLDS
    if T <= t0:
        return ZONE_LABELS[0]
    if T <= t1:
        return ZONE_LABELS[1]
    if T <= t2:
        return ZONE_LABELS[2]
    return ZONE_LABELS[3]


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="phi_otimes_o_instrument_v0_1",
        description="PhiO instrument CLI (contract-driven).",
    )
    sub = p.add_subparsers(dest="cmd", required=False)

    sp_t = sub.add_parser("new-template", help="Generate a pytest template JSON")
    sp_t.add_argument("--name", default="Template", help="system.name")
    sp_t.add_argument("--out", required=True, help="Output JSON path")

    sp_s = sub.add_parser("score", help="Score an input JSON and write results.json to outdir")
    sp_s.add_argument("--input", required=True, help="Input JSON path")
    sp_s.add_argument("--outdir", required=True, help="Output directory")

    for d in ["Cx", "K", "G", "D"]:
        sp_s.add_argument(f"--agg_{d}", default="median", help=f"Aggregation for {d} (median|bottleneck)")
    sp_s.add_argument("--agg_τ", dest="agg_tau_unicode", default=None, help="Aggregation for τ (median|bottleneck)")
    sp_s.add_argument("--agg_tau", dest="agg_tau_ascii", default=None, help="Aggregation for tau (median|bottleneck)")
    sp_s.add_argument("--bottleneck", action="store_true", help="Alias: set all aggregations to bottleneck")

    return p.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    import sys

    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv == ["--help"] or argv == ["-h"]:
        parser = argparse.ArgumentParser(
            prog="phi_otimes_o_instrument_v0_1",
            description="PhiO instrument CLI (contract-driven).",
        )
        sub = parser.add_subparsers(dest="cmd")
        sub.add_parser("new-template", help="Generate a pytest template JSON")
        sub.add_parser("score", help="Score an input JSON and write results.json to outdir")
        parser.add_argument("--input", help="(score) input JSON")
        parser.add_argument("--outdir", help="(score) output directory")
        parser.add_argument("--agg_Cx", help="Aggregation for Cx")
        parser.add_argument("--agg_K", help="Aggregation for K")
        parser.add_argument("--agg_G", help="Aggregation for G")
        parser.add_argument("--agg_D", help="Aggregation for D")
        parser.add_argument("--agg_τ", help="Aggregation for τ")
        parser.add_argument("--agg_tau", help="Aggregation for tau")
        parser.add_argument("--bottleneck", help="Use bottleneck aggregation")
        parser.print_help()
        return 0

    args = parse_args(argv)

    try:
        if args.cmd == "new-template":
            tpl = build_template(name=args.name)
            outp = Path(args.out)
            outp.parent.mkdir(parents=True, exist_ok=True)
            outp.write_text(json.dumps(tpl, ensure_ascii=False, indent=2), encoding="utf-8")
            return 0

        if args.cmd == "score":
            inp = Path(args.input)
            data = json.loads(inp.read_text(encoding="utf-8"))

            validate_input(data)

            agg_modes = {
                "Cx": getattr(args, "agg_Cx", "median"),
                "K": getattr(args, "agg_K", "median"),
                "G": getattr(args, "agg_G", "median"),
                "D": getattr(args, "agg_D", "median"),
            }
            tau_mode = args.agg_tau_unicode or args.agg_tau_ascii or "median"
            agg_modes["τ"] = tau_mode
            agg_modes["tau"] = tau_mode

            if getattr(args, "bottleneck", False):
                for k in list(agg_modes.keys()):
                    agg_modes[k] = "bottleneck"

            dim_scores = aggregate_dimension_scores(data, agg_modes)
            T, K_eff = compute_metrics(dim_scores)
            zone = assign_zone(T)

            outdir = Path(args.outdir)
            outdir.mkdir(parents=True, exist_ok=True)
            out = {
                "instrument": {"id": __instrument_id__, "version": __version__},
                "dimension_scores": dim_scores,
                "T": T,
                "K_eff": K_eff,
                "zone": zone,
            }
            (outdir / "results.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
            return 0

        return 2

    except Exception as e:
        # Contract: non-zero returncode on invalid input
        sys.stderr.write(str(e) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
