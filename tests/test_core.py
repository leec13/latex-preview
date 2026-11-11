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

if __name__ == "__main__":
    test_classify(); test_compile_all(); test_error_line(); print("OK")
