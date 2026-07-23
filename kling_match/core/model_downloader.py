"""
model_downloader.py — הורדת מודלי ML בהפעלה ראשונה / כשמודלים חסרים.

שלושה מודלים נדרשים:
  1. MuQ        — OpenMuQ/MuQ-large-msd-iter  (HuggingFace)
  2. MusicFM    — minzwon/MusicFM             (HuggingFace)
  3. SongFormer — ASLP-lab/SongFormer         (HuggingFace)

בדיקה בכל הפעלה:
  - אם כולם קיימים ושלמים  → ממשיכים מיד (בדיקה מיידית, פחות ממילישנייה)
  - אם חסרים / חלקיים (.part) → שואלים את המשתמש אם להוריד
  - קבצי .part מזוהים כהורדה שנקטעה → הודעה שונה למשתמש
"""

from __future__ import annotations

import os
import sys
import urllib.request
import urllib.error
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal as Signal, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)
from PyQt6.QtGui import QFont


# ── נתיבי יעד ────────────────────────────────────────────────────────────────

def _models_root() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "models")
    return os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "models")
    )


def _model_files() -> list[dict]:
    mr = _models_root()
    HF = "https://huggingface.co"
    return [
        {
            "name": "MuQ (model.safetensors)",
            "url":  f"{HF}/OpenMuQ/MuQ-large-msd-iter/resolve/main/model.safetensors",
            "dest": os.path.join(mr, "MuQ", "model.safetensors"),
            "size_mb": 1272,
        },
        {
            "name": "MuQ (config.json)",
            "url":  f"{HF}/OpenMuQ/MuQ-large-msd-iter/resolve/main/config.json",
            "dest": os.path.join(mr, "MuQ", "config.json"),
            "size_mb": 1,
        },
        {
            "name": "MusicFM (pretrained_msd.pt)",
            "url":  f"{HF}/minzwon/MusicFM/resolve/main/pretrained_msd.pt",
            "dest": os.path.join(mr, "MusicFM", "pretrained_msd.pt"),
            "size_mb": 1256,
        },
        {
            "name": "MusicFM (msd_stats.json)",
            "url":  f"{HF}/minzwon/MusicFM/resolve/main/msd_stats.json",
            "dest": os.path.join(mr, "MusicFM", "msd_stats.json"),
            "size_mb": 1,
        },
        {
            "name": "SongFormer (SongFormer.safetensors)",
            "url":  f"{HF}/ASLP-lab/SongFormer/resolve/main/SongFormer.safetensors",
            "dest": os.path.join(mr, "SongFormer", "SongFormer.safetensors"),
            "size_mb": 100,
        },
    ]


# ── סטטוס המודלים ─────────────────────────────────────────────────────────────

def _file_ok(path: str) -> bool:
    """קובץ קיים ושלם (לא .part)."""
    return os.path.isfile(path) and os.path.getsize(path) > 1024


def _has_partial() -> bool:
    """בודק אם קיים לפחות קובץ .part (הורדה שנקטעה)."""
    for f in _model_files():
        if os.path.isfile(f["dest"] + ".part"):
            return True
    return False


def models_status() -> str:
    """
    מחזיר:
      'ok'      — כולם קיימים ושלמים
      'partial' — לפחות אחד נקטע באמצע (.part קיים)
      'missing' — לפחות אחד חסר לחלוטין
    """
    files = _model_files()
    all_ok = all(_file_ok(f["dest"]) for f in files)
    if all_ok:
        return "ok"
    if _has_partial():
        return "partial"
    return "missing"


# ── Worker thread ─────────────────────────────────────────────────────────────

