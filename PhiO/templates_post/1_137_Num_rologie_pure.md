# α (≈1/137) — Numérologie pure (POST)

## Machine-checkable block (do not edit keys)
```json
{
  "case_id": "0001",
  "pre_source": "TEST_MATRIX_PRE_NUMEROLOGIE_PURE.md",
  "post": {
    "A": [0, 0, 0, 0, 0],
    "B": [0, 0, 0]
  }
}
```

## Scoring (0–2)

### A — Verrous E (A1..A5)
- A1 / E1 — Échelle Q explicite: score __ /2 — justification:
- A2 / E2 — Schéma explicite: score __ /2 — justification:
- A3 / E3 — Domaine explicite: score __ /2 — justification:
- A4 / E4 — Ordre explicite: score __ /2 — justification:
- A5 / E5 — Séparation structure vs contingence: score __ /2 — justification:

### B — Métrologie (B1..B3)
- B1 — α(0) IR on-shell / Thomson: score __ /2 — justification:
- B2 — “1/137” comme arrondi + valeur recommandée: score __ /2 — justification:
- B3 — Running illustré via α(MZ) ou α(Q): score __ /2 — justification:

## Audit log (5 lignes)
- L1: … tags: [H/S/NC]
- L2: … tags: [H/S/NC]
- L3: … tags: [H/S/NC]
- L4: … tags: [H/S/NC]
- L5: … tags: [H/S/NC]

## Verdict rule (deterministic)
- min(post.A) == 0 → INCOMPATIBLE
- min(post.A) == 1 → INCONCLUSIF
- all(post.A) == 2 and min(post.B) < 2 → COMPATIBLE_PARTIELLE
- all(post.A) == 2 and min(post.B) >= 2 → COMPATIBLE
