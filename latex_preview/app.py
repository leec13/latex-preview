"""Point d'entrée : `latex-preview` ou `python -m latex_preview`."""

from __future__ import annotations

import multiprocessing
import sys

from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow


def main() -> None:
    multiprocessing.freeze_support()  # pour une future application .app autonome
    app = QApplication(sys.argv)
    app.setApplicationName("LaTeX Preview")
    app.setOrganizationName("LatexPreview")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
