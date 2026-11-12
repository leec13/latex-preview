"""Préférences persistantes (QSettings : ~/Library/Preferences sur macOS)."""

from __future__ import annotations

from PySide6.QtCore import QSettings

from .core.document import DEFAULT_PREAMBLE

WELCOME = r"""\frac{\partial P(n,t)}{\partial t} = \lambda\,(n-1)\,P(n-1,t) + \mu\,(n+1)\,P(n+1,t) - (\lambda+\mu)\,n\,P(n,t)"""

DEFAULTS = {
    "preamble": DEFAULT_PREAMBLE,
    "engine": "pdflatex",
    "font_size": 11,
    "text_width_cm": 16.0,
    "zoom": 2.0,
    "auto_refresh": True,
    "auto_break": True,
    "png_dpi": 300,
    "png_transparent": True,
    "last_text": WELCOME,
    "last_dir": "",
    "vertical_layout": False,
    "model_text": "",
    "model_path": "",
    "tr_expand": False,
    "tr_defs": False,
    "tr_collect": False,
}

_TYPES = {k: type(v) for k, v in DEFAULTS.items()}


class Settings:
    def __init__(self) -> None:
        self._q = QSettings("LatexPreview", "LatexPreview")

    def get(self, key: str):
        default = DEFAULTS[key]
        value = self._q.value(key, default)
        t = _TYPES[key]
        try:
            if t is bool:
                return value if isinstance(value, bool) else str(value).lower() in ("1", "true", "yes")
            return t(value)
        except (TypeError, ValueError):
            return default

    def set(self, key: str, value) -> None:
        self._q.setValue(key, value)

    def raw(self) -> QSettings:
        return self._q
