"""Opérations SymPy sur du LaTeX : LaTeX → SymPy → opération → LaTeX.

Le parseur LaTeX de SymPy (backend antlr) a quelques pièges que ce module
corrige :
  * `\\lambda (n-1)` ou `x\\left(1-x\\right)` sont lus comme des appels de
    fonction : on les reconvertit en produits, sauf pour les fonctions
    déclarées (champ « Fonctions »), celles à plusieurs arguments `P(n,t)` et
    celles écrites à la manière de SymPy `N{\\left(t \\right)}` ;
  * `e^{x}` : le symbole `e` devient la constante d'Euler ;
  * les dérivées `\\frac{dN}{dt}`, `\\frac{\\partial^2 u}{\\partial x^2}` et les
    symboles décorés `\\bar{f}`, `\\dot{x}`, `\\mathbf{x}`… sont remplacés avant
    lecture par des symboles opaques, puis réécrits à l'identique en sortie.

Toutes les fonctions publiques prennent et rendent des chaînes : elles
peuvent tourner dans un processus séparé (interruptible).
"""

from __future__ import annotations

import re
import string
import warnings
from dataclasses import dataclass, field

from .document import classify

OPERATIONS = {
    "simplify": "Simplifier",
    "expand": "Développer",
    "factor": "Factoriser",
    "cancel": "Réduire",
    "apart": "Éléments simples",
    "collect": "Regrouper selon",
    "diff": "Dériver par rapport à",
    "integrate": "Intégrer par rapport à",
    "doit": "Évaluer",
    "solve": "Résoudre pour",
    "subs": "Substituer",
}
NEEDS_VAR = {"collect", "diff", "integrate", "solve", "apart"}

_DECORATORS = ("dot", "ddot", "hat", "widehat", "bar", "overline", "tilde", "widetilde",
               "vec", "mathbf", "boldsymbol", "bm", "mathcal", "mathbb", "mathfrak",
               "mathsf", "mathrm", "mathit", "operatorname", "check", "breve")


class SympyLatexError(Exception):
    pass


# ---------------------------------------------------------------- outils texte
def _read_group(s: str, i: int) -> tuple[str, int] | None:
    """Lit un groupe {...} commençant à s[i] == '{'. Retourne (contenu, fin)."""
    if i >= len(s) or s[i] != "{":
        return None
    depth = 0
    for j in range(i, len(s)):
        c = s[j]
        if c == "\\":
            continue
        if c == "{" and (j == 0 or s[j - 1] != "\\"):
            depth += 1
        elif c == "}" and s[j - 1] != "\\":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
    return None


def _read_subscript(s: str, i: int) -> int:
    """Si s[i:] commence par un indice _x ou _{...}, retourne sa fin, sinon i."""
    if i < len(s) and s[i] == "_":
        if i + 1 < len(s) and s[i + 1] == "{":
            g = _read_group(s, i + 1)
            return g[1] if g else i
        m = re.match(r"_(\\[A-Za-z]+|[A-Za-z0-9])", s[i:])
        if m:
            return i + m.end()
    return i


def _placeholder_name(n: int) -> str:
    letters = string.ascii_lowercase
    out = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        out = letters[r] + out
    return "Zq" + out


