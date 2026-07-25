"""
auto_updater.py — בדיקת עדכונים ל-Kling-Match.

Flow:
  1. בהפעלה: בדיקה שקטה ב-background מול GitHub API.
  2. השוואת tag מרוחק לגרסה מקומית.
  3. אם יש גרסה חדשה — פופאפ שמבקש אישור מהמשתמש.
  4. אישור → מוריד את updater.exe מה-release, מפעיל אותו, וסוגר את עצמו.
  5. updater.exe מוריד את update.zip, מחליף את _internal/app/, ומפעיל מחדש.

assets ב-GitHub Release:
  Kling-Match-setup.exe    ← מתקין מלא
  Kling-Match-portable.zip ← גרסה ניידת
  update.zip               ← עדכון קוד בלבד (לא כולל מודלים)
  updater.exe              ← כלי העדכון הנפרד
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from typing import Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal as Signal, Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# ── Constants ──────────────────────────────────────────────────────────────────
GITHUB_OWNER    = "Lotzi-tosafix"
GITHUB_REPO     = "Kling-Match"
API_URL         = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
REQUEST_TIMEOUT = 8
DOWNLOAD_TIMEOUT = 60   # timeout להורדת updater.exe (קטן — ~15MB)


# ── Version / install helpers ──────────────────────────────────────────────────

def _app_root() -> str:
    """תיקיית ה-EXE (frozen) או שורש הריפו (dev)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _install_type_file() -> str:
    return os.path.join(_app_root(), "install_type.txt")


def _target_app_dir() -> str:
    """
    התיקייה שבה נמצא קוד Python — זו שmake_update_zip.py ארז.
    תומך בשתי פריסות PyInstaller:
      flat:     <install>/app/           (גרסאות חדשות)
      internal: <install>/_internal/app/ (גרסאות ישנות)
    """
    if getattr(sys, "frozen", False):
        root = _app_root()
        flat = os.path.join(root, "app")
        if os.path.isdir(flat):
            return flat
        return os.path.join(root, "_internal", "app")
    return _app_root()


def _updater_exe_path() -> str:
    """נתיב ל-updater.exe שמגיע עם ההתקנה — ליד Kling-Match.exe."""
    return os.path.join(_app_root(), "updater.exe")


def get_local_version() -> str:
    from kling_match import __version__
    return __version__


def get_install_type() -> str:
    """'installer', 'portable', או 'dev'."""
    try:
        with open(_install_type_file(), encoding="utf-8") as f:
            return f.read().strip().lower()
    except FileNotFoundError:
        return "dev"


def _version_tuple(v: str) -> tuple:
    v = v.lstrip("v")
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return (0,)


# ── GitHub API ─────────────────────────────────────────────────────────────────

