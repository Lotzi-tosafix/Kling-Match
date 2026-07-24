"""
_shared.py — רכיבים משותפים ל-controls_panel ול-settings_dialog.
קובץ זה לא מייבא משאר קבצי ה-ui כדי למנוע circular imports.
"""

from __future__ import annotations

import qtawesome as qta
from PyQt6.QtCore import Qt, pyqtSignal as Signal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QWidget

import kling_match.ui.styles as _styles


# ── פורמטי שמירה זמינים ───────────────────────────────────────────────────────
# (מזהה, תווית תצוגה, תיאור לתפריט)
FORMATS = [
    ("mp3",  "MP3",       "MP3  ·  איכות גבוהה"),
    ("m4r",  "M4R",       "M4R  ·  רינגטון iPhone"),
    ("wav",  "WAV",       "WAV  ·  ללא דחיסה"),
]


# ── ToggleSwitch ──────────────────────────────────────────────────────────────
class ToggleSwitch(QWidget):
    """
    מתג Toggle מצויר ידנית — נראה כמו מתג iOS/Material.
    פולט toggled(bool) בכל שינוי.
    """

    toggled = Signal(bool)

    _W = 50
    _H = 26
    _R = 11

    def __init__(self, checked: bool = False,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._checked = checked
        self.setFixedSize(self._W, self._H)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        if self._checked != checked:
            self._checked = checked
            self.update()
            self.toggled.emit(self._checked)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.setChecked(not self._checked)

    def paintEvent(self, event) -> None:  # noqa: N802
        from PyQt6.QtGui import QPainter, QColor, QPainterPath
        from PyQt6.QtCore import QRectF

        p = QPainter(self)
        p.setRenderHint(p.RenderHint.Antialiasing)

        w, h, r = self._W, self._H, self._H // 2

        track_color = QColor(_styles.COLOR_PRIMARY if self._checked
                             else _styles.COLOR_OUTLINE_BRIGHT)
        track_path = QPainterPath()
        track_path.addRoundedRect(QRectF(0, 0, w, h), r, r)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track_color)
        p.drawPath(track_path)

        margin = 3
        knob_d = h - margin * 2
        knob_x = (w - knob_d - margin) if self._checked else margin
        p.setBrush(QColor("#ffffff"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(int(knob_x), margin, knob_d, knob_d)

        p.end()
