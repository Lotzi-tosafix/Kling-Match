"""
updater.py — Kling-Match standalone updater.

Usage (called by Kling-Match automatically):
    updater.exe <zip_path> <target_dir> <exe_to_restart>

    zip_path       — נתיב לקובץ update.zip שהורד כבר ע"י Kling-Match
    target_dir     — נתיב ל-_internal\\app\\ (התיקייה להחלפה)
    exe_to_restart — נתיב ל-Kling-Match.exe (מופעל אחרי העדכון)

The updater:
  1. מציג חלון progress קטן.
  2. מחלץ את update.zip ל-target_dir (מחליף app/).
  3. מוחק את ה-zip הזמני.
  4. מפעיל את exe_to_restart ויוצא.

On any error: restores backup and shows an error dialog.
"""

from __future__ import annotations

import os
import shutil
import sys
import zipfile

from PyQt6.QtCore import Qt, QThread, pyqtSignal as Signal
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMessageBox,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

# ── colour palette (dark, matches main app) ───────────────────────────────────
_BG       = "#0d0d1c"
_SURFACE  = "#161628"
_PRIMARY  = "#DA627D"
_SECONDARY= "#87CEFA"
_TEXT     = "#eeeef8"
_MUTED    = "#7878a0"
_OUTLINE  = "#2a2a50"

_STYLE = f"""
QWidget   {{ background: {_BG}; color: {_TEXT}; font-family: 'Segoe UI'; font-size: 10pt; }}
QLabel    {{ background: transparent; }}
QProgressBar {{
    background: {_SURFACE}; border: none; border-radius: 4px;
    min-height: 8px; max-height: 8px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {_PRIMARY}, stop:1 {_SECONDARY});
    border-radius: 4px;
}}
"""


# ── Apply thread ──────────────────────────────────────────────────────────────

class _ApplyThread(QThread):
    """מחיל את update.zip בthread נפרד."""
    done   = Signal()
    failed = Signal(str)

    def __init__(self, zip_path: str, target_dir: str) -> None:
        super().__init__()
        self._zip_path  = zip_path
        self._target_dir = target_dir

    def run(self) -> None:
        try:
            _extract_update(self._zip_path, self._target_dir)
            self.done.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            try:
                if os.path.isfile(self._zip_path):
                    os.unlink(self._zip_path)
            except OSError:
                pass


def _extract_update(zip_path: str, target_dir: str) -> None:
    """
    מחלץ את update.zip ל-target_dir.
    מצפה למבנה: app/kling_match/..., app/version.txt וכו'.
    מסיר את הקידומת "app/" ומחלץ ישירות ל-target_dir.
    שומר גיבוי ומשחזר אותו אם יש שגיאה.
    """
    backup = target_dir + ".bak"

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()

    if not all(n.startswith("app/") or n == "app/" for n in names):
        raise ValueError("מבנה קובץ העדכון שגוי — לא כל הרשומות תחת app/")

    if os.path.isdir(backup):
        shutil.rmtree(backup)
    if os.path.isdir(target_dir):
        shutil.copytree(target_dir, backup)

    try:
        if os.path.isdir(target_dir):
            shutil.rmtree(target_dir)
        os.makedirs(target_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.infolist():
                rel = member.filename[len("app/"):]
                if not rel:
                    continue
                dest = os.path.join(target_dir, rel.replace("/", os.sep))
                if member.is_dir():
                    os.makedirs(dest, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with zf.open(member) as src, open(dest, "wb") as dst:
                        shutil.copyfileobj(src, dst)

        if os.path.isdir(backup):
            shutil.rmtree(backup)

    except Exception:
        if os.path.isdir(backup):
            if os.path.isdir(target_dir):
                shutil.rmtree(target_dir)
            shutil.copytree(backup, target_dir)
        raise


# ── Main window ────────────────────────────────────────────────────────────────

class UpdaterWindow(QWidget):

    def __init__(self, zip_path: str, target_dir: str, exe_to_restart: str) -> None:
        super().__init__()
        self._zip_path      = zip_path
        self._target_dir    = target_dir
        self._exe_to_restart = exe_to_restart
        self._thread: _ApplyThread | None = None

        self.setWindowTitle("Kling-Match — מעדכן")
        self.setFixedSize(420, 140)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowTitleHint)
        self.setStyleSheet(_STYLE)
        self._build_ui()

    def _build_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(14)

        self._title = QLabel("מחיל עדכון...")
        self._title.setStyleSheet(f"font-size: 12pt; font-weight: 700; color: {_TEXT};")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._title)

        self._status = QLabel("מחליף קבצים...")
        self._status.setStyleSheet(f"font-size: 9pt; color: {_MUTED};")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._status)

        self._bar = QProgressBar()
        self._bar.setRange(0, 0)   # indeterminate — לא ידוע כמה זמן
        self._bar.setTextVisible(False)
        lay.addWidget(self._bar)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._thread = _ApplyThread(self._zip_path, self._target_dir)
        self._thread.done.connect(self._on_done)
        self._thread.failed.connect(self._on_error)
        self._thread.start()

    def _on_done(self) -> None:
        self._bar.setRange(0, 100)
        self._bar.setValue(100)
        self._title.setText("העדכון הושלם!")
        self._status.setText("מפעיל מחדש...")
        QApplication.processEvents()
        import subprocess
        subprocess.Popen([self._exe_to_restart])
        QApplication.quit()

    def _on_error(self, msg: str) -> None:
        QMessageBox.critical(
            self, "שגיאת עדכון",
            f"העדכון נכשל:\n\n{msg}\n\n"
            "הגרסה הקודמת שוחזרה. נסה שוב מאוחר יותר."
        )
        QApplication.quit()


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) != 4:
        print(
            "Usage: updater.exe <zip_path> <target_dir> <exe_to_restart>",
            file=sys.stderr,
        )
        sys.exit(1)

    _, zip_path, target_dir, exe_to_restart = sys.argv

    app = QApplication(sys.argv)
    app.setApplicationName("Kling-Match Updater")

    win = UpdaterWindow(zip_path, target_dir, exe_to_restart)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
