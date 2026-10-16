from __future__ import annotations

import numpy as np


def detect_transients(
    audio: np.ndarray,
    sample_rate: int,
    *,
    refine_window_sec: float = 0.015,
) -> list[float]:
    """Sample-precise transient (onset) times in seconds.

    librosa's onset detector gives a frame-accurate estimate (hop-length
    resolution, ~11ms by default); each one is refined to the sample with
    the steepest local rise in amplitude nearby, independent of whichever
    detector produced the raw beat proposal.
    """
    import librosa

    coarse_times = librosa.onset.onset_detect(y=audio, sr=sample_rate, units="time", backtrack=True)
    return [
        _refine_to_sample(audio, sample_rate, float(t), window_sec=refine_window_sec)
        for t in coarse_times
    ]


def _refine_to_sample(
    audio: np.ndarray,
    sample_rate: int,
    approx_time_sec: float,
    *,
    window_sec: float,
) -> float:
    center = int(round(approx_time_sec * sample_rate))
    half_window = max(1, int(round(window_sec * sample_rate)))
    start = max(0, center - half_window)
    end = min(len(audio), center + half_window)
    if end - start < 2:
        return approx_time_sec
    rise = np.diff(np.abs(audio[start:end]))
    return (start + int(np.argmax(rise))) / sample_rate


def snap_to_nearest_transient(
    time_sec: float,
    transient_times: list[float],
    *,
    max_distance_sec: float = 0.05,
) -> float:
    """The nearest transient to `time_sec` if within max_distance_sec,
    otherwise `time_sec` unchanged. Takes a precomputed transient list so
    callers (e.g. live drag-snapping) don't re-run detection per call."""
    if not transient_times:
        return time_sec
    transients = np.asarray(transient_times)
    nearest = float(transients[np.argmin(np.abs(transients - time_sec))])
    return nearest if abs(nearest - time_sec) <= max_distance_sec else time_sec
