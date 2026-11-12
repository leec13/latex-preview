"""Tests de la traduction LaTeX → Python (python -m pytest tests).

Les cas « VALIDÉ n° k » reprennent les exemples validés avec l'utilisateur
le 12/11/2026 : ce sont les comportements attendus, pas des choix internes.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import sympy as sp
from latex_preview.core.model import DEFAULT_MODEL as MOD, parse_model, normalize_latex
from latex_preview.core.translate import auto_name, latex_to_python as L2P, split_equations

HERE = pathlib.Path(__file__).parent
# Sortie de « python moment_closure.py --print-eqs 2 » (fil « Closure order 3 equations »)
SCRIPT_M_A1_A1 = ("dM_A1_A1/dt = -2*M_A1_A1*m + 2*M_A1_A1*rmaxA - 2*M_A1_A1*s*thA**2 + 4*M_A1_A1*s*thA*x1 "
                  "- 2*M_A1_A1*s*x1**2 + 2*M_A1_B1*m + m*n_A1 + m*n_B1 + n_A1*rmaxA + n_A1*s*thA**2 "
                  "- 2*n_A1*s*thA*x1 + n_A1*s*x1**2 - 6*M_A1_A1*n_A1/KA - 2*M_A1_A1*n_A2/KA + M_A1_A1/KA "
                  "- 4*M_A1_A2*n_A1/KA + M_A1_A2/KA + 4*n_A1**3/KA + 4*n_A1**2*n_A2/KA")
SCRIPT_M_A1_A1_TEX = (HERE / "script_M_A1_A1.tex").read_text()   # même équation, en LaTeX
MOMENT = (HERE / "moment_ordre2.tex").read_text()


def ok(*a, **k):
    r = L2P(*a, **k)
    assert r["ok"], r["error"]
    return r


def rhs(py, **loc):
    return sp.sympify(py.split("=", 1)[1], locals=loc)


# ------------------------------------------------------------------ modèle
def test_model_names():
    m = parse_model(MOD)
    assert m.moment_name(["B2", "A1"]) == "M_A1_B2"
    assert m.moment_name(["A2", "A1", "A1"]) == "T_A1_A1_A2"
    assert m.moment_name(["A1"] * 4) == "Q_A1_A1_A1_A1"
    assert m.parse_moment_name("T_A1_A2_B1") == ["A1", "A2", "B1"]
    assert normalize_latex("N_{A}^{x_{1}}") == normalize_latex("N_A^{x_1}")


# ------------------------------------------------------------- VALIDÉ n° 1
def test_valide_1_equation_du_modele():
    r = ok(r"\frac{d}{dt}\langle N_{A}^{x_1} N_{A}^{x_2}\rangle = -\frac{2}{K_A}"
           r"\langle (N_{A}^{x_1})^2 N_{A}^{x_2}\rangle + m\,\langle N_{A}^{x_2} N_{B}^{x_1}\rangle", MOD)
    assert r["python"] == "dM_A1_A2_dt = M_A2_B1*m - 2*T_A1_A1_A2/KA"
    assert r["auto_names"] == [] and r["warnings"] == []


def test_valide_1_sortie_reelle_du_script():
    r = ok(SCRIPT_M_A1_A1_TEX, MOD)
    assert r["python"].startswith("dM_A1_A1_dt = ") and r["auto_names"] == []
    assert sp.simplify(rhs(r["python"]) - rhs(SCRIPT_M_A1_A1)) == 0


def test_valide_1_ancienne_notation():
    """Équation de la veille, écrite avec N_{A}^{1}, r_{A}^{1} (alias du modèle)."""
    r = ok(MOMENT, MOD)
    assert r["auto_names"] == [] and r["python"].startswith("dM_A2_A2_dt = ")
    for name in ("M_A2_A2", "M_A1_A2", "M_A2_B1", "n_B1", "r_A1", "rmaxA", "KA"):
        assert name in r["python"], name


def test_ecritures_equivalentes():
    a = ok(r"\langle N_{A}^{x_2} N_{A}^{x_1} \rangle", MOD)["python"]
    b = ok(r"\langle N_A^{x_1} N_A^{x_2} \rangle", MOD)["python"]
    c = ok(r"\langle N_{A}^{x_1} N_{A}^{x_1} N_{A}^{x_2}\rangle", MOD)["python"]
    assert a == b == "M_A1_A2" and c == "T_A1_A1_A2"


# ------------------------------------------------------------- VALIDÉ n° 2
def test_valide_2_noms_automatiques():
    r = ok(r"\frac{d}{dt} N_{1} = r_{1} N_{1} - \delta N_{1} + \delta N_{2}", MOD)
    assert r["python"] == "dN1_dt = -N1*delta + N1*r1 + N2*delta"
    assert sorted(r["auto_names"]) == sorted(["N_{1} → N1", "r_{1} → r1", r"\delta → delta", "N_{2} → N2"])
    assert r["warnings"] == []


def test_valide_2_regle_des_noms():
    assert auto_name("x_{i,j}") == "xij"
    assert auto_name(r"\theta_{12}") == "theta12"
    assert auto_name(r"\mathrm{zz}") == "zz"
    assert auto_name("z_1^*") == "z1star"


def test_noms_automatiques_sans_collision():
    # \mathrm{KA} ne doit pas prendre le nom du paramètre KA (= K_A) du modèle
    r = ok(r"\mathrm{KA} + K_A", MOD)
    assert r["python"] in ("KA + KA_2", "KA_2 + KA")
    assert r["auto_names"] == [r"\mathrm{KA} → KA_2"]


# ------------------------------------------------------------- VALIDÉ n° 3
CLOSURE = (r"\langle (N_{A}^{x_1})^2 N_{A}^{x_2}\rangle {rel} 2\langle N_{A}^{x_1}\rangle "
           r"\langle N_{A}^{x_1} N_{A}^{x_2}\rangle + \langle N_{A}^{x_2}\rangle\langle (N_{A}^{x_1})^2\rangle "
           r"- 2\langle N_{A}^{x_1}\rangle^2\langle N_{A}^{x_2}\rangle")


def test_valide_3_fermeture_egal_et_approx():
    expected = "T_A1_A1_A2 = M_A1_A1*n_A2 + 2*M_A1_A2*n_A1 - 2*n_A1**2*n_A2"
    for rel in ("=", r"\approx", r"\simeq"):
        assert ok(CLOSURE.replace("{rel}", rel), MOD)["python"] == expected, rel


# --------------------------------------------------- systèmes et fonctions
def test_systeme_align():
    eqs = r"""\begin{align}
