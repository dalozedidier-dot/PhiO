#!/usr/bin/env python3
"""
validate_traceability.py
- Validates traceability_cases.json against basic invariants (no external deps).
- Intended to be run in CI / locally.

Exit codes:
 0 = OK
 2 = invalid file / parse error
 3 = invariant violation
"""
from __future__ import annotations
import json, sys, os, re

ALLOWED_VERDICTS = {"INCOMPATIBLE","INCONCLUSIF","COMPATIBLE_PARTIELLE","COMPATIBLE"}

def die(code:int, msg:str)->None:
    print(msg, file=sys.stderr)
    sys.exit(code)

def is_vec(v, n):
    return isinstance(v, list) and len(v)==n and all(isinstance(x,int) and 0<=x<=2 for x in v)

def main(path:str)->int:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        die(2, f"ERROR: cannot read/parse {path}: {e}")

    if not isinstance(data, list):
        die(3, "ERROR: root must be a JSON array")

    seen = set()
    for i, case in enumerate(data):
        if not isinstance(case, dict):
            die(3, f"ERROR: case[{i}] must be an object")

        cid = case.get("case_id")
        if not isinstance(cid, str) or not re.fullmatch(r"[0-9]{4}", cid):
            die(3, f"ERROR: case[{i}].case_id must be 4 digits")
        if cid in seen:
            die(3, f"ERROR: duplicate case_id: {cid}")
        seen.add(cid)

        pre_source = case.get("pre_source")
        if not isinstance(pre_source, str) or not pre_source.strip():
            die(3, f"ERROR: case[{i}].pre_source must be non-empty string")

        pre = case.get("pre")
        post = case.get("post")
        if not isinstance(pre, dict) or not isinstance(post, dict):
            die(3, f"ERROR: case[{i}].pre and .post must be objects")

        A_pre, B_pre = pre.get("A"), pre.get("B")
        if not is_vec(A_pre, 5) or not is_vec(B_pre, 3):
            die(3, f"ERROR: case[{i}].pre.A must be 5 ints 0..2 and pre.B 3 ints 0..2")

        A_post, B_post = post.get("A"), post.get("B")
        if A_post is not None and not is_vec(A_post, 5):
            die(3, f"ERROR: case[{i}].post.A must be null or 5 ints 0..2")
        if B_post is not None and not is_vec(B_post, 3):
            die(3, f"ERROR: case[{i}].post.B must be null or 3 ints 0..2")

        verdict = case.get("verdict_E")
        if verdict not in ALLOWED_VERDICTS:
            die(3, f"ERROR: case[{i}].verdict_E must be one of {sorted(ALLOWED_VERDICTS)}")

    print(f"OK: {len(data)} cases validated ({path})")
    return 0

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "traceability_cases.json"
    sys.exit(main(path))
