# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for Kling-Match
# Run from repo root: pyinstaller build\Kling-Match.spec --noconfirm

import os
import sys

root     = os.path.dirname(os.path.dirname(os.path.abspath(SPEC)))
site_pkg = os.path.join(os.path.dirname(sys.executable), 'Lib', 'site-packages')

block_cipher = None

# ── אוסף אוטומטית את כל התיקיות מ-site-packages שנמצאות ──────────────────
def _site_datas(*pkg_names):
    """מחזיר רשימת (src, dst) לכל חבילה שנמצאת ב-site-packages."""
    result = []
    for name in pkg_names:
        p = os.path.join(site_pkg, name)
        if os.path.isdir(p):
            result.append((p, name))
    return result


def _songformer_datas(songformer_root, dst_prefix='app/SongFormer'):
    """
    אוסף את כל קבצי SongFormer למעט תיקיית ckpts/ (מודלים כבדים).
    המודלים מורדים בהפעלה ראשונה ולא נארזים ב-EXE.
    """
    SKIP_DIRS = {'ckpts'}
    result = []
    for dirpath, dirnames, filenames in os.walk(songformer_root):
        # מנע כניסה לתיקיות שברשימה
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            src = os.path.join(dirpath, fname)
            rel = os.path.relpath(dirpath, songformer_root).replace('\\', '/')
            if rel == '.':
                dst = dst_prefix
            else:
                dst = dst_prefix + '/' + rel
            result.append((src, dst))
    return result

a = Analysis(
    [os.path.join(root, 'main.py')],
    pathex=[root],
    binaries=[],
    datas=[
        # ── App code ─────────────────────────────────────────────────────
        (os.path.join(root, 'kling_match'),  'app/kling_match'),
        (os.path.join(root, 'version.txt'),  'app'),
        # ── models/ ו-SongFormer/ckpts/ אינם נארזים — מורדים בהפעלה ראשונה
        # ── x_clip data (קובץ BPE) ────────────────────────────────────────
        (os.path.join(site_pkg, 'x_clip', 'data'), 'x_clip/data'),
        # ── soundfile DLL ─────────────────────────────────────────────────
        (os.path.join(site_pkg, '_soundfile_data'), '_soundfile_data'),
        # ── ffmpeg ────────────────────────────────────────────────────────
        (os.environ.get('FFMPEG_EXE',  r'C:\Users\user\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe'),  '.'),
        (os.environ.get('FFPROBE_EXE', r'C:\Users\user\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffprobe.exe'), '.'),
        # ── Splash ────────────────────────────────────────────────────────
        (os.path.join(root, 'build', 'splash.png'),   'build'),
        (os.path.join(root, 'build', 'icon_256.png'), 'build'),
    ] + _songformer_datas(os.path.join(root, 'SongFormer')) + _site_datas(        # כל החבילות שPyInstaller לא אוסף אוטומטית
        'msaf', 'mir_eval', 'jams', 'cvxopt', 'sklearn',
        'vmo', 'networkx', 'x_transformers', 'audioread',
        'pooch', 'platformdirs', 'tqdm', 'packaging',
        'decorator', 'joblib', 'lazy_loader', 'einops',
        'ema_pytorch', 'ftfy', 'omegaconf', 'antlr4',
        'huggingface_hub', 'accelerate',
    ),
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'torch',
        'torchaudio',
        'librosa',
        'pydub',
        'sounddevice',
        'numpy',
        'scipy',
        'omegaconf',
        'safetensors',
        'transformers',
        'ema_pytorch',
        'qtawesome',
        'x_clip',
        'msaf', 'mir_eval', 'jams',
        'cvxopt', 'cvxopt.base', 'cvxopt.blas', 'cvxopt.lapack',
        'sklearn', 'sklearn.mixture', 'sklearn.cluster',
        'sklearn.decomposition', 'sklearn.neighbors',
        'sklearn.utils', 'sklearn.metrics', 'sklearn.preprocessing',
        'vmo', 'networkx',
        'x_transformers', 'audioread', 'soundfile',
        'pooch', 'platformdirs', 'tqdm', 'packaging',
        'decorator', 'joblib', 'lazy_loader', 'einops',
        'ftfy', 'antlr4', 'huggingface_hub', 'accelerate',
    ],
    hookspath=[],
    runtime_hooks=[os.path.join(root, 'build', 'rthook_scipy_compat.py')],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# PyInstaller native splash — appears instantly before Python starts
splash = Splash(
    os.path.join(root, 'build', 'splash.png'),
    binaries=a.binaries,
    datas=a.datas,
    text_pos=None,           # text is already baked into the image
    text_size=11,
    text_color='#87CEFA',
    minify_script=True,
    always_on_top=True,
)

exe = EXE(
    pyz,
    a.scripts,
    splash,
    splash.binaries,
    [],
    exclude_binaries=True,
    name='Kling-Match',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(root, 'build', 'icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Kling-Match',
)
