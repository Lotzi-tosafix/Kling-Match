"""
styles.py — עיצוב Material 3 לאפליקציית קלינג-Match
תומך מצב כהה (ברירת מחדל) ומצב בהיר.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

# ── פלטת צבעים — מצב כהה ────────────────────────────────────────────────────
_DARK = dict(
    PRIMARY        = "#DA627D",
    PRIMARY_DIM    = "#b34d63",
    SECONDARY      = "#87CEFA",
    SECONDARY_DIM  = "#5aaed4",
    BG             = "#0d0d1c",
    SURFACE1       = "#161628",
    SURFACE2       = "#1c1c35",
    SURFACE3       = "#232342",
    SURFACE4       = "#2a2a52",
    OUTLINE        = "#2a2a50",
    OUTLINE_BRIGHT = "#3a3a68",
    ON_SURFACE     = "#eeeef8",
    ON_PRIMARY     = "#ffffff",
    ON_SECONDARY   = "#0d0d1c",
    MUTED          = "#7878a0",
    DISABLED_TEXT  = "#40405c",
    DISABLED_BG    = "#111120",
    SUCCESS        = "#4caf88",
    WARNING        = "#f0a060",
    ERROR          = "#ef5350",
)

# ── פלטת צבעים — מצב בהיר ────────────────────────────────────────────────────
_LIGHT = dict(
    PRIMARY        = "#c0395a",
    PRIMARY_DIM    = "#9e2d49",
    SECONDARY      = "#1a78b4",
    SECONDARY_DIM  = "#155e8e",
    BG             = "#f0f0f8",
    SURFACE1       = "#ffffff",
    SURFACE2       = "#e8e8f4",
    SURFACE3       = "#dcdcee",
    SURFACE4       = "#d0d0e4",
    OUTLINE        = "#b0b0cc",
    OUTLINE_BRIGHT = "#8888aa",
    ON_SURFACE     = "#1a1a2e",
    ON_PRIMARY     = "#ffffff",
    ON_SECONDARY   = "#ffffff",
    MUTED          = "#5858805",
    DISABLED_TEXT  = "#a0a0b8",
    DISABLED_BG    = "#e0e0ee",
    SUCCESS        = "#2e7d56",
    WARNING        = "#c07020",
    ERROR          = "#c62828",
)

# תיקון typo בשדה MUTED של _LIGHT
_LIGHT["MUTED"] = "#585880"

FONT_FAMILY = "Segoe UI"
FONT_SIZE   = 10

# ── מצב נוכחי ─────────────────────────────────────────────────────────────────
_current_palette = _DARK

# ── קיצורי גישה לצבעים הנוכחיים (מעודכנים ע"י apply_styles) ─────────────────
COLOR_PRIMARY        = _DARK["PRIMARY"]
COLOR_PRIMARY_DIM    = _DARK["PRIMARY_DIM"]
COLOR_SECONDARY      = _DARK["SECONDARY"]
COLOR_SECONDARY_DIM  = _DARK["SECONDARY_DIM"]
COLOR_BG             = _DARK["BG"]
COLOR_SURFACE1       = _DARK["SURFACE1"]
COLOR_SURFACE2       = _DARK["SURFACE2"]
COLOR_SURFACE3       = _DARK["SURFACE3"]
COLOR_SURFACE4       = _DARK["SURFACE4"]
COLOR_OUTLINE        = _DARK["OUTLINE"]
COLOR_OUTLINE_BRIGHT = _DARK["OUTLINE_BRIGHT"]
COLOR_ON_SURFACE     = _DARK["ON_SURFACE"]
COLOR_ON_PRIMARY     = _DARK["ON_PRIMARY"]
COLOR_ON_SECONDARY   = _DARK["ON_SECONDARY"]
COLOR_MUTED          = _DARK["MUTED"]
COLOR_DISABLED_TEXT  = _DARK["DISABLED_TEXT"]
COLOR_DISABLED_BG    = _DARK["DISABLED_BG"]
COLOR_SUCCESS        = _DARK["SUCCESS"]
COLOR_WARNING        = _DARK["WARNING"]
COLOR_ERROR          = _DARK["ERROR"]


def _build_stylesheet(p: dict) -> str:
    """בונה stylesheet דינמי לפי פלטה נתונה."""
    return f"""