def fetch_latest_release() -> Optional[dict]:
    req = urllib.request.Request(
        API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"Kling-Match/{get_local_version()}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _find_asset(assets: list, *name_candidates: str) -> Optional[dict]:
    """מחפש אסט לפי שם — תומך בכמה שמות אפשריים."""
    for asset in assets:
        if asset.get("name", "").lower() in name_candidates:
            return asset
    return None


def check_for_update() -> Optional[dict]:
    """
    בודק אם יש גרסה חדשה.
    מחזיר dict עם {tag, version, notes, update_url, updater_url} אם כן, אחרת None.
    """
    data = fetch_latest_release()
    if not data:
        return None

    remote_tag    = data.get("tag_name", "").lstrip("v")
    local_version = get_local_version().lstrip("v")

    if _version_tuple(remote_tag) <= _version_tuple(local_version):
        return None

    assets = data.get("assets", [])

    # update.zip — מקבל גם "Kling-Match-update.zip" (גרסאות ישנות)
    update_asset = _find_asset(assets, "update.zip", "kling-match-update.zip")

    if not update_asset:
        return None

    return {
        "tag":        data.get("tag_name", remote_tag),
        "version":    remote_tag,
        "notes":      data.get("body", "").strip(),
        "update_url": update_asset["browser_download_url"],
    }


# ── Download updater.exe thread ────────────────────────────────────────────────

class _DownloadUpdaterThread(QThread):
    """מוריד את update.zip לתיקיית temp ומדווח התקדמות."""
    progress = Signal(int)
    done     = Signal(str)   # נתיב לקובץ update.zip שהורד
    failed   = Signal(str)

    def __init__(self, url: str, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._url = url

    def run(self) -> None:
        try:
            req = urllib.request.Request(
                self._url,
                headers={"User-Agent": f"Kling-Match/{get_local_version()}"},
            )
            with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                tmp = tempfile.NamedTemporaryFile(
                    delete=False, suffix=".zip", prefix="kling_update_"
                )
                downloaded = 0
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    tmp.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        self.progress.emit(int(downloaded / total * 100))
                tmp.close()
            self.done.emit(tmp.name)
        except Exception as exc:
            self.failed.emit(str(exc))


# ── Update dialog ──────────────────────────────────────────────────────────────

class UpdateDialog(QDialog):
    """
    פופאפ עדכון עם שלושה מצבים:
      1. הצעה — מציג גרסה + notes + כפתורי אישור/דחייה
      2. הורדה — progress bar של updater.exe
      3. שגיאה — הודעה
    """

    def __init__(self, update_info: dict, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._info   = update_info
        self._thread: Optional[_DownloadUpdaterThread] = None

        self.setWindowTitle("עדכון זמין — Kling-Match")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setMinimumWidth(440)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self._build_ui()

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        from kling_match.ui import styles as _st

        lay = QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)

        # ── header ────────────────────────────────────────────────────────────
        import qtawesome as qta
        header = QWidget()
        header.setStyleSheet(
            f"background: {_st.COLOR_SURFACE3};"
            f" border-bottom: 1px solid {_st.COLOR_OUTLINE_BRIGHT};"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 14, 20, 14)
        hl.setSpacing(10)
        ico = QLabel()
        ico.setPixmap(qta.icon("fa5s.arrow-circle-up",
                               color=_st.COLOR_PRIMARY).pixmap(20, 20))
        ico.setStyleSheet("background: transparent; border: none;")
        hl.addWidget(ico, 0, Qt.AlignmentFlag.AlignVCenter)
        title = QLabel(f"Kling-Match {self._info['tag']} זמינה!")
        title.setStyleSheet(
            f"color: {_st.COLOR_ON_SURFACE}; font-size: 12pt; font-weight: 700;"
            f" background: transparent; border: none;"
        )
        hl.addWidget(title, 1)
        lay.addWidget(header)

        # ── body ──────────────────────────────────────────────────────────────
        body = QWidget()
        body.setStyleSheet(f"background: {_st.COLOR_SURFACE3};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(20, 16, 20, 16)
        bl.setSpacing(10)

        sub = QLabel(
            f"הגרסה המותקנת: {get_local_version()}  →  חדשה: {self._info['version']}"
        )
        sub.setStyleSheet(
            f"color: {_st.COLOR_MUTED}; font-size: 9pt; background: transparent;"
        )
        bl.addWidget(sub)

        notes = self._info.get("notes", "")
        if notes:
            notes_lbl = QLabel(notes[:500] + ("…" if len(notes) > 500 else ""))
            notes_lbl.setWordWrap(True)
            notes_lbl.setStyleSheet(
                f"font-size: 9pt; color: {_st.COLOR_ON_SURFACE};"
                f" background: {_st.COLOR_SURFACE4};"
                f" border-radius: 8px; padding: 10px;"
            )
            bl.addWidget(notes_lbl)

        # progress (hidden until download starts)
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setVisible(False)
        bl.addWidget(self._progress)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"font-size: 9pt; color: {_st.COLOR_MUTED}; background: transparent;"
        )
        self._status_lbl.setVisible(False)
        bl.addWidget(self._status_lbl)

        lay.addWidget(body)

        # ── footer ────────────────────────────────────────────────────────────
        footer = QWidget()
        footer.setStyleSheet(
            f"background: {_st.COLOR_SURFACE3};"
            f" border-top: 1px solid {_st.COLOR_OUTLINE_BRIGHT};"
        )
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(20, 12, 20, 12)
        fl.setSpacing(10)
        fl.addStretch()

        self._skip_btn = QPushButton("אחר כך")
        self._skip_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._skip_btn.setStyleSheet(
            f"QPushButton {{ border-radius: 16px;"
            f" border: 1.5px solid {_st.COLOR_OUTLINE_BRIGHT};"
            f" background: transparent; color: {_st.COLOR_ON_SURFACE};"
            f" padding: 6px 20px; font-size: 10pt; min-height: 34px; }}"
            f"QPushButton:hover {{ background: {_st.COLOR_SURFACE4}; }}"
        )
        self._skip_btn.clicked.connect(self.reject)
        fl.addWidget(self._skip_btn)

        self._update_btn = QPushButton("עדכן עכשיו")
        self._update_btn.setDefault(True)
        self._update_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._update_btn.setStyleSheet(
            f"QPushButton {{ border-radius: 16px; border: none;"
            f" background: {_st.COLOR_PRIMARY}; color: #ffffff;"
            f" padding: 6px 24px; font-size: 10pt; font-weight: 600;"
            f" min-height: 34px; }}"
            f"QPushButton:hover {{ background: {_st.COLOR_PRIMARY_DIM}; }}"
            f"QPushButton:pressed {{ background: #8b3050; }}"
        )
        self._update_btn.clicked.connect(self._start_update)
        fl.addWidget(self._update_btn)
        lay.addWidget(footer)

    # ── slots ──────────────────────────────────────────────────────────────────

    def _start_update(self) -> None:
        self._update_btn.setEnabled(False)
        self._skip_btn.setEnabled(False)

        # בדוק שה-updater.exe קיים לפני שמתחילים
        updater = _updater_exe_path()
        if not os.path.isfile(updater):
            self._on_error(
                f"לא נמצא updater.exe במיקום:\n{updater}\n\n"
                "נסה להתקין מחדש מ-Kling-Match-setup.exe"
            )
            return

        self._progress.setVisible(True)
        self._status_lbl.setText("מוריד עדכון...")
        self._status_lbl.setVisible(True)

        self._thread = _DownloadUpdaterThread(self._info["update_url"], self)
        self._thread.progress.connect(self._progress.setValue)
        self._thread.done.connect(self._on_zip_downloaded)
        self._thread.failed.connect(self._on_error)
        self._thread.start()

    def _on_zip_downloaded(self, zip_path: str) -> None:
        self._status_lbl.setText("מפעיל עדכון...")

        updater       = _updater_exe_path()
        target_dir    = _target_app_dir()
        exe_to_restart = sys.executable

        subprocess.Popen(
            [updater, zip_path, target_dir, exe_to_restart],
            creationflags=subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP,
        )

        import PyQt6.QtWidgets as _qw
        _qw.QApplication.quit()

    def _on_error(self, msg: str) -> None:
        self._progress.setVisible(False)
        self._status_lbl.setText(f"שגיאה: {msg}")
        self._update_btn.setEnabled(True)
        self._skip_btn.setEnabled(True)


# ── Background check thread ────────────────────────────────────────────────────

class _CheckThread(QThread):
    update_available = Signal(dict)

    def run(self) -> None:
        info = check_for_update()
        if info:
            self.update_available.emit(info)


_check_thread: Optional[_CheckThread] = None


def start_update_check(parent: Optional[QWidget] = None) -> None:
    """
    מפעיל בדיקת עדכונים ברקע.
    נקרא פעם אחת אחרי שהחלון הראשי גלוי.
    """
    if get_install_type() == "dev":
        return

    global _check_thread
    _check_thread = _CheckThread()

    def _on_update(info: dict) -> None:
        dlg = UpdateDialog(info, parent=parent)
        dlg.exec()

    _check_thread.update_available.connect(_on_update)
    _check_thread.start()