@dataclass
class Context:
    """État partagé entre l'expression, la variable et la substitution."""

    functions: set[str] = field(default_factory=set)
    atoms: dict[str, str] = field(default_factory=dict)   # latex d'origine -> nom
    positive: bool = False
    sup_index: bool = True   # N_{A}^{2} : l'exposant fait partie du nom (indice)
    moments: dict[str, object] = field(default_factory=dict)   # nom -> monôme SymPy
    derivs: dict[str, tuple[str, str]] = field(default_factory=dict)  # nom -> (préfixe, moment)

    def atom(self, latex: str) -> str:
        latex = latex.strip()
        if latex not in self.atoms:
            self.atoms[latex] = _placeholder_name(len(self.atoms))
        return r"\mathit{" + self.atoms[latex] + "}"

    @property
    def atom_latex(self) -> dict[str, str]:
        return {v: k for k, v in self.atoms.items()}

    def symbol(self, name: str):
        sp = _sympy()
        return sp.Symbol(name, positive=True) if self.positive else sp.Symbol(name)

    def latex_of(self, sym) -> str:
        return self.atom_latex.get(sym.name) or _sympy().latex(sym)

    def expand(self, text: str) -> str:
        """Remplace les symboles opaques d'un texte par leur LaTeX d'origine."""
        back = self.atom_latex
        return re.sub(r"\\mathit\{(Zq[a-z]+)\}", lambda m: back.get(m.group(1), m.group(0)), text)


_GREEK = ("(alpha|beta|gamma|delta|epsilon|varepsilon|zeta|eta|theta|vartheta|iota|kappa|"
          "lambda|mu|nu|xi|pi|varpi|rho|varrho|sigma|varsigma|tau|upsilon|phi|varphi|chi|psi|"
          "omega|Gamma|Delta|Theta|Lambda|Xi|Pi|Sigma|Upsilon|Phi|Psi|Omega)")
_STAR_RE = re.compile(
    r"(\\[A-Za-z]+|[A-Za-z])(_\{[^{}]*\}|_[A-Za-z0-9])?"
    r"(\^(\{\s*(\*|\\star|\\ast)\s*\}|\*|\\star(?![A-Za-z])|\\ast(?![A-Za-z]))|'+)")
_GREEK_CMD_RE = re.compile(r"\\" + _GREEK + r"(?![A-Za-z])")
_SIMPLE_SUB_RE = re.compile(r"^(?:[A-Za-z0-9]+|\\" + _GREEK + r")$")


_PLACEHOLDER_RE = re.compile(r"\\mathit\{Zq[a-z]+\}")
_OPEN_RE = re.compile(r"(\\left\s*)?\\langle(?![A-Za-z])")
_CLOSE_RE = re.compile(r"(\\right\s*)?\\rangle(?![A-Za-z])")


def _protect_brackets(s: str, ctx: Context) -> str:
    """`\\langle … \\rangle` (moments, espérances) → symbole opaque, imbrication comprise."""
    out, i = [], 0
    while i < len(s):
        m = _OPEN_RE.match(s, i)
        if not m:
            out.append(s[i])
            i += 1
            continue
        depth, j = 0, i
        while j < len(s):
            mo, mc = _OPEN_RE.match(s, j), _CLOSE_RE.match(s, j)
            if mo:
                depth += 1
                j = mo.end()
            elif mc:
                depth -= 1
                j = mc.end()
                if depth == 0:
                    break
            else:
                j += 1
        if depth:
            raise SympyLatexError("\\langle sans \\rangle correspondant.")
        out.append(_moment_atom(s[i:j], ctx))
        i = j
    return "".join(out)


def _moment_inner(text: str) -> str:
    m_open, m_close = _OPEN_RE.match(text), None
    for m in _CLOSE_RE.finditer(text):
        m_close = m
    return text[m_open.end():m_close.start()]


def moment_latex(inner, ctx: Context) -> str | None:
    """Écriture canonique d'un moment monôme : facteurs triés, (X)^{k}.

    Retourne None si le contenu n'est pas un monôme de symboles."""
    sp = _sympy()
    if not isinstance(inner, (sp.Symbol, sp.Pow, sp.Mul)):
        return None
    parts = []
    for base, exp in inner.as_powers_dict().items():
        if not isinstance(base, sp.Symbol) or not (exp.is_Integer and exp > 0):
            return None
        b = ctx.latex_of(base)
        if exp == 1:
            parts.append((b, b))
        else:
            bb = f"({b})" if ("_" in b or "^" in b or " " in b) else b
            parts.append((b, f"{bb}^{{{exp}}}"))
    parts.sort()
    return r"\langle " + " ".join(p for _, p in parts) + r" \rangle"


