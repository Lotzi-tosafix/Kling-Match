"""
auto_updater.py — Automatic update mechanism for Kling-Match.

Flow:
  1. On startup, check GitHub API for the latest release.
  2. Compare remote tag to local version.txt.
  3. If newer: show a popup asking the user to approve.
  4. On approval: download only the update archive (app-only, no models).
  5. Extract and replace the app/ directory, then restart.

Update assets on GitHub Releases:
  - Kling-Match-<ver>-setup.exe        ← full installer (first install only)
  - Kling-Match-<ver>-portable.zip     ← full portable (first install only)
  - Kling-Match-<ver>-update.zip       ← app-code-only patch (used for updates)

install_type.txt (in app root):
  "installer"  → installer build
  "portable"   → portable build
Either type downloads the same update.zip — only app/ code is replaced.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import zipfile
from typing import Callable, Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal as Signal
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# ── Constants ──────────────────────────────────────────────────────────────────
GITHUB_OWNER = "Lotzi-tosafix"
GITHUB_REPO  = "Kling-Match"
API_URL      = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
UPDATE_ASSET = "update.zip"          # asset name in GitHub Release
REQUEST_TIMEOUT = 8                  # seconds for API check
DOWNLOAD_TIMEOUT = 300               # seconds for download (large file safety)


# ── Version helpers ────────────────────────────────────────────────────────────

def _app_root() -> str:
    """
    Returns the root directory of the running application.
    When frozen (PyInstaller), this is the directory containing the EXE.
    When running as plain Python, this is the repo root.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # dev mode: two levels up from this file (core/ → kling_match/ → root)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _version_file() -> str:
    return os.path.join(_app_root(), "version.txt")


def _install_type_file() -> str:
    return os.path.join(_app_root(), "install_type.txt")


