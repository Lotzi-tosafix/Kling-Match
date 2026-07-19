"""
WaveformWidget — תצוגת גל קול מרכזית עם קטעים מסומנים.

פריסה:
  - ה-Widget תופס את הרוחב המלא אך מצייר את הגל בתוך "כרטיס" עם margins ו-border-radius
  - גל קול בצבע תכלת אחיד (SECONDARY מהפלטה הנוכחית)
  - Segment overlays, fade regions, playback cursor
  - cursor: PointingHandCursor על קטעים, SizeHorCursor על גבולות בעריכה
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np

from PyQt6.QtCore import Qt, pyqtSignal as Signal, QRect, QPoint, QRectF
from PyQt6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QBrush,
    QFont,
    QFontMetrics,
)
from PyQt6.QtWidgets import QWidget, QApplication

from kling_match.models.segment import Segment, SEGMENT_COLORS
import kling_match.ui.styles as _styles

# ── קבועי ציור ──────────────────────────────────────────────────────────────
CARD_MARGIN_H   = 20    # margin אופקי מקצות ה-widget לכרטיס
CARD_RADIUS     = 6     # עיגול קצוות קטן לכרטיס הגל
TIMELINE_HEIGHT = 22    # גובה סרגל הזמן (בתוך הכרטיס, תחתון)
HANDLE_RADIUS   = 6     # רדיוס ידית גרירת גבול
BOUNDARY_TOL    = 7     # טולרנס לזיהוי גבול בלחיצה (פיקסלים)
MIN_SEG_DUR     = 0.5   # מינימום אורך קטע (שניות)
DOWNSAMPLE_N    = 2000  # נקודות ציור גל קול


class WaveformWidget(QWidget):
    """
    ווידג'ט תצוגת גל קול מרכזי.

    הגל מוצג בתוך כרטיס עם margins ו-border-radius.
    גובה מינימלי 160px (מנוהל ע"י MainWindow ל-~1/5 מגובה המסך).
    """

    segment_clicked  = Signal(int)           # index
    boundary_dragged = Signal(int, float)    # boundary_idx, new_time
    timeline_clicked = Signal(float)         # time_sec
    file_dropped     = Signal(str)           # path

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._samples_down: Optional[np.ndarray] = None
        self._sample_rate: int = 44100
        self._duration: float = 0.0

        self._segments: List[Segment] = []
        self._selected_indices: List[int] = []

        self._edit_mode: bool = False
        self._dragging_boundary: Optional[int] = None
        self._drag_time: Optional[float] = None

        self._playback_pos: float = -1.0
        self._fade_in: float = 0.0
        self._fade_out: float = 0.0
        self._drag_hover: bool = False   # האם קובץ מרחף מעל

        self.setMinimumHeight(130)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setAcceptDrops(True)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_audio(self, samples: np.ndarray, sample_rate: int) -> None:
        self._sample_rate = sample_rate
        mono = samples.mean(axis=1) if samples.ndim > 1 else samples.astype(float)
        total = len(mono)
        self._duration = total / sample_rate if sample_rate > 0 else 0.0

        if total > DOWNSAMPLE_N:
            step = total / DOWNSAMPLE_N
            idx  = np.arange(DOWNSAMPLE_N)
            s    = (idx * step).astype(int)
            e    = np.minimum(((idx + 1) * step).astype(int), total)
            down = np.array([np.max(np.abs(mono[a:b])) if b > a else 0.0
                             for a, b in zip(s, e)])
        else:
            down = np.abs(mono)

        mx = down.max()
        if mx > 0:
            down = down / mx
        self._samples_down = down
        self.update()

    def set_segments(self, segments: List[Segment]) -> None:
        self._segments = list(segments)
        self.update()

    def set_selected(self, indices: List[int]) -> None:
        self._selected_indices = list(indices)
        self.update()

    def set_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = enabled
        self._dragging_boundary = None
        self._drag_time = None
        self.update()

    def set_playback_position(self, time_sec: float) -> None:
        """עדכון מיקום סמן השמעה. time_sec < 0 → מסתיר את הסמן."""
        self._playback_pos = time_sec
        self.update()

    def set_fade_regions(self, fade_in: float, fade_out: float) -> None:
        self._fade_in = fade_in
        self._fade_out = fade_out
        self.update()

    # ── Geometry helpers ──────────────────────────────────────────────────────

    def _card_rect(self) -> QRect:
        """מלבן ה'כרטיס' כולל (עם margins אופקיים וללא margin אנכי)."""
        return QRect(CARD_MARGIN_H, 0,
                     self.width() - 2 * CARD_MARGIN_H, self.height())

    def _wave_rect(self) -> QRect:
        """אזור הגל בתוך הכרטיס (ללא סרגל הזמן)."""
        cr = self._card_rect()
        return QRect(cr.x(), cr.y(), cr.width(), cr.height() - TIMELINE_HEIGHT)

    def _time_to_x(self, t: float) -> int:
        if self._duration <= 0:
            return self._card_rect().x()
        cr = self._card_rect()
        return cr.x() + int(t / self._duration * cr.width())

    def _x_to_time(self, x: int) -> float:
        if self._duration <= 0:
            return 0.0
        cr = self._card_rect()
        rel = x - cr.x()
        return max(0.0, min(self._duration, rel / cr.width() * self._duration))

    def _segment_at_x(self, x: int) -> Optional[int]:
        t = self._x_to_time(x)
        for i, seg in enumerate(self._segments):
            if seg.start <= t < seg.end:
                return i
        return None

    def _boundary_at_x(self, x: int) -> Optional[int]:
        for i in range(len(self._segments) - 1):
            bx = self._time_to_x(self._segments[i].end)
            if abs(x - bx) <= BOUNDARY_TOL:
                return i
        return None

    # ── Drag & Drop ───────────────────────────────────────────────────────────

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile():
                event.acceptProposedAction()
                self._drag_hover = True
                self.update()
                return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._drag_hover = False
        self.update()

    def dropEvent(self, event) -> None:  # noqa: N802
        self._drag_hover = False
        self.update()
        if event.mimeData().hasUrls():
            path = event.mimeData().urls()[0].toLocalFile()
            if path:
                event.acceptProposedAction()
                self.file_dropped.emit(path)

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:  # noqa: N802
        # קרא צבעים עדכניים מהפלטה הנוכחית בכל ציור
        p = _styles.get_palette()
        C_BG             = p["BG"]
        C_SURFACE2       = p["SURFACE2"]
        C_SECONDARY      = p["SECONDARY"]
        C_PRIMARY        = p["PRIMARY"]
        C_OUTLINE        = p["OUTLINE"]
        C_OUTLINE_BRIGHT = p["OUTLINE_BRIGHT"]
        C_MUTED          = p["MUTED"]
        C_ON_SURFACE     = p["ON_SURFACE"]

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        cr  = self._card_rect()
        wr  = self._wave_rect()
        wh  = wr.height()

        # ── רקע חיצוני (margin) ─────────────────────────────────────────────
        painter.fillRect(self.rect(), QColor(C_BG))

        # ── כרטיס עם rounded corners ─────────────────────────────────────────
        card_path = QPainterPath()
        card_path.addRoundedRect(QRectF(cr), CARD_RADIUS, CARD_RADIUS)
        painter.fillPath(card_path, QColor(C_BG))

        # clip לתוך הכרטיס
        painter.setClipPath(card_path)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # ── אם אין שמע — מסך ריק עם הוראות העלאה ───────────────────────────
        if self._samples_down is None:
            self._draw_empty_state(painter, cr, p)
            painter.setClipping(False)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            border_color = QColor(C_SECONDARY if self._drag_hover else C_OUTLINE_BRIGHT)
            border_pen = QPen(border_color, 2 if self._drag_hover else 1,
                              Qt.PenStyle.DashLine if self._drag_hover else Qt.PenStyle.SolidLine)
            painter.setPen(border_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(cr), CARD_RADIUS, CARD_RADIUS)
            painter.end()
            return

        # ── שכבות ────────────────────────────────────────────────────────────
        self._draw_waveform(painter, cr, wh, C_SECONDARY)
        self._draw_segments(painter, cr, wh)
        self._draw_boundaries(painter, cr, wh, C_OUTLINE_BRIGHT, C_PRIMARY, C_SECONDARY)
        self._draw_fade_regions(painter, cr, wh, p)
        self._draw_playback_cursor(painter, cr, wh, C_PRIMARY)
        self._draw_timeline(painter, cr, wh, C_SURFACE2, C_OUTLINE, C_OUTLINE_BRIGHT, C_MUTED, C_PRIMARY)

        # ── גבול כרטיס ───────────────────────────────────────────────────────
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setClipping(False)
        border_pen = QPen(QColor(C_OUTLINE_BRIGHT))
        border_pen.setWidth(1)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(cr), CARD_RADIUS, CARD_RADIUS)

        painter.end()

    def _draw_empty_state(self, painter: QPainter, cr: QRect, p: dict) -> None:
        """ציור מסך ריק עם הזמנה לגרירת קובץ."""
        C_SECONDARY  = p["SECONDARY"]
        C_MUTED      = p["MUTED"]
        C_ON_SURFACE = p["ON_SURFACE"]

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = cr.width(), cr.height()
        cx = cr.x() + w // 2
        cy = cr.y() + h // 2

        if self._drag_hover:
            overlay = QColor(C_SECONDARY)
            overlay.setAlpha(18)
            painter.fillRect(cr, overlay)

        icon_r = 28
        icon_color = QColor(C_SECONDARY if self._drag_hover else C_MUTED)
        icon_color.setAlpha(200 if self._drag_hover else 120)
        painter.setPen(QPen(icon_color, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPoint(cx, cy - 30), icon_r, icon_r)

        arrow_color = QColor(C_SECONDARY if self._drag_hover else C_MUTED)
        arrow_color.setAlpha(200 if self._drag_hover else 130)
        arrow_pen = QPen(arrow_color, 2.5, Qt.PenStyle.SolidLine,
                         Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(arrow_pen)
        painter.drawLine(cx, cy - 47, cx, cy - 18)
        painter.drawLine(cx, cy - 47, cx - 9, cy - 38)
        painter.drawLine(cx, cy - 47, cx + 9, cy - 38)

        font_main = QFont("Segoe UI", 12, QFont.Weight.DemiBold)
        painter.setFont(font_main)
        main_color = QColor(C_SECONDARY if self._drag_hover else C_ON_SURFACE)
        main_color.setAlpha(220 if self._drag_hover else 160)
        painter.setPen(QPen(main_color))
        main_text = "גרור קובץ שמע לכאן"
        fm_main = QFontMetrics(font_main)
        painter.drawText(cx - fm_main.horizontalAdvance(main_text) // 2,
                         cy + 18, main_text)

        font_sub = QFont("Segoe UI", 9)
        painter.setFont(font_sub)
        sub_color = QColor(C_MUTED)
        sub_color.setAlpha(160)
        painter.setPen(QPen(sub_color))
        sub_text = "או לחץ על 'בחר שיר'  ·  MP3, WAV, FLAC, AAC, OGG, M4A"
        fm_sub = QFontMetrics(font_sub)
        painter.drawText(cx - fm_sub.horizontalAdvance(sub_text) // 2,
                         cy + 40, sub_text)

    def _draw_waveform(self, painter: QPainter, cr: QRect, wh: int,
                       C_SECONDARY: str) -> None:
        if self._samples_down is None or len(self._samples_down) == 0:
            return
        n   = len(self._samples_down)
        mid = cr.y() + wh // 2
        painter.setPen(QPen(QColor(C_SECONDARY), 1))
        for i, amp in enumerate(self._samples_down):
            x    = cr.x() + int(i / n * cr.width())
            half = int(amp * (wh // 2) * 0.88)
            painter.drawLine(x, mid - half, x, mid + half)

    def _draw_segments(self, painter: QPainter, cr: QRect, wh: int) -> None:
        for i, seg in enumerate(self._segments):
            x1 = self._time_to_x(seg.start)
            x2 = self._time_to_x(seg.end)
            if x2 <= x1:
                continue
            color_hex = SEGMENT_COLORS.get(seg.label, "#888888")
            color = QColor(color_hex)
            color.setAlpha(110 if i in self._selected_indices else 55)
            painter.fillRect(x1, cr.y(), x2 - x1, wh, color)

            if i in self._selected_indices:
                border = QColor(color_hex)
                border.setAlpha(230)
                pen = QPen(border, 2)
                painter.setPen(pen)
                painter.drawRect(x1, cr.y(), x2 - x1 - 1, wh - 1)

    def _draw_boundaries(self, painter: QPainter, cr: QRect, wh: int,
                          C_OUTLINE_BRIGHT: str, C_PRIMARY: str,
                          C_SECONDARY: str) -> None:
        for i in range(len(self._segments) - 1):
            bx = self._time_to_x(self._segments[i].end)

            if self._edit_mode:
                pen = QPen(QColor(C_OUTLINE_BRIGHT), 2, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawLine(bx, cr.y(), bx, cr.y() + wh)

                mid_y = cr.y() + wh // 2
                hc = QColor(C_PRIMARY if self._dragging_boundary == i else C_SECONDARY)
                painter.setBrush(QBrush(hc))
                painter.setPen(QPen(QColor("#ffffff"), 1))
                painter.drawEllipse(QPoint(bx, mid_y), HANDLE_RADIUS, HANDLE_RADIUS)

                if self._dragging_boundary == i and self._drag_time is not None:
                    ts   = self._format_time_precise(self._drag_time)
                    font = QFont("Segoe UI", 9)
                    painter.setFont(font)
                    fm   = QFontMetrics(font)
                    tw   = fm.horizontalAdvance(ts)
                    tx   = max(cr.x() + 2, min(bx - tw // 2, cr.right() - tw - 2))
                    ty   = mid_y - HANDLE_RADIUS - 6
                    bg   = QRect(tx - 6, ty - fm.ascent() - 2, tw + 12, fm.height() + 4)
                    painter.setBrush(QBrush(QColor(C_PRIMARY)))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                    painter.drawRoundedRect(bg, 6, 6)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                    painter.setPen(QPen(QColor("#ffffff")))
                    painter.drawText(tx, ty, ts)
            else:
                pen = QPen(QColor(C_OUTLINE_BRIGHT), 1)
                painter.setPen(pen)
                painter.drawLine(bx, cr.y(), bx, cr.y() + wh)

    def _draw_fade_regions(self, painter: QPainter, cr: QRect, wh: int,
                            p: dict) -> None:
        if self._duration <= 0:
            return
        # במצב בהיר — גוון כהה על הגל; במצב כהה — שחור
        light = _styles.is_light_mode()
        fade_color = (80, 80, 80) if light else (0, 0, 0)
        if self._fade_in > 0:
            fx = self._time_to_x(self._fade_in)
            grad = QLinearGradient(cr.x(), 0, fx, 0)
            grad.setColorAt(0.0, QColor(*fade_color, 140))
            grad.setColorAt(1.0, QColor(*fade_color, 0))
            painter.fillRect(cr.x(), cr.y(), fx - cr.x(), wh, QBrush(grad))
        if self._fade_out > 0:
            fx = self._time_to_x(self._duration - self._fade_out)
            grad = QLinearGradient(fx, 0, cr.right(), 0)
            grad.setColorAt(0.0, QColor(*fade_color, 0))
            grad.setColorAt(1.0, QColor(*fade_color, 140))
            painter.fillRect(fx, cr.y(), cr.right() - fx, wh, QBrush(grad))

    def _draw_playback_cursor(self, painter: QPainter, cr: QRect, wh: int,
                               C_PRIMARY: str) -> None:
        if self._playback_pos < 0:
            return
        cx = self._time_to_x(self._playback_pos)
        pen = QPen(QColor(C_PRIMARY), 2)
        painter.setPen(pen)
        painter.drawLine(cx, cr.y(), cx, cr.y() + wh)

    def _draw_timeline(self, painter: QPainter, cr: QRect, wh: int,
                        C_SURFACE2: str, C_OUTLINE: str, C_OUTLINE_BRIGHT: str,
                        C_MUTED: str, C_PRIMARY: str) -> None:
        ty = cr.y() + wh
        painter.fillRect(cr.x(), ty, cr.width(), TIMELINE_HEIGHT, QColor(C_SURFACE2))

        painter.setPen(QPen(QColor(C_OUTLINE)))
        painter.drawLine(cr.x(), ty, cr.right(), ty)

        if self._duration <= 0:
            return

        font = QFont("Segoe UI", 8)
        painter.setFont(font)
        fm = QFontMetrics(font)

        intervals = [5, 10, 15, 30, 60, 120, 300]
        interval = intervals[-1]
        for iv in intervals:
            if self._duration / iv <= 20:
                interval = iv
                break

        t = 0.0
        while t <= self._duration:
            x   = self._time_to_x(t)
            painter.setPen(QPen(QColor(C_OUTLINE_BRIGHT)))
            painter.drawLine(x, ty, x, ty + 5)
            lbl = self._format_time_simple(t)
            tw  = fm.horizontalAdvance(lbl)
            tx  = max(cr.x(), min(x - tw // 2, cr.right() - tw))
            painter.setPen(QPen(QColor(C_MUTED)))
            painter.drawText(tx, ty + TIMELINE_HEIGHT - 3, lbl)
            t  += interval

        # עיגול סמן השמעה על סרגל הזמן
        if self._playback_pos >= 0:
            cx = self._time_to_x(self._playback_pos)
            circle_y = ty + TIMELINE_HEIGHT // 2
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setBrush(QBrush(QColor(C_PRIMARY)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPoint(cx, circle_y), 5, 5)

    # ── Mouse events ──────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:  # noqa: N802
        pos = event.position() if hasattr(event, "position") else None
        x = int(pos.x() if pos else event.x())
        y = int(pos.y() if pos else event.y())

        wr = self._wave_rect()
        if y >= wr.bottom():          # timeline
            self.timeline_clicked.emit(self._x_to_time(x))
            return

        if self._edit_mode:
            b = self._boundary_at_x(x)
            if b is not None:
                self._dragging_boundary = b
                self._drag_time = self._x_to_time(x)
                self.update()
                return

        idx = self._segment_at_x(x)
        if idx is not None:
            self.segment_clicked.emit(idx)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        pos = event.position() if hasattr(event, "position") else None
        x = int(pos.x() if pos else event.x())
        y = int(pos.y() if pos else event.y())

        if self._dragging_boundary is not None and self._edit_mode:
            self._handle_boundary_drag(x)
            return

        cr = self._card_rect()
        in_card = cr.contains(x, y)

        if self._edit_mode and in_card:
            if self._boundary_at_x(x) is not None:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        elif in_card and not self._edit_mode:
            wr = self._wave_rect()
            if y >= wr.bottom():
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            elif self._segment_at_x(x) is not None:
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._dragging_boundary is not None:
            self._dragging_boundary = None
            self._drag_time = None
            self.update()

    def _handle_boundary_drag(self, x: int) -> None:
        i = self._dragging_boundary
        if i is None or i >= len(self._segments) - 1:
            return
        left, right = self._segments[i], self._segments[i + 1]
        lo = left.start + MIN_SEG_DUR
        hi = right.end  - MIN_SEG_DUR
        if lo > hi:
            return
        t = max(lo, min(hi, self._x_to_time(x)))
        if abs(t - left.end) < 1e-6:
            return
        self._drag_time = t
        self.update()
        self.boundary_dragged.emit(i, t)

    # ── Format helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _format_time_precise(t: float) -> str:
        t = max(0.0, t)
        ms = int(round(t * 1000))
        s, ms = divmod(ms, 1000)
        m, s  = divmod(s, 60)
        return f"{m:02d}:{s:02d}.{ms:03d}"

    @staticmethod
    def _format_time_simple(t: float) -> str:
        t = max(0.0, t)
        s = int(t)
        return f"{s // 60}:{s % 60:02d}"
