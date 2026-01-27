from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


# -------------------------
# Utils
# -------------------------

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()


def _safe_read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _load_repo_local_contracts(repo_root: Path) -> Dict[str, Any]:
    """
    Charge ./tests/contracts.py de façon déterministe (pas d'import "tests" ambigu).
    Retourne {"module": mod|None, "path": Path|None, "sha256": str|None, "error": str|None}
    """
    out: Dict[str, Any] = {"module": None, "path": None, "sha256": None, "error": None}

    p = repo_root / "tests" / "contracts.py"
    out["path"] = str(p)
    if not p.exists():
        out["error"] = "tests/contracts.py missing"
        return out

    try:
        out["sha256"] = _sha256_file(p)
        spec = importlib.util.spec_from_file_location("phio_repo_tests_contracts", str(p))
        if spec is None or spec.loader is None:
            out["error"] = "spec_from_file_location failed"
            return out
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
        out["module"] = mod
        return out
    except Exception as e:
        out["error"] = f"load contracts.py failed: {e}"
        return out


def _run_help_fallback(instrument_path: str) -> str:
    res = subprocess.run(
        ["python3", instrument_path, "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return (res.stdout or "") + (res.stderr or "")


# -------------------------
# Zones extraction (internal, no dependency)
# -------------------------

def _extract_zone_thresholds_internal(instrument_src: str) -> Optional[Dict[str, Any]]:
    """
    Extraction robuste des seuils:
      1) AST: ZONE_THRESHOLDS = [..] ou (..)
      2) Regex tolérante: ZONE_THRESHOLDS = [..] / (..), même avec commentaires/trailing

    Retourne:
      {"thresholds":[...], "pattern":"ast_assign"} ou {"thresholds":[...], "pattern":"regex"}
    ou None si rien détecté.
    """
    # 1) AST
    try:
        tree = ast.parse(instrument_src)
        for node in ast.walk(tree):
            # Assign: ZONE_THRESHOLDS = [...]
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "ZONE_THRESHOLDS":
                        try:
                            val = ast.literal_eval(node.value)
                        except Exception:
                            val = None
                        if isinstance(val, (list, tuple)) and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in val):
                            return {"thresholds": [float(x) for x in list(val)], "pattern": "ast_assign"}
            # AnnAssign: ZONE_THRESHOLDS: ... = [...]
            if isinstance(node, ast.AnnAssign):
                t = node.target
                if isinstance(t, ast.Name) and t.id == "ZONE_THRESHOLDS" and node.value is not None:
                    try:
                        val = ast.literal_eval(node.value)
                    except Exception:
                        val = None
                    if isinstance(val, (list, tuple)) and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in val):
                        return {"thresholds": [float(x) for x in list(val)], "pattern": "ast_annassign"}
    except SyntaxError:
        # On ne stoppe pas : on tente regex
        pass
    except Exception:
        pass

    # 2) Regex tolérante (pas d'ancrage fin-de-ligne)
    m = re.search(r"ZONE_THRESHOLDS\s*=\s*\[([^\]]+)\]", instrument_src)
    if not m:
        m = re.search(r"ZONE_THRESHOLDS\s*=\s*\(([^\)]+)\)", instrument_src)
    if not m:
        return None

    inside = m.group(1)
    nums = re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", inside)
    if not nums:
        return None

    return {"thresholds": [float(x) for x in nums], "pattern": "regex"}


