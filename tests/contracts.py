from __future__ import annotations

import ast
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ----------------------------
# CLI helpers (used by tests)
# ----------------------------

def run_help(instrument_path: str) -> str:
    """Run instrument --help and return combined stdout+stderr (never raises)."""
    res = subprocess.run(
        ["python3", instrument_path, "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return (res.stdout or "") + (res.stderr or "")


def _extract_long_flags(help_text: str) -> List[str]:
    """
    Extract long flags from argparse-like help.
    Supports unicode tokens (ex: --agg_τ).
    Returns unique sorted list.
    """
    flags = re.findall(r"(?<!\w)(--[0-9A-Za-z_\-τ]+)", help_text)
    flags = [f.strip() for f in flags if f.strip()]
    return sorted(set(flags))


def parse_help_flags(help_text: str) -> Dict[str, Any]:
    """
    Tests expect a dict with keys:
      - has_new_template
      - mentions_agg
      - mentions_bottleneck

    Also exposes raw long flags list under key "flags".
    """
    flags_list = _extract_long_flags(help_text)
    txt = help_text.lower()

    has_new_template = ("new-template" in txt)
    has_score = (re.search(r"\bscore\b", txt) is not None)

    mentions_agg = (
        "--agg_tau" in flags_list
        or "--agg_τ" in flags_list
        or "agg_" in txt
        or "--agg" in txt
    )

    mentions_bottleneck = ("bottleneck" in txt)

    has_tau_ascii = ("--agg_tau" in flags_list)
    has_tau_unicode = ("--agg_τ" in flags_list)

    return {
        "flags": flags_list,
        "has_new_template": has_new_template,
        "has_score": has_score,
        "mentions_agg": mentions_agg,
        "mentions_bottleneck": mentions_bottleneck,
        "has_tau_ascii": has_tau_ascii,
        "has_tau_unicode": has_tau_unicode,
    }


def detect_tau_agg_flag(help_or_flags: Any) -> Dict[str, bool]:
    """
    Detect presence of tau aggregation flags.

    Accepts:
      - help text (str)
      - list/tuple/set of flags
      - dict returned by parse_help_flags (contains key "flags")
    """
    if isinstance(help_or_flags, str):
        flags = parse_help_flags(help_or_flags)["flags"]
    elif isinstance(help_or_flags, dict):
        flags = list(help_or_flags.get("flags", []))
    else:
        flags = list(help_or_flags)

    s = set(flags)
    return {
        "has_tau_ascii": "--agg_tau" in s,
        "has_tau_unicode": "--agg_τ" in s,
    }


def extract_cli_contract(help_text: str) -> Dict[str, Any]:
    """
    Minimal contract summary used by contract_probe.
    Keeps:
      - flags as list
      - tau_aliases dict
    """
    parsed = parse_help_flags(help_text)
    flags_list = parsed["flags"]

    subcommands: List[str] = []
    for cmd in ["new-template", "score"]:
        if re.search(rf"\b{re.escape(cmd)}\b", help_text):
            subcommands.append(cmd)

    tau_aliases = detect_tau_agg_flag(flags_list)

    return {
        "help_valid": len(help_text.strip()) > 0,
        "help_len": len(help_text),
        "subcommands": sorted(set(subcommands)),
        "flags": flags_list,
        "required_subcommands": ["new-template", "score"],
        "required_flags": ["--input", "--outdir"],
        "tau_aliases": tau_aliases,
    }


# ----------------------------
# AST helpers (zones extraction)
# ----------------------------

def _literal_eval_safe(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _collect_if_chain(node: ast.If) -> Optional[List[ast.If]]:
    # Collect a linear if/elif chain: if -> elif -> elif ...
    chain: List[ast.If] = []
    cur: Optional[ast.If] = node
    while isinstance(cur, ast.If):
        chain.append(cur)
        if cur.orelse and len(cur.orelse) == 1 and isinstance(cur.orelse[0], ast.If):
            cur = cur.orelse[0]
        else:
            break
    return chain if chain else None


def _extract_threshold_from_test(test: ast.AST) -> Optional[float]:
    # Accept simple Compare: T <= 0.5, T < 1.0, etc.
    if not isinstance(test, ast.Compare):
        return None
    if len(test.ops) != 1 or len(test.comparators) != 1:
        return None

    left = test.left
    right = test.comparators[0]
    if not isinstance(left, ast.Name):
        return None
    if left.id not in {"T", "t"}:
        return None

    val = _literal_eval_safe(right)
    if _is_number(val):
        return float(val)
    return None


def _extract_zone_from_body(body: List[ast.stmt]) -> Optional[str]:
    # Accept assignment: zone = "Z0"
    for st in body:
        if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name):
            if st.targets[0].id in {"zone", "Z", "label"}:
                val = _literal_eval_safe(st.value)
                if isinstance(val, str) and val:
                    return val
    return None


def _parse_if_chain_for_T(chain: List[ast.If]) -> Tuple[List[float], List[str]]:
    thresholds: List[float] = []
    zones: List[str] = []

    for n in chain:
        th = _extract_threshold_from_test(n.test)
        z = _extract_zone_from_body(n.body)
        if th is None or z is None:
            return ([], [])
        thresholds.append(float(th))
        zones.append(str(z))
    return thresholds, zones


def extract_zone_thresholds_ast(instrument_path: str) -> Optional[Dict[str, Any]]:
    """
    Heuristic AST extraction of zone logic. Returns a dict with either:
      - {"thresholds": [...], "pattern": "assign"} for numeric cutpoints
      - {"mapping": {...}, "pattern": "assign"} for dict-based zones
      - {"thresholds": [...], "zones": [...], "pattern": "if_chain"} for if/elif chain
    or None if not detected (conservative).

    Debug: set env PHIO_DEBUG_AST=1.
    """
    debug = os.environ.get("PHIO_DEBUG_AST", "0") == "1"

    p = Path(instrument_path)
    if not p.exists():
        if debug:
            print(f"[PHIO_DEBUG_AST] instrument not found: {instrument_path}")
        return None

    src = p.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        if debug:
            print(f"[PHIO_DEBUG_AST] ast.parse SyntaxError: {e}")
        return None

    # 1) Look for assignments to obvious names
    candidate_names = {"ZONE_THRESHOLDS", "ZONES", "ZONE_BOUNDS", "ZONE_LIMITS", "ZONE_CUTS", "THRESHOLDS"}

    def _handle_assign(name: str, value_node: ast.AST) -> Optional[Dict[str, Any]]:
        val = _literal_eval_safe(value_node)
        if debug:
            print(f"[PHIO_DEBUG_AST] assign {name} -> {val!r}")

        if isinstance(val, (list, tuple)) and len(val) > 0 and all(_is_number(x) for x in val):
            return {"thresholds": [float(x) for x in val], "pattern": "assign", "name": name}

        if isinstance(val, dict) and len(val) > 0:
            return {"mapping": val, "pattern": "assign", "name": name}

        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in candidate_names:
                    out = _handle_assign(t.id, node.value)
                    if out:
                        return out

        if isinstance(node, ast.AnnAssign):
            t = node.target
            if isinstance(t, ast.Name) and t.id in candidate_names and node.value is not None:
                out = _handle_assign(t.id, node.value)
                if out:
                    return out

    # 2) Look for if/elif chain setting zone based on T comparisons
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            chain = _collect_if_chain(node)
            if not chain:
                continue
            ths, z = _parse_if_chain_for_T(chain)
            if ths and z and len(ths) == len(z):
                if debug:
                    print(f"[PHIO_DEBUG_AST] if_chain thresholds={ths} zones={z}")
                return {"thresholds": ths, "zones": z, "pattern": "if_chain"}

    if debug:
        print("[PHIO_DEBUG_AST] no zones pattern detected")
    return None
