@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

:: ── קרא גרסה ─────────────────────────────────────────────────────────────────
set /p VERSION=<version.txt
set VERSION=%VERSION: =%
set TAG=v%VERSION%

echo.
echo ============================================================
echo  Kling-Match %TAG% — GitHub Upload
echo ============================================================

:: ── ודא ש-gh מותקן ───────────────────────────────────────────────────────────
where gh >nul 2>&1
if errorlevel 1 (
    echo ERROR: GitHub CLI ^(gh^) is not installed or not in PATH.
    echo Download from: https://cli.github.com/
    pause & exit /b 1
)

:: ── ודא שכל הקבצים קיימים ────────────────────────────────────────────────────
set INSTALLER=dist\installer\Kling-Match-%VERSION%-setup.exe
set PORTABLE=dist\Kling-Match-%VERSION%-portable.zip
set UPDATE=dist\Kling-Match-%VERSION%-update.zip

set MISSING=0
if not exist "%INSTALLER%" (echo MISSING: %INSTALLER% & set MISSING=1)
if not exist "%PORTABLE%"  (echo MISSING: %PORTABLE%  & set MISSING=1)
if not exist "%UPDATE%"    (echo MISSING: %UPDATE%     & set MISSING=1)

if "%MISSING%"=="1" (
    echo.
    echo Run release_build.bat first to generate the missing files.
    pause & exit /b 1
)

echo.
echo Files to upload:
echo   %INSTALLER%
echo   %PORTABLE%
echo   %UPDATE%
echo.

:: ── צור release ב-GitHub ─────────────────────────────────────────────────────
echo Creating GitHub release %TAG%...
gh release create "%TAG%" ^
    "%INSTALLER%#Kling-Match-%VERSION%-setup.exe" ^
    "%PORTABLE%#Kling-Match-%VERSION%-portable.zip" ^
    "%UPDATE%#update.zip" ^
    --title "Kling-Match %VERSION%" ^
    --notes "Release %VERSION%" ^
    --draft
if errorlevel 1 (
    echo ERROR: gh release create failed.
    echo Make sure you are logged in: gh auth login
    pause & exit /b 1
)

echo.
echo ============================================================
echo  Release %TAG% created as DRAFT on GitHub.
echo  Review and publish at:
echo  https://github.com/Lotzi-tosafix/Kling-Match/releases
echo ============================================================
echo.
pause
