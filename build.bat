@echo off
:: מעבר לתיקייה שבה ממוקם קובץ ה-BAT
cd /d "%~dp0"

echo Running PyInstaller build...
pyinstaller build\Kling-Match.spec --noconfirm

echo.
echo Done!
pause