class _DownloadWorker(QThread):
    file_started  = Signal(str, int)   # (שם, size_mb)
    file_progress = Signal(int)        # 0-100 לקובץ הנוכחי
    overall_progress = Signal(int, int)  # (קבצים שהסתיימו, סה"כ קבצים)
    file_done     = Signal(str)
    all_done      = Signal()
    failed        = Signal(str)

    def __init__(self, files: list[dict], parent=None) -> None:
        super().__init__(parent)
        self._files = files
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        total = len(self._files)
        done  = 0

        for f in self._files:
            if self._cancelled:
                return

            # קובץ שלם — דלג
            if _file_ok(f["dest"]):
                done += 1
                self.overall_progress.emit(done, total)
                continue

            self.file_started.emit(f["name"], f["size_mb"])

            os.makedirs(os.path.dirname(f["dest"]), exist_ok=True)
            tmp  = f["dest"] + ".part"
            downloaded = os.path.getsize(tmp) if os.path.isfile(tmp) else 0

            try:
                req = urllib.request.Request(
                    f["url"],
                    headers={
                        "User-Agent": "Kling-Match/0.9",
                        "Range": f"bytes={downloaded}-",
                    }
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    total_bytes = int(resp.headers.get("Content-Length", 0)) + downloaded
                    mode = "ab" if downloaded > 0 else "wb"
                    with open(tmp, mode) as fp:
                        while not self._cancelled:
                            chunk = resp.read(131072)
                            if not chunk:
                                break
                            fp.write(chunk)
                            downloaded += len(chunk)
                            if total_bytes > 0:
                                self.file_progress.emit(
                                    int(downloaded / total_bytes * 100)
                                )

                if self._cancelled:
                    return

                if os.path.isfile(f["dest"]):
                    os.remove(f["dest"])
                os.rename(tmp, f["dest"])

                done += 1
                self.file_done.emit(f["name"])
                self.overall_progress.emit(done, total)

            except Exception as exc:
                self.failed.emit(
                    f"שגיאה בהורדת {f['name']}:\n{exc}\n\n"
                    "ודא שיש חיבור לאינטרנט ונסה שוב."
                )
                return

        if not self._cancelled:
            self.all_done.emit()


# ── Dialog ────────────────────────────────────────────────────────────────────

class ModelDownloadDialog(QDialog):

    def __init__(self, files: list[dict], parent=None) -> None:
        super().__init__(parent)
        self._files   = files
        self._worker: Optional[_DownloadWorker] = None
        self._success = False

        self.setWindowTitle("Kling-Match — הורדת מודלים")
        self.setMinimumWidth(520)
        # לא מגדירים RTL על כל ה-dialog — גורם לבעיות בטקסט מעורב עברית/אנגלית
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint
        )
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 20)

        # כותרת — עברית בלבד, RTL
        title = QLabel("הורדת מודלי AI")
        f = QFont()
        f.setPointSize(13)
        f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        layout.addWidget(title)

        # תיאור — כל שורה עברית בלבד, ללא מילים אנגליות באמצע
        total_mb = sum(
            f["size_mb"] for f in self._files
            if not _file_ok(f["dest"])
        )
        total_gb = round(total_mb / 1024, 1)
        desc = QLabel(
            f"כדי לנתח שירים, יש להוריד מודלי AI בגודל {total_gb} GB.\n"
            f"ההורדה מתבצעת פעם אחת בלבד מ-HuggingFace.\n"
            f"אם הורדה קודמת נקטעה — היא תמשיך מהנקודה שבה עצרה."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        layout.addWidget(desc)

        # שם קובץ נוכחי — LTR כי הוא שם קובץ אנגלי
        self._file_label = QLabel("מתחיל...")
        self._file_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._file_label.setStyleSheet("font-size: 9pt; color: #aaa;")
        layout.addWidget(self._file_label)

        # progress קובץ נוכחי — RTL
        self._file_bar = QProgressBar()
        self._file_bar.setRange(0, 100)
        self._file_bar.setValue(0)
        self._file_bar.setTextVisible(True)
        self._file_bar.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        layout.addWidget(self._file_bar)

        # תווית "התקדמות כוללת" — RTL כי עברית
        total_label = QLabel("התקדמות כוללת")
        total_label.setStyleSheet("font-size: 9pt; color: #888;")
        total_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        total_label.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        layout.addWidget(total_label)

        # חישוב סה"כ MB להורדה
        self._total_mb_to_download = sum(
            f["size_mb"] for f in self._files
            if not _file_ok(f["dest"])
        )
        self._downloaded_mb = 0.0
        self._current_file_start_mb = 0.0

        # progress כולל — RTL
        self._total_bar = QProgressBar()
        self._total_bar.setRange(0, max(self._total_mb_to_download, 1))
        self._total_bar.setValue(0)
        self._total_bar.setTextVisible(False)
        self._total_bar.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        layout.addWidget(self._total_bar)

        self._current_file_size_mb = 0

        # כפתור ביטול
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = QPushButton("ביטול")
        self._cancel_btn.setStyleSheet(
            "QPushButton { border: 1px solid #555; border-radius: 14px;"
            " padding: 5px 20px; } QPushButton:hover { background: #333; }"
        )
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._cancel_btn)
        layout.addLayout(btn_row)

    def start_downloads(self) -> None:
        self._worker = _DownloadWorker(self._files, self)
        self._worker.file_started.connect(self._on_file_started)
        self._worker.file_progress.connect(self._on_file_progress)
        self._worker.overall_progress.connect(self._on_overall_progress)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_file_started(self, name: str, size_mb: int) -> None:
        self._file_label.setText(f"{name}  ({size_mb} MB)")
        self._file_bar.setValue(0)
        self._current_file_size_mb = size_mb
        self._current_file_start_mb = self._downloaded_mb

    def _on_file_progress(self, pct: int) -> None:
        self._file_bar.setValue(pct)
        # עדכן progress כולל לפי MB שהורדנו
        mb_in_current = self._current_file_size_mb * pct / 100.0
        total_done_mb = int(self._current_file_start_mb + mb_in_current)
        self._total_bar.setValue(min(total_done_mb, self._total_mb_to_download))

    def _on_overall_progress(self, done: int, total: int) -> None:
        # עדכן גם את ה-downloaded_mb לאחר סיום קובץ
        completed_mb = sum(
            f["size_mb"] for f in self._files[:done]
            if not _file_ok(self._files[done - 1]["dest"])
               or True  # תמיד תחשב
        )
        self._downloaded_mb = sum(
            f["size_mb"] for i, f in enumerate(self._files)
            if i < done and not _file_ok(f["dest"])
               or (i < done and _file_ok(f["dest"]))
        )

    def _on_file_done(self, name: str) -> None:
        self._file_bar.setValue(100)
        # עדכן את ה-mb שהורדנו
        for f in self._files:
            if f["name"] == name:
                self._downloaded_mb += f["size_mb"]
                break

    def _on_all_done(self) -> None:
        self._total_bar.setValue(self._total_mb_to_download)
        self._success = True
        self.accept()

    def _on_failed(self, msg: str) -> None:
        self._cancel_btn.setText("סגור")
        QMessageBox.critical(self, "שגיאת הורדה", msg)
        self.reject()

    def _on_cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        self.reject()

    def was_successful(self) -> bool:
        return self._success


