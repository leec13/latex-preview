# Historique des versions

## v0.3.0 — 2026-11-11
- Panneau SymPy (⌘K) : interprétation de l'expression, Simplifier, Développer, Factoriser,
  Réduire, Évaluer, Éléments simples, Regrouper, Dériver, Intégrer, Résoudre, Substituer.
  Agit sur la sélection ou tout le texte, ⌘Z pour annuler, calcul interruptible.
- Lecture du LaTeX corrigée pour les cas usuels : produits vs fonctions, e^x, dérivées en
  fraction et symboles décorés conservés à l'identique, N^*, notation de SymPy.
- Nouvelle dépendance : antlr4-python3-runtime 4.11 (`conda env update -f environment.yml --prune`).

## v0.2.0 — 2026-11-11
- Nouvelle option « Couper les lignes longues » : les équations trop longues sont coupées
  à la largeur de la fenêtre (package breqn), suites alignées sous « = ». La mise en page
  suit le redimensionnement et le zoom ; repli automatique sur une ligne si breqn échoue.
- Fermer la fenêtre pendant une compilation ne provoque plus d'erreur.

## v0.1.0 — 2026-11-11
Première version : aperçu LaTeX compilé avec TeX Live et recadré, zoom, erreurs en français,
export PDF/PNG, copie d'image, préambule personnalisable.
