"""Modèle : correspondance entre noms Python (scripts SymPy) et écriture LaTeX.

Le modèle est un petit fichier texte (.ini) lisible et partageable :

    [variables]        code = LaTeX | autre écriture LaTeX …
    [moments]          préfixes par ordre, séparateur, format des dérivées
    [parametres]       nom Python = LaTeX | autre écriture …
    [definitions]      nom = expression Python (remplacements facultatifs)

Les noms des moments sont construits comme dans moment_closure.py :
préfixe selon l'ordre (n, M, T, Q…) puis les codes des variables, triés dans
l'ordre de déclaration et séparés par « _ » : ⟨N_A^{x_1} N_B^{x_2}⟩ → M_A1_B2.
"""

from __future__ import annotations

import configparser
import re
from dataclasses import dataclass, field

DEFAULT_MODEL = r"""# Modèle : une population, deux niches (A, B), deux phénotypes (x1, x2).
# Fichier partageable : copiez-le et adaptez-le pour un autre modèle.
# Plusieurs écritures LaTeX sont possibles, séparées par « | » :
# la première sert pour l'affichage, les autres sont aussi reconnues.

[variables]
# code = écriture LaTeX de la variable d'état (ordre = ordre de tri des moments)
A1 = N_{A}^{x_1} | N_{A}^{1} | N_{A1}
A2 = N_{A}^{x_2} | N_{A}^{2} | N_{A2}
B1 = N_{B}^{x_1} | N_{B}^{1} | N_{B1}
B2 = N_{B}^{x_2} | N_{B}^{2} | N_{B2}

[moments]
# Nom Python d'un moment : préfixe de l'ordre (1, 2, 3, 4…) + codes triés.
# Exemples : <N_A^{x_1}> -> n_A1,  <N_A^{x_1} N_B^{x_2}> -> M_A1_B2.
prefixes = n, M, T, Q
separateur = _
# Nom de la dérivée d<…>/dt d'un moment ou d'une variable ({nom} = son nom Python)
derivee = d{nom}_dt
# Nom Python d'une variable d'état seule (hors moyenne)
variable = N{code}

[parametres]
m = m
s = s
x1 = x_1 | x_{1}
x2 = x_2 | x_{2}
thA = \theta_A | \theta_{A}
thB = \theta_B | \theta_{B}
rmaxA = r_{\max,A} | r_{\max A} | r_{max,A}
rmaxB = r_{\max,B} | r_{\max B} | r_{max,B}
KA = K_A | K_{A}
KB = K_B | K_{B}
r_A1 = r_{A}^{x_1} | r_{A}^{1}
r_A2 = r_{A}^{x_2} | r_{A}^{2}
r_B1 = r_{B}^{x_1} | r_{B}^{1}
r_B2 = r_{B}^{x_2} | r_{B}^{2}
t = t

[fonctions]
# Fonctions appelées avec des arguments, ex. R1(z) : nom Python = LaTeX
# R1 = R_1

[definitions]
# Remplacements facultatifs (case « Remplacer par les définitions »), en Python.
r_A1 = rmaxA - s*(x1 - thA)**2
r_A2 = rmaxA - s*(x2 - thA)**2
r_B1 = rmaxB - s*(x1 - thB)**2
r_B2 = rmaxB - s*(x2 - thB)**2
"""


class ModelError(Exception):
    pass


def normalize_latex(s: str) -> str:
    """Forme de comparaison : sans espaces, accolades inutiles retirées.

    N_{A}^{x_{1}}, N_A^{x_1} et N_{A}^{x_1} donnent la même clé."""
    s = re.sub(r"\\left\s*([(\[|.])|\\right\s*([)\]|.])", lambda m: m.group(1) or m.group(2), s)
    s = re.sub(r"\\[,;:! ]", "", s)
    s = re.sub(r"\s+", "", s)
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"([_^])\{(\\[A-Za-z]+|[A-Za-z0-9])\}", r"\1\2", s)
    return s