# ── Public entry point ────────────────────────────────────────────────────────

def ensure_models(parent=None) -> bool:
    """
    בודק בכל הפעלה אם המודלים קיימים.

    Returns:
        True  — כל המודלים קיימים (בין אם היו או הורדו עכשיו)
        False — המשתמש ביטל או ההורדה נכשלה
    """
    status = models_status()

    if status == "ok":
        return True  # הכל תקין — ממשיכים מיד

    files = _model_files()

    # בניית הודעה מתאימה לפי המצב
    if status == "partial":
        title = "הורדה לא הושלמה"
        text  = (
            "הורדת מודלי ה-AI נקטעה בהפעלה קודמת.\n\n"
            "ללא המודלים לא ניתן לנתח שירים.\n"
            "להמשיך את ההורדה?"
        )
    else:  # missing
        title = "נדרשים מודלי AI"
        text  = (
            "כדי לנתח שירים, Kling-Match צריך להוריד מודלי AI.\n\n"
            "מדובר בהורדה חד-פעמית של כ-2.6 GB מ-HuggingFace.\n"
            "להוריד עכשיו?"
        )

    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    msg.setIcon(QMessageBox.Icon.Question)
    download_btn = msg.addButton("הורד", QMessageBox.ButtonRole.AcceptRole)
    msg.addButton("יציאה", QMessageBox.ButtonRole.RejectRole)
    msg.exec()

    if msg.clickedButton() != download_btn:
        return False

    # פתח חלון הורדה
    dlg = ModelDownloadDialog(files, parent=parent)
    dlg.start_downloads()
    dlg.exec()
    return dlg.was_successful()
