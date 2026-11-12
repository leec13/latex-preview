"""Panneau Traduction : LaTeX de l'éditeur ⇄ code Python selon le modèle."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontDatabase, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDockWidget, QGroupBox, QHBoxLayout, QLabel, QPlainTextEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from ..core.model import DEFAULT_MODEL
from ..core.translate import latex_to_python, python_to_latex, warm_up
from .model_dialog import ModelDialog
from .worker import Runner

DEBOUNCE_MS = 300


class TranslatePanel(QDockWidget):
    def __init__(self, editor: QPlainTextEdit, settings, parent=None) -> None:
        super().__init__("Traduction", parent)
        self.setObjectName("translate_dock")
        self.editor = editor
        self.s = settings
        self.runner = Runner(warm_up=warm_up, parent=self)
        self.runner.finished.connect(self._on_result)
        self._l2p_id = 0
        self._p2l_id = 0
        self._pending = False
        self._p2l_revision = None

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
        lay.addWidget(box1, 3)

        # --- Python → LaTeX ----------------------------------------------
        box2 = QGroupBox("Python → LaTeX (dans l'éditeur)")
        l2 = QVBoxLayout(box2)
        self.py_in = QPlainTextEdit()
        self.py_in.setFont(mono)
        self.py_in.setPlaceholderText("Collez une sortie de script, une ligne par équation, par ex.\n"
                                      "dM_A1_A2/dt = -2*T_A1_A1_A2/KA + m*(M_A2_B1 + M_A1_B2)")
        l2.addWidget(self.py_in, 1)
        prow = QHBoxLayout()
        self.collect = QCheckBox("Regrouper par moment")
        self.collect.setToolTip("Met en facteur chaque moment (plus lisible qu'une sortie développée)")
        self.collect.setChecked(self.s.get("tr_collect"))
        self.collect.toggled.connect(lambda v: self.s.set("tr_collect", v))
        prow.addWidget(self.collect)
        prow.addStretch(1)
        self.b_convert = QPushButton("Convertir dans l'éditeur")
        self.b_convert.setToolTip("Remplace le texte de l'éditeur (⌘Z pour revenir en arrière)")
        self.b_convert.clicked.connect(self.convert_python)
        prow.addWidget(self.b_convert)
        l2.addLayout(prow)
        self.p2l_info = QLabel()
        self.p2l_info.setWordWrap(True)
        self.p2l_info.setTextFormat(Qt.TextFormat.PlainText)
        l2.addWidget(self.p2l_info)
        lay.addWidget(box2, 2)
        self.setWidget(w)

        self._timer = QTimer(self, singleShot=True, interval=DEBOUNCE_MS)
        self._timer.timeout.connect(self._request_l2p)
        self.editor.textChanged.connect(self._timer.start)
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
        text = self.editor.toPlainText()
        if not text.strip():
            self.py_out.setPlainText("")
            self.l2p_info.setText("")
            return
        self._l2p_id = self.runner.submit(latex_to_python, 15, text=text, model_text=self.model_text,
                                          expand=self.expand.isChecked(),
                                          use_definitions=self.defs.isChecked())

    def _copy_python(self) -> None:
        QApplication.clipboard().setText(self.py_out.toPlainText())
        self._info(self.l2p_info, "Code Python copié.", "ok")

    # ------------------------------------------------------------ Python → LaTeX
    def convert_python(self) -> None:
        text = self.py_in.toPlainText()
        if not text.strip():
            self._info(self.p2l_info, "Collez d'abord du code Python au-dessus.", "error")
            return
        self._p2l_revision = self.editor.document().revision()
        self._p2l_id = self.runner.submit(python_to_latex, 20, text=text, model_text=self.model_text,
                                          collect=self.collect.isChecked())
        self.b_convert.setEnabled(False)
        self._info(self.p2l_info, "Conversion…", "")

    # ------------------------------------------------------------ résultats
    def _info(self, label: QLabel, text: str, kind: str) -> None:
        color = {"error": "#b00020", "warn": "#a15c00", "ok": "#2e7d32"}.get(kind, "#333")
        label.setStyleSheet(f"color:{color};")
        label.setText(text)

    def _on_result(self, rid: int, res: dict) -> None:
        if rid == self._l2p_id:
            if res["ok"]:
                self.py_out.setPlainText(res["python"])
                if res.get("warnings"):
                    self._info(self.l2p_info, "⚠ " + " ; ".join(res["warnings"]), "warn")
                else:
                    n = res.get("count", 0)
                    self._info(self.l2p_info, f"{n} équation{'s' if n > 1 else ''}, tous les symboles "
                               "sont dans le modèle." if n else "", "ok")
            else:
                self.py_out.setPlainText("")
                self._info(self.l2p_info, res["error"], "error")
        if rid == self._p2l_id:
            self.b_convert.setEnabled(True)
            self._apply_p2l(res)
        if self._pending and not self.runner.busy:
            self._request_l2p()

    def _apply_p2l(self, res: dict) -> None:
        if not res["ok"]:
            self._info(self.p2l_info, res["error"], "error")
            return
        if self.editor.document().revision() != self._p2l_revision:
            self._info(self.p2l_info, "L'éditeur a changé pendant la conversion : rien n'a été remplacé.",
                       "error")
            return
        cur = QTextCursor(self.editor.document())
        cur.select(QTextCursor.SelectionType.Document)
        cur.beginEditBlock()  # un seul ⌘Z pour revenir en arrière
        cur.insertText(res["latex"])
        cur.endEditBlock()
        n = res.get("count", 0)
        msg = f"{n} équation{'s' if n > 1 else ''} dans l'éditeur (⌘Z pour revenir en arrière)."
        if res.get("warnings"):
            self._info(self.p2l_info, msg + "\n⚠ " + " ; ".join(res["warnings"]), "warn")
        else:
            self._info(self.p2l_info, msg, "ok")

    def shutdown(self) -> None:
        self.runner.shutdown()
