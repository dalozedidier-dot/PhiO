#!/usr/bin/env python3
"""
PhiO v0.1 — minimal, contract-oriented instrument

This file is intentionally self-contained (stdlib-only) to keep CI deterministic.

CLI contract (tests/):
- subcommands: new-template, score
- flags: --input, --outdir (score)
- aggregation: --agg_<DIM> {median,bottleneck} including tau aliases --agg_tau and --agg_τ
Outputs:
- results.json in outdir with keys: T, K_eff, zone, dimension_scores
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple


# ----------------------------
# Core dimensions (contract)
# ----------------------------
CORE_DIMS: Tuple[str, ...] = ("Cx", "K", "τ", "G", "D")


def _median(values: Sequence[float]) -> float:
    # statistics.median handles odd/even; cast for safety
    return float(statistics.median(list(values)))


def _aggregate_for_dim(dim: str, scores: List[float], method: str) -> float:
    """
    Aggregation policy:
      - median: statistical median
      - bottleneck: "worst-case for stability" -> maximize positive dims, minimize K
        (so T increases, K_eff decreases, matching test contract)
    """
    if not scores:
        raise ValueError(f"No scores for dimension {dim}")

    m = method.lower().strip()
    if m == "median":
        return _median(scores)
    if m == "bottleneck":
        if dim == "K":
            return float(min(scores))
        return float(max(scores))
    raise ValueError(f"Unknown aggregation method: {method}")


def _validate_input(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    if not isinstance(payload, dict):
        raise ValueError("Input must be a JSON object")
    system = payload.get("system", {})
    items = payload.get("items", [])
    if not isinstance(items, list):
        raise ValueError("'items' must be a list")

    # strict item validation (tests expect failures)
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            raise ValueError(f"Item #{i} must be an object")
        if "dimension" not in it:
            raise ValueError(f"Item #{i} missing 'dimension'")
        if "score" not in it:
            raise ValueError(f"Item #{i} missing 'score'")

        dim = it.get("dimension")
        if not isinstance(dim, str) or not dim.strip():
            raise ValueError(f"Item #{i} invalid 'dimension'")

        score = it.get("score")
        if isinstance(score, bool) or not isinstance(score, int):
            raise ValueError(f"Item #{i} 'score' must be int (0..3)")
        if score < 0 or score > 3:
            raise ValueError(f"Item #{i} 'score' out of range (0..3)")

        w = it.get("weight", 1.0)
        if isinstance(w, bool) or not isinstance(w, (int, float)):
            raise ValueError(f"Item #{i} 'weight' must be numeric")
        if float(w) <= 0:
            raise ValueError(f"Item #{i} 'weight' must be > 0")

    return system, items


def _dimension_scores(items: List[Dict[str, Any]], agg_map: Dict[str, str]) -> Dict[str, float]:
    # collect scores by dimension (replicate by weight if non-integer? keep simple weighted list)
    by_dim: Dict[str, List[float]] = {}
    for it in items:
        dim = str(it["dimension"])
        sc = float(it["score"])
        w = float(it.get("weight", 1.0))
        # encode weight as multiplicity (bounded) to keep deterministic & simple
        mult = max(1, int(round(w)))
        by_dim.setdefault(dim, []).extend([sc] * mult)

    out: Dict[str, float] = {}
    for dim, scores in by_dim.items():
        method = agg_map.get(dim, "median")
        out[dim] = _aggregate_for_dim(dim, scores, method)
    return out


def _compute_metrics(ds: Dict[str, float]) -> Tuple[float, float]:
    # tau alias resolution
    tau = ds.get("τ", ds.get("tau", 0.0))
    Cx = ds.get("Cx", 0.0)
    K = ds.get("K", 0.0)
    G = ds.get("G", 0.0)
    D = ds.get("D", 0.0)

    denom = 1.0 + tau + G + D + Cx
    # prevent division by zero (though denom >= 1 by construction)
    K_eff = float(K) / float(denom) if denom != 0 else float("inf")
    T = float(Cx + tau + G + D - K_eff)
    return T, K_eff


def _zone_from_T(T: float) -> str:
    # simple stable zoning. Not used as a hard constraint except presence,
    # and optional robustness case can be provided to avoid boundary flakiness.
    if T < 0.0:
        return "Z0"
    if T < 1.0:
        return "Z1"
    if T < 2.0:
        return "Z2"
    if T < 3.0:
        return "Z3"
    return "Z4"


def cmd_new_template(args: argparse.Namespace) -> int:
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # template includes core dims; scores default 2 (mid) to avoid boundaries
    items = []
    for d in CORE_DIMS:
        items.append(
            {
                "dimension": d,
                "score": 2,
                "weight": 1.0,
                "justification": "template",
            }
        )

    payload = {
        "system": {"name": args.name, "description": "template", "context": "cli"},
        "items": items,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def _parse_agg_pairs(rest: List[str]) -> Dict[str, str]:
    """
    Parse unknown args as pairs:
      --agg_<DIM> <METHOD>
    where METHOD in {median, bottleneck}.
    """
    agg: Dict[str, str] = {}
    i = 0
    while i < len(rest):
        tok = rest[i]
        if not tok.startswith("--agg_"):
            raise ValueError(f"Unknown argument: {tok}")
        dim = tok[len("--agg_") :]
        if not dim:
            raise ValueError("Invalid aggregation flag")
        if i + 1 >= len(rest):
            raise ValueError(f"Aggregation flag missing value: {tok}")
        method = rest[i + 1]
        agg[dim] = method
        i += 2
    # normalize tau aliases
    if "tau" in agg and "τ" not in agg:
        # keep both views consistent
        agg["τ"] = agg["tau"]
    if "τ" in agg and "tau" not in agg:
        agg["tau"] = agg["τ"]
    return agg


def cmd_score(args: argparse.Namespace, rest: List[str]) -> int:
    inp = Path(args.input).expanduser().resolve()
    outdir = Path(args.outdir).expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    try:
        payload = json.loads(inp.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Invalid JSON input: {e}")
        return 1

    try:
        _system, items = _validate_input(payload)
    except Exception as e:
        print(str(e))
        return 1

    try:
        agg_map = _parse_agg_pairs(rest)
    except Exception as e:
        print(str(e))
        return 2  # align with argparse-style "usage" errors

    ds = _dimension_scores(items, agg_map)
    T, K_eff = _compute_metrics(ds)
    res = {
        "T": T,
        "K_eff": K_eff,
        "zone": _zone_from_T(T),
        "dimension_scores": ds,
    }

    (outdir / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="PhiO", description="PhiO v0.1 instrument (contract harness).", epilog="Contract flags: --input --outdir --agg_tau --agg_τ (aggregation: median|bottleneck).")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_new = sub.add_parser("new-template", help="Generate a template JSON input.")
    p_new.add_argument("--name", required=True, help="System name")
    p_new.add_argument("--out", required=True, help="Output JSON file path")
    p_new.set_defaults(_handler=cmd_new_template)

    p_score = sub.add_parser("score", help="Score a JSON input and write results.json")
    p_score.add_argument("--input", required=True, help="Input JSON file")
    p_score.add_argument("--outdir", required=True, help="Output directory (results.json)")
    # Do NOT define all --agg_* explicitly; accept as extra args.
    # But ensure tau aliases are visible in help:
    p_score.add_argument("--agg_tau", help="Aggregation for tau (alias). Use with value: median|bottleneck", required=False)
    p_score.add_argument("--agg_τ", help="Aggregation for τ (alias). Use with value: median|bottleneck", required=False)

    return p


def main(argv: List[str] | None = None) -> int:
    import sys

    argv = list(sys.argv[1:] if argv is None else argv)

    parser = build_parser()

    # We want to accept dynamic --agg_<DIM> pairs.
    # argparse can't handle arbitrary options; we parse known args first.
    args, rest = parser.parse_known_args(argv)

    # If user used the explicit tau alias options, translate them into rest pairs.
    # They are defined only for help visibility and basic parsing.
    # If present, we append them as if they were dynamic flags.
    # Remove them from args to avoid confusion.
    if getattr(args, "agg_tau", None) is not None:
        rest = ["--agg_tau", args.agg_tau] + rest
    if getattr(args, "agg_τ", None) is not None:
        rest = ["--agg_τ", args.__dict__["agg_τ"]] + rest

    if args.cmd == "new-template":
        return cmd_new_template(args)
    if args.cmd == "score":
        # remap dim token for tau variants: allow users to pass --agg_τ or --agg_tau as dynamic flags too.
        # _parse_agg_pairs already normalizes.
        try:
            return cmd_score(args, rest)
        except Exception as e:
            print(str(e))
            return 1

    print("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())