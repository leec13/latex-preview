"""Panneau SymPy : interprétation, opérations, substitution.

Les calculs tournent dans un processus séparé : un calcul trop long peut être
interrompu (bouton Annuler ou délai) sans bloquer l'interface.
"""

from __future__ import annotations

import multiprocessing
from concurrent.futures import ProcessPoolExecutor

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QFontDatabase, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDockWidget, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from ..core.sympy_ops import NEEDS_VAR, OPERATIONS, run_operation, warm_up

PARSE_DEBOUNCE_MS = 600


class SympyRunner(QObject):
    """Exécute run_operation dans un processus de calcul unique, interruptible."""

    finished = Signal(int, dict)   # (numéro de requête, résultat)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._ctx = multiprocessing.get_context("spawn")
        self._executor: ProcessPoolExecutor | None = None
        self._next_id = 0
        self._pending: dict[int, object] = {}
        self._start()

    def _start(self) -> None:
        self._executor = ProcessPoolExecutor(max_workers=1, mp_context=self._ctx)
        self._executor.submit(warm_up)  # charge SymPy pendant que l'on tape

    def submit(self, timeout_s: float, **kwargs) -> int:
        self._next_id += 1
        rid = self._next_id
        try:
            fut = self._executor.submit(run_operation, **kwargs)
        except Exception:  # processus mort : on relance
            self.restart()
            fut = self._executor.submit(run_operation, **kwargs)
        self._pending[rid] = fut
        fut.add_done_callback(lambda f, rid=rid: self._done(rid, f))
        if timeout_s:
            QTimer.singleShot(int(timeout_s * 1000), lambda rid=rid: self._timeout(rid, timeout_s))
        return rid

    def _done(self, rid: int, fut) -> None:
        if self._pending.pop(rid, None) is None or fut.cancelled():
            return
        try:
            res = fut.result()
        except Exception as exc:  # processus tué ou planté
            res = {"ok": False, "error": f"Calcul interrompu ({type(exc).__name__}).",
                   "latex": "", "interpretation": "", "symbols": []}
        try:
            self.finished.emit(rid, res)
        except RuntimeError:  # application en cours de fermeture
            pass

    def _timeout(self, rid: int, timeout_s: float) -> None:
        if rid in self._pending:
            self.cancel_all(f"Calcul interrompu : plus de {timeout_s:.0f} s.")

    def cancel_all(self, message: str = "Calcul annulé.") -> None:
        ids = list(self._pending)
        self._pending.clear()
        self.restart()
        for rid in ids:
            self.finished.emit(rid, {"ok": False, "error": message, "latex": "",
                                     "interpretation": "", "symbols": []})

    @property
    def busy(self) -> bool:
        return bool(self._pending)

    def restart(self) -> None:
        self.shutdown()
        self._start()

    def shutdown(self) -> None:
        ex, self._executor = self._executor, None
        if ex is None:
            return
        for p in list(getattr(ex, "_processes", {}).values()):
            try:
                p.terminate()
            except Exception:
                pass
        ex.shutdown(wait=False, cancel_futures=True)


