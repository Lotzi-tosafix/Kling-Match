"""
ControlsPanel — TopPanel + InfoBar + BottomPanel לאפליקציית קלינג-Match.

פריסת BottomPanel:
  שורה 1 (סליידרים): [Fade In ——]  [Fade Out ——]  [Crossfade ——]
  ─────────────────────────────────────────────────────────────
  שורה 2 (כפתורים): [⚙]  ···  [תצוגה מקדימה]  [שמור כ...]  [⋯]  ···  [0:00]
                     שמאל        ── מרכז ──                          ימין

כל סליידר — מבנה אנכי (QVBoxLayout):
  שורה עליונה:  ערך כחול (שמאל)  ··· שם (ימין)
  שורה תחתונה: סליידר רחב
"""

from __future__ import annotations

from typing import Optional

import qtawesome as qta
from PyQt6.QtCore import Qt, pyqtSignal as Signal, QSize, QTimer
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSlider,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

def _rounded_menu(parent: QWidget) -> "RoundedMenu":
    """מחזיר RoundedMenu — QMenu עם פינות מעוגלות אמיתיות ב-Windows."""
    return RoundedMenu(parent)


class RoundedMenu(QMenu):
    """
    QMenu עם פינות מעוגלות אמיתיות.
    פותר את באג Windows שבו border-radius ב-stylesheet מתעלם מה-native frame.
    הפתרון: WA_TranslucentBackground + ציור רקע מותאם ב-paintEvent.
    """

    _RADIUS = 12

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )

    def paintEvent(self, event) -> None:  # noqa: N802
        from PyQt6.QtGui import QPainter, QPainterPath, QColor, QPen
        from PyQt6.QtCore import QRectF
        import kling_match.ui.styles as _st

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, self._RADIUS, self._RADIUS)

        # רקע — קרא מהפלטה הנוכחית
        p = _st.get_palette()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(p["SURFACE4"]))
        painter.drawPath(path)

        # גבול
        painter.setPen(QPen(QColor(p["OUTLINE_BRIGHT"]), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        painter.end()

        # ציור הפריטים על גבי הרקע המעוגל שלנו
        super().paintEvent(event)

import kling_match.ui.styles as _styles
from kling_match.ui.styles import (
    COLOR_MUTED,
    COLOR_SECONDARY,
    COLOR_ON_SURFACE,
    COLOR_PRIMARY,
    COLOR_PRIMARY_DIM,
    COLOR_SURFACE2,
    COLOR_SURFACE3,
    COLOR_SURFACE4,
    COLOR_DISABLED_TEXT,
    COLOR_OUTLINE_BRIGHT,
    COLOR_OUTLINE,
    COLOR_DISABLED_BG,
    COLOR_WARNING,
)

_ICO_SM = 13


# ── helper: כפתור עם אייקון ──────────────────────────────────────────────────
def _btn(icon_name: str, text: str, color: str = COLOR_ON_SURFACE,
         tip: str = "", checkable: bool = False) -> QPushButton:
    b = QPushButton()
    b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    if icon_name:
        b.setIcon(qta.icon(icon_name, color=color))
    b.setText(f"  {text}" if text else "")
    if tip:
        b.setToolTip(tip)
    b.setCheckable(checkable)
    return b


# ── SplitSaveButton ───────────────────────────────────────────────────────────
# פורמטים זמינים — מיובאים מ-_shared.py (משותף עם settings_dialog)
from kling_match.ui._shared import FORMATS as _FORMATS, ToggleSwitch  # noqa: E402


class SplitSaveButton(QWidget):
    """
    כפתור מפוצל לשמירה.
    מצויר ידנית ב-paintEvent — עוקף בעיות RTL/LTR ו-stylesheet גלובלי.
    """

    export_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.setFixedHeight(46)
        self.setMinimumWidth(160)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._current_fmt = _FORMATS[0]
        self._enabled = False
        self._hover_main  = False
        self._hover_arrow = False
        self._ARROW_W = 30
        self._RADIUS  = 17

        # תפריט פורמטים — נבנה בכל פתיחה כדי לקרוא צבעים עדכניים
        self._fmt_menu = _rounded_menu(self)
        self._fmt_menu.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def _rebuild_fmt_menu(self) -> None:
        """בנה מחדש את תפריט הפורמטים עם צבעים עדכניים."""
        self._fmt_menu.clear()
        c_secondary = _styles.get_palette()["SECONDARY"]
        for fmt_id, _, fmt_desc in _FORMATS:
            self._fmt_menu.addAction(
                qta.icon("fa5s.file-audio", color=c_secondary),
                fmt_desc,
                lambda fid=fmt_id: self._select_format(fid),
            )

    def sizeHint(self):  # noqa: N802
        from PyQt6.QtCore import QSize
        return QSize(180, 34)

    def minimumSizeHint(self):  # noqa: N802
        from PyQt6.QtCore import QSize
        return QSize(160, 34)

    # ── geometry ──────────────────────────────────────────────────────────────

    def _main_rect(self):
        from PyQt6.QtCore import QRect
        # כפתור שמירה — תופס את כל הרוחב מלבד ARROW_W מהימין
        return QRect(self._ARROW_W + 1, 0, self.width() - self._ARROW_W - 1, self.height())

    def _arrow_rect(self):
        from PyQt6.QtCore import QRect
        return QRect(0, 0, self._ARROW_W, self.height())

    # ── paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:  # noqa: N802
        from PyQt6.QtGui import QPainter, QPainterPath, QColor, QPen, QFontMetrics
        from PyQt6.QtCore import QRectF, Qt as _Qt

        # קרא צבעים עדכניים מהפלטה הנוכחית
        pal = _styles.get_palette()
        C_OUTLINE        = pal["OUTLINE"]
        C_DISABLED_BG    = pal["DISABLED_BG"]
        C_DISABLED_TEXT  = pal["DISABLED_TEXT"]
        C_PRIMARY_DIM    = pal["PRIMARY_DIM"]
        C_PRIMARY        = pal["PRIMARY"]
        C_SURFACE3       = pal["SURFACE3"]
        C_SURFACE1       = pal["SURFACE1"]

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self._enabled:
            border_c = QColor(C_OUTLINE)
            bg_c     = QColor(C_DISABLED_BG)
            text_c   = QColor(C_DISABLED_TEXT)
            arrow_bg = QColor(C_DISABLED_BG)
        else:
            border_c = QColor(C_PRIMARY_DIM)
            bg_c     = QColor(C_SURFACE3 if self._hover_main else "transparent")
            text_c   = QColor(C_PRIMARY)
            arrow_bg = QColor(C_SURFACE3 if self._hover_arrow else "transparent")

        w, h = self.width(), self.height()
        aw = self._ARROW_W
        r  = self._RADIUS

        # ── רקע כפתור חץ (שמאל) ──────────────────────────────────────────
        arrow_path = QPainterPath()
        arrow_rf = QRectF(0, 0, aw, h)
        arrow_path.moveTo(arrow_rf.right(), arrow_rf.bottom())
        arrow_path.lineTo(arrow_rf.left() + r, arrow_rf.bottom())
        arrow_path.arcTo(QRectF(arrow_rf.left(), arrow_rf.bottom()-r*2, r*2, r*2), 270, -90)
        arrow_path.lineTo(arrow_rf.left(), arrow_rf.top() + r)
        arrow_path.arcTo(QRectF(arrow_rf.left(), arrow_rf.top(), r*2, r*2), 180, -90)
        arrow_path.lineTo(arrow_rf.right(), arrow_rf.top())
        arrow_path.closeSubpath()
        p.setPen(_Qt.PenStyle.NoPen)
        p.setBrush(arrow_bg)
        p.drawPath(arrow_path)

        p.setPen(QPen(border_c, 1.5))
        p.setBrush(_Qt.BrushStyle.NoBrush)
        p.drawPath(arrow_path)

        # ── רקע כפתור ראשי (ימין) ─────────────────────────────────────────
        main_path = QPainterPath()
        main_rf = QRectF(aw, 0, w - aw, h)
        main_path.moveTo(main_rf.left(), main_rf.top())
        main_path.lineTo(main_rf.right() - r, main_rf.top())
        main_path.arcTo(QRectF(main_rf.right()-r*2, main_rf.top(), r*2, r*2), 90, -90)
        main_path.lineTo(main_rf.right(), main_rf.bottom() - r)
        main_path.arcTo(QRectF(main_rf.right()-r*2, main_rf.bottom()-r*2, r*2, r*2), 0, -90)
        main_path.lineTo(main_rf.left(), main_rf.bottom())
        main_path.closeSubpath()
        p.setPen(_Qt.PenStyle.NoPen)
        p.setBrush(bg_c)
        p.drawPath(main_path)

        p.setPen(QPen(border_c, 1.5))
        p.setBrush(_Qt.BrushStyle.NoBrush)
        p.drawPath(main_path)

        # ── מפריד ─────────────────────────────────────────────────────────
        p.setPen(QPen(border_c, 1))
        p.drawLine(aw, 4, aw, h - 4)

        # ── חץ (בכפתור השמאלי) ────────────────────────────────────────────
        p.setPen(QPen(text_c, 1.5, _Qt.PenStyle.SolidLine,
                      _Qt.PenCapStyle.RoundCap, _Qt.PenJoinStyle.RoundJoin))
        cx = aw // 2
        cy = h // 2
        p.drawLine(cx - 4, cy - 2, cx, cy + 2)
        p.drawLine(cx, cy + 2, cx + 4, cy - 2)

        # ── טקסט + אייקון כפתור ראשי ──────────────────────────────────────
        _, fmt_label, _ = self._current_fmt
        text = f"שמור כ-{fmt_label}"
        icon_color = C_PRIMARY if self._enabled else C_DISABLED_TEXT
        icon_px = qta.icon("fa5s.download", color=icon_color)
        icon_size = 14
        ico_img = icon_px.pixmap(icon_size, icon_size)

        font = self.font()
        fm = QFontMetrics(font)
        text_w = fm.horizontalAdvance(text)
        total_w = icon_size + 6 + text_w
        start_x = aw + (w - aw - total_w) // 2

        p.drawPixmap(start_x, (h - icon_size) // 2, ico_img)
        p.setPen(QPen(text_c))
        p.setFont(font)
        p.drawText(start_x + icon_size + 6, (h + fm.ascent() - fm.descent()) // 2, text)

        p.end()

    # ── mouse ─────────────────────────────────────────────────────────────────

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        x = int(event.position().x())
        in_arrow = x < self._ARROW_W
        self._hover_arrow = in_arrow and self._enabled
        self._hover_main  = not in_arrow and self._enabled
        if self._enabled:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover_main = self._hover_arrow = False
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if not self._enabled:
            return
        x = int(event.position().x())
        if x < self._ARROW_W:
            self._open_menu()
        else:
            self._on_save()

    # ── logic ─────────────────────────────────────────────────────────────────

    def _select_format(self, fmt_id: str) -> None:
        for f in _FORMATS:
            if f[0] == fmt_id:
                self._current_fmt = f
                break
        self.update()

    def _on_save(self) -> None:
        self.export_clicked.emit(self._current_fmt[0])

    def _open_menu(self) -> None:
        self._rebuild_fmt_menu()
        pos = self.mapToGlobal(self.rect().bottomLeft())
        self._fmt_menu.exec(pos)

    def set_enabled(self, enabled: bool) -> None:  # noqa: N802
        self._enabled = enabled
        self._hover_main = self._hover_arrow = False
        if enabled:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.update()

    def current_format(self) -> str:
        return self._current_fmt[0]


# ── SplitUploadButton ─────────────────────────────────────────────────────────
class SplitUploadButton(QWidget):
    """
    כפתור מפוצל לבחירת שיר / פתיחת פרויקט.
    חלק ימין (ראשי): בחר שיר  — כפתור ראשי ממולא (Primary)
    חלק שמאל (חץ):   תפריט עם 'פתח פרויקט'
    """

    upload_clicked       = Signal()
    open_project_clicked = Signal()

    _ARROW_W = 30
    _RADIUS  = 17

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.setFixedHeight(46)
        self.setMinimumWidth(160)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self._hover_main  = False
        self._hover_arrow = False
        self._song_loaded = False   # האם שיר כבר נטען

        # תפריט נפתח — נבנה בכל פתיחה
        self._menu = _rounded_menu(self)
        self._menu.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def set_song_loaded(self, loaded: bool) -> None:
        """קרא לאחר טעינת שיר — מחליף ל'החלף שיר' + אייקון רענון."""
        self._song_loaded = loaded
        self.update()

    def _rebuild_menu(self) -> None:
        self._menu.clear()
        c_secondary = _styles.get_palette()["SECONDARY"]
        self._menu.addAction(
            qta.icon("fa5s.folder", color=c_secondary),
            "פתח פרויקט",
            lambda: self.open_project_clicked.emit(),
        )

    def sizeHint(self):  # noqa: N802
        from PyQt6.QtCore import QSize
        return QSize(170, 34)

    def minimumSizeHint(self):  # noqa: N802
        from PyQt6.QtCore import QSize
        return QSize(150, 34)

    def _main_rect(self):
        from PyQt6.QtCore import QRect
        return QRect(self._ARROW_W + 1, 0, self.width() - self._ARROW_W - 1, self.height())

    def _arrow_rect(self):
        from PyQt6.QtCore import QRect
        return QRect(0, 0, self._ARROW_W, self.height())

    def paintEvent(self, event) -> None:  # noqa: N802
        from PyQt6.QtGui import QPainter, QPainterPath, QColor, QPen, QFontMetrics
        from PyQt6.QtCore import QRectF, Qt as _Qt

        # קרא צבעים עדכניים מהפלטה הנוכחית
        pal = _styles.get_palette()
        C_PRIMARY     = pal["PRIMARY"]
        C_PRIMARY_DIM = pal["PRIMARY_DIM"]
        C_ON_PRIMARY  = pal["ON_PRIMARY"]

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        _FILL       = QColor(C_PRIMARY_DIM if self._hover_main else C_PRIMARY)
        _ARROW_FILL = QColor(C_PRIMARY_DIM if self._hover_arrow else C_PRIMARY)
        _TEXT       = QColor(C_ON_PRIMARY)
        _BORDER     = QColor(C_PRIMARY_DIM)

        w, h = self.width(), self.height()
        aw = self._ARROW_W
        r  = self._RADIUS

        # ── רקע כפתור חץ (שמאל) ──────────────────────────────────────────
        arrow_path = QPainterPath()
        arrow_rf = QRectF(0, 0, aw, h)
        arrow_path.moveTo(arrow_rf.right(), arrow_rf.bottom())
        arrow_path.lineTo(arrow_rf.left() + r, arrow_rf.bottom())
        arrow_path.arcTo(QRectF(arrow_rf.left(), arrow_rf.bottom()-r*2, r*2, r*2), 270, -90)
        arrow_path.lineTo(arrow_rf.left(), arrow_rf.top() + r)
        arrow_path.arcTo(QRectF(arrow_rf.left(), arrow_rf.top(), r*2, r*2), 180, -90)
        arrow_path.lineTo(arrow_rf.right(), arrow_rf.top())
        arrow_path.closeSubpath()
        p.setPen(_Qt.PenStyle.NoPen)
        p.setBrush(_ARROW_FILL)
        p.drawPath(arrow_path)

        # ── רקע כפתור ראשי (ימין) ─────────────────────────────────────────
        main_path = QPainterPath()
        main_rf = QRectF(aw, 0, w - aw, h)
        main_path.moveTo(main_rf.left(), main_rf.top())
        main_path.lineTo(main_rf.right() - r, main_rf.top())
        main_path.arcTo(QRectF(main_rf.right()-r*2, main_rf.top(), r*2, r*2), 90, -90)
        main_path.lineTo(main_rf.right(), main_rf.bottom() - r)
        main_path.arcTo(QRectF(main_rf.right()-r*2, main_rf.bottom()-r*2, r*2, r*2), 0, -90)
        main_path.lineTo(main_rf.left(), main_rf.bottom())
        main_path.closeSubpath()
        p.setPen(_Qt.PenStyle.NoPen)
        p.setBrush(_FILL)
        p.drawPath(main_path)

        # ── מפריד ─────────────────────────────────────────────────────────
        p.setPen(QPen(_BORDER, 1))
        p.drawLine(aw, 4, aw, h - 4)

        # ── חץ (בכפתור השמאלי) ────────────────────────────────────────────
        p.setPen(QPen(_TEXT, 1.5, _Qt.PenStyle.SolidLine,
                      _Qt.PenCapStyle.RoundCap, _Qt.PenJoinStyle.RoundJoin))
        cx = aw // 2
        cy = h // 2
        p.drawLine(cx - 4, cy - 2, cx, cy + 2)
        p.drawLine(cx, cy + 2, cx + 4, cy - 2)

        # ── טקסט + אייקון כפתור ראשי ──────────────────────────────────────
        if self._song_loaded:
            text     = "החלף שיר"
            icon_name = "fa5s.sync-alt"
        else:
            text     = "בחר שיר"
            icon_name = "fa5s.folder-open"
        icon_px = qta.icon(icon_name, color=C_ON_PRIMARY)
        icon_size = 14
        ico_img = icon_px.pixmap(icon_size, icon_size)

        font = self.font()
        fm = QFontMetrics(font)
        text_w = fm.horizontalAdvance(text)
        total_w = icon_size + 6 + text_w
        start_x = aw + (w - aw - total_w) // 2

        p.drawPixmap(start_x, (h - icon_size) // 2, ico_img)
        p.setPen(QPen(_TEXT))
        p.setFont(font)
        p.drawText(start_x + icon_size + 6, (h + fm.ascent() - fm.descent()) // 2, text)

        p.end()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        x = int(event.position().x())
        self._hover_arrow = x < self._ARROW_W
        self._hover_main  = not self._hover_arrow
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover_main = self._hover_arrow = False
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        x = int(event.position().x())
        if x < self._ARROW_W:
            self._rebuild_menu()
            pos = self.mapToGlobal(self.rect().bottomLeft())
            self._menu.exec(pos)
        else:
            self.upload_clicked.emit()


# ── ToggleSwitch — defined in _shared.py, imported via _FORMATS import above ──


# ── SettingsDialog — moved to settings_dialog.py ─────────────────────────────
from kling_match.ui.settings_dialog import SettingsDialog  # noqa: E402


# ── SaveProjectDialog ─────────────────────────────────────────────────────────
class SaveProjectDialog(QDialog):
    """
    דיאלוג שמירת פרויקט.
    המשתמש מקליד שם פרויקט ובוחר תיקיית יעד (ברירת מחדל: Music/kling-Match/Projects).
    """

    def __init__(self, default_name: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        import os
        from kling_match.core.project_manager import ProjectManager

        self.setWindowTitle("שמור פרויקט")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setMinimumWidth(400)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self._projects_root = ProjectManager.default_projects_root()
        self._setup(default_name)

    def _setup(self, default_name: str) -> None:
        import os
        lay = QVBoxLayout(self)
        lay.setSpacing(14)
        lay.setContentsMargins(20, 20, 20, 16)

        # כותרת
        title = QLabel("שמור פרויקט")
        title.setStyleSheet(
            f"color: {COLOR_ON_SURFACE}; font-size: 11pt; font-weight: 700;"
            " background: transparent;"
        )
        lay.addWidget(title)

        # שם פרויקט
        name_lbl = QLabel("שם הפרויקט:")
        name_lbl.setStyleSheet(
            f"color: {COLOR_ON_SURFACE}; font-size: 9pt; background: transparent;"
        )
        lay.addWidget(name_lbl)

        self._name_edit = QLineEdit(default_name)
        self._name_edit.setPlaceholderText("לדוגמה: השיר שלי")
        self._name_edit.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._name_edit.selectAll()
        lay.addWidget(self._name_edit)

        # תיקיית שמירה
        folder_lbl = QLabel("תיקיית פרויקטים:")
        folder_lbl.setStyleSheet(
            f"color: {COLOR_ON_SURFACE}; font-size: 9pt; background: transparent;"
        )
        lay.addWidget(folder_lbl)

        folder_row = QHBoxLayout()
        folder_row.setSpacing(6)
        folder_row.setContentsMargins(0, 0, 0, 0)

        self._folder_edit = QLineEdit(self._projects_root)
        self._folder_edit.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._folder_edit.setReadOnly(True)
        self._folder_edit.setStyleSheet(
            f"color: {COLOR_MUTED}; font-size: 8pt;"
        )

        browse_btn = QPushButton()
        browse_btn.setIcon(qta.icon("fa5s.folder-open", color=COLOR_MUTED))
        browse_btn.setIconSize(QSize(12, 12))
        browse_btn.setFixedSize(24, 24)
        browse_btn.setToolTip("בחר תיקייה אחרת")
        browse_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        browse_btn.setStyleSheet(
            f"QPushButton {{ border-radius: 6px;"
            f" border: 1px solid {COLOR_OUTLINE_BRIGHT}; background: transparent; padding: 0; }}"
            f"QPushButton:hover {{ background: {COLOR_SURFACE3}; }}"
        )
        browse_btn.clicked.connect(self._browse_folder)

        # עוטף את השורה ב-widget עם LTR מפורש כדי למנוע היפוך מ-RTL של הדיאלוג
        folder_widget = QWidget()
        folder_widget.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        folder_widget_lay = QHBoxLayout(folder_widget)
        folder_widget_lay.setContentsMargins(0, 0, 0, 0)
        folder_widget_lay.setSpacing(6)
        folder_widget_lay.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        folder_widget_lay.addWidget(self._folder_edit, stretch=1)
        folder_widget_lay.addWidget(browse_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        folder_row.addWidget(folder_widget)
        lay.addLayout(folder_row)

        # תיאור תיקיית יעד
        self._dest_lbl = QLabel()
        self._dest_lbl.setStyleSheet(
            f"color: {COLOR_MUTED}; font-size: 8pt; background: transparent;"
        )
        self._dest_lbl.setWordWrap(True)
        self._name_edit.textChanged.connect(self._update_dest_label)
        self._update_dest_label()
        lay.addWidget(self._dest_lbl)

        lay.addSpacing(6)

        # כפתורים
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_btn.setText("שמור")
        self._ok_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.setText("ביטול")
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        self._name_edit.textChanged.connect(self._validate)
        self._validate()

    def _update_dest_label(self) -> None:
        import os
        name = self._name_edit.text().strip()
        if name:
            path = os.path.join(self._projects_root, name)
            self._dest_lbl.setText(f"יישמר ב: {path}")
        else:
            self._dest_lbl.setText("")

    def _validate(self) -> None:
        self._ok_btn.setEnabled(bool(self._name_edit.text().strip()))

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "בחר תיקיית פרויקטים", self._projects_root
        )
        if folder:
            self._projects_root = folder
            self._folder_edit.setText(folder)
            self._update_dest_label()

    def _on_accept(self) -> None:
        if self._name_edit.text().strip():
            self.accept()

    def project_name(self) -> str:
        return self._name_edit.text().strip()

    def projects_root(self) -> str:
        return self._projects_root


# ── _FadeSlider ───────────────────────────────────────────────────────────────
class _FadeSlider(QWidget):
    """
    סליידר Fade/Crossfade:
      שורה עליונה:  [ערך כחול]  ─── stretch ───  [שם]
      שורה תחתונה: [══════════ סליידר ══════════]
    """

    valueChanged = Signal(float)

    def __init__(self, label: str, max_sec: float = 5.0,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        self._ticks = int(max_sec / 0.25)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)
        outer.setAlignment(Qt.AlignmentFlag.AlignTop)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(0)

        self._val_lbl = QLabel("0.0s")
        top_row.addWidget(self._val_lbl)
        top_row.addStretch()

        name_lbl = QLabel(label)
        top_row.addWidget(name_lbl)
        self._name_lbl = name_lbl
        outer.addLayout(top_row)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, self._ticks)
        self._slider.setValue(0)
        self._slider.setSingleStep(1)
        self._slider.setPageStep(2)
        self._slider.setInvertedAppearance(True)
        self._slider.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._slider.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        outer.addWidget(self._slider)
        self._slider.valueChanged.connect(self._on_change)
        self.setMinimumWidth(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._refresh_label_styles()

    def _on_change(self, tick: int) -> None:
        sec = tick * 0.25
        self._val_lbl.setText(f"{sec:.1f}s")
        self.valueChanged.emit(sec)

    def value(self) -> float:
        return self._slider.value() * 0.25

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        super().setEnabled(enabled)
        self._slider.setEnabled(enabled)
        self._refresh_label_styles()

    def refresh_styles(self) -> None:
        """עדכן צבעי תוויות לפי הפלטה הנוכחית."""
        self._refresh_label_styles()

    def _refresh_label_styles(self) -> None:
        p = _styles.get_palette()
        enabled = self.isEnabled()
        val_color  = p["SECONDARY"]       if enabled else p["DISABLED_TEXT"]
        name_color = p["ON_SURFACE"]      if enabled else p["DISABLED_TEXT"]
        self._val_lbl.setStyleSheet(
            f"color: {val_color}; font-size: 9pt; font-weight: 600;"
            f" background: transparent;"
        )
        self._name_lbl.setStyleSheet(
            f"color: {name_color}; font-size: 9pt; background: transparent;"
        )


# ── TopPanel ──────────────────────────────────────────────────────────────────
class TopPanel(QWidget):
    """בחר שיר | נגן שיר  ·········  שם_קובץ · M:SS"""

    upload_clicked      = Signal()
    play_song_clicked   = Signal()
    open_project_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("TopPanel")
        self.setFixedHeight(54)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._setup()
        _styles.register_refresh_callback(self._refresh_play_btn_icon)

    def _refresh_play_btn_icon(self) -> None:
        """רענן אייקון כפתור ניגון לפי הפלטה הנוכחית."""
        playing = self._play_song_btn.isChecked()
        ico  = "fa5s.stop" if playing else "fa5s.play"
        self._play_song_btn.setIcon(
            qta.icon(ico, color=_styles.get_palette()["SECONDARY"])
        )

    def _setup(self) -> None:
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 4, 14, 4)
        row.setSpacing(8)

        self._upload_btn = SplitUploadButton(self)
        self._upload_btn.upload_clicked.connect(self.upload_clicked.emit)
        self._upload_btn.open_project_clicked.connect(self.open_project_clicked.emit)
        row.addWidget(self._upload_btn)

        self._play_song_btn = _btn("fa5s.play", "נגן שיר",
                                   color=COLOR_SECONDARY,
                                   tip="נגן/עצור את השיר המלא",
                                   checkable=True)
        self._play_song_btn.setObjectName("PlaySongButton")
        self._play_song_btn.toggled.connect(self._on_play_toggled)
        row.addWidget(self._play_song_btn)

        row.addStretch()

        self._filename_lbl = QLabel("")
        self._filename_lbl.setObjectName("FileNameLabel")
        self._filename_lbl.setToolTip("שם הקובץ הנוכחי")
        self._filename_lbl.setVisible(False)
        row.addWidget(self._filename_lbl)

        self._duration_lbl = QLabel("")
        self._duration_lbl.setObjectName("FileDurationLabel")
        self._duration_lbl.setToolTip("אורך השיר")
        self._duration_lbl.setVisible(False)
        row.addWidget(self._duration_lbl)

    def _on_play_toggled(self, checked: bool) -> None:
        ico  = "fa5s.stop" if checked else "fa5s.play"
        text = "עצור" if checked else "נגן שיר"
        self._play_song_btn.setIcon(qta.icon(ico, color=_styles.get_palette()["SECONDARY"]))
        self._play_song_btn.setText(f"  {text}")
        self.play_song_clicked.emit()

    def set_file_info(self, filename: str, duration: float) -> None:
        if not filename:
            self._filename_lbl.setText("")
            self._duration_lbl.setText("")
            self._filename_lbl.setVisible(False)
            self._duration_lbl.setVisible(False)
            self._upload_btn.set_song_loaded(False)
            return
        m, s = int(duration // 60), int(duration % 60)
        self._filename_lbl.setText(f"  {filename}  ")
        self._duration_lbl.setText(f"  {m}:{s:02d}  ")
        self._filename_lbl.setVisible(True)
        self._duration_lbl.setVisible(True)
        self._upload_btn.set_song_loaded(True)

    def set_song_duration(self, seconds: float) -> None:
        pass  # מיושם עכשיו דרך set_file_info

    def set_song_playing(self, playing: bool) -> None:
        self._play_song_btn.blockSignals(True)
        self._play_song_btn.setChecked(playing)
        ico  = "fa5s.stop" if playing else "fa5s.play"
        text = "עצור" if playing else "נגן שיר"
        self._play_song_btn.setIcon(qta.icon(ico, color=_styles.get_palette()["SECONDARY"]))
        self._play_song_btn.setText(f"  {text}")
        self._play_song_btn.blockSignals(False)


# ── InfoBar ───────────────────────────────────────────────────────────────────
class InfoBar(QWidget):
    """
    שורת מידע קבועה (ROW 2) — תמיד גלויה, גובה ~32px.

    פריסה (RTL):
      ימין:  כפתור "ערוך מקטעים" (disabled עד סיום ניתוח)
      אמצע: מכל ProgressBar (track תמיד גלוי, מילוי מוצג רק בניתוח)
      שמאל: תווית סטטוס (ריקה כשאין הודעה)
    """

    edit_toggled = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("InfoBar")
        self.setMinimumHeight(50)
        self.setMaximumHeight(54)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self.clear_status)
        self._setup()
        _styles.register_refresh_callback(self.refresh_styles)

    def _setup(self) -> None:
        from kling_match.ui.waveform_widget import CARD_MARGIN_H

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 6, 14, 6)
        row.setSpacing(8)
        row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # שמאל: תווית סטטוס
        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("StatusLabel")
        self._status_lbl.setMinimumWidth(180)
        self._status_lbl.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred
        )
        self._status_lbl.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        row.addWidget(self._status_lbl)

        # אמצע: מכל progress (track תמיד גלוי) — גובה קבוע 6px
        self._pb_container = QWidget()
        self._pb_container.setObjectName("ProgressContainer")
        self._pb_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._pb_container.setFixedHeight(6)
        pb_lay = QHBoxLayout(self._pb_container)
        pb_lay.setContentsMargins(CARD_MARGIN_H, 0, CARD_MARGIN_H, 0)
        pb_lay.setSpacing(0)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)
        pb_lay.addWidget(self._progress_bar)

        row.addWidget(self._pb_container, stretch=1, alignment=Qt.AlignmentFlag.AlignVCenter)

        # ימין: כפתור ערוך מקטעים — גובה קבוע 34px
        self._edit_btn = QPushButton()
        self._edit_btn.setObjectName("EditButton")
        self._edit_btn.setText("  ערוך מקטעים")
        self._edit_btn.setCheckable(True)
        self._edit_btn.setEnabled(False)
        self._edit_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._edit_btn.setToolTip("הפעל/כבה עריכת גבולות קטעים")
        self._edit_btn.setFixedHeight(34)
        self._edit_btn.toggled.connect(self._on_edit_toggled)
        row.addWidget(self._edit_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self.refresh_styles()

    # ── Public API ────────────────────────────────────────────────────────────

    def set_status(self, msg: str, timeout_ms: int = 0) -> None:
        self._status_lbl.setText(msg)
        self._status_timer.stop()
        if timeout_ms > 0:
            self._status_timer.start(timeout_ms)

    def clear_status(self) -> None:
        self._status_lbl.setText("")

    def set_progress(self, value: int) -> None:
        self._progress_bar.setValue(value)

    def set_progress_visible(self, visible: bool) -> None:
        # לא מסתירים — מאפסים ל-0 בסוף כדי שה-track יישאר גלוי
        if not visible:
            self._progress_bar.setValue(0)

    def set_edit_enabled(self, enabled: bool) -> None:
        self._edit_btn.setEnabled(enabled)
        self.refresh_styles()

    def _on_edit_toggled(self, checked: bool) -> None:
        """החלף טקסט ואייקון בעת הפעלת/כיבוי עריכה."""
        self.edit_toggled.emit(checked)
        self.refresh_styles()

    def refresh_styles(self) -> None:
        """עדכן צבעי כפתורי ואייקוני InfoBar לפי הפלטה הנוכחית."""
        p = _styles.get_palette()
        checked = self._edit_btn.isChecked()
        if checked:
            self._edit_btn.setText("  שמור")
            icon_color = p["PRIMARY"]
        else:
            self._edit_btn.setText("  ערוך מקטעים")
            icon_color = p["ON_SURFACE"]
        self._edit_btn.setIcon(qta.icon("fa5s.cut", color=icon_color))


# ── BottomPanel ───────────────────────────────────────────────────────────────
class BottomPanel(QWidget):
    """
    פאנל תחתון — שתי שורות:
      שורה 1: Fade In | Fade Out | Crossfade
      שורה 2: תצוגה מקדימה | שמור כ... | ⋯  ···  משך נבחר
    """

    preview_clicked   = Signal()
    stop_clicked      = Signal()
    export_clicked    = Signal(str)
    copy_json_clicked = Signal()
    save_project_clicked = Signal()
    fade_in_changed   = Signal(float)
    fade_out_changed  = Signal(float)
    crossfade_changed = Signal(float)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("BottomPanel")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._is_playing = False
        self._default_format = "mp3"
        self._setup()
        _styles.register_refresh_callback(self.refresh_all_styles)

    def _setup(self) -> None:
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(20, 10, 20, 10)
        main_lay.setSpacing(8)

        # ── שורה 1: סליידרים ─────────────────────────────────────────────
        slider_row = QHBoxLayout()
        slider_row.setSpacing(28)
        slider_row.setContentsMargins(0, 0, 0, 0)
        slider_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._fade_in   = _FadeSlider("Fade In",   max_sec=5.0)
        self._fade_out  = _FadeSlider("Fade Out",  max_sec=5.0)
        self._crossfade = _FadeSlider("Crossfade", max_sec=5.0)
        self._crossfade.setEnabled(False)

        self._fade_in.valueChanged.connect(self.fade_in_changed.emit)
        self._fade_out.valueChanged.connect(self.fade_out_changed.emit)
        self._crossfade.valueChanged.connect(self.crossfade_changed.emit)

        slider_row.addWidget(self._fade_in,   stretch=1)
        slider_row.addWidget(self._fade_out,  stretch=1)
        slider_row.addWidget(self._crossfade, stretch=1)
        main_lay.addLayout(slider_row)

        # ── separator ─────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        main_lay.addWidget(sep)

        # ── שורה 2: כפתורים ──────────────────────────────────────────────
        # פריסה: [משך נבחר]  stretch  [תצוגה מקדימה] [שמור] [⋯]  stretch  [⚙]
        # הכפתורים הראשיים ממורכזים, משך בצד ימין (RTL), הגדרות בצד שמאל
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.setContentsMargins(0, 0, 0, 0)

        # ── ימין (RTL): תווית משך ────────────────────────────────────────
        self._dur_lbl = QLabel("0:00")
        self._dur_lbl.setObjectName("DurationLabel")
        self._dur_lbl.setToolTip("משך הקטעים הנבחרים")
        btn_row.addWidget(self._dur_lbl)

        # stretch שמאלי — דוחף כפתורים למרכז
        btn_row.addStretch()

        # ── מרכז: כפתורים ראשיים ─────────────────────────────────────────
        self._preview_btn = _btn("fa5s.headphones", "תצוגה מקדימה",
                                 color=COLOR_SECONDARY,
                                 tip="השמע תצוגה מקדימה עם האפקטים")
        self._preview_btn.setObjectName("PreviewButton")
        self._preview_btn.setEnabled(False)
        self._preview_btn.clicked.connect(self._on_preview_clicked)
        btn_row.addWidget(self._preview_btn)

        # ── כפתור מפוצל: שמור ────────────────────────────────────────────
        self._split_save = SplitSaveButton(self)
        self._split_save.set_enabled(False)
        self._split_save.export_clicked.connect(self.export_clicked.emit)
        btn_row.addWidget(self._split_save)

        self._more_btn = QPushButton()
        self._more_btn.setIconSize(QSize(14, 14))
        self._more_btn.setToolTip("אפשרויות נוספות")
        self._more_btn.setFixedSize(36, 34)
        self._more_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._more_menu = _rounded_menu(self)
        self._more_menu.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._more_btn.clicked.connect(self._open_more_menu)
        btn_row.addWidget(self._more_btn)

        # stretch ימני — מרכז את הכפתורים
        btn_row.addStretch()

        # ── שמאל: תווית זמן ניתוח + כפתור הגדרות ───────────────────────
        self._analysis_time_lbl = QLabel("")
        self._analysis_time_lbl.setObjectName("AnalysisTimeLabel")
        self._analysis_time_lbl.setToolTip("זמן שלקח הניתוח האחרון")
        self._analysis_time_lbl.setStyleSheet(
            f"color: {COLOR_MUTED}; font-size: 8pt; background: transparent;"
        )
        self._analysis_time_lbl.setVisible(False)
        btn_row.addWidget(self._analysis_time_lbl)

        self._settings_btn = QPushButton()
        self._settings_btn.setIconSize(QSize(14, 14))
        self._settings_btn.setToolTip("הגדרות")
        self._settings_btn.setFixedSize(36, 34)
        self._settings_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._settings_btn.clicked.connect(self._open_settings)
        btn_row.addWidget(self._settings_btn)

        main_lay.addLayout(btn_row)
        # עדכן צבעים בהתאם לפלטה הנוכחית
        self._refresh_icon_styles()

    def _on_preview_clicked(self) -> None:
        if self._is_playing:
            self.stop_clicked.emit()
        else:
            self.preview_clicked.emit()

    def _refresh_icon_styles(self) -> None:
        """עדכן צבעי כפתורי האייקון בהתאם לפלטה הנוכחית."""
        p = _styles.get_palette()
        c_muted  = p["MUTED"]
        c_ob     = p["OUTLINE_BRIGHT"]
        c_s3     = p["SURFACE3"]
        icon_ss = (
            f"QPushButton {{ border-radius: 17px; border: 1.5px solid {c_ob};"
            f" background: transparent; padding: 0;"
            f" min-width: 36px; max-width: 36px; min-height: 34px; max-height: 34px; }}"
            f"QPushButton:hover {{ background: {c_s3}; border-color: {c_muted}; }}"
            f"QPushButton::menu-indicator {{ width: 0; height: 0; image: none; }}"
        )
        self._more_btn.setIcon(qta.icon("fa5s.ellipsis-h", color=c_muted))
        self._more_btn.setStyleSheet(icon_ss)
        self._settings_btn.setIcon(qta.icon("fa5s.cog", color=c_muted))
        self._settings_btn.setStyleSheet(icon_ss)

    def refresh_all_styles(self) -> None:
        """עדכן את כל הרכיבים הדינמיים בלוח התחתון לפי הפלטה הנוכחית."""
        p = _styles.get_palette()
        self._refresh_icon_styles()
        # סליידרים
        self._fade_in.refresh_styles()
        self._fade_out.refresh_styles()
        self._crossfade.refresh_styles()
        # תווית זמן ניתוח
        self._analysis_time_lbl.setStyleSheet(
            f"color: {p['MUTED']}; font-size: 8pt; background: transparent;"
        )
        # כפתור תצוגה מקדימה — רענן אייקון לפי המצב הנוכחי
        if self._is_playing:
            self._preview_btn.setIcon(qta.icon("fa5s.stop", color=p["ON_SURFACE"]))
        else:
            self._preview_btn.setIcon(qta.icon("fa5s.headphones", color=p["SECONDARY"]))

    def _open_more_menu(self) -> None:
        """בנה מחדש ופתח את תפריט האפשרויות עם צבעים עדכניים."""
        self._more_menu.clear()
        c = _styles.get_palette()["SECONDARY"]
        self._more_menu.addAction(
            qta.icon("fa5s.save", color=c), "שמור פרויקט",
            lambda: self.save_project_clicked.emit()
        )
        self._more_menu.addSeparator()
        self._more_menu.addAction(
            qta.icon("fa5s.file-export", color=c), "ייצוא כ-JSON",
            lambda: self.copy_json_clicked.emit()
        )
        self._more_menu.exec(
            self._more_btn.mapToGlobal(self._more_btn.rect().bottomLeft())
        )

    def _open_settings(self) -> None:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()

        dlg = SettingsDialog(current_format=self._default_format, parent=self)

        # תצוגה מקדימה חיה — הפעל/כבה stylesheet + רענן כפתורים מיד
        def _apply_preview(light: bool) -> None:
            _styles.apply_styles(app, light=light)
            self.refresh_all_styles()

        dlg.preview_mode_changed.connect(_apply_preview)

        result = dlg.exec()
        if result == QDialog.DialogCode.Accepted:
            self._default_format = dlg.selected_format()
            self._split_save._select_format(self._default_format)
            _styles.apply_styles(app, light=dlg.is_light_mode())
        # ביטול — dlg._on_cancel שלח preview_mode_changed לחזרה למצב מקורי
        # בכל מקרה, רענן את כל הרכיבים
        self.refresh_all_styles()

    def set_selection_duration(self, seconds: float) -> None:
        m, s = int(seconds // 60), int(seconds % 60)
        self._dur_lbl.setText(f"{m}:{s:02d}")

    def set_analysis_time(self, elapsed_sec: float) -> None:
        """הצגת זמן ניתוח ליד כפתור ההגדרות."""
        if elapsed_sec < 60:
            txt = f"ניתוח: {elapsed_sec:.0f}ש'"
        else:
            m = int(elapsed_sec // 60)
            s = int(elapsed_sec % 60)
            txt = f"ניתוח: {m}:{s:02d}ד'"
        self._analysis_time_lbl.setText(txt)
        self._analysis_time_lbl.setVisible(True)

    def clear_analysis_time(self) -> None:
        """איפוס תווית זמן הניתוח (בטעינת שיר חדש)."""
        self._analysis_time_lbl.setText("")
        self._analysis_time_lbl.setVisible(False)

    def set_preview_playing(self, playing: bool) -> None:
        self._is_playing = playing
        p = _styles.get_palette()
        if playing:
            self._preview_btn.setIcon(qta.icon("fa5s.stop", color=p["ON_SURFACE"]))
            self._preview_btn.setText("  עצור")
        else:
            self._preview_btn.setIcon(qta.icon("fa5s.headphones", color=p["SECONDARY"]))
            self._preview_btn.setText("  תצוגה מקדימה")

    def set_crossfade_enabled(self, enabled: bool) -> None:
        self._crossfade.setEnabled(enabled)

    def set_export_enabled(self, enabled: bool) -> None:
        self._preview_btn.setEnabled(enabled)
        self._split_save.set_enabled(enabled)

    def set_json_enabled(self, _: bool) -> None:
        pass

    def get_fade_in(self)   -> float: return self._fade_in.value()
    def get_fade_out(self)  -> float: return self._fade_out.value()
    def get_crossfade(self) -> float: return self._crossfade.value()
