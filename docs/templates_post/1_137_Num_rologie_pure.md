# α (≈1/137) — Numérologie pure — POST Template (à remplir)

## Machine-checkable (ne pas modifier la structure)
```json
{
  "case_id": "0001",
  "pre_source": "TEST_MATRIX_PRE_NUMEROLOGIE_PURE.md",
  "post": {
    "A": [0,0,0,0,0],
    "B": [0,0,0]
  }
}
```

## Règle de verdict E (déterministe)
- Si min(post.A) == 0 → verdict_E = "INCOMPATIBLE"
- Sinon si min(post.A) == 1 → verdict_E = "INCONCLUSIF"
- Sinon (post.A tous à 2) :
  - Si min(post.B) < 2 → verdict_E = "COMPATIBLE_PARTIELLE"
  - Sinon → verdict_E = "COMPATIBLE"

## Champs à remplir (descriptif uniquement)
- A1..A5: score 0–2 + justification (1–3 lignes chacune)
- B1..B3: score 0–2 + justification (1–3 lignes chacune)
- Log d’audit: 5 lignes typiques (tags H/S/NC si utilisés)
