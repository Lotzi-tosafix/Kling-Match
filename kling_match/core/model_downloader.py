"""
model_downloader.py — הורדת מודלי ML בהפעלה ראשונה.

שלושה מודלים נדרשים:
  1. MuQ          — OpenMuQ/MuQ-large-msd-iter  (HuggingFace Hub)
  2. MusicFM      — minzwon/MusicFM              (HuggingFace Hub)
  3. SongFormer   — ASLP-lab/SongFormer          (HuggingFace Hub)

ה-downloader בודק אם המודלים קיימים בנתיב הנכון לפני כל הורדה.
אם כולם קיימים — מחזיר מיד ללא חלון.
אם חסר לפחות אחד — מציג חלון progress ומוריד.
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
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)
from PyQt6.QtGui import QFont


# ── נתיבי יעד ─────────────────────────────────────────────────────────────────

def _models_root() -> str:
    """
    מחזיר את תיקיית models/ בהתאם למצב ריצה.
    frozen: ליד ה-EXE  (dist/Kling-Match/models/)
    dev:    שורש המאגר (repo/models/)
    """
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "models")
    # dev: שני רמות מעל kling_match/core/
    return os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "models")
    )


def _ckpts_root(songformer_dir: str) -> str:
    """מחזיר את נתיב ckpts/ של SongFormer."""
    if getattr(sys, "frozen", False):
        # frozen: _MEIPASS/app/SongFormer/src/SongFormer/ckpts
        base = getattr(sys, "_MEIPASS", "")
        return os.path.join(base, "app", "SongFormer", "src", "SongFormer", "ckpts")
    return os.path.join(songformer_dir, "ckpts")


def _model_files(songformer_dir: str) -> list[dict]:
    """
    מחזיר רשימת מילונים עם פרטי כל קובץ מודל.
    כל מילון: name, url, dest_path, size_mb (הערכה).
    """
    mr = _models_root()
    cr = _ckpts_root(songformer_dir)

    HF = "https://huggingface.co"
    return [
        {
            "name": "MuQ (model.safetensors)",
            "url": f"{HF}/OpenMuQ/MuQ-large-msd-iter/resolve/main/model.safetensors",
            "dest": os.path.join(mr, "MuQ", "model.safetensors"),
            "size_mb": 1272,
        },
        {
            "name": "MuQ (config.json)",
            "url": f"{HF}/OpenMuQ/MuQ-large-msd-iter/resolve/main/config.json",
            "dest": os.path.join(mr, "MuQ", "config.json"),
            "size_mb": 1,
        },
        {
            "name": "MusicFM (pretrained_msd.pt)",
            "url": f"{HF}/minzwon/MusicFM/resolve/main/pretrained_msd.pt",
            "dest": os.path.join(cr, "MusicFM", "pretrained_msd.pt"),
            "size_mb": 1256,
        },
        {
            "name": "MusicFM (msd_stats.json)",
            "url": f"{HF}/minzwon/MusicFM/resolve/main/msd_stats.json",
            "dest": os.path.join(cr, "MusicFM", "msd_stats.json"),
            "size_mb": 1,
        },
        {
            "name": "SongFormer (SongFormer.safetensors)",
            "url": f"{HF}/ASLP-lab/SongFormer/resolve/main/SongFormer.safetensors",
            "dest": os.path.join(cr, "SongFormer.safetensors"),
            "size_mb": 100,
        },
    ]


def models_exist(songformer_dir: str) -> bool:
    """בודק אם כל קבצי המודלים קיימים ואינם ריקים."""
    for f in _model_files(songformer_dir):
        if not os.path.isfile(f["dest"]) or os.path.getsize(f["dest"]) < 1024:
            return False
    return True


# ── Worker thread ──────────────────────────────────────────────────────────────

class _DownloadWorker(QThread):
    """מוריד את כל קבצי המודלים ברצף ומדווח על התקדמות."""

    # signals
    file_started  = Signal(str, int)   # (שם קובץ, גודל_MB)
    file_progress = Signal(int)        # אחוז 0-100 של הקובץ הנוכחי
    file_done     = Signal(str)        # שם קובץ שהסתיים
    all_done      = Signal()
    failed        = Signal(str)        # הודעת שגיאה

    def __init__(self, files: list[dict], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._files = files
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        for f in self._files:
            if self._cancelled:
                return

            # כבר קיים ותקין — דלג
            if os.path.isfile(f["dest"]) and os.path.getsize(f["dest"]) > 1024:
                self.file_started.emit(f["name"], f["size_mb"])
                self.file_progress.emit(100)
                self.file_done.emit(f["name"])
                continue

            self.file_started.emit(f["name"], f["size_mb"])

            # ודא שהתיקייה קיימת
            os.makedirs(os.path.dirname(f["dest"]), exist_ok=True)

            # הורדה עם resuming (Range header)
            tmp_path = f["dest"] + ".part"
            downloaded = os.path.getsize(tmp_path) if os.path.isfile(tmp_path) else 0

            try:
                req = urllib.request.Request(
                    f["url"],
                    headers={
                        "User-Agent": "Kling-Match/0.9",
                        "Range": f"bytes={downloaded}-",
                    }
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    total = int(resp.headers.get("Content-Length", 0)) + downloaded
                    mode = "ab" if downloaded > 0 else "wb"
                    with open(tmp_path, mode) as fp:
                        chunk_size = 131072  # 128 KB
                        while not self._cancelled:
                            chunk = resp.read(chunk_size)
                            if not chunk:
                                break
                            fp.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                self.file_progress.emit(
                                    int(downloaded / total * 100)
                                )

                if self._cancelled:
                    return

                # rename tmp → final
                if os.path.isfile(f["dest"]):
                    os.remove(f["dest"])
                os.rename(tmp_path, f["dest"])
                self.file_done.emit(f["name"])

            except Exception as exc:
                self.failed.emit(
                    f"שגיאה בהורדת {f['name']}:\n{exc}\n\n"
                    "ודא שיש חיבור לאינטרנט ונסה שוב."
                )
                return

        if not self._cancelled:
            self.all_done.emit()


# ── Dialog ─────────────────────────────────────────────────────────────────────

class ModelDownloadDialog(QDialog):
    """
    חלון הורדת מודלים.
    מוצג רק אם לפחות מודל אחד חסר.
    חוסם את המשך ההפעלה עד שההורדה מסתיימת.
    """

    def __init__(self, files: list[dict], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._files  = files
        self._worker: Optional[_DownloadWorker] = None
        self._success = False

        self.setWindowTitle("Kling-Match — הורדת מודלים")
        self.setMinimumWidth(500)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint
        )
        # לא ניתן לסגור ידנית
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 20)

        # כותרת
        title = QLabel("הורדת מודלי ניתוח מוזיקה")
        f = QFont()
        f.setPointSize(13)
        f.setBold(True)
        title.setFont(f)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # הסבר
        total_mb = sum(f["size_mb"] for f in self._files
                       if not (os.path.isfile(f["dest"])
                               and os.path.getsize(f["dest"]) > 1024))
        total_gb = round(total_mb / 1024, 1)
        desc = QLabel(
            f"Kling-Match דורש מודלי AI לניתוח שירים.\n"
            f"הם יורדו פעם אחת בלבד מ-HuggingFace ({total_gb} GB).\n"
            f"ההורדה ניתנת להמשך אם נקטעת."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        # שם הקובץ הנוכחי
        self._file_label = QLabel("מתחיל...")
        self._file_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._file_label.setStyleSheet("font-size: 9pt; color: #aaa;")
        layout.addWidget(self._file_label)

        # progress bar קובץ נוכחי
        self._file_bar = QProgressBar()
        self._file_bar.setRange(0, 100)
        self._file_bar.setValue(0)
        self._file_bar.setTextVisible(True)
        layout.addWidget(self._file_bar)

        # progress bar כולל
        overall_label = QLabel("התקדמות כוללת")
        overall_label.setStyleSheet("font-size: 9pt; color: #888;")
        layout.addWidget(overall_label)

        self._total_bar = QProgressBar()
        self._total_bar.setRange(0, len(self._files))
        self._total_bar.setValue(0)
        self._total_bar.setTextVisible(False)
        layout.addWidget(self._total_bar)

        self._done_count = 0

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
        """מפעיל את ה-worker thread."""
        self._worker = _DownloadWorker(self._files, self)
        self._worker.file_started.connect(self._on_file_started)
        self._worker.file_progress.connect(self._file_bar.setValue)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_file_started(self, name: str, size_mb: int) -> None:
        self._file_label.setText(f"{name}  ({size_mb} MB)")
        self._file_bar.setValue(0)

    def _on_file_done(self, name: str) -> None:
        self._done_count += 1
        self._total_bar.setValue(self._done_count)
        self._file_bar.setValue(100)

    def _on_all_done(self) -> None:
        self._success = True
        self.accept()

    def _on_failed(self, msg: str) -> None:
        from PyQt6.QtWidgets import QMessageBox
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


# ── Public entry point ─────────────────────────────────────────────────────────

def ensure_models(songformer_dir: str, parent: Optional[QWidget] = None) -> bool:
    """
    בודק אם המודלים קיימים. אם לא — מציג חלון הורדה.

    Returns:
        True אם כל המודלים קיימים (בין אם היו קיימים מראש או הורדו עכשיו).
        False אם המשתמש ביטל או ההורדה נכשלה.
    """
    files = _model_files(songformer_dir)

    # בדוק אילו קבצים חסרים
    missing = [
        f for f in files
        if not os.path.isfile(f["dest"]) or os.path.getsize(f["dest"]) < 1024
    ]

    if not missing:
        return True  # הכל קיים — אין מה לעשות

    dlg = ModelDownloadDialog(files, parent=parent)
    dlg.start_downloads()
    dlg.exec()
    return dlg.was_successful()
