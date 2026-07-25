@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

:: ── קרא גרסה מ-version.txt ──────────────────────────────────────────────────
set /p VERSION=<version.txt
set VERSION=%VERSION: =%
echo.
echo ============================================================
echo  Kling-Match v%VERSION% — Build Pipeline
echo ============================================================

:: ── ודא ש-dist\Kling-Match קיים (חייב להריץ build.bat קודם) ────────────────
if not exist "dist\Kling-Match\Kling-Match.exe" (
    echo ERROR: dist\Kling-Match\Kling-Match.exe not found.
    echo Run build.bat first to build with PyInstaller.
    pause & exit /b 1
)

:: ── הסר מודלים מה-dist לפני הבנייה ─────────────────────────────────────────
:: המודלים יורדים בזמן ריצה ואין לכלול אותם בשחרור (יגדילו אותו ב-~2.6 GB)
if exist "dist\Kling-Match\models" (
    echo Removing dist\Kling-Match\models\ from release build...
    rmdir /s /q "dist\Kling-Match\models"
)

:: ── שלב 1: בנה updater.exe ──────────────────────────────────────────────────
echo.
echo [1/4] Building updater.exe...
pyinstaller updater\updater.spec --noconfirm
if errorlevel 1 (
    echo ERROR: updater build failed.
    pause & exit /b 1
)
echo updater.exe — Done.

:: ── שלב 2: update.zip ────────────────────────────────────────────────────────
echo.
echo [2/4] Building update.zip...
python build\make_update_zip.py
if errorlevel 1 (
    echo ERROR: make_update_zip.py failed.
    pause & exit /b 1
)
:: שנה שם ל-Kling-Match-update.zip
copy /y "dist\update.zip" "dist\Kling-Match-update.zip"
del "dist\update.zip"
echo update.zip — Done.

:: ── שלב 3: Inno Setup installer ──────────────────────────────────────────────
echo.
echo [3/4] Building installer...
set ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=C:\Program Files\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" (
    echo WARNING: Inno Setup not found — skipping installer.
    echo Download from: https://jrsoftware.org/isdl.php
    goto :portable
)
"%ISCC%" "build\Kling-Match.iss"
if errorlevel 1 (
    echo ERROR: Inno Setup failed.
    pause & exit /b 1
)
echo Installer — Done.

:: ── שלב 4: Portable ZIP ──────────────────────────────────────────────────────
:portable
echo.
echo [4/4] Building portable ZIP...

:: כתוב סמן portable
copy /y "build\install_type_portable.txt" "dist\Kling-Match\install_type.txt"

:: צור portable.zip דרך Python
set PORTABLE_ZIP=dist\Kling-Match-portable.zip
if exist "%PORTABLE_ZIP%" del "%PORTABLE_ZIP%"
python -c "import shutil, os; shutil.make_archive(os.path.join('dist', 'Kling-Match-portable'), 'zip', os.path.join('dist', 'Kling-Match'))"
if errorlevel 1 (
    echo ERROR: Failed to create portable ZIP.
    pause & exit /b 1
)
echo Portable ZIP — Done.

:: ── סיכום ────────────────────────────────────────────────────────────────────
echo.
echo ============================================================
echo  Build complete! Files in dist\:
echo.
dir /b dist\*.zip dist\installer\*.exe 2>nul
echo ============================================================
echo.
pause
