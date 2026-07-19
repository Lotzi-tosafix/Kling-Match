"""
מעתיק את קבצי המודלים שהורדו מ-Downloads למקומם הנכון.
"""
import os, shutil

# ── 1. SongFormer checkpoint ──────────────────────────────────────────────────
src_sf = r"C:\Users\user\Downloads\SongFormer.safetensors"
dst_sf = r"C:\Users\user\kling-Match\SongFormer\src\SongFormer\ckpts\SongFormer.safetensors"
if os.path.exists(src_sf):
    shutil.copy2(src_sf, dst_sf)
    print(f"✓ SongFormer.safetensors copied to ckpts")
else:
    print(f"✗ Not found: {src_sf}")

# ── 2. MuQ model → HuggingFace cache ─────────────────────────────────────────
# HuggingFace שומר מודלים כאן:
# %USERPROFILE%\.cache\huggingface\hub\models--OpenMuQ--MuQ-large-msd-iter\snapshots\<hash>\
# נבנה את המבנה ונשים את הקבצים בתוכו

hf_dir = os.path.join(
    os.environ["USERPROFILE"],
    ".cache", "huggingface", "hub",
    "models--OpenMuQ--MuQ-large-msd-iter",
    "snapshots",
    "main"          # hash מזויף — MuQ.from_pretrained ינסה גם את main
)
os.makedirs(hf_dir, exist_ok=True)

# model.safetensors
src_muq = r"C:\Users\user\Downloads\model.safetensors"
dst_muq = os.path.join(hf_dir, "model.safetensors")
if os.path.exists(src_muq):
    shutil.copy2(src_muq, dst_muq)
    print(f"✓ model.safetensors copied to HuggingFace cache")
else:
    print(f"✗ Not found: {src_muq}")

# config.json
src_cfg = r"C:\Users\user\Downloads\config.json"
dst_cfg = os.path.join(hf_dir, "config.json")
if os.path.exists(src_cfg):
    shutil.copy2(src_cfg, dst_cfg)
    print(f"✓ config.json copied to HuggingFace cache")
else:
    print(f"✗ Not found: {src_cfg}")

print(f"\nMuQ cache dir: {hf_dir}")
print("Done.")