def _zones_section(instrument_path: Path, contracts_mod: Optional[Any]) -> Dict[str, Any]:
    """
    Zones = priorité extracteur repo-local si présent, sinon fallback interne.
    Toujours retourne un dict stable.
    """
    instrument_src = _safe_read_text(instrument_path)
    has_marker = "ZONE_THRESHOLDS" in instrument_src

    raw_from_tests = None
    raw_err = None
    if contracts_mod is not None and hasattr(contracts_mod, "extract_zone_thresholds_ast"):
        try:
            raw_from_tests = contracts_mod.extract_zone_thresholds_ast(str(instrument_path))
        except Exception as e:
            raw_err = str(e)
            raw_from_tests = None

    raw_internal = _extract_zone_thresholds_internal(instrument_src)

    chosen = None
    method = None
    error = None

    # Priorité: extracteur tests s'il retourne qqch de valide
    if isinstance(raw_from_tests, dict) and ("thresholds" in raw_from_tests or "mapping" in raw_from_tests or "constants" in raw_from_tests):
        chosen = raw_from_tests
        method = "tests_extractor"
    elif raw_internal is not None:
        chosen = raw_internal
        method = "internal_extractor"
    else:
        chosen = None
        method = "ast_failed"
        if raw_err:
            error = f"tests.extract_zone_thresholds_ast error: {raw_err}"
        elif has_marker:
            error = "extract_zone_thresholds_ast returned None (marker present) + internal extractor found nothing"
        else:
            error = "ZONE_THRESHOLDS marker not found in instrument + no zones detected"

    # Normalisation vers ton schéma actuel (zones/constants/if_chain)
    out: Dict[str, Any] = {
        "zones": {},
        "constants": {},
        "if_chain": [],
        "attempted": True,
        "method": method,
    }
    if error:
        out["error"] = error

    # Diagnostics forensiques (non-narratifs)
    out["_forensics"] = {
        "instrument_has_ZONE_THRESHOLDS": has_marker,
        "instrument_sha256": f"sha256:{_sha256_file(instrument_path)}",
        "instrument_head_sha256": f"sha256:{_sha256_text('\n'.join(instrument_src.splitlines()[:80]))}",
        "tests_extractor_raw_is_none": raw_from_tests is None,
        "tests_extractor_raw_type": type(raw_from_tests).__name__ if raw_from_tests is not None else "NoneType",
        "tests_extractor_error": raw_err,
        "internal_extractor_found": raw_internal is not None,
        "internal_extractor_pattern": (raw_internal or {}).get("pattern") if raw_internal else None,
    }

    # Ligne indicative (si existe)
    zone_line = None
    for i, line in enumerate(instrument_src.splitlines(), 1):
        if "ZONE_THRESHOLDS" in line:
            zone_line = f"{i}: {line.strip()}"
            break
    out["_forensics"]["instrument_zone_line"] = zone_line

    if chosen is None:
        return out

    # Cas thresholds
    if isinstance(chosen, dict) and isinstance(chosen.get("thresholds"), (list, tuple)):
        ths = [
            float(x) for x in list(chosen.get("thresholds"))
            if isinstance(x, (int, float)) and not isinstance(x, bool)
        ]
        out["constants"] = {f"THRESH_{i}": v for i, v in enumerate(ths)}
        out["zones"] = dict(out["constants"])
        out["pattern"] = chosen.get("pattern")

    # Cas mapping
    elif isinstance(chosen, dict) and isinstance(chosen.get("mapping"), dict):
        mp = chosen.get("mapping") or {}
        out["constants"] = {str(k): v for k, v in mp.items()}
        out["zones"] = {str(k): v for k, v in mp.items()}
        out["pattern"] = chosen.get("pattern")

    # Cas constants passthrough (si ton tests extractor retourne déjà constants)
    elif isinstance(chosen, dict) and isinstance(chosen.get("constants"), dict):
        out["constants"] = chosen.get("constants") or {}
        out["zones"] = {k: v for k, v in (out["constants"] or {}).items()}
        out["if_chain"] = chosen.get("if_chain") if isinstance(chosen.get("if_chain"), list) else []
        out["pattern"] = chosen.get("pattern", "passthrough")

    else:
        out["method"] = "ast_failed"
        out["error"] = "zones chosen dict has no recognized structure"
    return out


# -------------------------
# CLI section (minimal)
# -------------------------

