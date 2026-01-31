PhiO CI / Contrat / Zones — backup v0.3.1

Contenu :
- contract_probe.py (à placer à la racine du repo)
- .github/workflows/generate_baseline.yml (workflow GitHub Actions)

Installation :
1) Copier contract_probe.py à la racine (remplacement complet).
2) Copier .github/workflows/generate_baseline.yml (remplacement complet).
3) Lancer Actions -> "Generate contract baseline".
4) Lire .contract/contract_baseline.json :
   - summary.zones_count
   - zones.method
   - zones._forensics.internal.instrument_has_ZONE_THRESHOLDS
   - zones._forensics.internal.instrument_zone_line
   - _probe_forensics.contracts.contracts_load_error