def _moment_atom(text: str, ctx: Context) -> str:
    """Moment → symbole opaque ; deux écritures du même monôme → même symbole."""
    try:
        inner = parse(_moment_inner(text), ctx)
    except SympyLatexError:
        inner = None
    canon = moment_latex(inner, ctx) if inner is not None else None
    if canon is None:
        return ctx.atom(text)
    ph = ctx.atom(canon)
    ctx.moments[ph[len(r"\mathit{"):-1]] = inner
    return ph


def _indexed_symbol_end(s: str, i: int, ctx: Context) -> int | None:
    """Fin d'un symbole indicé à garder opaque (indice complexe, ou exposant
    d'indice avec ctx.sup_index), sinon None."""
    m = re.match(r"[A-Za-z](?![A-Za-z])|" + _GREEK_CMD_RE.pattern, s[i:])
    if not m:
        return None
    j = i + m.end()
    k = _read_subscript(s, j)
    if k == j:
        return None
    sub = s[j + 1:k]
    sub = sub[1:-1] if sub.startswith("{") else sub
    complex_sub = not _SIMPLE_SUB_RE.match(sub.strip())
    end = k
    if ctx.sup_index and s[k:k + 1] == "^":
        if s[k + 1:k + 2] == "{":
            g = _read_group(s, k + 1)
            if g:
                end = g[1]
        else:
            m2 = re.match(r"\^([A-Za-z0-9])", s[k:])
            if m2:
                end = k + m2.end()
    if complex_sub or end != k:
        return end
    return None


_DERIV_START = re.compile(r"^\s*(\\mathrm\{d\}|d|\\partial)(\s|\^|\\|[A-Za-z{(]|$)")


def _protect(s: str, ctx: Context) -> str:
    """Remplace dérivées en fraction et symboles décorés par des symboles opaques."""
    out, i = [], 0
    while i < len(s):
        m_ph = _PLACEHOLDER_RE.match(s, i)
        if m_ph:  # symbole opaque déjà posé
            out.append(m_ph.group(0))
            i = m_ph.end()
            continue
        if s.startswith(r"\frac", i) and not s[i + 5:i + 6].isalpha():
            j = i + 5
            while j < len(s) and s[j] == " ":
                j += 1
            num = _read_group(s, j)
            if num:
                k = num[1]
                while k < len(s) and s[k] == " ":
                    k += 1
                den = _read_group(s, k)
                if den and _DERIV_START.match(num[0]) and _DERIV_START.match(den[0]):
                    # Opérateur seul (\frac{d}{dt} f) : laissé au parseur.
                    body = re.sub(r"^\s*(\\mathrm\{d\}|d|\\partial)(\^\{?\d+\}?)?", "", num[0]).strip()
                    if body:
                        out.append(ctx.atom(ctx.expand(s[i:den[1]])))
                        i = den[1]
                        continue
                    # Forme opérateur \frac{d}{dt} X : si X est un symbole
                    # (moment, symbole indicé…), la dérivée entière est opaque.
                    k2 = den[1]
                    while k2 < len(s) and s[k2] == " ":
                        k2 += 1
                    m_ph = re.match(r"\\mathit\{Zq[a-z]+\}", s[k2:])
                    end_sym = k2 + m_ph.end() if m_ph else _indexed_symbol_end(s, k2, ctx)
                    if end_sym is None:
                        m_l = re.match(r"([A-Za-z]|\\" + _GREEK + r")(?![A-Za-z(])(?!\s*\()", s[k2:])
                        end_sym = k2 + m_l.end() if m_l else None
                    if end_sym is not None:
                        ph = ctx.atom(ctx.expand(s[i:end_sym]))
                        if m_ph:
                            inner_name = m_ph.group(0)[len(r"\mathit{"):-1]
                            if inner_name in ctx.moments:
                                prefix = ctx.expand(s[i:k2]).rstrip()
                                ctx.derivs[ph[len(r"\mathit{"):-1]] = (prefix, inner_name)
                        out.append(ph)
                        i = end_sym
                        continue
        # Symbole à indice complexe (r_{\max,A}) ou exposant d'indice (N_{A}^{2}).
        if i == 0 or not (s[i - 1].isalpha() or s[i - 1] == "\\"):
            end_idx = _indexed_symbol_end(s, i, ctx)
            if end_idx is not None:
                # un éventuel ^* derrière fait partie du symbole
                m_st = re.match(r"\^(\{\s*(\*|\\star)\s*\}|\*)", s[end_idx:])
                if m_st:
                    end_idx += m_st.end()
                out.append(ctx.atom(s[i:end_idx]))
                i = end_idx
                continue
        # Symbole étoilé ou primé (équilibre N^*, dérivée N') : opaque.
        m = _STAR_RE.match(s, i)
        if m and (i == 0 or not s[i - 1].isalpha()):
            out.append(ctx.atom(m.group(0)))
            i = m.end()
            continue
        m = re.match(r"\\(" + "|".join(_DECORATORS) + r")(?![A-Za-z])\s*", s[i:])
        if m:
            g = _read_group(s, i + m.end())
            if g:
                name, inner = m.group(1), g[0].strip()
                end = g[1]
                if name == "mathrm" and inner in ("d", "e"):
                    out.append(" " + inner + " ")
                    i = end
                    continue
                if name in ("mathrm", "mathit") and len(inner) == 1 and inner.isalpha():
                    out.append(inner)
                    i = end
                    continue
                end = _read_subscript(s, end)
                out.append(ctx.atom(s[i:end]))
                i = end
                continue
        # Autre commande : recopiée d'un bloc (évite de traiter ses lettres).
        m = re.match(r"\\[A-Za-z]+", s[i:])
        if m:
            out.append(m.group(0))
            i += m.end()
            continue
        out.append(s[i])
        i += 1
    return "".join(out)


