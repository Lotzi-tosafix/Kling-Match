import os

dist_dir = r"C:\Users\user\kling-Match\dist\Kling-Match"
portable = r"C:\Users\user\kling-Match\dist\Kling-Match-0.9-portable.zip"

total = 0
for root, dirs, files in os.walk(dist_dir):
    for f in files:
        total += os.path.getsize(os.path.join(root, f))

print(f"גודל לא דחוס:    {round(total/1024/1024/1024, 2)} GB")
print(f"portable.zip:    {round(os.path.getsize(portable)/1024/1024/1024, 2)} GB")
print(f"יחס דחיסה:       {round(os.path.getsize(portable)/total*100, 1)}%")
print()
print("הקבצים הגדולים ביותר:")
sizes = []
for root, dirs, files in os.walk(dist_dir):
    for f in files:
        p = os.path.join(root, f)
        sizes.append((os.path.getsize(p), p))
sizes.sort(reverse=True)
for size, path in sizes[:10]:
    rel = path.replace(dist_dir + "\\", "")
    print(f"  {round(size/1024/1024):5} MB  {rel}")