* {{ outline: none; }}

QWidget {{
    background-color: {p['SURFACE1']};
    color: {p['ON_SURFACE']};
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 10pt;
}}

QMainWindow {{ background-color: {p['BG']}; }}

/* ── BUTTONS ─────────────────────────────────────────────────────── */
QPushButton {{
    background-color: transparent;
    color: {p['ON_SURFACE']};
    border: 1.5px solid {p['OUTLINE_BRIGHT']};
    border-radius: 18px;
    padding: 5px 18px;
    font-size: 10pt;
    font-weight: 500;
    min-height: 34px;
    min-width: 60px;
}}
QPushButton:hover {{
    background-color: {p['SURFACE3']};
    border-color: {p['SECONDARY']};
    color: {p['SECONDARY']};
}}
QPushButton:pressed {{
    background-color: {p['PRIMARY_DIM']};
    border-color: {p['PRIMARY_DIM']};
    color: {p['ON_PRIMARY']};
}}
QPushButton:checked {{
    background-color: {p['PRIMARY']};
    border-color: {p['PRIMARY']};
    color: {p['ON_PRIMARY']};
    font-weight: 600;
}}
QPushButton:checked:hover {{
    background-color: {p['PRIMARY_DIM']};
    border-color: {p['PRIMARY_DIM']};
}}
QPushButton:disabled {{
    background-color: {p['DISABLED_BG']};
    color: {p['DISABLED_TEXT']};
    border-color: {p['OUTLINE']};
}}

/* ── PLAY SONG — Outlined Secondary ─────────────────────────────── */
#PlaySongButton {{
    background-color: transparent;
    color: {p['SECONDARY']};
    border: 1.5px solid {p['SECONDARY_DIM']};
    border-radius: 18px;
    padding: 5px 18px;
    font-weight: 600;
    min-height: 34px;
}}
#PlaySongButton:hover {{
    background-color: {p['SURFACE3']};
    border-color: {p['SECONDARY']};
    color: {p['SECONDARY']};
}}
#PlaySongButton:pressed {{
    background-color: {p['SECONDARY_DIM']};
    color: {p['ON_SECONDARY']};
}}
#PlaySongButton:checked {{
    background-color: {p['SECONDARY_DIM']};
    border-color: {p['SECONDARY_DIM']};
    color: {p['ON_SECONDARY']};
}}

/* ── PREVIEW — Outlined Secondary ───────────────────────────── */
#PreviewButton {{
    background-color: transparent;
    color: {p['ON_SURFACE']};
    border: 1.5px solid {p['OUTLINE_BRIGHT']};
    border-radius: 18px;
    padding: 5px 20px;
    font-weight: 600;
    min-height: 34px;
}}
#PreviewButton:enabled {{
    color: {p['SECONDARY']};
    border-color: {p['SECONDARY_DIM']};
}}
#PreviewButton:hover  {{ background-color: {p['SURFACE3']}; border-color: {p['SECONDARY']}; color: {p['SECONDARY']}; }}
#PreviewButton:pressed {{ background-color: {p['SECONDARY_DIM']}; color: {p['ON_SECONDARY']}; border: none; }}
#PreviewButton:disabled {{
    background-color: {p['DISABLED_BG']};
    color: {p['DISABLED_TEXT']};
    border: 1.5px solid {p['OUTLINE']};
}}

/* ── SAVE — Outlined Primary ─────────────────────────────────────── */
#SaveButton {{
    background-color: transparent;
    color: {p['PRIMARY']};
    border: 1.5px solid {p['PRIMARY_DIM']};
    border-radius: 18px;
    padding: 5px 18px;
    font-weight: 600;
    min-height: 34px;
}}
#SaveButton:hover {{
    background-color: {p['SURFACE3']};
    border-color: {p['PRIMARY']};
}}
#SaveButton:pressed {{
    background-color: {p['PRIMARY_DIM']};
    color: {p['ON_PRIMARY']};
}}
#SaveButton:disabled {{
    background-color: {p['DISABLED_BG']};
    color: {p['DISABLED_TEXT']};
    border-color: {p['OUTLINE']};
}}

