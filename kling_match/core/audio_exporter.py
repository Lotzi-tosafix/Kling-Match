"""
AudioExporter — ייצוא רינגטון לפורמטים MP3, WAV ו-m4r.

דרישות: 9.4, 9.5, 9.7
"""

import os
import tempfile

from pydub import AudioSegment


class ExportError(Exception):
    """שגיאה בייצוא קובץ שמע."""
    pass


class AudioExporter:
    """
    מחלקה סטטית לייצוא שמע לפורמטים שונים.
    כל המתודות הן @staticmethod ואינן שומרות מצב.
    """

    @staticmethod
    def export_mp3(
        audio: AudioSegment,
        output_path: str,
        bitrate: str = "192k",
    ) -> None:
        """
        מייצא AudioSegment לקובץ MP3.

        Args:
            audio: AudioSegment לייצוא
            output_path: נתיב קובץ הפלט (כולל סיומת .mp3)
            bitrate: קצב סיביות, ברירת מחדל "192k" (דרישה 9.4: לפחות 192kbps)

        Raises:
            ExportError: אם הייצוא נכשל
        """
        try:
            audio.export(output_path, format="mp3", bitrate=bitrate)
        except Exception as exc:
            raise ExportError(
                f"ייצוא MP3 נכשל לנתיב '{output_path}': {exc}"
            ) from exc

    @staticmethod
    def export_wav(
        audio: AudioSegment,
        output_path: str,
    ) -> None:
        """
        מייצא AudioSegment לקובץ WAV ללא דחיסה.

        Args:
            audio: AudioSegment לייצוא
            output_path: נתיב קובץ הפלט (כולל סיומת .wav)

        Raises:
            ExportError: אם הייצוא נכשל
        """
        try:
            audio.export(output_path, format="wav")
        except Exception as exc:
            raise ExportError(
                f"ייצוא WAV נכשל לנתיב '{output_path}': {exc}"
            ) from exc

    @staticmethod
    def export_m4r(
        audio: AudioSegment,
        output_path: str,
    ) -> None:
        """
        מייצא AudioSegment לקובץ m4r (רינגטון iPhone).

        m4r הוא בעצם קובץ m4a (AAC) עם סיומת שונה.
        האלגוריתם:
        1. מייצא כ-m4a (קידוד AAC דרך ffmpeg)
        2. משנה שם לסיומת .m4r

        Args:
            audio: AudioSegment לייצוא
            output_path: נתיב קובץ הפלט (כולל סיומת .m4r)

        Raises:
            ExportError: אם הייצוא נכשל
        """
        base, _ = os.path.splitext(output_path)
        final_path = base + ".m4r"

        output_dir = os.path.dirname(os.path.abspath(final_path))
        tmp_fd, tmp_m4a_path = tempfile.mkstemp(suffix=".m4a", dir=output_dir)
        os.close(tmp_fd)

        try:
            audio.export(
                tmp_m4a_path,
                format="mp4",
                codec="aac",
            )
            if os.path.exists(final_path):
                os.remove(final_path)
            os.rename(tmp_m4a_path, final_path)
        except Exception as exc:
            if os.path.exists(tmp_m4a_path):
                try:
                    os.remove(tmp_m4a_path)
                except OSError:
                    pass
            raise ExportError(
                f"ייצוא m4r נכשל לנתיב '{final_path}': {exc}"
            ) from exc
