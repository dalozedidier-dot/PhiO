# PhiO – Contrat de validation v1.5 (HONEST)

Ce dépôt contient la **suite de tests contractuels PhiO** (patch contract v1.5).
Le but est de figer un **contrat minimal** autour de l'instrument (fichier Python pointé par `PHIO_INSTRUMENT`)
et de bloquer les dérives via baseline + CI.

## Usage rapide (local)

```bash
# Depuis la racine du dépôt
./scripts/dev-setup.sh

export PHIO_INSTRUMENT="../phi_otimes_o_instrument_v0_1.py"
export PHIO_CONTRACT_POLICY=HONEST
export PHIO_TAU_POLICY=AT_LEAST_ONE
export PHIO_ALLOW_EXEC_EXTRACTION=false

./final_validation.sh
```

Résultat attendu (mode HONEST) :
- ✅ 2 tests PASS (CLI)
- ⚠️ 1 test XFAIL (zones) **assumé**
- ✅ régression baseline PASS

## Baseline (règle de stabilité)

- Fichier : `.contract/contract_baseline.json`
- Toute modification de baseline = **breaking change intentionnel**.
- Mise à jour autorisée uniquement via :
```bash
export PHIO_UPDATE_BASELINE=true
python -m pytest tests/test_99_contract_regression.py -v --tb=short
```

Un hook `pre-commit` versionné dans `.githooks/` bloque toute modification de baseline si
`PHIO_UPDATE_BASELINE` n'est pas à `true`.

## Zones : XFAIL assumé (HONEST)

Le test `tests/test_08_zone_thresholds.py` est XFAIL lorsque l'instrument ne fournit pas de constantes `ZONE_*`
littérales extractibles. C'est une limite déclarée du contrat HONEST (pas de faux positifs).

## CI/CD (règles)

- ❌ `PHIO_UPDATE_BASELINE=true` interdit en CI
- ✅ baseline exigée dans le dépôt
- ✅ exécution de `./final_validation.sh` + `pytest tests/`

Voir `.github/workflows/phi_ci.yml`.
