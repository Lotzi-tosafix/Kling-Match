"""
ProjectManager — שמירה וטעינה של פרויקטי קלינג-Match.

מבנה קובץ פרויקט (.klng — JSON):
  {
    "version": 1,
    "project_name": "שם הפרויקט",
    "created_at": "ISO-8601",
    "audio_filename": "song.mp3",          ← שם קובץ השמע בתוך תיקיית הפרויקט
    "audio_duration": 210.5,
    "segments": [
        {"start": 0.0, "end": 18.5, "label": "intro"},
        ...
    ],
    "selected_indices": [1, 2],
    "fade_in": 0.5,
    "fade_out": 0.5,
    "crossfade": 0.0,
    "default_export_format": "mp3"
  }

מבנה תיקיות:
  <Music>/kling-Match/Projects/<project_name>/
    ├── <project_name>.klng      ← קובץ הפרויקט
    └── <audio_filename>         ← עותק של קובץ השמע המקורי
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import List, Optional

from kling_match.models.segment import Segment


# ── קבועים ───────────────────────────────────────────────────────────────────

PROJECT_VERSION = 1
PROJECT_EXT = ".klng"

# תיקיית Projects ברירת מחדל: ~\Music\kling-Match\Projects
def _default_projects_root() -> str:
    music = os.path.join(os.path.expanduser("~"), "Music")
    return os.path.join(music, "Kling-Match", "Projects")


# ── מבנה נתוני פרויקט ────────────────────────────────────────────────────────

@dataclass
class ProjectData:
    """כל הנתונים הנדרשים לשמירה ושחזור פרויקט."""
    project_name: str
    audio_path: str                  # נתיב מקורי (להעתקה)
    audio_duration: float
    segments: List[Segment]
    selected_indices: List[int]
    fade_in: float
    fade_out: float
    crossfade: float
    default_export_format: str = "mp3"


@dataclass
class LoadedProject:
    """תוצאת טעינת פרויקט."""
    project_name: str
    audio_path: str                  # נתיב לקובץ בתיקיית הפרויקט
    audio_duration: float
    segments: List[Segment]
    selected_indices: List[int]
    fade_in: float
    fade_out: float
    crossfade: float
    default_export_format: str = "mp3"


# ── ProjectManager ────────────────────────────────────────────────────────────

class ProjectManager:
    """
    אחראי על שמירה וטעינה של פרויקטים לדיסק.
    כל המתודות הן סטטיות — אין צורך ב-instance.
    """

    @staticmethod
    def default_projects_root() -> str:
        """מחזיר את נתיב תיקיית Projects ברירת מחדל."""
        return _default_projects_root()

    @staticmethod
    def project_dir(project_name: str,
                    projects_root: Optional[str] = None) -> str:
        """מחזיר את נתיב תיקיית הפרויקט (לא יוצר אותה)."""
        root = projects_root or _default_projects_root()
        # ניקוי שמות לא חוקיים ב-Windows
        safe_name = _sanitize_name(project_name)
        return os.path.join(root, safe_name)

    @staticmethod
    def save(data: ProjectData,
             projects_root: Optional[str] = None,
             progress_callback=None) -> str:
        """
        שומר פרויקט לדיסק.

        1. יוצר תיקיית פרויקט
        2. מעתיק קובץ שמע מקורי (אם עוד לא שם)
        3. כותב קובץ .klmatch

        Args:
            data: נתוני הפרויקט
            projects_root: תיקיית Projects בסיסית (None = ברירת מחדל)
            progress_callback: callable(step: str) לעדכון התקדמות

        Returns:
            נתיב לקובץ הפרויקט שנוצר

        Raises:
            ProjectSaveError: בכל שגיאת שמירה
        """
        root = projects_root or _default_projects_root()
        safe_name = _sanitize_name(data.project_name)
        proj_dir = os.path.join(root, safe_name)

        try:
            os.makedirs(proj_dir, exist_ok=True)
        except OSError as e:
            raise ProjectSaveError(f"לא ניתן ליצור תיקיית פרויקט:\n{e}") from e

        # ── העתקת קובץ שמע ──────────────────────────────────────────────
        audio_filename = os.path.basename(data.audio_path)
        dest_audio = os.path.join(proj_dir, audio_filename)

        if progress_callback:
            progress_callback("מעתיק קובץ שמע...")

        if os.path.abspath(data.audio_path) != os.path.abspath(dest_audio):
            try:
                shutil.copy2(data.audio_path, dest_audio)
            except OSError as e:
                raise ProjectSaveError(
                    f"לא ניתן להעתיק את קובץ השמע:\n{e}"
                ) from e

        # ── כתיבת קובץ פרויקט ───────────────────────────────────────────
        if progress_callback:
            progress_callback("שומר קובץ פרויקט...")

        project_file = os.path.join(proj_dir, f"{safe_name}{PROJECT_EXT}")
        payload = {
            "version": PROJECT_VERSION,
            "project_name": data.project_name,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "audio_filename": audio_filename,
            "audio_duration": data.audio_duration,
            "segments": [
                {"start": seg.start, "end": seg.end, "label": seg.label}
                for seg in data.segments
            ],
            "selected_indices": data.selected_indices,
            "fade_in": data.fade_in,
            "fade_out": data.fade_out,
            "crossfade": data.crossfade,
            "default_export_format": data.default_export_format,
        }

        try:
            with open(project_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        except OSError as e:
            raise ProjectSaveError(f"לא ניתן לכתוב קובץ פרויקט:\n{e}") from e

        return project_file

    @staticmethod
    def load(project_file: str) -> LoadedProject:
        """
        טוען פרויקט מקובץ .klmatch.

        Args:
            project_file: נתיב לקובץ .klmatch

        Returns:
            LoadedProject עם כל הנתונים

        Raises:
            ProjectLoadError: אם הקובץ פגום, חסר, או גרסה לא נתמכת
        """
        try:
            with open(project_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise ProjectLoadError(f"לא ניתן לפתוח קובץ פרויקט:\n{e}") from e

        version = data.get("version", 0)
        if version != PROJECT_VERSION:
            raise ProjectLoadError(
                f"גרסת קובץ פרויקט לא נתמכת: {version}\n"
                f"(גרסה נדרשת: {PROJECT_VERSION})"
            )

        # קובץ שמע — בתיקייה שבה נמצא .klmatch
        proj_dir = os.path.dirname(project_file)
        audio_filename = data.get("audio_filename", "")
        audio_path = os.path.join(proj_dir, audio_filename)

        if not os.path.isfile(audio_path):
            raise ProjectLoadError(
                f"קובץ השמע חסר מתיקיית הפרויקט:\n{audio_path}"
            )

        # שחזור קטעים
        try:
            segments = [
                Segment(
                    start=float(s["start"]),
                    end=float(s["end"]),
                    label=str(s["label"]),
                )
                for s in data.get("segments", [])
            ]
        except (KeyError, TypeError, ValueError) as e:
            raise ProjectLoadError(f"נתוני קטעים פגומים:\n{e}") from e

        return LoadedProject(
            project_name=data.get("project_name", ""),
            audio_path=audio_path,
            audio_duration=float(data.get("audio_duration", 0.0)),
            segments=segments,
            selected_indices=list(data.get("selected_indices", [])),
            fade_in=float(data.get("fade_in", 0.0)),
            fade_out=float(data.get("fade_out", 0.0)),
            crossfade=float(data.get("crossfade", 0.5)),
            default_export_format=str(data.get("default_export_format", "mp3")),
        )

    @staticmethod
    def list_projects(projects_root: Optional[str] = None) -> list[str]:
        """
        מחזיר רשימת שמות תיקיות פרויקט קיימות.
        """
        root = projects_root or _default_projects_root()
        if not os.path.isdir(root):
            return []
        return sorted(
            d for d in os.listdir(root)
            if os.path.isdir(os.path.join(root, d))
        )


# ── שגיאות ───────────────────────────────────────────────────────────────────

class ProjectSaveError(Exception):
    """שגיאת שמירת פרויקט."""


class ProjectLoadError(Exception):
    """שגיאת טעינת פרויקט."""


# ── פונקציות עזר ─────────────────────────────────────────────────────────────

_ILLEGAL_CHARS = r'\/:*?"<>|'

def _sanitize_name(name: str) -> str:
    """מנקה שם לשימוש כשם תיקייה ב-Windows."""
    for ch in _ILLEGAL_CHARS:
        name = name.replace(ch, "_")
    name = name.strip(". ")
    return name or "project"