/* ── PROGRESS BAR ────────────────────────────────────────────────── */
QProgressBar {{
    background-color: {p['SURFACE2']};
    border: none;
    border-radius: 3px;
    max-height: 4px;
    min-height: 4px;
}}
QProgressBar::chunk {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {p['PRIMARY']}, stop:1 {p['SECONDARY']}
    );
    border-radius: 3px;
}}

/* ── SLIDERS — Fade / Crossfade ──────────────────────────────────── */
QSlider {{
    border: none;
    background: transparent;
}}
QSlider::groove:horizontal {{
    height: 4px;
    background-color: {p['SURFACE3']};
    border-radius: 2px;
    border: none;
    margin: 0;
}}
QSlider::sub-page:horizontal {{
    background-color: {p['SURFACE3']};
    border-radius: 2px;
    height: 4px;
    border: none;
}}
QSlider::add-page:horizontal {{
    background-color: {p['SECONDARY']};
    border-radius: 2px;
    height: 4px;
    border: none;
}}
QSlider::handle:horizontal {{
    background-color: {p['SECONDARY']};
    border: 2px solid {p['SURFACE1']};
    width: 14px;
    height: 14px;
    border-radius: 7px;
    margin: -5px 0;
}}
QSlider::handle:horizontal:hover {{
    background-color: {p['PRIMARY']};
    border-color: {p['SURFACE1']};
    width: 16px;
    height: 16px;
    border-radius: 8px;
    margin: -6px 0;
}}
QSlider::handle:horizontal:disabled {{
    background-color: {p['DISABLED_TEXT']};
    border-color: {p['OUTLINE']};
}}
QSlider:disabled::sub-page:horizontal,
QSlider:disabled::add-page:horizontal {{
    background-color: {p['DISABLED_TEXT']};
}}

/* ── STATUS BAR ──────────────────────────────────────────────────── */
QStatusBar {{
    background-color: {p['BG']};
    color: {p['MUTED']};
    border-top: 1px solid {p['OUTLINE']};
    font-size: 9pt;
    padding: 3px 12px;
}}
QStatusBar::item {{ border: none; }}

/* ── MENUS ───────────────────────────────────────────────────────── */
QMenu {{
    background-color: {p['SURFACE4']};
    color: {p['ON_SURFACE']};
    border: 1px solid {p['OUTLINE_BRIGHT']};
    border-radius: 12px;
    padding: 6px 4px;
    font-size: 10pt;
}}
QMenu::item {{
    padding: 8px 28px 8px 16px;
    border-radius: 8px;
    margin: 1px 4px;
    min-width: 130px;
}}
QMenu::item:selected {{ background-color: {p['SURFACE3']}; color: {p['SECONDARY']}; }}
QMenu::item:disabled {{ color: {p['DISABLED_TEXT']}; }}
QMenu::separator {{
    height: 1px;
    background-color: {p['OUTLINE']};
    margin: 4px 10px;
}}

/* ── LABELS ──────────────────────────────────────────────────────── */
QLabel {{ background-color: transparent; color: {p['ON_SURFACE']}; }}

#DurationLabel {{
    color: {p['SECONDARY']};
    font-size: 12pt;
    font-weight: 700;
    background-color: transparent;
}}

#SongDurationLabel {{
    color: {p['MUTED']};
    font-size: 9pt;
    background-color: transparent;
}}

/* ── STATUS TOAST ────────────────────────────────────────────────── */
#StatusToast {{
    background-color: {p['SURFACE3']};
    color: {p['MUTED']};
    border-top: 1px solid {p['OUTLINE']};
    font-size: 9pt;
    padding: 4px 16px;
    border-radius: 0px;
}}

