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

## Panneau Traduction LaTeX ⇄ Python (⌘K)

Ce panneau fait le lien entre les équations écrites en LaTeX, par exemple transcrites depuis le tableau blanc, et vos scripts Python/SymPy. Il s'appuie sur un **modèle** : une table de correspondance exacte entre noms Python et écriture LaTeX. Il ne devine rien : tout symbole absent du modèle est **signalé** (⚠).

**LaTeX de l'éditeur → Python** (en direct)
- Chaque équation de l'éditeur donne une ligne de code, par exemple :
  `\frac{d}{dt} \langle (N_{A}^{x_1})^{2} \rangle = …` → `dM_A1_A1_dt = …`
- Les moments sont nommés comme dans `moment_closure.py` : `n_A1`, `M_A1_A2`, `T_A1_A1_A2`, `Q_…`. Les variables sont triées dans l'ordre A1, A2, B1, B2. Les écritures équivalentes donnent le même nom : `\langle N_{A}^{x_2} N_{A}^{x_1} \rangle` → `M_A1_A2`.
- Un système (`align`, plusieurs lignes `\\`, lignes de continuation `&\quad + …`) donne une ligne par équation.
- Options :
  - **Développer** donne le même format que `--print-eqs` ;
  - **Remplacer par les définitions** remplace par exemple `r_A1` par `rmaxA - s*(x1 - thA)**2`.
- **Copier le Python** pour le coller dans un script.

**Python → LaTeX** (vers l'éditeur)
- Collez une sortie de script, avec une ligne par équation, par exemple `dM_A1_A2/dt = …` ou `dM_A1_A2_dt = …`, puis cliquez sur **Convertir dans l'éditeur**. Le texte de l'éditeur est remplacé, et ⌘Z revient en arrière.
- Plusieurs équations donnent un bloc par équation, et chacune est coupée à la largeur de la fenêtre.
- **Regrouper par moment** met chaque moment en facteur. C'est plus lisible qu'une sortie développée.
- L'aller-retour est exact : Python → LaTeX → Python redonne la même expression. C'est vérifié par les tests sur une sortie réelle de `moment_closure.py`.

**Le modèle** (bouton « Modifier le modèle… »)
- C'est un petit fichier `.ini` lisible. Vous pouvez l'**enregistrer et le partager** avec l'équipe, et en **ouvrir** un autre pour un autre modèle.
- Le modèle par défaut correspond à deux niches et deux phénotypes. Il contient :
  - les variables `A1 = N_{A}^{x_1}`… ;
  - les préfixes `n, M, T, Q` ;
  - les paramètres `rmaxA = r_{\max,A}`, `thA = \theta_A`, `KA = K_A`, `r_A1 = r_{A}^{x_1}`… ;
  - les définitions des `r_A1`….
- Une même variable peut avoir plusieurs écritures, séparées par `|`. Par exemple, `N_{A}^{x_1} | N_{A}^{1}` reconnaît les deux notations, et la première sert pour l'affichage.
- Les **fonctions** appelées avec des arguments, comme `R1(z_star1)`, se déclarent dans la section `[fonctions]`, par exemple `R1 = R_1`. Sans déclaration, la convention suivante s'applique :
  - `\mathrm{R1}(z)`, avec une parenthèse simple, est un appel ;
  - `\mathrm{N11}\left(…\right)` est un produit ;
  - `\operatorname{f}(…)` est toujours une fonction.
  Les noms hors modèle sont écrits `\mathrm{…}`, pour être relus comme un seul nom.
- Un exposant sur un symbole du modèle est une puissance (`x_1^{2}` = x₁²). Un exposant qui fait partie d'un nom du modèle (`N_{A}^{x_1}`) est un indice.

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
    pipeline.py    # chaîne complète, coupure des lignes longues
    model.py       # modèle de correspondances noms Python ⇄ LaTeX (.ini)
    translate.py   # traduction LaTeX ⇄ Python
    sympy_ops.py   # lecture du LaTeX par SymPy (moments, indices, dérivées)
  ui/              # interface PySide6 (Qt)
  settings.py      # préférences persistantes
```
