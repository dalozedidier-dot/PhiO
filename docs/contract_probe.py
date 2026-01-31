#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
contract_probe.py — PhiO CI baseline generator (auto-sufficient zones extraction)

Goals:
- Strict JSON baseline (never python code).
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
        if isinstance(obj, (set, tuple)):
            return [json_sanitize(x) for x in obj]
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        if isinstance(obj, Path):
            return str(obj)
        return repr(obj)




def canonicalize_json(obj: Any) -> Any:
    """Recursively sort dict keys for deterministic JSON.

    Lists keep their order (assumed meaningful). Sets/tuples are converted by json_sanitize().
    """
    obj = json_sanitize(obj)
    if isinstance(obj, dict):
        return {k: canonicalize_json(obj[k]) for k in sorted(obj.keys(), key=lambda x: str(x))}
    if isinstance(obj, list):
        return [canonicalize_json(x) for x in obj]
    return obj

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

        flags = set(re.findall(r"(?<!\w)(--[A-Za-z0-9_\-τ]+)", txt))
        out["flags"] = sorted(flags)

        out["tau_aliases"]["has_tau_ascii"] = "--agg_tau" in flags
        out["tau_aliases"]["has_tau_unicode"] = "--agg_τ" in flags

        # Subcommands: best-effort extraction
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

    for node in ast.walk(tree):
        # Handle Assign and AnnAssign
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "ZONE_THRESHOLDS":
                    try:
                        return ast.literal_eval(node.value), None
                    except Exception as e:
                        return None, f"literal_eval_failed: {type(e).__name__}: {e}"
        if isinstance(node, ast.AnnAssign):
            tgt = node.target
            if isinstance(tgt, ast.Name) and tgt.id == "ZONE_THRESHOLDS" and node.value is not None:
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

    stack = [opener]
    j = i + 1
    in_str: Optional[str] = None
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
        return ZonesExtraction(ok=True, method="internal_ast_assign", value=val, error=None, forensics=fx)
    fx["internal_ast_error"] = err

    # Balanced capture + literal_eval
    lit, err2 = balanced_capture_after_equals(text, "ZONE_THRESHOLDS")
    if lit is None:
        fx["internal_fallback_error"] = err2
        return ZonesExtraction(ok=False, method="internal_failed", value=None, error=err2, forensics=fx)

    fx["captured_literal_len"] = len(lit)
    try:
        v2 = ast.literal_eval(lit)
        return ZonesExtraction(ok=True, method="internal_regex_balanced_literal_eval", value=v2, error=None, forensics=fx)
    except Exception as e:
        fx["internal_fallback_literal_eval_error"] = f"{type(e).__name__}: {e}"
        return ZonesExtraction(ok=False, method="internal_failed", value=None, error=fx["internal_fallback_literal_eval_error"], forensics=fx)


# -------------------------
# Optional: call tests/contracts.py extractor (if available)
# -------------------------

def try_tests_extractor(contracts_mod: Any, instrument_path: Path) -> Tuple[Optional[Any], Dict[str, Any]]:
    """
    Try to call extract_zone_thresholds_ast from loaded contracts module.
    Returns (value_or_none, forensics_dict).
    """
    fx: Dict[str, Any] = {
        "tests_extractor_available": False,
        "tests_extractor_called": False,
        "tests_extractor_returned_none": False,
        "tests_extractor_type": None,
        "tests_extractor_error": None,
    }
    if contracts_mod is None:
        return None, fx

    fn = getattr(contracts_mod, "extract_zone_thresholds_ast", None)
    if fn is None or not callable(fn):
        return None, fx

    fx["tests_extractor_available"] = True
    fx["tests_extractor_called"] = True
    try:
        res = fn(str(instrument_path))
        if res is None:
            fx["tests_extractor_returned_none"] = True
            return None, fx
        fx["tests_extractor_type"] = type(res).__name__
        return res, fx
    except Exception as e:
        fx["tests_extractor_error"] = f"{type(e).__name__}: {e}"
        return None, fx


# -------------------------
# Compliance synthesis
# -------------------------

def axis_cli_level(cli: Dict[str, Any]) -> str:
    if not cli.get("help_valid"):
        return "MINIMAL"
    req_flags = set(cli.get("required_flags", []))
    got_flags = set(cli.get("flags", []))
    req_cmds = set(cli.get("required_subcommands", []))
    got_cmds = set(cli.get("subcommands", []))
    if req_flags.issubset(got_flags) and req_cmds.issubset(got_cmds):
        return "FULL"
    return "PARTIAL"


def axis_zones_level(zones_count: int, attempted: bool, method: str) -> str:
    if zones_count > 0:
        return "FULL"
    if attempted:
        return "PARTIAL"
    return "MINIMAL"


