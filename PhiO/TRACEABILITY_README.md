# Traceability (PRE → POST)

Files:
- traceability_cases.json: list of cases (machine-checkable)
- templates_post/: fill POST templates, then copy A/B into traceability_cases.json
- scripts/validate_traceability.py: validator (no external deps)
- tests/test_traceability.sh: convenience wrapper

Validate:
```bash
bash tests/test_traceability.sh
```