@dataclass
class Model:
    variables: list[tuple[str, list[str]]] = field(default_factory=list)
    parameters: list[tuple[str, list[str]]] = field(default_factory=list)
    functions: list[tuple[str, list[str]]] = field(default_factory=list)
    definitions: dict[str, str] = field(default_factory=dict)
    prefixes: list[str] = field(default_factory=lambda: ["n", "M", "T", "Q"])
    separator: str = "_"
    derivative: str = "d{nom}_dt"
    variable_format: str = "N{code}"

    # ------------------------------------------------------------ index
    def __post_init__(self) -> None:
        self._index()

    def _index(self) -> None:
        self.var_order = {code: k for k, (code, _) in enumerate(self.variables)}
        self.var_latex = {code: lat[0] for code, lat in self.variables}
        self.param_latex = {name: lat[0] for name, lat in self.parameters}
        self._latex_to_var = {}
        for code, lats in self.variables:
            for lat in lats:
                self._latex_to_var.setdefault(normalize_latex(lat), code)
        self._latex_to_param = {}
        for name, lats in self.parameters:
            for lat in lats:
                self._latex_to_param.setdefault(normalize_latex(lat), name)
        self.var_python = {self.variable_format.format(code=c): c for c, _ in self.variables}
        self.function_latex = {name: lat[0] for name, lat in self.functions}
        self._latex_to_function = {}
        for name, lats in self.functions:
            for lat in lats:
                self._latex_to_function.setdefault(normalize_latex(lat), name)

    # ------------------------------------------------------------ requêtes
    def var_of_latex(self, latex: str) -> str | None:
        return self._latex_to_var.get(normalize_latex(latex))

    def param_of_latex(self, latex: str) -> str | None:
        return self._latex_to_param.get(normalize_latex(latex))

    def function_of_latex(self, latex: str) -> str | None:
        return self._latex_to_function.get(normalize_latex(latex))

    @property
    def function_latex_keys(self) -> set[str]:
        return set(self._latex_to_function)

    def prefix(self, order: int) -> str:
        return self.prefixes[order - 1] if order <= len(self.prefixes) else f"X{order}"

    def moment_name(self, codes: list[str]) -> str:
        codes = sorted(codes, key=lambda c: self.var_order[c])
        return self.prefix(len(codes)) + self.separator + self.separator.join(codes)

    def parse_moment_name(self, name: str) -> list[str] | None:
        """« M_A1_B2 » → ['A1', 'B2'] ; None si ce n'est pas un nom de moment."""
        head, sep, rest = name.partition(self.separator)
        if not sep or not rest:
            return None
        codes = rest.split(self.separator) if self.separator else [rest]
        if any(c not in self.var_order for c in codes):
            return None
        if head != self.prefix(len(codes)):
            return None
        return codes

    def derivative_name(self, name: str) -> str:
        return self.derivative.format(nom=name)

    def parse_derivative_name(self, text: str) -> str | None:
        """« dM_A1_A2_dt », « dM_A1_A2/dt », « d(M_A1_A2)/dt » → « M_A1_A2 »."""
        text = text.replace(" ", "")
        pats = [re.escape(self.derivative).replace(r"\{nom\}", r"(?P<n>\w+?)"),
                r"d\((?P<n>\w+)\)/dt", r"d(?P<n>\w+)/dt"]
        for p in pats:
            m = re.fullmatch(p, text)
            if m:
                return m.group("n")
        return None

    def moment_latex(self, codes: list[str]) -> str:
        """⟨…⟩ canonique : variables dans l'ordre déclaré, répétitions en (X)^{k}."""
        counts: dict[str, int] = {}
        for c in sorted(codes, key=lambda c: self.var_order[c]):
            counts[c] = counts.get(c, 0) + 1
        parts = []
        for c, k in counts.items():
            lat = self.var_latex[c]
            if k == 1:
                parts.append(lat)
            else:
                needs = "_" in lat or "^" in lat or " " in lat
                parts.append(f"({lat})^{{{k}}}" if needs else f"{lat}^{{{k}}}")
        return r"\langle " + " ".join(parts) + r" \rangle"


def parse_model(text: str) -> Model:
    cp = configparser.ConfigParser(interpolation=None, delimiters=("=",),
                                   comment_prefixes=("#",), inline_comment_prefixes=None,
                                   strict=False, empty_lines_in_values=False)
    cp.optionxform = str  # garder la casse des noms (KA ≠ ka)
    try:
        cp.read_string(text)
    except configparser.Error as exc:
        raise ModelError(f"Fichier de modèle illisible : {exc}") from exc

    def entries(section):
        if not cp.has_section(section):
            return []
        out = []
        for name, value in cp.items(section):
            lats = [v.strip() for v in value.split("|") if v.strip()]
            if not lats:
                raise ModelError(f"[{section}] « {name} » n'a pas d'écriture LaTeX.")
            out.append((name.strip(), lats))
        return out

    variables = entries("variables")
    if not variables:
        raise ModelError("La section [variables] est vide.")
    model = Model(variables=variables, parameters=entries("parametres"),
                  functions=entries("fonctions"))
    if cp.has_section("moments"):
        sec = cp["moments"]
        if "prefixes" in sec:
            model.prefixes = [p.strip() for p in sec["prefixes"].split(",") if p.strip()]
        model.separator = sec.get("separateur", model.separator).strip() or "_"
        model.derivative = sec.get("derivee", model.derivative).strip()
        model.variable_format = sec.get("variable", model.variable_format).strip()
    if cp.has_section("definitions"):
        model.definitions = {k.strip(): v.strip() for k, v in cp.items("definitions")}
    model._index()
    return model
