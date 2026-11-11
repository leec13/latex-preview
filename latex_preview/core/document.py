"""Transformation d'un extrait LaTeX « brut » en document compilable.

L'utilisateur peut coller :
  * une expression nue (sortie de sympy.latex, par exemple) ;
  * une expression entourée de $...$, $$...$$, \\[...\\] ou \\(...\\) ;
  * un ou plusieurs environnements (equation, align, gather...) ;
  * du texte mêlant prose et formules ;
  * un document complet (avec \\documentclass), compilé tel quel.

Le module détermine le cas, construit le source .tex et garde la
correspondance des numéros de ligne pour signaler les erreurs au bon endroit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

DEFAULT_PREAMBLE = r"""\usepackage{amsmath,amssymb,amsfonts}
\usepackage{mathtools}
\usepackage{bm}
\usepackage{xcolor}

% Macros personnelles (exemples) :
% \newcommand{\E}{\mathbb{E}}
% \newcommand{\Var}{\operatorname{Var}}
% \newcommand{\dd}{\mathrm{d}}
"""

# Environnements de niveau « paragraphe » : ils s'utilisent hors mode math.
DISPLAY_ENVS = (
    "equation", "align", "gather", "multline", "flalign", "alignat",
    "eqnarray", "displaymath", "math",
)
_DISPLAY_ENV_RE = re.compile(
    r"\\begin\{(?:" + "|".join(DISPLAY_ENVS) + r")\*?\}"
)
# Délimiteurs mathématiques non échappés.
_DOLLAR_RE = re.compile(r"(?<!\\)\$")
_BRACKET_OPEN_RE = re.compile(r"(?<!\\)\\\[|(?<!\\)\\\(")
# Couples de délimiteurs extérieurs, du plus spécifique au plus général.
_OUTER_DELIMS = (
    re.compile(r"^\$\$(.*)\$\$$", re.S),
    re.compile(r"^\\\[(.*)\\\]$", re.S),
    re.compile(r"^\\\((.*)\\\)$", re.S),
    re.compile(r"^\$(.*)\$$", re.S),
)
_FENCE_RE = re.compile(r"^\s*```[A-Za-z]*\s*$")


@dataclass
class BuiltDocument:
    source: str            # source .tex complet
    mode: str              # "math", "body" ou "full"
    body_first_line: int   # ligne (1-based) du source où commence le texte utilisateur
    user_line_shift: int   # lignes de l'extrait original retirées avant ce texte
    preamble_first_line: int = 0
    preamble_line_count: int = 0
    user_text: str = ""    # extrait tel que collé (pour retrouver un symbole fautif)
    broken: bool = False   # True si la coupure automatique (breqn) est utilisée
    notes: list[str] = field(default_factory=list)

    def find_token_line(self, token: str) -> int | None:
        """Ligne (1-based) de la première occurrence d'une commande dans l'extrait."""
        rx = re.compile(re.escape(token) + (r"(?![A-Za-z])" if token[-1:].isalpha() else ""))
        m = rx.search(self.user_text)
        return self.user_text.count("\n", 0, m.start()) + 1 if m else None

    def user_line_count(self) -> int:
        return self.user_text.count("\n") + 1

    def map_line(self, tex_line: int) -> tuple[str, int] | None:
        """Convertit un numéro de ligne du .tex en (zone, ligne).

        zone vaut "extrait" ou "préambule"; None si la ligne est ailleurs.
        """
        if self.mode == "full":
            return ("extrait", tex_line)
        if self.body_first_line <= tex_line:
            return ("extrait", tex_line - self.body_first_line + 1 + self.user_line_shift)
        p0 = self.preamble_first_line
        if p0 and p0 <= tex_line < p0 + self.preamble_line_count:
            return ("préambule", tex_line - p0 + 1)
        return None


def strip_code_fences(text: str) -> str:
    """Retire les clôtures Markdown ```latex ... ``` (copie depuis un chat)."""
    lines = text.splitlines()
    if lines and any(_FENCE_RE.match(l) for l in lines):
        lines = [("" if _FENCE_RE.match(l) else l) for l in lines]
    return "\n".join(lines)


def _strip_env_blocks(text: str) -> str:
    """Supprime les blocs \\begin{..}..\\end{..} imbriqués (pour l'analyse)."""
    pattern = re.compile(r"\\begin\{([^}]*)\}(?:(?!\\begin\{).)*?\\end\{\1\}", re.S)
    prev = None
    while prev != text:
        prev = text
        text = pattern.sub(" ", text)
    return text


def _has_math_delimiters(text: str) -> bool:
    return bool(
        _DOLLAR_RE.search(text)
        or _BRACKET_OPEN_RE.search(text)
        or _DISPLAY_ENV_RE.search(text)
    )


def _math_env(math: str, auto_break: bool = False) -> str:
    """Choisit l'environnement adapté à une expression nue.

    Si l'utilisateur a déjà structuré l'expression (& ou \\\\), on respecte
    ses choix ; sinon, avec auto_break, on utilise dmath* (package breqn) qui
    coupe les lignes trop longues et aligne les suites sur le signe « = ».
    """
    top = _strip_env_blocks(math)
    if re.search(r"(?<!\\)&", top):
        return "align*"
    if "\\\\" in top:
        return "gather*"
    return "dmath*" if auto_break else "equation*"


# Conversions vers breqn dans le mode « texte et formules » (sans changer
# le nombre de lignes, pour garder la correspondance des numéros de ligne).
_BODY_BREAK_SUBS = [
    (re.compile(r"\\(begin|end)\{equation(\*?)\}"), r"\\\1{dmath\2}"),
    (re.compile(r"(?<!\\)\\\["), r"\\begin{dmath*}"),
    (re.compile(r"(?<!\\)\\\]"), r"\\end{dmath*}"),
]
_DOUBLE_DOLLAR_RE = re.compile(r"(?<!\\)\$\$(.+?)(?<!\\)\$\$", re.S)


def _body_to_breqn(body: str) -> tuple[str, bool]:
    new = _DOUBLE_DOLLAR_RE.sub(lambda m: "\\begin{dmath*}" + m.group(1) + "\\end{dmath*}", body)
    for rx, rep in _BODY_BREAK_SUBS:
        new = rx.sub(rep, new)
    return new, new != body


def classify(snippet: str) -> tuple[str, str, int]:
    """Retourne (mode, texte, lignes retirées au début).

    mode : "full" (document complet), "body" (à placer tel quel dans le
    corps) ou "math" (expression à envelopper dans un environnement).
    """
    text = strip_code_fences(snippet)
    leading = len(text) - len(text.lstrip())
    shift = text[:leading].count("\n")
    text = text.strip()

    if "\\documentclass" in text:
        return "full", snippet, 0

    for rx in _OUTER_DELIMS:
        m = rx.match(text)
        if m and not _has_math_delimiters(m.group(1)):
            inner = m.group(1)
            return "math", inner.strip("\n"), shift + (1 if inner.startswith("\n") else 0)

    if _has_math_delimiters(text):
        return "body", text, shift
    return "math", text, shift


def build_document(
    snippet: str,
    preamble: str = DEFAULT_PREAMBLE,
    font_size: int = 11,
    text_width_cm: float = 16.0,
    auto_break: bool = False,
    line_width_pt: float | None = None,
) -> BuiltDocument:
    """Construit le source .tex.

    auto_break : coupe les équations trop longues (breqn).
    line_width_pt : largeur de ligne imposée (p. ex. celle de la fenêtre
    d'aperçu) ; sinon text_width_cm.
    """
    mode, body, shift = classify(snippet)
    if mode == "full":
        return BuiltDocument(source=snippet, mode="full", body_first_line=1,
                             user_line_shift=0, user_text=snippet)

    # Page large et très haute : le contenu qui déborde reste visible,
    # et le recadrage automatique supprime ensuite le blanc.
    margin_pt = 170.0  # ≈ 6 cm
    width_pt = line_width_pt if line_width_pt else text_width_cm * 72.27 / 2.54
    header = [
        f"\\documentclass[{font_size}pt]{{article}}",
        f"\\usepackage[paperwidth={width_pt + 2 * margin_pt:.1f}pt,"
        f"paperheight=200cm,textwidth={width_pt:.1f}pt,"
        f"top=2cm,hmargin={margin_pt:.1f}pt]{{geometry}}",
        "\\pagestyle{empty}",
        "\\setlength{\\parindent}{0pt}",
    ]
    preamble_lines = preamble.rstrip("\n").splitlines()
    preamble_first = len(header) + 1

    broken = False
    if mode == "math":
        env = _math_env(body, auto_break)
        broken = env == "dmath*"
        content = f"\\begin{{{env}}}\n{body}\n\\end{{{env}}}"
        open_lines = 1  # ligne \begin{env}
    else:
        content, broken = _body_to_breqn(body) if auto_break else (body, False)
        open_lines = 0

    # breqn doit être chargé après amsmath/mathtools, donc après le préambule.
    extra = ["\\usepackage{breqn}"] if broken else []
    lines = header + preamble_lines + extra + ["\\begin{document}"]

    body_first_line = len(lines) + 1 + open_lines
    source = "\n".join(lines) + "\n" + content + "\n\\end{document}\n"
    return BuiltDocument(
        source=source,
        mode=mode,
        body_first_line=body_first_line,
        user_line_shift=shift,
        preamble_first_line=preamble_first,
        preamble_line_count=len(preamble_lines),
        user_text=snippet,
        broken=broken,
    )
