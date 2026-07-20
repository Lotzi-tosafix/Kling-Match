"""
main.py — entry point for Kling-Match.
"""

import sys
import os


def _find_app_root() -> str:
    """
    Locate the app root in both dev and frozen (PyInstaller) modes.
    PyInstaller places data under sys._MEIPASS/app/ per our spec.
    """
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        app_dir = os.path.join(base, "app")
        if os.path.isdir(app_dir):
            return app_dir
        return base
    return os.path.dirname(os.path.abspath(__file__))


_APP_ROOT = _find_app_root()

# Ensure app root is on sys.path so imports work in the frozen bundle
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)

# Default SongFormer path — can be overridden via SONGFORMER_DIR env var
_SONGFORMER_DIR = os.environ.get(
    "SONGFORMER_DIR",
    os.path.join(_APP_ROOT, "SongFormer", "src", "SongFormer"),
)


def _configure_ffmpeg() -> None:
    """
    Ensure pydub can find ffmpeg instantly in the frozen bundle.
    Adds _MEIPASS to PATH so subprocess calls to 'ffmpeg' resolve immediately.
    """
    if not getattr(sys, "frozen", False):
        return
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass and os.path.isfile(os.path.join(meipass, "ffmpeg.exe")):
        os.environ["PATH"] = meipass + os.pathsep + os.environ.get("PATH", "")


def _close_pyinstaller_splash() -> None:
    """Close the PyInstaller native splash screen (frozen builds only)."""
    try:
        import pyi_splash  # type: ignore
        pyi_splash.close()
    except ImportError:
        pass


def main() -> int:
    """Main entry point."""
    # Configure ffmpeg path immediately — before any pydub import
    _configure_ffmpeg()

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("Kling-Match")
    app.setOrganizationName("KlingMatch")

    from kling_match.app_state import AppState
    from kling_match.core.auto_updater import start_update_check
    from kling_match.core.model_downloader import ensure_models
    from kling_match.ui.main_window import MainWindow
    from kling_match.ui.styles import apply_styles

    apply_styles(app)

    # סגור splash לפני חלון ההורדה כדי שהחלון יהיה גלוי
    _close_pyinstaller_splash()

    # בדוק/הורד מודלים לפני פתיחת החלון הראשי
    if not ensure_models(_SONGFORMER_DIR):
        # המשתמש ביטל או ההורדה נכשלה
        return 1

    state = AppState()
    window = MainWindow(state=state, songformer_dir=_SONGFORMER_DIR)

    # הצג את החלון הראשי ועבד אירועים כדי ש-Windows יגדיר אותו כחלון פעיל
    window.show()
    window.raise_()
    window.activateWindow()
    app.processEvents()

    # Open a file if passed as a command-line argument (e.g. double-click)
    _open_file_from_args(window)

    # Background update check (installer/portable builds only)
    start_update_check(parent=window)

    return app.exec()


def _open_file_from_args(window) -> None:
    """Open a file passed as the first command-line argument."""
    args = sys.argv[1:]
    if not args:
        return
    path = args[0]
    if not os.path.isfile(path):
        return
    ext = os.path.splitext(path)[1].lower()
    if ext == ".klng":
        window.open_project_file(path)
    elif ext in (".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"):
        window.open_audio_file(path)


if __name__ == "__main__":
    sys.exit(main())
