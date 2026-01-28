```python
# tests/contracts.py

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, Optional


def extract_zone_thresholds_ast(instrument_path: str) -> Optional[Dict[str, Any]]:
    """
    Heuristique AST, descriptive-only.

    Objectif:
    - Lire le fichier instrument (script python)
    - Détecter une définition "seuils" ou "mapping" de zones si elle existe
    - Retourner un dict minimal:
        {"pattern": "<string>", "thresholds": {...}} ou {"pattern": "<string>", "mapping": {...}}
    - Retourner None si rien de plausible n'est détecté

    Aucune validation sémantique, aucun jugement, juste extraction best-effort.
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

    # Marqueur optionnel d'absence explicite (si tu veux documenter "pas stable")
    # Exemple: PHIO_NO_ZONE_THRESHOLDS = True
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "PHIO_NO_ZONE_THRESHOLDS":
                    try:
                        v = ast.literal_eval(node.value)
                        if v is True:
                            return None
                    except Exception:
                        pass

    candidates: list[dict[str, Any]] = []

    def _is_interesting_name(name: str) -> bool:
        u = name.upper()
        keywords = ("ZONE", "ZONING", "THRESH", "THRESHOLD", "MAPPING", "MAP")
        return any(k in u for k in keywords)

    def _try_literal(value_node: ast.AST) -> Optional[Any]:
        try:
            return ast.literal_eval(value_node)
        except Exception:
            return None

    def _is_plausible_mapping(obj: Any) -> bool:
        if not isinstance(obj, dict):
            return False
        if len(obj) == 0:
            return False

        ok_key = (str, int, float)
        ok_val = (str, int, float, tuple, list, dict)

        for k, v in obj.items():
            if not isinstance(k, ok_key):
                return False
            if not isinstance(v, ok_val):
                return False
        return True

    def _best_kind(varname: str, mapping_obj: dict) -> str:
        u = varname.upper()
        if "MAP" in u or "MAPPING" in u:
            return "mapping"
        # Heuristique: si les valeurs sont numériques, on préfère "thresholds"
        numeric_vals = 0
        for v in mapping_obj.values():
            if isinstance(v, (int, float)):
                numeric_vals += 1
        if numeric_vals >= max(1, len(mapping_obj) // 2):
            return "thresholds"
        return "mapping"

    # 1) Chercher les Assign du style: ZONE_THRESHOLDS = {...}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue

        target_names: list[str] = []
        for t in node.targets:
            if isinstance(t, ast.Name):
                target_names.append(t.id)

        if not target_names:
            continue

        for name in target_names:
            if not _is_interesting_name(name):
                continue

            lit = _try_literal(node.value)
            if _is_plausible_mapping(lit):
                kind = _best_kind(name, lit)
                candidates.append(
                    {
                        "pattern": f"assign:{name}",
                        kind: lit,
                    }
                )

    # 2) Chercher les AnnAssign du style: ZONE_THRESHOLDS: dict = {...}
    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name):
            continue

        name = node.target.id
        if not _is_interesting_name(name):
            continue

        if node.value is None:
            continue

        lit = _try_literal(node.value)
        if _is_plausible_mapping(lit):
            kind = _best_kind(name, lit)
            candidates.append(
                {
                    "pattern": f"annassign:{name}",
                    kind: lit,
                }
            )

    # 3) Si rien, tenter un pattern "dict([...])" ou "mapping = dict(...)"
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue

        target_names: list[str] = []
        for t in node.targets:
            if isinstance(t, ast.Name):
                target_names.append(t.id)

        if not target_names:
            continue

        call = node.value
        if not isinstance(call, ast.Call):
            continue
        if not isinstance(call.func, ast.Name) or call.func.id != "dict":
            continue

        # dict([("a", 1), ("b", 2)]) ou dict(a=1, b=2)
        constructed: Optional[dict] = None

        # dict(a=1, b=2)
        if call.keywords:
            d: dict[Any, Any] = {}
            ok = True
            for kw in call.keywords:
                if kw.arg is None:
                    ok = False
                    break
                val = _try_literal(kw.value)
                if val is None:
                    ok = False
                    break
                d[kw.arg] = val
            if ok and _is_plausible_mapping(d):
                constructed = d

        # dict([("a",1),("b",2)])
        if constructed is None and call.args:
            lit = _try_literal(call.args[0])
            if isinstance(lit, (list, tuple)):
                d = {}
                ok = True
                for item in lit:
                    if not (isinstance(item, (list, tuple)) and len(item) == 2):
                        ok = False
                        break
                    k, v = item
                    d[k] = v
                if ok and _is_plausible_mapping(d):
                    constructed = d

        if constructed is None:
            continue

        for name in target_names:
            if not _is_interesting_name(name):
                continue
            kind = _best_kind(name, constructed)
            candidates.append(
                {
                    "pattern": f"assign:dictcall:{name}",
                    kind: constructed,
                }
            )

    if not candidates:
        return None

    # Si plusieurs candidats, on prend le plus "riche" (le plus d'entrées)
    def _score(c: dict[str, Any]) -> int:
        if "thresholds" in c and isinstance(c["thresholds"], dict):
            return len(c["thresholds"])
        if "mapping" in c and isinstance(c["mapping"], dict):
            return len(c["mapping"])
        return 0

    candidates.sort(key=_score, reverse=True)
    return candidates[0]
```