/* ── SCROLLBARS ──────────────────────────────────────────────────── */
QScrollBar:horizontal {{ background: transparent; height: 5px; border-radius: 2px; margin: 0; }}
QScrollBar:vertical {{ background: transparent; width: 5px; border-radius: 2px; margin: 0; }}
QScrollBar::handle:horizontal, QScrollBar::handle:vertical {{
    background-color: {p['OUTLINE_BRIGHT']};
    border-radius: 2px;
    min-width: 20px; min-height: 20px;
}}
QScrollBar::handle:hover {{ background-color: {p['PRIMARY']}; }}
QScrollBar::add-line, QScrollBar::sub-line,
QScrollBar::add-page, QScrollBar::sub-page {{
    width: 0; height: 0; background: transparent;
}}

/* ── MESSAGE BOX ─────────────────────────────────────────────────── */
QMessageBox {{ background-color: {p['SURFACE1']}; }}
QMessageBox QLabel {{
    color: {p['ON_SURFACE']};
    font-size: 10pt;
    padding: 6px;
    background-color: transparent;
}}

/* ── WAVEFORM CARD ───────────────────────────────────────────────── */
#WaveformCard {{
    background-color: {p['BG']};
    border: 1px solid {p['OUTLINE']};
    border-radius: 16px;
}}

/* ── PANELS ──────────────────────────────────────────────────────── */
#TopPanel {{
    background-color: {p['SURFACE2']};
    border-bottom: 1px solid {p['OUTLINE']};
}}
#BottomPanel {{
    background-color: {p['BG']};
    border-top: 1px solid {p['OUTLINE']};
}}
#BottomPanel QWidget {{
    background-color: transparent;
}}
#BottomPanel QLabel {{
    background-color: transparent;
}}

/* ── INFO BAR ────────────────────────────────────────────────────── */
#InfoBar {{
    background-color: {p['SURFACE2']};
    border-bottom: 1px solid {p['OUTLINE']};
}}
#InfoBar QWidget {{
    background-color: transparent;
}}
#InfoBar QProgressBar {{
    min-height: 6px;
    max-height: 6px;
    border-radius: 3px;
    background-color: transparent;
    border: none;
}}
#InfoBar QProgressBar::chunk {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {p['PRIMARY']}, stop:1 {p['SECONDARY']}
    );
    border-radius: 3px;
}}

/* ── FILE NAME & DURATION LABELS (TopPanel) ──────────────────────── */
#FileNameLabel {{
    color: {p['ON_SURFACE']};
    font-size: 10pt;
    font-weight: 600;
    background-color: {p['SURFACE3']};
    border: 1px solid {p['OUTLINE_BRIGHT']};
    border-radius: 10px;
    padding: 2px 10px;
}}
#FileDurationLabel {{
    color: {p['SECONDARY']};
    font-size: 10pt;
    font-weight: 700;
    background-color: {p['SURFACE3']};
    border: 1px solid {p['OUTLINE_BRIGHT']};
    border-radius: 10px;
    padding: 2px 10px;
}}

/* ── STATUS LABEL (InfoBar) ──────────────────────────────────────── */
#StatusLabel {{
    color: {p['ON_SURFACE']};
    font-size: 10pt;
    font-weight: 600;
    background: transparent;
}}

/* ── PROGRESS CONTAINER (track — always visible) ─────────────────── */
#ProgressContainer {{
    background-color: {p['SURFACE3']};
    border-radius: 5px;
    min-height: 6px;
    max-height: 6px;
}}

/* ── EDIT BUTTON — checked state מותאם ─────────────────────────── */
#EditButton {{
    color: {p['ON_SURFACE']};
}}
#EditButton:checked {{
    background-color: transparent;
    border-color: {p['PRIMARY']};
    color: {p['PRIMARY']};
    font-weight: 700;
}}
#EditButton:checked:hover {{
    background-color: {p['SURFACE3']};
    border-color: {p['PRIMARY']};
    color: {p['PRIMARY']};
}}
#EditButton:disabled {{
    color: {p['DISABLED_TEXT']};
    border-color: {p['OUTLINE']};
    background-color: {p['DISABLED_BG']};
}}

/* ── SEPARATORS ──────────────────────────────────────────────────── */
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    color: {p['OUTLINE']};
    background-color: {p['OUTLINE']};
    border: none;
    max-height: 1px; min-height: 1px;
}}

