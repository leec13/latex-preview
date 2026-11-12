"""Corrections proposées (erreurs de compilation) et conseils (oublis qui compilent).

Validé avec l'utilisateur (12/11/2026) :
* une correction n'est proposée que si le texte corrigé COMPILE (vérifié par
  pipeline.py, qui essaie les candidats de candidates() dans l'ordre) ;
* rien n'est modifié sans clic sur « Appliquer » ;
* conseils non bloquants : « \\ » manquant devant une lettre grecque ou une
  commande courante, parenthèses déséquilibrées, caractères Unicode.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

GREEK = ("alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa lambda mu nu "
         "xi pi varpi rho varrho sigma varsigma tau upsilon phi varphi chi psi omega "
         "Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega").split()

# Commandes connues (pour retrouver une commande mal orthographiée).
KNOWN = set(GREEK) | set("""
frac dfrac tfrac sqrt sum prod int iint iiint oint lim limsup liminf infty partial nabla
cdot cdots ldots dots vdots ddots times div pm mp leq geq neq le ge ne approx simeq equiv sim
propto to rightarrow leftarrow Rightarrow Leftarrow Leftrightarrow leftrightarrow mapsto
langle rangle left right big Big bigg Bigg bigl bigr Bigl Bigr biggl biggr Biggl Biggr
mathrm mathit mathbf mathbb mathcal mathfrak mathsf mathtt boldsymbol bm text textrm textit
operatorname exp log ln sin cos tan cot sinh cosh tanh arcsin arccos arctan max min sup inf
det dim ker deg gcd arg Pr hat bar tilde dot ddot vec overline underline widehat widetilde
overbrace underbrace binom quad qquad label nonumber notag displaystyle textstyle in notin
subset subseteq supset cup cap emptyset varnothing forall exists neg land lor star ast circ
bullet prime ell hbar Re Im mid parallel perp angle colon vert Vert lvert rvert lVert rVert
lfloor rfloor lceil rceil not begin end mathop limits nolimits stackrel overset underset
xrightarrow underline cfrac substack phantom hspace vspace mbox hbox
""".split())

# Mots que l'on signale quand ils sont écrits sans « \ » (dans les maths).
ADVICE_WORDS = set(GREEK) - {"eta", "nu", "mu", "pi", "xi", "chi", "phi", "psi", "tau", "rho"} | {
    "partial", "sum", "prod", "int", "infty", "sqrt", "frac", "langle", "rangle", "exp", "ln",
    "log", "sin", "cos", "tan", "lim", "nabla", "cdot", "leq", "geq", "approx",
}
# Lettres grecques courtes : signalées seulement suivies d'un indice ou exposant (mu_A, pi^2),
# pour ne pas confondre avec des produits voulus (m·u).
SHORT_GREEK = {"eta", "nu", "mu", "pi", "xi", "chi", "phi", "psi", "tau", "rho"}

UNICODE = {
    "α": r"\alpha", "β": r"\beta", "γ": r"\gamma", "δ": r"\delta", "ε": r"\varepsilon",
    "ζ": r"\zeta", "η": r"\eta", "θ": r"\theta", "ι": r"\iota", "κ": r"\kappa", "λ": r"\lambda",
    "μ": r"\mu", "ν": r"\nu", "ξ": r"\xi", "π": r"\pi", "ρ": r"\rho", "σ": r"\sigma", "τ": r"\tau",
    "υ": r"\upsilon", "φ": r"\varphi", "ϕ": r"\phi", "χ": r"\chi", "ψ": r"\psi", "ω": r"\omega",
    "Γ": r"\Gamma", "Δ": r"\Delta", "Θ": r"\Theta", "Λ": r"\Lambda", "Ξ": r"\Xi", "Π": r"\Pi",
    "Σ": r"\Sigma", "Φ": r"\Phi", "Ψ": r"\Psi", "Ω": r"\Omega",
    "≤": r"\leq", "≥": r"\geq", "≠": r"\neq", "≈": r"\approx", "≃": r"\simeq", "≡": r"\equiv",
    "∼": r"\sim", "∝": r"\propto", "·": r"\cdot", "⋅": r"\cdot", "×": r"\times", "÷": r"\div",
    "±": r"\pm", "∓": r"\mp", "∞": r"\infty", "∂": r"\partial", "∇": r"\nabla", "∑": r"\sum",
    "∏": r"\prod", "∫": r"\int", "√": r"\sqrt", "→": r"\to", "←": r"\leftarrow",
    "⇒": r"\Rightarrow", "⇔": r"\Leftrightarrow", "↦": r"\mapsto", "⟨": r"\langle",
    "⟩": r"\rangle", "∈": r"\in", "∉": r"\notin", "∀": r"\forall", "∃": r"\exists",
    "…": r"\dots", "⋯": r"\cdots", "−": "-", "–": "-", "∗": "*", "′": "'",
    "²": "^{2}", "³": "^{3}", "¹": "^{1}", "⁴": "^{4}", "⁰": "^{0}",
    "₀": "_{0}", "₁": "_{1}", "₂": "_{2}", "₃": "_{3}", "₄": "_{4}",
    "\u00a0": " ",
}

_PAIRS = {"(": ")", "[": "]", r"\{": r"\}", "|": "|", ".": ".", r"\langle": r"\rangle",
          r"\lvert": r"\rvert", r"\|": r"\|", r"\lfloor": r"\rfloor", r"\lceil": r"\rceil"}


@dataclass
class Fix:
    text: str           # texte complet corrigé
    description: str


@dataclass
class Advice:
    message: str
    text: str | None = None   # texte corrigé si l'on peut appliquer automatiquement


# =================================================================== outils
def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _brace_scan(text: str) -> tuple[list[int], list[int]]:
    """(positions des « { » non fermées, positions des « } » en trop)."""
    stack, extra = [], []
    k = 0
    while k < len(text):
        c = text[k]
        if c == "\\":
            k += 2
            continue
        if c == "%":  # commentaire jusqu'à la fin de la ligne
            nl = text.find("\n", k)
            k = len(text) if nl < 0 else nl
            continue
        if c == "{":
            stack.append(k)
        elif c == "}":
            if stack:
                stack.pop()
            else:
                extra.append(k)
        k += 1
    return stack, extra


def _end_of_line(text: str, pos: int) -> int:
    nl = text.find("\n", pos)
    end = len(text) if nl < 0 else nl
    while end > pos and text[end - 1] in " \t":
        end -= 1
    return end


def _insert(text: str, pos: int, what: str) -> str:
    return text[:pos] + what + text[pos:]


def user_macros(preamble: str) -> set[str]:
    return set(re.findall(r"\\(?:re)?newcommand\*?\s*\{?\\([A-Za-z]+)", preamble or "")) | \
        set(re.findall(r"\\DeclareMathOperator\*?\s*\{?\\([A-Za-z]+)", preamble or ""))


# =================================================================== candidats
def unicode_fix(text: str) -> Fix | None:
    found = [ch for ch in dict.fromkeys(text) if ch in UNICODE and ch != "\u00a0"]
    if not found and "\u00a0" not in text:
        return None
    out = []
    for i, ch in enumerate(text):
        rep = UNICODE.get(ch)
        if rep is None:
            out.append(ch)
            continue
        nxt = text[i + 1] if i + 1 < len(text) else ""
        out.append(rep + (" " if rep.startswith("\\") and nxt.isalpha() else ""))
    desc = "Caractères Unicode remplacés : " + ", ".join(f"{c} → {UNICODE[c]}" for c in found[:6])
    if len(found) > 6:
        desc += "…"
    if not found:
        desc = "Espaces insécables remplacées"
    return Fix("".join(out), desc)


def _brace_candidates(text: str) -> list[Fix]:
    opened, extra = _brace_scan(text)
    out = []
    if extra:
        pos = extra[0]
        out.append(Fix(text[:pos] + text[pos + 1:],
                       f"Accolade « }} » en trop supprimée (ligne {_line_of(text, pos)})"))
    if opened:
        pos = opened[-1]
        line = _line_of(text, pos)
        # 1) fermer juste après le groupe qui suit : \partial{N}{… → \partial{N}}{…
        for m in re.finditer(r"\}", text[pos + 1:]):
            at = pos + 1 + m.end()
            out.append(Fix(_insert(text, at, "}"),
                           f"Accolade « }} » ajoutée (ligne {_line_of(text, at)}), "
                           f"pour fermer celle ouverte ligne {line}"))
            if len(out) >= 3:
                break
        # 2) en fin de ligne, 3) en fin de texte
        eol = _end_of_line(text, pos)
        out.append(Fix(_insert(text, eol, "}" * len(opened) if len(opened) > 1 else "}"),
                       f"Accolade « }} » ajoutée en fin de ligne {line}"))
        end = len(text.rstrip())
        if end != eol:
            out.append(Fix(_insert(text, end, "}"), "Accolade « } » ajoutée à la fin"))
    return out


def _left_right_candidates(text: str) -> list[Fix]:
    lefts = list(re.finditer(r"\\left\s*(\\[A-Za-z]+|\\[{}|]|[()\[\]|.])", text))
    rights = list(re.finditer(r"\\right\s*(\\[A-Za-z]+|\\[{}|]|[()\[\]|.])", text))
    out = []
    if len(lefts) > len(rights):
        # le dernier \left sans partenaire : on cherche en appariant de droite à gauche
        unmatched = None
        events = sorted([(m.start(), +1, m) for m in lefts] + [(m.start(), -1, m) for m in rights])
        stack = []
        for _, kind, m in events:
            if kind > 0:
                stack.append(m)
            elif stack:
                stack.pop()
        unmatched = stack[-1] if stack else lefts[-1]
        delim = unmatched.group(1)
        close = r"\right" + _PAIRS.get(delim, ".")
        line = _line_of(text, unmatched.start())
        eol = _end_of_line(text, unmatched.end())
        out.append(Fix(_insert(text, eol, " " + close),
                       f"« {close} » ajouté en fin de ligne {line} (pour le \\left{delim})"))
        end = len(text.rstrip())
        if end != eol:
            out.append(Fix(_insert(text, end, " " + close), f"« {close} » ajouté à la fin"))
        out.append(Fix(text[:unmatched.start()] + delim + text[unmatched.end():],
                       f"« \\left{delim} » remplacé par « {delim} » (ligne {line})"))
    elif len(rights) > len(lefts):
        stack, extra = 0, None
        events = sorted([(m.start(), +1, m) for m in lefts] + [(m.start(), -1, m) for m in rights])
        for _, kind, m in events:
            if kind > 0:
                stack += 1
            elif stack:
                stack -= 1
            elif extra is None:
                extra = m
        extra = extra or rights[0]
        delim = extra.group(1)
        out.append(Fix(text[:extra.start()] + delim + text[extra.end():],
                       f"« \\right{delim} » sans \\left remplacé par « {delim} » "
                       f"(ligne {_line_of(text, extra.start())})"))
    return out


def _typo_candidates(text: str, errors, known: set[str]) -> list[Fix]:
    """Commande mal orthographiée → commande connue la plus proche.

    On ne dépend pas du journal de compilation (son format varie selon la version de
    TeX Live) : on prend d'abord les commandes citées dans le journal, puis toutes les
    commandes du texte qui ne sont pas connues. Seules les corrections qui compilent
    seront retenues (pipeline)."""
    from_log = [e.context[1:] for e in errors
                if "Undefined control sequence" in e.message and e.context.startswith("\\")]
    in_text = [n for n in re.findall(r"\\([A-Za-z]+)", text) if n not in known]
    singles, best, logged = [], {}, []
    for name in dict.fromkeys(from_log + in_text):
        rx = re.compile(r"\\" + re.escape(name) + r"(?![A-Za-z])")
        if not rx.search(text):
            continue
        matches = difflib.get_close_matches(name, sorted(known), n=2, cutoff=0.7)
        if matches:
            best[name] = matches[0]
        for good in matches:
            fix = Fix(rx.sub(lambda _: "\\" + good, text), f"« \\{name} » remplacé par « \\{good} »")
            (logged if name in from_log else singles).append(fix)
    # Ordre : la commande citée par TeX corrigée seule, puis toutes ensemble, puis les autres.
    out = logged
    if len(best) > 1:
        # Plusieurs fautes à la fois (\fracc … \lamda …) : toutes corrigées ensemble d'abord,
        # sinon aucune correction isolée ne compile.
        fixed = text
        for name, good in best.items():
            fixed = re.sub(r"\\" + re.escape(name) + r"(?![A-Za-z])", lambda _, g=good: "\\" + g, fixed)
        out.append(Fix(fixed, "Commandes corrigées : "
                       + ", ".join(f"\\{n} → \\{g}" for n, g in best.items())))
    return out + singles


def _double_script_candidates(text: str) -> list[Fix]:
    out = []
    for op in ("^", "_"):
        rx = re.compile(re.escape(op) + r"(\{[^{}]*\}|\\?[A-Za-z0-9])" + re.escape(op)
                        + r"(\{[^{}]*\}|\\?[A-Za-z0-9])")
        m = rx.search(text)
        if m:
            a = m.group(1)[1:-1] if m.group(1).startswith("{") else m.group(1)
            new = f"{op}{{{a}{op}{m.group(2)}}}"
            word = "exposant" if op == "^" else "indice"
            out.append(Fix(text[:m.start()] + new + text[m.end():],
                           f"Double {word} : « {m.group(0)} » écrit « {new} »"))
    return out


def _dollar_candidates(text: str) -> list[Fix]:
    if "$" not in text.replace(r"\$", ""):
        return []
    return [Fix(re.sub(r"(?<!\\)\$+", " ", text), "Signes « $ » retirés")]


def candidates(text: str, errors, preamble: str = "") -> list[Fix]:
    """Corrections à essayer, de la plus vraisemblable à la moins vraisemblable.

    Les caractères Unicode sont remplacés d'abord (et combinés aux autres corrections)."""
    known = KNOWN | user_macros(preamble)
    base_fix = unicode_fix(text)
    base = base_fix.text if base_fix else text
    msgs = " ".join(e.message for e in errors)
    structural: list[Fix] = []
    structural += _typo_candidates(base, errors, known)
    structural += _brace_candidates(base)
    structural += _left_right_candidates(base)
    if "Double superscript" in msgs or "Double subscript" in msgs:
        structural += _double_script_candidates(base)
    structural += _dollar_candidates(base)
    out = []
    if base_fix:
        out.append(base_fix)
        out += [Fix(f.text, base_fix.description + " ; " + f.description) for f in structural]
    else:
        out = structural
    seen, unique = set(), []
    for f in out:
        if f.text != text and f.text not in seen:
            seen.add(f.text)
            unique.append(f)
    return unique


