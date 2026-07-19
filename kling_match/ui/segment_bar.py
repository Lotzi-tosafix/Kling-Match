"""
SegmentBar — שורת תגיות קטעים.

מציגה תגית עגולה לכל קטע, ברוחב פרופורציונלי לאורכו.
- border-radius בפינות כל תגית
- cursor: PointingHandCursor
- tooltip עם שם ועת-זמן בריחוף
- margins אופקיים התואמים ל-WaveformWidget
"""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal as Signal, QRect, QRectF, QPoint
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
    QBrush,
    QCursor,
)
from PyQt6.QtWidgets import QWidget, QToolTip

from kling_match.models.segment import SEGMENT_COLORS, Segment
import kling_match.ui.styles as _styles
from kling_match.ui.waveform_widget import CARD_MARGIN_H   # margin אחיד

_DEFAULT_COLOR = "#888888"
_TAG_RADIUS    = 6
_PADDING_H     = 5
_BAR_RADIUS    = 6    # עיגול קצוות קטן לרקע הסרגל


class SegmentBar(QWidget):
    """
    שורת תגיות קטעים — כל תגית קלה, עגולה, עם tooltip.

    Signals:
        segment_clicked(int)
    """

    segment_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self._segments: List[Segment] = []
        self._selected_indices: List[int] = []
        self._duration: float = 0.0

    # ── Public API ────────────────────────────────────────────────────────────

    def set_segments(self, segments: List[Segment]) -> None:
        self._segments = list(segments)
        self._selected_indices = []
        self._duration = segments[-1].end if segments else 0.0
        self.update()

    def set_selected(self, indices: List[int]) -> None:
        self._selected_indices = list(indices)
        self.update()

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:  # noqa: N802
        # קרא צבעים עדכניים מהפלטה הנוכחית
        p = _styles.get_palette()
        C_BG       = p["BG"]
        C_SURFACE2 = p["SURFACE2"]

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = self.width()
        h = self.height()

        # רקע חיצוני — צבע הרקע הראשי
        painter.fillRect(self.rect(), QColor(C_BG))

        # כרטיס עם rounded corners + margins
        card_rect = QRectF(CARD_MARGIN_H, 2, w - 2 * CARD_MARGIN_H, h - 4)
        card_path = QPainterPath()
        card_path.addRoundedRect(card_rect, _BAR_RADIUS, _BAR_RADIUS)
        painter.fillPath(card_path, QColor(C_SURFACE2))

        if not self._segments or self._duration <= 0:
            painter.end()
            return

        painter.setClipPath(card_path)

        font = QFont("Segoe UI", 9, QFont.Weight.DemiBold)
        painter.setFont(font)
        fm = QFontMetrics(font)

        inner_w = w - 2 * CARD_MARGIN_H
        tag_h   = h - 8
        tag_y   = 4

        for i, seg in enumerate(self._segments):
            x1 = CARD_MARGIN_H + int(seg.start / self._duration * inner_w)
            x2 = CARD_MARGIN_H + int(seg.end   / self._duration * inner_w)
            seg_w = x2 - x1 - 1          # 1px gap בין תגיות
            if seg_w <= 0:
                continue

            color_hex  = SEGMENT_COLORS.get(seg.label, _DEFAULT_COLOR)
            is_selected = i in self._selected_indices
            color = QColor(color_hex)

            # ── מילוי תגית ────────────────────────────────────────────────
            fill = QColor(color)
            fill.setAlpha(210 if is_selected else 150)

            path = QPainterPath()
            path.addRoundedRect(QRectF(x1, tag_y, seg_w, tag_h), _TAG_RADIUS, _TAG_RADIUS)
            painter.fillPath(path, fill)

            # ── מסגרת תגית ────────────────────────────────────────────────
            border = QColor("#ffffff" if is_selected else color_hex)
            border.setAlpha(255 if is_selected else 120)
            painter.setPen(QPen(border, 1.5 if is_selected else 1.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

            # ── טקסט ──────────────────────────────────────────────────────
            text = seg.label_he
            avail = seg_w - _PADDING_H * 2
            if avail > fm.horizontalAdvance("…") + 2:
                while len(text) > 1 and fm.horizontalAdvance(text + "…") > avail:
                    text = text[:-1]
                if fm.horizontalAdvance(text) > avail:
                    text = ""
                elif text != seg.label_he:
                    text += "…"

                if text:
                    tx = x1 + (seg_w - fm.horizontalAdvance(text)) // 2
                    ty = tag_y + (tag_h + fm.ascent() - fm.descent()) // 2

                    # צל
                    painter.setPen(QPen(QColor(0, 0, 0, 140)))
                    painter.drawText(tx + 1, ty + 1, text)
                    # טקסט
                    painter.setPen(QPen(QColor("#ffffff")))
                    painter.drawText(tx, ty, text)

        painter.end()

    # ── Mouse events ──────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:  # noqa: N802
        x = int(event.position().x() if hasattr(event, "position") else event.x())
        idx = self._tag_at_x(x)
        if idx is not None:
            self.segment_clicked.emit(idx)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        x = int(event.position().x() if hasattr(event, "position") else event.x())
        y = int(event.position().y() if hasattr(event, "position") else event.y())
        idx = self._tag_at_x(x)
        if idx is not None:
            seg = self._segments[idx]
            tip = (
                f"{seg.label_he}  ({seg.label})\n"
                f"{self._fmt(seg.start)} → {self._fmt(seg.end)}  "
                f"({self._fmt(seg.duration)})"
            )
            QToolTip.showText(
                self.mapToGlobal(QPoint(x, y)), tip, self
            )
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        else:
            QToolTip.hideText()
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _tag_at_x(self, x: int) -> Optional[int]:
        if self._duration <= 0:
            return None
        inner_w = self.width() - 2 * CARD_MARGIN_H
        for i, seg in enumerate(self._segments):
            x1 = CARD_MARGIN_H + int(seg.start / self._duration * inner_w)
            x2 = CARD_MARGIN_H + int(seg.end   / self._duration * inner_w)
            if x1 <= x < x2:
                return i
        return None

    @staticmethod
    def _fmt(t: float) -> str:
        t = max(0.0, t)
        s = int(t)
        ms = int((t - s) * 10)
        return f"{s // 60}:{s % 60:02d}.{ms}"