\frac{d}{dt}\langle N_{A}^{x_1}\rangle &= \langle N_{A}^{x_1}\rangle\left(r_{A}^{x_1}
   - \frac{\langle N_{A}^{x_1}\rangle + \langle N_{A}^{x_2}\rangle}{K_A}\right) \\
 &\quad - m\left(\langle N_{A}^{x_1}\rangle - \langle N_{B}^{x_1}\rangle\right) \\
\frac{d\langle N_{A}^{x_2} N_{A}^{x_1}\rangle}{dt} &\approx - \frac{2}{K_A}\langle (N_{A}^{x_1})^2 N_{A}^{x_2}\rangle + z
\end{align}"""
    assert len(split_equations(eqs)) == 2
    lines = ok(eqs, MOD)["python"].splitlines()
    assert lines[0] == "dn_A1_dt = -m*(n_A1 - n_B1) + n_A1*(r_A1 - (n_A1 + n_A2)/KA)"
    assert lines[1] == "dM_A1_A2_dt = z - 2*T_A1_A1_A2/KA"


def test_definitions_et_edo():
    r = ok(r"\frac{d}{dt} N_{A}^{x_1} = N_{A}^{x_1} r_{A}^{x_1}", MOD, use_definitions=True)
    assert r["python"] == "dNA1_dt = NA1*(rmaxA - s*(-thA + x1)**2)"


def test_fonctions_et_produits():
    assert ok(r"\mathrm{N11}\left(a + b\right)", MOD)["python"] == "N11*(a + b)"
    assert ok(r"\mathrm{R1}(z)", MOD)["python"] == "R1(z)"
    assert ok(r"N_{A}^{x_1}\left(r_{A}^{x_1} - 1\right)", MOD)["python"] == "NA1*(r_A1 - 1)"
    assert ok(r"\frac{d}{dt} N(t) = a N(t)", MOD)["python"] == "dN_dt = a*N(t)"
    mod = MOD.replace("# R1 = R_1", "R1 = R_1")
    r = ok(r"\frac{d}{dt} N_{11} = N_{11} \left(R_1\left(z_1^*\right) - \frac{N_{11} + N_{12}}{K_1}\right)", mod)
    assert r["python"] == "dN11_dt = N11*(R1(z1star) - (N11 + N12)/K1)"


# ------------------------------------------------------------- VALIDÉ n° 6
def test_valide_6_erreur_sans_traduction_partielle():
    r = L2P(r"\frac{d}{dt}\langle N_{A}^{x_1}\rangle = \frac{2}{K_A", MOD)
    assert not r["ok"] and r["python"] == "" and "Accolade" in r["error"]