def get_local_version() -> str:
    """Read version from version.txt. Falls back to package __version__."""
    try:
        with open(_version_file(), encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        from kling_match import __version__
        return __version__


def get_install_type() -> str:
    """Returns 'installer', 'portable', or 'dev'."""
    try:
        with open(_install_type_file(), encoding="utf-8") as f:
            return f.read().strip().lower()
    except FileNotFoundError:
        return "dev"


def _version_tuple(v: str) -> tuple:
    """Convert '1.2.3' → (1, 2, 3) for comparison. Strips leading 'v'."""
    v = v.lstrip("v")
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return (0,)


# ── GitHub API ─────────────────────────────────────────────────────────────────

def fetch_latest_release() -> Optional[dict]:
    """
    Query GitHub API for the latest release.
    Returns the parsed JSON dict, or None on network/parse error.
    """
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


def check_for_update() -> Optional[dict]:
    """
    Check if a newer release exists.

    Returns:
        dict with keys {tag, version, notes, download_url, size_bytes}
        if an update is available, else None.
    """
    data = fetch_latest_release()
    if not data:
        return None

    remote_tag     = data.get("tag_name", "").lstrip("v")
    remote_version = remote_tag
    local_version  = get_local_version().lstrip("v")

    if _version_tuple(remote_version) <= _version_tuple(local_version):
        return None   # already up to date

    # Find the update.zip asset
    download_url: Optional[str] = None
    size_bytes: int = 0
    for asset in data.get("assets", []):
        if asset.get("name", "").lower() == UPDATE_ASSET:
            download_url = asset["browser_download_url"]
            size_bytes   = asset.get("size", 0)
            break

    if not download_url:
        return None   # no update asset published yet

    return {
        "tag":          data.get("tag_name", remote_version),
        "version":      remote_version,
        "notes":        data.get("body", ""),
        "download_url": download_url,
        "size_bytes":   size_bytes,
    }


# ── Download worker ────────────────────────────────────────────────────────────

class _DownloadThread(QThread):
    """Downloads a URL to a temp file and reports progress."""

    progress   = Signal(int)   # 0-100
    finished   = Signal(str)   # path to temp file
    failed     = Signal(str)   # error message

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
                tmp   = tempfile.NamedTemporaryFile(
                    delete=False, suffix=".zip", prefix="kling_update_"
                )
                downloaded = 0
                chunk_size = 65536
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    tmp.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        self.progress.emit(int(downloaded / total * 100))
                tmp.close()
            self.finished.emit(tmp.name)
        except Exception as exc:
            self.failed.emit(str(exc))


# ── Apply update ───────────────────────────────────────────────────────────────

def _apply_update(zip_path: str) -> None:
    """
    Extract update.zip and replace the app/ directory.

    Expected zip structure:
        app/
            main.py
            kling_match/
            SongFormer/
            version.txt
            ...
    The models/ directory and the launcher EXE are NOT touched.
    """
    root = _app_root()
    app_dir = os.path.join(root, "app")

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()

    # Validate: all entries must start with "app/"
    if not all(n.startswith("app/") or n == "app/" for n in names):
        raise ValueError(
            "Update archive has unexpected structure. "
            "Expected all files under app/."
        )

    # Backup current app/ to app.bak/ (overwrite if exists)
    bak_dir = os.path.join(root, "app.bak")
    if os.path.isdir(app_dir):
        if os.path.isdir(bak_dir):
            shutil.rmtree(bak_dir)
        shutil.copytree(app_dir, bak_dir)

    try:
        # Remove old app/ and extract new one
        if os.path.isdir(app_dir):
            shutil.rmtree(app_dir)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(root)

        # Remove backup on success
        if os.path.isdir(bak_dir):
            shutil.rmtree(bak_dir)

    except Exception:
        # Restore backup on failure
        if os.path.isdir(bak_dir):
            if os.path.isdir(app_dir):
                shutil.rmtree(app_dir)
            shutil.copytree(bak_dir, app_dir)
        raise


def _restart_app() -> None:
    """Restart the application process."""
    if getattr(sys, "frozen", False):
        os.execv(sys.executable, [sys.executable] + sys.argv[1:])
    else:
        os.execv(sys.executable, [sys.executable] + sys.argv)


# ── Update dialog ──────────────────────────────────────────────────────────────

class UpdateDialog(QDialog):
    """
    Popup shown when a new version is available.
    Displays version info and release notes, then lets the user
    approve or dismiss the update.
    """

    def __init__(self, update_info: dict, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._info    = update_info
        self._thread: Optional[_DownloadThread] = None

        self.setWindowTitle("Update Available — Kling-Match")
        self.setMinimumWidth(480)
        self.setMinimumHeight(200)
        self._setup_ui()

    def _setup_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(20, 20, 20, 16)

        # ── Header ──────────────────────────────────────────────────────
        title = QLabel(
            f"<b>Kling-Match {self._info['tag']} is available</b>"
        )
        title.setStyleSheet("font-size: 12pt;")
        lay.addWidget(title)

        local_ver = get_local_version()
        sub = QLabel(
            f"You have version {local_ver}. "
            f"The new version is {self._info['version']}."
        )
        sub.setWordWrap(True)
        lay.addWidget(sub)

        size_mb = self._info["size_bytes"] / 1_048_576
        size_lbl = QLabel(
            f"Download size: {size_mb:.1f} MB  "
            f"(app code only — models are not re-downloaded)"
        )
        size_lbl.setWordWrap(True)
        size_lbl.setStyleSheet("font-size: 9pt; color: #888;")
        lay.addWidget(size_lbl)

        # ── Release notes ────────────────────────────────────────────────
        notes = self._info.get("notes", "").strip()
        if notes:
            notes_lbl = QLabel(notes[:600] + ("…" if len(notes) > 600 else ""))
            notes_lbl.setWordWrap(True)
            notes_lbl.setStyleSheet(
                "font-size: 9pt; background: rgba(0,0,0,0.05);"
                " border-radius: 6px; padding: 8px;"
            )
            lay.addWidget(notes_lbl)

        # ── Progress bar (hidden until download starts) ──────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setVisible(False)
        lay.addWidget(self._progress)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("font-size: 9pt; color: #888;")
        self._status_lbl.setVisible(False)
        lay.addWidget(self._status_lbl)

        # ── Buttons ──────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._skip_btn = QPushButton("Skip this time")
        self._skip_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._skip_btn)

        self._update_btn = QPushButton("Update now")
        self._update_btn.setDefault(True)
        self._update_btn.setStyleSheet(
            "QPushButton { background: #DA627D; color: white; border: none;"
            " border-radius: 16px; padding: 6px 22px; font-weight: 600; }"
            "QPushButton:hover { background: #b34d63; }"
        )
        self._update_btn.clicked.connect(self._start_download)
        btn_row.addWidget(self._update_btn)

        lay.addLayout(btn_row)

    def _start_download(self) -> None:
        self._update_btn.setEnabled(False)
        self._skip_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status_lbl.setText("Downloading update…")
        self._status_lbl.setVisible(True)

        self._thread = _DownloadThread(self._info["download_url"], self)
        self._thread.progress.connect(self._progress.setValue)
        self._thread.finished.connect(self._on_download_done)
        self._thread.failed.connect(self._on_download_failed)
        self._thread.start()

    def _on_download_done(self, zip_path: str) -> None:
        self._status_lbl.setText("Applying update…")
        QApplication.processEvents()
        try:
            _apply_update(zip_path)
        except Exception as exc:
            self._on_error(f"Failed to apply update:\n{exc}")
            return
        finally:
            try:
                os.unlink(zip_path)
            except OSError:
                pass

        self._status_lbl.setText("Update complete. Restarting…")
        QApplication.processEvents()
        _restart_app()

    def _on_download_failed(self, error: str) -> None:
        self._on_error(f"Download failed:\n{error}")

    def _on_error(self, msg: str) -> None:
        self._progress.setVisible(False)
        self._status_lbl.setText(f"Error: {msg}")
        self._update_btn.setEnabled(True)
        self._skip_btn.setEnabled(True)


# ── Public entry point ─────────────────────────────────────────────────────────

class _CheckThread(QThread):
    """Background thread that checks for updates silently."""
    update_available = Signal(dict)

    def run(self) -> None:
        info = check_for_update()
        if info:
            self.update_available.emit(info)


_check_thread: Optional[_CheckThread] = None   # keep reference alive


def start_update_check(parent: Optional[QWidget] = None) -> None:
    """
    Start a background update check. If an update is found, show the
    UpdateDialog on the main thread. Call this once after the main window
    is shown.

    Args:
        parent: parent widget for the UpdateDialog.
    """
    # Skip update check in dev mode (no version.txt / install_type = dev)
    if get_install_type() == "dev":
        return

    global _check_thread
    _check_thread = _CheckThread()

    def _on_update(info: dict) -> None:
        dlg = UpdateDialog(info, parent=parent)
        dlg.exec()

    _check_thread.update_available.connect(_on_update)
    _check_thread.start()
