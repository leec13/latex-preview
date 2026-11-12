"""Panneau Traduction : LaTeX de l'éditeur → code Python selon le modèle."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDockWidget, QGroupBox, QHBoxLayout, QLabel, QPlainTextEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from ..core.model import DEFAULT_MODEL
from ..core.translate import latex_to_python, warm_up
from .model_dialog import ModelDialog
from .worker import Runner



class TranslatePanel(QDockWidget):
    def __init__(self, editor: QPlainTextEdit, settings, parent=None) -> None:
        super().__init__("Traduction", parent)
        self.setObjectName("translate_dock")
        self.editor = editor
        self.s = settings
        self.runner = Runner(warm_up=warm_up, parent=self)
        self.runner.finished.connect(self._on_result)
        self._l2p_id = 0
        self._pending = False

        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono.setPointSize(11)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 6, 8, 8)

        # --- modèle -------------------------------------------------------
        mrow = QHBoxLayout()
        self.model_label = QLabel()
        self.model_label.setWordWrap(True)
        mrow.addWidget(self.model_label, 1)
        b_model = QPushButton("Modifier le modèle…")
        b_model.clicked.connect(self.edit_model)
        mrow.addWidget(b_model)
        lay.addLayout(mrow)

        # --- LaTeX → Python ----------------------------------------------
        box1 = QGroupBox("LaTeX de l'éditeur → Python")
        l1 = QVBoxLayout(box1)
        orow = QHBoxLayout()
        self.expand = QCheckBox("Développer")
        self.expand.setToolTip("Développe le membre de droite, comme la sortie de moment_closure.py")
        self.expand.setChecked(self.s.get("tr_expand"))
        self.defs = QCheckBox("Remplacer par les définitions")
        self.defs.setToolTip("Applique la section [definitions] du modèle,\n"
                             "par ex. r_A1 → rmaxA - s*(x1 - thA)**2")
        self.defs.setChecked(self.s.get("tr_defs"))
        for cb in (self.expand, self.defs):
            cb.toggled.connect(self._on_options)
            orow.addWidget(cb)
        orow.addStretch(1)
        l1.addLayout(orow)
        self.py_out = QPlainTextEdit(readOnly=True)
        self.py_out.setFont(mono)
        self.py_out.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.py_out.setPlaceholderText("Le code Python de l'équation de l'éditeur s'affiche ici.")
        l1.addWidget(self.py_out, 1)
        self.l2p_info = QLabel()
        self.l2p_info.setWordWrap(True)
        self.l2p_info.setTextFormat(Qt.TextFormat.PlainText)
        l1.addWidget(self.l2p_info)
        b_copy = QPushButton("Copier le Python")
        b_copy.clicked.connect(self._copy_python)
        l1.addWidget(b_copy)
        lay.addWidget(box1, 1)

        self.setWidget(w)

        self._timer = QTimer(self, singleShot=True, interval=50)
        self._timer.timeout.connect(self._request_l2p)
        # La traduction suit la compilation de l'aperçu (validé le 12/11, solution a) :
        # rien n'est traduit tant que le texte ne compile pas. Voir on_compiled().
        self._compiled: tuple[str, bool] | None = None   # (texte, compile ?)
        self._l2p_text = ""
        self.visibilityChanged.connect(lambda v: v and self._timer.start())
        self._update_model_label()
        self._timer.start()

    # ------------------------------------------------------------ modèle
    @property
    def model_text(self) -> str:
        return self.s.get("model_text") or DEFAULT_MODEL

    def _update_model_label(self) -> None:
        path = self.s.get("model_path")
        if self.model_text == DEFAULT_MODEL:
            name = "deux niches (par défaut)"
        elif path:
            name = os.path.basename(path)
        else:
            name = "personnalisé"
        self.model_label.setText(f"Modèle : <b>{name}</b>")

    def edit_model(self) -> None:
        dlg = ModelDialog(self.model_text, self.s.get("model_path"), self)
        if dlg.exec():
            self.s.set("model_text", dlg.text)
            self.s.set("model_path", dlg.path)
            self._update_model_label()
            self._timer.start()

    def _on_options(self) -> None:
        self.s.set("tr_expand", self.expand.isChecked())
        self.s.set("tr_defs", self.defs.isChecked())
        self._timer.start()

    # ------------------------------------------------------------ LaTeX → Python
    def _request_l2p(self) -> None:
        if not self.isVisible():
            return
        if self.runner.busy:  # une traduction tourne : on relancera à la fin
            self._pending = True
            return
        self._pending = False
        if self._compiled is None:
            return
        text, compiles = self._compiled
        if not text.strip():
            self.py_out.setPlainText("")
            self.l2p_info.setText("")
            return
        if not compiles:
            self._show_not_compiling()
            return
        self._l2p_text = text
        self._l2p_id = self.runner.submit(latex_to_python, 15, text=text, model_text=self.model_text,
                                          expand=self.expand.isChecked(),
                                          use_definitions=self.defs.isChecked())

    def on_compiled(self, text: str, ok: bool) -> None:
        """Appelé par la fenêtre après chaque compilation de l'aperçu."""
        self._compiled = (text, ok)
        if ok:
            self._timer.start()
        else:
            self._show_not_compiling()

    def _show_not_compiling(self) -> None:
        self.py_out.setPlainText("")
        self._info(self.l2p_info, "Le LaTeX ne compile pas : corrigez d'abord l'erreur "
                   "(voir sous l'aperçu).", "error")

    def _copy_python(self) -> None:
        QApplication.clipboard().setText(self.py_out.toPlainText())
        self._info(self.l2p_info, "Code Python copié.", "ok")

    # ------------------------------------------------------------ résultats
    def _info(self, label: QLabel, text: str, kind: str) -> None:
        color = {"error": "#b00020", "warn": "#a15c00", "ok": "#2e7d32", "info": "#455a64"}.get(kind, "#333")
        label.setStyleSheet(f"color:{color};")
        label.setText(text)

    def _on_result(self, rid: int, res: dict) -> None:
        current = self._compiled is not None and self._compiled == (self._l2p_text, True)
        if rid == self._l2p_id and not current:
            pass  # traduction d'un texte qui a changé depuis (ou qui ne compile plus) : ignorée
        elif rid == self._l2p_id:
            if res["ok"]:
                self.py_out.setPlainText(res["python"])
                n = res.get("count", 0)
                lines = [f"{n} équation{'s' if n > 1 else ''}." if n else ""]
                auto = res.get("auto_names", [])
                if auto:
                    lines.append(f"{len(auto)} nom{'s' if len(auto) > 1 else ''} automatique"
                                 f"{'s' if len(auto) > 1 else ''} (hors modèle) : " + ", ".join(auto))
                kind = "info" if auto else "ok"
                if res.get("warnings"):
                    lines.append("⚠ " + " ; ".join(res["warnings"]))
                    kind = "warn"
                self._info(self.l2p_info, "\n".join(l for l in lines if l), kind)
            else:
                self.py_out.setPlainText("")
                self._info(self.l2p_info, res["error"], "error")
        if self._pending and not self.runner.busy:
            self._request_l2p()

    def shutdown(self) -> None:
        self.runner.shutdown()
