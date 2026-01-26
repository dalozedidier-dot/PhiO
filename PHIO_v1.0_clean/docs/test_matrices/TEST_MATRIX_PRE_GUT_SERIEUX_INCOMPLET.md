TEST_MATRIX_PRE_GUT_SERIEUX_INCOMPLET.md
Version: v0.1
Title: Baseline Pre — GUT sérieux mais incomplet (archetype, stock)
Scope: Profil E/B (0–2) + log d’audit hypothétique (simulé pour 5 lignes typiques) pour comparatif Pre/Post

0) Statut des données
Source: Archetype générique basé sur GUT avancés (ex. MSSM SU(5) ou flipped SO(10) avec two-loop, mais sans fermeture totale de α(0)).
Note: Représente l'état de l'art où unification est précise, mais α reste input relatif.
Conséquence: Le scoring est illustratif ; pour un cas réel, adapter avec extraits originaux.

1) Échelle de scoring (0–2) — compatible E stricte
0 = absent OU violé (suppression / confusion / contradiction explicite avec le verrou).
1 = mentionné mais non instancié (vague, analogique, non relié au formalisme requis).
2 = instancié/opérationnalisé (borne, domaine, schéma, ordre, séparation input/output correctement posés).

2) A — Verrous E (0–2)
A1 / E1 — Échelle Q explicite
Score: 2
Justification:
Instancié: RG complet avec découplage, Λ_GUT précise.

A2 / E2 — Schéma explicite (renormalisation physique)
Score: 2
Justification:
Instancié: \overline{MS}/DR-bar avec matching détaillé.

A3 / E3 — Domaine explicite (IR atomique / EW / hadronique / UV)
Score: 2
Justification:
Instancié: séparation claire IR/EW/GUT/Planck.

A4 / E4 — Ordre explicite (LO/NLO, corrections, hiérarchie EFT)
Score: 1
Justification:
Mentionné: two-loop RG + one-loop thresholds, mais pas full NNLO pour spectre complet.

A5 / E5 — Séparation structure vs contingence (input empirique vs output)
Score: 1
Justification:
Mentionné: couplages unifiés comme structure, mais α(0) reste input (pas output absolu sans réduction inter-secteurs).

Vecteur Pre(A)
Pre(A) = [2, 2, 2, 1, 1]

3) B — Métrologie / hygiène de référence (0–2)
B1 — α(0) IR on-shell / Thomson
Score: 2
Justification:
Instancié: limite Thomson/on-shell utilisée comme référence IR.

B2 — “1/137” comme arrondi + valeur recommandée (CODATA/NIST)
Score: 2
Justification:
Instancié: CODATA/NIST cité avec précision.

B3 — Running illustré via α(MZ) ou α(Q) opérationnel
Score: 2
Justification:
Instancié: α(MZ) ≈ 1/128 illustré avec plots RG.

Vecteur Pre(B)
Pre(B) = [2, 2, 2]

4) Log d’audit (hypothétique, simulé sur 5 lignes typiques)
Référence: Lignes illustratives d'un GUT sérieux générique.
L1: "RG two-loop de α(Q) de MZ à Λ_GUT." → OK (E1/E2/E3) + pas de tags majeurs.
L2: "Matching thresholds aux masses SUSY." → OK (E3/E4 mentionnés).
L3: "Unification impose relations relatives des couplages." → OK provisoire (E5 à 1) + (NC) sur valeur absolue.
L4: "α(0) input empirique, mais contraint par GUT." → OK (E5 mentionné) + (H) minimale.
L5: "Pas de dérivation numérique pure de α(0)." → INCONCLUSIF + (NC).

5) Statistiques de tags (sur lignes simulées) — descriptif
H (hypothèses additionnelles): ~1/5
S (suppression de variable): ~0/5
NC (non-calculabilité / nécessite input): ~2/5
Lecture: profil "RG avancé → unification partielle" avec déficit mineur sur E4/E5.

6) Verdict E stricte (baseline Pre)
Verdict: INCONCLUSIF
Raison formelle:
E1–E3 à 2 ; E4/E5 à 1 (pas de verrou à 0, mais incomplet pour clôture explicative).

7) Préparation comparatif Pre/Post (0–2)
Pre(A) = [2,2,2,1,1]
Pre(B) = [2,2,2]
Notes:
Pour éviter ddr neutralisée, utiliser une échelle 0–2 sur Pre et Post.
Post attendu: document "α (≈1/137)" (verrouillage E complet), à encoder en 0–2 sur A1..A5 et B1..B3.

8) Points d’alerte
Archetype générique: dans cas réels avancés, si E4 monte à 2 (full NNLO), verdict pourrait être COMPATIBLE PARTIELLE.
Ambiguïté possible: E5 reste à 1 tant que α(0) n'est pas output pur (question ouverte).
NC lié à dépendance au spectre (masses libres).
