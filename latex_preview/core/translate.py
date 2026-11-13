"""Traduction LaTeX → Python selon un modèle (voir model.py).

Une ligne de code par équation, avec les noms du modèle (n_A1, M_A1_A2, T_…,
rmaxA, KA, r_A1…). Les symboles hors modèle reçoivent un nom automatique
(N_{1} → N1), indiqué à l'utilisateur.

Fonctions « chaîne → dict », utilisables dans un sous-processus.
"""

from __future__ import annotations

import re

from .model import Model, ModelError, normalize_latex, parse_model
from .sympy_ops import Context, SympyLatexError, parse

_ENVS = ("equation", "align", "gather", "multline", "flalign", "alignat", "eqnarray",
         "aligned", "gathered", "split", "dmath", "dgroup", "displaymath")
_ENV_RE = re.compile(r"\\(begin|end)\{(?:" + "|".join(_ENVS) + r")\*?\}(\{[^}]*\})?")
_FENCE_RE = re.compile(r"^\s*```[A-Za-z]*\s*$", re.M)
_SAFE_FUNCS = {"exp", "log", "ln", "sqrt", "sin", "cos", "tan", "Abs", "Rational",
               "Integer", "Float", "pi", "E"}


# ===================================================================== utilitaires
def split_equations(text: str) -> list[str]:
    """Découpe un bloc LaTeX en équations (environnements, \\\\, lignes vides, $$)."""
    t = _FENCE_RE.sub("", text)
    t = re.sub(r"(?<!\\)%.*$", "", t, flags=re.M)
    t = re.sub(r"\\(label|tag)\{[^}]*\}|\\nonumber|\\notag", "", t)
    t = re.sub(r"\\(approx|simeq)(?![A-Za-z])", "=", t)
    t = _ENV_RE.sub("\n\n", t)
    t = re.sub(r"\$\$|\\\[|\\\]", "\n\n", t)
    t = re.sub(r"(?<!\\)&", " ", t)
    pieces = []
    for block in re.split(r"\n\s*\n", t):
        for part in re.split(r"\\\\(?:\[[^\]]*\])?", block):
            part = part.strip().rstrip(".,;").strip()
            if not part:
                continue
            # Une ligne de continuation (sans « = ») prolonge l'équation précédente.
            if pieces and "=" not in part and "=" in pieces[-1]:
                pieces[-1] += " " + part
            else:
                pieces.append(part)
    return pieces


def auto_name(latex: str) -> str:
    """Nom Python automatique pour un symbole hors modèle (validé avec l'utilisateur) :
    N_{1} → N1, r_{1} → r1, \\delta → delta, x_{i,j} → xij, \\theta_{12} → theta12."""
    s = re.sub(r"\\(?:mathrm|mathit|operatorname|text|mathbf|bm|boldsymbol)\{([^{}]*)\}", r"\1", latex)
    s = re.sub(r"\^\{?\s*(\*|\\star|\\ast)\s*\}?", "star", s)
    s = s.replace("'", "prime")
    s = re.sub(r"\\(left|right)(?![A-Za-z])", "", s)
    s = re.sub(r"\\([A-Za-z]+)", r"\1", s)
    s = re.sub(r"[^A-Za-z0-9]+", "", s)
    if not s or s[0].isdigit():
        s = "v" + s
    return s


class AutoNamer:
    """Attribue les noms automatiques, sans collision avec le modèle ni entre eux."""

    def __init__(self, model: Model) -> None:
        self.by_latex: dict[str, str] = {}
        self.used = set(model.param_latex) | set(model.function_latex) | set(model.var_python)
        self.report: list[str] = []

    def name(self, latex: str, kind: str = "") -> str:
        key = latex.strip()
        if key in self.by_latex:
            return self.by_latex[key]
        base = auto_name(key)
        name, k = base, 2
        while name in self.used:
            name, k = f"{base}_{k}", k + 1
        self.used.add(name)
        self.by_latex[key] = name
        self.report.append(f"{key} → {name}" + (f" ({kind})" if kind else ""))
        return name


def _model(model_text: str) -> Model:
    return parse_model(model_text)


