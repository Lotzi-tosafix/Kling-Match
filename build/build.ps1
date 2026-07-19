# build.ps1 — Full build pipeline for Kling-Match
#
# Usage:
#   .\build\build.ps1            → builds installer + portable + update.zip
#   .\build\build.ps1 -Target update   → builds only update.zip
#
# Requirements:
#   pip install pyinstaller
#   Inno Setup 6 installed at default path
#
param(
    [string]$Target = "all"   # all | installer | portable | update
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent

# ── Read version ──────────────────────────────────────────────────────────────
$Version = (Get-Content "$Root\version.txt" -Encoding UTF8).Trim()
Write-Host "Building Kling-Match v$Version" -ForegroundColor Cyan

# ── Step 1: PyInstaller ───────────────────────────────────────────────────────
if ($Target -in @("all","installer","portable")) {
    Write-Host "`n[1/4] Running PyInstaller..." -ForegroundColor Yellow
    Push-Location $Root
    pyinstaller build\Kling-Match.spec --noconfirm
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
    Pop-Location
    Write-Host "PyInstaller done." -ForegroundColor Green
}

# ── Step 2: Build update.zip (app code only) ──────────────────────────────────
if ($Target -in @("all","update")) {
    Write-Host "`n[2/4] Building update.zip..." -ForegroundColor Yellow
    $UpdateZip = "$Root\dist\Kling-Match-$Version-update.zip"

    # The update archive contains only the app/ folder
    # (no models/, no launcher EXE)
    $AppDir = "$Root\dist\Kling-Match\app"
    if (-not (Test-Path $AppDir)) {
        # In dev mode, create app/ from source
        $AppDir = "$Root"
        Write-Host "  (Using source directory for update archive)"
    }

    if (Test-Path $UpdateZip) { Remove-Item $UpdateZip }
    Add-Type -Assembly System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory($AppDir, $UpdateZip)
    Write-Host "update.zip → $UpdateZip" -ForegroundColor Green
}

# ── Step 3: Inno Setup installer ─────────────────────────────────────────────
if ($Target -in @("all","installer")) {
    Write-Host "`n[3/4] Building installer with Inno Setup..." -ForegroundColor Yellow
    $ISCC = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if (-not (Test-Path $ISCC)) {
        $ISCC = "C:\Program Files\Inno Setup 6\ISCC.exe"
    }
    if (-not (Test-Path $ISCC)) {
        Write-Warning "Inno Setup not found. Skipping installer build."
        Write-Warning "Download from: https://jrsoftware.org/isdl.php"
    } else {
        & $ISCC "$Root\build\Kling-Match.iss"
        if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
        Write-Host "Installer built." -ForegroundColor Green
    }
}

# ── Step 4: Portable ZIP ──────────────────────────────────────────────────────
if ($Target -in @("all","portable")) {
    Write-Host "`n[4/4] Building portable ZIP..." -ForegroundColor Yellow
    $DistDir    = "$Root\dist\Kling-Match"
    $PortableZip = "$Root\dist\Kling-Match-$Version-portable.zip"

    # Write portable marker
    Copy-Item "$Root\build\install_type_portable.txt" "$DistDir\install_type.txt" -Force

    if (Test-Path $PortableZip) { Remove-Item $PortableZip }
    Add-Type -Assembly System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory($DistDir, $PortableZip)
    Write-Host "Portable ZIP → $PortableZip" -ForegroundColor Green
}

Write-Host "`nAll done. Files in: $Root\dist\" -ForegroundColor Cyan
