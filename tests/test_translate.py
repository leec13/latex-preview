"""Tests de la traduction LaTeX ⇄ Python (python -m pytest tests)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import sympy as sp
from latex_preview.core.model import DEFAULT_MODEL as MOD, parse_model, normalize_latex
from latex_preview.core.translate import latex_to_python as L2P, python_to_latex as P2L, split_equations

# Sortie de « python moment_closure.py --print-eqs 2 » (fil « Closure order 3 equations »)
SCRIPT_M_A1_A1 = ("dM_A1_A1/dt = -2*M_A1_A1*m + 2*M_A1_A1*rmaxA - 2*M_A1_A1*s*thA**2 + 4*M_A1_A1*s*thA*x1 "
                  "- 2*M_A1_A1*s*x1**2 + 2*M_A1_B1*m + m*n_A1 + m*n_B1 + n_A1*rmaxA + n_A1*s*thA**2 "
                  "- 2*n_A1*s*thA*x1 + n_A1*s*x1**2 - 6*M_A1_A1*n_A1/KA - 2*M_A1_A1*n_A2/KA + M_A1_A1/KA "
                  "- 4*M_A1_A2*n_A1/KA + M_A1_A2/KA + 4*n_A1**3/KA + 4*n_A1**2*n_A2/KA")
MOMENT = (pathlib.Path(__file__).parent / "moment_ordre2.tex").read_text()


def ok(fn, *a, **k):
    r = fn(*a, **k)
    assert r["ok"], r["error"]
    return r


def rhs(py):
    return sp.sympify(py.split("=", 1)[1])


def test_model_names():
    m = parse_model(MOD)
    assert m.moment_name(["B2", "A1"]) == "M_A1_B2"
    assert m.moment_name(["A2", "A1", "A1"]) == "T_A1_A1_A2"
    assert m.moment_name(["A1"] * 4) == "Q_A1_A1_A1_A1"
    assert m.parse_moment_name("T_A1_A2_B1") == ["A1", "A2", "B1"]
    assert m.parse_moment_name("M_A1") is None            # mauvais ordre pour le préfixe
    assert m.moment_latex(["A2", "A1", "A1"]) == r"\langle (N_{A}^{x_1})^{2} N_{A}^{x_2} \rangle"
    assert m.parse_derivative_name("dM_A1_A2/dt") == "M_A1_A2"
    assert m.parse_derivative_name("dM_A1_A2_dt") == "M_A1_A2"
    assert normalize_latex("N_{A}^{x_{1}}") == normalize_latex("N_A^{x_1}")


def test_script_output_round_trip():
    lat = ok(P2L, SCRIPT_M_A1_A1, MOD)
    assert lat["warnings"] == []
    assert lat["latex"].startswith(r"\frac{d}{dt} \langle (N_{A}^{x_1})^{2} \rangle = ")
    back = ok(L2P, lat["latex"], MOD)
    assert back["warnings"] == []
    assert back["python"].startswith("dM_A1_A1_dt = ")
    assert sp.simplify(rhs(back["python"]) - rhs(SCRIPT_M_A1_A1)) == 0


def test_handwritten_equation_old_notation():
    """Équation d'hier, écrite avec N_{A}^{1} et r_{A}^{1} (alias du modèle)."""
    r = ok(L2P, MOMENT, MOD)
    assert r["warnings"] == []
    assert r["python"].startswith("dM_A2_A2_dt = ")
    for name in ("M_A2_A2", "M_A1_A2", "M_A2_B1", "n_B1", "r_A1", "rmaxA", "KA"):
        assert name in r["python"], name


def test_equivalent_writings_same_name():
    a = ok(L2P, r"\langle N_{A}^{x_2} N_{A}^{x_1} \rangle", MOD)["python"]
    b = ok(L2P, r"\langle N_A^{x_1} N_A^{x_2} \rangle", MOD)["python"]
    c = ok(L2P, r"\langle N_{A}^{x_1} N_{A}^{x_1} N_{A}^{x_2}\rangle", MOD)["python"]
    assert a == b == "M_A1_A2" and c == "T_A1_A1_A2"


