from __future__ import annotations

import numpy as np

from beatgrid.detection.base import DetectionResult
from beatgrid.detection.refine import fit_anchor_and_bpm


class BeatThisDetector:
    """Primary detector: Beat This! (ISMIR 2024, CPJKU) — code and weights
    are MIT-licensed, more accurate than DBN-based trackers like madmom's,
    at the cost of a PyTorch dependency. CPU inference is fine: this runs
    once per analysis, not in realtime.

    Beat This! only returns beat (and downbeat) timestamps, no tempo — the
    BPM is estimated from those timestamps via the same linear-regression
    fit (detection.refine) used for multi-anchor tempo-drift segments.
    """

    name = "beat_this"

    def __init__(self, checkpoint: str = "final0", device: str = "cpu") -> None:
        self._checkpoint = checkpoint
        self._device = device
        self._audio2beats = None  # lazy: loading the model is expensive

    def _get_audio2beats(self):
        if self._audio2beats is None:
            from beat_this.inference import Audio2Beats

            self._audio2beats = Audio2Beats(checkpoint_path=self._checkpoint, device=self._device)
        return self._audio2beats

    def detect(self, audio: np.ndarray, sample_rate: int) -> DetectionResult:
        audio2beats = self._get_audio2beats()
        beats, _downbeats = audio2beats(audio, sample_rate)
        beat_times = [float(t) for t in beats]

        if len(beat_times) < 2:
            raise ValueError("Beat This! detected fewer than 2 beats; cannot estimate tempo")

        _anchor_time, bpm = fit_anchor_and_bpm(beat_times, list(range(len(beat_times))))
        return DetectionResult(bpm=bpm, beat_times=beat_times)
