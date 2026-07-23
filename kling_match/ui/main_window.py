"""
MainWindow — חלון ראשי של קלינג-Match.

פריסה:
  ROW 1 — TopPanel   (בחר שיר | נגן שיר  ···  שם קובץ · אורך)
  ROW 2 — InfoBar    (סטטוס | ProgressBar | ערוך מקטעים)
  ROW 3 — SegmentBar + WaveformWidget
  ROW 4+5 — BottomPanel (סליידרים + כפתורים)
"""

from __future__ import annotations

import json
import os
from typing import Optional

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from kling_match.app_state import AppState
from kling_match.core.audio_exporter import AudioExporter, ExportError
from kling_match.core.audio_processor import AudioProcessor
from kling_match.core.preview_player import PreviewPlayer
from kling_match.core.songformer_wrapper import SongFormerWrapper
from kling_match.core.validators import (
    ERROR_MESSAGES,
    validate_fade_vs_duration,
    validate_file_format,
    validate_file_size,
)
from kling_match.ui.controls_panel import TopPanel, BottomPanel, InfoBar
from kling_match.ui.controls_panel import SaveProjectDialog
from kling_match.ui.segment_bar import SegmentBar
from kling_match.ui.waveform_widget import WaveformWidget

_FILE_FILTER = (
    "קבצי שמע (*.mp3 *.wav *.flac *.aac *.ogg *.m4a);;"
    "כל הקבצים (*)"
)
_PROJECT_FILTER = "פרויקט קלינג-Match (*.klng);;כל הקבצים (*)"
_DEFAULT_SONGFORMER_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "SongFormer", "src", "SongFormer"
)

# ── תיקיות ברירת מחדל ────────────────────────────────────────────────────────
_MUSIC_ROOT      = os.path.join(os.path.expanduser("~"), "Music", "Kling-Match")
_DIR_RINGTONES   = os.path.join(_MUSIC_ROOT, "Ringtones")
_DIR_JSON        = os.path.join(_MUSIC_ROOT, "Json")
_DIR_DOWNLOADS   = os.path.join(os.path.expanduser("~"), "Downloads")


# ── טעינת שמע מהירה — ללא subprocess של ffmpeg ───────────────────────────────
def _load_audio_fast(path: str):
    """
    טוען קובץ שמע ומחזיר (samples_float32, sample_rate, PydubAudioSegment).

    שיטה:
      - soundfile  — WAV / FLAC / OGG (מהיר, pure C, ללא ffmpeg)
      - audioread  — MP3 / AAC / M4A  (משתמש ב-Windows Media Foundation /
                     GStreamer, ללא subprocess של ffmpeg)

    לאחר טעינה, בונה pydub AudioSegment מ-PCM כדי שצינור הייצוא/תצוגה מקדימה
    ימשיך לעבוד כרגיל.
    """
    import numpy as np
    from pydub import AudioSegment as _Pydub

    ext = os.path.splitext(path)[1].lower()

    # --- soundfile מטפל בפורמטים לא דחוסים ----------------------------------------
    _soundfile_formats = {".wav", ".flac", ".ogg", ".aiff", ".aif"}
    if ext in _soundfile_formats:
        import soundfile as sf
        data, sr = sf.read(path, dtype="float32", always_2d=False)
        # המרה ל-pydub: int16 PCM
        pcm = (data * 32767).clip(-32768, 32767).astype(np.int16)
        channels = 1 if pcm.ndim == 1 else pcm.shape[1]
        seg = _Pydub(
            pcm.tobytes(),
            frame_rate=sr,
            sample_width=2,
            channels=channels,
        )
        samples = data if data.ndim == 2 else data
        return samples, sr, seg

    # --- audioread מטפל ב-MP3 / AAC / M4A / פורמטים אחרים -------------------------
    import audioread

    with audioread.audio_open(path) as f:
        sr = f.samplerate
        channels = f.channels
        raw_blocks = []
        for block in f:
            raw_blocks.append(block)

    raw_bytes = b"".join(raw_blocks)
    # audioread מחזיר int16 raw PCM
    pcm_np = np.frombuffer(raw_bytes, dtype=np.int16)

    # בניית pydub AudioSegment
    seg = _Pydub(
        raw_bytes,
        frame_rate=sr,
        sample_width=2,
        channels=channels,
    )

    # samples float32 לצורך Waveform
    samples_f = pcm_np.astype(np.float32)
    if channels == 2:
        samples_f = samples_f.reshape(-1, 2)

    return samples_f, sr, seg


