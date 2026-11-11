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

## Avec SymPy

```python
import sympy as sp
t = sp.symbols("t"); N = sp.Function("N")
r, K = sp.symbols("r K", positive=True)
print(sp.latex(sp.Eq(N(t).diff(t), r*N(t)*(1 - N(t)/K))))
```

Collez la sortie dans l'outil. Une intégration directe de SymPy dans l'interface est prévue pour une prochaine version.

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
