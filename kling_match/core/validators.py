"""
פונקציות ולידציה לקלינג-Match.

מכיל ולידציות לפורמט קובץ, גודל קובץ, ערכי Fade ו-Crossfade.
"""

import os
from typing import Set

# פורמטים נתמכים (lowercase)
SUPPORTED_FORMATS: Set[str] = {"mp3", "wav", "flac", "aac", "ogg", "m4a"}

# גבול גודל קובץ: 500MB בבייטים
FILE_SIZE_LIMIT_BYTES: int = 524_288_000  # 500 * 1024 * 1024

# טווחי ולידציה
CROSSFADE_MIN: float = 0.1
CROSSFADE_MAX: float = 5.0

FADE_MIN: float = 0.0
FADE_MAX: float = 10.0

# הודעות שגיאה בעברית
ERROR_MESSAGES = {
    "model_not_found": (
        "מודל SongFormer לא נמצא בנתיב המוגדר.\n"
        "אנא התקן את המודל לפי ההנחיות:\n"
        "1. הורד את המודל מ-ASLP-lab/SongFormer\n"
        "2. הנח את הקבצים בתיקייה: {model_dir}"
    ),
    "unsupported_format": (
        "פורמט הקובץ '{ext}' אינו נתמך.\n"
        "פורמטים נתמכים: MP3, WAV, FLAC, AAC, OGG, M4A"
    ),
    "file_too_large": (
        "גודל הקובץ ({size_mb:.0f}MB) עולה על 500MB.\n"
        "האם להמשיך בטעינה?"
    ),
    "fade_too_long": (
        "משך ה-Fade In ({fi:.1f}s) ו-Fade Out ({fo:.1f}s) יחד\n"
        "עולים על משך הרינגטון ({dur:.1f}s)."
    ),
    "analysis_failed": (
        "ניתוח השיר נכשל.\n"
        "פרטי השגיאה: {error}\n"
        "האם לנסות שוב?"
    ),
}


def validate_file_format(path: str) -> bool:
    """
    בודק אם סיומת הקובץ נתמכת על ידי האפליקציה.

    הבדיקה אינה תלויה ב-case (MP3, mp3, Mp3 — כולם תקינים).

    Args:
        path: נתיב לקובץ (מחרוזת).

    Returns:
        True אם הסיומת שייכת לקבוצת הפורמטים הנתמכים, False אחרת.
    """
    _, ext = os.path.splitext(path)
    # הסר את הנקודה המובילה והמר ל-lowercase
    ext_lower = ext.lstrip(".").lower()
    return ext_lower in SUPPORTED_FORMATS


def validate_file_size(size_bytes: int) -> bool:
    """
    בודק אם גודל הקובץ עולה על 500MB.

    Args:
        size_bytes: גודל הקובץ בבייטים.

    Returns:
        True אם הגודל עולה על 524,288,000 בייטים (500MB) — דורש הצגת אזהרה.
        False אם הגודל תקין (אינו עולה על הגבול).
    """
    return size_bytes > FILE_SIZE_LIMIT_BYTES


def validate_crossfade(value: float) -> bool:
    """
    בודק אם ערך ה-Crossfade נמצא בטווח התקין [0.1, 5.0] שניות.

    Args:
        value: ערך ה-Crossfade בשניות.

    Returns:
        True אם הערך בטווח [0.1, 5.0], False אחרת.
    """
    return CROSSFADE_MIN <= value <= CROSSFADE_MAX


def validate_fade(value: float) -> bool:
    """
    בודק אם ערך Fade In או Fade Out נמצא בטווח התקין [0.0, 10.0] שניות.

    Args:
        value: ערך ה-Fade בשניות.

    Returns:
        True אם הערך בטווח [0.0, 10.0], False אחרת.
    """
    return FADE_MIN <= value <= FADE_MAX


def validate_fade_vs_duration(fade_in: float, fade_out: float, duration: float) -> bool:
    """
    בודק שסכום ה-Fade In וה-Fade Out אינו עולה על משך הרינגטון.

    אם הסכום עולה על המשך, לא ניתן לייצא את הרינגטון.

    Args:
        fade_in: משך Fade In בשניות.
        fade_out: משך Fade Out בשניות.
        duration: משך הרינגטון הכולל בשניות.

    Returns:
        True אם fade_in + fade_out <= duration (תקין, ניתן לייצא).
        False אם הסכום עולה על המשך (שגיאה, יש למנוע ייצוא).
    """
    return fade_in + fade_out <= duration