class SympyPanel(QDockWidget):
    """Dock à droite de la fenêtre ; agit sur la sélection, sinon sur tout le texte."""

    def __init__(self, editor: QPlainTextEdit, settings, parent=None) -> None:
        super().__init__("SymPy", parent)
        self.setObjectName("sympy_dock")
        self.editor = editor
        self.s = settings
        self.runner = SympyRunner(self)
        self.runner.finished.connect(self._on_result)
        self._parse_id = 0
        self._op_id = 0
        self._op_target: tuple[int, int, int, bool] | None = None  # (début, fin, révision, sélection)

        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 6, 8, 8)

        self.scope = QLabel()
        self.scope.setStyleSheet("color:#555;")
        lay.addWidget(self.scope)

        lay.addWidget(QLabel("SymPy a compris :"))
        self.interp = QPlainTextEdit(readOnly=True)
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono.setPointSize(11)
        self.interp.setFont(mono)
        self.interp.setMaximumHeight(84)
        self.interp.setToolTip("Vérifiez ici que SymPy a bien lu l'expression : "
                               "produits (*), puissances (**), fonctions f(x)…")
        lay.addWidget(self.interp)

        form = QFormLayout()
        self.var = QComboBox(editable=True)
        self.var.setToolTip("Variable pour dériver, intégrer, regrouper, résoudre, éléments simples.\n"
                            "Liste remplie avec les symboles de l'expression ; on peut taper du LaTeX.")
        self.var.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        form.addRow("Variable :", self.var)
        self.functions = QLineEdit(self.s.get("sympy_functions"))
        self.functions.setToolTip(
            "Noms à lire comme des fonctions quand ils sont suivis de (…) avec un seul argument.\n"
            "Sinon « \\lambda (n-1) » est un produit. Les appels à plusieurs arguments P(n,t)\n"
            "et la notation de SymPy N{\\left(t \\right)} sont toujours des fonctions.")
        self.functions.editingFinished.connect(self._on_options_changed)
        form.addRow("Fonctions :", self.functions)
        self.positive = QCheckBox("Symboles réels positifs")
        self.positive.setToolTip("Permet par ex. √(x²) → x, ln(x)+ln(y) → ln(xy). "
                                 "Adapté aux taux, effectifs, concentrations…")
        self.positive.setChecked(self.s.get("sympy_positive"))
        self.positive.toggled.connect(self._on_options_changed)
        form.addRow("", self.positive)
        self.sup_index = QCheckBox("Exposant après un indice = indice")
        self.sup_index.setToolTip(
            "Coché : N_{A}^{2} et r_{A}^{1} sont des noms de variables (exposant = indice\n"
            "de type, de patch…) ; une puissance s'écrit alors (N_{A}^{2})^{2}.\n"
            "Décoché : x_{i}^{2} est le carré de x_i (convention de sympy.latex).")
        self.sup_index.setChecked(self.s.get("sympy_sup_index"))
        self.sup_index.toggled.connect(self._on_options_changed)
        form.addRow("", self.sup_index)
        lay.addLayout(form)

        grid = QGridLayout()
        grid.setSpacing(4)
        self._buttons = []
        ops = ["simplify", "expand", "factor", "cancel", "doit", "apart",
               "collect", "diff", "integrate", "solve"]
        labels = {"collect": "Regrouper", "diff": "Dériver", "integrate": "Intégrer",
                  "solve": "Résoudre"}
        tips = {
            "simplify": "simplify() sur chaque membre",
            "expand": "Développe produits et puissances",
            "factor": "Factorise (polynômes, fractions)",
            "cancel": "Réduit au même dénominateur et simplifie la fraction",
            "doit": "Calcule les sommes, intégrales et dérivées écrites (∑, ∫, d/dx)",
            "apart": "Décomposition en éléments simples selon la variable",
            "collect": "Regroupe les termes selon les puissances de la variable",
            "diff": "Dérive chaque membre par rapport à la variable",
            "integrate": "Primitive de chaque membre par rapport à la variable",
            "solve": "Résout l'équation (ou expression = 0) pour la variable",
        }
        for k, op in enumerate(ops):
            text = labels.get(op, OPERATIONS[op])
            b = QPushButton(text + (" ⟨var⟩" if op in NEEDS_VAR else ""))
            b.setToolTip(tips[op])
            b.clicked.connect(lambda _=False, op=op: self.run(op))
            grid.addWidget(b, k // 2, k % 2)
            self._buttons.append(b)
        lay.addLayout(grid)

        box = QGroupBox("Substitution")
        bl = QFormLayout(box)
        self.old = QLineEdit(placeholderText="ex. K   ou   \\lambda")
        self.new = QLineEdit(placeholderText="ex. \\frac{N^*}{2}   ou   \\mu + 1")
        self.old.returnPressed.connect(lambda: self.new.setFocus())
        self.new.returnPressed.connect(lambda: self.run("subs"))
        bl.addRow("Remplacer :", self.old)
        bl.addRow("par :", self.new)
        self.subs_btn = QPushButton("Substituer")
        self.subs_btn.clicked.connect(lambda: self.run("subs"))
        bl.addRow("", self.subs_btn)
        self._buttons.append(self.subs_btn)
        lay.addWidget(box)

        row = QHBoxLayout()
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        row.addWidget(self.status, 1)
        self.cancel_btn = QPushButton("Annuler")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(lambda: self.runner.cancel_all())
        row.addWidget(self.cancel_btn)
        lay.addLayout(row)

        hint = QLabel("Agit sur la sélection s'il y en a une, sinon sur tout le texte. "
                      "⌘Z annule le remplacement.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#777; font-size:11px;")
        lay.addWidget(hint)
        lay.addStretch(1)
        self.setWidget(w)

        self._parse_timer = QTimer(self, singleShot=True, interval=PARSE_DEBOUNCE_MS)
        self._parse_timer.timeout.connect(self._request_parse)
        self.editor.textChanged.connect(self._parse_timer.start)
        self.editor.selectionChanged.connect(self._parse_timer.start)
        self.visibilityChanged.connect(lambda v: v and self._parse_timer.start())
        self._update_scope()
        self._parse_timer.start()

    # ------------------------------------------------------------ cible
    def _target(self) -> tuple[str, int, int, bool]:
        cur = self.editor.textCursor()
        if cur.hasSelection():
            text = cur.selection().toPlainText()
            if text.strip():
                return text, cur.selectionStart(), cur.selectionEnd(), True
        text = self.editor.toPlainText()
        return text, 0, len(text), False

    def _update_scope(self) -> bool:
        sel = self._target()[3]
        self.scope.setText("Agit sur : <b>la sélection</b>" if sel else "Agit sur : tout le texte")
        return sel

    def _common_kwargs(self) -> dict:
        return {"functions": self.functions.text(), "positive": self.positive.isChecked(),
                "sup_index": self.sup_index.isChecked()}

    def _on_options_changed(self) -> None:
        self.s.set("sympy_functions", self.functions.text())
        self.s.set("sympy_positive", self.positive.isChecked())
        self.s.set("sympy_sup_index", self.sup_index.isChecked())
        self._parse_timer.start()

    # ------------------------------------------------------------ requêtes
    def _request_parse(self) -> None:
        if not self.isVisible():
            return
        self._update_scope()
        text = self._target()[0]
        if not text.strip():
            self.interp.setPlainText("")
            return
        self._parse_id = self.runner.submit(10, text=text, op="parse", **self._common_kwargs())

    def run(self, op: str) -> None:
        text, start, end, sel = self._target()
        if not text.strip():
            self._set_status("L'éditeur est vide.", error=True)
            return
        var = self.var.currentText().strip()
        if op in NEEDS_VAR and not var:
            self._set_status(f"Choisissez d'abord une variable pour « {OPERATIONS[op]} ».", error=True)
            self.var.setFocus()
            return
        self._op_target = (start, end, self.editor.document().revision(), sel)
        self._op_id = self.runner.submit(
            self.s.get("sympy_timeout"), text=text, op=op, var=var,
            old=self.old.text(), new=self.new.text(), **self._common_kwargs())
        self._set_busy(True, f"{OPERATIONS[op]}…")

    def _set_busy(self, busy: bool, message: str = "") -> None:
        for b in self._buttons:
            b.setEnabled(not busy)
        self.cancel_btn.setVisible(busy)
        if message:
            self._set_status(message)

    def _set_status(self, text: str, error: bool = False) -> None:
        self.status.setStyleSheet("color:#b00020;" if error else "color:#333;")
        self.status.setText(text)

    # ------------------------------------------------------------ résultats
    def _on_result(self, rid: int, res: dict) -> None:
        if rid == self._parse_id:
            self._show_parse(res)
        if rid == self._op_id:
            self._set_busy(False)
            self._apply_result(res)

    def _show_parse(self, res: dict) -> None:
        if res["ok"]:
            self.interp.setStyleSheet("")
            self.interp.setPlainText(res["interpretation"])
            current = self.var.currentText()
            syms = res["symbols"]
            if [self.var.itemText(i) for i in range(self.var.count())] != syms:
                self.var.blockSignals(True)
                self.var.clear()
                self.var.addItems(syms)
                self.var.setCurrentText(current if current else (syms[0] if len(syms) == 1 else ""))
                self.var.blockSignals(False)
        else:
            self.interp.setStyleSheet("color:#b00020;")
            self.interp.setPlainText(res["error"])

    def _apply_result(self, res: dict) -> None:
        if not res["ok"]:
            self._set_status(res["error"], error=True)
            return
        start, end, revision, sel = self._op_target
        doc = self.editor.document()
        if doc.revision() != revision:
            self._set_status("Le texte a changé pendant le calcul : résultat non inséré.", error=True)
            return
        cur = QTextCursor(doc)
        cur.setPosition(start)
        cur.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cur.beginEditBlock()          # un seul ⌘Z pour annuler
        cur.insertText(res["latex"])
        cur.endEditBlock()
        if sel:  # garder le résultat sélectionné pour enchaîner les opérations
            cur.setPosition(start)
            cur.setPosition(start + len(res["latex"]), QTextCursor.MoveMode.KeepAnchor)
            self.editor.setTextCursor(cur)
        self._set_status("Fait. ⌘Z pour revenir en arrière.")

    def shutdown(self) -> None:
        self.runner.shutdown()
