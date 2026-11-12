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

## Erreurs : corrections proposées et conseils

**Quand le texte ne compile pas**, l'outil cherche une correction vraisemblable et **ne la propose que si le texte corrigé compile vraiment**. L'aperçu montre alors le rendu corrigé avec un **liseré orange**, et la correction est décrite dans un **bandeau orange** juste sous l'aperçu. **Appliquer**, ou **⌘⇧↵**, modifie le texte, et ⌘Z revient en arrière. Rien ne change sans ce clic. Sans correction possible, l'aperçu garde le dernier rendu valide en grisé.

| Erreur | Correction proposée |
|---|---|
| accolade non fermée (`\frac{a}{b`, `\frac{\partial{N}{\partial t}`) | `}` ajoutée au bon endroit |
| accolade en trop | `}` supprimée |
| `\left(` sans `\right)` | `\right)` ajouté en fin de ligne |
| `\right)` sans `\left(` | **pas de correction** : l'erreur et sa ligne sont signalées, et c'est à vous de placer le `\left(` |
| commande mal orthographiée (`\fracc`, `\lamda`, `\langel`) | la commande connue la plus proche, macros du préambule comprises |
| double exposant `x^2^3` | `x^{2^3}` |
| caractères Unicode collés (`α ≤ β · γ`) | `\alpha \leq \beta \cdot \gamma` |
| `$…$` dans une équation | `$` retirés |

**Conseils (le texte compile, mais il y a sans doute un oubli)**, dans le bandeau bleu sous l'aperçu :
- **`\` manquant** devant une lettre grecque ou une commande courante (`alpha`, `theta_A`, `partial`, `sum`, `int`, `prod`, `infty`, `sqrt`, `frac`, `exp`, `ln`, `log`, `sin`, `cos`…). Le bouton Appliquer ajoute les `\`.
  - Les lettres grecques courtes, comme `mu`, `pi`, `nu`, `xi`, `phi` ou `tau`, ne sont signalées que suivies d'un indice ou d'un exposant (`mu_A`), pour ne pas confondre avec un produit voulu (m·u).
  - Rien n'est signalé dans `\text{…}`, `\mathrm{…}` ou le texte hors formules.
- **Parenthèses déséquilibrées** : la ligne concernée est indiquée, sans correction automatique.
- **Caractères Unicode** qui compilent avec lualatex ou xelatex mais s'affichent mal.

## Panneau Traduction LaTeX → Python (⌘K)

Chaque équation de l'éditeur est traduite en une ligne de code Python, en direct, avec les noms d'un **modèle** de correspondances. Le modèle par défaut correspond à deux niches et deux phénotypes, avec les conventions de `moment_closure.py`.

- Exemple : `\frac{d}{dt}\langle N_{A}^{x_1} N_{A}^{x_2}\rangle = -\frac{2}{K_A}\langle (N_{A}^{x_1})^2 N_{A}^{x_2}\rangle + m\,\langle N_{A}^{x_2} N_{B}^{x_1}\rangle` → `dM_A1_A2_dt = M_A2_B1*m - 2*T_A1_A1_A2/KA`
  - L'ordre des termes est celui de SymPy, qui place les majuscules d'abord.
  - Les écritures équivalentes d'un même moment donnent le même nom.
- **Relations sans dérivée** (fermetures) : `\langle (N_{A}^{x_1})^2 N_{A}^{x_2}\rangle \approx …` → `T_A1_A1_A2 = …`. `\approx` et `\simeq` sont lus comme `=`.
- **Systèmes** (`align`, `\\`, lignes de continuation `&\quad + …`) : une ligne par équation.
- **Symboles hors modèle** : ils reçoivent un **nom automatique**, indiqué sous le code : `N_{1}` → `N1`, `r_{1}` → `r1`, `\delta` → `delta`, `x_{i,j}` → `xij`, `\theta_{12}` → `theta12`. Un nom déjà pris par le modèle reçoit un suffixe (`KA_2`).
- **Fonctions** : `R_1(z)` est une fonction si `R1 = R_1` est déclaré dans la section `[fonctions]` du modèle. Sans déclaration, `\mathrm{R1}(z)`, avec une parenthèse simple, est un appel, et `\mathrm{N11}\left(…\right)` est un produit.
- **Options** :
  - **Développer** donne le même format que `--print-eqs` ;
  - **Remplacer par les définitions** remplace par exemple `r_A1` par `rmaxA - s*(x1 - thA)**2`.
- **Le modèle** est un fichier `.ini` lisible, qu'on modifie avec « Modifier le modèle… ». On peut l'enregistrer, le partager et en ouvrir un autre. Une variable peut avoir plusieurs écritures, séparées par `|` (`N_{A}^{x_1} | N_{A}^{1}`), et la première sert pour l'affichage.
- Une erreur de frappe ne produit jamais de traduction partielle : le message d'erreur s'affiche à la place du code.

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
    translate.py   # traduction LaTeX → Python
    fixes.py       # corrections proposées et conseils
    sympy_ops.py   # lecture du LaTeX par SymPy (moments, indices, dérivées)
  ui/              # interface PySide6 (Qt)
  settings.py      # préférences persistantes
```
