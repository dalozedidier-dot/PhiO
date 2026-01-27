#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
contract_probe.py — PhiO CI baseline generator (auto-sufficient zones extraction)

Objectives:
- Generate a strictly-JSON baseline (never python code).
- Deterministic load of ./tests/contracts.py (no 'import tests.contracts').
- Zones extraction:
    1) try tests/contracts.py extractor (if present)
    2) internal AST extractor on instrument file
    3) internal fallback (balanced-bracket capture + ast.literal_eval)
- Write forensics into baseline:
    - _probe_forensics
    - zones._forensics
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# -------------------------
# Utils
# -------------------------

def sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def json_sanitize(obj: Any) -> Any:
    """
    Ensure obj is JSON-serializable (best-effort) without injecting code.
    """
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        # Reduce to safe representation
        if isinstance(obj, (set, tuple)):
            return [json_sanitize(x) for x in obj]
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        if isinstance(obj, Path):
            return str(obj)
        return repr(obj)


# -------------------------
# Deterministic load of ./tests/contracts.py
# -------------------------

def load_contracts_module(repo_root: Path) -> Tuple[Optional[Any], Dict[str, Any]]:
    """
    Deterministically load ./tests/contracts.py via importlib.
    Returns (module_or_none, forensics_dict).
    """
    import importlib.util  # stdlib

    contracts_path = repo_root / "tests" / "contracts.py"
    fx: Dict[str, Any] = {
        "contracts_path": str(contracts_path),
        "contracts_exists": contracts_path.exists(),
        "contracts_loaded": False,
        "contracts_sha256": None,
        "contracts_load_error": None,
    }

    if not contracts_path.exists():
        return None, fx

    try:
        fx["contracts_sha256"] = sha256_file(contracts_path)
    except Exception as e:
        fx["contracts_load_error"] = f"sha256_failed: {type(e).__name__}: {e}"
        return None, fx

    try:
        spec = importlib.util.spec_from_file_location("phio_contracts_local", str(contracts_path))
        if spec is None or spec.loader is None:
            fx["contracts_load_error"] = "spec_from_file_location returned None"
            return None, fx
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
        fx["contracts_loaded"] = True
        return mod, fx
    except Exception as e:
        fx["contracts_load_error"] = f"{type(e).__name__}: {e}"
        return None, fx


# -------------------------
# CLI help probe (subprocess)
# -------------------------

def run_help(instrument_path: Path, timeout_s: int = 20) -> Dict[str, Any]:
    cmd = [sys.executable, str(instrument_path), "--help"]
    out: Dict[str, Any] = {
        "help_valid": False,
        "help_len": 0,
        "subcommands": [],
        "flags": [],
        "required_subcommands": ["new-template", "score"],
        "required_flags": ["--input", "--outdir"],
        "tau_aliases": {"has_tau_ascii": False, "has_tau_unicode": False},
        "_forensics": {
            "cmd": cmd,
            "returncode": None,
            "timeout_s": timeout_s,
            "stderr_tail": None,
        },
    }

    try:
        cp = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
        txt = (cp.stdout or "") + ("\n" + cp.stderr if cp.stderr else "")
        out["_forensics"]["returncode"] = cp.returncode
        out["_forensics"]["stderr_tail"] = (cp.stderr or "")[-400:] if cp.stderr else ""
        out["help_valid"] = (cp.returncode == 0) and (len((cp.stdout or "").strip()) > 0)
        out["help_len"] = len(txt)

        # Flags (include unicode τ possibility)
        flags = set(re.findall(r"(?<!\w)(--[A-Za-z0-9_\-τ]+)", txt))
        out["flags"] = sorted(flags)

        out["tau_aliases"]["has_tau_ascii"] = "--agg_tau" in flags
        out["tau_aliases"]["has_tau_unicode"] = "--agg_τ" in flags

        # Subcommands: best-effort extraction
        # Look for a "Commands:" section then parse until blank line
        subcommands: List[str] = []
        lines = txt.splitlines()
        idx_cmd = None
        for i, line in enumerate(lines):
            if re.search(r"^\s*(Commands|Subcommands)\s*:\s*$", line):
                idx_cmd = i
                break
        if idx_cmd is not None:
            for j in range(idx_cmd + 1, len(lines)):
                if lines[j].strip() == "":
                    break
                m = re.match(r"^\s*([a-z][a-z0-9\-]*)\s{2,}.*$", lines[j].strip())
                if m:
                    subcommands.append(m.group(1))
        out["subcommands"] = sorted(set(subcommands))
        return out

    except subprocess.TimeoutExpired:
        out["_forensics"]["returncode"] = "timeout"
        out["_forensics"]["stderr_tail"] = None
        out["help_valid"] = False
        out["help_len"] = 0
        return out
    except Exception as e:
        out["_forensics"]["returncode"] = "exception"
        out["_forensics"]["stderr_tail"] = f"{type(e).__name__}: {e}"
        out["help_valid"] = False
        out["help_len"] = 0
        return out