class MainWindow(QMainWindow):

    def __init__(
        self,
        state: AppState,
        songformer_dir: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._state          = state
        self._songformer_dir = songformer_dir or os.path.abspath(_DEFAULT_SONGFORMER_DIR)
        self._analysis_thread: Optional[SongFormerWrapper] = None
        self._preview_player = PreviewPlayer(self)
        self._song_player    = PreviewPlayer(self)
        self._audio_segment  = None

        self.setWindowTitle("Kling-Match")
        self.setMinimumSize(960, 640)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        self._setup_ui()
        self._connect_state_signals()
        self._connect_ui_signals()

    # ── UI setup ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ROW 1 — TopPanel
        self._top = TopPanel()
        lay.addSpacing(50)
        lay.addWidget(self._top)

        # ROW 2 — InfoBar
        self._info_bar = InfoBar()
        lay.addSpacing(30)
        lay.addWidget(self._info_bar)

        # ROW 3a — SegmentBar
        self._segment_bar = SegmentBar()
        self._segment_bar.setFixedHeight(44)
        lay.addSpacing(10)
        lay.addWidget(self._segment_bar)

        # ROW 3b — WaveformWidget (~1/5 גובה מסך)
        self._waveform = WaveformWidget()
        screen_h = QApplication.primaryScreen().availableGeometry().height()
        wf_h = max(180, min(320, screen_h // 4))
        self._waveform.setFixedHeight(wf_h)
        lay.addWidget(self._waveform)

        # ROW 4+5 — BottomPanel
        self._bottom = BottomPanel()
        lay.addWidget(self._bottom)

    # ── Signals ───────────────────────────────────────────────────────────────

    def _connect_state_signals(self) -> None:
        s = self._state
        s.file_loaded.connect(self._on_file_loaded)
        s.analysis_started.connect(self._on_analysis_started)
        s.analysis_progress.connect(self._on_analysis_progress)
        s.analysis_done.connect(self._on_analysis_done)
        s.analysis_failed.connect(self._on_analysis_failed)
        s.selection_changed.connect(self._on_selection_changed)
        s.boundary_edited.connect(self._on_boundary_edited)
        s.fade_changed.connect(self._on_fade_changed)
        s.preview_state_changed.connect(self._on_preview_state_changed)
        s.preview_position.connect(self._waveform.set_playback_position)

    def _connect_ui_signals(self) -> None:
        self._top.upload_clicked.connect(self._open_file_dialog)
        self._top.play_song_clicked.connect(self._on_play_song_clicked)
        self._top.open_project_clicked.connect(self._on_open_project)

        self._info_bar.edit_toggled.connect(self._on_edit_toggled)

        self._bottom.preview_clicked.connect(self._on_preview_clicked)
        self._bottom.stop_clicked.connect(self._on_stop_clicked)
        self._bottom.export_clicked.connect(self._on_export)
        self._bottom.copy_json_clicked.connect(self._on_copy_json)
        self._bottom.save_project_clicked.connect(self._on_save_project)
        self._bottom.fade_in_changed.connect(self._on_fade_in_changed)
        self._bottom.fade_out_changed.connect(self._on_fade_out_changed)
        self._bottom.crossfade_changed.connect(self._on_crossfade_changed)
        self._segment_bar.segment_clicked.connect(self._on_segment_clicked)
        self._waveform.segment_clicked.connect(self._on_segment_clicked)
        self._waveform.boundary_dragged.connect(self._on_boundary_dragged)
        self._waveform.timeline_clicked.connect(self._on_timeline_clicked)
        self._waveform.file_dropped.connect(self._on_file_dropped)

        self._preview_player.position_changed.connect(self._state.preview_position.emit)
        self._preview_player.playback_finished.connect(self._on_playback_finished)

        self._song_player.position_changed.connect(self._waveform.set_playback_position)
        self._song_player.playback_finished.connect(self._on_song_finished)

    # ── Status helpers ────────────────────────────────────────────────────────

    def _show_status(self, msg: str, timeout_ms: int = 0) -> None:
        self._info_bar.set_status(msg, timeout_ms)

    def _clear_status(self) -> None:
        self._info_bar.clear_status()
    # ── Convenience wrappers ──────────────────────────────────────────────────

    def _set_export_enabled(self, v: bool) -> None:
        self._bottom.set_export_enabled(v)

    def _set_json_enabled(self, v: bool) -> None:
        self._bottom.set_json_enabled(v)

    def _set_selection_duration(self, sec: float) -> None:
        self._bottom.set_selection_duration(sec)

    def _set_crossfade_visible(self, v: bool) -> None:
        self._bottom.set_crossfade_enabled(v)

    def _set_preview_playing(self, v: bool) -> None:
        self._bottom.set_preview_playing(v)

    def _set_song_playing(self, v: bool) -> None:
        self._top.set_song_playing(v)

    # ── Mutex ─────────────────────────────────────────────────────────────────

    def _stop_all_players(self) -> None:
        if self._preview_player.is_playing():
            self._preview_player.stop()
            self._state.preview_playing = False
            self._set_preview_playing(False)
        if self._song_player.is_playing():
            self._song_player.stop()
            self._set_song_playing(False)
        self._waveform.set_playback_position(-1.0)

    # ── File loading ──────────────────────────────────────────────────────────

    def _open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "בחר קובץ שמע", _DIR_DOWNLOADS, _FILE_FILTER
        )
        if not path:
            return
        if not validate_file_format(path):
            ext = os.path.splitext(path)[1]
            QMessageBox.warning(self, "פורמט לא נתמך",
                                ERROR_MESSAGES["unsupported_format"].format(ext=ext))
            return
        size = os.path.getsize(path)
        if validate_file_size(size):
            reply = QMessageBox.question(
                self, "קובץ גדול",
                ERROR_MESSAGES["file_too_large"].format(size_mb=size / 1_048_576),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._load_file(path)

    def _load_file(self, path: str) -> None:
        self._stop_all_players()
        self._state.reset()
        self._audio_segment = None

        self._waveform.set_segments([])
        self._waveform.set_selected([])
        self._waveform.set_playback_position(-1.0)
        self._segment_bar.set_segments([])
        self._set_export_enabled(False)
        self._set_json_enabled(False)
        self._set_selection_duration(0.0)
        self._bottom.clear_analysis_time()
        self._info_bar.set_edit_enabled(False)

        try:
            audio_data, sample_rate, self._audio_segment = _load_audio_fast(path)
            self._state.audio_samples     = audio_data
            self._state.audio_sample_rate = sample_rate
            self._state.audio_duration    = len(self._audio_segment) / 1000.0
            self._waveform.set_audio(audio_data, sample_rate)
            self._top.set_file_info(
                os.path.basename(path), self._state.audio_duration
            )
        except Exception as e:
            self._show_error("שגיאת טעינה", f"לא ניתן לטעון את הקובץ:\n{e}")
            return

        self._state.audio_path = path
        self._state.file_loaded.emit(os.path.basename(path))
        self._start_analysis(path)

    def _start_analysis(self, path: str) -> None:
        self._state.analysis_started.emit()
        self._analysis_start_time = __import__("time").monotonic()
        self._analysis_thread = SongFormerWrapper(path, self._songformer_dir)
        self._analysis_thread.progress.connect(self._state.analysis_progress.emit)
        self._analysis_thread.finished.connect(self._on_analysis_finished_raw)
        self._analysis_thread.error.connect(self._state.analysis_failed.emit)
        self._analysis_thread.start()

    def _on_analysis_finished_raw(self, segments: list) -> None:
        import time
        elapsed = time.monotonic() - getattr(self, "_analysis_start_time", 0)
        self._bottom.set_analysis_time(elapsed)
        self._state.segments = segments
        self._state.analysis_done.emit(segments)

    # ── AppState handlers ─────────────────────────────────────────────────────

    def _on_file_loaded(self, filename: str) -> None:
        self._info_bar.set_status(f"נטען: {filename}")

    def _on_analysis_started(self) -> None:
        self._info_bar.set_progress(0)
        self._info_bar.set_progress_visible(True)
        self._info_bar.set_status("מנתח את מבנה השיר...")

    def _on_analysis_progress(self, pct: int) -> None:
        self._info_bar.set_progress(pct)

    def _on_analysis_done(self, segments: list) -> None:
        self._info_bar.set_progress_visible(False)
        self._info_bar.set_edit_enabled(True)
        self._waveform.set_segments(segments)
        self._segment_bar.set_segments(segments)
        self._set_json_enabled(True)
        self._info_bar.set_status(
            f"{len(segments)} קטעים זוהו — לחץ על קטע לבחירה."
        )

    def _on_analysis_failed(self, error_msg: str) -> None:
        self._info_bar.set_progress_visible(False)
        reply = self._show_error(
            "שגיאת ניתוח",
            ERROR_MESSAGES["analysis_failed"].format(error=error_msg),
            icon=QMessageBox.Icon.Critical,
            extra_buttons=QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Retry and self._state.audio_path:
            self._start_analysis(self._state.audio_path)

    def _on_selection_changed(self, indices: list) -> None:
        self._waveform.set_selected(indices)
        self._segment_bar.set_selected(indices)
        has = bool(indices)
        self._set_export_enabled(has)
        self._set_selection_duration(self._state.get_selected_duration())
        non_adj = has and not self._state.are_selected_adjacent()
        self._set_crossfade_visible(non_adj)

    def _on_boundary_edited(self, _idx: int, _t: float) -> None:
        self._waveform.set_segments(self._state.segments)

    def _on_fade_changed(self, fade_in: float, fade_out: float) -> None:
        self._waveform.set_fade_regions(fade_in, fade_out)

    def _on_preview_state_changed(self, playing: bool) -> None:
        self._set_preview_playing(playing)

    # ── UI handlers ───────────────────────────────────────────────────────────

    def _on_file_dropped(self, path: str) -> None:
        if not validate_file_format(path):
            ext = os.path.splitext(path)[1]
            QMessageBox.warning(self, "פורמט לא נתמך",
                                ERROR_MESSAGES["unsupported_format"].format(ext=ext))
            return
        size = os.path.getsize(path)
        if validate_file_size(size):
            reply = QMessageBox.question(
                self, "קובץ גדול",
                ERROR_MESSAGES["file_too_large"].format(size_mb=size / 1_048_576),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._load_file(path)

    def _on_segment_clicked(self, index: int) -> None:
        self._state.toggle_segment_selection(index)

    def _on_boundary_dragged(self, boundary_idx: int, new_time: float) -> None:
        self._state.update_boundary(boundary_idx, new_time)

    def _on_timeline_clicked(self, time_sec: float) -> None:
        if self._preview_player.is_playing():
            self._preview_player.seek(time_sec)
        elif self._song_player.is_playing():
            self._song_player.seek(time_sec)

    def _on_edit_toggled(self, enabled: bool) -> None:
        self._state.edit_mode = enabled
        self._waveform.set_edit_mode(enabled)

    def _on_fade_in_changed(self, value: float) -> None:
        self._state.fade_in = value
        self._state.fade_changed.emit(value, self._state.fade_out)

    def _on_fade_out_changed(self, value: float) -> None:
        self._state.fade_out = value
        self._state.fade_changed.emit(self._state.fade_in, value)

    def _on_crossfade_changed(self, value: float) -> None:
        self._state.crossfade = value

    def _on_copy_json(self) -> None:
        if not self._state.segments:
            self._show_status("אין ניתוח לייצוא — טען שיר קודם.", 3000)
            return
        data = [
            {"start": str(round(s.start, 2)), "end": str(round(s.end, 2)), "label": s.label}
            for s in self._state.segments
        ]
        json_text = json.dumps(data, indent=2, ensure_ascii=False)

        base = os.path.splitext(os.path.basename(self._state.audio_path or "segments"))[0]
        default_name = f"{base}.txt"

        os.makedirs(_DIR_JSON, exist_ok=True)
        save_path, _ = QFileDialog.getSaveFileName(
            self, "שמור ניתוח כ-JSON",
            os.path.join(_DIR_JSON, default_name),
            "קובץ טקסט (*.txt);;כל הקבצים (*)"
        )
        if not save_path:
            return
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(json_text)
            self._show_status(f"נשמר: {os.path.basename(save_path)} ✓", 4000)
        except Exception as e:
            self._show_error("שגיאת שמירה", str(e))

    # ── Play full song ────────────────────────────────────────────────────────

    def _on_play_song_clicked(self) -> None:
        if self._song_player.is_playing():
            self._song_player.stop()
            self._set_song_playing(False)
            self._waveform.set_playback_position(-1.0)
            return
        if not self._audio_segment:
            self._show_status("טען שיר תחילה.", 2500)
            self._set_song_playing(False)
            return
        if self._preview_player.is_playing():
            self._preview_player.stop()
            self._state.preview_playing = False
            self._set_preview_playing(False)
        try:
            self._song_player.play(self._audio_segment, segment_map=[(0.0, 0.0)])
            self._set_song_playing(True)
        except Exception as e:
            self._show_error("שגיאת השמעה", str(e), icon=QMessageBox.Icon.Warning)
            self._set_song_playing(False)

    def _on_song_finished(self) -> None:
        self._set_song_playing(False)
        self._waveform.set_playback_position(-1.0)

    # ── Preview ───────────────────────────────────────────────────────────────

    def _on_preview_clicked(self) -> None:
        if not self._audio_segment or not self._state.selected_indices:
            return
        if self._song_player.is_playing():
            self._song_player.stop()
            self._set_song_playing(False)
        selected_segs = [
            self._state.segments[i]
            for i in sorted(self._state.selected_indices)
            if i < len(self._state.segments)
        ]
        is_adj = self._state.are_selected_adjacent()
        try:
            ringtone = AudioProcessor.build_ringtone(
                self._audio_segment, selected_segs,
                self._state.fade_in, self._state.fade_out,
                self._state.crossfade, is_adj,
            )
            self._state.preview_playing = True
            self._state.preview_state_changed.emit(True)
            segment_map: list[tuple[float, float]] = []
            rt_cursor = 0.0
            xfade = self._state.crossfade if not is_adj else 0.0
            for idx, seg in enumerate(selected_segs):
                segment_map.append((rt_cursor, seg.start))
                dur = seg.end - seg.start
                rt_cursor += (
                    dur - xfade if idx < len(selected_segs) - 1 and not is_adj else dur
                )
            self._preview_player.play(ringtone, segment_map=segment_map)
        except Exception as e:
            self._show_error("שגיאת תצוגה מקדימה", str(e), icon=QMessageBox.Icon.Warning)

    def _on_stop_clicked(self) -> None:
        self._preview_player.stop()

    def _on_playback_finished(self) -> None:
        self._state.preview_playing = False
        self._state.preview_state_changed.emit(False)
        self._waveform.set_playback_position(-1.0)

    # ── Export ────────────────────────────────────────────────────────────────

    def _on_export(self, format_str: str) -> None:
        if not self._audio_segment or not self._state.selected_indices:
            return
        selected_segs = [
            self._state.segments[i]
            for i in sorted(self._state.selected_indices)
            if i < len(self._state.segments)
        ]
        total_dur = sum(s.duration for s in selected_segs)
        if not validate_fade_vs_duration(self._state.fade_in, self._state.fade_out, total_dur):
            QMessageBox.warning(
                self, "שגיאת Fade",
                ERROR_MESSAGES["fade_too_long"].format(
                    fi=self._state.fade_in, fo=self._state.fade_out, dur=total_dur
                ),
            )
            return
        base = os.path.splitext(os.path.basename(self._state.audio_path or "ringtone"))[0]
        default_name = f"{base} - רינגטון.{format_str}"

        os.makedirs(_DIR_RINGTONES, exist_ok=True)
        save_path, _ = QFileDialog.getSaveFileName(
            self, "שמור רינגטון",
            os.path.join(_DIR_RINGTONES, default_name),
            "MP3 (*.mp3)" if format_str == "mp3"
            else "iPhone Ringtone (*.m4r)" if format_str == "m4r"
            else "WAV (*.wav)",
        )
        if not save_path:
            return
        is_adj = self._state.are_selected_adjacent()
        try:
            ringtone = AudioProcessor.build_ringtone(
                self._audio_segment, selected_segs,
                self._state.fade_in, self._state.fade_out,
                self._state.crossfade, is_adj,
            )
        except Exception as e:
            self._show_error("שגיאת עיבוד", str(e))
            return
        try:
            if format_str == "mp3":
                AudioExporter.export_mp3(ringtone, save_path)
            elif format_str == "m4r":
                AudioExporter.export_m4r(ringtone, save_path)
            else:
                AudioExporter.export_wav(ringtone, save_path)
            self._show_status(f"נשמר: {os.path.basename(save_path)} ✓", 4000)
        except ExportError as e:
            self._show_error("שגיאת ייצוא", str(e))

    # ── Project save / load ───────────────────────────────────────────────────

    def _on_save_project(self) -> None:
        from kling_match.core.project_manager import (
            ProjectManager, ProjectData, ProjectSaveError
        )

        if not self._state.audio_path:
            self._show_status("טען שיר תחילה כדי לשמור פרויקט.", 3000)
            return
        if not self._state.segments:
            self._show_status("יש לבצע ניתוח לפני שמירת הפרויקט.", 3000)
            return

        # שם ברירת מחדל — שם הקובץ ללא סיומת
        default_name = os.path.splitext(
            os.path.basename(self._state.audio_path)
        )[0]

        dlg = SaveProjectDialog(default_name=default_name, parent=self)
        if dlg.exec() != SaveProjectDialog.DialogCode.Accepted:
            return

        project_name  = dlg.project_name()
        projects_root = dlg.projects_root()

        data = ProjectData(
            project_name=project_name,
            audio_path=self._state.audio_path,
            audio_duration=self._state.audio_duration,
            segments=list(self._state.segments),
            selected_indices=list(self._state.selected_indices),
            fade_in=self._state.fade_in,
            fade_out=self._state.fade_out,
            crossfade=self._state.crossfade,
            default_export_format=self._bottom._default_format,
        )

        self._show_status("שומר פרויקט...", 0)
        QApplication.processEvents()

        try:
            proj_file = ProjectManager.save(
                data,
                projects_root=projects_root,
                progress_callback=lambda msg: self._show_status(msg),
            )
        except ProjectSaveError as e:
            self._show_error("שגיאת שמירת פרויקט", str(e))
            self._show_status("שמירה נכשלה.", 4000)
            return

        self._show_status(
            f"הפרויקט נשמר: {os.path.basename(proj_file)} ✓", 5000
        )

    def _on_open_project(self) -> None:
        from kling_match.core.project_manager import (
            ProjectManager, ProjectLoadError
        )

        path, _ = QFileDialog.getOpenFileName(
            self, "פתח פרויקט", ProjectManager.default_projects_root(),
            _PROJECT_FILTER
        )
        if not path:
            return

        try:
            proj = ProjectManager.load(path)
        except ProjectLoadError as e:
            self._show_error("שגיאת טעינת פרויקט", str(e))
            return

        self._restore_project(proj)

    def _restore_project(self, proj) -> None:
        """Restore app state from a LoadedProject object (shared by open dialog and CLI open)."""
        # Stop players and reset state
        self._stop_all_players()
        self._state.reset()
        self._audio_segment = None
        self._waveform.set_segments([])
        self._waveform.set_selected([])
        self._waveform.set_playback_position(-1.0)
        self._segment_bar.set_segments([])
        self._set_export_enabled(False)
        self._set_selection_duration(0.0)
        self._info_bar.set_edit_enabled(False)

        # Load audio
        try:
            audio_data, sample_rate, self._audio_segment = _load_audio_fast(proj.audio_path)
            self._state.audio_samples     = audio_data
            self._state.audio_sample_rate = sample_rate
            self._state.audio_duration    = len(self._audio_segment) / 1000.0
            self._waveform.set_audio(audio_data, sample_rate)
            self._top.set_file_info(
                os.path.basename(proj.audio_path), self._state.audio_duration
            )
        except Exception as e:
            self._show_error("שגיאת טעינת שמע", f"לא ניתן לטעון את קובץ השמע:\n{e}")
            return

        # Restore state
        self._state.audio_path      = proj.audio_path
        self._state.segments        = proj.segments
        self._state.fade_in         = proj.fade_in
        self._state.fade_out        = proj.fade_out
        self._state.crossfade       = proj.crossfade

        # Update UI
        self._waveform.set_segments(proj.segments)
        self._segment_bar.set_segments(proj.segments)
        self._info_bar.set_edit_enabled(True)
        self._waveform.set_fade_regions(proj.fade_in, proj.fade_out)

        # Restore default export format
        self._bottom._default_format = proj.default_export_format
        self._bottom._split_save._select_format(proj.default_export_format)

        # Restore selection
        for idx in proj.selected_indices:
            if 0 <= idx < len(proj.segments):
                self._state.selected_indices.append(idx)
        if self._state.selected_indices:
            self._waveform.set_selected(self._state.selected_indices)
            self._segment_bar.set_selected(self._state.selected_indices)
            self._set_export_enabled(True)
            self._set_selection_duration(self._state.get_selected_duration())
            non_adj = not self._state.are_selected_adjacent()
            self._set_crossfade_visible(non_adj)

        self._state.file_loaded.emit(os.path.basename(proj.audio_path))
        self._show_status(
            f"פרויקט נטען: {proj.project_name} — {len(proj.segments)} קטעים.", 5000
        )

    # ── Error dialog ──────────────────────────────────────────────────────────

    def open_project_file(self, path: str) -> None:
        """Open a .klng project file directly (e.g. from command line / Explorer)."""
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self._on_open_project_from_path(path))

    def open_audio_file(self, path: str) -> None:
        """Open an audio file directly (e.g. from command line / Explorer)."""
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self._load_file(path))

    def _on_open_project_from_path(self, path: str) -> None:
        """Load a project from an explicit file path (no dialog)."""
        from kling_match.core.project_manager import ProjectManager, ProjectLoadError
        try:
            proj = ProjectManager.load(path)
        except ProjectLoadError as e:
            self._show_error("Project load error", str(e))
            return
        self._restore_project(proj)

    def _show_error(
        self,
        title: str,
        message: str,
        icon: QMessageBox.Icon = QMessageBox.Icon.Critical,
        extra_buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.NoButton,
    ) -> QMessageBox.StandardButton:
        box = QMessageBox(icon, title, message, parent=self)
        box.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        box.setStandardButtons(
            extra_buttons if extra_buttons != QMessageBox.StandardButton.NoButton
            else QMessageBox.StandardButton.Ok
        )
        copy_btn = box.addButton("העתק שגיאה", QMessageBox.ButtonRole.ActionRole)
        box.exec()
        if box.clickedButton() == copy_btn:
            # מעתיק את הודעת השגיאה בלבד — ללא כותרת וללא שאלות נוספות
            # מוציא שורות שמתחילות ב"האם" (שאלות כמו "האם לנסות שוב?")
            clean_lines = [
                ln for ln in message.splitlines()
                if not ln.strip().startswith("האם")
            ]
            clean_msg = "\n".join(clean_lines).strip()
            QApplication.clipboard().setText(clean_msg)
            return QMessageBox.StandardButton.Ok
        return box.standardButton(box.clickedButton())
