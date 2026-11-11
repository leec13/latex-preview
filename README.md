# LaTeX Preview

Petit outil pour **coller du LaTeX « brut » et voir immédiatement son rendu**, puis le copier ou l'exporter en PDF/PNG.
La compilation passe par votre TeX Live : le rendu est identique à celui d'Overleaf.

## Installation (macOS, une seule fois)

Prérequis : conda (Miniforge, Miniconda ou Anaconda) et TeX Live / MacTeX.

```bash
cd latex-preview
conda env create -f environment.yml
conda activate latex-preview
pip install -e .
```

## Lancement

```bash
conda activate latex-preview
latex-preview          # ou : python -m latex_preview
```

Pour le lancer en une commande, ajoutez à `~/.zshrc` :

```bash
alias ltx='conda run --no-capture-output -n latex-preview latex-preview &'
```

## Ce que l'on peut coller

| Vous collez… | L'outil… |
|---|---|
| une expression nue (`sympy.latex(expr)`) | l'enveloppe dans `equation*` |
| une expression avec `&` ou `\\` | utilise `align*` ou `gather*` |
| `$…$`, `$$…$$`, `\[…\]`, `\(…\)` | retire les délimiteurs |
| `\begin{align}…`, `equation`, `gather`… | compile tel quel (numéros compris) |
| du texte avec des formules | compile tel quel |
| un document complet (`\documentclass`) | compile tel quel |
| un bloc Markdown ```` ```latex ```` copié depuis un chat | retire les clôtures |

## Fonctions

- **Couper les lignes longues** (coché par défaut) : une équation trop longue est coupée pour tenir dans la largeur de l'aperçu. Les lignes suivantes sont alignées sous le signe « = », et une expression sans « = » est coupée aussi. La coupure se refait quand on redimensionne la fenêtre ou qu'on zoome : on choisit la taille avec le zoom, et l'équation s'adapte à la fenêtre. Les équations déjà structurées à la main (`&`, `\\`) ne sont pas touchées. Cette fonction utilise le package `breqn`, inclus dans TeX Live et MacTeX. Si `breqn` échoue sur une expression, elle est affichée sur une ligne. Limite : une fraction dont le numérateur est à lui seul plus large que la fenêtre ne peut pas être coupée.
- Aperçu automatique pendant la frappe. Il se décoche via **Auto** ; dans ce cas, **⌘↵** recompile.
- Fenêtre et séparateur redimensionnables. Pour mettre l'aperçu sous l'éditeur : *Affichage → Aperçu sous l'éditeur*.
- Zoom : **⌘ + molette**, pincement au trackpad, **⌘+ / ⌘−**, **Ajuster** (⌘9), taille réelle (⌘0).
- Erreurs expliquées en français et ligne fautive surlignée. L'aperçu précédent reste affiché en grisé, et un clic sur « Ligne n » place le curseur sur cette ligne.
- **⇧⌘V** : remplace tout le texte par le contenu du presse-papiers.
- **⇧⌘C** : copie le rendu en image, à coller dans Keynote, PowerPoint, Mail…
- **⌘E** : export en PDF vectoriel recadré, à inclure avec `\includegraphics`.
- **⇧⌘E** : export en PNG (300 dpi, fond transparent par défaut).
- *Préambule et options* (⌘,) : packages et macros personnelles, taille de police, largeur du texte, résolution PNG.
- Moteurs disponibles : pdflatex (par défaut, le plus rapide), lualatex, xelatex.
- Le texte, le zoom, la taille de la fenêtre et les options sont conservés d'une session à l'autre.

## Panneau SymPy (⌘K)

Le panneau à droite modifie le LaTeX avec SymPy. Il **agit sur la sélection** s'il y en a une, sinon sur tout le texte. Le résultat remplace le texte d'origine, et **⌘Z** revient en arrière.

- **SymPy a compris :** affiche comment SymPy lit l'expression, en notation Python (`*` pour un produit, `**` pour une puissance). Vérifiez cette ligne avant d'appliquer une opération.
- **Opérations :** Simplifier, Développer, Factoriser, Réduire (même dénominateur), Évaluer (calcule les ∑, ∫ et d/dx écrits). Les opérations suivantes demandent une **variable** : Éléments simples, Regrouper, Dériver, Intégrer, Résoudre. Sur une équation, l'opération s'applique à chaque membre.
- **Substitution :** un champ « Remplacer » et un champ « par », tous les deux en LaTeX. Par exemple `K` → `\frac{N^*}{2}`, ou `\lambda` → `\mu + 1`. On peut aussi remplacer une dérivée entière, comme `\frac{dN}{dt}` → `0` pour chercher les équilibres.
- **Variable :** la liste propose les symboles de l'expression, et on peut aussi taper du LaTeX.
- **Fonctions :** dans le LaTeX, `\lambda (n-1)` peut être un produit ou un appel de fonction. Par défaut, c'est un **produit**. Les noms listés dans ce champ (`f, g, h` par défaut) sont lus comme des fonctions. `P(n,t)`, qui a plusieurs arguments, et la notation de SymPy `N{\left(t \right)}` sont toujours lus comme des fonctions.
- **Symboles réels positifs :** permet des simplifications comme √(x²) → x ou ln x + ln y → ln(xy). C'est adapté aux taux, effectifs et concentrations.
- **Annuler :** un calcul trop long s'arrête de lui-même après 20 s, ou plus tôt avec le bouton Annuler.

Les éléments suivants sont gardés **tels quels** : ils sont traités comme des symboles, puis réécrits à l'identique :
- les dérivées écrites en fraction (`\frac{\mathrm{d}N}{\mathrm{d}t}`, `\frac{\partial P(n,t)}{\partial t}`, `\frac{\partial^2 u}{\partial x^2}`) ;
- les symboles décorés (`\bar{f}`, `\dot{x}`, `\mathbf{v}_i`, `\hat{p}`…), étoilés (`N^*`) ou primés (`x'`).

`e^{x}` est lu comme l'exponentielle.

**Limites :** une seule équation ou expression à la fois (pas de `align` ni de `\\`). `cases` n'est pas compris par SymPy.

## Dépannage

- **« pdflatex introuvable »** : vérifiez que `/Library/TeX/texbin/pdflatex` existe. L'outil cherche aussi dans `/usr/local/texlive/*/bin/*` et `/opt/homebrew/bin`.
- **Package manquant** : avec MacTeX complet, cela ne devrait pas arriver. Sinon, lancez `sudo tlmgr install <package>`.
- **lualatex lent au premier lancement** : il construit son cache de polices une fois pour toutes.

## Tests

```bash
python -m pytest tests
```

## Structure

```
latex_preview/
  core/            # sans interface graphique, réutilisable en script
    document.py    # analyse de l'extrait collé, construction du .tex
    compiler.py    # appel à TeX Live, analyse et traduction des erreurs
    pdf_tools.py   # recadrage, rendu, export (PyMuPDF)
  ui/              # interface PySide6 (Qt)
  settings.py      # préférences persistantes
```
