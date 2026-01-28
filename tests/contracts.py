from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, Optional


def extract_zone_thresholds_ast(instrument_path: str) -> Optional[Dict[str, Any]]:
    """
    Extraction best-effort de structures type mapping/thresholds depuis un script python.
    Descriptive-only: on vérifie uniquement la forme, jamais le sens.
    """
    p = Path(instrument_path)
    if not p.exists() or not p.is_file():
        return None

    try:
        source = p.read_text(encoding="utf-8")
    except Exception:
        return None

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    def is_interesting(name: str) -> bool:
        u = name.upper()
        return any(k in u for k in ("ZONE", "ZONING", "THRESH", "THRESHOLD", "MAP", "MAPPING"))

    def try_lit(node: ast.AST) -> Optional[Any]:
        try:
            return ast.literal_eval(node)
        except Exception:
            return None

    candidates: list[dict[str, Any]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            target_names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            lit = try_lit(node.value)
            if isinstance(lit, dict) and lit and any(is_interesting(n) for n in target_names):
                for name in target_names:
                    if is_interesting(name):
                        key = "thresholds" if any(isinstance(v, (int, float)) for v in lit.values()) else "mapping"
                        candidates.append({"pattern": f"assign:{name}", key: lit})

        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.value is not None and is_interesting(node.target.id):
                lit = try_lit(node.value)
                if isinstance(lit, dict) and lit:
                    key = "thresholds" if any(isinstance(v, (int, float)) for v in lit.values()) else "mapping"
                    candidates.append({"pattern": f"annassign:{node.target.id}", key: lit})

    if not candidates:
        return None

    def score(c: dict[str, Any]) -> int:
        d = c.get("thresholds") or c.get("mapping") or {}
        return len(d) if isinstance(d, dict) else 0

    candidates.sort(key=score, reverse=True)
    return candidates[0]
