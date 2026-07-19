# Release Checklist — Kling-Match

## Every release

1. **Bump version** in `version.txt` and `kling_match/__init__.py`

2. **Build all artifacts**
   ```powershell
   .\build\build.ps1
   ```
   This produces in `dist/`:
   - `Kling-Match-X.Y.Z-setup.exe`      ← full installer  
   - `Kling-Match-X.Y.Z-portable.zip`   ← full portable  
   - `Kling-Match-X.Y.Z-update.zip`     ← app-code patch (small!)

3. **Create GitHub Release**
   - Tag: `vX.Y.Z`
   - Upload **all three** files as release assets
   - The `update.zip` **must** be named exactly `update.zip` in the asset name
     (the auto-updater searches for this exact name)

4. **Write release notes** — shown to users in the update popup

## First-time setup for users

Users download either:
- `setup.exe` → installs to Program Files / AppData, writes `install_type.txt = installer`
- `portable.zip` → extract anywhere, `install_type.txt` already inside = `portable`

Both types receive the same `update.zip` on next update.

## How updates work

1. App starts → `start_update_check()` runs in background thread
2. Calls `GET https://api.github.com/repos/Lotzi-tosafix/Kling-Match/releases/latest`
3. Compares remote tag to local `version.txt`
4. If newer: shows popup with version info + release notes
5. User clicks "Update now" → downloads `update.zip` (~5-30 MB)
6. Extracts `app/` folder, replaces old code, restarts
7. Models (MuQ 1.3GB, MusicFM 1.25GB, SongFormer 100MB) are **never** re-downloaded

## Inno Setup

Download: https://jrsoftware.org/isdl.php  
Install to default path (`C:\Program Files (x86)\Inno Setup 6\`)  
Then run `build.ps1` — it will find it automatically.
