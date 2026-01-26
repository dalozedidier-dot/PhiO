#!/usr/bin/env python3
"""validate_traceability.py

Validation *sans dépendances* de traceability_cases.json.

Sortie:
- 0: OK
- 2: JSON invalide / parse error
- 3: violation d'invariants
"""

from __future__ import annotations
import json, sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ALLOWED_VERDICTS = {"INCOMPATIBLE","INCONCLUSIF","COMPATIBLE_PARTIELLE","COMPATIBLE"}

def _fail(msg: str, code: int = 3) -> int:
    print(f"ERROR: {msg}", file=sys.stderr)
    return code

def _is_scores(v: Any, n: int) -> bool:
    if not isinstance(v, list) or len(v) != n:
        return False
    for x in v:
        if not isinstance(x, int) or x < 0 or x > 2:
            return False
    return True

def compute_verdict(postA: List[int], postB: List[int]) -> str:
    # Règle déterministe (post)
    mA = min(postA)
    if mA == 0:
        return "INCOMPATIBLE"
    if mA == 1:
        return "INCONCLUSIF"
    # ici: tous A == 2
    return "COMPATIBLE" if min(postB) >= 2 else "COMPATIBLE_PARTIELLE"

def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print("Usage: validate_traceability.py <traceability_cases.json>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    if not path.exists():
        return _fail(f"file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return _fail(f"JSON parse error: {e}", code=2)

    if not isinstance(data, list):
        return _fail("root must be an array")

    seen = set()
    for i, case in enumerate(data):
        if not isinstance(case, dict):
            return _fail(f"case[{i}] must be an object")
        # strict keys
        allowed_keys = {"case_id","pre_source","pre","post","verdict_E","notes"}
        extra = set(case.keys()) - allowed_keys
        if extra:
            return _fail(f"case[{i}] has extra keys: {sorted(extra)}")

        cid = case.get("case_id")
        if not isinstance(cid, str) or not cid.isdigit() or len(cid) != 4:
            return _fail(f"case[{i}].case_id must be 4 digits")
        if cid in seen:
            return _fail(f"duplicate case_id: {cid}")
        seen.add(cid)

        ps = case.get("pre_source")
        if not isinstance(ps, str) or not ps.strip():
            return _fail(f"case[{i}].pre_source must be non-empty string")

        pre = case.get("pre")
        if not isinstance(pre, dict) or set(pre.keys()) != {"A","B"}:
            return _fail(f"case[{i}].pre must have keys A,B only")
        if not _is_scores(pre.get("A"), 5):
            return _fail(f"case[{i}].pre.A must be [5] ints in 0..2")
        if not _is_scores(pre.get("B"), 3):
            return _fail(f"case[{i}].pre.B must be [3] ints in 0..2")

        post = case.get("post")
        if not isinstance(post, dict) or set(post.keys()) != {"A","B"}:
            return _fail(f"case[{i}].post must have keys A,B only")
        postA = post.get("A")
        postB = post.get("B")
        if postA is not None and not _is_scores(postA, 5):
            return _fail(f"case[{i}].post.A must be null or [5] ints in 0..2")
        if postB is not None and not _is_scores(postB, 3):
            return _fail(f"case[{i}].post.B must be null or [3] ints in 0..2")

        verdict = case.get("verdict_E")
        if verdict not in ALLOWED_VERDICTS:
            return _fail(f"case[{i}].verdict_E invalid: {verdict}")

        # If post present, verdict must match rule
        if postA is not None and postB is not None:
            expected = compute_verdict(postA, postB)
            if verdict != expected:
                return _fail(f"case[{i}] verdict mismatch: expected {expected}, got {verdict}")

        notes = case.get("notes")
        if not isinstance(notes, str):
            return _fail(f"case[{i}].notes must be string")

    print(f"OK: {len(data)} cases validated")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
