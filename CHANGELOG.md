# Historique des versions

## v0.6.1 — 2026-11-12
- Commandes mal orthographiées : plusieurs fautes dans le même texte (`\fracc{1}{2} \lamda + 1
  \langel x \rangle`) sont corrigées ensemble ; avant, aucune correction isolée ne compilait
  et rien n'était proposé (cas signalé par l'utilisateur).
- Les commandes inconnues sont aussi cherchées dans le texte, pas seulement dans le journal
  de TeX. Ordre des essais : commande citée par TeX seule, puis toutes ensemble, puis les autres.

## v0.6.0 — 2026-11-12
Spécifié par exemples avec l'utilisateur avant le développement.
- **Corrections proposées** quand le texte ne compile pas (accolades, \left/\right, commande
  mal orthographiée, double exposant, Unicode, $ en trop) : seulement si la correction
  compile ; aperçu à liseré orange, bouton Appliquer (⌘Z).
- **Conseils** non bloquants : « \ » manquant (alpha, theta_A, partial, sum…), parenthèses
  déséquilibrées, caractères Unicode.
- Traduction : noms automatiques sans tiret bas pour les symboles hors modèle (N_{1} → N1),
  affichés discrètement ; \approx et \simeq lus comme « = ».
- Retiré : Python → LaTeX (le cœur SymPy reste pour le futur outil de calcul des moments).

## v0.5.1 — 2026-11-12
- Traduction : les appels de fonction (`R1(z_star1)`) sont acceptés dans les deux sens
  (erreur « 'Symbol' object is not callable » corrigée) ; section [fonctions] du modèle.
- `\frac{d}{dt} N_{11}` et `\frac{d}{dt} \mathrm{N11}` correctement lus ; sécurité : une
  équation lue seulement en partie par SymPy est signalée au lieu d'être tronquée en silence.
- Avertissements sans doublons.

## v0.5.0 — 2026-11-12
- Le panneau SymPy est remplacé par un panneau **Traduction LaTeX ⇄ Python** (⌘K), fondé sur
  un **modèle** de correspondances (fichier .ini partageable) : n_A1, M_A1_A2, T_…, Q_…,
  paramètres rmaxA, thA, KA, r_A1… comme dans moment_closure.py. Aucun symbole deviné :
  ce qui n'est pas dans le modèle est signalé.
- LaTeX → Python en direct (systèmes align compris), options Développer et Définitions.
- Python → LaTeX vers l'éditeur, option Regrouper par moment ; aller-retour exact.
- Le cœur SymPy (core/sympy_ops.py) est conservé : il sert à la lecture du LaTeX et
  servira au futur outil de calcul des moments.

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