# =================================================================== conseils
_MATH_RE = re.compile(
    r"\$\$.*?\$\$|(?<!\\)\$.*?(?<!\\)\$|\\\[.*?\\\]|\\\(.*?\\\)"
    r"|\\begin\{(equation|align|gather|multline|flalign|alignat|eqnarray|dmath|displaymath|math)"
    r"\*?\}.*?\\end\{\1\*?\}", re.S)
_TEXT_ARG_RE = re.compile(r"\\(text|textrm|textit|mathrm|operatorname|mbox|label|begin|end|"
                          r"usepackage|documentclass|tag|ref|eqref|cite)\*?\s*\{[^{}]*\}")


def _math_regions(text: str, mode: str) -> list[tuple[int, int]]:
    if mode == "math":
        return [(0, len(text))]
    return [(m.start(), m.end()) for m in _MATH_RE.finditer(text)]


def _mask(text: str) -> str:
    """Remplace commentaires et arguments textuels par des espaces (positions gardées)."""
    t = re.sub(r"(?<!\\)%.*", lambda m: " " * len(m.group(0)), text)
    return _TEXT_ARG_RE.sub(lambda m: " " * len(m.group(0)), t)


def advice(text: str, mode: str) -> list[Advice]:
    """Conseils non bloquants. mode : « math », « body » ou « full »."""
    out = []
    masked = _mask(text)
    regions = _math_regions(masked, mode)

    # 1. « \ » manquant
    hits = []
    word_rx = re.compile(r"(?<![\\A-Za-z])([A-Za-z]+)(?![A-Za-z])")
    for a, b in regions:
        for m in word_rx.finditer(masked, a, b):
            w = m.group(1)
            if w in ADVICE_WORDS or (w in SHORT_GREEK and masked[m.end():m.end() + 1] in ("_", "^")):
                hits.append(m)
    if hits:
        words = list(dict.fromkeys(m.group(1) for m in hits))
        fixed = text
        for m in sorted(hits, key=lambda m: m.start(), reverse=True):
            fixed = fixed[:m.start()] + "\\" + fixed[m.start():]
        out.append(Advice("Il manque probablement des « \\ » : "
                          + ", ".join(f"{w} → \\{w}" for w in words[:6])
                          + ("…" if len(words) > 6 else ""), fixed))

    # 2. parenthèses déséquilibrées
    for a, b in regions:
        first_extra, opens = None, []
        for k in range(a, b):
            c = masked[k]
            if c == "(":
                opens.append(k)
            elif c == ")":
                if opens:
                    opens.pop()
                elif first_extra is None:
                    first_extra = k
        if first_extra is not None:
            out.append(Advice(f"Parenthèse « ) » en trop, ligne {_line_of(text, first_extra)}"))
            break
        if opens:
            out.append(Advice(f"Parenthèse « ( » jamais fermée, ouverte ligne {_line_of(text, opens[0])}"))
            break

    # 3. Unicode (compile parfois avec lualatex/xelatex, mais s'affiche mal)
    uf = unicode_fix(text)
    if uf and any(ch in UNICODE and ch != "\u00a0" for ch in text):
        out.append(Advice(uf.description.replace("remplacés", "à remplacer"), uf.text))
    return out
