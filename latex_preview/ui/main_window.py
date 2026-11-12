"""Fenêtre principale : éditeur à gauche, aperçu à droite."""

from __future__ import annotations

import atexit
import html
import os
import threading
from dataclasses import dataclass

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFontDatabase, QKeySequence, QTextCursor, QTextFormat
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QLabel, QMainWindow,
    QMessageBox, QPlainTextEdit, QSplitter, QTextEdit, QToolBar, QVBoxLayout, QWidget,
)

from ..core.compiler import ENGINES, TexCompiler, find_engine
from ..core.pdf_tools import CroppedPdf, export_pdf, export_png
from ..core.pipeline import RenderOutcome, render_snippet
from ..settings import Settings
from .highlighter import LatexHighlighter
from .options_dialog import OptionsDialog
from .preview import PreviewArea, cropped_to_qimage
from .translate_panel import TranslatePanel

DEBOUNCE_MS = 450


@dataclass(frozen=True)
class Job:
    text: str
    preamble: str
    engine: str
    font_size: int
    text_width_cm: float
    auto_break: bool
    line_width_pt: float | None


@dataclass
class JobOutcome:
    job: Job
    render: RenderOutcome


class _Bridge(QObject):
    """Ramène le résultat du fil de compilation vers le fil de l'interface."""
    finished = Signal(object)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LaTeX Preview")
        self.s = Settings()
        self.compiler = TexCompiler()
        self._bridge = _Bridge()
        self._bridge.finished.connect(self._on_finished)
        self._busy = False
        self._pending: Job | None = None
        self._last_job: Job | None = None
        self._last_log = ""
        self._last_full_pdf: bytes | None = None
        self._last_mode = "math"

        self._build_editor()
        self.preview = PreviewArea(zoom=self.s.get("zoom"))
        self.preview.zoomChanged.connect(self._on_zoom_changed)
        self.preview.widthChanged.connect(self._on_preview_width_changed)

        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setTextFormat(Qt.TextFormat.RichText)
        self.error_label.setStyleSheet(
            "QLabel { background:#fff0f0; color:#8b0000; border-top:1px solid #e5b4b4;"
            " padding:8px; font-size:12px; }")
        self.error_label.linkActivated.connect(self._on_error_link)
        self.error_label.hide()

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        rl.addWidget(self.preview, 1)
        rl.addWidget(self.error_label)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.editor)
        self.splitter.addWidget(right)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setChildrenCollapsible(False)
        self.setCentralWidget(self.splitter)

        self.translate_panel = TranslatePanel(self.editor, self.s, self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.translate_panel)

        self._build_actions()
        self._build_toolbar()
        self._build_menus()

        self._timer = QTimer(self, singleShot=True, interval=DEBOUNCE_MS)
        self._timer.timeout.connect(self.refresh)
        self.editor.textChanged.connect(self._on_text_changed)

        self._restore_state()
        self._check_tex()
        self.editor.setPlainText(self.s.get("last_text"))
        self.refresh()

    # ------------------------------------------------------------------ UI
    def _build_editor(self) -> None:
        self.editor = QPlainTextEdit()
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(13)
        self.editor.setFont(font)
        self.editor.setPlaceholderText(
            "Collez ici du LaTeX : expression nue (sortie de sympy.latex), $$…$$, \\[…\\],\n"
            "environnements align/equation, texte avec formules, ou document complet.")
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._highlighter = LatexHighlighter(self.editor.document())

    def _act(self, text, slot, shortcut=None, tip=None) -> QAction:
        a = QAction(text, self)
        a.triggered.connect(slot)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        if tip:
            a.setToolTip(tip)
            a.setStatusTip(tip)
        return a

    def _build_actions(self) -> None:
        self.a_refresh = self._act("Actualiser", lambda: self.refresh(force=True), "Ctrl+Return",
                                   "Recompiler maintenant (⌘↵)")
        self.a_paste_replace = self._act("Coller en remplaçant", self.paste_replace, "Ctrl+Shift+V",
                                         "Remplacer tout le texte par le presse-papiers (⇧⌘V)")
        self.a_copy_img = self._act("Copier l'image", self.copy_image, "Ctrl+Shift+C",
                                    "Copier le rendu dans le presse-papiers (⇧⌘C)")
        self.a_pdf = self._act("Exporter PDF…", self.export_pdf, "Ctrl+E",
                               "Enregistrer le rendu recadré en PDF vectoriel (⌘E)")
        self.a_png = self._act("Exporter PNG…", self.export_png, "Ctrl+Shift+E",
                               "Enregistrer le rendu en image PNG (⇧⌘E)")
        self.a_open = self._act("Ouvrir un fichier .tex…", self.open_file, QKeySequence.StandardKey.Open)
        self.a_save = self._act("Enregistrer l'extrait…", self.save_file, QKeySequence.StandardKey.Save)
        self.a_options = self._act("Préambule et options…", self.edit_options, "Ctrl+,")
        self.a_zoom_in = self._act("Zoom avant", lambda: self.preview.zoom_in(), QKeySequence.StandardKey.ZoomIn)
        self.a_zoom_out = self._act("Zoom arrière", lambda: self.preview.zoom_out(), QKeySequence.StandardKey.ZoomOut)
        self.a_zoom_100 = self._act("Taille réelle", lambda: self.preview.set_zoom(1.0), "Ctrl+0")
        self.a_fit = self._act("Ajuster à la fenêtre", lambda: self.preview.fit_width(), "Ctrl+9")
        self.a_layout = self._act("Aperçu sous l'éditeur", self._toggle_layout)
        self.a_layout.setCheckable(True)
        self.a_log = self._act("Journal de compilation…", self.show_log, "Ctrl+L")
        self.a_quit = self._act("Quitter", self.close, QKeySequence.StandardKey.Quit)
        self.a_translate = self.translate_panel.toggleViewAction()
        self.a_translate.setText("Traduction")
        self.a_translate.setShortcut(QKeySequence("Ctrl+K"))
        self.a_translate.setToolTip("Afficher / masquer le panneau Traduction LaTeX ⇄ Python (⌘K)")

    def _build_toolbar(self) -> None:
        tb = QToolBar("Outils")
        tb.setObjectName("main_toolbar")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(tb)
        tb.addAction(self.a_refresh)
        self.auto_box = QCheckBox("Auto")
        self.auto_box.setToolTip("Recompiler automatiquement pendant la frappe")
        self.auto_box.setChecked(self.s.get("auto_refresh"))
        self.auto_box.toggled.connect(lambda v: self.s.set("auto_refresh", v))
        tb.addWidget(self.auto_box)
        self.break_box = QCheckBox("Couper les lignes longues")
        self.break_box.setToolTip(
            "Coupe les équations trop longues pour qu'elles tiennent dans la largeur\n"
            "de l'aperçu, avec les lignes suivantes alignées sous le signe « = ».\n"
            "Les expressions sans « = » sont coupées aussi. Les équations déjà\n"
            "structurées par vous (&, \\\\) ne sont pas modifiées.")
        self.break_box.setChecked(self.s.get("auto_break"))
        self.break_box.toggled.connect(self._on_break_toggled)
        tb.addWidget(self.break_box)
        self.engine_box = QComboBox()
        self.engine_box.addItems(ENGINES)
        self.engine_box.setCurrentText(self.s.get("engine"))
        self.engine_box.setToolTip("Moteur TeX")
        self.engine_box.currentTextChanged.connect(self._on_engine_changed)
        tb.addWidget(self.engine_box)
        tb.addSeparator()
        tb.addAction(self.a_zoom_out)
        self.zoom_label = QLabel()
        self.zoom_label.setMinimumWidth(52)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tb.addWidget(self.zoom_label)
        tb.addAction(self.a_zoom_in)
        tb.addAction(self.a_fit)
        tb.addSeparator()
        tb.addAction(self.a_copy_img)
        tb.addAction(self.a_pdf)
        tb.addAction(self.a_png)
        tb.addSeparator()
        tb.addAction(self.a_translate)
        tb.addAction(self.a_options)
        self.a_zoom_out.setText("−")
        self.a_zoom_in.setText("+")
        self.a_fit.setText("Ajuster")
        self._on_zoom_changed(self.preview.zoom)

    def _build_menus(self) -> None:
        mb = self.menuBar()
        m = mb.addMenu("Fichier")
        for a in (self.a_open, self.a_save, None, self.a_pdf, self.a_png, self.a_copy_img, None, self.a_quit):
            m.addSeparator() if a is None else m.addAction(a)
        m = mb.addMenu("Édition")
        m.addAction(self.a_paste_replace)
        m.addAction(self.a_refresh)
        m = mb.addMenu("Affichage")
        for a in (self.a_zoom_in, self.a_zoom_out, self.a_zoom_100, self.a_fit, None, self.a_layout,
                  self.a_translate, self.a_log):
            m.addSeparator() if a is None else m.addAction(a)
        m = mb.addMenu("Document")
        m.addAction(self.a_options)

    # ------------------------------------------------------------ état
    def _restore_state(self) -> None:
        q = self.s.raw()
        geo = q.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        else:
            self.resize(1200, 640)
        ws = q.value("window_state")
        if ws is not None:
            self.restoreState(ws)  # position et visibilité du panneau SymPy
        st = q.value("splitter")
        if st is not None:
            self.splitter.restoreState(st)
        if self.s.get("vertical_layout"):
            self.a_layout.setChecked(True)
            self.splitter.setOrientation(Qt.Orientation.Vertical)

    def closeEvent(self, event) -> None:
        q = self.s.raw()
        q.setValue("geometry", self.saveGeometry())
        q.setValue("splitter", self.splitter.saveState())
        q.setValue("window_state", self.saveState())
        self.translate_panel.shutdown()
        self.s.set("last_text", self.editor.toPlainText())
        self.s.set("zoom", self.preview.zoom)
        if self._busy:  # une compilation tourne encore : nettoyer à la sortie
            atexit.register(self.compiler.cleanup)
        else:
            self.compiler.cleanup()
        super().closeEvent(event)

    def _check_tex(self) -> None:
        if find_engine(self.engine_box.currentText()) is None:
            QMessageBox.warning(
                self, "TeX introuvable",
                f"Impossible de trouver « {self.engine_box.currentText()} ».\n\n"
                "Installez TeX Live / MacTeX, ou vérifiez qu'il est dans "
                "/Library/TeX/texbin.")

    # ---------------------------------------------------------- compilation
    def _current_job(self) -> Job:
        auto_break = self.break_box.isChecked()
        width = None
        if auto_break:
            # Arrondi à 6 pt : évite de recompiler pour un pixel de différence.
            width = round(self.preview.available_width_pt() / 6.0) * 6.0
        return Job(
            text=self.editor.toPlainText(),
            preamble=self.s.get("preamble"),
            engine=self.engine_box.currentText(),
            font_size=self.s.get("font_size"),
            text_width_cm=self.s.get("text_width_cm"),
            auto_break=auto_break,
            line_width_pt=width,
        )

    def _on_text_changed(self) -> None:
        self._clear_error_highlight()
        if self.auto_box.isChecked():
            self._timer.start()

    def _on_break_toggled(self, checked: bool) -> None:
        self.s.set("auto_break", checked)
        self.refresh(force=True)

    def _on_preview_width_changed(self) -> None:
        # La fenêtre ou le zoom a changé : on remet en page (avec délai).
        timer = getattr(self, "_timer", None)
        if timer is not None and self.isVisible() and self.break_box.isChecked():
            timer.start()

    def _on_engine_changed(self, engine: str) -> None:
        self.s.set("engine", engine)
        self.refresh(force=True)

    def refresh(self, force: bool = False) -> None:
        self._timer.stop()
        job = self._current_job()
        if not job.text.strip():
            self._last_job = job
            self.preview.show_placeholder("Collez du LaTeX dans l'éditeur.")
            self._show_errors([])
            self.statusBar().clearMessage()
            return
        if not force and job == self._last_job:
            return
        if self._busy:
            self._pending = job
            return
        self._start(job)

    def _start(self, job: Job) -> None:
        self._busy = True
        self._last_job = job
        self.statusBar().showMessage("Compilation…")

        def work():
            out = render_snippet(self.compiler, job.text, job.preamble, job.engine,
                                 job.font_size, job.text_width_cm,
                                 job.auto_break, job.line_width_pt)
            try:
                self._bridge.finished.emit(JobOutcome(job, out))
            except RuntimeError:  # fenêtre déjà détruite (fermeture)
                pass

        threading.Thread(target=work, daemon=True).start()

    def _on_finished(self, outcome: JobOutcome) -> None:
        self._busy = False
        out, job = outcome.render, outcome.job
        self._last_log = out.result.log
        if out.result.ok:
            self._last_mode = out.doc.mode
            self._last_full_pdf = out.result.pdf_bytes
            self.preview.set_document(out.cropped)
            self._show_errors([])
            mode = {"math": "expression", "body": "texte et formules", "full": "document complet"}[out.doc.mode]
            msg = f"Compilé en {out.result.duration:.2f} s".replace(".", ",") + f" · {job.engine} · {mode}"
            if out.doc.broken:
                msg += " · coupé à la largeur de la fenêtre"
            if out.note:
                msg += f" · {out.note}"
            self.statusBar().showMessage(msg)
        else:
            self.preview.set_stale(self.preview.cropped is not None)
            self._show_errors(out.result.errors)
            self.statusBar().showMessage("Erreur de compilation — dernier rendu valide affiché en grisé")
        if self._pending is not None:
            job, self._pending = self._pending, None
            if job != self._last_job:
                self._start(job)

    # -------------------------------------------------------------- erreurs
    def _show_errors(self, errors) -> None:
        self._clear_error_highlight()
        if not errors:
            self.error_label.hide()
            return
        parts = []
        for e in errors[:4]:
            msg = e.friendly if e.friendly != e.message else html.escape(e.message)
            ctx = f" <code>{html.escape(e.context)}</code>" if e.context else ""
            if e.line and e.zone == "extrait":
                parts.append(f"<a href='line:{e.line}'>Ligne {e.line}</a> : {msg}{ctx}")
            elif e.line and e.zone == "préambule":
                parts.append(f"<a href='preamble'>Préambule, ligne {e.line}</a> : {msg}{ctx}")
            else:
                parts.append(f"{msg}{ctx}")
        more = "" if len(errors) <= 4 else f"<br>… et {len(errors) - 4} autre(s)."
        self.error_label.setText("<br>".join(parts) + more +
                                 " &nbsp; <a href='log'>Journal complet</a>")
        self.error_label.show()
        first = next((e for e in errors if e.line and e.zone == "extrait"), None)
        if first:
            self._highlight_line(first.line)

    def _highlight_line(self, line: int) -> None:
        block = self.editor.document().findBlockByNumber(line - 1)
        if not block.isValid():
            return
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(QColor("#ffd7d7"))
        sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        cur = QTextCursor(block)
        sel.cursor = cur
        self.editor.setExtraSelections([sel])

    def _clear_error_highlight(self) -> None:
        self.editor.setExtraSelections([])

    def _on_error_link(self, link: str) -> None:
        if link.startswith("line:"):
            block = self.editor.document().findBlockByNumber(int(link[5:]) - 1)
            if block.isValid():
                self.editor.setTextCursor(QTextCursor(block))
                self.editor.setFocus()
        elif link == "preamble":
            self.edit_options()
        elif link == "log":
            self.show_log()

    def show_log(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Journal de compilation")
        dlg.resize(800, 500)
        lay = QVBoxLayout(dlg)
        view = QPlainTextEdit(self._last_log or "(aucune compilation)")
        view.setReadOnly(True)
        view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        lay.addWidget(view)
        view.moveCursor(QTextCursor.MoveOperation.End)
        dlg.exec()

    # ---------------------------------------------------------- actions
    def paste_replace(self) -> None:
        text = QApplication.clipboard().text()
        if text:
            self.editor.setPlainText(text)
            self.refresh(force=True)

    def _require_render(self) -> CroppedPdf | None:
        c = self.preview.cropped
        if c is None:
            QMessageBox.information(self, "Rien à exporter", "Aucun rendu valide pour l'instant.")
        return c

    def _ask_path(self, title: str, filt: str, default_name: str) -> str | None:
        start = os.path.join(self.s.get("last_dir") or os.path.expanduser("~"), default_name)
        path, _ = QFileDialog.getSaveFileName(self, title, start, filt)
        if path:
            self.s.set("last_dir", os.path.dirname(path))
        return path or None

    def copy_image(self) -> None:
        c = self._require_render()
        if c is None:
            return
        dpi = self.s.get("png_dpi")
        img = cropped_to_qimage(c, dpi / 72.0, transparent=False)
        dpm = round(dpi / 0.0254)
        img.setDotsPerMeterX(dpm)  # taille physique correcte au collage
        img.setDotsPerMeterY(dpm)
        QApplication.clipboard().setImage(img)
        self.statusBar().showMessage(f"Image copiée ({img.width()}×{img.height()} px, {dpi} dpi)", 4000)

    def export_pdf(self) -> None:
        c = self._require_render()
        if c is None:
            return
        path = self._ask_path("Exporter en PDF", "PDF (*.pdf)", "equation.pdf")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        if self._last_mode == "full" and self._last_full_pdf:
            with open(path, "wb") as f:  # document complet : pages d'origine
                f.write(self._last_full_pdf)
        else:
            export_pdf(c, path)
        self.statusBar().showMessage(f"PDF enregistré : {path}", 5000)

    def export_png(self) -> None:
        c = self._require_render()
        if c is None:
            return
        path = self._ask_path("Exporter en PNG", "Image PNG (*.png)", "equation.png")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        export_png(c, path, dpi=self.s.get("png_dpi"), transparent=self.s.get("png_transparent"))
        self.statusBar().showMessage(f"PNG enregistré : {path}", 5000)

    def open_file(self) -> None:
        start = self.s.get("last_dir") or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(self, "Ouvrir", start, "LaTeX (*.tex *.txt);;Tous (*)")
        if path:
            self.s.set("last_dir", os.path.dirname(path))
            with open(path, encoding="utf-8", errors="replace") as f:
                self.editor.setPlainText(f.read())
            self.refresh(force=True)

    def save_file(self) -> None:
        path = self._ask_path("Enregistrer l'extrait", "LaTeX (*.tex)", "extrait.tex")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())

    def edit_options(self) -> None:
        dlg = OptionsDialog(self.s, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            dlg.apply()
            self.refresh(force=True)

    # ---------------------------------------------------------------- vue
    def _toggle_layout(self, checked: bool) -> None:
        self.s.set("vertical_layout", checked)
        self.splitter.setOrientation(Qt.Orientation.Vertical if checked else Qt.Orientation.Horizontal)

    def _on_zoom_changed(self, z: float) -> None:
        self.zoom_label.setText(f"{z * 100:.0f} %")
        self.s.set("zoom", z)
        self._on_preview_width_changed()  # au zoom, la largeur disponible change