_SPACING_RE = re.compile(r"(?<!\\)\\[,;:!> ]|\\q?quad(?![A-Za-z])|~")
_SIZED_RE = re.compile(r"\\(?:big|Big|bigg|Bigg)[lrm]?(?![A-Za-z])")
_SYMPY_CALL_RE = re.compile(r"(\\?[A-Za-z]+(?:_\{[^{}]*\}|_[A-Za-z0-9])?)\s*\{\s*\\left\(")


def _sympy_style_calls(s: str, ctx: Context) -> str:
    """`N{\\left(t \\right)}` (sortie de sympy.latex) → `N(t)`, N déclarée fonction."""
    while True:
        m = _SYMPY_CALL_RE.search(s)
        if not m:
            return s
        brace = s.index("{", m.start(1) + len(m.group(1)))
        g = _read_group(s, brace)
        if not g:
            return s
        inner = g[0].strip()
        inner = re.sub(r"^\\left\(", "(", inner)
        inner = re.sub(r"\\right\)$", ")", inner)
        ctx.functions.add(m.group(1).lstrip("\\"))
        s = s[:m.start()] + m.group(1) + inner + s[g[1]:]


def preprocess(text: str, ctx: Context) -> str:
    s = text.strip()
    mode, inner, _ = classify(s)
    if mode != "math":
        raise SympyLatexError(
            "SymPy ne traite qu'une expression ou une équation à la fois : "
            "sélectionnez une seule formule dans l'éditeur.")
    s = inner.strip()
    s = re.sub(r"(?<!\\)%.*$", "", s, flags=re.M)        # commentaires
    s = s.replace(r"\dfrac", r"\frac").replace(r"\tfrac", r"\frac")
    s = re.sub(r"\\left\s*\.|\\right\s*\.", " ", s)
    s = _SIZED_RE.sub("", s)
    s = _SPACING_RE.sub(" ", s)
    s = re.sub(r"[.,;]\s*$", "", s)                         # ponctuation finale
    _check_balance(s)
    top = re.sub(r"\\begin\{([^}]*)\}.*?\\end\{\1\}", " ", s, flags=re.S)
    if "\\\\" in top or re.search(r"(?<!\\)&", top):
        raise SympyLatexError(
            "Plusieurs lignes ou un alignement (\\\\, &) : sélectionnez une seule "
            "équation ou expression.")
    s = _sympy_style_calls(s, ctx)
    s = _protect_brackets(s, ctx)
    s = _protect(s, ctx)
    return s