/* ── LINE EDIT ───────────────────────────────────────────────────── */
QLineEdit {{
    background-color: {p['SURFACE2']};
    color: {p['ON_SURFACE']};
    border: 1.5px solid {p['OUTLINE_BRIGHT']};
    border-radius: 8px;
    padding: 4px 10px;
    font-size: 10pt;
}}
QLineEdit:focus {{
    border-color: {p['PRIMARY']};
}}
"""


# ── stylesheet מוכן לכל מצב ──────────────────────────────────────────────────
GLOBAL_STYLESHEET = _build_stylesheet(_DARK)


# ── רשימת callbacks לרענון ─────────────────────────────────────────────────
_refresh_callbacks: list = []


def register_refresh_callback(fn) -> None:
    """רשום פונקציה שתיקרא בכל פעם שהפלטה משתנה."""
    if fn not in _refresh_callbacks:
        _refresh_callbacks.append(fn)


def apply_styles(app: QApplication, light: bool = False) -> None:
    """מחיל עיצוב על האפליקציה. light=True להפעלת מצב בהיר."""
    global _current_palette
    global COLOR_PRIMARY, COLOR_PRIMARY_DIM, COLOR_SECONDARY, COLOR_SECONDARY_DIM
    global COLOR_BG, COLOR_SURFACE1, COLOR_SURFACE2, COLOR_SURFACE3, COLOR_SURFACE4
    global COLOR_OUTLINE, COLOR_OUTLINE_BRIGHT, COLOR_ON_SURFACE, COLOR_ON_PRIMARY
    global COLOR_ON_SECONDARY, COLOR_MUTED, COLOR_DISABLED_TEXT, COLOR_DISABLED_BG
    global COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, GLOBAL_STYLESHEET

    _current_palette = _LIGHT if light else _DARK
    p = _current_palette

    # עדכון קבועי הצבע הגלובליים
    COLOR_PRIMARY        = p["PRIMARY"]
    COLOR_PRIMARY_DIM    = p["PRIMARY_DIM"]
    COLOR_SECONDARY      = p["SECONDARY"]
    COLOR_SECONDARY_DIM  = p["SECONDARY_DIM"]
    COLOR_BG             = p["BG"]
    COLOR_SURFACE1       = p["SURFACE1"]
    COLOR_SURFACE2       = p["SURFACE2"]
    COLOR_SURFACE3       = p["SURFACE3"]
    COLOR_SURFACE4       = p["SURFACE4"]
    COLOR_OUTLINE        = p["OUTLINE"]
    COLOR_OUTLINE_BRIGHT = p["OUTLINE_BRIGHT"]
    COLOR_ON_SURFACE     = p["ON_SURFACE"]
    COLOR_ON_PRIMARY     = p["ON_PRIMARY"]
    COLOR_ON_SECONDARY   = p["ON_SECONDARY"]
    COLOR_MUTED          = p["MUTED"]
    COLOR_DISABLED_TEXT  = p["DISABLED_TEXT"]
    COLOR_DISABLED_BG    = p["DISABLED_BG"]
    COLOR_SUCCESS        = p["SUCCESS"]
    COLOR_WARNING        = p["WARNING"]
    COLOR_ERROR          = p["ERROR"]
    GLOBAL_STYLESHEET    = _build_stylesheet(p)

    app.setStyle("Fusion")
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    app.setStyleSheet(GLOBAL_STYLESHEET)
    font = QFont(FONT_FAMILY, FONT_SIZE)
    app.setFont(font)

    # רענן ציור של כל הווידג'טים (חשוב לווידג'טים שמציירים ידנית)
    for widget in app.allWidgets():
        widget.update()

    # קרא לכל callbacks שנרשמו לרענון סגנונות דינמיים
    for fn in list(_refresh_callbacks):
        try:
            fn()
        except Exception:
            pass


def is_light_mode() -> bool:
    """מחזיר True אם המצב הנוכחי הוא מצב בהיר."""
    return _current_palette is _LIGHT


def get_palette() -> dict:
    """מחזיר את הפלטה הנוכחית."""
    return _current_palette