# -------------------------
# Zones extraction: internal AST + fallback
# -------------------------

@dataclass
class ZonesExtraction:
    ok: bool
    method: str
    value: Any
    error: Optional[str]
    forensics: Dict[str, Any]


def find_zone_marker_line(text: str) -> Optional[int]:
    # Prefer an assignment-like marker
    for i, line in enumerate(text.splitlines(), start=1):
        if re.match(r"^\s*ZONE_THRESHOLDS\s*=", line):
            return i
    # Fallback: any occurrence
    for i, line in enumerate(text.splitlines(), start=1):
        if "ZONE_THRESHOLDS" in line:
            return i
    return None


def ast_extract_zone_thresholds(text: str) -> Tuple[Optional[Any], Optional[str]]:
    """
    Parse python source and extract the literal value assigned to ZONE_THRESHOLDS if possible.
    Returns (value_or_none, error_or_none).
    """
    try:
        tree = ast.parse(text)
    except Exception as e:
        return None, f"ast_parse_failed: {type(e).__name__}: {e}"

    target_names = {"ZONE_THRESHOLDS"}

    for node in ast.walk(tree):
        # Handle Assign and AnnAssign
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id in target_names:
                    try:
                        return ast.literal_eval(node.value), None
                    except Exception as e:
                        return None, f"literal_eval_failed: {type(e).__name__}: {e}"
        if isinstance(node, ast.AnnAssign):
            tgt = node.target
            if isinstance(tgt, ast.Name) and tgt.id in target_names and node.value is not None:
                try:
                    return ast.literal_eval(node.value), None
                except Exception as e:
                    return None, f"literal_eval_failed: {type(e).__name__}: {e}"

    return None, "not_found_in_ast"


def balanced_capture_after_equals(text: str, name: str = "ZONE_THRESHOLDS") -> Tuple[Optional[str], Optional[str]]:
    """
    Fallback extractor: locate 'NAME =' then capture a balanced bracket expression starting at first
    '[', '{', '(' until matching closing bracket.
    """
    m = re.search(rf"^\s*{re.escape(name)}\s*=\s*", text, flags=re.MULTILINE)
    if not m:
        return None, "assign_marker_not_found"

    start = m.end()
    # Skip whitespace/newlines
    n = len(text)
    i = start
    while i < n and text[i].isspace():
        i += 1
    if i >= n:
        return None, "unexpected_eof_after_equals"

    opener = text[i]
    pairs = {"[": "]", "{": "}", "(": ")"}
    if opener not in pairs:
        return None, f"unexpected_opener:{repr(opener)}"

    closer = pairs[opener]
    stack = [opener]
    j = i + 1
    in_str = None  # type: Optional[str]
    escape = False

    while j < n:
        ch = text[j]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_str:
                in_str = None
            j += 1
            continue

        if ch in ("'", '"'):
            in_str = ch
            j += 1
            continue

        if ch in pairs:
            stack.append(ch)
        elif ch in ("]", "}", ")"):
            if not stack:
                return None, "unbalanced_closing"
            top = stack.pop()
            if pairs[top] != ch:
                return None, "mismatched_brackets"
            if not stack:
                # inclusive capture
                return text[i : j + 1], None
        j += 1

    return None, "unterminated_brackets"


def normalize_zones_to_json_obj(z: Any) -> Tuple[Dict[str, Any], int]:
    """
    Produce a JSON-friendly 'zones' dict + zones_count.
    If input is a list/tuple -> dict keyed by index strings.
    If dict -> use as-is.
    Else -> wrap into {"_value": ...} with count 0.
    """
    if isinstance(z, dict):
        # ensure json-safe
        zz = {str(k): json_sanitize(v) for k, v in z.items()}
        return zz, len(zz)
    if isinstance(z, (list, tuple)):
        zz = {str(i): json_sanitize(v) for i, v in enumerate(z)}
        return zz, len(zz)
    return {"_value": json_sanitize(z)}, 0


def internal_extract_zones(instrument_path: Path) -> ZonesExtraction:
    text = read_text(instrument_path)
    marker_line = find_zone_marker_line(text)
    has_marker = marker_line is not None

    fx: Dict[str, Any] = {
        "instrument_has_ZONE_THRESHOLDS": bool(has_marker),
        "instrument_zone_line": marker_line,
        "instrument_sha256": sha256_file(instrument_path) if instrument_path.exists() else None,
        "instrument_head_sha256": sha256_bytes(text[:2048].encode("utf-8", errors="replace")),
        "internal_ast_error": None,
        "internal_fallback_error": None,
        "internal_fallback_literal_eval_error": None,
        "captured_literal_len": None,
    }

    # AST path
    val, err = ast_extract_zone_thresholds(text)
    if val is not None:
        return ZonesExtracti
