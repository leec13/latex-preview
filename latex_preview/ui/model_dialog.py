"""Dialogue d'édition du modèle (fichier .ini de correspondances)."""

from __future__ import annotations

import os

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit,
    QPushButton, QVBoxLayout,
)

from ..core.model import DEFAULT_MODEL, ModelError, parse_model


class ModelDialog(QDialog):
    def __init__(self, text: str, path: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Modèle de traduction")
        self.resize(760, 640)
        self.path = path
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(
            "Correspondances entre les noms Python de vos scripts et l'écriture LaTeX. "
            "Ce fichier peut être enregistré et partagé avec l'équipe."))
        self.edit = QPlainTextEdit(text)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(12)
        self.edit.setFont(font)
        lay.addWidget(self.edit, 1)
        self.info = QLabel()
        self.info.setWordWrap(True)
        lay.addWidget(self.info)

        row = QHBoxLayout()
        for label, slot in (("Ouvrir…", self._open), ("Enregistrer sous…", self._save),
                            ("Modèle par défaut", self._reset)):
            b = QPushButton(label)
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.edit.textChanged.connect(self._check)
        self._check()

    @property
    def text(self) -> str:
        return self.edit.toPlainText()

    def _check(self) -> bool:
        try:
            m = parse_model(self.text)
        except ModelError as exc:
            self.info.setStyleSheet("color:#b00020;")
            self.info.setText(str(exc))
            return False
        self.info.setStyleSheet("color:#2e7d32;")
        self.info.setText(f"Modèle valide : {len(m.variables)} variables, {len(m.parameters)} paramètres, "
                          f"{len(m.definitions)} définitions.")
        return True

    def _open(self) -> None:
        start = os.path.dirname(self.path) if self.path else os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(self, "Ouvrir un modèle", start, "Modèle (*.ini);;Tous (*)")
        if path:
            with open(path, encoding="utf-8") as f:
                self.edit.setPlainText(f.read())
            self.path = path

    def _save(self) -> None:
        start = self.path or os.path.join(os.path.expanduser("~"), "modele.ini")
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer le modèle", start, "Modèle (*.ini)")
        if path:
            if not path.lower().endswith(".ini"):
                path += ".ini"
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.text)
            self.path = path

    def _reset(self) -> None:
        self.edit.setPlainText(DEFAULT_MODEL)
        self.path = ""

    def _accept(self) -> None:
        if not self._check():
            QMessageBox.warning(self, "Modèle invalide", self.info.text())
            return
        self.accept()
