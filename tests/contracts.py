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
    - Retourner un dict minimal descriptif
    - Retourner None si rien de plausible n'est détecté

    Aucune validation sémantique, aucun jugement.
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

    candidates: list[dict[str, Any]] = []

    def _is_interesting_name(name: str) -> bool:
        u = name.upper()
        return any(k in u for k in ("ZONE", "ZONING", "THRESH", "THRESHOLD", "MAP"))

    def _try_literal(node: ast.AST) -> Optional[Any]:
        try:
            return ast.literal_eval(node)
        except Exception:
            return None

    def _is_mapping(obj: Any) -> bool:
        return isinstance(obj, dict) and len(obj) > 0

    def _kind(name: str, mapping: dict) -> str:
        if any(isinstance(v, (int, float)) for v in mapping.values()):
            return "thresholds"
        return "mapping"

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue

        targets = []
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            value = node.value
        else:
            if isinstance(node.target, ast.Name):
                targets = [node.target.id]
                value = node.value
            else:
                continue

        if value is None:
            continue

        lit = _try_literal(value)
        if not _is_mapping(lit):
            continue

        for name in targets:
            if _is_interesting_name(name):
