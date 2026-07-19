"""
AppState — מצב מרכזי של אפליקציית קלינג-Match.

מחלקה יחידה (Singleton) המחזיקה את כל מצב האפליקציה
ומשמשת כ-Controller. משתמשת ב-Qt Signals להודיע לרכיבי UI על שינויים.

דרישות: 10.3
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal as Signal

from kling_match.models.segment import Segment


class AppState(QObject):
    """
    מצב מרכזי של האפליקציה.

    מחזיק את כל נתוני המצב ופולט Qt Signals בעת שינויים,
    כך שרכיבי UI יכולים להתחבר ולהגיב לשינויים.
    """

    # ─── Signals ────────────────────────────────────────────────────────────

    # קובץ שמע נטען — שם הקובץ
    file_loaded = Signal(str)

    # ניתוח SongFormer
    analysis_started = Signal()
    analysis_progress = Signal(int)   # אחוז 0-100
    analysis_done = Signal(list)      # List[Segment]
    analysis_failed = Signal(str)     # הודעת שגיאה

    # בחירת קטעים — List[int] אינדקסים נבחרים
    selection_changed = Signal(list)

    # עריכת גבול — אינדקס גבול, זמן חדש בשניות
    boundary_edited = Signal(int, float)

    # אפקטי Fade — fade_in, fade_out בשניות
    fade_changed = Signal(float, float)

    # Crossfade — משך בשניות
    crossfade_changed = Signal(float)

    # מצב תצוגה מקדימה — True=מנגן, False=עצר
    preview_state_changed = Signal(bool)

    # מיקום תצוגה מקדימה — שניות
    preview_position = Signal(float)

    # ─── Constructor ────────────────────────────────────────────────────────

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._init_state()

    def _init_state(self) -> None:
        """אתחול כל שדות המצב לערכי ברירת מחדל."""

        # קובץ שמע
        self.audio_path: Optional[str] = None
        self.audio_duration: float = 0.0
        self.audio_samples: Optional[np.ndarray] = None
        self.audio_sample_rate: int = 44100

        # ניתוח
        self.segments: List[Segment] = []

        # בחירה
        self.selected_indices: List[int] = []

        # עריכה
        self.edit_mode: bool = False

        # אפקטים
        self.fade_in: float = 0.0
        self.fade_out: float = 0.0
        self.crossfade: float = 0.5

        # תצוגה מקדימה
        self.preview_playing: bool = False
        self.preview_position_val: float = 0.0

    # ─── Public API ─────────────────────────────────────────────────────────

    def reset(self) -> None:
        """
        מאפס את כל המצב לערכי ברירת מחדל.

        נקרא כאשר המשתמש לוחץ על "העלה שיר אחר" (דרישה 10.3).
        """
        self._init_state()

    # ─── לוגיקת בחירה ועריכה (דרישות 4.1, 4.2, 4.3, 4.4, 4.5, 5.5, 5.7) ──

    def toggle_segment_selection(self, index: int) -> None:
        """
        בחירה/ביטול בחירה של קטע לפי אינדקס.

        אם הקטע כבר נבחר — מסיר אותו מהבחירה.
        אם הקטע לא נבחר — מוסיף אותו לבחירה.
        פולט selection_changed עם הרשימה המעודכנת.

        Args:
            index: אינדקס הקטע ברשימת segments
        """
        indices = list(self.selected_indices)
        if index in indices:
            indices.remove(index)
        else:
            indices.append(index)
        self.selected_indices = indices
        self.selection_changed.emit(indices)

    def update_boundary(self, boundary_index: int, new_time: float) -> bool:
        """
        עדכון גבול בין קטעים עם ולידציית מינימום 0.5 שניות ושמירת רציפות.

        גבול boundary_index הוא הנקודה בין segments[boundary_index]
        לבין segments[boundary_index + 1].
        לאחר העדכון: segments[boundary_index].end == segments[boundary_index+1].start

        Args:
            boundary_index: אינדקס הגבול (0 = בין קטע 0 לקטע 1)
            new_time: הזמן החדש לגבול בשניות

        Returns:
            True אם העדכון בוצע, False אם נדחה (ולידציה נכשלה)
        """
        _MIN_DURATION = 0.5

        if boundary_index < 0 or boundary_index >= len(self.segments) - 1:
            return False

        left = self.segments[boundary_index]
        right = self.segments[boundary_index + 1]

        # ולידציה: כל קטע חייב להיות לפחות MIN_DURATION שניות
        if new_time - left.start < _MIN_DURATION:
            return False
        if right.end - new_time < _MIN_DURATION:
            return False

        # עדכון עם שמירת רציפות: end[i] == start[i+1]
        left.end = new_time
        right.start = new_time

        self.boundary_edited.emit(boundary_index, new_time)
        return True

    def get_selected_duration(self) -> float:
        """
        חישוב משך כולל של כל הקטעים הנבחרים בשניות.

        Returns:
            סכום משכי הקטעים הנבחרים (בדיוק של מילישניות)
        """
        return sum(
            self.segments[i].duration
            for i in self.selected_indices
            if 0 <= i < len(self.segments)
        )

    def are_selected_adjacent(self) -> bool:
        """
        בדיקה האם כל הקטעים הנבחרים סמוכים זה לזה (ללא פערים).

        קטעים נחשבים סמוכים אם אינדקסיהם הממוינים הם רצף רציף.
        קטע בודד נחשב תמיד סמוך.

        Returns:
            True אם הקטעים סמוכים, False אחרת
        """
        if len(self.selected_indices) <= 1:
            return True
        sorted_idx = sorted(self.selected_indices)
        for i in range(len(sorted_idx) - 1):
            if sorted_idx[i + 1] - sorted_idx[i] != 1:
                return False
        return True