# ===================================================================== LaTeX → Python
def _python_names(expr, ctx: Context, model: Model, namer: AutoNamer) -> dict:
    """Symboles de l'expression (opaques ou non) → Symbol(nom Python du modèle)."""
    import sympy as sp

    def symbol_name(sym) -> str | None:
        inner = ctx.moments.get(sym.name)
        if inner is not None:
            codes = []
            for base, exp in inner.as_powers_dict().items():
                code = model.var_of_latex(ctx.latex_of(base))
                if code is None:
                    return None
                codes += [code] * int(exp)
            return model.moment_name(codes)
        d = ctx.derivs.get(sym.name)
        if d is not None:
            target = ctx.symbol(d[1])
            name = symbol_name(target)
            if name is None:  # dérivée d'un symbole hors modèle : dX_dt quand même
                name = namer.name(ctx.latex_of(target))
            return model.derivative_name(name)
        latex = ctx.latex_of(sym)
        code = model.var_of_latex(latex)
        if code is not None:
            return model.variable_format.format(code=code)
        return model.param_of_latex(latex)

    repl = {}
    for sym in expr.free_symbols:
        name = symbol_name(sym)
        if name is not None:
            repl[sym] = sp.Symbol(name)
            continue
        latex = ctx.latex_of(sym)
        # x_1^{2} hors modèle mais x_1 dans le modèle : c'est un carré, pas un nom.
        m = re.fullmatch(r"(.+?)\^\{?\s*(\d+)\s*\}?", normalize_latex(latex))
        if m:
            base = model.var_of_latex(m.group(1))
            base = model.variable_format.format(code=base) if base else model.param_of_latex(m.group(1))
            if base:
                repl[sym] = sp.Symbol(base) ** int(m.group(2))
                continue
        repl[sym] = sp.Symbol(namer.name(latex))
    return repl


def _rename_functions(expr, ctx: Context, model: Model, namer: AutoNamer):
    """R_{1}(z) → R1(z) selon la section [fonctions] du modèle."""
    import sympy as sp
    from sympy.core.function import AppliedUndef

    names = {}
    for f in expr.atoms(AppliedUndef):
        name = f.func.__name__
        if name in names:
            continue
        head = ctx.head_atom(name)
        latex = ctx.atom_latex.get(head or name) or ctx.latex_of(sp.Symbol(name))
        py = model.function_of_latex(latex)
        if py is None:
            py = namer.name(latex, "fonction")
        names[name] = py
    if not names:
        return expr
    return expr.replace(lambda e: isinstance(e, AppliedUndef) and e.func.__name__ in names,
                        lambda e: sp.Function(names[e.func.__name__])(*e.args))


def _definitions(model: Model) -> dict:
    import sympy as sp
    from sympy.parsing.sympy_parser import parse_expr

    out = {}
    for name, code in model.definitions.items():
        ids = set(re.findall(r"[A-Za-z_]\w*", code)) - _SAFE_FUNCS
        local = {i: sp.Symbol(i) for i in ids}
        try:
            out[sp.Symbol(name)] = parse_expr(code, local_dict=local)
        except Exception as exc:
            raise ModelError(f"[definitions] « {name} » illisible : {exc}") from exc
    return out


def latex_to_python(text: str, model_text: str, expand: bool = False,
                    use_definitions: bool = False) -> dict:
    """Retourne {ok, python, auto_names, warnings, error, count}."""
    import sympy as sp
    from sympy.core.function import AppliedUndef

    try:
        model = _model(model_text)
        defs = _definitions(model) if use_definitions else {}
        lines, warnings = [], []
        namer = AutoNamer(model)
        pieces = split_equations(text)
        if not pieces:
            return {"ok": True, "python": "", "auto_names": [], "warnings": [], "error": "", "count": 0}
        for k, piece in enumerate(pieces, 1):
            ctx = Context(sup_index=True, function_latex=model.function_latex_keys,
                          declared=model.declared_latex)
            try:
                expr = parse(piece, ctx)
            except SympyLatexError as exc:
                raise SympyLatexError(f"Équation {k} : {exc}" if len(pieces) > 1 else str(exc)) from exc
            expr = expr.xreplace(_python_names(expr, ctx, model, namer))
            expr = _rename_functions(expr, ctx, model, namer)
            # d/dt N(t) écrit avec une fonction : dN_dt
            expr = expr.replace(
                lambda e: (isinstance(e, sp.Derivative) and isinstance(e.expr, AppliedUndef)
                           and e.expr.args == e.variables),
                lambda e: sp.Symbol(model.derivative_name(e.expr.func.__name__)))
            if defs:
                expr = expr.xreplace(defs)
            if isinstance(expr, sp.Equality):
                lhs, rhs = expr.lhs, expr.rhs
                if expand:
                    rhs = sp.expand(rhs)
                left = sp.sstr(lhs)
                if not isinstance(lhs, sp.Symbol):
                    warnings.append(f"équation {k} : le membre de gauche n'est pas un nom simple")
                lines.append(f"{left} = {sp.sstr(rhs)}")
            else:
                lines.append(sp.sstr(sp.expand(expr) if expand else expr))
        return {"ok": True, "python": "\n".join(lines), "auto_names": namer.report,
                "warnings": list(dict.fromkeys(warnings)),
                "error": "", "count": len(lines)}
    except (SympyLatexError, ModelError) as exc:
        return {"ok": False, "python": "", "auto_names": [], "warnings": [], "error": str(exc), "count": 0}
    except Exception as exc:
        return {"ok": False, "python": "", "auto_names": [], "warnings": [],
                "error": f"Erreur ({type(exc).__name__}) : {exc}", "count": 0}


def warm_up() -> bool:
    from .model import DEFAULT_MODEL
    latex_to_python(r"\langle N_{A}^{x_1} \rangle", DEFAULT_MODEL)
    return True
