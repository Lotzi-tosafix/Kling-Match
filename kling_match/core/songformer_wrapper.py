"""
SongFormerWrapper — עטיפה ל-SongFormer ב-QThread נפרד.

מקבל נתיב לקובץ שמע ומחזיר רשימת קטעים (List[Segment]) דרך signal.
מריץ את pipeline SongFormer בתהליכון נפרד כדי לא לחסום את ה-UI.

דרישות: 2.1, 2.2, 2.3, 2.5, 2.6, 2.7
"""

from __future__ import annotations

import math
import os
import sys
from typing import List, Optional, Tuple

from PyQt6.QtCore import QThread, pyqtSignal as Signal

from kling_match.models.segment import Segment

# סוג MsaInfo: רשימת זוגות (timestamp_float, label_string)
MsaInfo = List[Tuple[float, str]]

# ─── Cache גלובלי למודלים ────────────────────────────────────────────────────
# המודלים נטענים פעם אחת ונשמרים כאן כדי לא לטעון מחדש בכל ניתוח
_MODELS_CACHE: dict = {
    "muq": None,
    "musicfm": None,
    "msa": None,
    "hp": None,
    "device": None,
}

# קבועים מ-SongFormer
_AFTER_DOWNSAMPLING_FRAME_RATES: float = 8.333
_DATASET_LABEL: str = "SongForm-HX-8Class"
_DATASET_IDS: List[int] = [5]
_TIME_DUR: int = 420          # חלון עיבוד בשניות
_INPUT_SAMPLING_RATE: int = 24000
_WIN_SIZE: int = 420
_HOP_SIZE: int = 420
_NUM_CLASSES: int = 128
_MODEL_NAME: str = "SongFormer"
_CHECKPOINT: str = "SongFormer.safetensors"
_CONFIG_PATH: str = "SongFormer.yaml"

# גודל תת-חלון לחישוב embeddings — מוגבל לחיסכון בזיכרון RAM
# כל embedding מחושב ב-30s, ואז משורשרים לחלון המלא של 420s
_EMBEDDING_SUB_CHUNK_SEC: int = 30


