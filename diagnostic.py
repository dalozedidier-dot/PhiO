#!/usr/bin/env python3
"""Diagnostic Φ⊗O v0.1 (CLI + inspection légère).

Sorties:
- diagnostic_report.json (par défaut)
"""

import argparse, json, re, subprocess, tempfile, sys
from pathlib import Path

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

def read_source(path: Path):
    return path.read_text(encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instrument", default="phi_otimes_o_instrument_v0_1.py")
    ap.add_argument("--out", default="diagnostic_report.json")
    args = ap.parse_args()

    inst = Path(args.instrument).resolve()
    if not inst.exists():
        print(f"Instrument introuvable: {inst}", file=sys.stderr)
        return 1

    report = {"instrument": str(inst), "conventions": {}, "cli": {}}

    # static hints
    code = read_source(inst)
    report["conventions"]["bottleneck_mentioned"] = "bottleneck" in code.lower()

    # help
    h = run(["python3", str(inst), "--help"])
    report["cli"]["help"] = {"returncode": h.returncode, "stdout": h.stdout, "stderr": h.stderr}

    # new-template
    tpl_path = Path("template_diagnostic.json").resolve()
    nt = run(["python3", str(inst), "new-template", "--name", "Diagnostic", "--out", str(tpl_path)])
    report["cli"]["new_template"] = {"returncode": nt.returncode, "stdout": nt.stdout, "stderr": nt.stderr, "path": str(tpl_path)}
    template = None
    if nt.returncode == 0 and tpl_path.exists():
        template = json.loads(tpl_path.read_text(encoding="utf-8"))
        report["conventions"]["template_keys"] = list(template.keys())
        report["conventions"]["item_keys"] = list(template.get("items", [{}])[0].keys()) if template.get("items") else []
        report["conventions"]["dimensions"] = sorted({it.get("dimension") for it in template.get("items", []) if it.get("dimension")})

    # score baseline
    if template is not None:
        outdir = Path("output_diagnostic").resolve()
        sc = run(["python3", str(inst), "score", "--input", str(tpl_path), "--outdir", str(outdir)])
        report["cli"]["score_valid"] = {"returncode": sc.returncode, "stdout": sc.stdout, "stderr": sc.stderr}
        res_path = outdir / "results.json"
        if sc.returncode == 0 and res_path.exists():
            results = json.loads(res_path.read_text(encoding="utf-8"))
            report["conventions"]["result_keys"] = list(results.keys())
            report["conventions"]["sample_T"] = results.get("T")
            report["conventions"]["sample_K_eff"] = results.get("K_eff")

    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.out)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
