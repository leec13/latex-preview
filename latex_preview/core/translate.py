"""Traduction LaTeX ⇄ Python selon un modèle (voir model.py).

* LaTeX → Python : une ligne de code par équation, avec les noms du modèle
  (n_A1, M_A1_A2, T_…, rmaxA, KA, r_A1…). Ce qui n'est pas dans le modèle est
  signalé, jamais deviné en silence.
* Python → LaTeX : une sortie de script (« dM_A1_A1/dt = -2*M_A1_A1*m + … »)
  redevient du LaTeX avec la vraie notation, prêt pour l'aperçu.

Fonctions « chaîne → dict », utilisables dans un sous-processus.
"""

from __future__ import annotations

import re

from .model import Model, ModelError, parse_model
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


def _sanitize(latex: str) -> str:
    """Identifiant Python lisible pour un symbole hors modèle (signalé)."""
    s = re.sub(r"\\(?:mathrm|mathit|operatorname|text)\{([^{}]*)\}", r"\1", latex)
    s = re.sub(r"\\(max|min|langle|rangle|left|right)", r"\1", s)
    s = re.sub(r"\\([A-Za-z]+)", r"\1", s)
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")
    if not s or s[0].isdigit():
        s = "v_" + s
    return s


def _model(model_text: str) -> Model:
    return parse_model(model_text)


# ===================================================================== LaTeX → Python
def _python_names(expr, ctx: Context, model: Model, unknown: list[str]) -> dict:
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
                unknown.append(ctx.latex_of(target))
                name = _sanitize(ctx.latex_of(target))
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
        m = re.fullmatch(r"(.+?)\^\{?\s*(\d+)\s*\}?", latex)
        if m:
            base = model.var_of_latex(m.group(1))
            base = model.variable_format.format(code=base) if base else model.param_of_latex(m.group(1))
            if base:
                repl[sym] = sp.Symbol(base) ** int(m.group(2))
                continue
        repl[sym] = sp.Symbol(_sanitize(latex))
        unknown.append(latex)
    return repl


def _rename_functions(expr, ctx: Context, model: Model, unknown: list[str]):
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
            py = _sanitize(latex)
            unknown.append(latex + " (fonction)")
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
    """Retourne {ok, python, warnings, error, count}."""
    import sympy as sp
    from sympy.core.function import AppliedUndef

    try:
        model = _model(model_text)
        defs = _definitions(model) if use_definitions else {}
        lines, warnings = [], []
        pieces = split_equations(text)
        if not pieces:
            return {"ok": True, "python": "", "warnings": [], "error": "", "count": 0}
        for k, piece in enumerate(pieces, 1):
            ctx = Context(sup_index=True, function_latex=model.function_latex_keys)
            try:
                expr = parse(piece, ctx)
            except SympyLatexError as exc:
                raise SympyLatexError(f"Équation {k} : {exc}" if len(pieces) > 1 else str(exc)) from exc
            unknown: list[str] = []
            expr = expr.xreplace(_python_names(expr, ctx, model, unknown))
            expr = _rename_functions(expr, ctx, model, unknown)
            # d/dt N(t) écrit avec une fonction : dN_dt
            expr = expr.replace(
                lambda e: (isinstance(e, sp.Derivative) and isinstance(e.expr, AppliedUndef)
                           and e.expr.args == e.variables),
                lambda e: sp.Symbol(model.derivative_name(e.expr.func.__name__)))
            if defs:
                expr = expr.xreplace(defs)
            for u in unknown:
                msg = f"« {u} » n'est pas dans le modèle"
                if msg not in warnings:
                    warnings.append(msg)
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
        return {"ok": True, "python": "\n".join(lines), "warnings": list(dict.fromkeys(warnings)),
                "error": "", "count": len(lines)}
    except (SympyLatexError, ModelError) as exc:
        return {"ok": False, "python": "", "warnings": [], "error": str(exc), "count": 0}
    except Exception as exc:
        return {"ok": False, "python": "", "warnings": [],
                "error": f"Erreur ({type(exc).__name__}) : {exc}", "count": 0}


# ===================================================================== Python → LaTeX
def _split_assignment(line: str) -> tuple[str | None, str]:
    m = re.match(r"^\s*([^=<>!]+?)\s*=(?!=)\s*(.+)$", line)
    if m:
        return m.group(1), m.group(2)
    return None, line


def _latex_name(name: str, model: Model) -> tuple[str, bool]:
    """(LaTeX, connu ?) pour un nom Python."""
    codes = model.parse_moment_name(name)
    if codes is not None:
        return model.moment_latex(codes), True
    if name in model.param_latex:
        return model.param_latex[name], True
    if name in model.var_python:
        return model.var_latex[model.var_python[name]], True
    if name in model.function_latex:
        return model.function_latex[name], True
    return "", False