def _cli_section(instrument_path: Path, contracts_mod: Optional[Any]) -> Dict[str, Any]:
    help_text = None
    try:
        if contracts_mod is not None and hasattr(contracts_mod, "run_help"):
            help_text = contracts_mod.run_help(str(instrument_path))
        else:
            help_text = _run_help_fallback(str(instrument_path))
    except Exception:
        help_text = _run_help_fallback(str(instrument_path))

    help_text = help_text or ""
    flags = sorted(set(re.findall(r"(?<!\w)(--[0-9A-Za-z_\-τ]+)", help_text)))

    subcommands = [cmd for cmd in ["new-template", "score"] if cmd in help_text]
    tau_aliases = {
        "has_tau_ascii": "--agg_tau" in help_text,
        "has_tau_unicode": "--agg_τ" in help_text,
    }

    return {
        "help_valid": len(help_text.strip()) > 0,
        "help_len": len(help_text),
        "subcommands": subcommands,
        "flags": flags,
        "required_subcommands": ["new-template", "score"],
        "required_flags": ["--input", "--outdir"],
        "tau_aliases": tau_aliases,
    }


def _formula_section() -> Dict[str, Any]:
    # régime actuel chez toi: non vérifié
    return {"golden_attempted": False, "golden_pass": False}


def _compliance(cli: Dict[str, Any], zones: Dict[str, Any], formula: Dict[str, Any]) -> Dict[str, Any]:
    def assess(full: bool, partial: bool) -> str:
        if full:
            return "FULL"
        if partial:
            return "PARTIAL"
        return "MINIMAL"

    cli_full = bool(
        cli.get("help_valid")
        and len(cli.get("subcommands") or []) >= 2
        and all(f in (cli.get("flags") or []) for f in ["--input", "--outdir"])
    )
    cli_partial = bool(cli.get("help_valid"))
    cli_level = assess(cli_full, cli_partial)

    zones_full = bool((zones.get("zones") or {}))
    zones_partial = bool(zones.get("attempted"))
    zones_level = assess(zones_full, zones_partial)

    formula_full = bool(formula.get("golden_pass"))
    formula_partial = bool(formula.get("golden_attempted"))
    formula_level = assess(formula_full, formula_partial)

    order = {"FULL": 3, "PARTIAL": 2, "MINIMAL": 1}
    global_level = min([cli_level, zones_level, formula_level], key=lambda x: order[x])

    return {
        "axes": {"cli": cli_level, "zones": zones_level, "formula": formula_level},
        "global": global_level,
        "summary": f"CLI:{cli_level}/ZONES:{zones_level}/FORMULA:{formula_level}",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instrument", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parent
    probe_path = Path(__file__).resolve()
    probe_sha = _sha256_file(Path(__file__).resolve())

    instrument_path = Path(args.instrument).resolve()
    if not instrument_path.exists():
        raise SystemExit(f"Instrument not found: {instrument_path}")

    contracts_info = _load_repo_local_contracts(repo_root)
    contracts_mod = contracts_info.get("module")

    cli = _cli_section(instrument_path, contracts_mod)
    zones = _zones_section(instrument_path, contracts_mod)
    formula = _formula_section()
    compliance = _compliance(cli, zones, formula)

    zones_count = len(zones.get("zones") or {})

    report: Dict[str, Any] = {
        "contract_version": "1.5",
        "instrument_path": str(instrument_path),
        "instrument_hash": f"sha256:{_sha256_file(instrument_path)}",
        "validation_timestamp": datetime.now(timezone.utc).isoformat(),
        "compliance": compliance,
        "summary": {
            "cli_help_valid": bool(cli.get("help_valid")),
            "zones_attempted": True,
            "zones_count": zones_count,
            "formula_checked": False,
            "formula_pass": False,
        },
        "cli": cli,
        "zones": zones,
        "formula": formula,
        "_probe_forensics": {
            "probe_path": str(probe_path),
            "probe_sha256": f"sha256:{probe_sha}",
            "repo_root": str(repo_root),
            "contracts_py_path": contracts_info.get("path"),
            "contracts_py_sha256": (f"sha256:{contracts_info.get('sha256')}" if contracts_info.get("sha256") else None),
            "contracts_load_error": contracts_info.get("error"),
            "contracts_has_run_help": bool(contracts_mod is not None and hasattr(contracts_mod, "run_help")),
            "contracts_has_extract_zone_thresholds_ast": bool(contracts_mod is not None and hasattr(contracts_mod, "extract_zone_thresholds_ast")),
        },
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote contract report to: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
