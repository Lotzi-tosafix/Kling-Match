"""
PreviewPlayer — נגן תצוגה מקדימה לרינגטון.

משתמש ב-pygame.mixer להשמעה עם תמיכה מלאה ב-seek.
פולט position_changed כל 50ms ו-playback_finished בסיום ההשמעה.
"""

from __future__ import annotations

import io
import time

from PyQt6.QtCore import QObject, QTimer, pyqtSignal as Signal

# pygame.mixer is initialized lazily on first play() call,
# not at import time, to keep startup and file-load fast.
_mixer_initialized: bool = False


def _ensure_mixer() -> None:
    """Initialize pygame.mixer once, on first use."""
    global _mixer_initialized
    if _mixer_initialized:
        return
    import pygame
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    _mixer_initialized = True


class PreviewPlayer(QObject):
    """
    נגן תצוגה מקדימה המשמיע AudioSegment דרך pygame.mixer.

    תומך ב-seek (קפיצה לנקודת זמן), pause, resume ו-stop.

    Signals:
        position_changed(float): נפלט כל 50ms עם מיקום ההשמעה בשיר המקורי (שניות)
        playback_finished(): נפלט כאשר ההשמעה מסתיימת
    """

    position_changed = Signal(float)
    playback_finished = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        # מצב
        self._is_playing: bool = False
        self._play_start_wall: float = 0.0   # שעון קיר בעת תחילת ההשמעה
        self._seek_offset: float = 0.0        # מיקום ברינגטון בעת ה-seek האחרון (שניות)
        self._duration: float = 0.0           # אורך הרינגטון הכולל (שניות)

        # מפת זמנים: [(ringtone_sec, original_sec), ...]
        self._segment_map: list[tuple[float, float]] = [(0.0, 0.0)]

        # AudioSegment שמור לצורך seek
        self._current_audio: AudioSegment | None = None

        # QTimer לפליטת position_changed כל 50ms
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._on_timer_tick)

        # QTimer לבדיקת סיום השמעה
        self._end_check_timer = QTimer(self)
        self._end_check_timer.setInterval(100)
        self._end_check_timer.timeout.connect(self._check_playback_ended)

    # ------------------------------------------------------------------
    # ממשק ציבורי
    # ------------------------------------------------------------------

    def play(
        self,
        audio,
        segment_map: list[tuple[float, float]] | None = None,
    ) -> None:
        """
        מתחיל השמעה של AudioSegment מההתחלה.

        Args:
            audio: AudioSegment להשמעה
            segment_map: רשימת (ringtone_sec, original_sec) לכל קטע.
                         קובעת את מיקום הסמן בשיר המקורי תוך כדי נגינה.
        """
        self._stop_internal()

        if len(audio) == 0:
            return

        self._current_audio = audio
        self._duration = len(audio) / 1000.0
        self._segment_map = segment_map or [(0.0, 0.0)]

        self._play_from(0.0)

    def seek(self, original_time: float) -> None:
        """
        קפיצה לנקודת זמן בשיר המקורי.

        Args:
            original_time: זמן בשניות בשיר המקורי
        """
        if self._current_audio is None:
            return

        ringtone_time = self._original_to_ringtone(original_time)
        if ringtone_time is None:
            # מחוץ לתחום — עצור
            self.stop()
            return

        was_playing = self._is_playing
        self._stop_internal()

        if was_playing:
            self._play_from(ringtone_time)
        else:
            # לא מנגן — עדכן ויזואלית בלבד
            self.position_changed.emit(original_time)

    def stop(self) -> None:
        """עוצר השמעה ופולט playback_finished."""
        was_playing = self._is_playing
        self._stop_internal()
        if was_playing:
            self.playback_finished.emit()

    def is_playing(self) -> bool:
        return self._is_playing

    # ------------------------------------------------------------------
    # לוגיקה פנימית
    # ------------------------------------------------------------------

    def _play_from(self, ringtone_sec: float) -> None:
        """
        מתחיל השמעה ממיקום נתון ברינגטון (שניות).
        """
        if self._current_audio is None:
            return

        import pygame
        _ensure_mixer()

        start_ms = int(ringtone_sec * 1000)
        chunk = self._current_audio[start_ms:]

        if len(chunk) == 0:
            return

        # המרה ל-WAV ב-memory buffer
        buf = io.BytesIO()
        chunk.export(buf, format="wav")
        buf.seek(0)

        try:
            sound = pygame.mixer.Sound(buf)
            pygame.mixer.Channel(0).play(sound)
        except Exception:
            return

        self._seek_offset = ringtone_sec
        self._play_start_wall = time.monotonic()
        self._is_playing = True

        self._timer.start()
        self._end_check_timer.start()

    def _stop_internal(self) -> None:
        """עוצר pygame ומאפס מצב פנימי ללא פליטת signal."""
        self._timer.stop()
        self._end_check_timer.stop()
        self._is_playing = False
        if _mixer_initialized:
            import pygame
            try:
                pygame.mixer.Channel(0).stop()
            except Exception:
                pass

    def _on_timer_tick(self) -> None:
        """נקרא כל 50ms — מחשב מיקום ופולט position_changed."""
        if not self._is_playing:
            return

        elapsed = time.monotonic() - self._play_start_wall
        ringtone_pos = min(self._seek_offset + elapsed, self._duration)
        original_pos = self._ringtone_to_original(ringtone_pos)
        self.position_changed.emit(original_pos)

    def _check_playback_ended(self) -> None:
        """בודק אם pygame סיים לנגן ופולט playback_finished."""
        if not self._is_playing:
            return

        import pygame
        elapsed = time.monotonic() - self._play_start_wall
        remaining = self._duration - self._seek_offset - elapsed

        channel_busy = pygame.mixer.Channel(0).get_busy()

        if not channel_busy or remaining <= 0:
            self._stop_internal()
            self.playback_finished.emit()

    # ------------------------------------------------------------------
    # ממירי זמן
    # ------------------------------------------------------------------

    def _ringtone_to_original(self, ringtone_sec: float) -> float:
        """ממיר זמן ברינגטון לזמן בשיר המקורי לפי segment_map."""
        if not self._segment_map:
            return ringtone_sec

        for i in range(len(self._segment_map) - 1, -1, -1):
            rt_start, orig_start = self._segment_map[i]
            if ringtone_sec >= rt_start:
                return orig_start + (ringtone_sec - rt_start)

        rt_start, orig_start = self._segment_map[0]
        return orig_start + (ringtone_sec - rt_start)

    def _original_to_ringtone(self, original_sec: float) -> float | None:
        """ממיר זמן בשיר המקורי לזמן ברינגטון. מחזיר None אם מחוץ לתחום."""
        if not self._segment_map:
            return None

        for i, (rt_start, orig_start) in enumerate(self._segment_map):
            rt_end = (
                self._segment_map[i + 1][0]
                if i + 1 < len(self._segment_map)
                else self._duration
            )
            orig_end = orig_start + (rt_end - rt_start)

            if orig_start <= original_sec <= orig_end:
                return rt_start + (original_sec - orig_start)

        return None