def _check_balance(s: str) -> None:
    """Le parseur peut ignorer silencieusement la fin d'une expression mal
    formée : on vérifie d'abord accolades et \\left/\\right."""
    t = s.replace(r"\{", "").replace(r"\}", "")
    depth = 0
    for c in t:
        depth += (c == "{") - (c == "}")
        if depth < 0:
            raise SympyLatexError("Accolade fermante « } » en trop.")
    if depth:
        raise SympyLatexError("Accolade fermante « } » manquante.")
    left = len(re.findall(r"\\left(?![A-Za-z])", s))
    right = len(re.findall(r"\\right(?![A-Za-z])", s))
    if left != right:
        raise SympyLatexError("\\left et \\right ne sont pas appariés.")


# --------------------------------------------------------------- SymPy
def _sympy():
    import sympy
    return sympy


def parse(text: str, ctx: Context):
    sp = _sympy()
    from sympy.parsing.latex import parse_latex
    from sympy.core.function import AppliedUndef

    src = preprocess(text, ctx)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            expr = parse_latex(src, backend="antlr")
    except ImportError as exc:
        raise SympyLatexError(
            "Le module antlr4 est manquant : conda env update -f environment.yml --prune") from exc
    except Exception as exc:  # LaTeXParsingError et erreurs internes
        first = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        raise SympyLatexError(f"SymPy n'a pas compris l'expression : {first}") from exc

    expr = _evaluate_arithmetic(expr)
    funcs = ctx.functions
    # Ce qui est dérivé (d/dt N(t)) est une fonction, même à un argument.
    for d in expr.atoms(sp.Derivative):
        if isinstance(d.expr, AppliedUndef):
            funcs.add(d.expr.func.__name__)

    def is_fake_call(e):
        return (isinstance(e, AppliedUndef) and len(e.args) == 1
                and e.func.__name__ not in funcs)

    # Appels à un argument non déclarés → produits ; boucle pour les imbrications.
    for _ in range(10):
        new = expr.replace(is_fake_call, lambda e: sp.Symbol(e.func.__name__) * e.args[0])
        if new == expr:
            break
        expr = new

    # Hors intégrale, « d x » n'est pas une différentielle : d·x.
    if not expr.has(sp.Integral):
        diffs = {sym: sp.Symbol("d") * sp.Symbol(sym.name[1:]) for sym in expr.free_symbols
                 if re.fullmatch(r"d([A-Za-z]|" + _GREEK + r")(_.+)?", sym.name)
                 and sym.name[1:] not in ctx.atoms.values()}
        if diffs:
            expr = expr.xreplace(diffs)

    repl = {}
    for sym in expr.free_symbols:
        if sym.name == "e":
            repl[sym] = sp.E
        elif ctx.positive:
            repl[sym] = sp.Symbol(sym.name, positive=True)
    if repl:
        expr = expr.xreplace(repl)
    # log(x, E) produit par \ln → log(x)
    expr = expr.replace(lambda e: isinstance(e, sp.log) and len(e.args) == 2 and e.args[1] == sp.E,
                        lambda e: sp.log(e.args[0]))
    return expr


