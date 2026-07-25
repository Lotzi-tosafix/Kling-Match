"""
updater.py — Kling-Match standalone updater.

Usage (called by Kling-Match automatically):
    updater.exe <zip_url> <target_dir> <exe_to_restart>

    zip_url        — URL to update.zip on GitHub Releases
    target_dir     — absolute path to _internal\\app\\ (the dir to replace)
    exe_to_restart — absolute path to Kling-Match.exe (launched after update)

The updater:
  1. Shows a small progress window.
  2. Downloads update.zip to a temp file.
  3. Backs up target_dir to target_dir.bak.
  4. Extracts zip (strips the leading "app/" prefix) into target_dir.
  5. Removes the backup.
  6. Launches exe_to_restart and exits.

On any error: restores backup and shows an error dialog.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import urllib.request
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


# ── Download thread ────────────────────────────────────────────────────────────

class _Downloader(QThread):
    progress = Signal(int)      # 0-100
    done     = Signal(str)      # path to temp zip
    failed   = Signal(str)      # error message

    def __init__(self, url: str) -> None:
        super().__init__()
        self._url = url

    def run(self) -> None:
        try:
            req = urllib.request.Request(
                self._url,
                headers={"User-Agent": "Kling-Match-Updater/1.0"},
            )
            with urllib.request.urlopen(req, timeout=300) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                tmp = tempfile.NamedTemporaryFile(
                    delete=False, suffix=".zip", prefix="kling_upd_"
                )
                downloaded = 0
                while True:
                    chunk = resp.read(131072)
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


# ── Main window ────────────────────────────────────────────────────────────────

class UpdaterWindow(QWidget):

    def __init__(self, zip_url: str, target_dir: str, exe_to_restart: str) -> None:
        super().__init__()
        self._zip_url       = zip_url
        self._target_dir    = target_dir   # e.g. C:\...\Kling-Match\_internal\app
        self._exe_to_restart= exe_to_restart
        self._tmp_zip: str | None = None
        self._thread: _Downloader | None = None

        self.setWindowTitle("Kling-Match — מעדכן")
        self.setFixedSize(420, 160)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowTitleHint)
        self.setStyleSheet(_STYLE)
        self._build_ui()

    def _build_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(14)

        self._title = QLabel("מוריד עדכון...")
        self._title.setStyleSheet(f"font-size: 12pt; font-weight: 700; color: {_TEXT};")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._title)

        self._status = QLabel("מתחיל הורדה...")
        self._status.setStyleSheet(f"font-size: 9pt; color: {_MUTED};")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._status)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        lay.addWidget(self._bar)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._start_download()

    def _start_download(self) -> None:
        self._thread = _Downloader(self._zip_url)
        self._thread.progress.connect(self._bar.setValue)
        self._thread.done.connect(self._on_downloaded)
        self._thread.failed.connect(self._on_error)
        self._thread.start()

    def _on_downloaded(self, tmp_path: str) -> None:
        self._tmp_zip = tmp_path
        self._title.setText("מחיל עדכון...")
        self._status.setText("מחליף קבצים...")
        self._bar.setValue(100)
        QApplication.processEvents()
        try:
            self._apply()
        except Exception as exc:
            self._on_error(f"החלת העדכון נכשלה:\n{exc}")
            return
        self._launch_and_exit()

    def _apply(self) -> None:
        """
        Extract update.zip into target_dir.

        Expected zip layout (from make_update_zip.py):
            app/kling_match/...
            app/SongFormer/...
            app/version.txt
            ...

        We strip the leading "app/" and write directly into target_dir.
        A backup of target_dir is kept as target_dir + ".bak" until success.
        """
        target = self._target_dir
        backup = target + ".bak"

        # ── backup ────────────────────────────────────────────────────────────
        if os.path.isdir(backup):
            shutil.rmtree(backup)
        if os.path.isdir(target):
            shutil.copytree(target, backup)

        try:
            # ── validate zip structure ─────────────────────────────────────────
            with zipfile.ZipFile(self._tmp_zip, "r") as zf:
                names = zf.namelist()

            if not all(n.startswith("app/") or n == "app/" for n in names):
                raise ValueError(
                    "מבנה קובץ העדכון שגוי — לא כל הרשומות תחת app/"
                )

            # ── wipe old dir and extract ───────────────────────────────────────
            if os.path.isdir(target):
                shutil.rmtree(target)
            os.makedirs(target, exist_ok=True)

            with zipfile.ZipFile(self._tmp_zip, "r") as zf:
                for member in zf.infolist():
                    # strip leading "app/"
                    rel = member.filename[len("app/"):]
                    if not rel:          # the "app/" directory entry itself
                        continue
                    dest = os.path.join(target, rel.replace("/", os.sep))
                    if member.is_dir():
                        os.makedirs(dest, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(dest), exist_ok=True)
                        with zf.open(member) as src, open(dest, "wb") as dst:
                            shutil.copyfileobj(src, dst)

            # ── remove backup on success ───────────────────────────────────────
            if os.path.isdir(backup):
                shutil.rmtree(backup)

        except Exception:
            # ── restore backup on failure ──────────────────────────────────────
            if os.path.isdir(backup):
                if os.path.isdir(target):
                    shutil.rmtree(target)
                shutil.copytree(backup, target)
            raise

        finally:
            # cleanup temp zip
            try:
                if self._tmp_zip and os.path.isfile(self._tmp_zip):
                    os.unlink(self._tmp_zip)
            except OSError:
                pass

    def _launch_and_exit(self) -> None:
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
            "Usage: updater.exe <zip_url> <target_dir> <exe_to_restart>",
            file=sys.stderr,
        )
        sys.exit(1)

    _, zip_url, target_dir, exe_to_restart = sys.argv

    app = QApplication(sys.argv)
    app.setApplicationName("Kling-Match Updater")

    win = UpdaterWindow(zip_url, target_dir, exe_to_restart)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
