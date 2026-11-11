"""Coloration syntaxique légère pour le LaTeX."""

from __future__ import annotations

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat


def _fmt(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Weight.Bold)
    f.setFontItalic(italic)
    return f


class LatexHighlighter(QSyntaxHighlighter):
    def __init__(self, document) -> None:
        super().__init__(document)
        self._rules = [
            (QRegularExpression(r"\\(begin|end)\{[^}]*\}"), _fmt("#8250df", bold=True)),
            (QRegularExpression(r"\\[A-Za-z@]+\*?|\\."), _fmt("#0550ae")),
            (QRegularExpression(r"(?<!\\)\$\$?|\\\[|\\\]|\\\(|\\\)"), _fmt("#cf222e", bold=True)),
            (QRegularExpression(r"(?<!\\)&|\\\\"), _fmt("#bc4c00", bold=True)),
            (QRegularExpression(r"[{}]"), _fmt("#6e7781")),
            (QRegularExpression(r"(?<!\\)%.*$"), _fmt("#6a737d", italic=True)),
        ]

    def highlightBlock(self, text: str) -> None:
        for rx, fmt in self._rules:
            it = rx.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)
