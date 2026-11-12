"""Corrections proposées et conseils : les cas du tableau validé le 12/11/2026."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pytest
from latex_preview.core.compiler import TexCompiler
from latex_preview.core.fixes import advice
from latex_preview.core.pipeline import render_snippet


@pytest.fixture(scope="module")
def tex():
    c = TexCompiler()
    yield c
    c.cleanup()


def fix_of(tex, text, **kw):
    out = render_snippet(tex, text, **kw)
    assert not out.ok, "ce texte devrait échouer"
    assert out.fix is not None, [e.describe() for e in out.result.errors]
    assert out.fix_cropped is not None            # l'aperçu de la correction existe
    return out.fix


# --- erreurs bloquantes : correction vérifiée par compilation -------------
def test_accolade_non_fermee(tex):
    assert fix_of(tex, r"\frac{a}{b").text == r"\frac{a}{b}"


def test_accolade_partial(tex):
    assert fix_of(tex, r"\frac{\partial{N}{\partial t}").text == r"\frac{\partial{N}}{\partial t}"


def test_accolade_en_trop(tex):
    assert fix_of(tex, r"\frac{a}{b}} + c").text == r"\frac{a}{b} + c"


def test_left_sans_right(tex):
    assert fix_of(tex, r"\left( \frac{N}{K}").text == r"\left( \frac{N}{K} \right)"


def test_right_sans_left(tex):
    assert fix_of(tex, r"a + b \right)").text == r"a + b )"


def test_commandes_mal_orthographiees(tex):
    assert fix_of(tex, r"\fracc{1}{2}").text == r"\frac{1}{2}"
    assert fix_of(tex, r"\lamda + 1").text == r"\lambda + 1"
    assert fix_of(tex, r"\langel x \rangle").text == r"\langle x \rangle"


def test_double_exposant(tex):
    assert fix_of(tex, r"x^2^3").text == r"x^{2^3}"


def test_unicode(tex):
    f = fix_of(tex, "α ≤ β · γ")
    assert f.text == r"\alpha \leq \beta \cdot \gamma"
    assert "α → \\alpha" in f.description


def test_dollars_dans_une_equation(tex):
    out = render_snippet(tex, r"\frac{d}{dt} x = $\frac{a}{b}$ y")
    assert not out.ok and out.fix.text.split() == r"\frac{d}{dt} x = \frac{a}{b} y".split()


def test_unicode_et_accolade_ensemble(tex):
    assert fix_of(tex, r"\frac{α}{b").text == r"\frac{\alpha}{b}"


def test_pas_de_correction_inventee(tex):
    out = render_snippet(tex, r"\begin{toto} x \end{toto}")
    assert not out.ok and out.fix is None


# --- conseils (le texte compile) -----------------------------------------
def test_conseil_antislash(tex):
    out = render_snippet(tex, r"alpha + theta_A + partial N + sum_k x_k")
    assert out.ok and out.advice
    a = out.advice[0]
    assert a.text == r"\alpha + \theta_A + \partial N + \sum_k x_k"
    for w in ("alpha", "theta", "partial", "sum"):
        assert w in a.message


def test_conseil_pas_de_fausse_alerte():
    assert advice(r"\alpha + \mathrm{max} + \text{la somme sum} + K_{\max}", "math") == []
    assert advice(r"m u + p i", "math") == []                        # produits voulus
    assert advice(r"Le sum des termes $x + y$", "body") == []        # « sum » hors maths
    assert advice(r"mu_A + 1", "math")[0].text == r"\mu_A + 1"       # grec court avec indice


def test_conseil_parentheses():
    assert advice("(a + b)) c", "math")[0].message == "Parenthèse « ) » en trop, ligne 1"
    assert "jamais fermée" in advice("(a + (b\n+ c)", "math")[0].message
    assert advice(r"\left( a \right) + (b)", "math") == []


def test_faute_trouvee_sans_le_journal():
    """Sur certaines versions de TeX Live, le journal ne cite pas la commande fautive :
    la correction doit être trouvée quand même, en lisant le texte."""
    from latex_preview.core.compiler import TexError
    from latex_preview.core.fixes import candidates
    for text, good in [(r"\fracc{1}{2}", r"\frac{1}{2}"), (r"\lamda + 1", r"\lambda + 1"),
                       (r"\langel x \rangle", r"\langle x \rangle")]:
        sans_contexte = [TexError("Undefined control sequence.")]          # journal muet
        assert candidates(text, sans_contexte)[0].text == good
        assert candidates(text, [TexError("Emergency stop.")])[0].text == good  # autre message


def test_faute_a_cote_d_une_commande_valide(tex):
    # \mathscr est hors liste mais valide avec mathrsfs ; la vraie faute est \lamda
    out = render_snippet(tex, r"\lamda + \mathscr{L}", preamble="\\usepackage{amsmath}\n\\usepackage{mathrsfs}")
    assert out.fix is not None and out.fix.text == r"\lambda + \mathscr{L}"
