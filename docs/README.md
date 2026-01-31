# PHIO Contract Framework — v1.0.0 (clean)

Ce dépôt contient un **framework contractuel + test-suite** pour stabiliser des invariants (baseline, conventions, diagnostics)
et un **collecteur de contexte LLM** (bundle reproductible) utilisable en local ou en CI.

## Contenu

- `run_all_tests.sh` : suite principale (contrat + tests).
- `final_validation.sh` : validation rapide.
- `.contract/contract_baseline.json` : baseline contractuelle (source de vérité).
- `scripts/phio_llm_collect.sh` : collecteur (bundle + manifest + all_text.txt optionnel).
- `run_collector_tests.sh` + `tests/test_llm_collector_*.sh` : **batterie de tests extrêmes** du collecteur.
- `.github/workflows/` : CI (contrat + tests collecteur).

## Lancer en local

```bash
# setup (hooks, permissions)
./scripts/dev-setup.sh

# validation rapide
./final_validation.sh

# suite complète
./run_all_tests.sh
```

## Collecter un bundle LLM (debug)

```bash
# bundle standard
QUIET=1 ./scripts/phio_llm_collect.sh . _llm_bundle

# mode strict (échoue si baseline/golden absente ou si tests/ absent)
STRICT=1 QUIET=1 ./scripts/phio_llm_collect.sh . _llm_bundle_strict
```

## Lancer les tests “max” du collecteur

```bash
chmod +x run_collector_tests.sh tests/test_llm_collector_*.sh tests/test_cross_validation.sh
./run_collector_tests.sh
```

## Documentation

- `docs/Regles_epistemologiques.md`
- `docs/Glossaire.md`
- `docs/Frameworks_DD_DDR_E.md`
- `docs/test_matrices/` (PRE archetypes)