class SongFormerWrapper(QThread):
    """
    עטיפה ל-SongFormer הרצה ב-QThread נפרד.

    Signals:
        progress (int): אחוז השלמה 0-100
        finished (list): List[Segment] — רשימת קטעים לאחר ניתוח
        error (str): הודעת שגיאה אם הניתוח נכשל
    """

    progress = Signal(int)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, audio_path: str, songformer_dir: str) -> None:
        """
        אתחול ה-wrapper.

        Args:
            audio_path: נתיב לקובץ שמע לניתוח.
            songformer_dir: נתיב לתיקיית src/SongFormer.
        """
        super().__init__()
        self.audio_path = audio_path
        self.songformer_dir = songformer_dir

    # ─── Public API ─────────────────────────────────────────────────────────

    @staticmethod
    def check_model_exists(model_dir: str) -> bool:
        """
        בודק שתיקיית המודל קיימת ומכילה לפחות קובץ Python אחד.

        Args:
            model_dir: נתיב לתיקיית SongFormer (src/SongFormer).

        Returns:
            True אם הנתיב קיים ומכיל לפחות קובץ .py אחד, False אחרת.
        """
        if not os.path.isdir(model_dir):
            return False

        # בדיקה רקורסיבית — חיפוש קובץ .py אחד לפחות בתיקייה
        for _root, _dirs, files in os.walk(model_dir):
            for fname in files:
                if fname.endswith(".py"):
                    return True

        return False

    def run(self) -> None:
        """
        מריץ את pipeline SongFormer בתהליכון נפרד.

        שלבים:
        1. שינוי working directory ו-sys.path לתיקיית SongFormer
        2. ייבוא דינמי של מודולי SongFormer
        3. טעינת מודלים (עם cache גלובלי)
        4. עיבוד בחלונות של 420 שניות עם פליטת progress
        5. המרת MsaInfo לרשימת Segment ופליטת finished

        שגיאות נפלטות דרך error signal.
        working directory משוחזר ב-finally.
        """
        original_dir = os.getcwd()

        try:
            # ─── scipy monkey-patch FIRST — before any other imports ─────────
            # msaf.pymf uses scipy.inf / scipy.float_ removed in scipy >= 1.11
            # This must run before os.chdir and before any msaf-related import.
            try:
                import scipy as _scipy
                import numpy as _np_patch
                if not hasattr(_scipy, "inf"):      _scipy.inf      = _np_patch.inf
                if not hasattr(_scipy, "float_"):   _scipy.float_   = _np_patch.float64
                if not hasattr(_scipy, "int_"):     _scipy.int_     = _np_patch.int_
                if not hasattr(_scipy, "complex_"): _scipy.complex_ = _np_patch.complex128
                if not hasattr(_scipy, "bool_"):    _scipy.bool_    = _np_patch.bool_
                # Patch already-imported msaf submodules if PyInstaller loaded them early
                import sys as _sys_patch
                for _mn, _mod in list(_sys_patch.modules.items()):
                    if _mn.startswith(("msaf", "postprocessing")) and hasattr(_mod, "__dict__"):
                        if "inf" not in _mod.__dict__:
                            _mod.__dict__["inf"] = _np_patch.inf
            except Exception:
                pass

            # ─── שינוי working directory ו-sys.path ──────────────────────────
            os.chdir(self.songformer_dir)
            if self.songformer_dir not in sys.path:
                sys.path.insert(0, self.songformer_dir)
            # הוספת site-packages כדי ש-msaf וספריות אחרות יהיו נגישות
            import site as _site
            _user_site = _site.getusersitepackages()
            if _user_site not in sys.path:
                sys.path.insert(0, _user_site)
            # הוספת third_party ל-sys.path — musicfm ו-MuQ כתת-חבילות
            third_party_dir = os.path.join(
                os.path.dirname(self.songformer_dir), "third_party"
            )
            # third_party עצמה — לגישה ל-musicfm.model.xxx
            if os.path.isdir(third_party_dir) and third_party_dir not in sys.path:
                sys.path.insert(0, third_party_dir)
            # MuQ/src — מכיל את חבילת muq
            muq_src = os.path.join(third_party_dir, "MuQ", "src")
            if os.path.isdir(muq_src) and muq_src not in sys.path:
                sys.path.insert(0, muq_src)

            # ─── ייבוא דינמי של מודולי SongFormer ───────────────────────────
            try:
                import scipy
                import numpy as np
                # monkey-patch BEFORE any msaf/postprocessing import —
                # msaf.pymf uses scipy.inf which was removed in scipy 1.11
                scipy.inf = np.inf                          # type: ignore[attr-defined]
                scipy.float_ = np.float64                  # type: ignore[attr-defined]
                scipy.int_ = np.int_                       # type: ignore[attr-defined]
                scipy.complex_ = np.complex128             # type: ignore[attr-defined]
                # Also patch already-loaded msaf submodules if present
                import sys as _sys
                for _mod_name, _mod in list(_sys.modules.items()):
                    if _mod_name.startswith("msaf") or _mod_name.startswith("postprocessing"):
                        if hasattr(_mod, "inf") and _mod.inf is None:
                            _mod.inf = np.inf

                import importlib
                import torch
                import librosa
                from ema_pytorch import EMA
                from omegaconf import OmegaConf
                from muq import MuQ
                from musicfm.model.musicfm_25hz import MusicFM25Hz
                from postprocessing.functional import postprocess_functional_structure
                from dataset.label2id import (
                    DATASET_ID_ALLOWED_LABEL_IDS,
                    DATASET_LABEL_TO_DATASET_ID,
                )
            except ImportError as exc:
                self.error.emit(
                    f"לא ניתן לייבא את SongFormer.\n"
                    f"ייתכן שמודלי ה-AI לא הורדו.\n"
                    f"הפעל מחדש את Kling-Match כדי להוריד אותם.\n\n"
                    f"פרטי שגיאה: {exc}"
                )
                return

            # ─── טעינת מודלים (עם cache גלובלי) ─────────────────────────────
            self._ensure_models_loaded(
                torch=torch,
                MuQ=MuQ,
                MusicFM25Hz=MusicFM25Hz,
                importlib=importlib,
                OmegaConf=OmegaConf,
                EMA=EMA,
            )

            muq_model = _MODELS_CACHE["muq"]
            musicfm_model = _MODELS_CACHE["musicfm"]
            msa_model = _MODELS_CACHE["msa"]
            hp = _MODELS_CACHE["hp"]
            device = _MODELS_CACHE["device"]

            # ─── טעינת שמע ───────────────────────────────────────────────────
            import numpy as np
            import gc

            wav, _sr = librosa.load(self.audio_path, sr=_INPUT_SAMPLING_RATE)
            audio_duration: float = len(wav) / _INPUT_SAMPLING_RATE

            # ─── חישוב גודל חלון הקשר — 30% מאורך השיר, מעוגל ל-30ש' ───────
            ctx = max(30, min(int(round(audio_duration * 0.30 / 30)) * 30, _WIN_SIZE))
            self._resolved_context_sec = ctx

            # ─── הכנת מבני נתונים לאגירת logits ─────────────────────────────
            total_len = (
                (len(wav) // _INPUT_SAMPLING_RATE) // _TIME_DUR * _TIME_DUR
            ) + _TIME_DUR
            total_frames = math.ceil(total_len * _AFTER_DOWNSAMPLING_FRAME_RATES)

            logits = {
                "function_logits": np.zeros([total_frames, _NUM_CLASSES]),
                "boundary_logits": np.zeros([total_frames]),
            }
            logits_num = {
                "function_logits": np.zeros([total_frames, _NUM_CLASSES]),
                "boundary_logits": np.zeros([total_frames]),
            }

            # הכנת label masks
            dataset_id2label_mask: dict = {}
            for key, allowed_ids in DATASET_ID_ALLOWED_LABEL_IDS.items():
                dataset_id2label_mask[key] = np.ones(_NUM_CLASSES, dtype=bool)
                dataset_id2label_mask[key][allowed_ids] = False

            # ─── לולאת עיבוד בחלונות של WIN_SIZE=420 שניות ───────────────────
            # הכל בבת אחת (כמו האונליין) — כל חלון 420s מועבר ישירות למודל
            # ללא חלוקה לתת-חלונות, כך שה-context window מלא ותוצאות זהות לאונליין.
            total_windows = max(1, math.ceil(audio_duration / _HOP_SIZE))
            lens = 0
            i = 0
            window_idx = 0

            with torch.no_grad():
                while True:
                    # ─── גבולות חלון 420s ───────────────────────────────────
                    win_start_s = i
                    win_end_s = min(i + _WIN_SIZE, math.ceil(audio_duration))
                    start_idx = win_start_s * _INPUT_SAMPLING_RATE
                    end_idx = min(win_end_s * _INPUT_SAMPLING_RATE, len(wav))

                    if start_idx >= len(wav):
                        break
                    if end_idx - start_idx <= 1024:
                        i += _HOP_SIZE
                        window_idx += 1
                        continue

                    # ─── embedding של החלון המלא (420s) בבת אחת ─────────────
                    # אם context_window_sec < WIN_SIZE, מחשבים בחתיכות ומשרשרים.
                    # אם context_window_sec == WIN_SIZE (420), הכל בבת אחת כמו האונליין.
                    ctx = self._resolved_context_sec
                    if ctx >= (win_end_s - win_start_s):
                        # בת אחת — זהה לאונליין
                        audio_seg = torch.tensor(
                            wav[start_idx:end_idx], dtype=torch.float32
                        ).to(device)
                        muq_out = muq_model(audio_seg.unsqueeze(0),
                                            output_hidden_states=True)
                        muq_embd_420s = muq_out["hidden_states"][10]
                        del muq_out
                        torch.cuda.empty_cache()

                        _, mfm_hs = musicfm_model.get_predictions(
                            audio_seg.unsqueeze(0)
                        )
                        musicfm_embd_420s = mfm_hs[10]
                        del mfm_hs, audio_seg
                        torch.cuda.empty_cache()
                        gc.collect()
                    else:
                        # חלונות קטנים — חישוב בחתיכות ושרשור
                        muq_parts: list = []
                        mfm_parts: list = []
                        for sub_s in range(win_start_s, win_end_s, ctx):
                            sub_e = min(sub_s + ctx, win_end_s)
                            s_idx = sub_s * _INPUT_SAMPLING_RATE
                            e_idx = min(sub_e * _INPUT_SAMPLING_RATE, len(wav))
                            if e_idx - s_idx <= 1024:
                                continue
                            chunk = torch.tensor(
                                wav[s_idx:e_idx], dtype=torch.float32
                            ).to(device)
                            muq_out = muq_model(chunk.unsqueeze(0),
                                                output_hidden_states=True)
                            muq_parts.append(muq_out["hidden_states"][10])
                            del muq_out
                            torch.cuda.empty_cache()

                            _, mfm_hs = musicfm_model.get_predictions(
                                chunk.unsqueeze(0)
                            )
                            mfm_parts.append(mfm_hs[10])
                            del mfm_hs, chunk
                            torch.cuda.empty_cache()
                            gc.collect()

                        if not muq_parts:
                            i += _HOP_SIZE
                            window_idx += 1
                            continue
                        muq_embd_420s = torch.cat(muq_parts, dim=1)
                        musicfm_embd_420s = torch.cat(mfm_parts, dim=1)
                        del muq_parts, mfm_parts
                        gc.collect()

                    # ─── תת-חלונות 30s של ה-HOP (לפרטים מקומיים) ───────────
                    wraped_muq: list = []
                    wraped_mfm: list = []

                    for sub_s in range(win_start_s, win_start_s + _HOP_SIZE, 30):
                        sub_e = min(sub_s + 30, win_start_s + _HOP_SIZE)
                        s_idx = sub_s * _INPUT_SAMPLING_RATE
                        e_idx = min(sub_e * _INPUT_SAMPLING_RATE, len(wav))
                        if s_idx >= len(wav) or e_idx - s_idx <= 1024:
                            break

                        chunk = torch.tensor(
                            wav[s_idx:e_idx], dtype=torch.float32
                        ).to(device)

                        muq_out = muq_model(chunk.unsqueeze(0),
                                            output_hidden_states=True)
                        wraped_muq.append(muq_out["hidden_states"][10])
                        del muq_out
                        torch.cuda.empty_cache()

                        _, mfm_hs = musicfm_model.get_predictions(
                            chunk.unsqueeze(0)
                        )
                        wraped_mfm.append(mfm_hs[10])
                        del mfm_hs, chunk
                        torch.cuda.empty_cache()
                        gc.collect()

                    if not wraped_muq:
                        i += _HOP_SIZE
                        window_idx += 1
                        continue

                    wraped_muq_embd = torch.cat(wraped_muq, dim=1)
                    wraped_mfm_embd = torch.cat(wraped_mfm, dim=1)
                    del wraped_muq, wraped_mfm
                    gc.collect()

                    # ─── יישור אורכים ושרשור 4 embeddings ──────────────────
                    all_embds = [
                        wraped_mfm_embd,
                        wraped_muq_embd,
                        musicfm_embd_420s,
                        muq_embd_420s,
                    ]
                    min_len = min(x.shape[1] for x in all_embds)
                    all_embds = [x[:, :min_len, :] for x in all_embds]
                    embd = torch.cat(all_embds, dim=-1)
                    del all_embds, wraped_mfm_embd, wraped_muq_embd
                    del musicfm_embd_420s, muq_embd_420s
                    torch.cuda.empty_cache()
                    gc.collect()

                    # ─── הסקה ───────────────────────────────────────────────
                    dataset_ids = torch.Tensor(_DATASET_IDS).to(
                        device, dtype=torch.long
                    )
                    _msa_info, chunk_logits = msa_model.infer(
                        input_embeddings=embd,
                        dataset_ids=dataset_ids,
                        label_id_masks=torch.Tensor(
                            dataset_id2label_mask[
                                DATASET_LABEL_TO_DATASET_ID[_DATASET_LABEL]
                            ]
                        )
                        .to(device, dtype=bool)
                        .unsqueeze(0)
                        .unsqueeze(0),
                        with_logits=True,
                    )
                    del embd
                    torch.cuda.empty_cache()
                    gc.collect()

                    # ─── אגירת logits ────────────────────────────────────────
                    start_frame = int(i * _AFTER_DOWNSAMPLING_FRAME_RATES)
                    n_frames = chunk_logits["boundary_logits"][0].shape[0]
                    end_frame = min(start_frame + n_frames, total_frames)
                    actual = end_frame - start_frame

                    logits["function_logits"][start_frame:end_frame, :] += (
                        chunk_logits["function_logits"][0][:actual]
                        .detach().cpu().numpy()
                    )
                    logits["boundary_logits"][start_frame:end_frame] = (
                        chunk_logits["boundary_logits"][0][:actual]
                        .detach().cpu().numpy()
                    )
                    logits_num["function_logits"][start_frame:end_frame, :] += 1
                    logits_num["boundary_logits"][start_frame:end_frame] += 1
                    lens += end_frame - start_frame

                    del chunk_logits
                    gc.collect()

                    i += _HOP_SIZE
                    window_idx += 1

                    progress_pct = int(min(window_idx / total_windows * 100, 99))
                    self.progress.emit(progress_pct)

            # ─── ממוצע logits ─────────────────────────────────────────────────
            logits["function_logits"] /= np.maximum(
                logits_num["function_logits"], 1
            )
            logits["boundary_logits"] /= np.maximum(
                logits_num["boundary_logits"], 1
            )

            logits["function_logits"] = torch.from_numpy(
                logits["function_logits"][:min(lens, total_frames)]
            ).unsqueeze(0)
            logits["boundary_logits"] = torch.from_numpy(
                logits["boundary_logits"][:min(lens, total_frames)]
            ).unsqueeze(0)

            # ─── post-processing ──────────────────────────────────────────────
            msa_infer_output: MsaInfo = postprocess_functional_structure(logits, hp)

            # ─── ניקוי קטעים קצרים (rule-based) ─────────────────────────────
            msa_infer_output = self._rule_post_processing(msa_infer_output)

            # ─── המרה לרשימת Segment ─────────────────────────────────────────
            segments = self.msa_to_segments(msa_infer_output, audio_duration)

            self.progress.emit(100)
            self.finished.emit(segments)

        except Exception as exc:
            self.error.emit(str(exc))

        finally:
            os.chdir(original_dir)

    # ─── Private helpers ─────────────────────────────────────────────────────

    def _ensure_models_loaded(
        self,
        torch,
        MuQ,
        MusicFM25Hz,
        importlib,
        OmegaConf,
        EMA,
    ) -> None:
        """
        טוען את המודלים לתוך ה-cache הגלובלי אם עדיין לא נטענו.

        Args:
            torch, MuQ, MusicFM25Hz, importlib, OmegaConf, EMA:
                מודולים שכבר יובאו דינמית ב-run().
        """
        global _MODELS_CACHE

        if _MODELS_CACHE["muq"] is not None:
            return  # כבר נטענו

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        _MODELS_CACHE["device"] = device

        # MuQ — load from local models/ directory
        # חשוב: להעביר Path object ולא str — @validate_hf_hub_args של HF
        # מאמת str כ-repo ID אבל מקבל Path כנתיב מקומי ללא ולידציה
        import sys as _sys
        from pathlib import Path as _Path

        if getattr(_sys, "frozen", False):
            # frozen: models/ נמצא ליד ה-EXE (לא ב-_internal)
            muq_local    = _Path(os.path.dirname(_sys.executable)) / "models" / "MuQ"
            musicfm_dir  = _Path(os.path.dirname(_sys.executable)) / "models" / "MusicFM"
            songformer_ckpt = (
                _Path(os.path.dirname(_sys.executable))
                / "models" / "SongFormer" / "SongFormer.safetensors"
            )
        else:
            _repo_root   = _Path(self.songformer_dir).resolve().parents[3]
            muq_local    = _repo_root / "models" / "MuQ"
            musicfm_dir  = _repo_root / "models" / "MusicFM"
            songformer_ckpt = _repo_root / "models" / "SongFormer" / "SongFormer.safetensors"

        if not muq_local.is_dir():
            raise FileNotFoundError(
                f"תיקיית מודל MuQ לא נמצאה: {muq_local}\n"
                "הפעל מחדש את Kling-Match להורדת המודלים."
            )

        muq = MuQ.from_pretrained(muq_local, local_files_only=True)
        muq = muq.to(device).eval()
        _MODELS_CACHE["muq"] = muq

        # MusicFM
        musicfm = MusicFM25Hz(
            is_flash=False,
            stat_path=str(musicfm_dir / "msd_stats.json"),
            model_path=str(musicfm_dir / "pretrained_msd.pt"),
        )
        musicfm = musicfm.to(device).eval()
        _MODELS_CACHE["musicfm"] = musicfm

        # SongFormer MSA model
        module = importlib.import_module("models." + _MODEL_NAME)
        Model = getattr(module, "Model")
        hp = OmegaConf.load(os.path.join("configs", _CONFIG_PATH))
        msa_model = Model(hp)

        ckpt_path = str(songformer_ckpt)
        if ckpt_path.endswith(".pt"):
            ckpt = torch.load(ckpt_path, map_location=device)
        elif ckpt_path.endswith(".safetensors"):
            from safetensors.torch import load_file
            ckpt = {"model_ema": load_file(ckpt_path, device=str(device))}
        else:
            raise ValueError(f"פורמט checkpoint לא נתמך: {ckpt_path}")

        if ckpt.get("model_ema") is not None:
            model_ema = EMA(msa_model, include_online_model=False)
            model_ema.load_state_dict(ckpt["model_ema"])
            msa_model.load_state_dict(model_ema.ema_model.state_dict())
        else:
            msa_model.load_state_dict(ckpt["model"])

        msa_model.to(device).eval()
        _MODELS_CACHE["msa"] = msa_model
        _MODELS_CACHE["hp"] = hp

    # ─── Static utilities ────────────────────────────────────────────────────

    @staticmethod
    def _rule_post_processing(msa_list: MsaInfo) -> MsaInfo:
        """
        ניקוי rule-based על פלט SongFormer — זהה לאונליין (app.py).

        מסיר קטעים קצרים מאוד מתחילת/סוף הרשימה (פחות משנייה),
        ומאחד קטעים עוקבים עם אותה תווית בתחילה/סוף הרשימה.

        Args:
            msa_list: פלט postprocess_functional_structure.

        Returns:
            MsaInfo מנוקה.
        """
        if len(msa_list) <= 2:
            return msa_list

        result = msa_list.copy()

        # הסרת קטע פתיחה קצר מאוד (פחות משנייה)
        while len(result) > 2:
            first_duration = result[1][0] - result[0][0]
            if first_duration < 1.0:
                result[0] = (result[0][0], result[1][1])
                result = [result[0]] + result[2:]
            else:
                break

        # הסרת קטע סיום קצר מאוד
        while len(result) > 2:
            last_label_duration = result[-1][0] - result[-2][0]
            if last_label_duration < 1.0:
                result = result[:-2] + [result[-1]]
            else:
                break

        # איחוד שני קטעים עוקבים זהים בתחילה (עד 10 שניות)
        while len(result) > 2:
            if result[0][1] == result[1][1] and result[1][0] <= 10.0:
                result = [(result[0][0], result[0][1])] + result[2:]
            else:
                break

        # איחוד שני קטעים עוקבים זהים בסוף (עד 10 שניות)
        while len(result) > 2:
            last_duration = result[-1][0] - result[-2][0]
            if result[-2][1] == result[-3][1] and last_duration <= 10.0:
                result = result[:-2] + [result[-1]]
            else:
                break

        return result

    @staticmethod
    def msa_to_segments(msa_info: MsaInfo, audio_duration: float) -> List[Segment]:
        """
        ממיר MsaInfo לרשימת קטעים רציפים.

        MsaInfo = List[Tuple[float, str]] — רשימת זוגות (timestamp, label).
        הרשומה האחרונה היא (duration, "end") — מדולגת.
        end[i] = start[i+1], קטע אחרון מסתיים ב-audio_duration.

        Args:
            msa_info: פלט SongFormer — רשימת זוגות (timestamp, label).
            audio_duration: משך השמע הכולל בשניות.

        Returns:
            List[Segment]: רשימת קטעים רציפים.

        דרישות: 2.3, 2.7
        """
        segments: List[Segment] = []

        # מדלגים על הרשומה האחרונה ("end")
        for i in range(len(msa_info) - 1):
            start = msa_info[i][0]
            label = msa_info[i][1]

            # end[i] = start[i+1], קטע אחרון מסתיים ב-audio_duration
            if i + 1 < len(msa_info) - 1:
                end = msa_info[i + 1][0]
            else:
                # הקטע לפני "end" — מסתיים ב-audio_duration
                end = audio_duration

            segments.append(Segment(start=start, end=end, label=label))

        return segments
