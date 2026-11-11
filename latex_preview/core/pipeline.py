"""Chaîne complète : extrait → .tex → compilation → PDF recadré.

Gère le repli : si la coupure automatique (breqn) fait échouer la
compilation, on recompile sans coupure pour distinguer une vraie erreur de
l'utilisateur d'une incompatibilité de breqn.
"""

from __future__ import annotations

from dataclasses import dataclass

from .compiler import CompileResult, TexCompiler
from .document import BuiltDocument, DEFAULT_PREAMBLE, build_document
from .pdf_tools import CroppedPdf, crop_pdf


@dataclass
class RenderOutcome:
    doc: BuiltDocument
    result: CompileResult
    cropped: CroppedPdf | None
    note: str = ""          # information à afficher (repli, etc.)

    @property
    def ok(self) -> bool:
        return self.result.ok


def render_snippet(
    compiler: TexCompiler,
    text: str,
    preamble: str = DEFAULT_PREAMBLE,
    engine: str = "pdflatex",
    font_size: int = 11,
    text_width_cm: float = 16.0,
    auto_break: bool = False,
    line_width_pt: float | None = None,
) -> RenderOutcome:
    doc = build_document(text, preamble, font_size, text_width_cm, auto_break, line_width_pt)
    result = compiler.compile(doc, engine)
    note = ""
    if not result.ok and doc.broken:
        plain = build_document(text, preamble, font_size, text_width_cm, False, line_width_pt)
        plain_result = compiler.compile(plain, engine)
        plain_result.duration += result.duration
        doc, result = plain, plain_result
        if result.ok:
            note = "coupure automatique impossible ici : affiché sur une ligne"
    cropped = crop_pdf(result.pdf_bytes) if result.ok else None
    return RenderOutcome(doc, result, cropped, note)
