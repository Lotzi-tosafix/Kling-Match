<div dir="rtl">

# 🎵 Kling-Match

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)](https://github.com/Lotzi-tosafix/Kling-Match/releases)

**Kling-Match** היא אפליקציית דסקטופ חינמית לWindows לחיתוך רינגטונים חכם — האפליקציה מנתחת את מבנה השיר בעזרת AI ומציגה את הקטעים המוזיקליים (פתיח, פזמון, בריג׳ וכו׳), כך שניתן לבחור בדיוק את הקטע הנכון.

---

## ✨ תכונות עיקריות

- **ניתוח מבנה שיר** — זיהוי אוטומטי של קטעים מוזיקליים באמצעות מודל [SongFormer](https://github.com/ASLP-lab/SongFormer)
- **ממשק ויזואלי** — תצוגת גלים (waveform) עם סרגל קטעים אינטראקטיבי
- **עריכה ידנית** — גרירת גבולות קטעים לכיוון הדיוק
- **בחירה מרובה** — ניתן לשרשר מספר קטעים ברינגטון אחד
- **Fade In / Fade Out / Crossfade** — שליטה מלאה על המעברים
- **ייצוא ל-MP3, WAV, M4R** (רינגטון iPhone)
- **תצוגה מקדימה** — השמעת הרינגטון לפני השמירה
- **שמירת פרויקט** — שמירה וטעינה של עבודה בפורמט `.klng`
- **עדכון אוטומטי** — בדיקת עדכונים ברקע והורדה חלקה של הגרסה החדשה
- **מצב בהיר / כהה**

---

## 📥 הורדה והתקנה

גרסה נוכחית: ראה [Releases](https://github.com/Lotzi-tosafix/Kling-Match/releases)

שלושה סוגי שחרור זמינים:

| קובץ | תיאור |
|---|---|
| `Kling-Match-x.x-setup.exe` | מתקין מלא — מומלץ למשתמשים חדשים |
| `Kling-Match-x.x-portable.zip` | גרסה ניידת — חלץ והפעל, ללא התקנה |
| `update.zip` | עדכון קוד בלבד — מוריד האפליקציה אוטומטית |

> **הורדת מודלי AI בהפעלה הראשונה:**
> בהפעלה הראשונה האפליקציה תשאל האם להוריד את מודלי ה-AI הנדרשים (~2.6 GB).
> ההורדה מתבצעת **פעם אחת בלבד** מ-HuggingFace. אם הורדה קודמת נקטעה — היא תמשיך מהנקודה שבה עצרה.

---

## 🚀 שימוש

1. **בחר שיר** — לחץ על "בחר שיר" או גרור קובץ שמע לחלון
   - פורמטים נתמכים: MP3, WAV, FLAC, AAC, OGG, M4A
2. **המתן לניתוח** — ה-AI מזהה את מבנה השיר (לרוב עד כ-30 שניות)
3. **בחר קטעים** — לחץ על קטעים בסרגל הצבעים או בתצוגת הגלים
4. **ערוך** — אפשר להפעיל מצב עריכה וגרור את גבולות הקטעים
5. **הגדר מעברים** — כוונן Fade In, Fade Out, וCrossfade
6. **האזן** — לחץ "תצוגה מקדימה" לפני השמירה
7. **שמור** — בחר פורמט ושמור את הרינגטון

---

## 🖥️ דרישות מערכת

- Windows 10 / 11 (64-bit)
- ~500 MB פנוי בדיסק (לאפליקציה עצמה)
- ~2.6 GB פנוי בדיסק (למודלי AI — הורדה חד-פעמית)
- חיבור לאינטרנט להורדת המודלים בפעם הראשונה

---

## 🔧 הרצה ממקור (מפתחים)

### דרישות מוקדמות

- Python 3.11
- [ffmpeg](https://ffmpeg.org/download.html) — מוסף ל-PATH

### התקנה

```bash
git clone --recurse-submodules https://github.com/Lotzi-tosafix/Kling-Match.git
cd Kling-Match
pip install -r requirements.txt
```

### הרצה

```bash
python main.py
```

---

## 🏗️ בנייה

### EXE (PyInstaller)

```bash
build.bat
```

### קבצי שחרור מלאים (installer + portable + update.zip)

הבנייה מתבצעת אוטומטית ב-GitHub Actions בכל push שמשנה את `version.txt`.
אפשר גם להפעיל ידנית: **Actions → Release Build → Run workflow**

---

## 🧠 מודלי AI

האפליקציה משתמשת בשלושה מודלים:

| מודל | שימוש | גודל |
|---|---|---|
| [SongFormer](https://github.com/ASLP-lab/SongFormer) | ניתוח מבנה שיר | ~100 MB |
| [MuQ](https://huggingface.co/OpenMuQ/MuQ-large-msd-iter) | ייצוג שמע (SSL) | ~1.3 GB |
| [MusicFM](https://huggingface.co/minzwon/MusicFM) | ייצוג שמע (SSL) | ~1.2 GB |

---

## 📁 מבנה הפרויקט

```
Kling-Match/
├── main.py                      # נקודת כניסה
├── version.txt                  # מספר גרסה יחיד לכל הפרויקט
├── requirements.txt
├── kling_match/
│   ├── core/
│   │   ├── audio_processor.py   # עיבוד שמע, בניית רינגטון
│   │   ├── audio_exporter.py    # ייצוא MP3/WAV/M4R
│   │   ├── songformer_wrapper.py# עטיפת מודל ה-AI
│   │   ├── model_downloader.py  # הורדת מודלים בהפעלה ראשונה
│   │   ├── auto_updater.py      # עדכון אוטומטי
│   │   └── project_manager.py   # שמירה/טעינת פרויקטים .klng
│   ├── ui/
│   │   ├── main_window.py       # חלון ראשי
│   │   ├── controls_panel.py    # פאנלים ובקרים
│   │   ├── waveform_widget.py   # תצוגת גלים
│   │   ├── segment_bar.py       # סרגל קטעים
│   │   ├── settings_dialog.py   # פופאפ הגדרות
│   │   └── styles.py            # עיצוב Material 3
│   └── models/
│       └── segment.py           # מודל נתונים לקטע
├── SongFormer/                  # submodule
├── build/
│   ├── Kling-Match.spec         # הגדרות PyInstaller
│   ├── Kling-Match.iss          # סקריפט Inno Setup
│   └── make_update_zip.py       # בניית update.zip
└── .github/
    └── workflows/
        └── release.yml          # GitHub Actions — בנייה ושחרור אוטומטי
```

---

## 📜 רישיון

תוכנה זו מופצת תחת רישיון [GNU General Public License v3.0](LICENSE).

המשמעות בפשטות: אפשר להשתמש, לשנות ולהפיץ את הקוד — אך כל נגזרת חייבת להישאר פתוחה תחת אותו רישיון.

</div>
