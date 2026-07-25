"""
יוצר update.zip עם קוד Python בלבד (ללא מודלים/ckpts).
מבנה הzip: app/kling_match/..., app/SongFormer/..., app/version.txt
"""
import zipfile
import os
import sys

# Windows CI environments may default to cp1252 — force UTF-8 output
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# תמיכה בהרצה מכל מיקום — הנתיב יחושב יחסית לשורש הריפו
_repo_root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
_dist_root = os.path.join(_repo_root, "dist", "Kling-Match")

# PyInstaller newer versions use flat layout (app/ directly in dist\Kling-Match\)
# Older versions used _internal\app\ — support both
_flat_app  = os.path.join(_dist_root, "app")
_internal  = os.path.join(_dist_root, "_internal", "app")

if os.path.isdir(_flat_app):
    app_dir = _flat_app
elif os.path.isdir(_internal):
    app_dir = _internal
else:
    print(f"ERROR: לא נמצאה תיקיית app ב-{_dist_root}")
    print(f"  בדקתי: {_flat_app}")
    print(f"  בדקתי: {_internal}")
    sys.exit(1)

out_zip = os.path.join(_repo_root, "dist", "update.zip")

# סיומות שמדלגים עליהן (מודלים כבדים)
SKIP_EXTS = {".pt", ".pth", ".bin", ".safetensors", ".ckpt", ".onnx", ".npy"}

# תיקיות שמדלגים עליהן לחלוטין (ckpts, figs, third_party זה לא קוד)
SKIP_DIRS = {
    "ckpts",       # checkpoints של SongFormer + MusicFM
    "figs",        # תמונות README
}

def should_skip(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    # דלג על תיקיות שברשימה
    for part in parts[:-1]:
        if part in SKIP_DIRS:
            return True
    # דלג על סיומות כבדות
    ext = os.path.splitext(rel_path)[1].lower()
    if ext in SKIP_EXTS:
        return True
    return False

print(f"סורק {app_dir} ...")
count = 0
skipped_bytes = 0
included_bytes = 0

with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for root, dirs, files in os.walk(app_dir):
        # מנע כניסה לתיקיות שברשימה
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for fname in files:
            full_path = os.path.join(root, fname)
            rel = os.path.relpath(full_path, app_dir).replace(os.sep, "/")

            if should_skip(rel):
                skipped_bytes += os.path.getsize(full_path)
                continue

            arcname = "app/" + rel
            zf.write(full_path, arcname)
            included_bytes += os.path.getsize(full_path)
            count += 1
            if count % 100 == 0:
                print(f"  {count} קבצים...", flush=True)

size_mb   = round(os.path.getsize(out_zip) / 1024 / 1024, 1)
skip_mb   = round(skipped_bytes / 1024 / 1024, 0)
incl_mb   = round(included_bytes / 1024 / 1024, 1)

print(f"\nOK - {count} קבצים נכללו ({incl_mb} MB לפני דחיסה)")
print(f"דולגו: {skip_mb} MB של מודלים")
print(f"גודל update.zip: {size_mb} MB")

# ולידציה
print("\nבודק מבנה...")
with zipfile.ZipFile(out_zip, "r") as zf:
    names = zf.namelist()
bad = [n for n in names if not (n.startswith("app/") or n == "app/")]
if bad:
    print(f"ERROR: {len(bad)} רשומות לא מתחילות ב-app/")
else:
    print(f"מבנה תקין - כל {len(names)} רשומות תחת app/")

print("\nדוגמה לתוכן:")
for n in names[:8]:
    print(" ", n)
