"""
AudioProcessor — עיבוד שמע: חיתוך, שרשור, Fade, Crossfade ובניית רינגטון.

דרישות: 11.1, 11.2, 11.3, 11.4, 11.5
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from kling_match.models.segment import Segment

if TYPE_CHECKING:
    from pydub import AudioSegment


class AudioProcessor:
    """
    מחלקה סטטית לעיבוד שמע.
    כל המתודות הן @staticmethod ואינן שומרות מצב.
    """

    @staticmethod
    def load_audio(path: str) -> "AudioSegment":
        from pydub import AudioSegment
        return AudioSegment.from_file(path)

    @staticmethod
    def cut_segment(audio: "AudioSegment", start_sec: float, end_sec: float) -> "AudioSegment":
        start_ms = int(round(start_sec * 1000))
        end_ms = int(round(end_sec * 1000))
        return audio[start_ms:end_ms]

    @staticmethod
    def concatenate(segments: List["AudioSegment"]) -> "AudioSegment":
        from pydub import AudioSegment
        if not segments:
            return AudioSegment.empty()
        result = segments[0]
        for seg in segments[1:]:
            result = result + seg
        return result

    @staticmethod
    def apply_fade_in(audio: "AudioSegment", duration_sec: float) -> "AudioSegment":
        if duration_sec <= 0:
            return audio
        return audio.fade_in(int(round(duration_sec * 1000)))

    @staticmethod
    def apply_fade_out(audio: "AudioSegment", duration_sec: float) -> "AudioSegment":
        if duration_sec <= 0:
            return audio
        return audio.fade_out(int(round(duration_sec * 1000)))

    @staticmethod
    def apply_crossfade(
        seg1: "AudioSegment", seg2: "AudioSegment", duration_sec: float
    ) -> "AudioSegment":
        crossfade_ms = int(round(duration_sec * 1000))
        crossfade_ms = min(crossfade_ms, len(seg1), len(seg2))
        if crossfade_ms <= 0:
            return seg1 + seg2
        seg1_body = seg1[:-crossfade_ms]
        seg1_end  = seg1[-crossfade_ms:].fade_out(crossfade_ms)
        seg2_start = seg2[:crossfade_ms].fade_in(crossfade_ms)
        seg2_tail  = seg2[crossfade_ms:]
        return seg1_body + seg1_end.overlay(seg2_start) + seg2_tail

    @staticmethod
    def build_ringtone(
        audio: "AudioSegment",
        selected_segments: List[Segment],
        fade_in: float,
        fade_out: float,
        crossfade: float,
        is_adjacent: bool,
    ) -> "AudioSegment":
        from pydub import AudioSegment
        if not selected_segments:
            return AudioSegment.empty()

        cut_segments = [
            AudioProcessor.cut_segment(audio, seg.start, seg.end)
            for seg in selected_segments
        ]

        result = cut_segments[0]
        for i in range(1, len(cut_segments)):
            prev_seg = selected_segments[i - 1]
            curr_seg = selected_segments[i]
            segs_adjacent = abs(prev_seg.end - curr_seg.start) < 0.05
            if segs_adjacent or crossfade <= 0:
                result = result + cut_segments[i]
            else:
                result = AudioProcessor.apply_crossfade(result, cut_segments[i], crossfade)

        result = AudioProcessor.apply_fade_in(result, fade_in)
        result = AudioProcessor.apply_fade_out(result, fade_out)
        return result
