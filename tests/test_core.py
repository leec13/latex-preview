"""Tests du cœur : python -m pytest tests  (ou python tests/test_core.py)"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from latex_preview.core.document import classify, build_document
from latex_preview.core.compiler import TexCompiler
from latex_preview.core.pdf_tools import crop_pdf

MASTER = r"""\frac{\partial P(n,t)}{\partial t} = \lambda (n-1) P(n-1,t) + \mu (n+1) P(n+1,t) - (\lambda+\mu) n P(n,t)"""
ODE = r"""\begin{cases}
\dot{x} = r x \left(1 - \frac{x}{K}\right) - a x y \\
\dot{y} = b a x y - d y
\end{cases}"""
ALIGN = r"""\begin{align}
\frac{\mathrm{d}S}{\mathrm{d}t} &= -\beta S I \\
\frac{\mathrm{d}I}{\mathrm{d}t} &= \beta S I - \gamma I
\end{align}"""
MIXED = r"""Le flux de fitness $\phi(x)$ vérifie
$$\partial_t \phi = s\,\partial_x \phi + \frac{\sigma^2}{2}\partial_{xx}\phi$$"""
BARE_AMP = r"""f(x) &= x^2 \\ g(x) &= \sqrt{x}"""

def test_classify():
    assert classify(MASTER)[0] == "math"
    assert classify("$$" + MASTER + "$$")[0] == "math"
    assert classify(r"\[ x^2 \]")[0] == "math"
    assert classify(ODE)[0] == "math"
    assert classify(ALIGN)[0] == "body"
    assert classify(MIXED)[0] == "body"
    assert classify("```latex\n" + MASTER + "\n```")[0] == "math"
    assert classify(r"\documentclass{article}\begin{document}x\end{document}")[0] == "full"
    assert r"\begin{align*}" in build_document(BARE_AMP).source

def test_compile_all():
    c = TexCompiler()
    for s in (MASTER, ODE, ALIGN, MIXED, BARE_AMP, "$$" + MASTER + "$$"):
        r = c.compile(build_document(s))
        assert r.ok, (s, [e.describe() for e in r.errors])
        cp = crop_pdf(r.pdf_bytes)
        assert cp and cp.width_pt < 500 and cp.height_pt < 200, (cp.width_pt, cp.height_pt)

def test_error_line():
    c = TexCompiler()
    src = "a + b \\\\\n c + \\fracc{1}{2}"
    r = c.compile(build_document(src))
    assert not r.ok
    assert r.errors[0].line == 2 and r.errors[0].zone == "extrait", [e.describe() for e in r.errors]
    r = c.compile(build_document("x", preamble="\\usepackage{amsmath}\n\\undefinedmacro"))
    assert r.errors[0].zone == "préambule" and r.errors[0].line == 2, [e.describe() for e in r.errors]



# --- coupure automatique (breqn) -------------------------------------------
from latex_preview.core.pipeline import render_snippet

LONG = (r"F(x,t) = \frac{a^{2} x^{2}}{b^{2} x^{2} + 2 b x + 1} + \frac{2 a r x^{3}}{K b x + K}"
        r" - \frac{2 a r x^{2}}{b x + 1} + r^{2} x^{2} - \frac{\sigma^{3}}{x^{2} e^{\mu t} + e^{\mu t}}"
        r" + \frac{3 \sigma^{2} x}{x^{2} e^{\mu t} + e^{\mu t}} - \frac{2 r^{2} x^{3}}{K} + \frac{r^{2} x^{4}}{K^{2}}")
NOEQ = r"\left(x + 2 x^{2} + 3 x^{3} + 4 x^{4} + 5 x^{5} + 6 x^{6} + 7 x^{7} + 8 x^{8} + 9 x^{9} + 10 x^{10}\right)^{2}"


def test_auto_break_fits_width():
    c = TexCompiler()
    for s in (LONG, NOEQ, "$$" + LONG + "$$", "Texte : \\[" + LONG + "\\]"):
        out = render_snippet(c, s, auto_break=True, line_width_pt=220)
        assert out.ok and out.doc.broken, [e.describe() for e in out.result.errors]
        assert out.cropped.width_pt < 220 + 20, out.cropped.width_pt
        assert out.cropped.height_pt > 40  # plusieurs lignes
    one_line = render_snippet(c, LONG, auto_break=False)
    assert one_line.cropped.width_pt > 400


def test_auto_break_respects_user_structure():
    from latex_preview.core.document import build_document
    assert not build_document(BARE_AMP, auto_break=True).broken
    assert not build_document(ALIGN, auto_break=True).broken
    assert build_document(ODE, auto_break=True).broken  # cases dans une équation simple


def test_auto_break_user_error_still_reported():
    c = TexCompiler()
    out = render_snippet(c, "a + \\fracc{1}{2}", auto_break=True, line_width_pt=200)
    assert not out.ok
    assert out.result.errors[0].line == 1


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK")
