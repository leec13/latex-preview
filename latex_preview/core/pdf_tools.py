"""Recadrage, rendu et export du PDF compilé (PyMuPDF, rendu vectoriel)."""

from __future__ import annotations

from dataclasses import dataclass

import pymupdf

PAGE_GAP_PT = 14.0


@dataclass
class CroppedPdf:
    """PDF d'une seule page contenant le contenu recadré (pages empilées)."""

    pdf_bytes: bytes
    width_pt: float
    height_pt: float

    def open(self) -> pymupdf.Document:
        return pymupdf.open(stream=self.pdf_bytes, filetype="pdf")


def content_rect(page: pymupdf.Page) -> pymupdf.Rect | None:
    """Plus petit rectangle englobant tout ce qui est dessiné sur la page."""
    page_rect = page.rect
    rect = pymupdf.Rect()  # vide
    for _kind, bbox in page.get_bboxlog():
        r = pymupdf.Rect(bbox) & page_rect
        if r.is_empty or r.is_infinite:
            continue
        rect |= r
    return None if rect.is_empty else rect


def crop_pdf(pdf_bytes: bytes, padding_pt: float = 6.0) -> CroppedPdf | None:
    """Recadre chaque page sur son contenu et les empile sur une seule page."""
    src = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    clips = []
    for page in src:
        r = content_rect(page)
        if r is None:
            continue
        r = pymupdf.Rect(r.x0 - padding_pt, r.y0 - padding_pt,
                         r.x1 + padding_pt, r.y1 + padding_pt) & page.rect
        clips.append((page.number, r))
    if not clips:
        return None

    width = max(r.width for _, r in clips)
    height = sum(r.height for _, r in clips) + PAGE_GAP_PT * (len(clips) - 1)
    out = pymupdf.open()
    page = out.new_page(width=width, height=height)
    y = 0.0
    for pno, r in clips:
        # Contenu aligné à gauche, comme un bloc de texte.
        target = pymupdf.Rect(0, y, r.width, y + r.height)
        page.show_pdf_page(target, src, pno, clip=r)
        y += r.height + PAGE_GAP_PT
    data = out.tobytes(garbage=3, deflate=True)
    return CroppedPdf(data, width, height)


def render_rgba(cropped: CroppedPdf, scale: float, transparent: bool = False) -> tuple[bytes, int, int, int]:
    """Rend la page en pixels. Retourne (samples, largeur, hauteur, stride)."""
    doc = cropped.open()
    pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=transparent)
    return pix.samples, pix.width, pix.height, pix.stride


def export_png(cropped: CroppedPdf, path: str, dpi: int = 300, transparent: bool = True) -> None:
    doc = cropped.open()
    pix = doc[0].get_pixmap(dpi=dpi, alpha=transparent)
    pix.save(path)


def export_pdf(cropped: CroppedPdf, path: str) -> None:
    with open(path, "wb") as f:
        f.write(cropped.pdf_bytes)
