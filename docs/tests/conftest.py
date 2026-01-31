import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

import pytest

from .config import INSTRUMENT_PATH


def _run(cmd, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=cwd)


@dataclass
class CLIResult:
    """Résultat CLI compatible avec deux patterns de tests.

    - Pattern A: r = run_cli(...); r.returncode / r.stdout / r.stderr
    - Pattern B: proc, outdir = run_cli(...)

    On proxy les attributs sur subprocess.CompletedProcess et on rend l'objet itérable.
    """
    proc: subprocess.CompletedProcess
    outdir: Path

    @property
    def returncode(self) -> int:
        return int(self.proc.returncode)

    @property
    def stdout(self) -> str:
        return self.proc.stdout or ""

    @property
    def stderr(self) -> str:
        return self.proc.stderr or ""

    def __iter__(self) -> Iterator:
        yield self.proc
        yield self.outdir


@pytest.fixture(scope="session")
def instrument_path():
    assert INSTRUMENT_PATH.exists(), f"Instrument introuvable: {INSTRUMENT_PATH}"
    return str(INSTRUMENT_PATH)


@pytest.fixture
def run_cli(tmp_path, instrument_path):
    """Exécute le CLI comme une boîte noire.

    - Si input_json est fourni, on injecte automatiquement --input <tmpfile>
      (ou on remplace l'argument existant de --input).
    - Pour la commande score, on force --outdir si absent.
    - Retour: CLIResult (proxy CompletedProcess + outdir, itérable).
    """

    def _runner(args, input_json=None, outdir=None) -> CLIResult:
        outdir_p = Path(outdir) if outdir else (tmp_path / "out")
        outdir_p.mkdir(parents=True, exist_ok=True)

        cmd = ["python3", instrument_path] + list(args)

        tmp_input: Optional[Path] = None
        if input_json is not None:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8"
            ) as f:
                json.dump(input_json, f, ensure_ascii=False, indent=2)
                tmp_input = Path(f.name)

            # Replace existing --input target if present; otherwise inject --input <file>
            if "--input" in cmd:
                i = cmd.index("--input")
                if i + 1 < len(cmd):
                    cmd[i + 1] = str(tmp_input)
                else:
                    cmd.append(str(tmp_input))
            else:
                # Also handle --input=<path>
                replaced = False
                for i, a in enumerate(cmd):
                    if isinstance(a, str) and a.startswith("--input="):
                        cmd[i] = f"--input={tmp_input}"
                        replaced = True
                        break
                if not replaced:
                    cmd += ["--input", str(tmp_input)]

        # ensure outdir for score
        if "score" in cmd and ("--outdir" not in cmd):
            cmd += ["--outdir", str(outdir_p)]

        proc = _run(cmd)

        if tmp_input and tmp_input.exists():
            tmp_input.unlink(missing_ok=True)

        return CLIResult(proc=proc, outdir=outdir_p)

    return _runner


@pytest.fixture
def template_json(run_cli, tmp_path):
    """Template généré via CLI: source de vérité pour le schéma + labels."""
    out = tmp_path / "pytest_template.json"
    res = run_cli(["new-template", "--name", "PyTestTemplate", "--out", str(out)])
    assert res.returncode == 0, res.stderr or res.stdout
    assert out.exists()
    return json.loads(out.read_text(encoding="utf-8"))


@pytest.fixture
def infer_dimensions(template_json):
    dims = []
    for it in template_json.get("items", []):
        d = it.get("dimension")
        if d and d not in dims:
            dims.append(d)
    return dims


@pytest.fixture
def load_results():
    def _load(outdir: Path):
        p = Path(outdir) / "results.json"
        assert p.exists(), f"results.json absent dans {outdir}"
        return json.loads(p.read_text(encoding="utf-8"))

    return _load
