from __future__ import annotations

import ast
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def run_help(instrument_path: str) -> str:
    res = subprocess.run(
        ["python3", instrument_path, "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    # even if returncode != 0, keep stdout+stderr
    return (res.stdout or "") + (res.stderr or "")


def extract_cli_contract(help_text: str) -> Dict[str, Any]:
    # Minimal heuristics: detect subcommands + flags + tau aliases
    subcommands: List[str] = []
    flags: List[str] = []

    # detect subcommands (very basic)
    for cmd in ["new-template", "score"]:
        if re.search(rf"\b{re.escape(cmd)}\b", help_text):
            subcommands.append(cmd)

    # detect flags
    for f in ["--input", "--outdir", "--agg_tau", "--agg_τ", "--help"]:
        if f in help_text:
            flags.append(f)

    return {
        "help_valid": len(help_text.strip()) > 0,
        "help_len": len(help_text),
        "subcommands": sorted(set(subcommands)),
        "flags": sorted(set(flags)),
        "required_subcommands": ["new-template", "score"],
        "required_flags": ["--input", "--outdir"],
        "tau_aliases": {
            "has_tau_ascii": "--agg_tau" in help_text,
            "has_tau_unicode": "--agg_τ" in help_text,
        },
    }


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
    return chain if len(chain) >= 1 else None


def _parse_if_chain_for_T(chain: List[ast.If]) -> Tuple[List[float], List[str]]:
    # Very conservative: look for comparisons of a variable named "T" or "t" against constants,
    # and assignments to a variable named "zone" or similar.
    thresholds: List[float] = []
    zones: List[str] = []

    for n in chain:
        # Extract threshold from test
        th = _extract_threshold_from_test(n.test)
        z = _extract_zone_from_body(n.body)
        if th is None or z is None:
            return ([], [])
        thresholds.append(float(th))
        zones.append(str(z))
    return thresholds, zones


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


def extract_zone_thresholds_ast(instrument_path: str) -> Optional[Dict[str, Any]]:
    """Heuristic AST extraction of zone logic.

    Returns a dict with either:
      - {"thresholds": [...], "pattern": "if_chain"} for numeric cutpoints
      - {"mapping": {...}, "pattern": "assign"} for dict-based zones
      - {"thresholds": [...], "pattern": "assign"} for literal cutpoints
    or None if not detected.

    This is intentionally conservative: better return None than hallucinate.

    Debug:
      - set env PHIO_DEBUG_AST=1 to print what was detected / why it failed.
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

    # 1) Look for assignments / annotated assignments to obvious names
    candidate_names = {
        "ZONE_THRESHOLDS",
        "ZONES",
        "ZONE_BOUNDS",
        "ZONE_LIMITS",
        "ZONE_CUTS",
        "THRESHOLDS",
    }

    def _handle_assign(name: str, value_node: ast.AST) -> Optional[Dict[str, Any]]:
        val = _literal_eval_safe(value_node)
        if debug:
            print(f"[PHIO_DEBUG_AST] assign {name} -> {val!r}")

        if isinstance(val, (list, tuple)) and len(val) > 0:
            nums: List[float] = []
            for x in val:
                if _is_number(x):
                    nums.append(float(x))
                else:
                    return None
            return {"thresholds": nums, "pattern": "assign", "name": name}

        if isinstance(val, dict) and len(val) > 0:
            return {"mapping": val, "pattern": "assign", "name": name}

        return None

    for node in ast.walk(tree):
        # Plain assignment: NAME = <literal>
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in candidate_names:
                    out = _handle_assign(t.id, node.value)
                    if out:
                        return out

        # Annotated assignment: NAME: Type = <literal>
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