def _evaluate_arithmetic(expr):
    """Le parseur rend des sommes et produits non évalués, imbriqués : on les
    reconstruit (sans calculer les ∑, ∫ ni dérivées écrites)."""
    sp = _sympy()
    if not getattr(expr, "args", ()):
        return expr
    args = [_evaluate_arithmetic(a) for a in expr.args]
    if isinstance(expr, (sp.Add, sp.Mul, sp.Pow)):
        return expr.func(*args)
    if isinstance(expr, sp.Equality):
        return sp.Eq(*args, evaluate=False)
    try:
        return expr.func(*args, evaluate=False)
    except TypeError:
        return expr.func(*args)


def _symbol_names(expr, ctx: Context) -> dict:
    names = {}
    back = ctx.atom_latex
    for sym in expr.free_symbols:
        if sym.name in back:
            names[sym] = back[sym.name]
    return names


def to_latex(expr, ctx: Context) -> str:
    sp = _sympy()
    if isinstance(expr, (list, tuple)):
        return r" \\ ".join(to_latex(e, ctx) for e in expr)
    return sp.latex(expr, symbol_names=_symbol_names(expr, ctx), ln_notation=True)


def describe(expr, ctx: Context) -> str:
    """Interprétation lisible (notation Python de SymPy, symboles d'origine)."""
    sp = _sympy()
    back = ctx.atom_latex
    repl = {s: sp.Symbol(back[s.name]) for s in expr.free_symbols if s.name in back}
    return sp.sstr(expr.xreplace(repl) if repl else expr)


def symbols_latex(expr, ctx: Context) -> list[str]:
    """Symboles libres, écrits en LaTeX, pour le choix de la variable."""
    sp = _sympy()
    back = ctx.atom_latex
    out = []
    for s in sorted(expr.free_symbols, key=lambda s: s.name):
        out.append(back.get(s.name, sp.latex(s)))
    return out


def _on_sides(expr, fn):
    sp = _sympy()
    if isinstance(expr, sp.Equality):
        return sp.Eq(fn(expr.lhs), fn(expr.rhs), evaluate=False)
    return fn(expr)


def substitute(expr, pairs, ctx: Context):
    """Remplacements simultanés, propagés à l'intérieur des moments ⟨…⟩ et
    des dérivées d⟨…⟩/dt. Échanger X ↔ Y donne bien YX (et non XX)."""
    sp = _sympy()
    mapping = dict(pairs)
    if not mapping:
        raise SympyLatexError("Ajoutez au moins un remplacement.")
    extra = {}
    new_moment_names = {}
    for sym in expr.free_symbols:
        inner = ctx.moments.get(sym.name)
        if inner is None or sym in mapping:
            continue
        new_inner = inner.subs(mapping, simultaneous=True)
        if new_inner == inner:
            continue
        canon = moment_latex(new_inner, ctx)
        if canon is None:  # ex. ⟨X + 1⟩ : moment non monôme, gardé en bloc
            canon = r"\langle " + sp.latex(new_inner, symbol_names=_symbol_names(new_inner, ctx)) + r" \rangle"
        name = ctx.atom(canon)[len(r"\mathit{"):-1]
        if moment_latex(new_inner, ctx) is not None:
            ctx.moments[name] = new_inner
        extra[sym] = ctx.symbol(name)
        new_moment_names[sym.name] = name
    for sym in expr.free_symbols:
        d = ctx.derivs.get(sym.name)
        if d is None or sym in mapping or d[1] not in new_moment_names:
            continue
        prefix, inner_name = d
        new_inner_name = new_moment_names[inner_name]
        latex = prefix + " " + ctx.atom_latex[new_inner_name]
        name = ctx.atom(latex)[len(r"\mathit{"):-1]
        ctx.derivs[name] = (prefix, new_inner_name)
        extra[sym] = ctx.symbol(name)
    mapping.update(extra)
    return _on_sides(expr, lambda e: e.subs(mapping, simultaneous=True))


