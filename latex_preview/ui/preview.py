"""Zone d'aperçu : affiche le PDF recadré, zoomable (⌘+molette, pincement)."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QScrollArea

from ..core.pdf_tools import CroppedPdf, render_rgba

ZOOM_MIN, ZOOM_MAX = 0.25, 10.0


def cropped_to_qimage(cropped: CroppedPdf, scale: float, transparent: bool = False) -> QImage:
    samples, w, h, stride = render_rgba(cropped, scale, transparent)
    fmt = QImage.Format.Format_RGBA8888 if transparent else QImage.Format.Format_RGB888
    return QImage(samples, w, h, stride, fmt).copy()  # copy : détache du buffer


class PreviewArea(QScrollArea):
    zoomChanged = Signal(float)

    def __init__(self, zoom: float = 2.0, parent=None) -> None:
        super().__init__(parent)
        self._cropped: CroppedPdf | None = None
        self._zoom = zoom
        self._label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("background: white; padding: 18px;")
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self._opacity = QGraphicsOpacityEffect(self._label)
        self._opacity.setOpacity(1.0)
        self._label.setGraphicsEffect(self._opacity)
        self.setWidget(self._label)
        self.setWidgetResizable(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("QScrollArea { background: white; border: none; }")
        self.show_placeholder("Collez du LaTeX dans l'éditeur.")

    # --- contenu ----------------------------------------------------------
    @property
    def cropped(self) -> CroppedPdf | None:
        return self._cropped

    def set_document(self, cropped: CroppedPdf | None) -> None:
        self._cropped = cropped
        self.set_stale(False)
        if cropped is None:
            self.show_placeholder("Rien à afficher (contenu vide).")
        else:
            self._rerender()

    def show_placeholder(self, text: str) -> None:
        self._cropped = None
        self._label.setPixmap(QPixmap())
        self._label.setText(f"<span style='color:#888; font-size:14px'>{text}</span>")

    def set_stale(self, stale: bool) -> None:
        """Atténue l'aperçu quand il ne correspond plus au texte (erreur)."""
        self._opacity.setOpacity(0.35 if stale else 1.0)

    # --- zoom -------------------------------------------------------------
    @property
    def zoom(self) -> float:
        return self._zoom

    def set_zoom(self, zoom: float) -> None:
        zoom = max(ZOOM_MIN, min(ZOOM_MAX, zoom))
        if abs(zoom - self._zoom) < 1e-4:
            return
        self._zoom = zoom
        self._rerender()
        self.zoomChanged.emit(zoom)

    def zoom_in(self) -> None:
        self.set_zoom(self._zoom * 1.2)

    def zoom_out(self) -> None:
        self.set_zoom(self._zoom / 1.2)

    def fit_width(self) -> None:
        if self._cropped is None:
            return
        avail = self.viewport().width() - 2 * 18 - 4
        avail_h = self.viewport().height() - 2 * 18 - 4
        z = min(avail / self._cropped.width_pt, avail_h / self._cropped.height_pt)
        self.set_zoom(z)

    def _rerender(self) -> None:
        if self._cropped is None:
            return
        dpr = self.devicePixelRatioF()
        img = cropped_to_qimage(self._cropped, self._zoom * dpr)
        pix = QPixmap.fromImage(img)
        pix.setDevicePixelRatio(dpr)  # net sur écran Retina
        self._label.setText("")
        self._label.setPixmap(pix)

    # --- événements -------------------------------------------------------
    def wheelEvent(self, event) -> None:
        # Qt traduit ⌘ en ControlModifier sur macOS.
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta:
                self.set_zoom(self._zoom * (1.0015 ** delta))
            event.accept()
            return
        super().wheelEvent(event)

    def event(self, e) -> bool:
        # Pincement sur le trackpad du Mac.
        if e.type() == QEvent.Type.NativeGesture:
            if e.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                self.set_zoom(self._zoom * (1.0 + e.value()))
                return True
        return super().event(e)
