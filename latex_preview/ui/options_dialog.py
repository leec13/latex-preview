"""Dialogue « Préambule et options »."""

from __future__ import annotations

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QHBoxLayout,
    QLabel, QPlainTextEdit, QPushButton, QSpinBox, QComboBox, QVBoxLayout,
)

from ..core.document import DEFAULT_PREAMBLE
from .highlighter import LatexHighlighter


class OptionsDialog(QDialog):
    def __init__(self, settings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Préambule et options")
        self.resize(640, 560)
        self._s = settings

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Préambule ajouté avant <code>\\begin{document}</code> "
            "(packages, macros communes à l'équipe…) :"))
        self.preamble = QPlainTextEdit()
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(12)
        self.preamble.setFont(font)
        self.preamble.setPlainText(settings.get("preamble"))
        self._hl = LatexHighlighter(self.preamble.document())
        layout.addWidget(self.preamble, 1)

        reset = QPushButton("Rétablir le préambule par défaut")
        reset.clicked.connect(lambda: self.preamble.setPlainText(DEFAULT_PREAMBLE))
        row = QHBoxLayout()
        row.addWidget(reset)
        row.addStretch(1)
        layout.addLayout(row)

        form = QFormLayout()
        self.font_size = QComboBox()
        for size in (10, 11, 12):
            self.font_size.addItem(f"{size} pt", size)
        self.font_size.setCurrentIndex([10, 11, 12].index(settings.get("font_size"))
                                       if settings.get("font_size") in (10, 11, 12) else 1)
        form.addRow("Taille de police du document :", self.font_size)

        self.text_width = QDoubleSpinBox()
        self.text_width.setRange(5.0, 40.0)
        self.text_width.setSingleStep(0.5)
        self.text_width.setSuffix(" cm")
        self.text_width.setValue(settings.get("text_width_cm"))
        self.text_width.setToolTip("Largeur de ligne : sert à centrer les équations et "
                                   "à placer les numéros (16 cm ≈ article A4).\n"
                                   "Ignorée quand « Couper les lignes longues » est coché :\n"
                                   "la largeur suit alors celle de la fenêtre.")
        form.addRow("Largeur du texte :", self.text_width)

        self.png_dpi = QSpinBox()
        self.png_dpi.setRange(72, 1200)
        self.png_dpi.setSingleStep(50)
        self.png_dpi.setSuffix(" dpi")
        self.png_dpi.setValue(settings.get("png_dpi"))
        form.addRow("Résolution PNG / copie d'image :", self.png_dpi)

        self.png_transparent = QCheckBox("Fond transparent pour l'export PNG")
        self.png_transparent.setChecked(settings.get("png_transparent"))
        form.addRow("", self.png_transparent)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply(self) -> None:
        self._s.set("preamble", self.preamble.toPlainText())
        self._s.set("font_size", self.font_size.currentData())
        self._s.set("text_width_cm", self.text_width.value())
        self._s.set("png_dpi", self.png_dpi.value())
        self._s.set("png_transparent", self.png_transparent.isChecked())
