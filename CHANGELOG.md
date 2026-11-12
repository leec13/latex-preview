# Historique des versions

## v0.4.0 — 2026-11-11
- SymPy : substitutions **simultanées** (tableau de remplacements ; X↔Y donne YX),
  propagées à l'intérieur des moments ⟨…⟩ et des dérivées d⟨…⟩/dt. Bouton « Ajouter l'inverse ».
- Moments écrits sous forme canonique : ⟨N_A^2 N_A^1⟩ et ⟨N_A^1 N_A^2⟩ sont le même symbole.
- Correction : sélectionner du texte dans l'éditeur ne change plus la portée sans le dire
  (choix explicite « tout le texte / la sélection ») ; une somme insérée dans une sélection
  est mise entre parenthèses (a·x avec x → z+1 donnait « a z + 1 »).
- Interprétation mise à jour plus vite (300 ms, lectures périmées abandonnées, résultat
  affiché aussitôt après une opération).

## v0.3.1 — 2026-11-11
- SymPy : moments `\langle … \rangle` lus comme des variables ; indices composés
  (`r_{\max,A}`) ; dérivée en forme opérateur `\frac{d}{dt} X` conservée.
- Nouvelle case « Exposant après un indice = indice » (cochée) : `r_{A}^{1}` n'est plus
  lu comme une puissance (l'exposant disparaissait sans avertissement).
- `\frac{d}{dt} N(t)` : N reste une fonction.

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
