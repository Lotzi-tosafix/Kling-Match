"""
settings_dialog.py — פופאפ הגדרות של Kling-Match.

כולל:
  • מצב בהיר / כהה (תצוגה מקדימה חיה)
  • פורמט שמירה ברירת מחדל
  • אודות — גרסה + קישור GitHub
"""

from __future__ import annotations

import os

import qtawesome as qta
from PyQt6.QtCore import Qt, pyqtSignal as Signal, QUrl
from PyQt6.QtGui import QCursor, QDesktopServices
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

import kling_match.ui.styles as _styles
from kling_match import __version__
from kling_match.ui._shared import ToggleSwitch, FORMATS as _FORMATS

_GITHUB_URL = "https://github.com/Lotzi-tosafix/Kling-Match"

# ── מצב גלובלי (נשמר בין פתיחות) ────────────────────────────────────────────
_LIGHT_MODE: bool = False


class SettingsDialog(QDialog):
    """
    פופאפ הגדרות — פורמט שמירה ברירת מחדל + מצב בהיר/כהה + אודות.
    המתג משנה את המראה מיד (תצוגה מקדימה חיה).
    ביטול — מחזיר למצב הקודם.
    אישור — מאשר את השינוי.
    """

    preview_mode_changed = Signal(bool)

    def __init__(self, current_format: str = "mp3",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("הגדרות")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setMinimumWidth(400)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self._selected_fmt   = current_format
        self._original_light = _styles.is_light_mode()
        self._setup(current_format)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _section_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {_styles.COLOR_SECONDARY}; font-size: 9pt; font-weight: 700;"
            f" letter-spacing: 1px; background: transparent;"
            f" border-bottom: 1px solid {_styles.COLOR_OUTLINE_BRIGHT};"
            f" padding-bottom: 4px;"
        )
        return lbl

    def _card(self) -> tuple[QWidget, QHBoxLayout]:
        """מחזיר (widget, layout) של כרטיסיית הגדרה אחת."""
        card = QWidget()
        card.setStyleSheet(
            f"background: {_styles.COLOR_SURFACE4}; border-radius: 10px;"
        )
        lay = QHBoxLayout(card)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)
        return card, lay

    # ── build UI ──────────────────────────────────────────────────────────────

    def _setup(self, current_format: str) -> None:
        lay = QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)

        # ── כותרת ────────────────────────────────────────────────────────────
        header = QWidget()
        header.setStyleSheet(
            f"background: {_styles.COLOR_SURFACE3};"
            f" border-bottom: 1px solid {_styles.COLOR_OUTLINE_BRIGHT};"
        )
        header_lay = QHBoxLayout(header)
        header_lay.setContentsMargins(20, 14, 20, 14)
        header_lay.setSpacing(10)

        ico_lbl = QLabel()
        ico_lbl.setPixmap(
            qta.icon("fa5s.cog", color=_styles.COLOR_PRIMARY).pixmap(20, 20)
        )
        ico_lbl.setStyleSheet("background: transparent; border: none;")
        header_lay.addWidget(ico_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        title_lbl = QLabel("הגדרות")
        title_lbl.setStyleSheet(
            f"color: {_styles.COLOR_ON_SURFACE}; font-size: 13pt; font-weight: 700;"
            f" background: transparent; border: none;"
        )
        header_lay.addWidget(title_lbl, 1, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(header)

        # ── גוף ──────────────────────────────────────────────────────────────
        body = QWidget()
        body.setStyleSheet(f"background: {_styles.COLOR_SURFACE3};")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(20, 16, 20, 16)
        body_lay.setSpacing(12)

        # ── סעיף: מראה ───────────────────────────────────────────────────────
        body_lay.addWidget(self._section_title("מראה"))

        appearance_card, ac_lay = self._card()

        sun_ico = QLabel()
        sun_ico.setPixmap(
            qta.icon("fa5s.sun", color=_styles.COLOR_WARNING).pixmap(16, 16)
        )
        sun_ico.setStyleSheet("background: transparent; border: none;")
        ac_lay.addWidget(sun_ico, 0, Qt.AlignmentFlag.AlignVCenter)

        mode_lbl = QLabel("מצב בהיר")
        mode_lbl.setStyleSheet(
            f"color: {_styles.COLOR_ON_SURFACE}; font-size: 10pt;"
            f" background: transparent; border: none;"
        )
        ac_lay.addWidget(mode_lbl, 1, Qt.AlignmentFlag.AlignVCenter)

        self._toggle = ToggleSwitch(checked=_styles.is_light_mode(), parent=self)
        self._toggle.toggled.connect(self._on_toggle_preview)
        ac_lay.addWidget(self._toggle, 0, Qt.AlignmentFlag.AlignVCenter)

        body_lay.addWidget(appearance_card)
        body_lay.addSpacing(8)

        # ── סעיף: פורמט שמירה ────────────────────────────────────────────────
        body_lay.addWidget(self._section_title("פורמט שמירה ברירת מחדל"))

        self._btn_group = QButtonGroup(self)
        for fmt_id, fmt_label, fmt_desc in _FORMATS:
            desc_part = fmt_desc.split("·")[1].strip() if "·" in fmt_desc else fmt_desc

            fmt_card, fc_lay = self._card()

            audio_ico = QLabel()
            audio_ico.setPixmap(
                qta.icon("fa5s.file-audio",
                         color=_styles.COLOR_SECONDARY).pixmap(14, 14)
            )
            audio_ico.setStyleSheet("background: transparent; border: none;")
            fc_lay.addWidget(audio_ico, 0, Qt.AlignmentFlag.AlignVCenter)

            rb = QRadioButton(f"{fmt_label}  —  {desc_part}")
            rb.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            rb.setProperty("fmtId", fmt_id)
            rb.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            rb.setStyleSheet(
                f"QRadioButton {{ background: transparent; border: none;"
                f" color: {_styles.COLOR_ON_SURFACE}; font-size: 10pt; }}"
                f"QRadioButton::indicator {{"
                f"  width: 16px; height: 16px; border-radius: 8px;"
                f"  border: 2px solid {_styles.COLOR_OUTLINE_BRIGHT};"
                f"  background: {_styles.COLOR_SURFACE2};"
                f"}}"
                f"QRadioButton::indicator:checked {{"
                f"  background: {_styles.COLOR_PRIMARY};"
                f"  border-color: {_styles.COLOR_PRIMARY};"
                f"}}"
            )
            if fmt_id == current_format:
                rb.setChecked(True)
            self._btn_group.addButton(rb)
            fc_lay.addWidget(rb, 1, Qt.AlignmentFlag.AlignVCenter)
            body_lay.addWidget(fmt_card)

        body_lay.addSpacing(8)

        # ── סעיף: אודות ──────────────────────────────────────────────────────
        body_lay.addWidget(self._section_title("אודות"))

        about_card, ab_lay = self._card()

        app_ico = QLabel()
        app_ico.setPixmap(
            qta.icon("fa5s.tag", color=_styles.COLOR_MUTED).pixmap(14, 14)
        )
        app_ico.setStyleSheet("background: transparent; border: none;")
        ab_lay.addWidget(app_ico, 0, Qt.AlignmentFlag.AlignVCenter)

        about_text_lay = QHBoxLayout()
        about_text_lay.setSpacing(12)
        about_text_lay.setContentsMargins(0, 0, 0, 0)

        app_name_lbl = QLabel(f"Kling-Match  v{__version__}")
        app_name_lbl.setStyleSheet(
            f"color: {_styles.COLOR_ON_SURFACE}; font-size: 10pt; font-weight: 600;"
            f" background: transparent; border: none;"
        )
        about_text_lay.addWidget(app_name_lbl)

        github_btn = QPushButton("← GitHub")
        github_btn.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        github_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        github_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; padding: 0;"
            f" color: {_styles.COLOR_SECONDARY}; font-size: 10pt;"
            f" text-decoration: underline; }}"
            f"QPushButton:hover {{ color: {_styles.COLOR_PRIMARY}; }}"
        )
        github_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(_GITHUB_URL))
        )
        about_text_lay.addWidget(github_btn)

        ab_lay.addLayout(about_text_lay, 1)
        body_lay.addWidget(about_card)

        lay.addWidget(body)

        # ── footer ───────────────────────────────────────────────────────────
        footer = QWidget()
        footer.setStyleSheet(
            f"background: {_styles.COLOR_SURFACE3};"
            f" border-top: 1px solid {_styles.COLOR_OUTLINE_BRIGHT};"
        )
        footer_lay = QHBoxLayout(footer)
        footer_lay.setContentsMargins(20, 12, 20, 12)
        footer_lay.setSpacing(10)

        cancel_btn = QPushButton("ביטול")
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn.setStyleSheet(
            f"QPushButton {{ border-radius: 16px;"
            f" border: 1.5px solid {_styles.COLOR_OUTLINE_BRIGHT};"
            f" background: transparent; color: {_styles.COLOR_ON_SURFACE};"
            f" padding: 6px 20px; font-size: 10pt; min-height: 34px; }}"
            f"QPushButton:hover {{ background: {_styles.COLOR_SURFACE4};"
            f" border-color: {_styles.COLOR_SECONDARY};"
            f" color: {_styles.COLOR_SECONDARY}; }}"
        )
        cancel_btn.clicked.connect(self._on_cancel)

        ok_btn = QPushButton("אישור")
        ok_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        ok_btn.setStyleSheet(
            f"QPushButton {{ border-radius: 16px; border: none;"
            f" background: {_styles.COLOR_PRIMARY}; color: #ffffff;"
            f" padding: 6px 24px; font-size: 10pt; font-weight: 600;"
            f" min-height: 34px; }}"
            f"QPushButton:hover {{ background: {_styles.COLOR_PRIMARY_DIM}; }}"
            f"QPushButton:pressed {{ background: #8b3050; }}"
        )
        ok_btn.clicked.connect(self._on_accept)

        footer_lay.addStretch()
        footer_lay.addWidget(cancel_btn)
        footer_lay.addWidget(ok_btn)
        lay.addWidget(footer)

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_toggle_preview(self, light: bool) -> None:
        self.preview_mode_changed.emit(light)

    def _on_cancel(self) -> None:
        if _styles.is_light_mode() != self._original_light:
            self.preview_mode_changed.emit(self._original_light)
        self.reject()

    def _on_accept(self) -> None:
        global _LIGHT_MODE
        checked = self._btn_group.checkedButton()
        if checked:
            self._selected_fmt = checked.property("fmtId")
        _LIGHT_MODE = self._toggle.isChecked()
        self.accept()

    def selected_format(self) -> str:
        return self._selected_fmt

    def is_light_mode(self) -> bool:
        return self._toggle.isChecked()
