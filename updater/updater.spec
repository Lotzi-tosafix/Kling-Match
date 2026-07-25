# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Kling-Match Updater
# Run from repo root: pyinstaller updater\updater.spec --noconfirm

import os, sys

root     = os.path.dirname(os.path.dirname(os.path.abspath(SPEC)))
site_pkg = os.path.join(os.path.dirname(sys.executable), "Lib", "site-packages")

a = Analysis(
    [os.path.join(root, "updater", "updater.py")],
    pathex=[root],
    binaries=[],
    datas=[],
    hiddenimports=["PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # מוציאים את כל מה שלא צריך — updater קטן ומהיר
        "torch", "torchaudio", "numpy", "scipy", "librosa",
        "transformers", "sklearn", "matplotlib",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="updater",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,          # ללא חלון console
    onefile=True,           # קובץ EXE בודד
    icon=os.path.join(root, "build", "icon.ico"),
)
