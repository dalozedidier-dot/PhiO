# Bundle CI (web-only)

## Objectif
- Unifier les workflows dans `.github/workflows/`
- Produire des rapports (JUnit + HTML) et des artifacts
- Gérer la baseline contractuelle sans environnement local

## Fichiers inclus
- `.github/workflows/main.yml` : lint + tests + rapports + artifact
- `.github/workflows/phi_ci.yml` : contrat + tests + rapports + artifact (baseline requise)
- `.github/workflows/generate_baseline.yml` : génération baseline (workflow manuel)
- `.contract/contract_baseline.json` : placeholder (à remplacer via "Generate contract baseline")

## Procédure (GitHub UI)
1. Copie ces fichiers dans ton repo (en respectant l'arborescence).
2. Supprime tout dossier `github/workflows/` (sans point) et tout doublon.
3. Va dans Actions → "Generate contract baseline" → Run workflow.
4. Une fois le commit baseline poussé, le workflow `PhiO Contract CI` peut passer.

## Notes
- Si ta branche principale n'est pas `main`, remplace les branches dans `on:`.