def test_system_and_unknowns():
    eqs = r"""\begin{align}
\frac{d}{dt}\langle N_{A}^{x_1}\rangle &= \langle N_{A}^{x_1}\rangle\left(r_{A}^{x_1}
   - \frac{\langle N_{A}^{x_1}\rangle + \langle N_{A}^{x_2}\rangle}{K_A}\right) \\
 &\quad - m\left(\langle N_{A}^{x_1}\rangle - \langle N_{B}^{x_1}\rangle\right) \\
\frac{d\langle N_{A}^{x_2} N_{A}^{x_1}\rangle}{dt} &= - \frac{2}{K_A}\langle (N_{A}^{x_1})^2 N_{A}^{x_2}\rangle + z
\end{align}"""
    assert len(split_equations(eqs)) == 2
    r = ok(L2P, eqs, MOD)
    lines = r["python"].splitlines()
    assert lines[0] == "dn_A1_dt = -m*(n_A1 - n_B1) + n_A1*(r_A1 - (n_A1 + n_A2)/KA)"
    assert lines[1] == "dM_A1_A2_dt = z - 2*T_A1_A1_A2/KA"
    assert r["warnings"] == ["« z » n'est pas dans le modèle"]


def test_definitions_and_ode():
    r = ok(L2P, r"\frac{d}{dt} N_{A}^{x_1} = N_{A}^{x_1} r_{A}^{x_1}", MOD, use_definitions=True)
    assert r["python"] == "dNA1_dt = NA1*(rmaxA - s*(-thA + x1)**2)"


def test_python_system_to_latex_blocks():
    r = ok(P2L, "dn_A1/dt = n_A1*r_A1 - m*(n_A1 - n_B1)\ndn_B1/dt = n_B1*r_B1", MOD)
    assert r["count"] == 2 and r["latex"].count(r"\[") == 2
    assert "\\langle N_{B}^{x_1} \\rangle" in r["latex"]
    assert "« foo » n'est pas dans le modèle" in ok(P2L, "foo + m", MOD)["warnings"]


def test_unknown_names_round_trip():
    lat = ok(P2L, "dn_A1/dt = zz*n_A1 + foo_bar", MOD)["latex"]
    assert r"\mathrm{zz}" in lat
    back = ok(L2P, lat, MOD)
    assert back["python"] == "dn_A1_dt = foo_bar + n_A1*zz"
    assert sorted(back["warnings"]) == sorted(["« \\mathrm{zz} » n'est pas dans le modèle",
                                               "« \\mathrm{foo\\_bar} » n'est pas dans le modèle"])


# --- fonctions (R1(z_star1)) et notation N11 --------------------------------
LINE_N11 = "dN11_dt = N11 * (R1(z_star1) - ((N11+N12)/K1)) - delta * N11 + delta * N21"
EXTRA = """
N11 = N_{11}
N12 = N_{12}
N21 = N_{21}
K1 = K_1
delta = \\delta
z_star1 = z_1^*
"""
MOD_N11 = MOD.replace("t = t\n", "t = t\n" + EXTRA).replace("# R1 = R_1", "R1 = R_1")


def same(py_a, py_b):
    loc = {"R1": sp.Function("R1")}
    return sp.simplify(sp.sympify(py_a.split("=", 1)[1], locals=loc)
                       - sp.sympify(py_b.split("=", 1)[1], locals=loc)) == 0


def test_function_call_round_trip_unknown():
    lat = ok(P2L, LINE_N11, MOD)            # rien de déclaré : signalé mais traduit
    assert r"\mathrm{R1}(\mathrm{z\_star1})" in lat["latex"]
    assert "« R1 » (fonction) n'est pas dans le modèle" in lat["warnings"]
    back = ok(L2P, lat["latex"], MOD)
    assert back["python"].startswith("dN11_dt = ") and same(back["python"], LINE_N11)


def test_function_call_round_trip_declared():
    lat = ok(P2L, LINE_N11, MOD_N11)
    assert lat["warnings"] == []
    assert lat["latex"].startswith(r"\frac{d}{dt} N_{11} = ")
    assert r"R_1\left(z_1^*\right)" in lat["latex"]
    back = ok(L2P, lat["latex"], MOD_N11)
    assert back["warnings"] == [] and same(back["python"], LINE_N11)


def test_product_vs_call():
    # \mathrm{X}\left(…\right) = produit ; \mathrm{X}(…) = appel ; variable du modèle = produit
    assert ok(L2P, r"\mathrm{N11}\left(a + b\right)", MOD)["python"] == "N11*(a + b)"
    assert ok(L2P, r"\mathrm{R1}(z)", MOD)["python"] == "R1(z)"
    assert ok(L2P, r"N_{A}^{x_1}\left(r_{A}^{x_1} - 1\right)", MOD)["python"] == "NA1*(r_A1 - 1)"
    assert ok(L2P, r"\frac{d}{dt} N(t) = a N(t)", MOD)["python"] == "dN_dt = a*N(t)"


def test_partial_read_is_reported():
    r = L2P(r"\frac{d}{dt} \bad{N}_{11} = a", MOD)
    assert r["ok"] is False or "=" in r["python"]
