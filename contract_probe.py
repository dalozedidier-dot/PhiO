"""
contract_probe.py

Génère un rapport contractuel (CLI + zones + formule) pour l'instrument Phi⊗O.

Objectif: un contrat *honnête* et CI-friendly.
- Pas d'exécution "sandbox" implicite: zones par AST uniquement (via tests/contracts.py).
- Vérifications CLI: présence de sous-commandes/flags attendus.
- Vérification formule: optionnelle, via un run "score" contrôlé (pas de pytest requis).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Réutilise la logique contractuelle déjà versionnée dans la suite
from tests.contracts import run_help, extract_zone_thresholds_ast


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_cli_contract(instrument_path: Path) -> Dict[str, Any]:
    """Extrait un contrat CLI minimal à partir de --help."""
    cli: Dict[str, Any] = {
        "help_valid": False,
        "help_len": 0,
        "subcommands": [],
        "flags": [],
        "required_subcommands": ["new-template", "score"],
        "required_flags": ["--input", "--outdir"],
    }

    try:
        help_text = run_help(str(instrument_path))
        cli["help_valid"] = True
        cli["help_len"] = len(help_text or "")
    except Exception as e:
        cli["error"] = str(e)
        return cli

    help_text = help_text or ""

    # Sous-commandes (présence textuelle, volontairement simple)
    cli["subcommands"] = [s for s in cli["required_subcommands"] if s in help_text]

    # Flags (présence textuelle)
    flags = []
    for f in ["--input", "--outdir", "--help", "--agg_tau", "--agg_τ"]:
        if f in help_text:
            flags.append(f)
    cli["flags"] = sorted(set(flags))

    # Compléments informatifs: alias tau documentés ?
    cli["tau_aliases"] = {
        "has_tau_ascii": "--agg_tau" in help_text,
        "has_tau_unicode": "--agg_τ" in help_text,
    }
    return cli


def extract_zones_ast_only(instrument_path: Path) -> Dict[str, Any]:
    """
    Extraction *honnête* des zones (AST uniquement).

    Correction principale:
    - extract_zone_thresholds_ast(...) peut renvoyer None ou un type non-dict.
    - On normalise toujours la structure renvoyée pour éviter tout crash et
      rendre les sorties contractuelles stables.
    """
    # Structure normalisée de sortie (toujours conforme à ce shape)
    normalized: Dict[str, Any] = {
        "zones": {},
        "constants": {},
        "if_chain": [],
        "attempted": True,
        "method": "ast",
    }

    try:
        raw = extract_zone_thresholds_ast(str(instrument_path))

        # Guard 1: None
        if raw is None:
            normalized["method"] = "ast_failed"
            normalized["error"] = "extract_zone_thresholds_ast returned None"
            return normalized

        # Guard 2: type inattendu
        if not isinstance(raw, dict):
            normalized["method"] = "ast_failed"
            normalized["error"] = f"extract_zone_thresholds_ast returned non-dict: {type(raw).__name__}"
            return normalized

        # On fusionne prudemment ce que raw apporte
        # (en gardant les clés attendues)
        constants = raw.get("constants") if isinstance(raw.get("constants"), dict) else {}
        if_chain = raw.get("if_chain") if isinstance(raw.get("if_chain"), list) else []

        normalized["constants"] = constants
        normalized["if_chain"] = if_chain

        # Flat map "zones": uniquement constants (littéraux) pour conformité v1.5
        flat: Dict[str, Any] = {}
        for k, v in constants.items():
            flat[k] = v
        normalized["zones"] = flat

        # Si raw avait des champs additionnels utiles, on les conserve sans casser le shape
        # (mais on évite d'écraser nos clés normalisées)
        for k, v in raw.items():
            if k in ("zones", "constants", "if_chain", "attempted", "method", "error"):
                continue
            normalized[k] = v

        return normalized

    except Exception as e:
        normalized["method"] = "ast_failed"
        normalized["error"] = str(e)
        return normalized


def _run_score_once(
    instrument_path: Path, input_json: Dict[str, Any]
) -> Tuple[int, str, str, Optional[Dict[str, Any]]]:
    """Exécute `score` et renvoie (rc, stdout, stderr, results_json)."""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        in_path = td_path / "input.json"
        out_dir = td_path / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        in_path.write_text(json.dumps(input_json, ensure_ascii=False, indent=2), encoding="utf-8")

        cmd = ["python3", str(instrument_path), "score", "--input", str(in_path), "--outdir", str(out_dir)]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

        results_path = out_dir / "results.json"
        results = None
        if results_path.exists():
            try:
                results = json.loads(results_path.read_text(encoding="utf-8"))
            except Exception:
                results = None

        return proc.returncode, proc.stdout or "", proc.stderr or "", results


def check_formula_contract(instrument_path: Path) -> Dict[str, Any]:
    """Vérifie la formule si possible, sans dépendre de la suite pytest."""
    info: Dict[str, Any] = {"golden_attempted": True, "golden_pass": False}

    # Construire un template de base via new-template si possible
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        tpath = td_path / "template.json"
        proc = subprocess.run(
            ["python3", str(instrument_path), "new-template", "--name", "ContractProbe", "--out", str(tpath)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if proc.returncode != 0 or not tpath.exists():
            info["error"] = f"new-template failed: {proc.stderr or proc.stdout}"
            return info

        template = json.loads(tpath.read_text(encoding="utf-8"))

        # Forcer des scores connus (2) si possible
        for it in template.get("items", []):
            if "score" in it:
                it["score"] = 2

        rc, _out, err, results = _run_score_once(instrument_path, template)
        if rc != 0 or not results:
            info["error"] = f"score failed: {err}"
            return info

        # On exige T et K_eff
        if "T" not in results or "K_eff" not in results:
            info["error"] = "results.json missing T and/or K_eff"
            return info

        # Déduire les scores agrégés par dimension (si présents)
        dim_scores = results.get("dimension_scores") or {}
        # Fallback: lire depuis template si dimension_scores absent
        if not dim_scores:
            for it in template.get("items", []):
                dim = it.get("dimension")
                if dim is not None:
                    dim_scores[dim] = it.get("score", 0)

        # Normaliser l'accès à tau
        tau_key = "τ" if "τ" in dim_scores else ("tau" if "tau" in dim_scores else None)
        if tau_key is None:
            info["error"] = "cannot identify tau dimension key (τ or tau)"
            return info

        try:
            Cx = float(dim_scores.get("Cx", 0))
            K = float(dim_scores.get("K", 0))
            tau = float(dim_scores.get(tau_key, 0))
            G = float(dim_scores.get("G", 0))
            D = float(dim_scores.get("D", 0))

            k_eff_expected = K / (1.0 + tau + G + D + Cx)
            t_expected = Cx + tau + G + D - k_eff_expected

            # Tolérance honnête
            import math

            k_ok = math.isclose(float(results["K_eff"]), k_eff_expected, rel_tol=1e-5, abs_tol=1e-8)
            t_ok = math.isclose(float(results["T"]), t_expected, rel_tol=1e-5, abs_tol=1e-8)

            info["k_eff_expected"] = k_eff_expected
            info["t_expected"] = t_expected
            info["k_eff_observed"] = results["K_eff"]
            info["t_observed"] = results["T"]
            info["golden_pass"] = bool(k_ok and t_ok)
        except Exception as e:
            info["error"] = str(e)

    return info


def calculate_compliance_levels(
    cli_info: Dict[str, Any], zones_info: Dict[str, Any], formula_info: Dict[str, Any]
) -> Dict[str, Any]:
    """Niveaux de conformité multi-axes (CLI / zones / formule)."""

    def assess_level(full: bool, partial: bool) -> str:
        if full:
            return "FULL"
        if partial:
            return "PARTIAL"
        return "MINIMAL"

    # CLI
    cli_full = bool(
        cli_info.get("help_valid", False)
        and len(cli_info.get("subcommands", [])) >= 2
        and all(f in (cli_info.get("flags") or []) for f in ["--input", "--outdir"])
    )
    cli_partial = bool(cli_info.get("help_valid", False))
    cli_level = assess_level(cli_full, cli_partial)

    # Zones: filtre strict des non-littéraux
    zones = zones_info.get("zones") or {}
    literal_zones = {k: v for k, v in zones.items() if isinstance(v, (int, float, str))}
    zones_full = len(literal_zones) > 0
    # v1.5: PARTIAL si attempted=True, même si extraction vide
    zones_partial = bool(zones_info.get("attempted", False))
    zones_level = assess_level(zones_full, zones_partial)

    # Formule
    formula_full = bool(formula_info.get("golden_pass", False))
    formula_partial = bool(formula_info.get("golden_attempted", False))
    formula_level = assess_level(formula_full, formula_partial)

    order = {"FULL": 3, "PARTIAL": 2, "MINIMAL": 1}
    global_level = min([cli_level, zones_level, formula_level], key=lambda x: order[x])

    return {
        "axes": {"cli": cli_level, "zones": zones_level, "formula": formula_level},
        "global": global_level,
        "summary": f"CLI:{cli_level}/ZONES:{zones_level}/FORMULA:{formula_level}",
    }


def generate_contract_report(instrument_path: Path, check_formula: bool) -> Dict[str, Any]:
    cli = extract_cli_contract(instrument_path)
    zones = extract_zones_ast_only(instrument_path)
    formula = check_formula_contract(instrument_path) if check_formula else {"golden_attempted": False, "golden_pass": False}
    compliance = calculate_compliance_levels(cli, zones, formula)

    return {
        "contract_version": "1.5",
        "instrument_path": str(instrument_path),
        "instrument_hash": f"sha256:{_sha256_file(instrument_path)}",
        "validation_timestamp": datetime.now(timezone.utc).isoformat(),
        "compliance": compliance,
        "summary": {
            "cli_help_valid": cli.get("help_valid", False),
            "zones_attempted": zones.get("attempted", False),
            "zones_count": len([k for k, v in (zones.get("zones") or {}).items() if isinstance(v, (int, float, str))]),
            "formula_checked": bool(check_formula),
            "formula_pass": bool(formula.get("golden_pass", False)) if check_formula else False,
        },
        "cli": cli,
        "zones": zones,
        "formula": formula,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate a contractual validation report for Phi⊗O.")
    ap.add_argument("--instrument", required=True, help="Path to the instrument python file.")
    ap.add_argument("--out", required=True, help="Output JSON report path.")
    ap.add_argument("--check-formula", action="store_true", help="Also run a deterministic score to verify formula.")
    args = ap.parse_args()

    inst = Path(args.instrument).resolve()
    if not inst.exists():
        raise SystemExit(f"Instrument not found: {inst}")

    report = generate_contract_report(inst, check_formula=bool(args.check_formula))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote contract report to: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
