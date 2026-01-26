import ast
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
    # even if returncode != 0, keep stdout+stderr for diagnostics
    return (res.stdout or "") + "\n" + (res.stderr or "")

def parse_help_flags(help_text: str) -> Dict[str, bool]:
    ht = help_text.lower()
    return {
        "has_new_template": "new-template" in ht or "new_template" in ht,
        "has_score": re.search(r"\bscore\b", ht) is not None,
        "mentions_bottleneck": "bottleneck" in ht,
        "mentions_agg": "--agg" in ht or "agg_" in ht,
        "mentions_outdir": "--outdir" in ht,
        "mentions_input": "--input" in ht,
        "mentions_tau_unicode": "--agg_τ" in help_text,
        "mentions_tau_ascii": "--agg_tau" in ht,
    }

def detect_tau_agg_flag(help_text: str) -> Optional[str]:
    # Priority: explicit mention in --help
    if "--agg_τ" in help_text:
        return "--agg_τ"
    if "--agg_tau" in help_text.lower():
        return "--agg_tau"
    return None

def extract_zone_thresholds_ast(instrument_path: str) -> Optional[Dict[str, Any]]:
    """Heuristic AST extraction of zone logic.

    Returns a dict with either:
      - {"thresholds": [...], "pattern": "if_chain"} for numeric cutpoints
      - {"mapping": {...}, "pattern": "dict"} for dict-based zones
    or None if not detected.

    This is intentionally conservative: better return None than hallucinate.
    """
    p = Path(instrument_path)
    if not p.exists():
        return None
    src = p.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None

    # 1) Look for assignments to obvious names
    candidate_names = {"ZONE_THRESHOLDS", "ZONES", "ZONE_BOUNDS", "ZONE_LIMITS", "ZONE_CUTS", "THRESHOLDS"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in candidate_names:
                    val = _literal_eval_safe(node.value)
                    if isinstance(val, (list, tuple)) and all(_is_number(x) for x in val):
                        return {"thresholds": list(val), "pattern": "assign", "name": t.id}
                    if isinstance(val, dict):
                        return {"mapping": val, "pattern": "assign", "name": t.id}

    # 2) Look for if/elif chain setting zone based on T comparisons
    # Try to find comparisons like: if T < a: zone="A" elif T < b: zone="B" ...
    thresholds: List[float] = []
    zones: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            chain = _collect_if_chain(node)
            if not chain:
                continue
            # chain: list of (test, body)
            ths, z = _parse_if_chain_for_T(chain)
            if ths and z and len(ths) == len(z):
                return {"thresholds": ths, "zones": z, "pattern": "if_chain"}
    return None

def _literal_eval_safe(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except Exception:
        return None

def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)

def _collect_if_chain(node: ast.If) -> List[Tuple[ast.AST, List[ast.stmt]]]:
    chain = []
    cur = node
    while isinstance(cur, ast.If):
        chain.append((cur.test, cur.body))
        if len(cur.orelse) == 1 and isinstance(cur.orelse[0], ast.If):
            cur = cur.orelse[0]
        else:
            break
    return chain

def _parse_if_chain_for_T(chain: List[Tuple[ast.AST, List[ast.stmt]]]) -> Tuple[List[float], List[str]]:
    thresholds: List[float] = []
    zones: List[str] = []
    for test, body in chain:
        th = _extract_threshold_from_test(test)
        zn = _extract_zone_from_body(body)
        if th is None or zn is None:
            return [], []
        thresholds.append(th)
        zones.append(zn)
    # require strictly increasing thresholds to reduce false matches
    if any(thresholds[i] >= thresholds[i+1] for i in range(len(thresholds)-1)):
        return [], []
    return thresholds, zones

def _extract_threshold_from_test(test: ast.AST) -> Optional[float]:
    # Accept patterns:
    #   T < 3
    #   T <= 3
    #   score_T < 3 (any name containing 'T' is too loose; require Name 'T' or Attribute ending with '.T')
    if not isinstance(test, ast.Compare):
        return None
    if len(test.ops) != 1 or len(test.comparators) != 1:
        return None
    op = test.ops[0]
    if not isinstance(op, (ast.Lt, ast.LtE)):
        return None
    left = test.left
    if isinstance(left, ast.Name) and left.id != "T":
        return None
    if isinstance(left, ast.Attribute) and left.attr != "T":
        return None
    comp = test.comparators[0]
    val = _literal_eval_safe(comp)
    if _is_number(val):
        return float(val)
    return None

def _extract_zone_from_body(body: List[ast.stmt]) -> Optional[str]:
    # Look for assignment: zone = "A" or results["zone"] = "A"
    for st in body:
        if isinstance(st, ast.Assign) and len(st.targets) == 1:
            target = st.targets[0]
            val = _literal_eval_safe(st.value)
            if isinstance(val, str) and len(val) <= 5:
                if isinstance(target, ast.Name) and target.id in {"zone", "Zone"}:
                    return val
                if isinstance(target, ast.Subscript):
                    # results["zone"] = "A"
                    key = _literal_eval_safe(target.slice)
                    if key == "zone":
                        return val
    return None
