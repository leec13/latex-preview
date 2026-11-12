"""Tests des opérations SymPy (python -m pytest tests)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from latex_preview.core.sympy_ops import run_operation as R

MASTER = r"\frac{\partial P(n,t)}{\partial t} = \lambda (n-1) P(n-1,t) + \mu (n+1) P(n+1,t) - (\lambda+\mu) n P(n,t)"
LOGISTIC = r"\frac{\mathrm{d}N}{\mathrm{d}t} = r N \left(1 - \frac{N}{K}\right)"


def ok(**kw):
    r = R(**kw)
    assert r["ok"], r["error"]
    return r


def test_products_not_functions():
    r = ok(text=MASTER, op="parse")
    assert "lambda*(n - 1)" in r["interpretation"] and "P(n - 1, t)" in r["interpretation"]
    assert "\\lambda" in r["symbols"] and "n" in r["symbols"]
    r = ok(text=r"r x \left(1 - \frac{x}{K}\right)", op="expand")
    assert r["latex"] == r"r x - \frac{r x^{2}}{K}"


def test_derivative_kept_verbatim():
    r = ok(text=LOGISTIC, op="subs", old="K", new=r"\frac{N^*}{2}")
    assert r["latex"].startswith(r"\frac{\mathrm{d}N}{\mathrm{d}t} = ")
    assert "N^*" in r["latex"]
    r = ok(text=LOGISTIC, op="subs", old=r"\frac{\mathrm{d}N}{\mathrm{d}t}", new="0")
    assert r["latex"].startswith("0 =")


def test_euler_and_ln():
    assert ok(text=r"e^{-\mu t} e^{\mu t} x", op="simplify")["latex"] == "x"
    assert ok(text=r"\ln(x) + \ln(y)", op="simplify", positive=True)["latex"] == r"\ln{\left(x y \right)}"


def test_sympy_roundtrip_function_style():
    r = ok(text=r"N{\left(t \right)} = \frac{K e^{r t}}{e^{r t} - 1}", op="parse")
    assert r["interpretation"].startswith("Eq(N(t),")


def test_decorated_and_starred_symbols():
    r = ok(text=r"\dot{x} = x\left(f - \bar{f}\right)", op="expand")
    assert r["latex"] == r"\dot{x} = - \bar{f} x + f x"
    r = ok(text=r"r N^* + \mu^{\star}", op="parse")
    assert "N^*" in r["symbols"]


def test_operations():
    assert ok(text=r"\frac{1}{x(x+1)}", op="apart", var="x")["latex"] == r"- \frac{1}{x + 1} + \frac{1}{x}"
    assert ok(text=r"a x^2 + b x^2 + c x + d x", op="collect", var="x")["latex"] == \
        r"x^{2} \left(a + b\right) + x \left(c + d\right)"
    assert ok(text=r"x^2 - 3x + 2 = 0", op="solve", var="x")["latex"] == r"x = 1 \\ x = 2"
    assert ok(text=r"\sum_{k=1}^{n} k", op="doit")["latex"] == r"\frac{n^{2}}{2} + \frac{n}{2}"
    assert ok(text=r"\int_0^1 x^2 \, dx", op="doit")["latex"] == r"\frac{1}{3}"
    assert ok(text=r"$$\sin^2(\theta) + \cos^2(\theta)$$", op="simplify")["latex"] == "1"
    assert ok(text=r"\sqrt{x^2}", op="simplify", positive=True)["latex"] == "x"
    assert ok(text=r"x^2", op="diff", var="x")["latex"] == "2 x"


def test_errors():
    assert not R(text=r"\frac{a}{", op="simplify")["ok"]
    assert "Accolade" in R(text=r"\frac{N^*{2}", op="parse")["error"]
    assert not R(text=r"Soit $x$ et $y$", op="simplify")["ok"]
    assert "variable" in R(text="x^2", op="diff")["error"]


def test_multiline_rejected_clearly():
    assert "Plusieurs lignes" in R(text=r"x = - \sqrt{2} \\ x = \sqrt{2}")["error"]
    assert "Plusieurs lignes" in R(text=r"a &= b")["error"]


# --- Équations de moments (système dynamique avec migration) ---------------
MOMENT = (pathlib.Path(__file__).parent / "moment_ordre2.tex").read_text()


def test_moment_equation_parsed():
    r = ok(text=MOMENT, op="parse")
    syms = set(r["symbols"])
    for s in (r"\langle (N_{A}^{2})^{2} \rangle", r"\langle N_{A}^{1} N_{A}^{2} \rangle",
              r"r_{\max,A}", r"r_{A}^{1}", "K_{A}", "m",
              r"\frac{d}{d t} \langle (N_{A}^{2})^{2} \rangle"):
        assert s in syms, s
    assert "**1" not in r["interpretation"]  # r_A^1 n'est pas une puissance


def test_moment_equation_operations():
    r = ok(text=MOMENT, op="collect", var="m")
    assert r["latex"].startswith(r"\frac{d}{d t} \langle (N_{A}^{2})^{2} \rangle = ")
    assert r"m \left(" in r["latex"]
    r = ok(text=MOMENT, op="subs", old="m", new="0")
    assert " m" not in r["latex"].replace(r"\max", "")
    r = ok(text=MOMENT, op="subs", old=r"\langle N_{A}^{2} \rangle", new="0")
    assert r"\langle N_{A}^{2} \rangle" not in r["latex"]


def test_sup_index_option():
    assert ok(text=r"x_{i}^{2}", sup_index=False)["interpretation"] == "x_{i}**2"
    assert ok(text=r"x_{i}^{2}", sup_index=True)["symbols"] == ["x_{i}^{2}"]
    assert ok(text=r"r_{\max,A}", sup_index=False)["symbols"] == [r"r_{\max,A}"]


def test_operator_derivative_of_function():
    assert ok(text=r"\frac{d}{dt} N(t) = a")["interpretation"] == "Eq(Derivative(N(t), t), a)"


# --- substitutions simultanées et moments canoniques -----------------------
def test_simultaneous_swap():
    assert ok(text="X Y + X^2", op="subs", subs=[["X", "Y"], ["Y", "X"]])["latex"] == "X Y + Y^{2}"
    r = ok(text="a x + b y", op="subs", subs=[["x", "z+1"], ["", ""]])  # ligne vide ignorée
    assert r["result_interpretation"] == "a*(z + 1) + b*y" and r["is_sum"]
    assert "incomplet" in R(text="x", op="subs", subs=[["x", ""]])["error"]


def test_moments_canonical():
    assert ok(text=r"\langle N_{A}^{2} N_{A}^{1} \rangle - \langle N_{A}^{1} N_{A}^{2} \rangle",
              op="simplify")["latex"] == "0"
    assert ok(text=r"\langle N_{A}^{2} N_{A}^{2} \rangle - \langle (N_{A}^{2})^{2} \rangle",
              op="simplify")["latex"] == "0"


def test_swap_inside_moments():
    """Échange N_A^1 ↔ N_A^2 : donne l'équation de d⟨(N_A^1)²⟩/dt."""
    r = ok(text=MOMENT, op="subs", subs=[["N_{A}^{1}", "N_{A}^{2}"], ["N_{A}^{2}", "N_{A}^{1}"]])
    lhs, rhs = r["latex"].split(" = ", 1)
    assert lhs == r"\frac{d}{d t} \langle (N_{A}^{1})^{2} \rangle"
    assert r"2 \langle N_{A}^{1} N_{B}^{1} \rangle m" in rhs          # était ⟨N_A^2 N_B^1⟩
    assert r"\langle N_{A}^{1} N_{A}^{2} \rangle" in rhs              # moment croisé inchangé
    assert r"\langle (N_{A}^{2})^{2} \rangle" not in rhs
    # Échanger deux fois redonne l'équation de départ.
    back = ok(text=r["latex"], op="subs", subs=[["N_{A}^{1}", "N_{A}^{2}"], ["N_{A}^{2}", "N_{A}^{1}"]])
    diff = ok(text=back["latex"].split(" = ", 1)[1] + " - (" + MOMENT.split("=", 1)[1] + ")",
              op="simplify")
    assert diff["latex"] == "0"
