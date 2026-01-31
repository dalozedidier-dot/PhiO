# RUNBOOK — PHIO v1.0

## Routine locale (3 commandes)

```bash
./scripts/dev-setup.sh
./final_validation.sh
./run_all_tests.sh
```

Critère de succès :
- `final_validation.sh` sort sans erreur.
- `run_all_tests.sh` sort sans erreur.
- `.contract/contract_baseline.json` existe (baseline présente).

## Debug en cas d’échec CI / tests

1) Générer un bundle de contexte :

```bash
QUIET=1 INCLUDE_TEST_OUTPUTS=1 ./scripts/phio_llm_collect.sh . _debug_bundle
```

2) Ouvrir `_debug_bundle/missing_report.md` :
- `CRITICAL: no baseline/golden detected` → baseline absente / non copiée.
- `tests package marker: MISSING` → `tests/__init__.py` absent (selon votre politique, warning ou erreur).

3) Joindre `_debug_bundle/phio_llm_bundle.tar.gz` à l’issue.

## Mode STRICT

```bash
STRICT=1 QUIET=1 ./scripts/phio_llm_collect.sh . _strict_bundle
```

Comportement attendu :
- baseline/golden absente → exit 1
- `tests/` absent → exit 1

## Tests extrêmes du collecteur

```bash
./run_collector_tests.sh
```

Si un test échoue :
- relancer le test concerné avec `QUIET=0`
- vérifier `tree.txt`, `meta.txt`, `manifest.json` et l’extraction de `phio_llm_bundle.tar.gz`