def global_level(axes: Dict[str, str]) -> str:
    vals = list(axes.values())
    if all(v == "FULL" for v in vals):
        return "FULL"
    if "FULL" in vals and "MINIMAL" not in vals:
        return "PARTIAL"
    return "MINIMAL"


# -------------------------
# Main
# -------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instrument", required=True, help="Path to instrument python file")
    ap.add_argument("--out", required=True, help="Output baseline JSON path")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parent
    instrument_path = (repo_root / args.instrument).resolve() if not Path(args.instrument).is_absolute() else Path(args.instrument).resolve()
    out_path = (repo_root / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out).resolve()

    probe_path = Path(__file__).resolve()

    probe_fx: Dict[str, Any] = {
        "probe_path": str(probe_path),
        "probe_sha256": sha256_file(probe_path) if probe_path.exists() else None,
        "repo_root": str(repo_root),
        "cwd": os.getcwd(),
        "python": {
            "version": sys.version,
            "executable": sys.executable,
            "platform": platform.platform(),
        },
        "env": {
            "GITHUB_SHA": os.getenv("GITHUB_SHA"),
            "GITHUB_REF": os.getenv("GITHUB_REF"),
            "GITHUB_WORKFLOW": os.getenv("GITHUB_WORKFLOW"),
            "GITHUB_RUN_ID": os.getenv("GITHUB_RUN_ID"),
        },
    }

    contracts_mod, contracts_fx = load_contracts_module(repo_root)
    probe_fx.update({"contracts": contracts_fx})

    baseline: Dict[str, Any] = {
        "contract_version": "1.5",
        "instrument_path": str(instrument_path),
        "instrument_hash": sha256_file(instrument_path) if instrument_path.exists() else None,
        "validation_timestamp": utc_now_iso(),
        "_probe_forensics": probe_fx,
        "compliance": {},
        "summary": {},
        "cli": {},
        "zones": {},
        "formula": {"golden_attempted": False, "golden_pass": False},
    }

    cli = run_help(instrument_path) if instrument_path.exists() else {
        "help_valid": False, "help_len": 0, "subcommands": [], "flags": [],
        "required_subcommands": ["new-template", "score"], "required_flags": ["--input", "--outdir"],
        "tau_aliases": {"has_tau_ascii": False, "has_tau_unicode": False},
        "_forensics": {"cmd": None, "returncode": None, "timeout_s": None, "stderr_tail": "instrument_missing"},
    }
    baseline["cli"] = json_sanitize(cli)

    zones_attempted = True
    tests_val, tests_fx = try_tests_extractor(contracts_mod, instrument_path)
    internal = internal_extract_zones(instrument_path) if instrument_path.exists() else ZonesExtraction(
        ok=False, method="internal_failed", value=None, error="instrument_missing",
        forensics={"instrument_has_ZONE_THRESHOLDS": False, "instrument_zone_line": None}
    )

    zones_method: str
    zones_error: Optional[str]
    zones_value: Any
    chosen_forensics: Dict[str, Any]

    if tests_val is not None:
        zones_method = "tests_extractor"
        zones_value = tests_val
        zones_error = None
        chosen_forensics = {**tests_fx, "internal": json_sanitize(internal.forensics), "chosen": "tests_extractor"}
    elif internal.ok:
        zones_method = internal.method
        zones_value = internal.value
        zones_error = None
        chosen_forensics = {**tests_fx, "internal": json_sanitize(internal.forensics), "chosen": "internal"}
    else:
        zones_method = "ast_failed"  # preserve observed failure label convention
        zones_value = None
        zones_error = internal.error or "unknown"
        chosen_forensics = {**tests_fx, "internal": json_sanitize(internal.forensics), "chosen": "failed"}

    zones_dict, zones_count = normalize_zones_to_json_obj(zones_value) if zones_value is not None else ({}, 0)

    baseline["zones"] = {
        "zones": zones_dict,
        "constants": {},
        "if_chain": [],
        "attempted": zones_attempted,
        "method": zones_method,
        "error": zones_error,
        "_forensics": json_sanitize(chosen_forensics),
    }

    axes = {
        "cli": axis_cli_level(cli),
        "zones": axis_zones_level(zones_count, zones_attempted, str(zones_method)),
        "formula": "MINIMAL",
    }
    baseline["summary"] = {
        "cli_help_valid": bool(cli.get("help_valid")),
        "zones_attempted": True,
        "zones_count": zones_count,
        "formula_checked": False,
        "formula_pass": False,
    }
    baseline["compliance"] = {
        "axes": axes,
        "global": global_level(axes),
        "summary": f"CLI:{axes['cli']}/ZONES:{axes['zones']}/FORMULA:{axes['formula']}",
    }

    baseline = canonicalize_json(baseline)

    ensure_parent_dir(out_path)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(baseline, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
