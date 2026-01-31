TEST_MATRIX_PRE_GUT_NAIF.md
Version: v0.1
Title: Baseline Pre — GUT naïf (archetype, stock)
Scope: Profil E/B (0–2) + log d’audit hypothétique (simulé pour 5 lignes typiques) pour comparatif Pre/Post

0) Statut des données
Source: Archetype générique basé sur des GUT naïfs (ex. SU(5) basique sans SUSY, calculs one-loop approximatifs des années 70–90).
Note: Représente des tentatives d'unification forcée où α est "dérivé" par ajustement, sans verrouillage complet.
Conséquence: Le scoring est illustratif ; pour un cas réel, adapter avec extraits originaux.

1) Échelle de scoring (0–2) — compatible E stricte
0 = absent OU violé (suppression / confusion / contradiction explicite avec le verrou).
1 = mentionné mais non instancié (vague, analogique, non relié au formalisme requis).
2 = instancié/opérationnalisé (borne, domaine, schéma, ordre, séparation input/output correctement posés).

2) A — Verrous E (0–2)
A1 / E1 — Échelle Q explicite
Score: 2
Justification:
Instancié: unification à Λ_GUT ~ 10^{15} GeV, running RG de base mentionné.

A2 / E2 — Schéma explicite (renormalisation physique)
Score: 2
Justification:
Instancié: schéma MS-bar ou on-shell basique pour les couplages.

A3 / E3 — Domaine explicite (IR atomique / EW / hadronique / UV)
Score: 1
Justification:
Mentionné: UV/GUT vs IR, mais confusion sur matching précis (seuils ignorés).

A4 / E4 — Ordre explicite (LO/NLO, corrections, hiérarchie EFT)
Score: 1
Justification:
Mentionné: tree-level ou one-loop, mais pas de hiérarchie complète (thresholds omis).

A5 / E5 — Séparation structure vs contingence (input empirique vs output)
Score: 0
Justification:
Violation: α(0) traité comme output de l'unification, mais en réalité ajusté via inputs (pas de fermeture absolue).

Vecteur Pre(A)
Pre(A) = [2, 2, 1, 1, 0]

3) B — Métrologie / hygiène de référence (0–2)
B1 — α(0) IR on-shell / Thomson
Score: 1
Justification:
Mentionné: limite IR vague, mais pas verrouillée comme Thomson/on-shell.

B2 — “1/137” comme arrondi + valeur recommandée (CODATA/NIST)
Score: 1
Justification:
Mentionné: 1/137 approximatif, mais pas CODATA précis.

B3 — Running illustré via α(MZ) ou α(Q) opérationnel
Score: 1
Justification:
Mentionné: running basique, mais pas illustré avec α(MZ) concret.

Vecteur Pre(B)
Pre(B) = [1, 1, 1]

4) Log d’audit (hypothétique, simulé sur 5 lignes typiques)
Référence: Lignes illustratives d'un GUT naïf générique.
L1: "Les couplages unifient à Λ_GUT = 10^{16} GeV." → OK provisoire (E1/E2) + tags (H) : postulat unification.
L2: "Running one-loop: α^{-1}(Λ_GUT) = (α_s + α_w + α_em)/3." → OK (E1/E2/E4 mentionnés) + (S) sur domaines.
L3: "Donc α(0) ≈ 1/137 par inversion." → KO (E5 violé) + (NC) : ajustement post-hoc.
L4: "Ignorer thresholds pour simplicité." → KO (E3/E4 à 1) + (S).
L5: "Mystère résolu par GUT." → KO (E5=0) + (H).

5) Statistiques de tags (sur lignes simulées) — descriptif
H (hypothèses additionnelles): ~3/5
S (suppression de variable): ~2/5
NC (non-calculabilité / nécessite input): ~2/5
Lecture: profil "unification → valeur unique" avec déficit sur E3/E4/E5.

6) Verdict E stricte (baseline Pre)
Verdict: INCOMPATIBLE
Raison formelle:
E5=0 (un seul verrou manquant suffit ; ici E3/E4 à 1 aussi).

7) Préparation comparatif Pre/Post (0–2)
Pre(A) = [2,2,1,1,0]
Pre(B) = [1,1,1]
Notes:
Pour éviter ddr neutralisée, utiliser une échelle 0–2 sur Pre et Post.
Post attendu: document "α (≈1/137)" (verrouillage E complet), à encoder en 0–2 sur A1..A5 et B1..B3.

8) Points d’alerte
Archetype générique: dans cas réels, si ajustements empiriques explicites, E5 reste à 0.
Ambiguïté possible: si "naïf" inclut plus de détails, scores E3/E4/E5 pourraient monter à 2.
NC souvent lié à fitting des couplages initiaux.
