"""Export « Copier pour Overleaf » (breqn, non numéroté) — validé le 13/11/2026."""
import sys, pathlib, subprocess, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from latex_preview.core.compiler import find_engine
from latex_preview.core.document import overleaf_export
from latex_preview.core.pdf_tools import crop_pdf

MOMENT = (pathlib.Path(__file__).parent / "moment_ordre2.tex").read_text()


def test_expression_nue_dmath_etoile():
    code, breqn = overleaf_export(r"a + b = c")
    assert code == "\\begin{dmath*}\na + b = c\n\\end{dmath*}" and breqn


def test_delimiteurs_retires():
    assert overleaf_export(r"$$x^2 + 1$$")[0] == "\\begin{dmath*}\nx^2 + 1\n\\end{dmath*}"
    assert overleaf_export(r"\[ x^2 \]")[0] == "\\begin{dmath*}\nx^2\n\\end{dmath*}"


def test_structure_manuelle_respectee():
    code, breqn = overleaf_export(r"a &= b \\ c &= d")
    assert code.startswith("\\begin{align*}") and not breqn


def test_texte_avec_formules():
    code, _ = overleaf_export("Soit\n\\[ x = 1 \\]\net $y$.")
    assert code == "Soit\n\\begin{dmath*} x = 1 \\end{dmath*}\net $y$."


def test_equation_numerotee_par_l_utilisateur_reste_numerotee():
    code, _ = overleaf_export("\\begin{equation}\nx = 1\n\\end{equation}")
    assert code == "\\begin{dmath}\nx = 1\n\\end{dmath}"


def test_document_complet():
    assert overleaf_export("\\documentclass{article}\\begin{document}x\\end{document}") is None


def test_compile_dans_un_article_comme_overleaf():
    """Le code copié compile dans un article A4 standard (amsmath puis breqn) et y est coupé."""
    code, _ = overleaf_export(MOMENT)
    doc = ("\\documentclass[11pt,a4paper]{article}\n\\usepackage{amsmath,amssymb}\n"
           "\\usepackage{breqn}\n\\begin{document}\n" + code + "\n\\end{document}\n")
    with tempfile.TemporaryDirectory() as d:
        (pathlib.Path(d) / "art.tex").write_text(doc)
        r = subprocess.run([find_engine("pdflatex"), "-interaction=nonstopmode", "-halt-on-error", "art.tex"],
                           cwd=d, capture_output=True)
        assert r.returncode == 0, r.stdout[-800:]
        cropped = crop_pdf((pathlib.Path(d) / "art.pdf").read_bytes())
    assert cropped.width_pt < 360          # tient dans la largeur de texte (≈ 345 pt)
    assert cropped.height_pt > 60          # sur plusieurs lignes