def _unknown_latex(name: str) -> str:
    """Nom hors modèle : \\mathrm{…} s'il a plusieurs lettres (relu comme un seul nom)."""
    import sympy as sp
    plain = sp.latex(sp.Symbol(name))
    if len(name) > 1 and not plain.startswith("\\"):
        return r"\mathrm{" + name.replace("_", r"\_") + "}"
    return plain


def _printer(names: dict, model: Model, warnings: list[str]):
    """LaTeX avec les noms du modèle, y compris pour les fonctions R1(z) → R_1\\left(z\\right)."""
    from sympy.core.function import AppliedUndef
    from sympy.printing.latex import LatexPrinter

    class Printer(LatexPrinter):
        def _print_Function(self, expr, exp=None):
            if isinstance(expr, AppliedUndef):
                name = expr.func.__name__
                head = model.function_latex.get(name) or model.param_latex.get(name)
                if head is None:
                    msg = f"« {name} » (fonction) n'est pas dans le modèle"
                    if msg not in warnings:
                        warnings.append(msg)
                    head = _unknown_latex(name)
                args = ", ".join(self._print(a) for a in expr.args)
                if name in model.function_latex:
                    out = head + r"\left(" + args + r"\right)"
                else:  # hors modèle : parenthèses simples = appel (\left( = produit)
                    out = head + "(" + args + ")"
                return out if exp is None else r"\left(" + out + r"\right)^{" + exp + "}"
            return super()._print_Function(expr, exp)

    return Printer({"symbol_names": names})


def python_to_latex(text: str, model_text: str, collect: bool = False) -> dict:
    """Retourne {ok, latex, warnings, error, count}."""
    import sympy as sp
    from sympy.parsing.sympy_parser import parse_expr

    try:
        model = _model(model_text)
        out, warnings = [], []
        lines = [l for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
        for k, line in enumerate(lines, 1):
            lhs_txt, rhs_txt = _split_assignment(line.replace("^", "**"))
            ids = set(re.findall(r"[A-Za-z_]\w*", rhs_txt)) - _SAFE_FUNCS
            calls = set(re.findall(r"([A-Za-z_]\w*)\s*\(", rhs_txt)) - _SAFE_FUNCS
            local = {i: (sp.Function(i) if i in calls else sp.Symbol(i)) for i in ids}
            try:
                rhs = parse_expr(rhs_txt, local_dict=local, evaluate=True)
            except Exception as exc:
                raise ModelError(f"Ligne {k} illisible pour Python : {exc}") from exc

            names = {}
            moments = []
            for sym in rhs.free_symbols:
                latex, known = _latex_name(sym.name, model)
                if not known:
                    msg = f"« {sym.name} » n'est pas dans le modèle"
                    if msg not in warnings:
                        warnings.append(msg)
                    # Nom de plusieurs lettres : \mathrm{…} pour qu'il ne soit pas
                    # relu comme un produit de lettres.
                    names[sym] = _unknown_latex(sym.name)
                    continue
                names[sym] = latex
                if model.parse_moment_name(sym.name):
                    moments.append(sym)
            if collect and moments:
                order = sorted(moments, key=lambda s: (len(model.parse_moment_name(s.name)),
                                                       [model.var_order[c] for c in model.parse_moment_name(s.name)]))
                rhs = sp.collect(sp.expand(rhs), order)
            body = _printer(names, model, warnings).doprint(rhs)

            if lhs_txt is not None:
                target = model.parse_derivative_name(lhs_txt)
                if target is not None:
                    tl, known = _latex_name(target, model)
                    lhs_latex = r"\frac{d}{dt} " + (tl if known else _unknown_latex(target))
                    if not known:
                        warnings.append(f"« {target} » n'est pas dans le modèle")
                else:
                    tl, known = _latex_name(lhs_txt.strip(), model)
                    lhs_latex = tl if known else _unknown_latex(lhs_txt.strip())
                body = f"{lhs_latex} = {body}"
            out.append(body)
        if len(out) == 1:
            latex = out[0]
        else:  # plusieurs équations : un bloc par équation (coupure automatique)
            latex = "\n\n".join(f"\\[\n{b}\n\\]" for b in out)
        return {"ok": True, "latex": latex, "warnings": list(dict.fromkeys(warnings)),
                "error": "", "count": len(out)}
    except ModelError as exc:
        return {"ok": False, "latex": "", "warnings": [], "error": str(exc), "count": 0}
    except Exception as exc:
        return {"ok": False, "latex": "", "warnings": [],
                "error": f"Erreur ({type(exc).__name__}) : {exc}", "count": 0}


def warm_up() -> bool:
    from .model import DEFAULT_MODEL
    latex_to_python(r"\langle N_{A}^{x_1} \rangle", DEFAULT_MODEL)
    return True