def apply(expr, op: str, var=None, old=None, new=None):
    sp = _sympy()
    if op in NEEDS_VAR and var is None:
        raise SympyLatexError(f"Choisissez une variable pour « {OPERATIONS[op]} ».")
    if op == "simplify":
        return _on_sides(expr, sp.simplify)
    if op == "expand":
        return _on_sides(expr, sp.expand)
    if op == "factor":
        return _on_sides(expr, sp.factor)
    if op == "cancel":
        return _on_sides(expr, lambda e: sp.cancel(sp.together(e)))
    if op == "apart":
        return _on_sides(expr, lambda e: sp.apart(e, var))
    if op == "collect":
        return _on_sides(expr, lambda e: sp.collect(sp.expand(e), var))
    if op == "diff":
        return _on_sides(expr, lambda e: sp.diff(e, var))
    if op == "integrate":
        return _on_sides(expr, lambda e: sp.integrate(e, var))
    if op == "doit":
        return _on_sides(expr, lambda e: e.doit())
    if op == "solve":
        eq = expr if isinstance(expr, sp.Equality) else sp.Eq(expr, 0)
        sols = sp.solve(eq, var, dict=False)
        if not sols:
            raise SympyLatexError("Aucune solution trouvée.")
        return [sp.Eq(var, s, evaluate=False) for s in sols]
    raise SympyLatexError(f"Opération inconnue : {op}")


def _parse_functions(text: str) -> set[str]:
    return {f.strip().lstrip("\\") for f in re.split(r"[,\s;]+", text or "") if f.strip()}


def run_operation(text: str, op: str = "parse", var: str = "", old: str = "", new: str = "",
                  functions: str = "f, g, h", positive: bool = False,
                  sup_index: bool = True, subs: list | None = None) -> dict:
    """Point d'entrée « chaîne → chaîne », utilisable dans un sous-processus.

    subs : liste de couples [remplacer, par] (LaTeX), appliqués simultanément ;
    old/new : un seul couple (raccourci).
    Retourne {ok, latex, interpretation, result_interpretation, is_sum, symbols, error}.
    """
    ctx = Context(functions=_parse_functions(functions), positive=positive, sup_index=sup_index)
    try:
        expr = parse(text, ctx)
        result = {"ok": True, "interpretation": describe(expr, ctx),
                  "symbols": symbols_latex(expr, ctx), "latex": "", "error": "",
                  "result_interpretation": "", "is_sum": False}
        if op == "parse":
            return result
        sp = _sympy()
        if op == "subs":
            raw = [tuple(p) for p in (subs or [])]
            if old.strip() or new.strip():
                raw.append((old, new))
            pairs = []
            for k, (o, n) in enumerate(raw, 1):
                if not o.strip() and not n.strip():
                    continue
                if not o.strip() or not n.strip():
                    raise SympyLatexError(f"Remplacement n° {k} incomplet.")
                pairs.append((parse(o, ctx), parse(n, ctx)))
            out = substitute(expr, pairs, ctx)
        else:
            v = parse(var, ctx) if var.strip() else None
            if v is not None and not isinstance(v, sp.Symbol):
                raise SympyLatexError(f"« {var} » n'est pas une variable simple.")
            out = apply(expr, op, v)
        result["latex"] = to_latex(out, ctx)
        if not isinstance(out, list):
            result["result_interpretation"] = describe(out, ctx)
            result["is_sum"] = isinstance(out, sp.Add)
        return result
    except SympyLatexError as exc:
        return {"ok": False, "error": str(exc), "latex": "", "interpretation": "", "symbols": []}
    except Exception as exc:  # erreur interne de SymPy
        return {"ok": False, "error": f"Erreur SymPy ({type(exc).__name__}) : {exc}",
                "latex": "", "interpretation": "", "symbols": []}


def warm_up() -> bool:
    """Précharge SymPy et le parseur (appelé au démarrage du processus de calcul)."""
    run_operation("x + 1")
    return True
