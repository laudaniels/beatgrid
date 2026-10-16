from __future__ import annotations

import numpy as np

from beatgrid.detection.base import DetectionResult


class LibrosaBeatDetector:
    """Lightweight fallback detector — no PyTorch required. Less accurate
    than Beat This! but a plain `uv sync --extra core` away."""

    name = "librosa"

    def detect(self, audio: np.ndarray, sample_rate: int) -> DetectionResult:
        import librosa

        tempo, beat_times = librosa.beat.beat_track(y=audio, sr=sample_rate, units="time")
        bpm = float(np.asarray(tempo).reshape(-1)[0])
        return DetectionResult(bpm=bpm, beat_times=[float(t) for t in beat_times])
